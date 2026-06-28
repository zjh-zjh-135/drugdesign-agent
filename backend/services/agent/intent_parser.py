"""
intent_parser.py - Advanced User Intent Parser for DrugDesign Copilot

解析复杂用户输入，支持：
- 多意图识别与拆分（Multi-Intent Splitting）
- 实体提取（Entity Extraction: 靶点、分子、项目ID、SMILES等）
- 意图分类（Intent Classification: 简单操作、复杂分析、条件性请求、多意图组合）
- 模糊意图澄清（Ambiguity Resolution）
- 上下文依赖检测（Context Dependencies）
- 条件步骤检测（Conditional Step Detection）
"""

import json
import os
import re
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

import requests

KIMI_API_KEY = os.environ.get("KIMI_API_KEY", "")
KIMI_API_URL = "https://api.moonshot.cn/v1/chat/completions"
DEFAULT_MODEL = "moonshot-v1-32k"


class IntentType(Enum):
    """用户意图类型"""
    SIMPLE_CHAT = "simple_chat"           # 简单聊天
    SINGLE_ACTION = "single_action"       # 单一操作
    MULTI_INTENT = "multi_intent"         # 多意图组合
    COMPLEX_ANALYSIS = "complex_analysis" # 复杂分析请求
    CONDITIONAL = "conditional"           # 条件性请求（如果...就...）
    CLARIFICATION_NEEDED = "clarification_needed"  # 需要澄清
    COMPARISON = "comparison"             # 对比请求
    OPTIMIZATION = "optimization"         # 优化/迭代请求
    FOLLOW_UP = "follow_up"               # 上下文依赖（基于之前结果）
    EXPLORATION = "exploration"           # 探索/发现请求
    FULL_PIPELINE = "full_pipeline"       # 端到端全流程（从靶点到候选分子）


@dataclass
class ExtractedEntity:
    """提取的实体"""
    type: str                           # target | molecule | project_id | smiles | property | threshold | action
    value: str
    confidence: float = 1.0
    position: Tuple[int, int] = (0, 0)   # 在消息中的位置


@dataclass
class ParsedIntent:
    """解析后的意图"""
    primary_type: IntentType
    sub_types: List[IntentType] = field(default_factory=list)
    entities: List[ExtractedEntity] = field(default_factory=list)
    original_message: str = ""
    confidence: float = 0.0
    needs_clarification: bool = False
    clarification_question: str = ""
    detected_actions: List[str] = field(default_factory=list)  # 检测到的工具调用
    conditions: List[Dict[str, Any]] = field(default_factory=list)  # 条件
    dependencies: List[str] = field(default_factory=list)  # 依赖的上下文信息
    estimated_complexity: int = 1  # 1-5，预估复杂度
    suggested_tools: List[str] = field(default_factory=list)
    raw_llm_response: str = ""


class IntentParser:
    """
    用户意图解析器

    支持多阶段解析：
    1. 快速关键词检测（成本低，覆盖常见情况）
    2. 正则模式匹配（提取结构化实体）
    3. LLM 深度解析（处理复杂、模糊、多意图输入）
    """

    def __init__(self, api_key: Optional[str] = None, model: str = DEFAULT_MODEL, llm_client=None):
        self.model = model or DEFAULT_MODEL
        
        # 注入统一的 LLMClient
        if llm_client is not None:
            self.llm = llm_client
        else:
            from .llm_client import get_default_client
            self.llm = get_default_client(api_key=api_key, model=model)
        
        self._last_llm_call = 0.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def parse(self, message: str, context: Dict[str, Any] = None) -> ParsedIntent:
        """
        主解析入口。解析用户消息，返回结构化意图。
        """
        context = context or {}

        # Stage 1: 快速检测（低成本，覆盖80%情况）
        quick_result = self._quick_detect(message, context)
        if quick_result and quick_result.confidence >= 0.8:
            # 快速检测命中，但仍需判断是否需要澄清（考虑上下文）
            quick_result.original_message = message
            needs_clarify, question = self.needs_clarification(quick_result, context)
            quick_result.needs_clarification = needs_clarify
            quick_result.clarification_question = question
            return quick_result

        # Stage 2: 实体提取
        entities = self._extract_entities(message, context)
        
        # Stage 2.5: 如果提取到 SMILES 且要求分析性质 → 直接识别为单分子分析（跳过 LLM）
        smiles_entities = [e for e in entities if e.type == "smiles"]
        if smiles_entities:
            admet_keywords = [
                "admet", "性质", "属性", "分析", "评估", "预测", "预测一下",
                "admet分析", "admet评估", "admet预测", "admet性质",
                "药代", "毒性", "吸收", "分布", "代谢", "排泄",
            ]
            msg_lower = message.lower()
            if any(kw in msg_lower for kw in admet_keywords):
                return ParsedIntent(
                    primary_type=IntentType.SINGLE_ACTION,
                    confidence=0.92,
                    original_message=message,
                    entities=entities,
                    detected_actions=["analyze_single_molecule_admet"],
                    suggested_tools=["analyze_single_molecule_admet"],
                    estimated_complexity=1,
                )

        # Stage 3: LLM 深度解析（复杂情况）
        llm_result = self._llm_deep_parse(message, context, entities)

        # Stage 4: 合并结果
        final_intent = self._merge_results(quick_result, llm_result, entities)
        final_intent.original_message = message

        # 5. 根据上下文修正澄清需求
        needs_clarify, question = self.needs_clarification(final_intent, context)
        final_intent.needs_clarification = needs_clarify
        final_intent.clarification_question = question

        return final_intent

    def needs_clarification(self, intent: ParsedIntent, context: Dict[str, Any] = None) -> Tuple[bool, str]:
        """
        判断是否需要澄清，返回 (是否需要, 澄清问题)。
        关键改进：如果上下文有项目ID，降低澄清强度。
        """
        context = context or {}
        project_id = context.get("project_id")
        
        if intent.needs_clarification:
            missing = self._detect_missing_params(intent, context)
            if missing:
                question = self._build_clarification_question(missing, intent)
                return True, question
            # 如果意图解析器说需要澄清，但上下文足够，不需要澄清
            return False, ""

        # 自动判断：低置信度 + 模糊实体
        if intent.confidence < 0.6:
            missing = self._detect_missing_params(intent, context)
            if missing:
                question = self._build_clarification_question(missing, intent)
                return True, question

        return False, ""

    def _detect_missing_params(self, intent: ParsedIntent, context: Dict[str, Any] = None) -> List[str]:
        """检测缺少的必要参数（考虑上下文）。"""
        context = context or {}
        project_id = context.get("project_id")
        missing = []
        
        for action in intent.detected_actions:
            if action in ["create_project"] and not any(e.type == "target" for e in intent.entities):
                missing.append("靶点名称")
            if action in ["run_pipeline", "get_project_status", "analyze_failures"]:
                # 如果上下文有项目ID，不认为缺少
                if not project_id and not any(e.type == "project_id" for e in intent.entities):
                    missing.append("项目ID")
            if action in ["analyze_selectivity", "assess_synthesis_route"] and not any(e.type == "smiles" for e in intent.entities):
                missing.append("分子结构（SMILES）")
        return missing

    def split_multi_intent(self, intent: ParsedIntent) -> List[ParsedIntent]:
        """
        将多意图拆分为独立的子意图列表。
        每个子意图包含明确的单一目标。
        """
        if intent.primary_type != IntentType.MULTI_INTENT:
            return [intent]

        sub_intents = []
        # 基于检测到的 actions 拆分
        for i, action in enumerate(intent.detected_actions):
            sub = ParsedIntent(
                primary_type=IntentType.SINGLE_ACTION,
                original_message=intent.original_message,
                confidence=intent.confidence,
                detected_actions=[action],
                suggested_tools=[action],
            )
            # 提取该子意图相关的实体
            sub.entities = self._filter_entities_for_action(intent.entities, action)
            sub.estimated_complexity = 2
            sub_intents.append(sub)

        return sub_intents if sub_intents else [intent]

    def build_planning_context(self, intent: ParsedIntent) -> Dict[str, Any]:
        """
        将解析后的意图转换为 Planner 可用的上下文信息。
        """
        return {
            "intent_type": intent.primary_type.value,
            "sub_types": [st.value for st in intent.sub_types],
            "entities": [
                {"type": e.type, "value": e.value, "confidence": e.confidence}
                for e in intent.entities
            ],
            "detected_actions": intent.detected_actions,
            "conditions": intent.conditions,
            "dependencies": intent.dependencies,
            "estimated_complexity": intent.estimated_complexity,
            "suggested_tools": intent.suggested_tools,
            "needs_clarification": intent.needs_clarification,
            "clarification_question": intent.clarification_question,
        }

    # ------------------------------------------------------------------
    # Stage 1: Quick Detection
    # ------------------------------------------------------------------

    def _quick_detect(self, message: str, context: Dict[str, Any]) -> Optional[ParsedIntent]:
        """
        快速检测：基于关键词和模式匹配，低成本识别常见意图。
        增强上下文感知：如果上下文有 project_id，识别 follow_up 意图。
        """
        msg_lower = message.lower().strip()
        project_id = context.get("project_id")
        
        # P-1: 明确分析失败分子/失败原因 → 复杂分析（不是简单的 follow_up）
        failure_analysis_patterns = [
            "失败分子", "失败原因", "分析失败", "为什么失败", "失败分析",
            "哪些分子失败了", "失败的分子", "为什么会失败",
        ]
        for p in failure_analysis_patterns:
            if p in msg_lower:
                return ParsedIntent(
                    primary_type=IntentType.COMPLEX_ANALYSIS,
                    confidence=0.9,
                    original_message=message,
                    entities=[ExtractedEntity(type="project_id", value=str(project_id), confidence=0.9)] if project_id else [],
                    detected_actions=["analyze_failures", "get_project_status"],
                    suggested_tools=["analyze_failures", "get_project_status"],
                    estimated_complexity=3,
                )
        
        # P0: 上下文依赖检测（如果上下文有项目ID，用户说"再优化"、"分析结果"等）
        if project_id:
            follow_up_patterns = [
                "再优化", "继续优化", "再分析一下", "看看结果", "分析结果", "查看结果",
                "继续", "下一步", "然后呢", "结果呢", "优化一下", "再生成", "重新运行",
                "帮我分析", "检查一下", "评估一下", "看看", "对比", "比较",
                "为什么", "怎么回事", "出了什么问题",
            ]
            for p in follow_up_patterns:
                if p in msg_lower:
                    return ParsedIntent(
                        primary_type=IntentType.FOLLOW_UP,
                        confidence=0.85,
                        original_message=message,
                        entities=[ExtractedEntity(type="project_id", value=str(project_id), confidence=0.9)],
                        detected_actions=["get_project_status", "analyze_failures", "suggest_next_step"],
                        suggested_tools=["get_project_status", "analyze_failures", "suggest_next_step"],
                        estimated_complexity=2,
                    )
            
            # P0.3: 格式化追问（用户要详细数据/报告）
            format_patterns = [
                "详细数据", "详细结果", "具体数据", "给我看看", "详细点", "展开说说",
                "数据给我", "报告", "详细报告", "结果怎么样", "分子数据", "候选分子",
            ]
            for p in format_patterns:
                if p in msg_lower:
                    return ParsedIntent(
                        primary_type=IntentType.FOLLOW_UP,
                        confidence=0.9,
                        original_message=message,
                        entities=[ExtractedEntity(type="project_id", value=str(project_id), confidence=0.9)],
                        detected_actions=["format_top_molecules"],
                        suggested_tools=["format_top_molecules"],
                        estimated_complexity=2,
                    )
        
        # P0.5: 无上下文的分析失败/失败原因
        if not project_id:
            for p in failure_analysis_patterns:
                if p in msg_lower:
                    return ParsedIntent(
                        primary_type=IntentType.COMPLEX_ANALYSIS,
                        confidence=0.85,
                        original_message=message,
                        entities=[],
                        detected_actions=["analyze_failures", "list_projects"],
                        suggested_tools=["analyze_failures", "list_projects"],
                        needs_clarification=True,
                        clarification_question="请提供项目 ID，以便分析失败分子。",
                        estimated_complexity=3,
                    )
        
        # P1: 明显是聊天（极高置信度）
        chat_patterns = [
            "你好", "hello", "hi", "嗨", "谢谢", "再见", "bye", "在吗",
            "你是谁", "你能做什么", "介绍一下", "帮助",
        ]
        for p in chat_patterns:
            if p in msg_lower:
                return ParsedIntent(
                    primary_type=IntentType.SIMPLE_CHAT,
                    confidence=0.95,
                    original_message=message,
                )
        
        # P2: 明显是单一靶点操作（极高置信度）
        try:
            from ..target_database import search_targets
            targets = search_targets(message)
            if targets and len(targets) == 1:
                action_words = ["分析", "对比", "查看", "检查", "优化", "评估", "生成", "创建"]
                has_complex = any(w in msg_lower for w in action_words)
                if not has_complex or len(message) < 20:
                    return ParsedIntent(
                        primary_type=IntentType.SINGLE_ACTION,
                        confidence=0.9,
                        original_message=message,
                        entities=[ExtractedEntity(type="target", value=targets[0], confidence=0.9)],
                        detected_actions=["create_project"],
                        suggested_tools=["create_project", "run_pipeline", "wait_for_pipeline", "get_top_molecules"],
                        estimated_complexity=2,
                    )
        except Exception:
            pass
        
        # P2.5: 端到端全流程请求（跑一遍XXX的全流程）
        full_pipeline_patterns = [
            "跑一遍", "跑通", "全流程", "端到端", "一键", "从头到尾",
            "完整流程", "一键生成", "帮我跑", "跑个", "自动生成",
        ]
        for p in full_pipeline_patterns:
            if p in msg_lower:
                # 尝试提取靶点
                try:
                    from ..target_database import search_targets
                    targets = search_targets(message)
                    if targets:
                        target_name = targets[0]['name'] if isinstance(targets[0], dict) else targets[0]
                        return ParsedIntent(
                            primary_type=IntentType.FULL_PIPELINE,
                            confidence=0.9,
                            original_message=message,
                            entities=[ExtractedEntity(type="target", value=target_name, confidence=0.9)],
                            detected_actions=["run_full_pipeline"],
                            suggested_tools=["run_full_pipeline"],
                            estimated_complexity=4,
                        )
                except Exception:
                    pass
                # 即使没有明确靶点，也标记为全流程意图（后续可能缺少靶点需要澄清）
                return ParsedIntent(
                    primary_type=IntentType.FULL_PIPELINE,
                    confidence=0.7,
                    original_message=message,
                    detected_actions=["run_full_pipeline"],
                    suggested_tools=["run_full_pipeline"],
                    estimated_complexity=4,
                )
        
        # P3: 明显的多意图信号
        multi_signals = ["然后", "接着", "之后", "再", "先", "最后", "同时", "顺便", "也", "还要", "以及", "和"]
        if sum(1 for s in multi_signals if s in msg_lower) >= 2:
            return ParsedIntent(
                primary_type=IntentType.MULTI_INTENT,
                confidence=0.5,
                original_message=message,
            )
        
        # P4: 明显的条件性请求
        condition_patterns = ["如果", "假如", "要是", "若", "当", "除非", "否则", "就", "再"]
        if any(p in msg_lower for p in condition_patterns):
            return ParsedIntent(
                primary_type=IntentType.CONDITIONAL,
                confidence=0.6,
                original_message=message,
            )
        
        # P5: 上下文依赖（提到"之前"、"上次"、"上面"）
        if any(w in msg_lower for w in ["之前", "上次", "之前的结果", "上面", "刚才"]):
            return ParsedIntent(
                primary_type=IntentType.FOLLOW_UP,
                confidence=0.7,
                original_message=message,
            )
        
        return None

    # ------------------------------------------------------------------
    # Stage 2: Entity Extraction
    # ------------------------------------------------------------------

    def _extract_entities(self, message: str, context: Dict[str, Any]) -> List[ExtractedEntity]:
        """
        从消息中提取结构化实体。
        """
        entities = []
        msg_lower = message.lower()

        # 1. 靶点提取
        try:
            from ..target_database import search_targets
            targets = search_targets(message)
            for t in targets:
                target_name = t['name'] if isinstance(t, dict) else t
                entities.append(ExtractedEntity(type="target", value=target_name, confidence=0.85))
        except Exception:
            pass

        # 2. 项目ID提取（数字）——要求前面有项目/ID/编号关键字，或数字为独立标记（至少2位）
        project_id_patterns = [
            r'(?:项目|project)[\s:]*(?:id|ID|编号)?[\s:]*(\d+)',
            r'(?:id|ID|编号)[\s:]*(\d+)',
            r'\b(\d{2,})\b',  # 独立数字（至少2位）
        ]
        seen_pids = set()
        for pattern in project_id_patterns:
            for pid in re.findall(pattern, msg_lower):
                if pid not in seen_pids:
                    seen_pids.add(pid)
                    entities.append(ExtractedEntity(type="project_id", value=pid, confidence=0.8))

        # 3. SMILES 提取（改进版：支持显式和隐式 SMILES）
        # 方案 A：显式 SMILES 标记（如 "SMILES: CC(C)Oc1ccc(...)")
        explicit_pattern = r'SMILES[:\s]*([A-Za-z0-9\[\]\(\)\=@#\+\-\\\.\/\%]+)'
        for m in re.finditer(explicit_pattern, message, re.IGNORECASE):
            smiles = m.group(1).strip()
            if len(smiles) > 5 and self._is_valid_smiles_looking(smiles):
                entities.append(ExtractedEntity(type="smiles", value=smiles, confidence=0.9))
        
        # 方案 B：隐式 SMILES（通过特征匹配）
        # 常见模式：以 C, N, O 等开头，包含环数字、括号、@ 等
        # 例如：CC(C)Oc1ccc(cc1) 或 CN1C=NC2=C1C(=O)N(C(=O)N2C)
        implicit_pattern = r'\b([A-Z][a-z]?[0-9]*(?:[\(\)\[\]]|[=@#\+\-]|\.[A-Z][a-z]?[0-9]*)+(?:[0-9]+)?[A-Za-z0-9\(\)\[\]\=@#\+\-\\\.\/\%]*)\b'
        for m in re.finditer(implicit_pattern, message):
            smiles = m.group(1).strip()
            if len(smiles) > 5 and self._is_valid_smiles_looking(smiles):
                # 避免与已有显式 SMILES 重复
                if not any(e.type == "smiles" and e.value == smiles for e in entities):
                    entities.append(ExtractedEntity(type="smiles", value=smiles, confidence=0.6))

        # 4. 分子属性/阈值
        property_patterns = {
            "mw": r'(分子量|MW|分子量|molecular weight)[:\s]*([\d\.]+)',
            "logp": r'(LogP|脂溶性|logp)[:\s]*([\-\d\.]+)',
            "ic50": r'(IC50|ic50|抑制活性)[:\s]*([\d\.]+)',
            "kd": r'(Kd|KD|结合亲和力)[:\s]*([\d\.]+)',
        }
        for prop_type, pattern in property_patterns.items():
            matches = re.finditer(pattern, message, re.IGNORECASE)
            for m in matches:
                entities.append(ExtractedEntity(
                    type="property", 
                    value=f"{prop_type}:{m.group(2)}", 
                    confidence=0.75
                ))

        # 5. 动作/操作词
        action_keywords = {
            "create_project": ["创建项目", "新建项目", "新项目"],
            "run_pipeline": ["运行pipeline", "执行pipeline", "运行流程", "生成分子"],
            "analyze": ["分析", "评估", "看看", "检查", "诊断"],
            "compare": ["对比", "比较", "vs", "versus", "哪个更好"],
            "optimize": ["优化", "改进", "调整", "提升"],
            "get_status": ["状态", "进展", "进度", "结果"],
        }
        for action, keywords in action_keywords.items():
            for kw in keywords:
                if kw in msg_lower:
                    entities.append(ExtractedEntity(type="action", value=action, confidence=0.8))
                    break

        # 6. 对比对象（用于 comparison 意图）
        if any(w in msg_lower for w in ["对比", "比较", "vs", "versus", "哪个", "更好"]):
            entities.append(ExtractedEntity(type="comparison_signal", value="comparison", confidence=0.8))

        # 7. 优化/迭代信号
        if any(w in msg_lower for w in ["优化", "改进", "调整", "更好", "提升", "迭代"]):
            entities.append(ExtractedEntity(type="optimization_signal", value="optimization", confidence=0.8))

        return entities

    # ------------------------------------------------------------------
    # Stage 3: LLM Deep Parse
    # ------------------------------------------------------------------

    def _llm_deep_parse(self, message: str, context: Dict[str, Any], entities: List[ExtractedEntity]) -> ParsedIntent:
        """
        使用 LLM 进行深度意图解析，处理复杂、模糊、多意图输入。
        """
        entities_json = json.dumps(
            [{"type": e.type, "value": e.value} for e in entities],
            ensure_ascii=False, indent=2
        ) if entities else "[]"

        context_summary = json.dumps(context, ensure_ascii=False, indent=2) if context else "{}"

        prompt = f"""你是药物设计 AI 的意图解析专家。请分析用户消息，提取结构化意图信息。

## 用户消息
"{message}"

## 已提取的实体
{entities_json}

## 当前对话上下文
{context_summary}

## 输出格式
请返回严格的 JSON（不要 Markdown 代码块）：
{{
  "intent_type": "simple_chat|single_action|multi_intent|complex_analysis|conditional|clarification_needed|comparison|optimization|follow_up|exploration|full_pipeline",
  "confidence": 0.0-1.0,
  "needs_clarification": true/false,
  "clarification_question": "如果需要澄清，提出具体问题",
  "detected_actions": ["检测到的动作列表，如 create_project, analyze_molecular_diversity 等"],
  "suggested_tools": ["建议使用的工具"],
  "conditions": [{{"condition": "条件描述", "if_true": "如果满足做什么", "if_false": "如果不满足做什么"}}],
  "dependencies": ["依赖的上下文信息，如 '需要知道项目ID'"],
  "estimated_complexity": 1-5,
  "entities_needed": ["还缺少的必要实体"],
  "reasoning": "简要的推理过程"
}}

## 意图类型定义
- simple_chat: 打招呼、闲聊、知识问答
- single_action: 单一明确操作（如"创建EGFR项目"）
- multi_intent: 包含多个独立目标（如"分析A项目然后优化B项目"）
- complex_analysis: 需要多步分析（如"分析为什么ADMET差"）
- conditional: 包含条件逻辑（如"如果ADMET不好就优化"）
- clarification_needed: 信息不足，需要澄清
- comparison: 对比两个或多个对象
- optimization: 基于现有结果优化/迭代
- follow_up: 基于之前对话的上下文请求
- exploration: 探索性请求（如"有什么好靶点"）
- full_pipeline: 端到端全流程请求（如"跑一遍HER2的全流程"、"一键生成EGFR候选分子"）

## 规则
1. 必须返回合法的 JSON
2. 不要添加注释
3. 如果检测到多意图，confidence 应该较低（0.5-0.7）
4. 如果缺少关键信息，needs_clarification 为 true
"""

        raw_response = self.llm.cached_call(
            [{"role": "user", "content": prompt}],
            temperature=0.2,
            cache_ttl=60,
        )

        if not raw_response:
            return self._create_fallback_intent(message)

        try:
            # 清理可能的 Markdown 代码块
            text = raw_response.strip()
            if text.startswith("```"):
                text = text[text.find("{"):text.rfind("}")+1]
            parsed = json.loads(text)
        except json.JSONDecodeError:
            # 尝试提取 JSON
            match = re.search(r'\{[\s\S]*\}', raw_response)
            if match:
                try:
                    parsed = json.loads(match.group(0))
                except json.JSONDecodeError:
                    return self._create_fallback_intent(message)
            else:
                return self._create_fallback_intent(message)

        # 构建 ParsedIntent
        intent_type_str = parsed.get("intent_type", "single_action")
        try:
            intent_type = IntentType(intent_type_str)
        except ValueError:
            intent_type = IntentType.SINGLE_ACTION

        intent = ParsedIntent(
            primary_type=intent_type,
            confidence=parsed.get("confidence", 0.5),
            needs_clarification=parsed.get("needs_clarification", False),
            clarification_question=parsed.get("clarification_question", ""),
            detected_actions=parsed.get("detected_actions", []),
            suggested_tools=parsed.get("suggested_tools", []),
            conditions=parsed.get("conditions", []),
            dependencies=parsed.get("dependencies", []),
            estimated_complexity=parsed.get("estimated_complexity", 2),
            raw_llm_response=raw_response,
        )

        # 合并实体
        intent.entities = entities

        # 额外检测子类型
        if intent_type == IntentType.MULTI_INTENT:
            intent.sub_types = [IntentType.SINGLE_ACTION] * len(intent.detected_actions)
        elif intent_type == IntentType.CONDITIONAL:
            intent.sub_types = [IntentType.CONDITIONAL]

        return intent

    # ------------------------------------------------------------------
    # Merge & Helper
    # ------------------------------------------------------------------

    def _merge_results(self, quick: Optional[ParsedIntent], llm: ParsedIntent, entities: List[ExtractedEntity]) -> ParsedIntent:
        """合并快速检测和 LLM 解析的结果。保留快速检测中的关键实体，同时合并提取的实体。"""
        if quick and quick.confidence >= 0.8:
            # 高置信度快速检测优先
            result = quick
            # 合并实体：保留 quick 的实体，同时添加提取到的新实体
            existing = {(e.type, e.value) for e in result.entities}
            for e in entities:
                if (e.type, e.value) not in existing:
                    result.entities.append(e)
            result.detected_actions = llm.detected_actions if llm.detected_actions else quick.detected_actions
            result.suggested_tools = llm.suggested_tools if llm.suggested_tools else quick.suggested_tools
        else:
            result = llm
            if quick and quick.entities:
                # 合并实体
                existing = {(e.type, e.value) for e in result.entities}
                for e in quick.entities:
                    if (e.type, e.value) not in existing:
                        result.entities.append(e)

        return result

    def _detect_missing_params(self, intent: ParsedIntent, context: Dict[str, Any] = None) -> List[str]:
        """检测缺少的必要参数。"""
        missing = []
        for action in intent.detected_actions:
            if action in ["create_project", "run_full_pipeline"] and not any(e.type == "target" for e in intent.entities):
                missing.append("靶点名称")
            if action in ["run_pipeline", "get_project_status", "analyze_failures", "format_top_molecules"] and not any(e.type == "project_id" for e in intent.entities):
                missing.append("项目ID")
            if action in ["analyze_selectivity", "assess_synthesis_route"] and not any(e.type == "smiles" for e in intent.entities):
                missing.append("分子结构（SMILES）")
        return missing

    def _build_clarification_question(self, missing: List[str], intent: ParsedIntent) -> str:
        """构建澄清问题。"""
        if "靶点名称" in missing:
            return "你希望基于哪个靶点进行操作？（如 EGFR、BRAF、AKT1 等）"
        if "项目ID" in missing:
            return "请提供项目 ID，或告诉我你想操作哪个项目。"
        if "分子结构（SMILES）" in missing:
            return "请提供分子的 SMILES 结构式。"
        return f"我需要更多信息才能完成：{', '.join(missing)}。"

    def _filter_entities_for_action(self, entities: List[ExtractedEntity], action: str) -> List[ExtractedEntity]:
        """为特定动作过滤相关实体。"""
        relevant = []
        action_entity_map = {
            "create_project": ["target"],
            "run_full_pipeline": ["target"],
            "format_top_molecules": ["project_id"],
            "run_pipeline": ["project_id"],
            "get_project_status": ["project_id"],
            "analyze_molecular_diversity": ["smiles", "project_id"],
            "check_patent_novelty": ["smiles"],
            "analyze_selectivity": ["smiles", "target"],
            "assess_synthesis_route": ["smiles"],
            "compare_molecules": ["smiles", "project_id"],
        }
        relevant_types = action_entity_map.get(action, [])
        for e in entities:
            if e.type in relevant_types or e.type in ["action", "comparison_signal", "optimization_signal"]:
                relevant.append(e)
        return relevant

    def _create_fallback_intent(self, message: str) -> ParsedIntent:
        """创建 fallback 意图。"""
        return ParsedIntent(
            primary_type=IntentType.SINGLE_ACTION,
            confidence=0.3,
            original_message=message,
            needs_clarification=True,
            clarification_question="我没有完全理解你的请求，请更具体地描述你的需求。",
            detected_actions=["suggest_next_step"],
            suggested_tools=["suggest_next_step"],
        )

    # ------------------------------------------------------------------
    # LLM wrapper
    # ------------------------------------------------------------------

    def _is_valid_smiles_looking(self, text: str) -> bool:
        """验证字符串是否看起来像有效的 SMILES（启发式检查）。"""
        # 必须包含至少一个常见原子符号
        common_atoms = set("CNOPSFClBrIBSi")
        has_atoms = any(c in text for c in common_atoms)
        
        # 必须包含一些 SMILES 特征字符（括号、等号、环数字、@ 等）
        smiles_features = set("()[]=@#123456789")
        has_features = any(c in text for c in smiles_features)
        
        # 不能包含明显的非 SMILES 字符（如空格、中文标点等）
        invalid_chars = set(" \u3000\uff0c\u3002\uff01\uff1f\uff1b")
        no_invalid = not any(c in text for c in invalid_chars)
        
        # 长度适中（太短不可能是 SMILES）
        length_ok = 5 < len(text) < 500
        
        return has_atoms and has_features and no_invalid and length_ok

    def _call_llm(self, messages: List[Dict[str, str]], temperature: float = 0.7) -> str:
        """调用 LLM（委托给 LLMClient，带重试）。"""
        return self.llm.retry_call(messages, temperature=temperature, max_retries=2, base_delay=0.5)
