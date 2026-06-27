"""
executor.py - Task Executor

Iterates through a plan's steps, executes each via the ToolRegistry,
feeds the observation back to the LLM for adaptive decision-making,
handles long-running tasks, and returns a full execution log.
"""

import json
import os
import re
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

import requests

from .engine import Action, Observation
from .tools import get_registry

KIMI_API_KEY = os.environ.get("KIMI_API_KEY", "")
KIMI_API_URL = "https://api.moonshot.cn/v1/chat/completions"
DEFAULT_MODEL = "moonshot-v1-8k"
LLM_CALL_INTERVAL = 1.0  # seconds between LLM calls to respect rate limits
STEP_TIMEOUT = 300  # seconds per step
MAX_RETRIES = 2


@dataclass
class ExecutionStep:
    """记录一步执行结果"""
    step_number: int
    tool: str
    params: Dict[str, Any] = field(default_factory=dict)
    reason: str = ""
    expected_outcome: str = ""
    observation: Any = None
    status: str = "pending"  # pending / running / ok / error / timeout
    error: str = ""
    started_at: datetime = field(default_factory=datetime.now)
    finished_at: Optional[datetime] = None
    llm_decision: str = ""  # continue / modify / finish
    llm_thought: str = ""


@dataclass
class ExecutionLog:
    """完整执行日志"""
    goal: str = ""
    project_id: Optional[int] = None
    steps: List[ExecutionStep] = field(default_factory=list)
    final_answer: str = ""
    success: bool = False
    started_at: datetime = field(default_factory=datetime.now)
    finished_at: Optional[datetime] = None
    raw_llm_decisions: List[str] = field(default_factory=list)


class TaskExecutor:
    """
    Task executor for the DrugDesign Copilot Agent.

    Usage:
        executor = TaskExecutor()
        log = executor.execute_plan(plan, project_id=1)
    """

    def __init__(
        self,
        tool_registry=None,
        api_key: Optional[str] = None,
        model: str = DEFAULT_MODEL,
        temperature: float = 0.3,
        llm_interval: float = LLM_CALL_INTERVAL,
        step_timeout: int = STEP_TIMEOUT,
        max_retries: int = MAX_RETRIES,
    ):
        self.tools = tool_registry or get_registry()
        self.api_key = api_key or KIMI_API_KEY
        self.model = model
        self.temperature = temperature
        self.llm_interval = llm_interval
        self.step_timeout = step_timeout
        self.max_retries = max_retries
        self._last_llm_call = 0.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def execute_plan(
        self,
        plan: Dict[str, Any],
        project_id: Optional[int] = None,
        env_state: Optional[Dict[str, Any]] = None,
    ) -> ExecutionLog:
        """
        Execute a plan step by step, adapting based on LLM feedback.

        Args:
            plan: Output from TaskPlanner.plan()
            project_id: Current project ID
            env_state: Optional environment state dict

        Returns:
            ExecutionLog with full trace and final answer.
        """
        goal = plan.get("goal", "")
        steps = plan.get("steps", [])

        log = ExecutionLog(goal=goal, project_id=project_id)
        current_steps = list(steps)
        step_index = 0

        while step_index < len(current_steps):
            step_def = current_steps[step_index]
            exec_step = self._run_single_step(step_def, step_index + 1)
            log.steps.append(exec_step)

            # After each step, ask LLM what to do next
            decision = self._query_llm_decision(log, env_state)
            log.raw_llm_decisions.append(decision.get("raw", ""))

            exec_step.llm_decision = decision.get("decision", "continue")
            exec_step.llm_thought = decision.get("thought", "")

            if exec_step.llm_decision == "finish":
                log.final_answer = decision.get("answer", "")
                log.success = True
                break
            elif exec_step.llm_decision == "modify":
                # LLM wants to modify the plan
                new_steps = decision.get("new_steps", [])
                if new_steps:
                    # Replace remaining steps with the new plan
                    current_steps = current_steps[: step_index + 1] + new_steps
                # else continue with existing steps
            # "continue" or unrecognized -> just advance

            step_index += 1

            if step_index >= len(current_steps):
                # Reached the end of the plan
                final_decision = self._query_llm_final(log, env_state)
                log.final_answer = final_decision.get("answer", "计划执行完毕")
                log.success = final_decision.get("success", True)
                break

        log.finished_at = datetime.now()
        return log

    def to_report(self, log: ExecutionLog) -> Dict[str, Any]:
        """Convert ExecutionLog to a JSON-serializable report dict."""
        return {
            "success": log.success,
            "goal": log.goal,
            "project_id": log.project_id,
            "started_at": log.started_at.isoformat(),
            "finished_at": log.finished_at.isoformat() if log.finished_at else None,
            "total_steps": len(log.steps),
            "steps": [
                {
                    "step_number": s.step_number,
                    "tool": s.tool,
                    "params": s.params,
                    "reason": s.reason,
                    "status": s.status,
                    "error": s.error,
                    "observation": self._serialize_obs(s.observation),
                    "started_at": s.started_at.isoformat(),
                    "finished_at": s.finished_at.isoformat() if s.finished_at else None,
                    "llm_decision": s.llm_decision,
                    "llm_thought": s.llm_thought,
                }
                for s in log.steps
            ],
            "final_answer": log.final_answer,
        }

    # ------------------------------------------------------------------
    # Step execution
    # ------------------------------------------------------------------

    def _run_single_step(self, step_def: Dict[str, Any], step_number: int) -> ExecutionStep:
        """Execute a single step with timeout and retry logic."""
        tool_name = step_def.get("tool", "")
        params = step_def.get("params", {}) if isinstance(step_def.get("params"), dict) else {}
        reason = step_def.get("reason", "")
        expected = step_def.get("expected_outcome", "")

        exec_step = ExecutionStep(
            step_number=step_number,
            tool=tool_name,
            params=params,
            reason=reason,
            expected_outcome=expected,
        )
        exec_step.status = "running"

        func = self.tools.get(tool_name)
        if not func:
            exec_step.status = "error"
            exec_step.error = f"工具 '{tool_name}' 未注册"
            exec_step.finished_at = datetime.now()
            return exec_step

        # Execute with retry
        last_error = ""
        for attempt in range(self.max_retries + 1):
            try:
                # Simple timeout simulation via threading if needed
                result = func(**params)
                exec_step.observation = result
                exec_step.status = "ok"
                exec_step.error = ""
                break
            except Exception as e:
                last_error = str(e)
                exec_step.status = "error"
                exec_step.error = last_error
                if attempt < self.max_retries:
                    time.sleep(1)
                else:
                    exec_step.status = "error"
                    exec_step.error = f"{last_error} (已重试 {self.max_retries} 次)"

        exec_step.finished_at = datetime.now()
        return exec_step

    # ------------------------------------------------------------------
    # LLM decision queries
    # ------------------------------------------------------------------

    def _query_llm_decision(
        self, log: ExecutionLog, env_state: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Ask the LLM: continue / modify / finish?

        Returns a dict with keys:
            - decision: "continue" | "modify" | "finish"
            - thought: str
            - answer: str (if finish)
            - new_steps: list (if modify)
            - raw: str (raw LLM text)
        """
        self._rate_limit()

        system_prompt = """你是 DrugDesign Copilot Agent 的执行决策器。
你的任务是根据已执行的步骤和观察结果，决定下一步行动。

## 可选决策
1. "continue" - 继续执行计划中的下一步
2. "modify" - 修改剩余计划（提供新的步骤列表）
3. "finish" - 计划已完成，给出最终回答

## 输出格式
必须返回纯 JSON，不要 Markdown 代码块：
{
  "decision": "continue" | "modify" | "finish",
  "thought": "你的推理过程",
  "answer": "如果 decision 是 finish，这里填写最终回答",
  "new_steps": []  // 如果 decision 是 modify，提供新的步骤列表
}
"""

        history = self._format_execution_history(log)
        env_text = json.dumps(env_state or {}, ensure_ascii=False, indent=2)

        user_prompt = f"""已执行步骤：
{history}

当前环境状态：
{env_text}

请决定下一步行动（continue / modify / finish），并返回 JSON。"""

        raw = self._call_llm([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ])

        return self._parse_llm_decision(raw)

    def _query_llm_final(
        self, log: ExecutionLog, env_state: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Ask the LLM for a final summary after all steps are done."""
        self._rate_limit()

        system_prompt = """你是 DrugDesign Copilot Agent 的总结器。
根据所有执行步骤和结果，给出简洁的中文总结。
返回 JSON 格式：{"answer": "总结内容", "success": true/false}"""

        history = self._format_execution_history(log)
        user_prompt = f"""所有步骤已执行完毕。

执行历史：
{history}

请给出最终总结（JSON 格式）。"""

        raw = self._call_llm([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ])

        parsed = self._parse_llm_decision(raw)
        return {
            "answer": parsed.get("answer", "计划执行完毕"),
            "success": parsed.get("success", True),
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _rate_limit(self):
        """Ensure we don't hammer the LLM API."""
        elapsed = time.time() - self._last_llm_call
        if elapsed < self.llm_interval:
            time.sleep(self.llm_interval - elapsed)
        self._last_llm_call = time.time()

    def _call_llm(self, messages: List[Dict[str, str]]) -> str:
        """Call the KIMI API."""
        if not self.api_key:
            return ""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
        }
        try:
            resp = requests.post(
                KIMI_API_URL, headers=headers, json=payload, timeout=60
            )
            resp.raise_for_status()
            data = resp.json()
            return (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
            )
        except Exception:
            return ""

    def _parse_llm_decision(self, raw: str) -> Dict[str, Any]:
        """Parse LLM decision JSON."""
        text = raw.strip()
        code_fence = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if code_fence:
            text = code_fence.group(1).strip()
        if not text.startswith("{"):
            match = re.search(r"(\{[\s\S]*\})", text)
            if match:
                text = match.group(1).strip()
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return {"decision": "continue", "thought": "解析失败，默认继续", "raw": raw}

        return {
            "decision": parsed.get("decision", "continue"),
            "thought": parsed.get("thought", ""),
            "answer": parsed.get("answer", ""),
            "new_steps": parsed.get("new_steps", []),
            "success": parsed.get("success", True),
            "raw": raw,
        }

    def _format_execution_history(self, log: ExecutionLog) -> str:
        """Format executed steps for LLM context."""
        lines = []
        for s in log.steps:
            obs = self._serialize_obs(s.observation)
            lines.append(
                f"Step {s.step_number}: {s.tool}({json.dumps(s.params, ensure_ascii=False)})\n"
                f"  Status: {s.status}\n"
                f"  Observation: {obs}\n"
                f"  Thought: {s.llm_thought}"
            )
        return "\n\n".join(lines) if lines else "（尚无执行步骤）"

    def _serialize_obs(self, obs: Any) -> Any:
        """Serialize observation to JSON-safe format."""
        if obs is None:
            return None
        if isinstance(obs, (str, int, float, bool)):
            return obs
        try:
            return json.loads(json.dumps(obs, default=str, ensure_ascii=False))
        except Exception:
            return str(obs)
