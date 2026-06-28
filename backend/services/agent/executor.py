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
        llm_client=None,
    ):
        self.tools = tool_registry or get_registry()
        self.temperature = temperature
        self.llm_interval = llm_interval
        self.step_timeout = step_timeout
        self.max_retries = max_retries
        self._last_llm_call = 0.0
        
        # 注入统一的 LLMClient
        if llm_client is not None:
            self.llm = llm_client
        else:
            from .llm_client import get_default_client
            self.llm = get_default_client(api_key=api_key, model=model)

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

        # 简单工具列表：不需要 LLM 决策，直接继续
        SIMPLE_TOOLS = {
            "get_project_status", "list_projects", "get_top_molecules",
            "get_pipeline_progress", "get_failed_molecules", "compare_molecules",
            "suggest_next_step", "get_molecule_details",
        }

        while step_index < len(current_steps):
            step_def = current_steps[step_index]
            
            # 条件评估：如果步骤有条件，先评估
            condition = step_def.get("condition", "")
            if condition:
                condition_met = self._evaluate_condition(condition, log, env_state)
                if not condition_met:
                    # 条件不满足，跳过此步骤
                    skipped_step = ExecutionStep(
                        step_number=step_index + 1,
                        tool=step_def.get("tool", ""),
                        params=step_def.get("params", {}) if isinstance(step_def.get("params"), dict) else {},
                        reason=f"[条件不满足: {condition}] {step_def.get('reason', '')}",
                        expected_outcome=step_def.get("expected_outcome", ""),
                    )
                    skipped_step.status = "skipped"
                    skipped_step.observation = {"condition": condition, "skipped": True, "reason": "条件不满足"}
                    skipped_step.finished_at = datetime.now()
                    log.steps.append(skipped_step)
                    step_index += 1
                    continue
            
            exec_step = self._run_single_step(step_def, step_index + 1)
            log.steps.append(exec_step)

            # 判断是否需要 LLM 决策：简单工具直接跳过，复杂工具才决策
            tool_name = step_def.get("tool", "")
            if tool_name in SIMPLE_TOOLS and exec_step.status == "ok":
                # 简单工具成功执行，直接继续，不调用 LLM 决策
                exec_step.llm_decision = "continue"
                exec_step.llm_thought = "简单工具执行成功，直接继续"
            else:
                # 复杂工具或执行失败，调用 LLM 决策
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
        
        # 构建 steps 报告：如果 final_answer 已被强制格式化，steps 的 observation 简化为摘要，避免重复
        steps_report = []
        for s in log.steps:
            step_dict = {
                "step_number": s.step_number,
                "tool": s.tool,
                "params": s.params if isinstance(s.params, dict) else {},
                "reason": s.reason,
                "status": s.status,
                "error": s.error,
                "started_at": s.started_at.isoformat(),
                "finished_at": s.finished_at.isoformat() if s.finished_at else None,
                "llm_decision": s.llm_decision,
                "llm_thought": s.llm_thought,
            }
            
            # 如果最终答案已被强制格式化，steps 的 observation 简化为摘要，避免重复显示
            if enriched_answer and s.observation:
                step_dict["observation"] = f"已执行 {s.tool}，详细结果见下方报告"
            else:
                step_dict["observation"] = self._serialize_obs(s.observation)
            
            steps_report.append(step_dict)
        
        # 生成聊天摘要：如果 final_answer 很长，提取第一行作为摘要
        chat_summary = log.final_answer
        if len(log.final_answer) > 200:
            # 提取第一行非空内容作为摘要
            lines = [l.strip() for l in log.final_answer.strip().split('\n') if l.strip()]
            if lines:
                chat_summary = f"{lines[0]} ... 执行完成，详见下方报告。"
            else:
                chat_summary = "执行完成，详见下方报告。"

        return {
            "success": log.success,
            "goal": log.goal,
            "project_id": log.project_id,
            "started_at": log.started_at.isoformat(),
            "finished_at": log.finished_at.isoformat() if log.finished_at else None,
            "total_steps": len(log.steps),
            "steps": steps_report,
            "final_answer": log.final_answer,
            "chat_summary": chat_summary,
            "actions": [a.to_dict() for a in frontend_actions],
        }

    # ------------------------------------------------------------------
    # Step execution
    # ------------------------------------------------------------------

    def _run_single_step(self, step_def: Dict[str, Any], step_number: int) -> ExecutionStep:
        """Execute a single step with timeout, retry, and conditional evaluation."""
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
        condition = step_def.get("condition", "")

        exec_step = ExecutionStep(
            step_number=step_number,
            tool=tool_name,
            params=params,
            reason=reason,
            expected_outcome=expected,
        )
        exec_step.status = "running"

        # 条件评估：如果步骤有条件，先评估条件是否满足
        if condition:
            exec_step.reason = f"[条件: {condition}] {reason}"
            # 条件步骤由 LLM 决策器在 execute_plan 中处理
            # 这里标记为 condition，实际执行会由 LLM 判断是否跳过
            exec_step.status = "ok"
            exec_step.observation = {"condition": condition, "skipped": False, "note": "条件步骤，由决策器评估"}
            exec_step.finished_at = datetime.now()
            return exec_step

        func = self.tools.get(tool_name)
        if not func:
            exec_step.status = "error"
            exec_step.error = f"工具 '{tool_name}' 未注册"
            exec_step.finished_at = datetime.now()
            return exec_step

        # 特殊处理：wait_for_pipeline 使用后台线程 + 超时，避免阻塞主线程
        if tool_name == "wait_for_pipeline":
            return self._execute_wait_for_pipeline(func, params, exec_step)

        # Execute with retry (Phase 5: 追踪工具执行)
        last_error = ""
        tracer = None
        trace_step = None
        try:
            from .tracer import AgentTracer
            tracer = AgentTracer.get_current()
        except Exception:
            pass
        
        for attempt in range(self.max_retries + 1):
            # Phase 5: 开始追踪工具执行
            if tracer:
                trace_step = tracer.start_step(
                    step_type="tool_execution",
                    name=tool_name,
                    input_data={"params": params, "reason": reason, "attempt": attempt + 1}
                )
            
            try:
                result = func(**params)
                exec_step.observation = result
                exec_step.status = "ok"
                exec_step.error = ""
                
                # Phase 5: 完成追踪
                if tracer and trace_step:
                    trace_step.finish(output={"status": "ok", "result_type": type(result).__name__})
                
                break
            except Exception as e:
                last_error = str(e)
                exec_step.status = "error"
                exec_step.error = last_error
                
                # Phase 5: 记录错误
                if tracer and trace_step:
                    trace_step.finish(error=last_error)
                
                if attempt < self.max_retries:
                    time.sleep(1)
                else:
                    exec_step.status = "error"
                    exec_step.error = f"{last_error} (已重试 {self.max_retries} 次)"

        exec_step.finished_at = datetime.now()
        return exec_step

    def _execute_wait_for_pipeline(self, func, params: Dict, exec_step: ExecutionStep) -> ExecutionStep:
        """
        执行 wait_for_pipeline，使用后台线程 + 超时，避免阻塞主线程。
        
        - 如果 10 秒内完成，返回实际结果
        - 如果超时，返回 "正在等待" 状态，executor 后续会继续检查
        """
        import concurrent.futures
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(func, **params)
            try:
                result = future.result(timeout=10)  # 最多等待 10 秒
                exec_step.observation = result
                exec_step.status = "ok" if result.get("success", False) else "partial"
                exec_step.error = result.get("error", "")
            except concurrent.futures.TimeoutError:
                # Pipeline 仍在运行，返回等待状态
                exec_step.observation = {
                    "success": True,
                    "completed": False,
                    "status": "running",
                    "message": "Pipeline 正在运行中，已等待 10 秒。请稍后查看结果。",
                    "elapsed": 10,
                }
                exec_step.status = "ok"  # 标记为 ok，但不是 completed
                exec_step.error = ""
            except Exception as e:
                exec_step.status = "error"
                exec_step.error = str(e)
        
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
        
        # 检查最后一步是否是条件步骤
        is_condition_step = last_step and last_step.observation and isinstance(last_step.observation, dict) and last_step.observation.get("condition")
        condition_info = ""
        if is_condition_step:
            condition = last_step.observation.get("condition", "")
            condition_info = f"""

⚠️ 注意：上一步是条件步骤！
条件：{condition}

请评估该条件是否满足：
- 如果条件满足，建议 continue 执行该步骤对应的工具
- 如果条件不满足，建议 modify 跳过该步骤或执行替代方案
"""

        failure_info = ""
        if step_failed:
            failure_info = f"""

⚠️ 注意：上一步执行失败！
工具：{last_step.tool}
错误：{last_step.error}
参数：{json.dumps(last_step.params, ensure_ascii=False)}

请决定：
- 如果失败是因为缺少必要信息（如缺少 project_id），建议用 modify 生成获取信息的步骤
- 如果失败是不可修复的（如项目不存在），建议 finish 并告知用户
- 如果失败可以重试，建议 continue
"""

        system_prompt = f"""你是 DrugDesign Copilot Agent 的执行决策器。
你的任务是根据已执行的步骤和观察结果，决定下一步行动。

## 可选决策
1. "continue" - 继续执行计划中的下一步
2. "modify" - 修改剩余计划（如修复失败、调整策略、跳过条件不满足的步骤）
3. "finish" - 计划已完成或无法继续，给出最终回答

{f"## 当前状态：上一步失败，需要修复。" if step_failed else ""}
{f"## 当前状态：需要评估条件步骤。" if is_condition_step else ""}

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
{condition_info}
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

    def _call_llm(self, messages: List[Dict[str, str]]) -> str:
        """调用 LLM（委托给 LLMClient，带重试）。"""
        return self.llm.retry_call(messages, temperature=self.temperature, max_retries=2, base_delay=0.5)

    def _rate_limit(self):
        """Rate limit guard（向后兼容，实际逻辑在 LLMClient 中）。"""
        pass

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

    def _evaluate_condition(
        self,
        condition: str,
        log: ExecutionLog,
        env_state: Optional[Dict[str, Any]],
    ) -> bool:
        """
        评估条件是否满足。
        
        策略：
        1. 简单规则匹配（如分数比较、状态判断）
        2. 复杂条件使用 LLM 评估
        
        Args:
            condition: 条件描述字符串（如 "ADMET 分数 < 3"）
            log: 当前执行日志
            env_state: 环境状态
        
        Returns:
            True if condition is met, False otherwise.
        """
        # 策略 1：简单数值比较（从最后一步结果中提取数值）
        import re
        
        # 尝试从执行历史中提取数值进行比较
        # 例如："ADMET 分数 < 3" → 查找 observation 中的 score 或 value
        if log.steps:
            last_obs = log.steps[-1].observation
            if isinstance(last_obs, dict):
                # 提取数值模式："x < y", "x > y", "x >= y", "x <= y"
                numeric_match = re.search(r'([\w\s]+)\s*([<>=]+)\s*([\d\.]+)', condition)
                if numeric_match:
                    metric_name = numeric_match.group(1).strip().lower()
                    operator = numeric_match.group(2).strip()
                    threshold = float(numeric_match.group(3).strip())
                    
                    # 在 observation 中查找对应数值
                    value = None
                    for key in last_obs:
                        if metric_name in key.lower() or key.lower() in metric_name:
                            val = last_obs[key]
                            if isinstance(val, (int, float)):
                                value = float(val)
                                break
                    
                    if value is not None:
                        if operator == '<':
                            return value < threshold
                        elif operator == '>':
                            return value > threshold
                        elif operator == '<=':
                            return value <= threshold
                        elif operator == '>=':
                            return value >= threshold
                        elif operator == '==':
                            return value == threshold
        
        # 策略 2：使用 LLM 评估复杂条件
        # 构建提示，让 LLM 基于执行历史判断条件是否满足
        history = self._format_execution_history(log)
        env_text = json.dumps(env_state or {}, ensure_ascii=False, indent=2)
        
        prompt = f"""基于以下执行历史和环境状态，判断条件是否满足。

条件："{condition}"

已执行步骤：
{history}

环境状态：
{env_text}

请只回答 "true" 或 "false"，不要解释。"""
        
        raw = self.llm.retry_call([{"role": "user", "content": prompt}], temperature=0.0, max_retries=2, base_delay=0.5)
        return "true" in raw.lower()

    def _format_execution_history(self, log: ExecutionLog) -> str:
        """Format executed steps for LLM context.
        
        当步骤超过 5 步时，对早期步骤做压缩摘要，只保留最近 3 步的完整信息。
        """
        lines = []
        steps = log.steps
        
        if len(steps) > 5:
            # 压缩早期步骤：只保留 tool + status
            for s in steps[:-3]:
                lines.append(f"Step {s.step_number}: {s.tool} → {s.status}")
            
            # 保留最近 3 步的完整信息
            for s in steps[-3:]:
                obs = self._serialize_obs(s.observation)
                lines.append(
                    f"Step {s.step_number}: {s.tool}({json.dumps(s.params, ensure_ascii=False)})\n"
                    f"  Status: {s.status}\n"
                    f"  Observation: {obs}\n"
                    f"  Thought: {s.llm_thought}"
                )
        else:
            # 步骤少，保留完整信息
            for s in steps:
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
        # 但对于特定工具，我们强制使用专业格式化，覆盖 LLM 的简陋排版
        if log.final_answer and isinstance(log.final_answer, str):
            # 单分子 ADMET 分析：不管 LLM 是否已经包含数据，强制使用专业格式化
            if tool == "analyze_single_molecule_admet":
                return self._format_single_molecule_admet(obs)
            
            # 简单启发：检查是否包含 SMILES 或分子ID
            has_molecule_data = any(
                keyword in log.final_answer.lower()
                for keyword in ["molecule", "编号", "对接分数"]
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
        elif tool == "analyze_failures":
            return self._format_analyze_failures(obs)
        elif tool == "get_failed_molecules":
            return self._format_analyze_failures(obs)
        elif tool == "compare_molecules":
            return self._format_compare_molecules(obs)
        elif tool == "suggest_next_step":
            return self._format_suggest_next_step(obs)
        elif tool == "get_pipeline_progress":
            return self._format_pipeline_progress(obs)
        elif tool == "analyze_single_molecule_admet":
            return self._format_single_molecule_admet(obs)
        
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
    
    def _format_analyze_failures(self, obs: Dict) -> str:
        """格式化失败分子分析结果"""
        if not obs.get("success") and obs.get("total_failed") is None:
            return ""
        
        total = obs.get("total_failed", 0)
        lines = ["\n\n**失败分子分析报告**", ""]
        
        if total == 0:
            lines.append("✅ 当前没有失败分子记录。所有分子均通过了各阶段筛选。")
            return "\n".join(lines)
        
        lines.append(f"共发现 **{total}** 个失败分子\n")
        
        # 按阶段统计
        stage_counts = obs.get("stage_counts", {})
        if stage_counts:
            lines.append("**失败阶段分布**")
            lines.append("| 失败阶段 | 数量 | 占比 |")
            lines.append("|----------|------|------|")
            stage_names = {
                "filtering": "结构初筛",
                "structure_screening": "结构筛选",
                "admet": "ADMET 评估",
                "refinement": "FEP 精修",
                "synthesis": "合成评估",
                "unknown": "未分类",
            }
            for stage, count in sorted(stage_counts.items(), key=lambda x: x[1], reverse=True):
                name = stage_names.get(stage, stage)
                pct = count / total * 100 if total > 0 else 0
                lines.append(f"| {name} | {count} | {pct:.1f}% |")
            lines.append("")
        
        # 失败原因统计
        reasons = obs.get("reasons", {})
        if reasons:
            lines.append("**主要失败原因**")
            lines.append("| 失败原因 | 次数 | 占比 |")
            lines.append("|----------|------|------|")
            for reason, count in sorted(reasons.items(), key=lambda x: x[1], reverse=True)[:5]:
                pct = count / total * 100 if total > 0 else 0
                lines.append(f"| {reason} | {count} | {pct:.1f}% |")
            lines.append("")
        
        # 优化建议
        suggestions = obs.get("suggestions", [])
        if suggestions:
            lines.append("**💡 优化建议**")
            for i, sug in enumerate(suggestions, 1):
                lines.append(f"{i}. {sug}")
            lines.append("")
        
        return "\n".join(lines)
    
    def _format_compare_molecules(self, obs: Dict) -> str:
        """格式化分子对比结果"""
        if not obs.get("success"):
            return ""
        
        molecules = obs.get("molecules", [])
        if not molecules:
            return "\n\n**分子对比**：暂无对比数据。"
        
        lines = ["\n\n**分子对比报告**", ""]
        lines.append("| 分子ID | MW | LogP | hERG | QED | 对接分数 | ADMET | 合成难度 |")
        lines.append("|--------|------|------|------|-----|----------|-------|----------|")
        
        for mol in molecules:
            lines.append(
                f"| {mol.get('id', 'N/A')} | "
                f"{mol.get('mw', 'N/A')} | "
                f"{mol.get('logp', 'N/A')} | "
                f"{mol.get('herg', 'N/A')} | "
                f"{mol.get('qed', 'N/A')} | "
                f"{mol.get('docking_score', 'N/A')} | "
                f"{mol.get('admet_score', 'N/A')} | "
                f"{mol.get('sa_score', 'N/A')} |"
            )
        
        recommendation = obs.get("recommendation")
        if recommendation:
            lines.append(f"\n**推荐**: {recommendation}")
        
        return "\n".join(lines)
    
    def _format_suggest_next_step(self, obs: Dict) -> str:
        """格式化下一步建议"""
        if not obs.get("success"):
            return ""
        
        lines = ["\n\n---\n\n**下一步建议**", ""]
        
        suggestion = obs.get("suggestion")
        if suggestion:
            lines.append(f"{suggestion}")
        
        actions = obs.get("suggested_actions", [])
        if actions:
            lines.append("\n建议操作：")
            for action in actions:
                lines.append(f"- {action}")
        
        return "\n".join(lines)
    
    def _format_pipeline_progress(self, obs: Dict) -> str:
        """格式化 Pipeline 进度"""
        if not obs.get("success"):
            return ""
        
        lines = ["\n\n---\n\n**Pipeline 实时进度**", ""]
        lines.append(f"- 当前状态: {obs.get('status', 'N/A')}")
        lines.append(f"- 已完成阶段: {obs.get('completed_stages', 0)} / {obs.get('total_stages', 8)}")
        lines.append(f"- 已生成分子: {obs.get('num_generated', 0)}")
        lines.append(f"- 已通过分子: {obs.get('num_passed', 0)}")
        lines.append(f"- 失败分子: {obs.get('num_failed', 0)}")
        
        current_stage = obs.get('current_stage')
        if current_stage:
            lines.append(f"- 当前执行: {current_stage}")
        
        elapsed = obs.get('elapsed_seconds')
        if elapsed is not None:
            lines.append(f"- 已运行: {elapsed} 秒")
        
        return "\n".join(lines)
    
    def _format_single_molecule_admet(self, obs: Dict) -> str:
        """格式化单分子 ADMET 分析结果 — 正确读取嵌套数据，专业排版"""
        if not obs.get("success"):
            return f"\n\n**ADMET 分析失败**：{obs.get('message', '未知错误')}"
        
        smiles = obs.get("smiles", "N/A")
        canonical = obs.get("canonical_smiles", smiles)
        key_metrics = obs.get("key_metrics", {})
        admet = obs.get("admet_result", {})
        
        # 正确读取嵌套数据
        absorption = admet.get('absorption', {})
        distribution = admet.get('distribution', {})
        metabolism = admet.get('metabolism', {})
        excretion = admet.get('excretion', {})
        toxicity = admet.get('toxicity', {})
        drug_likeness = admet.get('drug_likeness', {})
        alerts = admet.get('alerts', {})
        overall_score = admet.get('overall_score') or obs.get('overall_score', 'N/A')
        
        # 辅助函数：格式化数值
        def fmt(val, fmt_str="{}"):
            if val is None:
                return "N/A"
            if isinstance(val, float):
                return fmt_str.format(val)
            return str(val)
        
        # 辅助函数：判断药物相似性
        def drug_like_status(qed, lipinski):
            if qed is None:
                return "N/A"
            if qed > 0.6 and lipinski <= 1:
                return "优秀"
            elif qed > 0.5 and lipinski <= 2:
                return "良好"
            elif qed > 0.3 and lipinski <= 4:
                return "一般"
            else:
                return "需改进"
        
        qed_val = drug_likeness.get('qed')
        lipinski_v = drug_likeness.get('lipinski_violations', 0)
        status = drug_like_status(qed_val, lipinski_v)
        
        lines = [
            "",
            "**单分子 ADMET 分析报告**",
            "",
            f"**SMILES**：`{canonical}`",
            "",
        ]
        
        # 基础理化性质
        lines.append("**基础理化性质**")
        lines.append("| 指标 | 数值 | 备注 |")
        lines.append("|------|------|------|")
        lines.append(f"| 分子量 (MW) | {fmt(key_metrics.get('MW'))} | {'通过' if key_metrics.get('MW', 500) <= 500 else '超标'} |")
        lines.append(f"| LogP | {fmt(key_metrics.get('LogP'))} | {'通过' if key_metrics.get('LogP', 5) <= 5 else '偏高'} |")
        lines.append(f"| TPSA | {fmt(key_metrics.get('TPSA'))} | {'通过' if key_metrics.get('TPSA', 140) <= 140 else '偏高'} |")
        lines.append(f"| HBD (氢键供体) | {fmt(key_metrics.get('HBD'))} | {'通过' if key_metrics.get('HBD', 5) <= 5 else '超标'} |")
        lines.append(f"| HBA (氢键受体) | {fmt(key_metrics.get('HBA'))} | {'通过' if key_metrics.get('HBA', 10) <= 10 else '超标'} |")
        lines.append(f"| 可旋转键 | {fmt(key_metrics.get('RotB'))} | {'通过' if key_metrics.get('RotB', 10) <= 10 else '偏多'} |")
        lines.append(f"| QED (药物相似度) | {fmt(qed_val)} | {status} |")
        lines.append("")
        
        # 吸收
        lines.append("**吸收 (Absorption)**")
        lines.append("| 指标 | 数值 | 评价 |")
        lines.append("|------|------|------|")
        lines.append(f"| 水溶性 (logS) | {fmt(absorption.get('solubility'))} | {'良好' if absorption.get('solubility', -5) > -4 else '偏低'} |")
        lines.append(f"| 渗透性 (Caco2) | {fmt(absorption.get('permeability'))} | {'良好' if absorption.get('permeability', -6) > -5 else '偏低'} |")
        lines.append(f"| 口服生物利用度 | {fmt(absorption.get('oral_bioavailability'), '{:.1%}')} | {'高' if absorption.get('oral_bioavailability', 0) > 0.7 else '中等'} |")
        lines.append(f"| 肠道吸收 (HIA) | {fmt(absorption.get('hia'), '{:.1%}')} | {'高' if absorption.get('hia', 0) > 0.8 else '中等'} |")
        lines.append(f"| PAMPA | {fmt(absorption.get('pampa'), '{:.1%}')} | {'良好' if absorption.get('pampa', 0) > 0.5 else '一般'} |")
        lines.append(f"| 脂溶性 | {fmt(absorption.get('lipophilicity'))} | {'适中' if 1 < absorption.get('lipophilicity', 0) < 4 else '偏高'} |")
        lines.append("")
        
        # 分布
        lines.append("**分布 (Distribution)**")
        lines.append("| 指标 | 数值 | 评价 |")
        lines.append("|------|------|------|")
        lines.append(f"| 血脑屏障 (BBB) | {fmt(distribution.get('bbb'), '{:.1%}')} | {'可透过' if distribution.get('bbb', 0) > 0.5 else '不易透过'} |")
        lines.append(f"| 血浆蛋白结合率 | {fmt(distribution.get('ppbr'), '{:.1%}')} | {'高' if distribution.get('ppbr', 0) > 0.8 else '适中'} |")
        lines.append(f"| 分布容积 (Vdss) | {fmt(distribution.get('vdss'))} | {'适中' if 0.3 < distribution.get('vdss', 0) < 3 else '偏高'} |")
        lines.append("")
        
        # 代谢
        lines.append("**代谢 (Metabolism)**")
        lines.append("| 指标 | 数值 | 评价 |")
        lines.append("|------|------|------|")
        lines.append(f"| CYP1A2 抑制 | {fmt(metabolism.get('cyp1a2'), '{:.1%}')} | {'高风险' if metabolism.get('cyp1a2', 0) > 0.5 else '低风险'} |")
        lines.append(f"| CYP2C9 抑制 | {fmt(metabolism.get('cyp2c9'), '{:.1%}')} | {'高风险' if metabolism.get('cyp2c9', 0) > 0.5 else '低风险'} |")
        lines.append(f"| CYP2D6 抑制 | {fmt(metabolism.get('cyp2d6'), '{:.1%}')} | {'高风险' if metabolism.get('cyp2d6', 0) > 0.5 else '低风险'} |")
        lines.append(f"| CYP3A4 抑制 | {fmt(metabolism.get('cyp3a4'), '{:.1%}')} | {'高风险' if metabolism.get('cyp3a4', 0) > 0.5 else '低风险'} |")
        lines.append(f"| CYP2C19 抑制 | {fmt(metabolism.get('cyp2c19'), '{:.1%}')} | {'高风险' if metabolism.get('cyp2c19', 0) > 0.5 else '低风险'} |")
        lines.append("")
        
        # 排泄
        lines.append("**排泄 (Excretion)**")
        lines.append("| 指标 | 数值 | 评价 |")
        lines.append("|------|------|------|")
        lines.append(f"| 半衰期 (h) | {fmt(excretion.get('half_life'))} | {'长' if excretion.get('half_life', 0) > 6 else '适中'} |")
        lines.append(f"| 肝脏清除率 | {fmt(excretion.get('clearance_hep'))} | {'适中' if 5 < excretion.get('clearance_hep', 0) < 20 else '偏高'} |")
        lines.append(f"| 微粒体清除率 | {fmt(excretion.get('clearance_mic'))} | {'适中' if 10 < excretion.get('clearance_mic', 0) < 30 else '偏高'} |")
        lines.append("")
        
        # 毒性
        lines.append("**毒性 (Toxicity)**")
        lines.append("| 指标 | 数值 | 评价 |")
        lines.append("|------|------|------|")
        lines.append(f"| hERG (心脏毒性) | {fmt(toxicity.get('herg'), '{:.1%}')} | {'高风险' if toxicity.get('herg', 0) > 0.5 else '低风险'} |")
        lines.append(f"| AMES (致突变性) | {fmt(toxicity.get('ames'), '{:.1%}')} | {'阳性' if toxicity.get('ames', 0) > 0.5 else '阴性'} |")
        lines.append(f"| DILI (肝毒性) | {fmt(toxicity.get('dili'), '{:.1%}')} | {'高风险' if toxicity.get('dili', 0) > 0.5 else '低风险'} |")
        lines.append(f"| ClinTox (临床毒性) | {fmt(toxicity.get('clintox'), '{:.1%}')} | {'高风险' if toxicity.get('clintox', 0) > 0.5 else '低风险'} |")
        lines.append(f"| LD50 (急性毒性) | {fmt(toxicity.get('ld50'))} | {'高毒性' if toxicity.get('ld50', 3) < 1.5 else '低毒性'} |")
        lines.append("")
        
        # 规则评估
        lines.append("**规则评估**")
        lines.append("| 规则 | 结果 | 状态 |")
        lines.append("|------|------|------|")
        lines.append(f"| Lipinski 五规则 | {fmt(lipinski_v)} 条违反 | {'通过' if lipinski_v == 0 else '需关注'} |")
        lines.append(f"| PAINS 警示 | {'有' if alerts.get('pains', 0) else '无'} | {'通过' if not alerts.get('pains', 0) else '需关注'} |")
        lines.append(f"| BRENK 警示 | {'有' if alerts.get('brenk', 0) else '无'} | {'通过' if not alerts.get('brenk', 0) else '需关注'} |")
        lines.append(f"| NIH 警示 | {'有' if alerts.get('nih', 0) else '无'} | {'通过' if not alerts.get('nih', 0) else '需关注'} |")
        lines.append("")
        
        # 总体评价
        lines.append(f"**总体评价**：总体评分 **{overall_score}**，药物相似性评估为 **{status}**。")
        lines.append("")
        
        return "\n".join(lines)
