# DrugDesign Copilot Agent - 最终目标与实现计划

> 版本: 1.0  
> 状态: 待审阅  
> 作者: AI Assistant  
> 目标: 实现真正全自动的药物设计 Copilot Agent，用户只需给目标，其余全部由 Agent 自主完成。

---

## 一、最终目标（Vision）

**用户输入一句自然语言，Agent 自主完成整个药物设计工作流。**

### 理想交互示例

```
用户: "帮我设计针对 EGFR 的分子"
Agent: 自动完成以下全部步骤
  1. 检测靶点 EGFR → 从数据库获取靶点信息（PDB、活性分子、描述）
  2. 创建项目（名称自动生成 EGFR_20250627）
  3. 自动添加靶点对应的已知活性分子作为参考
  4. 运行 Pipeline（分子生成 → 过滤 → 结构筛选 → ADMET → 精炼 → 合成）
  5. 等待 Pipeline 完成，获取 Top 候选分子
  6. 返回给用户：项目名称、Top 分子列表、SMILES、ADMET 预测、对接分数、QED 等
  7. 建议下一步（如分子对接、FEP 精筛、合成）

用户: "优化一下这些分子"
Agent: 自动执行失败分析 → 调整过滤参数 → 重新运行 Pipeline → 返回优化后的结果

用户: "Top 3 的分子对接分数怎么样？"
Agent: 自动获取项目状态 → 分析 Top 3 分子的对接分数 → 返回对比分析
```

### 核心原则
- **零点击**：用户只需说话，不需要点击任何按钮或填写任何表单
- **零配置**：Agent 自动推断所有参数，使用合理的默认值
- **全链路**：从靶点 → 项目 → Pipeline → 结果 → 分析 → 建议，全程自主
- **可解释**：每一步做了什么、结果如何、为什么这样，都清晰报告给用户

---

## 二、当前项目结构理解

### 后端（Flask + SQLAlchemy + SQLite）

| 文件/模块 | 作用 | 当前状态 |
|-----------|------|----------|
| `models/database.py` | 数据模型：Project, ActiveMolecule, GeneratedMolecule, MoleculeProperty, AdmetPrediction, PipelineRun, SynthesisRoute, AssayResult | 完整 |
| `services/pipeline.py` | PipelineRunner：8 阶段流程（输入→生成→过滤→结构筛选→ADMET→精炼→合成→报告） | 完整但 _run_async 调用有 bug（已修复） |
| `services/target_database.py` | 靶点数据库：已知靶点信息、活性分子、PDB ID | 30+ 靶点 |
| `services/agent/` | Agent 核心引擎 | 正在重构 |
| `services/agent/engine.py` | ReAct 引擎：Perceive→Plan→Execute→Report | 已实现，需完善 |
| `services/agent/planner.py` | TaskPlanner：LLM 生成多步计划 | 已实现，需完善 prompt |
| `services/agent/executor.py` | TaskExecutor：逐步执行计划，带 LLM 自适应 | 已实现，需增强类型防御 |
| `services/agent/tools.py` | 工具注册表：create_project, run_pipeline, get_top_molecules 等 | 已实现，需增加更多工具 |
| `services/agent/memory.py` | 三层记忆：对话、项目、全局 | 已实现 |
| `services/agent/action_protocol.py` | 前端动作协议：根据执行结果生成前端动作 | 已实现，但 Agent 自主模式不需要 |
| `routes/agent.py` | /api/agent/chat, /api/agent/goal | 已实现 |
| `routes/projects.py` | 项目 CRUD + /top-molecules | 已实现 |
| `routes/generation.py` | Pipeline 运行接口 | 已实现 |
| `routes/docking.py` | 分子对接接口 | 已实现 |
| `routes/admet.py` | ADMET 预测接口 | 已实现 |
| `routes/pipeline.py` | Pipeline 状态查询 | 已实现 |

### 前端（React + Vite + Tailwind）

| 组件/页面 | 作用 | 当前状态 |
|-----------|------|----------|
| `HelpChatModal.jsx` | Copilot 聊天弹窗（双模式：Copilot/Chat） | 已实现，需移除 action cards 和表单 |
| `TargetSelector.jsx` | 靶点搜索选择器 | 已实现，但 Agent 模式下不需要 |
| `ProjectList.jsx` | 项目列表 | 已实现 |
| `PipelineRun.jsx` | Pipeline 运行页面 | 已实现 |
| `MoleculeBrowser.jsx` | 分子浏览器 | 已实现 |
| `DockingView.jsx` | 分子对接界面 | 已实现 |
| `ADMETPanel.jsx` | ADMET 分析面板 | 已实现 |
| `AppContext.jsx` | 全局状态管理 | 已实现 |

### 关键数据流

```
用户 → /api/agent/chat → CopilotAgent.chat() → ReActEngine.run()
  → _is_simple_chat() → _needs_form() → Perceive → Plan → Execute → Report
  → 返回 {type, final_answer, steps, execution_report, actions}

Pipeline: PipelineRunner 在后台线程运行
  → 读取项目 active_molecules → 生成分子 → 筛选 → 保存到 generated_molecules
```

---

## 三、当前问题分析（Gap Analysis）

### P0（致命）

| # | 问题 | 影响 | 根因 |
|---|------|------|------|
| P0-1 | `'str' object has no attribute 'get'` | 执行失败，无法返回结果 | LLM 返回非 JSON 对象，代码未做类型防御 |
| P0-2 | `PipelineRunner` 参数顺序错误 | Pipeline 无法运行 | `tools.py` 中 `PipelineRunner(project_id, params, ...)` 应为 `PipelineRunner(session_factory, project_id, params, ...)` |
| P0-3 | 前端超时 30 秒 | 请求超时，无法完成 | axios timeout 太短，ReAct 需要多次 LLM 调用 |
| P0-4 | 没有自动添加活性分子 | Pipeline 没有种子分子，生成质量差 | `create_project` 没有调用 `get_active_molecules_for_target` |

### P1（重要）

| # | 问题 | 影响 | 根因 |
|---|------|------|------|
| P1-1 | 前端 Action Cards 要求用户点击 | 不是真正的自动化 | 设计上仍依赖用户确认 |
| P1-2 | `get_top_molecules` 返回空 | Pipeline 还没完成，没有结果 | Pipeline 是异步的，执行时还没完成 |
| P1-3 | Agent 不知道 Pipeline 进度 | 无法给用户准确的反馈 | 缺少 `get_pipeline_progress` 工具 |
| P1-4 | 没有工具获取 Pipeline 失败详情 | 无法分析为什么没分子 | 缺少 `get_pipeline_failures` 工具 |
| P1-5 | Planner 没有足够的环境信息 | 计划可能不精准 | Perception 层获取的状态不够丰富 |

### P2（增强）

| # | 问题 | 影响 | 根因 |
|---|------|------|------|
| P2-1 | 没有分子对接工具 | 无法完成对接分析 | 缺少 `run_docking` Agent 工具 |
| P2-2 | 没有 ADMET 单独分析工具 | 无法对已有分子做 ADMET | 缺少 `analyze_admet` Agent 工具 |
| P2-3 | 没有分子对比工具 | 无法对比多个分子 | 已有 `compare_molecules`，但不够直观 |
| P2-4 | 没有合成路径分析工具 | 无法评估合成可行性 | 已有 `synthesis_route` 接口，但缺少 Agent 工具封装 |
| P2-5 | 没有迭代优化闭环 | 一次 Pipeline 后无法自动优化 | 缺少 `optimize_pipeline` 策略 |

---

## 四、实现计划（详细步骤）

### 阶段 1：修复致命 Bug（P0）

**目标：让 Agent 能完整跑通 create_project → run_pipeline → get_top_molecules**

1. ✅ **P0-1：JSON 类型防御**（已完成）
   - `executor.py` `_parse_llm_decision`：增加 `isinstance(parsed, dict)` 检查
   - `executor.py` `_run_single_step`：增加 `step_def` 不是字典的防御
   - `executor.py` `execute_plan` modify 分支：过滤 `new_steps` 中的非字典元素
   - `planner.py` `_parse_llm_plan`：增加 `isinstance(plan, dict)` 检查
   - `action_protocol.py` `generate_from_result`：增加 `execution_report`/`env_state`/`steps` 类型检查

2. ✅ **P0-2：PipelineRunner 参数修复**（已完成）
   - `tools.py` `_run_async`：改为 `PipelineRunner(SessionLocal, project_id, params, pipeline_run.id)`
   - `pipeline.py` `__init__`：新增可选 `pipeline_run_id` 参数
   - `pipeline.py` `_run_pipeline`：如果传了 `pipeline_run_id`，复用已有记录

3. ✅ **P0-3：前端超时**（已完成）
   - `client.js`：axios timeout 从 30000 改为 120000

4. ✅ **P0-4：自动添加活性分子**（已完成）
   - `tools.py` `create_project`：创建项目后，如果 `target_name` 存在，调用 `get_active_molecules_for_target` 获取活性分子，添加到 `ActiveMolecule` 表
   - `planner.py` system prompt：明确告诉 LLM `create_project` 已自动添加活性分子

### 阶段 2：移除所有需要用户点击的交互（P1-1）

**目标：Agent 自主执行，前端只展示结果**

1. **修改 `engine.py` `_build_action_cards_from_plan`**
   - 当前行为：为每个计划步骤生成可点击的 Action Card
   - 目标行为：Action Cards 只作为**信息展示**（告诉用户 Agent 打算做什么），不执行任何操作
   - 或者：完全移除 Action Cards，在 `final_answer` 中用文字描述计划

2. **修改 `routes/agent.py` `/agent/chat`**
   - 移除 `action_cards` 字段（或保留但不触发前端交互）
   - 确保 `execution_report` 包含完整的执行结果

3. **修改 `HelpChatModal.jsx`**
   - 移除 Action Cards 的渲染逻辑
   - 移除 `handleExecuteAction`（用户点击执行按钮的函数）
   - 保留：消息展示、执行步骤展示、最终报告展示
   - 保留：系统通知（Toast）用于告知用户状态变化

### 阶段 3：增强 Agent 工具集（P1-2 ~ P2-5）

**目标：让 Agent 能处理更多场景，包括 Pipeline 异步等待、失败分析、进度查询等**

1. **新增 `get_pipeline_progress` 工具**（P1-3）
   - 查询指定项目的最新 PipelineRun 状态
   - 返回：status（pending/running/completed/failed）、当前阶段、分子数统计、预计完成时间
   - 位置：`tools.py` + `routes/projects.py` 端点

2. **新增 `get_pipeline_failures` 工具**（P1-4）
   - 查询 Pipeline 失败分子的详细信息
   - 返回：失败阶段分布、失败原因统计、建议调整
   - 复用已有的 `analyze_failures` 工具，但增强输出

3. **新增 `run_docking` 工具**（P2-1）
   - 对指定分子的 SMILES 运行分子对接
   - 返回：对接分数、结合模式、可视化数据
   - 封装 `routes/docking.py` 的对接逻辑

4. **新增 `analyze_admet` 工具**（P2-2）
   - 对指定分子的 SMILES 运行 ADMET 预测
   - 返回：溶解度、毒性、代谢稳定性、血脑屏障穿透等
   - 封装 `routes/admet.py` 的 ADMET 逻辑

5. **新增 `get_synthesis_route` 工具**（P2-4）
   - 对指定分子的 SMILES 生成合成路径
   - 返回：合成路线、可及性评分、预计步骤数
   - 封装已有的合成路径逻辑

6. **新增 `wait_for_pipeline` 工具**（关键！）
   - 这是一个"阻塞式"工具：轮询 Pipeline 状态直到完成（或超时）
   - 实现：循环调用 `get_pipeline_progress`，sleep 2 秒，最多等待 300 秒
   - 返回：最终状态、结果摘要、错误信息
   - 这样 Agent 可以：`create_project → run_pipeline → wait_for_pipeline → get_top_molecules`，全程自动

### 阶段 4：增强 Planner 的感知能力（P1-5）

**目标：Planner 能根据丰富的环境信息做出更精准的计划**

1. **扩展 `EnvironmentPerception`（Perception 层）**
   - 当前：只获取项目基本状态（分子数、Pipeline 状态）
   - 目标：增加以下信息：
     - 项目最近 3 次 PipelineRun 的结果（成功/失败/原因）
     - 当前失败分子的阶段分布
     - 当前 Top 分子的 ADMET 概况（平均溶解度、毒性等）
     - 项目的过滤参数配置
     - 是否有未完成的 Pipeline 正在运行

2. **扩展 `planner.py` system prompt**
   - 增加"Pipeline 异步等待策略"：
     - 如果目标需要 Pipeline 结果，计划必须包含 `wait_for_pipeline` 步骤
     - 如果 Pipeline 失败，计划应包含 `get_pipeline_failures` → `analyze_failures` → `adjust_filters` → 重新运行
   - 增加"分子优化策略"：
     - 如果用户说"优化"，先分析失败原因 → 调整参数 → 重跑
   - 增加"多轮对话策略"：
     - 如果用户没有指定项目，从记忆中查找最近的项目
     - 如果用户提到"上次"、"这个项目"，自动关联上下文

### 阶段 5：前端展示优化

**目标：用户看到的是 Agent 的完整工作过程和最终结果，而不是零散的按钮和表单**

1. **重新设计消息展示结构**
   - 用户消息：正常展示
   - Agent 系统消息：用时间线/步骤列表展示 ReAct 执行过程
   - Agent 最终结果：用结构化卡片展示（Top 分子表格、ADMET 雷达图、对接分数等）
   - 系统通知：Toast 提示重要事件（项目创建、Pipeline 启动、完成等）

2. **新增 `MoleculesResultCard` 组件**
   - 展示 Top N 分子的关键信息：
     - 结构式（2D SMILES 渲染）
     - 对接分数、ADMET 综合分、QED、分子量、LogP
     - 合成可及性评分
   - 可点击展开查看详细信息

3. **新增 `PipelineProgressBar` 组件**
   - 当 Pipeline 运行时，展示实时进度
   - 阶段：输入 → 生成 → 过滤 → 结构筛选 → ADMET → 精炼 → 合成 → 完成
   - 每个阶段显示当前分子数

4. **简化 HelpChatModal**
   - 移除：Action Cards、表单（ProjectCreationForm）、手动执行按钮
   - 保留：消息列表、输入框、建议问题、执行步骤展示、最终结果卡片
   - 新增：Pipeline 进度指示器（当 Agent 报告 Pipeline 正在运行时显示）

### 阶段 6：测试与验证

**目标：确保所有场景都能正确运行**

1. **场景测试矩阵**
   | 场景 | 输入 | 预期行为 |
   |------|------|----------|
   | 靶点直推 | "EGFR" | 创建项目 → 添加活性分子 → 运行 Pipeline → 等待 → 返回 Top 分子 |
   | 靶点直推（带描述） | "帮我设计针对 BRAF 的抗癌分子" | 同上 |
   | 优化项目 | "优化项目" | 获取状态 → 分析失败 → 调整参数 → 重跑 Pipeline → 返回新结果 |
   | 查看结果 | "Top 分子怎么样" | 获取项目状态 → 获取 Top 分子 → 分析 ADMET → 返回报告 |
   | 分子对接 | "对接一下 Top 3" | 获取 Top 3 SMILES → 运行对接 → 返回对接分数和结合模式 |
   | 对比分子 | "对比这几个分子" | 获取 SMILES → 对比性质 → 返回对比表格 |
   | 简单聊天 | "你好" | 正常聊天，不执行任何工具 |
   | 聊天带建议 | "有什么建议" | 获取项目状态 → 分析 → 给出建议 |

2. **错误恢复测试**
   - LLM 返回无效 JSON → 回退到默认计划
   - Pipeline 运行失败 → Agent 自动分析失败原因并建议调整
   - 网络超时 → 重试或告知用户稍后再试
   - 项目不存在 → 建议创建新项目或列出已有项目

3. **性能测试**
   - LLM 调用次数：单次用户请求 ≤ 5 次 LLM 调用（Planner + 2-3 次决策 + 总结）
   - 响应时间：简单聊天 < 3 秒，复杂任务（含 Pipeline）< 120 秒（前端超时）
   - 并发：支持 5 个用户同时与 Agent 交互

---

## 五、实现优先级（执行顺序）

```
阶段 1（P0 修复）→ 阶段 2（移除交互）→ 阶段 3（增强工具）→ 阶段 4（增强感知）→ 阶段 5（前端优化）→ 阶段 6（测试验证）
```

**关键路径**：阶段 1 → 阶段 2 → 阶段 3（wait_for_pipeline）

只有 `wait_for_pipeline` 实现后，Agent 才能完整地：`create → run → wait → get_top`，否则用户永远只能得到"Pipeline 正在运行中"的半成品结果。

---

## 六、成功标准（Definition of Done）

1. **用户输入一个靶点名称，120 秒内得到完整的 Top 分子报告**（不需要任何手动操作）
2. **用户输入"优化"，Agent 自动分析失败原因、调整参数、重跑 Pipeline、返回优化结果**
3. **用户输入任何与项目相关的问题，Agent 能正确调用工具并给出准确答案**
4. **用户输入简单问候/闲聊，Agent 正常聊天，不执行工具**
5. **前端没有任何"执行""确认"按钮需要用户点击**
6. **所有错误都有友好的错误消息和恢复建议**
7. **代码没有 P0/P1 级别 bug**

---

## 七、文件修改清单

### 后端（backend/）

| 文件 | 修改类型 | 修改内容 |
|------|----------|----------|
| `services/agent/engine.py` | 修改 | 移除 Action Cards 生成功能（或改为只展示） |
| `services/agent/planner.py` | 修改 | 增强 system prompt，增加 Pipeline 等待策略 |
| `services/agent/executor.py` | 修改 | 已修复类型防御，保持现状 |
| `services/agent/tools.py` | 新增 | 新增 `wait_for_pipeline`, `get_pipeline_progress`, `run_docking`, `analyze_admet`, `get_synthesis_route` |
| `services/agent/perception.py` | 修改 | 扩展环境感知信息 |
| `services/agent/action_protocol.py` | 修改 | 可选：完全移除或简化（Agent 自主模式不需要前端动作） |
| `routes/agent.py` | 修改 | 移除 `action_cards` 返回，简化响应结构 |
| `routes/projects.py` | 新增 | 新增 `/pipeline-progress` 端点 |
| `routes/docking.py` | 修改 | 增加可被 Agent 工具调用的函数接口 |
| `routes/admet.py` | 修改 | 增加可被 Agent 工具调用的函数接口 |
| `routes/pipeline.py` | 修改 | 增加可被 Agent 工具调用的函数接口 |

### 前端（frontend/）

| 文件 | 修改类型 | 修改内容 |
|------|----------|----------|
| `src/api/client.js` | 修改 | 已修复 timeout（120s），保持现状 |
| `src/components/HelpChatModal.jsx` | 大幅修改 | 移除 Action Cards、表单、手动执行按钮；新增 Pipeline 进度指示器、结果卡片 |
| `src/components/MoleculesResultCard.jsx` | 新增 | Top 分子结果展示卡片 |
| `src/components/PipelineProgressBar.jsx` | 新增 | Pipeline 实时进度条 |
| `src/store/AppContext.jsx` | 可选 | 简化 state 管理（如果不需要处理 Agent 动作） |

---

## 八、风险评估与应对

| 风险 | 可能性 | 影响 | 应对措施 |
|------|--------|------|----------|
| LLM 不稳定（JSON 解析失败、超时） | 高 | 中 | 多层防御：类型检查、fallback plan、错误恢复 |
| Pipeline 运行时间长（> 120s） | 中 | 高 | 前端改为"轮询"模式：先返回"Pipeline 已启动"，然后定期查询进度 |
| Pipeline 生成质量差（没有通过分子） | 中 | 高 | Agent 自动分析失败原因 → 调整参数 → 重跑 |
| 靶点数据库覆盖不全 | 中 | 中 | 如果靶点不存在，Agent 使用通用模板 + 告知用户 |
| LLM 成本过高 | 低 | 中 | 缓存常见计划、使用轻量级模型处理简单查询 |

---

## 九、后续扩展（V2 规划）

1. **多轮迭代优化**：Agent 自动跑多轮 Pipeline，每轮根据上一轮结果调整策略
2. **分子生成策略自适应**：根据靶点类型自动选择最佳生成策略（crem/rnn/scaffold）
3. **实验设计建议**：根据 Top 分子建议优先合成哪些、做哪些实验验证
4. **知识库增强**：接入文献数据库，自动检索靶点相关最新研究
5. **可视化增强**：3D 分子结构展示、对接姿态可视化、ADMET 雷达图

---

## 十、审查清单

请审阅以下问题，确认无误后再开始实现：

- [ ] 最终目标描述是否准确？
- [ ] 当前问题分析是否全面？
- [ ] 实现计划是否可行？
- [ ] 优先级是否合理？
- [ ] 成功标准是否可验证？
- [ ] 文件修改清单是否完整？
- [ ] 是否有遗漏的风险？

**审阅完成后，请回复："开始实现"，我将按阶段执行。**
