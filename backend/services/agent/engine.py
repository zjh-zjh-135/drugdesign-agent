"""
engine.py - DrugDesign Copilot Agent Core Engine (COMPLETE REWRITE)

ReAct 模式增强版: Perceive → Plan → Execute → Adapt → Report

Key changes from previous version:
- Removed keyword-based parse_user_intent and _extract_params
- LLM-driven perception, planning, and execution adaptation
- Supports both simple chat and goal-oriented autonomous workflows
- call_llm() method with KIMI API integration
- JSON parsing with robust error handling and fallback
"""

import json
import os
import re
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

import requests

KIMI_API_KEY = os.environ.get("KIMI_API_KEY", "")
KIMI_API_URL = "https://api.moonshot.cn/v1/chat/completions"
DEFAULT_MODEL = "moonshot-v1-8k"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Action:
    """Agent 可执行的动作"""
    tool: str
    params: Dict[str, Any] = field(default_factory=dict)
    id: int = 0


@dataclass
class Observation:
    """工具执行后的观察结果"""
    action_id: int
    result: Any
    status: str = "ok"   # ok / error / partial
    error: str = ""


@dataclass
class ThoughtStep:
    """ReAct 思考链中的一步（增强版）"""
    step: int
    thought: str
    action: Optional[Action] = None
    observation: Optional[Observation] = None
    timestamp: datetime = field(default_factory=datetime.now)
    llm_raw: str = ""           # raw LLM response for this step
    decision: str = ""          # continue / modify / finish
    plan_step: Optional[Dict] = None  # associated plan step metadata


# ---------------------------------------------------------------------------
# Tool Registry
# ---------------------------------------------------------------------------

class ToolRegistry:
    """工具注册表 - 所有 Agent 可调用的工具"""
    def __init__(self):
        self._tools: Dict[str, Any] = {}
        self._schemas: Dict[str, Dict] = {}

    def register(self, name: str, func, schema: Dict = None):
        self._tools[name] = func
        self._schemas[name] = schema or {}

    def get(self, name: str) -> Optional[Any]:
        return self._tools.get(name)

    def list_tools(self) -> List[Dict]:
        tools = []
        for name, schema in self._schemas.items():
            tools.append({
                "name": name,
                "description": schema.get("description", ""),
                "parameters": schema.get("parameters", {})
            })
        return tools

    def execute(self, action: Action) -> Observation:
        func = self._tools.get(action.tool)
        if not func:
            return Observation(
                action_id=action.id,
                result=None,
                status="error",
                error=f"工具 '{action.tool}' 未注册"
            )
        try:
            result = func(**action.params)
            return Observation(action_id=action.id, result=result, status="ok")
        except Exception as e:
            return Observation(action_id=action.id, result=None, status="error", error=str(e))


# ---------------------------------------------------------------------------
# ReActEngine (rewritten)
# ---------------------------------------------------------------------------

class ReActEngine:
    """
    增强版 ReAct 推理引擎

    核心循环:
    1. Perceive: 感知环境状态
    2. Plan: LLM 生成多步计划
    3. Execute: 逐步执行，每步后反馈给 LLM
    4. Adapt: 根据结果动态调整计划
    5. Report: 生成最终报告
    """

    def __init__(
        self,
        tool_registry: ToolRegistry,
        memory_store=None,
        max_steps: int = 10,
        llm_client=None,
        api_key: Optional[str] = None,
        model: str = DEFAULT_MODEL,
    ):
        self.tools = tool_registry
        self.memory = memory_store
        self.max_steps = max_steps
        self.llm = llm_client
        self.api_key = api_key or KIMI_API_KEY
        self.model = model
        self.steps: List[ThoughtStep] = []
        self._last_llm_call = 0.0

    # ------------------------------------------------------------------
    # Main entry
    # ------------------------------------------------------------------

    def run(self, user_message: str, context: Dict = None) -> Dict[str, Any]:
        """
        主执行循环。

        a. 判断是否为简单聊天（无目标导向）→ 直接返回聊天响应
        b. 如果是目标导向 → Perceive → Plan → Execute → Report
        """
        context = context or {}
        self.steps = []

        # ---- a. Check if simple chat -----------------------------------
        chat_check = self._is_simple_chat(user_message)
        if chat_check.get("is_chat", False):
            chat_response = self._generate_chat_response(user_message, context)
            return {
                "success": True,
                "type": "chat",
                "steps": [],
                "final_answer": chat_response,
                "action_cards": [],
                "autonomous": False,
            }

        # ---- b. Goal-oriented autonomous workflow --------------------
        project_id = context.get("project_id")

        # 1. Perceive
        try:
            from .perception import EnvironmentPerception
            perception = EnvironmentPerception(tool_registry=self.tools)
            env_state = perception.get_state(project_id)
            env_report = perception.format_for_llm(env_state)
        except Exception as e:
            env_state = {"error": str(e)}
            env_report = f"环境感知失败: {e}"

        # 2. Plan
        try:
            from .planner import TaskPlanner
            planner = TaskPlanner(
                api_key=self.api_key,
                model=self.model,
                temperature=0.3,
                max_steps=self.max_steps,
            )
            plan = planner.plan(
                goal=user_message,
                project_id=project_id,
                env_state=env_state,
                available_tools=self.tools.list_tools(),
            )
        except Exception as e:
            plan = {"success": False, "steps": [], "summary": f"规划失败: {e}", "raw_response": ""}

        # 3. Execute
        try:
            from .executor import TaskExecutor
            executor = TaskExecutor(
                tool_registry=self.tools,
                api_key=self.api_key,
                model=self.model,
                temperature=0.3,
            )
            execution_log = executor.execute_plan(
                plan=plan,
                project_id=project_id,
                env_state=env_state,
            )
            report = executor.to_report(execution_log)
        except Exception as e:
            report = {
                "success": False,
                "goal": user_message,
                "project_id": project_id,
                "steps": [],
                "final_answer": f"执行失败: {e}",
            }

        # 4. Build action cards from the plan for UI
        action_cards = self._build_action_cards_from_plan(plan)

        # 5. Build ThoughtSteps for compatibility
        thought_steps = self._build_thought_steps(report)

        return {
            "success": report.get("success", False),
            "type": "action",
            "steps": thought_steps,
            "final_answer": report.get("final_answer", ""),
            "action_cards": action_cards,
            "autonomous": True,
            "plan_summary": plan.get("summary", ""),
            "execution_report": report,
        }

    # ------------------------------------------------------------------
    # LLM wrapper
    # ------------------------------------------------------------------

    def call_llm(self, messages: List[Dict[str, str]], temperature: float = 0.7) -> str:
        """
        Call the KIMI API (moonshot-v1-8k).

        Args:
            messages: OpenAI-style message list [{"role": "...", "content": "..."}]
            temperature: Sampling temperature

        Returns:
            Raw text content from the LLM, or empty string on failure.
        """
        if not self.api_key:
            return ""

        # Rate limit guard
        elapsed = time.time() - self._last_llm_call
        if elapsed < 1.0:
            time.sleep(1.0 - elapsed)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }

        try:
            resp = requests.post(
                KIMI_API_URL, headers=headers, json=payload, timeout=60
            )
            resp.raise_for_status()
            data = resp.json()
            content = (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
            )
            self._last_llm_call = time.time()
            return content
        except Exception:
            self._last_llm_call = time.time()
            return ""

    # ------------------------------------------------------------------
    # System prompts
    # ------------------------------------------------------------------

    def _build_system_prompt(self, available_tools: List[Dict]) -> str:
        """Build a comprehensive system prompt for the ReAct loop."""
        tools_desc = []
        for t in available_tools:
            params = json.dumps(t.get("parameters", {}), ensure_ascii=False, indent=2)
            tools_desc.append(f"- {t.get('name', 'unknown')}: {t.get('description', '')}\n  参数: {params}")
        tools_text = "\n".join(tools_desc)

        return f"""你是 DrugDesign Copilot Agent，一个专业的药物设计 AI Agent。

你的任务是通过感知、规划、执行、适应的方式帮助用户完成药物设计任务。

## 可用工具
{tools_text}

## ReAct 格式规范

每次回复必须遵循以下格式之一：

**格式 A - 需要执行工具：**
Thought: [你的思考过程，分析当前状态和用户意图]
Action: {{
  "tool": "工具名称",
  "params": {{
    "参数名": "参数值"
  }}
}}

**格式 B - 最终回答：**
Thought: [总结思考过程]
Final Answer: [给用户的完整回答]

## 重要规则
1. 一次只能执行一个 Action
2. 如果工具返回成功，根据结果继续思考下一步
3. 如果工具返回错误，分析原因并尝试修复或告知用户
4. 所有回答使用中文
5. 对于药物设计专业术语，提供简明解释
"""

    # ------------------------------------------------------------------
    # JSON parsing helpers
    # ------------------------------------------------------------------

    def _parse_llm_plan(self, raw: str) -> Dict[str, Any]:
        """Parse a JSON plan from LLM response."""
        text = raw.strip()

        # Remove markdown fences
        code_fence = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if code_fence:
            text = code_fence.group(1).strip()

        if not text.startswith("{"):
            match = re.search(r"(\{[\s\S]*\})", text)
            if match:
                text = match.group(1).strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {}

    def _parse_llm_decision(self, raw: str) -> Dict[str, Any]:
        """Parse a decision JSON from LLM response."""
        parsed = self._parse_llm_plan(raw)
        if not parsed:
            return {
                "decision": "continue",
                "thought": "解析失败，默认继续",
                "answer": "",
                "new_steps": [],
                "raw": raw,
            }
        return {
            "decision": parsed.get("decision", "continue"),
            "thought": parsed.get("thought", ""),
            "answer": parsed.get("answer", ""),
            "new_steps": parsed.get("new_steps", []),
            "raw": raw,
        }

    # ------------------------------------------------------------------
    # Simple chat detection
    # ------------------------------------------------------------------

    def _is_simple_chat(self, message: str) -> Dict[str, Any]:
        """
        Determine if the user message is simple chat (no goal-oriented action).
        Uses a lightweight LLM prompt, with keyword fallback.
        """
        # Quick keyword heuristic for common chat patterns
        chat_indicators = [
            "你好", "hello", "hi", "嗨", "谢谢", "再见", "bye",
            "在吗", "你是谁", "你能做什么", "介绍一下", "？", "?",
        ]
        action_indicators = [
            "创建", "运行", "分析", "调整", "查看", "对比", "建议",
            "pipeline", "project", "项目", "分子", "优化", "生成",
        ]

        msg_lower = message.lower()
        chat_score = sum(1 for c in chat_indicators if c in msg_lower)
        action_score = sum(1 for a in action_indicators if a in msg_lower)

        # If strong chat signals and weak action signals, treat as chat
        if chat_score > 0 and action_score == 0:
            return {"is_chat": True, "reason": "keyword_heuristic"}
        if action_score > 0:
            return {"is_chat": False, "reason": "keyword_heuristic"}

        # Ambiguous -> ask LLM
        prompt = (
            '判断以下用户消息是"简单聊天"还是"目标导向的操作请求"。\n'
            '只返回 JSON：{"is_chat": true/false, "reason": "简短原因"}\n\n'
            f'用户消息："{message}"'
        )

        raw = self.call_llm(
            [{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        try:
            parsed = self._parse_llm_plan(raw)
            if "is_chat" in parsed:
                return parsed
        except Exception:
            pass

        # Final fallback: if message is very short, treat as chat
        return {"is_chat": len(message) < 15, "reason": "length_fallback"}

    def _generate_chat_response(self, message: str, context: Dict) -> str:
        """Generate a simple chat response using the LLM."""
        system = self._build_system_prompt(self.tools.list_tools())
        user = f"用户说：{message}\n\n请直接回答，不需要执行任何工具。"
        raw = self.call_llm(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0.7,
        )
        if raw:
            # Extract Final Answer if present
            match = re.search(r"Final Answer:\s*([\s\S]*)", raw, re.I)
            if match:
                return match.group(1).strip()
            return raw
        return "你好！我是 DrugDesign Copilot，可以帮你管理项目、运行 Pipeline、分析分子等。有什么可以帮你的吗？"

    # ------------------------------------------------------------------
    # Fallback keyword matching (simplified)
    # ------------------------------------------------------------------

    def _fallback_keyword_intent(self, message: str) -> Dict[str, Any]:
        """
        Simplified keyword-based intent detection (fallback when LLM fails).
        """
        action_keywords = {
            "create_project": ["创建项目", "新建项目", "新项目", "开始项目"],
            "run_pipeline": ["运行pipeline", "执行pipeline", "运行流程", "生成分子", "开始生成"],
            "analyze_failures": ["分析失败", "失败原因", "为什么失败", "查看失败"],
            "adjust_filters": ["调整过滤", "修改过滤", "过滤参数", "调整阈值"],
            "get_project_status": ["项目状态", "查看项目", "项目进展", "当前状态"],
            "compare_molecules": ["对比分子", "比较分子", "分子对比"],
            "suggest_next_step": ["下一步", "建议", "接下来怎么做"],
        }

        detected = []
        for tool_name, keywords in action_keywords.items():
            for kw in keywords:
                if kw in message:
                    detected.append(tool_name)
                    break

        if detected:
            return {"type": "action", "tools": detected}
        return {"type": "chat"}

    # ------------------------------------------------------------------
    # Output builders
    # ------------------------------------------------------------------

    def _build_action_cards_from_plan(self, plan: Dict[str, Any]) -> List[Dict]:
        """Generate action cards from the plan steps for the frontend."""
        cards = []
        steps = plan.get("steps", [])[:5]
        for i, step in enumerate(steps):
            tool_name = step.get("tool", "")
            params = step.get("params", {})

            card_templates = {
                "create_project": ("创建项目", "folder-plus"),
                "run_pipeline": ("运行 Pipeline", "play"),
                "analyze_failures": ("分析失败分子", "alert-triangle"),
                "adjust_filters": ("调整过滤参数", "sliders"),
                "get_project_status": ("查看项目状态", "activity"),
                "compare_molecules": ("分子对比", "git-compare"),
                "suggest_next_step": ("下一步建议", "lightbulb"),
                "list_projects": ("列出项目", "list"),
            }

            title, icon = card_templates.get(tool_name, (f"执行 {tool_name}", "zap"))
            cards.append({
                "title": title,
                "description": step.get("reason", "") or f"步骤 {i + 1}: {tool_name}",
                "icon": icon,
                "action": tool_name,
                "params": params,
                "status": "ready",
            })
        return cards

    def _build_thought_steps(self, report: Dict[str, Any]) -> List[Dict]:
        """Convert execution report steps to ThoughtStep-compatible dicts."""
        steps = []
        for s in report.get("steps", []):
            steps.append({
                "step": s.get("step_number", 0),
                "thought": s.get("reason", "") or s.get("llm_thought", ""),
                "action": {
                    "tool": s.get("tool", ""),
                    "params": s.get("params", {}),
                },
                "observation": s.get("observation", {}),
                "status": s.get("status", "unknown"),
            })
        return steps

    # ------------------------------------------------------------------
    # Legacy compatibility wrappers
    # ------------------------------------------------------------------

    def execute_step(self, user_message: str, context: Dict = None) -> Dict[str, Any]:
        """
        Legacy single-step execution (kept for backward compatibility).
        Delegates to the new run() method.
        """
        result = self.run(user_message, context)
        if result.get("type") == "chat":
            return {
                "type": "chat",
                "thought": "用户发起普通对话",
                "action": None,
                "observation": None,
            }
        steps = result.get("steps", [])
        if steps:
            first = steps[0]
            return {
                "type": "action",
                "thought": first.get("thought", ""),
                "action": first.get("action"),
                "observation": first.get("observation", {}),
                "status": first.get("status", "ok"),
            }
        return {
            "type": "chat",
            "thought": "无执行步骤",
            "action": None,
            "observation": None,
        }

    def parse_user_intent(self, message: str) -> Dict[str, Any]:
        """
        DEPRECATED: Keyword-based intent parsing removed.
        Kept as a thin wrapper for compatibility; uses LLM fallback.
        """
        check = self._is_simple_chat(message)
        if check.get("is_chat", False):
            return {"type": "chat"}
        # If not chat, we don't know the exact tools without planning
        return {"type": "action", "tools": []}

    def _extract_params(self, tool_name: str, message: str, context: Dict = None) -> Dict[str, Any]:
        """
        DEPRECATED: Parameter extraction removed.
        Kept for compatibility; returns empty params.
        """
        return {}

    def _generate_action_cards(self, result: Dict) -> List[Dict]:
        """DEPRECATED: Kept for compatibility."""
        return []

    def _generate_final_answer(self, result: Dict) -> str:
        """DEPRECATED: Kept for compatibility."""
        return result.get("final_answer", "")


# ---------------------------------------------------------------------------
# CopilotAgent (main entry)
# ---------------------------------------------------------------------------

class CopilotAgent:
    """
    DrugDesign Copilot Agent 主入口
    封装 ReActEngine + ToolRegistry + Memory，对外提供简洁接口
    """

    def __init__(self, db_session=None, tool_registry=None):
        self.db = db_session
        if tool_registry:
            self.tools = tool_registry
        else:
            from .tools import get_registry
            self.tools = get_registry()
        self.engine = ReActEngine(self.tools)
        self._register_default_tools()

    def _register_default_tools(self):
        """注册默认工具（占位，实际工具在 tools.py 中定义）"""
        pass

    def chat(self, message: str, project_id: int = None, session_id: str = None) -> Dict[str, Any]:
        """
        主聊天接口

        Args:
            message: 用户输入
            project_id: 当前项目ID（可选）
            session_id: 会话ID（可选）

        Returns:
            包含回答、action_cards、status 的字典
        """
        context = {"project_id": project_id, "session_id": session_id}

        # 保存用户消息到记忆
        if self.db and session_id:
            from .memory import save_message
            save_message(self.db, session_id, "user", message, project_id=project_id)

        # 运行增强版 ReAct 引擎
        result = self.engine.run(message, context)

        # 保存助手回复到记忆
        if self.db and session_id:
            from .memory import save_message
            final_answer = result.get("final_answer", "")
            save_message(
                self.db, session_id, "assistant", final_answer,
                project_id=project_id,
                metadata={
                    "action_cards": result.get("action_cards", []),
                    "autonomous": result.get("autonomous", False),
                },
            )

        return result

    def execute_action_card(self, action: str, params: Dict) -> Dict[str, Any]:
        """
        执行用户确认的 Action Card

        Args:
            action: 动作名称（如 "run_pipeline"）
            params: 动作参数

        Returns:
            执行结果
        """
        tool_func = self.tools.get(action)
        if not tool_func:
            return {"success": False, "error": f"未知动作: {action}"}
        try:
            result = tool_func(**params)
            return {"success": True, "data": result}
        except Exception as e:
            return {"success": False, "error": str(e)}
