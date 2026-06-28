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
# KNOWN_TARGETS 从 target_database 动态加载，避免硬编码与数据库不同步
# 支持精确匹配和模糊搜索（中英文/别名）

def _load_known_targets():
    """从靶点数据库加载所有已知靶点名称"""
    try:
        from ..services.target_database import SORTED_TARGET_NAMES
        return set(SORTED_TARGET_NAMES)
    except Exception:
        return set()


def _extract_target_from_message(message: str) -> Optional[str]:
    """
    从用户消息中提取/匹配已知靶点名称。
    1. 先尝试精确匹配（消息中包含完整靶点名）
    2. 再尝试模糊搜索（数据库中的别名/关键词匹配）
    3. 返回最匹配的靶点名称（数据库中的标准名）
    """
    msg_upper = message.upper()
    
    # 步骤1：精确匹配 - 按数据库中的靶点名称完整匹配
    known_targets = _load_known_targets()
    for target in sorted(known_targets, key=len, reverse=True):
        if target.upper() in msg_upper:
            return target
    
    # 步骤2：模糊搜索 - 查询 target_database 的搜索函数
    try:
        from ..services.target_database import search_targets
        results = search_targets(message)
        if results:
            # 返回最匹配的第一个
            return results[0]
    except Exception:
        pass
    
    return None


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
        
        # 注入统一的 LLMClient（如果未提供，使用默认单例）
        if llm_client is not None:
            self.llm = llm_client
        else:
            from .llm_client import get_default_client
            self.llm = get_default_client(api_key=api_key, model=model)
        
        self.api_key = api_key or KIMI_API_KEY
        self.model = model
        self.steps: List[ThoughtStep] = []
        self._last_llm_call = 0.0  # 保留用于向后兼容，但逻辑已移到 LLMClient

    # ------------------------------------------------------------------
    # Main entry
    # ------------------------------------------------------------------

    def run(self, user_message: str, context: Dict = None) -> Dict[str, Any]:
        """
        主执行循环（增强版 + Phase 5 追踪）。

        流程：
        a. 意图解析（Intent Parsing）→ 理解用户复杂输入
        b. 判断是否需要澄清 → 返回澄清问题
        c. 判断是否为简单聊天 → 直接返回聊天响应
        d. 判断是否需要表单 → 返回表单响应
        e. 多意图拆分 → 串行/并行执行子计划
        f. 目标导向 → Perceive → Plan → Execute → Report
        """
        import uuid
        trace_id = str(uuid.uuid4())[:8]
        
        context = context or {}
        context["trace_id"] = trace_id
        self.steps = []

        # Phase 5: 使用追踪器记录整个 ReAct 循环
        from .tracer import AgentTracer
        session_id = context.get("session_id")
        project_id = context.get("project_id")
        
        with AgentTracer(session_id=session_id, user_message=user_message, project_id=project_id) as tracer:
            # ===== 1. 意图解析 =====
            try:
                from .intent_parser import IntentParser, IntentType
                parser = IntentParser(api_key=self.api_key, model=self.model)
                parsed_intent = parser.parse(user_message, context)
                intent_context = parser.build_planning_context(parsed_intent)
                
                if parsed_intent:
                    tracer.set_intent(parsed_intent.intent_type.value if hasattr(parsed_intent.intent_type, 'value') else str(parsed_intent.intent_type))
            except Exception as e:
                parsed_intent = None
                intent_context = {}

            # ===== 2. 判断是否需要澄清 =====
            if parsed_intent and parsed_intent.needs_clarification:
                result = {
                    "success": True,
                    "type": "clarification",
                    "final_answer": parsed_intent.clarification_question,
                    "action_cards": [],
                    "steps": [],
                    "autonomous": False,
                    "parsed_intent": intent_context if parsed_intent else None,
                    "trace_id": trace_id,
                }
                tracer.finish(success=True, final_result=result)
                return result

            # ===== 3. 判断是否为简单聊天 =====
            is_chat = self._is_simple_chat_enhanced(user_message, parsed_intent)
            if is_chat.get("is_chat", False):
                chat_response = self._generate_chat_response(user_message, context)
                result = {
                    "success": True,
                    "type": "chat",
                    "steps": [],
                    "final_answer": chat_response,
                    "action_cards": [],
                    "autonomous": False,
                    "parsed_intent": intent_context if parsed_intent else None,
                    "trace_id": trace_id,
                }
                tracer.finish(success=True, final_result=result)
                return result

            # ===== 4. 判断是否需要表单 =====
            form_check = self._needs_form(user_message, context, parsed_intent)
            if form_check.get("needs_form", False):
                result = self._build_form_response(form_check)
                result["trace_id"] = trace_id
                tracer.finish(success=True, final_result=result)
                return result

            # ===== 5. 多意图处理 =====
            if parsed_intent and parsed_intent.primary_type == IntentType.MULTI_INTENT:
                sub_intents = parser.split_multi_intent(parsed_intent)
                if len(sub_intents) > 1:
                    result = self._execute_multi_intent(sub_intents, context, parser)
                    result["trace_id"] = trace_id
                    tracer.finish(success=result.get("success", False), final_result=result)
                    return result

            # ===== 6. 目标导向主流程 =====
            result = self._execute_goal_oriented(user_message, context, intent_context)
            result["trace_id"] = trace_id
            tracer.finish(success=result.get("success", False), final_result=result)
            return result

    def _execute_goal_oriented(self, user_message: str, context: Dict, intent_context: Dict) -> Dict[str, Any]:
        """执行目标导向的工作流。"""
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

        # 2. Plan（传入意图解析结果）
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
                intent_context=intent_context,
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
                "chat_summary": f"执行失败: {e}",
            }

        # 4. 条件步骤处理（如果 plan 中有 condition 步骤）
        if any("condition" in s for s in plan.get("steps", [])):
            report = self._handle_conditional_steps(plan, report, context)

        # 5. Build outputs
        action_cards = self._build_action_cards_from_plan(plan)
        thought_steps = self._build_thought_steps(report)

        return {
            "success": report.get("success", False),
            "type": "action",
            "steps": thought_steps,
            "final_answer": report.get("final_answer", ""),
            "chat_summary": report.get("chat_summary", ""),
            "action_cards": action_cards,
            "autonomous": True,
            "plan_summary": plan.get("summary", ""),
            "execution_report": report,
            "parsed_intent": intent_context,
        }

    def _execute_multi_intent(self, sub_intents: List, context: Dict, parser) -> Dict[str, Any]:
        """
        执行多意图拆分后的串行/并行处理。
        将多个子意图按顺序执行（有依赖）或并行执行（无依赖），结果合并。
        """
        import concurrent.futures
        
        all_results = []
        all_steps = []
        
        # 检测是否有依赖关系（简单判断：如果都涉及不同的项目ID，可以并行）
        can_parallel = len(sub_intents) <= 3  # 最多 3 个并行
        for i in range(len(sub_intents) - 1):
            entities_i = {e.type for e in sub_intents[i].entities}
            entities_j = {e.type for e in sub_intents[i + 1].entities}
            # 如果有相同的项目ID 或 靶点，认为有依赖
            if entities_i & entities_j:
                can_parallel = False
                break
        
        if can_parallel and len(sub_intents) > 1:
            # 并行执行
            with concurrent.futures.ThreadPoolExecutor(max_workers=len(sub_intents)) as executor:
                futures = []
                for sub_intent in sub_intents:
                    intent_context = parser.build_planning_context(sub_intent)
                    future = executor.submit(self._execute_goal_oriented, sub_intent.original_message, context, intent_context)
                    futures.append(future)
                
                for future in concurrent.futures.as_completed(futures):
                    result = future.result()
                    all_results.append(result)
                    all_steps.extend(result.get("steps", []))
        else:
            # 串行执行（原逻辑）
            for i, sub_intent in enumerate(sub_intents):
                intent_context = parser.build_planning_context(sub_intent)
                result = self._execute_goal_oriented(
                    sub_intent.original_message,
                    context,
                    intent_context
                )
                all_results.append(result)
                all_steps.extend(result.get("steps", []))
                
                # 将前一个结果作为后一个的上下文
                if result.get("success") and i < len(sub_intents) - 1:
                    context = {**context, "previous_result": result}

        # 合并所有结果
        combined_answer = self._merge_multi_intent_results(all_results)
        
        # 生成聊天摘要（多意图场景）
        chat_summary = combined_answer
        if len(combined_answer) > 200:
            lines = [l.strip() for l in combined_answer.strip().split('\n') if l.strip()]
            if lines:
                chat_summary = f"{lines[0]} ... 多个任务执行完成，详见下方报告。"
            else:
                chat_summary = "多个任务执行完成，详见下方报告。"
        
        return {
            "success": any(r.get("success", False) for r in all_results),
            "type": "multi_action",
            "steps": all_steps,
            "final_answer": combined_answer,
            "chat_summary": chat_summary,
            "action_cards": [],
            "autonomous": True,
            "sub_results": all_results,
            "parsed_intent": parser.build_planning_context(sub_intents[0]) if sub_intents else {},
        }

    def _merge_multi_intent_results(self, results: List[Dict]) -> str:
        """合并多个子意图的执行结果。"""
        parts = []
        for i, result in enumerate(results, 1):
            answer = result.get("final_answer", "")
            if answer:
                parts.append(f"### 任务 {i}\n{answer}")
        return "\n\n".join(parts) if parts else "所有任务已完成。"

    def _handle_conditional_steps(self, plan: Dict, report: Dict, context: Dict) -> Dict[str, Any]:
        """处理计划中的条件步骤。"""
        # 条件步骤已在 executor 中处理，这里可以添加额外的条件后处理
        # 例如：如果条件未满足，给出替代建议
        return report

    # ------------------------------------------------------------------
    # LLM wrapper
    # ------------------------------------------------------------------

    def call_llm(self, messages: List[Dict[str, str]], temperature: float = 0.7) -> str:
        """
        调用 LLM（向后兼容接口）。
        实际逻辑已委托给 LLMClient。
        """
        return self.llm.call(messages, temperature=temperature)

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
        """调用模块级函数进行靶点提取（支持精确匹配 + 模糊搜索）。"""
        return _extract_target_from_message(message)

    # ------------------------------------------------------------------
    # Simple chat detection
    # ------------------------------------------------------------------

    def _is_simple_chat_enhanced(self, message: str, parsed_intent: Any = None) -> Dict[str, Any]:
        """
        增强版聊天检测。结合意图解析结果 + 传统方法双重判断。
        """
        # 如果意图解析已明确分类，优先使用
        if parsed_intent:
            from .intent_parser import IntentType
            if parsed_intent.primary_type == IntentType.SIMPLE_CHAT:
                return {"is_chat": True, "reason": "意图解析器判定为简单聊天", "confidence": parsed_intent.confidence}
            if parsed_intent.primary_type in [IntentType.SINGLE_ACTION, IntentType.MULTI_INTENT, 
                                               IntentType.COMPLEX_ANALYSIS, IntentType.CONDITIONAL,
                                               IntentType.COMPARISON, IntentType.OPTIMIZATION,
                                               IntentType.FOLLOW_UP, IntentType.EXPLORATION]:
                return {"is_chat": False, "reason": f"意图解析器判定为: {parsed_intent.primary_type.value}", "confidence": parsed_intent.confidence}
        
        # 回退到传统方法
        return self._is_simple_chat(message)

    def _is_simple_chat(self, message: str) -> Dict[str, Any]:
        """
        传统聊天检测（回退用）。
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
    # Form detection (parameter collection) - Enhanced
    # ------------------------------------------------------------------

    def _needs_form(self, message: str, context: Dict, parsed_intent: Any = None) -> Dict[str, Any]:
        """
        增强版表单检测。结合上下文判断是否需要收集参数。
        关键规则：如果上下文中有项目ID，大多数请求直接执行，不需要表单。
        """
        msg_lower = message.lower()
        project_id = context.get("project_id")
        
        # 如果意图解析已识别需要澄清，但上下文有项目ID，降低澄清强度
        if parsed_intent and parsed_intent.needs_clarification:
            # 如果上下文有项目ID，且用户只是缺少靶点，尝试从上下文推断
            if project_id:
                missing = parsed_intent.clarification_question
                if "项目ID" in missing or "项目" in missing:
                    # 上下文有项目ID，不需要澄清
                    return {"needs_form": False, "project_id": project_id}
            # 否则确实需要澄清（如缺少靶点名称）
            return {"needs_form": True, "form_type": "clarification", "question": parsed_intent.clarification_question}
        
        # 如果消息中包含已知靶点，无需表单，直接走 ReAct
        detected_target = self._extract_target_from_message(message)
        if detected_target:
            return {"needs_form": False, "target": detected_target}
        
        # 创建项目意图：如果没有上下文且无靶点，需要表单
        create_patterns = ['创建项目', '新建项目', '新项目', '开始项目', '创建一个新项目']
        is_create_intent = any(p in msg_lower for p in create_patterns)
        
        if is_create_intent:
            # 如果已有项目上下文，不需要表单
            if project_id:
                return {"needs_form": False}
            # 无项目上下文且无靶点，需要表单
            return {"needs_form": True, "form_type": "project_creation"}
        
        # 多意图且无明确实体：如果上下文有项目ID，直接执行
        if parsed_intent and parsed_intent.primary_type.value == "multi_intent":
            if project_id:
                return {"needs_form": False}
            if not any(e.type in ["target", "project_id", "smiles"] for e in parsed_intent.entities):
                return {"needs_form": True, "form_type": "clarification", "question": "请明确你要执行的具体操作对象（靶点/项目/分子）。"}
        
        # 用户说"帮我分析"、"优化一下"、"查看结果"等：如果有上下文项目ID，直接执行
        action_keywords = ["分析", "优化", "查看", "检查", "评估", "调整", "对比", "运行"]
        if any(kw in msg_lower for kw in action_keywords):
            if project_id:
                return {"needs_form": False, "project_id": project_id}
        
        return {"needs_form": False}

    def _build_form_response(self, form_check: Dict) -> Dict[str, Any]:
        """构建需要表单响应。"""
        form_type = form_check.get("form_type", "")
        
        if form_type == "clarification":
            return {
                "success": True,
                "type": "clarification",
                "form_type": "clarification",
                "final_answer": form_check.get("question", "我需要更多信息才能继续。"),
                "action_cards": [],
                "steps": [],
                "autonomous": False,
            }
        
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
        
        # 实例级上下文记忆：当 db/session 不可用时提供回退
        self._last_project_id: Optional[int] = None
        self._last_target: Optional[str] = None

    def _register_default_tools(self):
        """注册默认工具（占位，实际工具在 tools.py 中定义）"""
        pass

    def chat(self, message: str, project_id: int = None, session_id: str = None, db=None) -> Dict[str, Any]:
        """
        主聊天接口（增强版：自动推断 project_id + 统一处理 + 实例级上下文记忆）
        """
        # 优先使用传入的 db 连接，否则使用 self.db
        db_conn = db or self.db
        
        # 1. 自动推断 project_id（多优先级：显式传入 > session 记忆 > 实例记忆）
        effective_project_id = project_id
        if not effective_project_id and db_conn and session_id:
            from .memory import get_session_project_id
            effective_project_id = get_session_project_id(db_conn, session_id)
        if not effective_project_id:
            # 回退到实例级记忆
            effective_project_id = self._last_project_id
        
        # 2. 从消息中提取靶点（如果有）
        detected_target = _extract_target_from_message(message)
        if detected_target:
            self._last_target = detected_target
        
        # 构建上下文，包含实例级记忆
        context = {
            "project_id": effective_project_id,
            "session_id": session_id,
            "last_target": self._last_target,
        }

        # 3. 保存用户消息到记忆（使用 effective_project_id）
        if db_conn and session_id:
            from .memory import save_message, update_session_project_id
            save_message(db_conn, session_id, "user", message, project_id=effective_project_id)
            if effective_project_id and not project_id:
                update_session_project_id(db_conn, session_id, effective_project_id)

        # 4. 运行增强版 ReAct 引擎
        result = self.engine.run(message, context)

        # 5. 从结果中更新实例级记忆
        if result.get("success"):
            report = result.get("execution_report", {})
            # 如果执行中创建了项目，更新 last_project_id
            if report and report.get("project_id"):
                self._last_project_id = report.get("project_id")
            # 如果 context 中有 project_id，也更新
            if effective_project_id:
                self._last_project_id = effective_project_id
        
        # 6. 保存助手回复到记忆（使用 chat_summary 避免重复显示）
        if db_conn and session_id:
            from .memory import save_message
            # 优先使用 chat_summary（简短版本），避免聊天消息显示完整报告
            final_answer_for_db = result.get("chat_summary", result.get("final_answer", ""))
            save_message(
                db_conn, session_id, "assistant", final_answer_for_db,
                project_id=effective_project_id,
                metadata={
                    "action_cards": result.get("action_cards", []),
                    "autonomous": result.get("autonomous", False),
                    "actions": result.get("execution_report", {}).get("actions", []),
                    "has_detailed_report": bool(result.get("final_answer")),
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
