# AI Agent 持续迭代优化手册

> 本文档记录 DrugDesign Copilot Agent 的测试方法、问题分析框架和迭代改进机制。
> 每次测试发现的问题，按此文档的流程记录、分析、修复、验证。

---

## 一、当前 Agent 架构总览

```
用户输入 → IntentParser(意图解析) → ReActEngine(决策执行) → ToolExecutor(工具执行) → 结果输出
              ↓                              ↓
         上下文记忆(project_id)          多意图并行/串行
         澄清/表单判断                  Perceive-Plan-Execute-Report
```

**核心模块**：`intent_parser.py` → `engine.py` → `planner.py` → `executor.py` → `tools.py`

---

## 二、测试反馈记录模板

每次测试发现问题，按以下模板记录：

```markdown
### 测试记录 #{序号}

**用户输入**: "分析失败分子原因"

**Agent 实际输出**:
```
Step 1: get_project_status({"project_id":35})
Step 2: suggest_next_step({"project_id":35})
```

**用户预期行为**:
- 调用 `analyze_failures` 或类似工具
- 分析 Pipeline 中标记为 `failed` 的分子的具体失败原因（如：ADMET 失败、合成不可行、结构不合格等）
- 给出针对性的失败原因分类和改进建议

**实际行为与预期的差距**:
1. 意图解析错误：将"分析失败分子原因"识别为"获取项目状态+建议"
2. 没有调用失败分析相关工具
3. 输出内容泛泛，没有聚焦"失败分子"

**根因分析**:
- [待分析] intent_parser 是否将"分析失败"映射到正确动作
- [待分析] 是否有 `analyze_failures` 工具注册
- [待分析] planner 的意图上下文是否传递正确

**修复方案**:
- [待确定]

**验证结果**:
- [待验证]
```

---

## 三、常见问题分类与诊断方法

### 3.1 意图解析问题（IntentParser）

**症状**：用户说 A，Agent 做 B

**诊断步骤**：
1. 检查 `_quick_detect` 是否匹配了错误的关键词
2. 检查 `parse_intent` 的 LLM 返回结果
3. 检查 `needs_clarification` 是否过度触发
4. 检查上下文记忆是否正确传递（`project_id` 是否在 `context` 中）

**常见修复**：
- 添加/修改关键词映射（`_quick_detect`）
- 调整 LLM 意图解析 Prompt，增加示例
- 修复 `needs_clarification` 对上下文的感知

### 3.2 规划问题（Planner）

**症状**：意图对了，但执行步骤不对

**诊断步骤**：
1. 检查 `TaskPlanner.plan()` 的输入（goal、project_id、env_state、intent_context）
2. 检查 LLM 规划返回的步骤是否包含正确的工具调用
3. 检查 `intent_context` 是否被正确传递给 planner

**常见修复**：
- 在 Planner Prompt 中增加更多工具使用示例
- 修复 `intent_context` 传递链（intent_parser → engine → planner）
- 增加工具参数校验，让 planner 知道需要什么参数

### 3.3 执行问题（Executor）

**症状**：规划正确，但执行失败或结果不对

**诊断步骤**：
1. 检查工具参数是否正确提取（从 message 或 context 中）
2. 检查工具执行是否成功（返回 `ok` 还是错误）
3. 检查 LLM 决策步骤（`_call_llm`）是否正确判断继续/终止

**常见修复**：
- 修复参数提取逻辑（正则、实体解析）
- 修复工具实现（如 `pipeline.py` 的 `pipeline_run` 初始化）
- 增加执行步骤的日志，便于调试

### 3.4 输出问题（Final Answer）

**症状**：执行了，但输出不符合用户期望

**诊断步骤**：
1. 检查 `_generate_final_answer` 或 `report_generator` 的输入
2. 检查 LLM 生成最终答案的 Prompt 是否包含足够的上下文
3. 检查输出格式是否符合用户预期（结构化/自然语言/表格）

**常见修复**：
- 增强最终答案生成的 Prompt，包含执行结果摘要
- 增加输出模板（如：失败分析 → 分类+原因+建议）
- 支持多种输出格式（Markdown 表格、结构化 JSON）

---

## 四、Agent 能力评估维度

每次测试，从以下维度评估：

| 维度 | 权重 | 评估标准 |
|------|------|----------|
| **意图理解** | 30% | 用户输入 → 正确意图类型的匹配率 |
| **上下文记忆** | 20% | 连续对话中 project_id/target 的保持率 |
| **工具选择** | 20% | 意图 → 正确工具调用的准确率 |
| **参数提取** | 15% | 从消息中提取正确参数的准确率 |
| **输出质量** | 15% | 最终答案是否符合用户预期（聚焦、有用、准确） |

**评分标准**：
- A（优秀）：完全正确，无需修改
- B（良好）：基本正确，有小瑕疵
- C（及格）：方向对了，但内容不够
- D（不及格）：方向错了，需要修复
- F（失败）：完全错误，无法使用

---

## 五、迭代改进流程

```
用户测试 → 发现问题 → 按模板记录 → 根因分析 → 定位模块 → 修改代码 → 验证修复 → 记录经验
     ↑                                                                              ↓
     └──────────────────────── 持续循环 ───────────────────────────────────────────┘
```

### 5.1 快速修复（当天完成）

- 意图关键词匹配错误 → 修改 `intent_parser.py` 的 `_quick_detect`
- 工具参数缺失 → 修改 `engine.py` 的 `_extract_params` 或 `executor.py` 的 `_extract_params`
- 输出格式问题 → 修改 `engine.py` 的最终答案生成 Prompt

### 5.2 中等修复（1-3 天）

- 意图解析 LLM Prompt 优化 → 增加 few-shot 示例
- Planner 规划能力增强 → 增加工具使用示例、增加约束
- 新工具/新功能 → 在 `tools.py` 注册，在 `executor.py` 实现

### 5.3 重大重构（1-2 周）

- 架构级问题（如上下文传递链断裂）
- 引入新的决策模式（如反射机制、多轮对话管理）
- 性能优化（如减少 LLM 调用次数、引入缓存）

---

## 六、测试用例库（持续积累）

### 6.1 基础功能测试

| # | 用户输入 | 预期工具调用 | 预期输出 |
|---|----------|-------------|----------|
| 1 | "帮我创建 EGFR 项目" | `create_project` | 项目创建成功，返回 project_id |
| 2 | "运行项目 35 的 pipeline" | `run_pipeline` | Pipeline 启动，返回 job_id |
| 3 | "查看项目 35 的状态" | `get_project_status` | 项目状态、进度、统计 |
| 4 | "分析失败分子原因" | `analyze_failures` | 失败分子分类、原因、建议 |
| 5 | "优化一下项目 35" | `suggest_next_step` / 调整参数+重跑 | 具体优化建议或执行优化 |
| 6 | "对比项目 35 和 36" | `compare_molecules` | 分子对比结果 |
| 7 | "项目 35 里最好的分子" | `get_top_molecules` | 排名前几的分子及属性 |

### 6.2 上下文记忆测试

| # | 对话序列 | 预期行为 |
|---|----------|----------|
| 1 | ①"创建 EGFR 项目" → ②"运行 pipeline" | ② 自动使用 ① 创建的 project_id |
| 2 | ①"看看项目 35" → ②"分析失败分子" → ③"优化一下" | ②③ 都使用 project_id=35 |
| 3 | ①"分析项目 35" → ②"再优化" | ② 识别为 follow-up，使用 project_id=35 |

### 6.3 边界/异常测试

| # | 用户输入 | 预期行为 |
|---|----------|----------|
| 1 | "帮我分析"（无上下文） | 澄清："请提供项目 ID 或靶点名称" |
| 2 | "运行项目 999999"（不存在的项目） | 优雅报错：项目不存在 |
| 3 | "分析失败分子"（无失败分子） | 提示：当前没有失败分子 |
| 4 | 超长消息（>1000 字符） | 正常处理，不截断关键信息 |
| 5 | 中英文混合 "帮我 analyze 项目 35" | 正确解析混合语言 |

---

## 七、调试工具与技巧

### 7.1 快速查看 Agent 内部状态

在 `engine.py` 的 `run()` 方法中添加日志：

```python
# 在 intent_parser 之后
print(f"[DEBUG] 意图解析结果: {parsed_intent}")
print(f"[DEBUG] 上下文: {context}")

# 在 planner 之后
print(f"[DEBUG] 规划步骤: {plan.steps}")

# 在 executor 之后
print(f"[DEBUG] 执行结果: {execution_result}")
```

### 7.2 查看 LLM 输入输出

在 `llm_client.py` 的 `call()` 中添加日志：

```python
print(f"[LLM CALL] Messages: {json.dumps(messages, ensure_ascii=False)[:500]}")
print(f"[LLM RESP] {content[:500]}")
```

### 7.3 测试单个模块

```python
# 测试意图解析
from backend.services.agent.intent_parser import IntentParser
parser = IntentParser()
result = parser.parse("分析失败分子原因", {"project_id": 35})
print(result)

# 测试工具执行
from backend.services.agent.tools import get_registry
registry = get_registry()
result = registry.execute("get_project_status", {"project_id": 35})
print(result)
```

---

## 八、经验记录（持续积累）

### 2024-XX-XX："分析失败分子原因"被错误识别为 follow_up

**问题**：用户说"分析失败分子原因"，Agent 执行了 `get_project_status` → `suggest_next_step`，没有分析失败分子  
**根因**：
1. `_quick_detect` 将"分析失败分子原因"匹配到 `follow_up_patterns`（因为包含"失败"），返回 `FOLLOW_UP` 意图
2. `planner` 的 `follow_up` 策略说：先获取上下文，再执行
3. `planner` 的 `user_prompt` 没有传递 `detected_actions`，LLM 不知道意图解析器已识别 `analyze_failures`
**修复**：
1. `intent_parser.py`：增加 `failure_analysis_patterns`，将"失败分子/失败原因/分析失败"识别为 `COMPLEX_ANALYSIS`
2. `planner.py`：在 `user_prompt` 中增加 `detected_actions` 字段，并增加规则：如果检测到 `analyze_failures`，直接调用
3. `planner.py`：修改 `follow_up` 和 `complex_analysis` 策略，明确"失败分析"场景直接调用分析工具
**验证**：用户说"分析失败分子原因"，Agent 直接调用 `analyze_failures`

### 2024-XX-XX：上下文记忆缺失导致追问

**问题**：Agent 不断追问项目 ID，不干活  
**根因**：`intent_parser` 的 `needs_clarification` 和 `engine` 的 `_needs_form` 不考虑 `context["project_id"]`  
**修复**：增强上下文感知，上下文有 `project_id` 时跳过澄清  
**验证**：用户说"帮我分析"，上下文有 project_id 时直接执行

### 2024-XX-XX：SSL 错误导致 LLM 调用失败

**问题**：`SSLError: UNEXPECTED_EOF_WHILE_READING`  
**根因**：网络波动 + LLM 调用无重试  
**修复**：`llm_client.py` 添加 `retry_call` + 连接池 + SSL 错误识别  
**验证**：网络波动时自动重试，不崩溃

### 2024-XX-XX：PipelineRunner 属性未初始化

**问题**：`AttributeError: 'PipelineRunner' object has no attribute 'pipeline_run'`  
**根因**：`__init__` 中未初始化 `self.pipeline_run`  
**修复**：添加 `self.pipeline_run = None`  
**验证**：Pipeline 能正常启动

---

## 九、下一步优化方向（待评估）

### 9.1 高优先级（影响核心体验）

- [ ] **意图解析准确率**：增加更多 few-shot 示例，覆盖药物设计专业术语
- [ ] **失败分析能力**：完善 `analyze_failures` 工具，给出结构化失败原因
- [ ] **输出质量**：最终答案增加数据可视化（表格、对比）
- [ ] **错误处理**：工具执行失败时，Agent 能自动重试或给出替代方案

### 9.2 中优先级（增强体验）

- [ ] **多轮对话**：支持更复杂的对话流（如："分析 → 优化 → 再运行 → 对比"）
- [ ] **记忆增强**：不仅记住 project_id，还记住用户的偏好（如常用靶点、常用参数）
- [ ] **主动建议**：Agent 能主动发现项目问题并提醒用户

### 9.3 低优先级（锦上添花）

- [ ] **流式输出**：支持 SSE 流式输出，减少等待感
- [ ] **语音/图片输入**：支持更多模态的输入
- [ ] **A/B 测试**：支持意图解析模型的 A/B 测试

---

## 十、总结：如何持续提升 Agent

> **核心原则**：每个用户反馈 = 一个测试用例 + 一个修复机会 + 一个经验积累

1. **发现问题**：用户测试，记录实际输出 vs 预期输出
2. **记录问题**：按"测试记录模板"填写，不遗漏细节
3. **分析根因**：从意图解析 → 规划 → 执行 → 输出，逐层定位
4. **精准修复**：最小改动原则，只改出问题的那一层
5. **验证修复**：回归测试，确保没引入新问题
6. **积累知识**：把经验写入本文档，形成知识库

**目标**：通过持续迭代，让 Agent 的意图理解准确率 > 90%，工具调用准确率 > 95%，用户满意度 > 90%。

---

*文档版本：v1.1*  
*最后更新：2024-XX-XX*  
*维护者：AI Agent 迭代团队*
