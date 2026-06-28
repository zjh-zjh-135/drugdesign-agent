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
        llm_client=None,
    ):
        self.temperature = temperature
        self.max_steps = max_steps
        
        # 注入统一的 LLMClient
        if llm_client is not None:
            self.llm = llm_client
        else:
            from .llm_client import get_default_client
            self.llm = get_default_client(api_key=api_key, model=model)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def plan(
        self,
        goal: str,
        project_id: Optional[int] = None,
        env_state: Optional[Dict[str, Any]] = None,
        available_tools: Optional[List[Dict]] = None,
        intent_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Generate an execution plan for the given user goal.

        Args:
            intent_context: Optional parsed intent from IntentParser, containing
                          intent_type, entities, conditions, dependencies, etc.
        """
        env_state = env_state or {}
        available_tools = available_tools or []
        intent_context = intent_context or {}

        # Phase 4: 使用 Prompt 模板加载系统提示词和用户提示词
        try:
            from .prompts import load_planner_prompts
            tools_desc = self._build_tools_description(available_tools)
            system_prompt, user_template = load_planner_prompts(
                tools_desc=tools_desc,
                intent_context=intent_context,
                max_steps=self.max_steps,
            )
            # 用户提示词需要额外格式化
            env_text = json.dumps(env_state, ensure_ascii=False, indent=2)
            intent_text = self._build_intent_text(intent_context)
            user_prompt = user_template.format(
                goal=goal,
                project_id=project_id if project_id else "未指定",
                env_text=env_text,
                intent_text=intent_text,
            )
        except Exception as e:
            # 如果模板加载失败，回退到原有硬编码提示词
            logger.warning(f"Prompt template loading failed: {e}, falling back to built-in prompts")
            system_prompt = self._build_system_prompt(available_tools, intent_context)
            user_prompt = self._build_user_prompt(goal, project_id, env_state, intent_context)

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

        # 如果意图解析建议了条件步骤，但 LLM 没有生成，添加条件包装
        if intent_context.get("conditions") and not any("condition" in s for s in steps):
            steps = self._inject_conditions(steps, intent_context.get("conditions", []))

        return {
            "success": True,
            "goal": goal,
            "project_id": project_id,
            "steps": steps,
            "summary": parsed.get("summary", "未提供摘要"),
            "raw_response": raw_response,
            "intent_context": intent_context,
        }

    # ------------------------------------------------------------------
    # Prompt builders (Phase 4: 新增辅助方法，原有方法保留作为 fallback)
    # ------------------------------------------------------------------

    def _build_tools_description(self, tools: List[Dict]) -> str:
        """构建工具描述文本（供 Prompt 模板使用）。"""
        tools_desc = []
        for t in tools:
            params = json.dumps(t.get("parameters", {}), ensure_ascii=False, indent=2)
            tools_desc.append(
                f"- {t.get('name', 'unknown')}: {t.get('description', '')}\n  参数: {params}"
            )
        return "\n".join(tools_desc) if tools_desc else "（当前无可用工具）"

    def _build_intent_text(self, intent_context: Dict[str, Any]) -> str:
        """构建意图解析文本（供 Prompt 模板使用）。"""
        if not intent_context:
            return ""
        detected_actions = intent_context.get('detected_actions', [])
        return f"""
## 意图解析结果（已自动识别）
- 意图类型：{intent_context.get('intent_type', 'unknown')}
- 检测到的实体：{json.dumps(intent_context.get('entities', []), ensure_ascii=False, indent=2)}
- 检测到的动作：{', '.join(detected_actions)}
- 建议工具：{', '.join(intent_context.get('suggested_tools', []))}
- 检测到的条件：{json.dumps(intent_context.get('conditions', []), ensure_ascii=False, indent=2)}
- 缺少的信息：{', '.join(intent_context.get('entities_needed', []))}
- 依赖的上下文：{', '.join(intent_context.get('dependencies', []))}

## 意图解析器建议
如果"检测到的动作"中包含明确的分析工具（如 analyze_failures、analyze_admet_sar），请直接调用该工具，不要先获取状态再建议。
"""

    def _build_system_prompt(self, tools: List[Dict], intent_context: Dict[str, Any] = None) -> str:
        """Build the system prompt that instructs the LLM to output JSON plans."""
        tools_desc = []
        for t in tools:
            params = json.dumps(t.get("parameters", {}), ensure_ascii=False, indent=2)
            tools_desc.append(
                f"- {t.get('name', 'unknown')}: {t.get('description', '')}\n  参数: {params}"
            )
        tools_text = "\n".join(tools_desc) if tools_desc else "（当前无可用工具）"

        # 根据意图上下文定制规划策略
        intent_type = intent_context.get("intent_type", "single_action") if intent_context else "single_action"
        complexity = intent_context.get("estimated_complexity", 2) if intent_context else 2
        conditions = intent_context.get("conditions", []) if intent_context else []
        conditions_text = json.dumps(conditions, ensure_ascii=False, indent=2) if conditions else "无"

        return f"""你是 DrugDesign Copilot Agent 的任务规划器。你的职责是将用户的目标拆解为可执行的步骤。

## 用户意图类型
当前意图类型：{intent_type}
预估复杂度：{complexity}/5
用户条件要求：{conditions_text}

## 可用工具（可以组合使用）
{tools_text}

## 输出格式
你必须返回一个严格的 JSON 对象，格式如下（不要包含 Markdown 代码块标记，只输出纯 JSON）：

{{
  "steps": [
    {{
      "tool": "工具名称",
      "params": {{"参数名": "参数值"}},
      "reason": "为什么需要这一步",
      "expected_outcome": "预期这一步会得到什么结果",
      "condition": "可选：执行条件（如'如果ADMET分数<3'）"
    }}
  ],
  "summary": "用一句话概括整个计划"
}}

## 规划策略（根据意图类型动态调整）

### 1. 单一操作（single_action）
- 直接调用对应工具，无需多余步骤
- 如果缺少参数，用 suggest_next_step 收集信息
- **单分子 ADMET 分析**：如果用户提供了 SMILES 并要求分析性质/ADMET，直接使用 `analyze_single_molecule_admet`，不需要创建项目或运行 Pipeline。这是最直接的分析方式。

### 2. 多意图组合（multi_intent）
- 将多个目标拆分为独立的步骤序列
- 使用变量传递结果（如"步骤1的project_id传递给步骤2"）
- 注意：不同意图可能需要不同的项目

### 3. 复杂分析（complex_analysis）
- 先获取数据 → 再分析 → 最后给出建议
- 例如：获取分子列表 → analyze_admet_sar → 生成报告
- **失败分析场景**：如果用户要求"分析失败分子原因"，直接使用 `analyze_failures` 获取失败分子的分类和原因，不需要先获取项目状态。如果还需要更详细的建议，可以追加 `suggest_next_step`。

### 4. 条件性请求（conditional）
- 必须包含条件判断步骤
- 使用 condition 字段标记条件步骤
- 例如：condition: "如果ADMET分数<3" 则执行 adjust_filters
- 如果条件不满足，提供替代方案

### 5. 对比请求（comparison）
- 先获取所有对比对象的数据
- 然后进行对比分析
- 最后给出对比结论和建议

### 6. 优化/迭代（optimization）
- 先获取当前状态（get_project_status）
- 分析问题（analyze_failures）
- 调整参数（adjust_filters）
- 重新执行（run_pipeline）
- 验证结果（get_top_molecules）
- 这个模式是：获取 → 分析 → 调整 → 重跑 → 验证

### 7. 上下文依赖（follow_up）
- 检查上下文是否包含所需信息
- 如果缺少，先获取上下文（get_project_status / list_projects）
- 然后基于上下文执行操作
- **例外**：如果用户明确提到"失败分子/失败原因/失败分析"，说明意图已经明确，直接调用 `analyze_failures`，不需要先获取状态

### 8. 探索性请求（exploration）
- 先用 list_projects 或 get_project_status 了解现状
- 然后 suggest_next_step 给出建议
- 避免直接执行不确定的操作

## 通用规划规则
1. **工具组合**：复杂目标需要多步组合工具。例如"优化项目"=获取状态→分析失败→建议调整→执行调整
2. **信息获取优先**：如果目标需要项目信息但当前没有，第一步用 "list_projects" 或 "get_project_status"
3. **分析优先**：如果用户要求分析，先用分析工具获取数据，再用建议工具给出结论
4. **执行验证**：重要操作（如 run_pipeline）后安排 "get_project_status" 验证结果
5. **靶点直通流程**：当用户想为特定靶点生成分子时（如只说"EGFR"或"BRAF"），计划应为：
   - 步骤1：create_project（target_name=靶点名称，name可不传，系统会自动生成）
     注意：create_project 会自动从靶点数据库添加该靶点的已知活性分子作为参考，无需额外步骤
   - 步骤2：run_pipeline（使用刚创建的项目ID）
   - 步骤3：wait_for_pipeline（等待 Pipeline 完成，这是必须的！Pipeline 是异步运行的，需要等待才能获取结果）
   - 步骤4：get_top_molecules（获取最佳候选分子）
   如果用户没有指定项目名，create_project 将自动生成 "靶点_YYYYMMDD" 格式的名称。
6. **Pipeline 异步等待策略**：run_pipeline 启动后，必须安排 wait_for_pipeline 等待其完成。不要跳过等待步骤直接获取结果。
7. **迭代优化流程**：如果用户要求优化或重新运行，计划应为：
   - get_project_status → analyze_failures → adjust_filters → run_pipeline → wait_for_pipeline → get_top_molecules
8. **ADMET结构分析**：如果用户问"为什么ADMET差""哪个基团导致问题"，使用 analyze_admet_sar 分析结构-活性关系。
9. **多样性分析**：如果用户问"分子结构是否多样""覆盖哪些骨架"，使用 analyze_molecular_diversity 对Top分子聚类。
10. **专利新颖性检查**：如果用户问"这些分子是否已有专利""是否新颖"，使用 check_patent_novelty 查询PubChem。
11. **选择性分析**：如果用户问"选择性怎么样""是否脱靶"，使用 analyze_selectivity 分析同家族靶点选择性。
12. **合成评估**：如果用户问"这个分子能合成吗""合成难度"，使用 assess_synthesis_route 评估合成路线。
13. **多步条件处理**：如果用户说"如果A就B，否则C"，生成两个条件步骤：
    - 步骤X（condition: "如果A"）→ tool: B
    - 步骤X+1（condition: "如果非A"）→ tool: C
    或者使用 suggest_next_step 来请用户确认。

## 技术规则
1. 步骤数量不超过 {self.max_steps} 步
2. 每一步必须对应一个可用的工具
3. 参数必须准确，project_id 必须正确传递
4. 如果目标不明确，先安排一个 "suggest_next_step" 或 "get_project_status" 来收集信息
5. 所有输出必须是合法的 JSON，不要添加注释
6. 禁止使用 markdown 代码块（```json），直接输出 JSON 字符串
"""

    def _build_user_prompt(
        self, goal: str, project_id: Optional[int], env_state: Dict[str, Any], intent_context: Dict[str, Any] = None
    ) -> str:
        """Build the user prompt that includes the goal and environment state."""
        env_text = json.dumps(env_state, ensure_ascii=False, indent=2)
        
        intent_text = ""
        if intent_context:
            detected_actions = intent_context.get('detected_actions', [])
            intent_text = f"""
## 意图解析结果（已自动识别）
- 意图类型：{intent_context.get('intent_type', 'unknown')}
- 检测到的实体：{json.dumps(intent_context.get('entities', []), ensure_ascii=False, indent=2)}
- 检测到的动作：{', '.join(detected_actions)}
- 建议工具：{', '.join(intent_context.get('suggested_tools', []))}
- 检测到的条件：{json.dumps(intent_context.get('conditions', []), ensure_ascii=False, indent=2)}
- 缺少的信息：{', '.join(intent_context.get('entities_needed', []))}
- 依赖的上下文：{', '.join(intent_context.get('dependencies', []))}

## 意图解析器建议
如果"检测到的动作"中包含明确的分析工具（如 analyze_failures、analyze_admet_sar），请直接调用该工具，不要先获取状态再建议。
"""
        
        return f"""用户目标：{goal}

项目ID：{project_id if project_id else '未指定'}

当前环境状态：
{env_text}
{intent_text}

请基于以上信息，生成一个执行计划（纯 JSON 格式）。如果意图解析结果中有条件要求，请在对应步骤的 condition 字段中标记。"""

    def _inject_conditions(self, steps: List[Dict], conditions: List[Dict]) -> List[Dict]:
        """将条件注入到步骤中，如果 LLM 没有处理。"""
        if not conditions:
            return steps
        
        # 简单策略：在最后添加条件步骤
        for i, cond in enumerate(conditions):
            steps.append({
                "step_number": len(steps) + i + 1,
                "tool": "suggest_next_step",
                "params": {"condition": cond.get("condition", "")},
                "reason": f"条件判断：{cond.get('condition', '')}",
                "expected_outcome": "根据条件执行后续操作",
                "condition": cond.get("condition", ""),
            })
        return steps

    # ------------------------------------------------------------------
    # LLM interaction
    # ------------------------------------------------------------------

    def _call_llm(self, messages: List[Dict[str, str]]) -> Optional[str]:
        """调用 LLM（委托给 LLMClient，带重试）。"""
        result = self.llm.retry_call(messages, temperature=self.temperature, max_retries=2, base_delay=0.5)
        # 如果返回错误消息，则视为调用失败
        if result.startswith("LLM 调用失败"):
            return None
        return result

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

        # 防御：确保解析结果是字典
        if not isinstance(plan, dict):
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
        # Stage 4: 不再默认调用 get_project_status + suggest_next_step
        # 改为返回诚实提示，让用户明确需求
        if project_id:
            steps.append({
                "step_number": 1,
                "tool": "get_project_status",
                "params": {"project_id": project_id},
                "reason": "获取项目基本信息以便给出针对性回复",
                "expected_outcome": "了解项目当前进展",
            })
        else:
            steps.append({
                "step_number": 1,
                "tool": "list_projects",
                "params": {},
                "reason": "列出已有项目供用户选择",
                "expected_outcome": "获取现有项目列表",
            })

        return {
            "success": False,
            "goal": goal,
            "project_id": project_id,
            "steps": steps,
            "summary": f"抱歉，我没有完全理解您的需求（{error}）。请告诉我：您想查看分子数据、分析失败原因，还是调整参数重新运行？",
            "raw_response": "",
        }
