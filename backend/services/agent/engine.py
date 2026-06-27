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

# 常见药物靶点名称
KNOWN_TARGETS = {
    "EGFR", "ALK", "BRAF", "KRAS", "PI3K", "MTOR", "VEGFR", "PDGFR", "FGFR",
    "HER2", "JAK", "STAT", "GSK3B", "CDK", "HDAC", "PARP", "AKT", "MEK", "ERK",
    "AMPK", "SIRT", "NAMPT", "PPAR", "FXR", "LXR", "ROR", "REV", "ERR", "ROCK",
    "BCL2", "BCLXL", "MCL1", "XIAP", "BRD4", "BET", "EZH2", "IDH1", "IDH2",
    "FLT3", "KIT", "PD1", "PDL1", "CTLA4", "LAG3", "TIM3", "TIGIT", "VISTA",
    "TNF", "IL6", "IL17", "IL23", "CSF1R", "TIE2", "MET", "RET", "ROS1",
    "TRK", "NTRK", "SMO", "PTCH", "GLI", "WNT", "BETA", "GAMMA", "DELTA",
    "AR", "ER", "PR", "GR", "MR", "SHP2", "SOS1", "KRA", "NRAS", "HRAS",
}


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
        b. 判断是否需要表单收集参数 → 返回表单响应
        c. 如果是目标导向 → Perceive → Plan → Execute → Report
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

        # ---- b. Check if form is needed --------------------------------
        form_check = self._needs_form(user_message, context)
        if form_check.get("needs_form", False):
            return self._build_form_response(form_check)

        # ---- c. Goal-oriented autonomous workflow --------------------
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
            return "API Key 未配置，无法调用 LLM 服务。"

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
    # Target detection
    # ------------------------------------------------------------------

    def _extract_target_from_message(self, message: str) -> Optional[str]:
        """
        从用户消息中提取已知靶点名称。
        匹配 KNOWN_TARGETS 中的靶点名（不区分大小写）。
        返回大写标准名称，如 'EGFR'。
        """
        msg_upper = message.upper()
        # 按长度降序匹配，避免短名匹配到长名的子串（如 RAF 匹配到 BRAF）
        for target in sorted(KNOWN_TARGETS, key=len, reverse=True):
            if target in msg_upper:
                return target
        return None

    # ------------------------------------------------------------------
    # Simple chat detection
    # ------------------------------------------------------------------

    def _is_simple_chat(self, message: str) -> Dict[str, Any]:
        """
        判断用户消息是简单聊天还是目标导向操作请求。
        三层判断：关键词快速匹配 → LLM 智能分析 → 长度 fallback
        """
        # P0: 靶点名称检测——如果消息中包含已知靶点，不是简单聊天
        detected_target = self._extract_target_from_message(message)
        if detected_target:
            return {"is_chat": False, "reason": f"检测到靶点名称：{detected_target}", "target": detected_target}
        
        # P1: 快速过滤——明显是聊天的短消息
        if len(message) < 8:
            return {"is_chat": True, "reason": "短消息，默认聊天"}
        
        # P2: 关键词快速匹配（聊天模式）
        chat_patterns = [
            "你好", "hello", "hi", "嗨", "谢谢", "再见", "bye",
            "在吗", "你是谁", "你能做什么", "介绍一下",
            "什么是", "怎么理解", "解释一下", "为什么",
        ]
        msg_lower = message.lower()
        for pattern in chat_patterns:
            if pattern in msg_lower:
                return {"is_chat": True, "reason": f"匹配聊天模式：{pattern}"}
        
        # P3: 关键词快速匹配（目标导向模式）
        action_patterns = [
            "创建", "运行", "分析", "调整", "查看", "对比", "建议",
            "pipeline", "project", "项目", "分子", "优化", "生成",
            "执行", "开始", "处理", "帮我", "自动",
        ]
        for pattern in action_patterns:
            if pattern in msg_lower:
                return {"is_chat": False, "reason": f"匹配操作模式：{pattern}"}
        
        # P4: LLM 智能分析（最准确但耗时）
        prompt = (
            '你是消息分类助手。判断以下消息是"简单聊天"还是"目标导向操作请求"。\n'
            '简单聊天：询问知识、打招呼、闲聊、表达观点\n'
            '目标导向：要求执行某个操作、分析数据、创建项目、运行流程\n'
            '只返回 JSON：{"is_chat": true/false, "reason": "简要原因", "confidence": 0.0-1.0}\n\n'
            f'用户消息："{message}"'
        )
        
        raw = self.call_llm(
            [{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        try:
            parsed = self._parse_llm_plan(raw)
            if "is_chat" in parsed:
                # LLM 高置信度时直接采用
                confidence = parsed.get("confidence", 0.5)
                if confidence >= 0.7:
                    return parsed
                # 低置信度时保守处理（默认聊天，避免误操作）
                return {"is_chat": True, "reason": f"LLM 低置信度({confidence})，保守处理为聊天"}
        except Exception:
            pass
        
        # P5: 最终 fallback——保守处理（默认聊天，避免误操作）
        return {"is_chat": True, "reason": "无法判断，保守处理为聊天"}

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
    # Form detection (parameter collection)
    # ------------------------------------------------------------------

    def _needs_form(self, message: str, context: Dict) -> Dict[str, Any]:
        """
        判断是否需要表单收集缺失参数。
        
        Returns:
            {"needs_form": False} 或 {"needs_form": True, "form_type": "..."}
        """
        msg_lower = message.lower()
        
        # 如果消息中包含已知靶点，无需表单，直接走 ReAct
        detected_target = self._extract_target_from_message(message)
        if detected_target:
            return {"needs_form": False, "target": detected_target}
        
        # 创建项目意图
        create_patterns = ['创建项目', '新建项目', '新项目', '开始项目', '创建一个新项目']
        is_create_intent = any(p in msg_lower for p in create_patterns)
        
        if is_create_intent:
            # 如果已有项目上下文，不需要表单
            if context.get("project_id"):
                return {"needs_form": False}
            # 无项目上下文且无靶点，需要表单
            return {"needs_form": True, "form_type": "project_creation"}
        
        return {"needs_form": False}

    def _build_form_response(self, form_check: Dict) -> Dict[str, Any]:
        """构建需要表单响应。"""
        form_type = form_check.get("form_type", "")
        
        if form_type == "project_creation":
            return {
                "success": True,
                "type": "form",
                "form_type": "create_project",
                "final_answer": "我可以直接帮你基于靶点名称自动创建项目并运行 Pipeline。请直接告诉我靶点名称（如 EGFR、BRAF），或在下方选择靶点。",
                "action_cards": [],
                "steps": [],
                "autonomous": False,
            }
        
        return {
            "success": True,
            "type": "form",
            "form_type": form_type,
            "final_answer": "请补充必要信息。",
            "action_cards": [],
            "steps": [],
            "autonomous": False,
        }

    # ------------------------------------------------------------------
    # Output builders
    # ------------------------------------------------------------------

    def _build_action_cards_from_plan(self, plan: Dict[str, Any]) -> List[Dict]:
        """Agent 自主模式下不返回 Action Cards，用户不需要手动点击。"""
        return []

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

    def chat(self, message: str, project_id: int = None, session_id: str = None, db=None) -> Dict[str, Any]:
        """
        主聊天接口（增强版：自动推断 project_id + 统一处理）
        """
        # 优先使用传入的 db 连接，否则使用 self.db
        db_conn = db or self.db
        
        # 1. 自动推断 project_id（从 session 记忆中获取）
        inferred_project_id = None
        if db_conn and session_id:
            from .memory import get_session_project_id
            inferred_project_id = get_session_project_id(db_conn, session_id)
        
        # 优先级：显式传入 > session 记忆 > None
        effective_project_id = project_id or inferred_project_id
        
        context = {
            "project_id": effective_project_id,
            "session_id": session_id,
        }

        # 2. 保存用户消息到记忆（使用 effective_project_id）
        if db_conn and session_id:
            from .memory import save_message, update_session_project_id
            save_message(db_conn, session_id, "user", message, project_id=effective_project_id)
            # 如果 project_id 已推断，更新 session 关联
            if effective_project_id and not inferred_project_id:
                update_session_project_id(db_conn, session_id, effective_project_id)

        # 3. 运行增强版 ReAct 引擎
        result = self.engine.run(message, context)

        # 4. 保存助手回复到记忆
        if db_conn and session_id:
            from .memory import save_message
            final_answer = result.get("final_answer", "")
            save_message(
                db_conn, session_id, "assistant", final_answer,
                project_id=effective_project_id,
                metadata={
                    "action_cards": result.get("action_cards", []),
                    "autonomous": result.get("autonomous", False),
                    "actions": result.get("execution_report", {}).get("actions", []),
                },
            )

        return result

    def execute_action_card(self, action: str, params: Dict) -> Dict[str, Any]:
        """
        执行用户确认的 Action Card
        """
        tool_func = self.tools.get(action)
        if not tool_func:
            return {"success": False, "error": f"未知动作: {action}"}
        try:
            result = tool_func(**params)
            return {"success": True, "data": result}
        except Exception as e:
            return {"success": False, "error": str(e)}
