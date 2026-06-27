"""
planner.py - LLM-driven Task Planner

Generates structured multi-step execution plans by calling the KIMI API.
The planner receives a user goal + environment state and outputs a list of
steps (tool, params, reason) as a JSON object.
"""

import json
import os
import re
import time
from typing import Dict, Any, List, Optional

import requests


KIMI_API_KEY = os.environ.get("KIMI_API_KEY", "")
KIMI_API_URL = "https://api.moonshot.cn/v1/chat/completions"
DEFAULT_MODEL = "moonshot-v1-8k"
MAX_STEPS = 10


class TaskPlanner:
    """
    LLM-driven task planner for the DrugDesign Copilot Agent.

    Usage:
        planner = TaskPlanner()
        plan = planner.plan(goal="帮我优化项目", project_id=1, env_state={...})
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = DEFAULT_MODEL,
        temperature: float = 0.3,
        max_steps: int = MAX_STEPS,
    ):
        self.api_key = api_key or KIMI_API_KEY
        self.model = model
        self.temperature = temperature
        self.max_steps = max_steps

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def plan(
        self,
        goal: str,
        project_id: Optional[int] = None,
        env_state: Optional[Dict[str, Any]] = None,
        available_tools: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """
        Generate an execution plan for the given user goal.

        Returns:
            {
                "success": bool,
                "goal": str,
                "project_id": int | None,
                "steps": [
                    {
                        "step_number": int,
                        "tool": str,
                        "params": dict,
                        "reason": str,
                        "expected_outcome": str
                    },
                    ...
                ],
                "summary": str,   # human-readable plan summary
                "raw_response": str  # raw LLM text (for debugging)
            }
        """
        env_state = env_state or {}
        available_tools = available_tools or []

        system_prompt = self._build_system_prompt(available_tools)
        user_prompt = self._build_user_prompt(goal, project_id, env_state)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        raw_response = self._call_llm(messages)

        if not raw_response:
            return self._fallback_plan(goal, project_id, error="LLM call failed")

        parsed = self._parse_llm_plan(raw_response)

        if not parsed.get("steps"):
            return self._fallback_plan(goal, project_id, error="Failed to parse plan")

        # Enforce max step limit
        steps = parsed["steps"][: self.max_steps]
        for i, step in enumerate(steps, start=1):
            step["step_number"] = i

        return {
            "success": True,
            "goal": goal,
            "project_id": project_id,
            "steps": steps,
            "summary": parsed.get("summary", "未提供摘要"),
            "raw_response": raw_response,
        }

    # ------------------------------------------------------------------
    # Prompt builders
    # ------------------------------------------------------------------

    def _build_system_prompt(self, tools: List[Dict]) -> str:
        """Build the system prompt that instructs the LLM to output JSON plans."""
        tools_desc = []
        for t in tools:
            params = json.dumps(t.get("parameters", {}), ensure_ascii=False, indent=2)
            tools_desc.append(
                f"- {t.get('name', 'unknown')}: {t.get('description', '')}\n  参数: {params}"
            )
        tools_text = "\n".join(tools_desc) if tools_desc else "（当前无可用工具）"

        return f"""你是 DrugDesign Copilot Agent 的任务规划器。你的职责是将用户的目标拆解为可执行的步骤。

## 可用工具
{tools_text}

## 输出格式
你必须返回一个严格的 JSON 对象，格式如下（不要包含 Markdown 代码块标记，只输出纯 JSON）：

{{
  "steps": [
    {{
      "tool": "工具名称",
      "params": {{"参数名": "参数值"}},
      "reason": "为什么需要这一步",
      "expected_outcome": "预期这一步会得到什么结果"
    }}
  ],
  "summary": "用一句话概括整个计划"
}}

## 规则
1. 步骤数量不超过 {self.max_steps} 步
2. 每一步必须对应一个可用的工具
3. 参数必须准确，project_id 必须正确传递
4. 如果目标不明确，先安排一个 "suggest_next_step" 或 "get_project_status" 来收集信息
5. 所有输出必须是合法的 JSON，不要添加注释
6. 禁止使用 markdown 代码块（```json），直接输出 JSON 字符串
"""

    def _build_user_prompt(
        self, goal: str, project_id: Optional[int], env_state: Dict[str, Any]
    ) -> str:
        """Build the user prompt that includes the goal and environment state."""
        env_text = json.dumps(env_state, ensure_ascii=False, indent=2)
        return f"""用户目标：{goal}

项目ID：{project_id if project_id else '未指定'}

当前环境状态：
{env_text}

请基于以上信息，生成一个执行计划（纯 JSON 格式）。"""

    # ------------------------------------------------------------------
    # LLM interaction
    # ------------------------------------------------------------------

    def _call_llm(self, messages: List[Dict[str, str]]) -> Optional[str]:
        """Call the KIMI API and return the raw text content."""
        if not self.api_key:
            return None

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
            choice = data.get("choices", [{}])[0]
            message = choice.get("message", {})
            return message.get("content", "").strip()
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    def _parse_llm_plan(self, raw: str) -> Dict[str, Any]:
        """Extract JSON from the LLM response and validate it."""
        # 1. Try to extract JSON block if wrapped in markdown
        text = raw.strip()

        # Remove markdown code fences
        code_fence = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if code_fence:
            text = code_fence.group(1).strip()

        # 2. Try to find the first JSON object
        if not text.startswith("{"):
            match = re.search(r"(\{[\s\S]*\})", text)
            if match:
                text = match.group(1).strip()

        try:
            plan = json.loads(text)
        except json.JSONDecodeError:
            return {}

        # Validate structure
        steps = plan.get("steps", [])
        if not isinstance(steps, list):
            return {}

        validated_steps = []
        for step in steps:
            if not isinstance(step, dict):
                continue
            tool = step.get("tool")
            if not tool or not isinstance(tool, str):
                continue
            validated_steps.append({
                "tool": tool,
                "params": step.get("params", {}) if isinstance(step.get("params"), dict) else {},
                "reason": str(step.get("reason", "")),
                "expected_outcome": str(step.get("expected_outcome", "")),
            })

        return {
            "steps": validated_steps,
            "summary": str(plan.get("summary", "")),
        }

    # ------------------------------------------------------------------
    # Fallback
    # ------------------------------------------------------------------

    def _fallback_plan(
        self, goal: str, project_id: Optional[int], error: str
    ) -> Dict[str, Any]:
        """Return a minimal fallback plan when LLM fails."""
        steps = []
        if project_id:
            steps.append({
                "step_number": 1,
                "tool": "get_project_status",
                "params": {"project_id": project_id},
                "reason": "LLM 规划失败，先获取项目状态",
                "expected_outcome": "了解项目当前进展",
            })
            steps.append({
                "step_number": 2,
                "tool": "suggest_next_step",
                "params": {"project_id": project_id},
                "reason": "基于状态获取建议",
                "expected_outcome": "得到下一步操作建议",
            })
        else:
            steps.append({
                "step_number": 1,
                "tool": "list_projects",
                "params": {},
                "reason": "LLM 规划失败，先列出项目",
                "expected_outcome": "获取现有项目列表",
            })

        return {
            "success": False,
            "goal": goal,
            "project_id": project_id,
            "steps": steps,
            "summary": f"LLM 规划失败（{error}），使用默认回退计划",
            "raw_response": "",
        }
