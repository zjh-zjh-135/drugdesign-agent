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
                # 防御：确保 new_steps 是列表，且每个元素是字典
                if isinstance(new_steps, list) and new_steps:
                    new_steps = [s for s in new_steps if isinstance(s, dict) and s.get("tool")]
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
        
        # 增强最终回答：如果 LLM 总结没有包含具体数据，追加格式化结果
        enriched_answer = self._enrich_final_answer(log)
        if enriched_answer:
            log.final_answer = enriched_answer
        
        # 生成前端动作（带异常保护，防止 action_protocol 中的类型错误）
        try:
            from .action_protocol import ActionGenerator
            action_gen = ActionGenerator()
            frontend_actions = action_gen.generate_from_result(
                execution_report={
                    "success": log.success,
                    "goal": log.goal,
                    "project_id": log.project_id,
                    "steps": [
                        {
                            "step_number": s.step_number,
                            "tool": s.tool,
                            "params": s.params if isinstance(s.params, dict) else {},
                            "reason": s.reason,
                            "status": s.status,
                            "error": s.error,
                            "observation": self._serialize_obs(s.observation),
                        }
                        for s in log.steps
                    ],
                    "final_answer": log.final_answer,
                },
                env_state={"project_id": log.project_id},
                goal=log.goal,
            )
        except Exception as e:
            print(f"[ActionGenerator Error] {e}")
            frontend_actions = []
        
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
                    "params": s.params if isinstance(s.params, dict) else {},
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
            "actions": [a.to_dict() for a in frontend_actions],
        }

    # ------------------------------------------------------------------
    # Step execution
    # ------------------------------------------------------------------

    def _run_single_step(self, step_def: Dict[str, Any], step_number: int) -> ExecutionStep:
        """Execute a single step with timeout and retry logic."""
        # 防御：确保 step_def 是字典
        if not isinstance(step_def, dict):
            exec_step = ExecutionStep(
                step_number=step_number,
                tool="unknown",
                params={},
                reason="Invalid step definition",
                expected_outcome="",
            )
            exec_step.status = "error"
            exec_step.error = f"Step definition is not a dict: {type(step_def)}"
            exec_step.finished_at = datetime.now()
            return exec_step
        
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
        Enhanced with error recovery: if the last step failed, ask LLM to repair.
        """
        self._rate_limit()

        # 检查最后一步是否失败
        last_step = log.steps[-1] if log.steps else None
        step_failed = last_step and last_step.status == "error"
        failure_info = ""
        if step_failed:
            failure_info = f"\n\n⚠️ 注意：上一步执行失败！\n工具：{last_step.tool}\n错误：{last_step.error}\n参数：{json.dumps(last_step.params, ensure_ascii=False)}\n\n请决定：\n- 如果失败是因为缺少必要信息（如缺少 project_id），建议用 modify 生成获取信息的步骤\n- 如果失败是不可修复的（如项目不存在），建议 finish 并告知用户\n- 如果失败可以重试，建议 continue"

        system_prompt = f"""你是 DrugDesign Copilot Agent 的执行决策器。
你的任务是根据已执行的步骤和观察结果，决定下一步行动。

## 可选决策
1. "continue" - 继续执行计划中的下一步
2. "modify" - 修改剩余计划（如修复失败、调整策略）
3. "finish" - 计划已完成或无法继续，给出最终回答

{f"## 当前状态：上一步失败，需要修复。" if step_failed else ""}

## 输出格式
必须返回纯 JSON，不要 Markdown 代码块：
{{
  "decision": "continue" | "modify" | "finish",
  "thought": "你的推理过程",
  "answer": "如果 decision 是 finish，这里填写最终回答",
  "new_steps": []  // 如果 decision 是 modify，提供新的步骤列表
}}
"""

        history = self._format_execution_history(log)
        env_text = json.dumps(env_state or {}, ensure_ascii=False, indent=2)

        user_prompt = f"""已执行步骤：
{history}

当前环境状态：
{env_text}
{failure_info}

请决定下一步行动（continue / modify / finish），并返回 JSON。"""

        raw = self._call_llm([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ])

        return self._parse_llm_decision(raw)

    def _query_llm_final(
        self, log: ExecutionLog, env_state: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Ask the LLM for a final summary with insightful analysis after all steps are done."""
        self._rate_limit()

        system_prompt = """你是 DrugDesign Copilot Agent 的总结分析师。

你的任务是根据所有执行步骤和结果，给出专业、详细、有洞察力的中文总结。

总结要求：
1. 简要说明做了什么（执行了哪些操作）
2. 关键数据和发现（用数字说话，必须列出具体的分子名称、SMILES、对接分数、ADMET分数等实际数据）
3. 专业解读和洞察（为什么这个结果重要）
4. 下一步建议（如果有的话）
5. 使用 Markdown 格式，层次清晰

特别重要：如果执行步骤中包含了具体的查询结果（如 get_top_molecules 的分子列表、get_project_status 的项目数据），必须在总结中完整列出这些实际结果，不要只给一个泛泛的总结。如果 Pipeline 刚完成，请列出具体的 Top 候选分子的完整信息。

返回 JSON 格式：{"answer": "总结内容（Markdown）", "success": true/false}"""

        history = self._format_execution_history(log)
        env_text = json.dumps(env_state or {}, ensure_ascii=False, indent=2)
        user_prompt = f"""所有步骤已执行完毕。

执行历史：
{history}

环境状态：
{env_text}

请给出专业、详细的总结分析（JSON 格式，answer 字段包含 Markdown 格式内容）。"""

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

        # 防御：确保解析结果是字典，不是字符串/列表
        if not isinstance(parsed, dict):
            return {"decision": "continue", "thought": "LLM 返回非对象格式，默认继续", "raw": raw}

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

    def _enrich_final_answer(self, log: ExecutionLog) -> str:
        """
        如果 LLM 的最终回答没有包含具体数据（如分子列表、项目信息等），
        直接基于最后一步的 observation 构建格式化结果。
        返回 enriched_answer 或空字符串（如果不需要增强）。
        """
        if not log.steps:
            return ""
        
        # 找出最后一步有成功 observation 的步骤
        last_success_step = None
        for s in reversed(log.steps):
            obs = s.observation
            if obs and isinstance(obs, dict) and obs.get("success"):
                last_success_step = s
                break
        
        if not last_success_step:
            return ""
        
        obs = last_success_step.observation
        tool = last_success_step.tool
        
        # 如果 LLM 已经提到了分子名称/ID，说明它已经包含了数据
        if log.final_answer and isinstance(log.final_answer, str):
            # 简单启发：检查是否包含 SMILES 或分子ID
            has_molecule_data = any(
                keyword in log.final_answer.lower()
                for keyword in ["smiles", "molecule", "分子", "编号", "对接分数", "admet"]
            )
            if has_molecule_data:
                return ""
        
        # 根据工具类型构建格式化结果
        if tool == "get_top_molecules":
            return self._format_top_molecules(obs)
        elif tool == "get_project_status":
            return self._format_project_status(obs)
        elif tool == "create_project":
            return self._format_create_project(obs)
        elif tool == "wait_for_pipeline":
            return self._format_pipeline_result(obs)
        
        return ""
    
    def _format_top_molecules(self, obs: Dict) -> str:
        """格式化 Top 分子结果"""
        count = obs.get("count", 0)
        molecules = obs.get("molecules", [])
        if not molecules:
            return "\n\n---\n\n**Top 分子结果**：暂无通过合成筛选的分子。Pipeline 可能尚未完成，或没有分子通过所有筛选阶段。"
        
        lines = ["\n\n---\n\n**Top 候选分子**", ""]
        for i, mol in enumerate(molecules, 1):
            lines.append(f"**{i}. {mol.get('id', '未知')}**")
            lines.append(f"- SMILES: `{mol.get('smiles', 'N/A')}`")
            lines.append(f"- 综合得分: {mol.get('score', 'N/A')}")
            lines.append(f"- 对接分数: {mol.get('docking_score', 'N/A')}")
            lines.append(f"- ADMET 分数: {mol.get('admet_score', 'N/A')}")
            lines.append(f"- QED: {mol.get('qed', 'N/A')}")
            lines.append(f"- 分子量: {mol.get('mw', 'N/A')}")
            lines.append(f"- LogP: {mol.get('logp', 'N/A')}")
            lines.append(f"- SA Score: {mol.get('sa_score', 'N/A')}")
            lines.append(f"- 生成策略: {mol.get('generation_strategy', 'N/A')}")
            lines.append("")
        return "\n".join(lines)
    
    def _format_project_status(self, obs: Dict) -> str:
        """格式化项目状态结果"""
        if not obs.get("success"):
            return ""
        lines = ["\n\n---\n\n**项目状态**", ""]
        lines.append(f"- 项目名称: {obs.get('project_name', 'N/A')}")
        lines.append(f"- 总分子数: {obs.get('total_molecules', 0)}")
        lines.append(f"- 失败分子数: {obs.get('failed', 0)}")
        lines.append(f"- 通过分子数: {obs.get('passed', 0)}")
        
        stages = obs.get("stages", {})
        if stages:
            lines.append("\n各阶段统计：")
            for stage, count in stages.items():
                lines.append(f"- {stage}: {count}")
        
        latest = obs.get("latest_pipeline")
        if latest:
            lines.append(f"\n最新 Pipeline: #{latest.get('id')} ({latest.get('status')})")
        
        return "\n".join(lines)
    
    def _format_create_project(self, obs: Dict) -> str:
        """格式化项目创建结果"""
        if not obs.get("success"):
            return ""
        lines = ["\n\n---\n\n**项目创建成功**", ""]
        lines.append(f"- 项目 ID: {obs.get('project_id')}")
        lines.append(f"- 项目名称: {obs.get('name')}")
        lines.append(f"- 靶点: {obs.get('target_name', 'N/A')}")
        lines.append(f"- 设计目标: {obs.get('design_goal', 'N/A')}")
        added = obs.get("active_molecules_added", 0)
        if added > 0:
            lines.append(f"- 已自动添加 {added} 个已知活性分子作为参考")
        return "\n".join(lines)
    
    def _format_pipeline_result(self, obs: Dict) -> str:
        """格式化 Pipeline 等待结果"""
        if not obs.get("success"):
            return ""
        lines = ["\n\n---\n\n**Pipeline 执行结果**", ""]
        lines.append(f"- 状态: {obs.get('status', 'N/A')}")
        lines.append(f"- 完成: {'是' if obs.get('completed') else '否'}")
        lines.append(f"- 等待时长: {obs.get('elapsed_seconds', 0)} 秒")
        lines.append(f"- 生成分子数: {obs.get('num_generated', 0)}")
        lines.append(f"- 通过分子数: {obs.get('num_passed', 0)}")
        lines.append(f"- 失败分子数: {obs.get('num_failed', 0)}")
        
        stage_counts = obs.get("stage_counts", {})
        if stage_counts:
            lines.append("\n各阶段分子数：")
            for stage, count in stage_counts.items():
                if count > 0:
                    lines.append(f"- {stage}: {count}")
        
        summary = obs.get("summary")
        if summary:
            lines.append(f"\n{summary}")
        
        return "\n".join(lines)
