# DrugDesign Agent 全面优化计划

> **版本**：v1.0  
> **日期**：2025-06-28  
> **范围**：`backend/services/agent/` 目录下全部文件 + 新增工具  
> **目标**：将 AI Agent 从"勉强能用"提升到"专业级商用水平"

---

## 一、项目结构总览（执行本计划前必读）

```
drugdesign-agent/
├── run.py                          ← 后端启动脚本
├── .env                            ← API密钥、数据库路径
├── backend/
│   ├── app.py                      ← Flask总入口（注册所有路由蓝图）
│   ├── drugdesign.db               ← SQLite数据库（项目、分子、Pipeline记录）
│   ├── models/database.py          ← SQLAlchemy数据表定义（Project、Molecule等）
│   │
│   ├── routes/                     ← 前端调用的API接口（16个模块，70+端点）
│   │   ├── agent.py               ← /api/agent/chat, /api/agent/goal（Agent主入口）
│   │   ├── projects.py            ← 项目CRUD + 靶点搜索
│   │   ├── pipeline.py            ← Pipeline运行控制 + 失败分子库
│   │   ├── admet.py              ← ADMET五维预测
│   │   ├── docking.py            ← AutoDock Vina分子对接
│   │   ├── synthesis.py          ← 逆合成分析
│   │   ├── structure.py          ← 3D结构获取（SDF/PDB/XYZ）
│   │   ├── activity.py           ← QSAR活性预测/训练
│   │   └── ...（其他8个模块）
│   │
│   ├── services/                   ← 业务逻辑引擎（真正干活）
│   │   ├── pipeline.py            ← 8层Pipeline总管（生成→过滤→结构→ADMET→精修→合成→输出）
│   │   ├── generation.py          ← 分子生成（CReM/RDKit/Scaffold）
│   │   ├── filtering.py           ← 分子过滤（PAINS/药物样性）
│   │   ├── admet.py              ← ADMET预测（5分类深度学习）
│   │   ├── docking.py            ← 分子对接（Vina）
│   │   ├── synthesis.py          ← 逆合成分析（20种反应模板）
│   │   ├── structure.py          ← 3D结构处理
│   │   ├── activity.py           ← QSAR活性预测/训练
│   │   ├── fep_refinement.py     ← FEP精修（OpenFE/OpenMM）
│   │   ├── target_database.py    ← 30个靶点数据库
│   │   └── utils.py              ← RDKit基础工具（SMILES验证/描述符计算/可视化）
│   │
│   └── services/agent/             ← ⭐ AI Agent核心（本次优化重点）
│       ├── engine.py              ← Agent主控（ReAct循环：Perceive→Plan→Execute→Report）
│       ├── intent_parser.py       ← 意图解析器（3层：关键词→正则→LLM）
│       ├── planner.py            ← 任务规划器（LLM生成JSON步骤计划）
│       ├── executor.py           ← 任务执行器（逐步调用工具+LLM决策）
│       ├── tools.py              ← 工具注册表（当前15个工具）
│       ├── perception.py         ← 环境感知（查询项目状态）
│       ├── memory.py             ← 记忆模块（Buffer+Project+Long-term）
│       ├── llm_client.py         ← LLM调用封装（Kimi API）
│       ├── config.py             ← Agent配置（模型/超时/缓存）
│       ├── tracer.py            ← 执行追踪（替代LangSmith）
│       ├── action_protocol.py     ← 前端动作生成（导航/状态更新/Toast）
│       └── prompts/              ← 提示词模板（YAML）
│           ├── planner_system.yaml
│           └── planner_user.yaml
│
└── frontend/
    ├── src/App.jsx               ← 路由总管
    ├── src/api/client.js         ← Axios封装（调用后端API）
    ├── src/components/           ← 可复用UI组件
    │   ├── HelpChatModal.jsx     ← Copilot聊天窗口（Agent交互入口）
    │   ├── AgentTracePanel.jsx   ← Agent执行追踪面板
    │   └── ...（其他组件）
    └── src/pages/                ← 16个页面（项目/分子/Pipeline/ADMET/对接/合成等）
```

**数据流动（用户输入一句话后）**：
```
用户输入
  → 前端 HelpChatModal.jsx
  → axios POST /api/agent/goal
  → routes/agent.py 接收
  → services/agent/engine.py 启动ReAct循环
    → intent_parser.py 识别意图（11种类型）
    → planner.py 生成执行计划（JSON步骤列表）
    → executor.py 逐个执行工具
    → tools.py 中的工具调用 services/ 下的引擎
  → 结果返回前端 → 渲染报告
```

---

## 二、当前问题诊断（根本原因）

### 2.1 为什么"AI不懂用户意思"

| 问题 | 表现 | 根因 |
|------|------|------|
| 用户说"分析这个分子的合成" | Agent报错/无工具 | `synthesis.py` 有完整功能，但 `tools.py` 没有 `analyze_synthesis` 工具 |
| 用户说"对接一下这个分子" | Agent只能跑完整Pipeline | `docking.py` 有独立API，但Agent无法单独调用对接 |
| 用户说"查一下EGFR靶点" | Agent无响应 | `target_database.py` 有搜索功能，但Agent没有 `search_targets` 工具 |
| 用户说"训练一个QSAR模型" | Agent无法执行 | `activity.py` 有训练功能，但Agent没有 `train_qsar_model` 工具 |
| 用户说"获取3D结构" | Agent无法执行 | `structure.py` 有API，但Agent没有 `get_3d_structure` 工具 |
| 用户说"如果ADMET>80就继续" | 条件判断可能出错 | `executor.py` 条件评估用 `"true" in raw.lower()` 判断，过于简单 |
| 用户说"帮我优化一下" | 丢失上下文 | `memory.py` 超token时直接截断为最近5条，丢失早期关键信息 |
| 用户说复杂多步骤任务 | 规划可能引用不存在工具 | `planner_system.yaml` 提到 `analyze_admet_sar`、`check_patent_novelty` 等未注册工具 |
| 用户说"分析失败原因" | 没有project_id时返回错误 | `intent_parser.py` 中 `str(None)` = `"None"` 被当作有效ID |
| 用户说"跑AKT1全流程" | 1000个分子全部失败 | `filtering.py` 空字典 `{}` 触发回退到严格默认值 |

**核心结论**：Agent的"大脑"（engine/planner/executor）功能基本齐全，但**"手脚"（tools）严重短缺**——前端有完整功能，但Agent只能调用15个工具，大量功能无法直接调用。

### 2.2 技术债务清单

| 文件 | 问题 | 严重程度 |
|------|------|----------|
| `tools.py` | 每次调用创建新数据库Session，无连接池 | **高** |
| `planner.py` | 模板加载失败时 `logger` 未定义，会抛 `NameError` | **高** |
| `intent_parser.py` | `str(project_id)` 可能为 `"None"` | **高** |
| `executor.py` | `_evaluate_condition` 用 `"true" in raw.lower()` 判断，易误判 | **高** |
| `memory.py` | 超token直接截断而非摘要，丢失关键上下文 | **高** |
| `planner_system.yaml` | 引用5个未注册工具（`analyze_admet_sar` 等） | 中 |
| `executor.py` | 条件步骤逻辑重复处理 | 中 |
| `perception.py` | 每次plan()重新查询全部状态，无缓存 | 中 |
| `intent_parser.py` | SMILES隐式提取正则过于宽泛，误报率高 | 中 |
| `tools.py` | 工具参数无schema校验，LLM可能编造参数 | 中 |
| `config.py` | `STEP_TIMEOUT` 30秒与 `executor.py` 300秒不一致 | 低 |
| `tracer.py` | 追踪文件无大小限制，长期运行可能GB级 | 低 |

---

## 三、优化目标

### 3.1 总体目标

将 Agent 从"只能跑Pipeline的全自动化工具"升级为**"能理解复杂药物设计任务、能调用任意系统功能、能给出专业建议的智能化学家助手"**。

### 3.2 具体目标

| 维度 | 现状 | 目标 |
|------|------|------|
| 工具覆盖 | 15个工具 | **22+个工具**（覆盖所有前端核心功能） |
| 意图理解 | 11种类型，关键词匹配为主 | **增强LLM深度解析权重**，减少误判 |
| 任务规划 | 线性步骤列表 | **支持条件分支、循环迭代、并行执行** |
| 执行可靠性 | 单步失败即中断 | **支持失败重试、自适应降级、优雅回退** |
| 上下文记忆 | 粗暴截断 | **智能摘要+关键信息保留** |
| 参数校验 | 无校验 | **schema校验，LLM错误参数提前拦截** |
| 用户反馈 | 成功/失败 | **成功/部分成功/失败+原因+建议** |
| 无法完成 | 尝试后失败 | **提前识别，明确反馈"无法完成+原因+替代方案"** |

---

## 四、详细执行计划（分5个阶段）

### 阶段1：工具补全（高优先级，让Agent"有手有脚"）

**目标**：将系统已有但Agent无法调用的功能，全部注册为Agent工具。

#### 1.1 新增工具清单（7个高优先级工具）

| # | 工具名 | 调用哪个服务 | 功能 | 用户场景 |
|---|--------|-------------|------|----------|
| 1 | `search_targets` | `target_database.search_targets` | 搜索靶点数据库 | "帮我查一下EGFR" |
| 2 | `get_target_info` | `target_database.get_target_info` | 获取靶点详细信息 | "EGFR有什么已知的药物" |
| 3 | `run_docking` | `docking.run_docking` | 分子对接 | "对接一下这个分子和AKT1" |
| 4 | `analyze_synthesis` | `synthesis.SynthesisAnalyzer.analyze` | 逆合成分析 | "这个分子能合成吗" |
| 5 | `predict_activity` | `activity.predict_activity` | 活性预测 | "预测这个分子对HER2的活性" |
| 6 | `train_qsar_model` | `activity.train_qsar_model` | QSAR模型训练 | "用这些分子训练一个模型" |
| 7 | `get_3d_structure` | `structure.get_molecule_structure` | 获取3D结构 | "给我这个分子的3D结构" |

#### 1.2 增强现有工具

| 工具 | 增强内容 |
|------|----------|
| `analyze_single_molecule_admet` | 支持批量分析（`smiles_list` 参数） |
| `compare_molecules` | 支持对比更多维度（ADMET、合成可及性、对接分数） |
| `run_full_pipeline` | 支持更细粒度的参数控制（`filter_params` 传入） |

#### 1.3 修改文件

- `backend/services/agent/tools.py` — 新增7个工具注册 + 增强现有工具
- `backend/services/agent/planner.py` — 更新工具描述构建逻辑
- `backend/services/agent/intent_parser.py` — 为新工具添加意图检测关键词

#### 1.4 验收标准

- [ ] 用户输入"帮我查一下EGFR靶点" → Agent返回靶点信息
- [ ] 用户输入"分析CCO的合成路线" → Agent调用 `analyze_synthesis`
- [ ] 用户输入"对接一下这个分子" → Agent调用 `run_docking`
- [ ] 用户输入"预测活性" → Agent调用 `predict_activity`
- [ ] 所有新工具在 `/api/agent/tools` 列表中可见

---

### 阶段2：意图解析增强（让Agent"更懂人话"）

**目标**：提升意图识别准确率，减少误判和漏判。

#### 2.1 修复已知Bug

| 文件 | 修改 | 原因 |
|------|------|------|
| `intent_parser.py` | 修复 `str(project_id)` 为 `"None"` 的问题 | 避免无效project_id被当作有效值 |
| `intent_parser.py` | 优化SMILES隐式提取正则 | 减少误报（如"ATP"被误判为SMILES） |
| `intent_parser.py` | 优化 `_is_valid_smiles_looking` 检查 | 增加更严格的SMILES验证 |
| `planner.py` | 修复 `logger` 未定义 | 模板加载失败时不崩溃 |
| `planner_system.yaml` | 删除引用未注册工具的示例 | 避免LLM幻觉 |

#### 2.2 增强意图检测

| 意图 | 新增检测模式 | 示例 |
|------|------------|------|
| `SINGLE_ACTION` | 对接相关词汇 | "对接一下"、"docking"、"结合能" |
| `SINGLE_ACTION` | 合成相关词汇 | "合成路线"、"逆合成"、"能合成吗" |
| `SINGLE_ACTION` | 靶点查询词汇 | "查一下靶点"、"有什么靶点"、"target database" |
| `SINGLE_ACTION` | 3D结构词汇 | "3D结构"、"SDF文件"、"PDB格式" |
| `SINGLE_ACTION` | 活性预测词汇 | "预测活性"、"IC50"、"pIC50"、"QSAR" |
| `FOLLOW_UP` | 上下文依赖词扩展 | "上面的分子"、"刚才的结果"、"用刚才的项目" |
| `CLARIFICATION_NEEDED` | 模糊动词 + 无实体 | "分析一下"、"优化一下"（无明确对象） |

#### 2.3 改进多意图拆分

- 当前：`split_multi_intent` 按 `detected_actions` 简单拆分
- 改进：保留原始消息中的实体分配关系，确保子意图有完整上下文

#### 2.4 修改文件

- `backend/services/agent/intent_parser.py`
- `backend/services/agent/planner.py`
- `backend/services/agent/prompts/planner_system.yaml`

#### 2.5 验收标准

- [ ] 用户输入"帮我查一下EGFR" → 意图识别为 `SINGLE_ACTION` + 工具 `search_targets`
- [ ] 用户输入"分析一下"（无对象）→ 意图识别为 `CLARIFICATION_NEEDED`
- [ ] 用户输入"ATP的合成路线" → 不将"ATP"误判为SMILES
- [ ] 用户输入"项目None的结果" → 不将"None"当作有效project_id

---

### 阶段3：执行引擎增强（让Agent"更可靠"）

**目标**：提升执行可靠性，支持失败重试、自适应降级、条件判断。

#### 3.1 修复条件评估逻辑

**文件**：`backend/services/agent/executor.py`

**当前问题**：
```python
# 第685行：过于简单
return "true" in raw.lower()
# LLM回答 "The condition is false because..." 会被误判为 true
```

**改进方案**：要求LLM返回结构化JSON：
```json
{"result": false, "reason": "The condition requires ADMET > 80, but the value is 65"}
```

然后严格解析 `result` 字段（布尔值），而非模糊字符串匹配。

#### 3.2 修复记忆截断问题

**文件**：`backend/services/agent/memory.py`

**当前问题**：超token时直接截断为最近5条，丢失早期关键信息。

**改进方案**：
1. 优先保留**关键消息类型**：项目创建、靶点设定、Pipeline启动、重要结果
2. 对非关键消息进行**LLM摘要**而非直接丢弃
3. 摘要格式：`{"type": "summary", "content": "用户之前创建了AKT1项目并运行了Pipeline"}`

#### 3.3 添加工具参数Schema校验

**文件**：`backend/services/agent/tools.py` 中的 `ToolRegistry.execute`

**当前**：直接 `func(**action.params)`，无校验。

**改进**：在调用前校验参数：
1. 检查必填参数是否缺失
2. 检查参数类型是否匹配（str/int/float）
3. 检查参数值是否在允许范围（如 `admet_threshold` 0-100）
4. 校验失败时返回明确错误，不执行工具

#### 3.4 添加感知缓存

**文件**：`backend/services/agent/perception.py`

**当前**：每次 `plan()` 都重新查询完整环境状态。

**改进**：添加 `perception_cache`（TTL=10秒），同一project_id的环境状态在短时间内复用。

#### 3.5 数据库连接池优化

**文件**：`backend/services/agent/tools.py`

**当前**：每次工具调用都 `init_db()` + `Session()`。

**改进**：使用上下文管理器 `get_db()` 或引入 `SessionLocal` 连接池。

#### 3.6 修改文件

- `backend/services/agent/executor.py`
- `backend/services/agent/memory.py`
- `backend/services/agent/tools.py`
- `backend/services/agent/perception.py`

#### 3.7 验收标准

- [ ] 条件"如果ADMET>80就继续"在ADMET=65时正确判断为false
- [ ] 超token时保留项目创建、靶点设定等关键信息
- [ ] LLM编造不存在参数时，工具执行前拦截并返回错误
- [ ] 同一project_id 10秒内重复查询时，使用缓存

---

### 阶段4：规划器增强（让Agent"更聪明"）

**目标**：提升任务规划质量，支持更复杂的任务结构。

#### 4.1 改进规划器Prompt

**文件**：`backend/services/agent/prompts/planner_system.yaml`

**改进内容**：
1. 明确列出**所有可用工具**（更新为22+个）
2. 为每个工具提供**参数schema**（类型、必填、默认值）
3. 添加**参数校验规则**：LLM生成参数时检查必填项
4. 添加**执行策略示例**：
   - 简单任务：单步执行
   - 复杂任务：多步串行
   - 分析任务：先获取数据，再分析，再建议
   - 条件任务：生成条件步骤
5. 添加**失败处理策略**：如果某步失败，如何降级或重试

#### 4.2 支持循环迭代

**当前**：计划是一维步骤列表，不支持循环。

**改进**：当用户说"优化直到ADMET>80"时，规划器生成循环结构：
```json
{
  "steps": [
    {"tool": "get_top_molecules", "params": {"project_id": "X"}},
    {"tool": "analyze_failures", "params": {"project_id": "X"}},
    {"condition": "admet_score < 80", "steps": [
      {"tool": "adjust_filters", "params": {"admet_threshold": 70}},
      {"tool": "run_pipeline", "params": {"project_id": "X"}}
    ], "max_iterations": 3}
  ]
}
```

#### 4.3 添加工具参数校验层

**文件**：`backend/services/agent/planner.py`

在 `plan()` 返回前，对生成的步骤进行**参数校验**：
1. 检查工具名是否存在于 `ToolRegistry`
2. 检查必填参数是否都存在
3. 检查参数类型是否正确
4. 参数校验失败时，请求LLM重新生成

#### 4.4 修改文件

- `backend/services/agent/prompts/planner_system.yaml`
- `backend/services/agent/prompts/planner_user.yaml`
- `backend/services/agent/planner.py`

#### 4.5 验收标准

- [ ] Prompt中列出的工具名与实际 `tools.py` 注册的工具名完全一致
- [ ] 用户说"帮我优化直到ADMET>80" → 规划器生成带条件的循环计划
- [ ] 规划器生成的计划如果参数缺失，自动触发重试
- [ ] 规划器不再引用不存在的工具

---

### 阶段5：用户体验优化（让Agent"更友好"）

**目标**：提升用户交互体验，让Agent的回答更专业、更实用。

#### 5.1 统一格式化输出

**文件**：`backend/services/agent/executor.py` + 新建 `backend/services/agent/formatters.py`

**当前问题**：`executor.py` 和 `tools.py` 中有大量重复的Markdown格式化逻辑。

**改进**：抽取统一格式化器：
- `MoleculeFormatter` — 分子卡片格式化
- `PipelineFormatter` — Pipeline结果格式化
- `AdmetFormatter` — ADMET报告格式化
- `ComparisonFormatter` — 分子对比格式化
- `SynthesisFormatter` — 合成路线格式化
- `DockingFormatter` — 对接结果格式化

#### 5.2 改进无法完成的反馈

**当前**：Agent尝试失败后返回错误。

**改进**：在 `engine.py` 中增加**预检查逻辑**：
1. 如果用户请求涉及不存在的服务/工具 → 明确告知"暂不支持，建议..."
2. 如果用户请求缺少必要信息 → 询问补充信息
3. 如果用户请求超出系统能力 → 告知限制并给出替代方案

示例：
- 用户："帮我做一个动物实验" → Agent："目前系统支持计算层面的药物设计（分子生成、ADMET预测、对接打分等），动物实验属于湿实验验证，暂无法通过本平台完成。建议：1. 先通过本平台筛选出Top候选分子；2. 联系CRO进行体外/体内验证。"

#### 5.3 添加执行追踪增强

**文件**：`frontend/src/components/AgentTracePanel.jsx` + `backend/services/agent/tracer.py`

**改进**：
1. 追踪面板显示每个步骤的**详细耗时**和**Token用量**
2. 追踪面板支持**步骤展开/折叠**
3. 追踪面板显示**LLM原始思考过程**（thought）
4. 追踪面板支持**导出为Markdown报告**

#### 5.4 修改文件

- 新建 `backend/services/agent/formatters.py`
- `backend/services/agent/executor.py`
- `backend/services/agent/engine.py`
- `backend/services/agent/tracer.py`
- `frontend/src/components/AgentTracePanel.jsx`

#### 5.5 验收标准

- [ ] 所有格式化逻辑集中到 `formatters.py`
- [ ] 用户请求不存在的功能时，Agent给出明确的"暂不支持"+替代方案
- [ ] 追踪面板显示每个步骤的耗时和Token用量
- [ ] 追踪面板支持导出Markdown报告

---

## 五、执行顺序与依赖关系

```
阶段1：工具补全 ───────────────────────┐
  （必须最先完成，后续阶段依赖）       │
                                      │ 可以并行
阶段2：意图解析增强 ───────────────────┤
  （与阶段1无强依赖，但工具多了后     │
   意图检测也要覆盖新工具）            │
                                      │
阶段3：执行引擎增强 ───────────────────┤
  （依赖阶段1完成，因为工具参数校验    │
   需要知道所有工具的schema）          │
                                      │
阶段4：规划器增强 ─────────────────────┤
  （依赖阶段1+3，因为Prompt要列出      │
   所有工具，且参数校验需要schema）     │
                                      │
阶段5：用户体验优化 ───────────────────┘
  （依赖前面所有阶段，最后做美化）
```

**推荐执行顺序**：1 → 2 → 3 → 4 → 5（串行），其中阶段1和2可以并行。

---

## 六、验收测试用例（每个阶段完成后必须验证）

### 阶段1验收测试

| # | 测试输入 | 期望行为 |
|---|---------|---------|
| 1.1 | "帮我查一下EGFR靶点" | 调用 `search_targets`，返回靶点信息列表 |
| 1.2 | "EGFR有什么已知药物" | 调用 `get_target_info`，返回靶点描述+活性分子 |
| 1.3 | "对接一下CCO和AKT1" | 调用 `run_docking`，返回结合能 |
| 1.4 | "分析CCO的合成路线" | 调用 `analyze_synthesis`，返回路线+步数+成本 |
| 1.5 | "预测这个分子对HER2的活性" | 调用 `predict_activity`，返回pIC50+置信度 |
| 1.6 | "获取CCO的3D结构" | 调用 `get_3d_structure`，返回SDF/PDB |

### 阶段2验收测试

| # | 测试输入 | 期望行为 |
|---|---------|---------|
| 2.1 | "分析一下" | 识别为 `CLARIFICATION_NEEDED`，询问分析对象 |
| 2.2 | "ATP的合成路线" | 不将"ATP"误判为SMILES |
| 2.3 | "项目None的结果" | 不将"None"当作有效project_id，询问具体项目 |
| 2.4 | "帮我查一下EGFR" | 意图识别为 `SINGLE_ACTION`，工具 `search_targets` |

### 阶段3验收测试

| # | 测试输入 | 期望行为 |
|---|---------|---------|
| 3.1 | "如果ADMET>80就继续优化" | 条件评估正确，ADMET=65时返回false |
| 3.2 | 长对话后问"AKT1项目怎么样了" | 能记住AKT1项目，因为关键信息被保留 |
| 3.3 | LLM编造参数 `"project_idd": 1` | 参数校验拦截，返回参数错误 |
| 3.4 | 连续快速查询同一项目 | 10秒内使用缓存，不重复查数据库 |

### 阶段4验收测试

| # | 测试输入 | 期望行为 |
|---|---------|---------|
| 4.1 | "优化直到ADMET>80" | 生成带循环的计划，最多3次迭代 |
| 4.2 | "帮我做一个不存在的任务" | 规划器不引用不存在工具，返回降级计划 |
| 4.3 | 规划缺少必填参数 | 自动触发重试，补齐参数 |

### 阶段5验收测试

| # | 测试输入 | 期望行为 |
|---|---------|---------|
| 5.1 | "帮我做动物实验" | 明确告知"暂不支持"+替代方案（先计算筛选） |
| 5.2 | "给我一份完整的报告" | 格式化输出专业报告，包含所有关键信息 |
| 5.3 | 追踪面板 | 显示每步耗时、Token、LLM思考过程 |

---

## 七、风险与回退方案

| 风险 | 影响 | 回退方案 |
|------|------|----------|
| 新增工具引入Bug | 影响现有功能 | 每个工具独立开发，通过 `try/except` 包裹，失败时返回graceful error |
| 参数校验太严格 | LLM合法参数被拦截 | 参数校验先添加为警告模式（记录但不拦截），观察一段时间后再启用拦截 |
| Prompt修改导致LLM输出不稳定 | 计划格式变化 | 保留原有 `_fallback_plan` 机制，LLM输出不符合schema时回退到默认计划 |
| 记忆摘要增加LLM调用次数 | 成本增加 | 摘要仅在超token时触发，且使用缓存降低重复调用 |
| 缓存导致数据不一致 | 看到旧数据 | 缓存TTL仅10秒，且关键操作（写操作）自动清空缓存 |

---

## 八、文件修改清单（最终）

### 新建文件

| 文件 | 说明 |
|------|------|
| `backend/services/agent/formatters.py` | 统一格式化器 |
| `backend/services/agent/prompts/intent_parser.yaml` | 意图解析器提示词模板 |
| `backend/services/agent/prompts/executor.yaml` | 执行器提示词模板 |

### 修改文件（按阶段）

**阶段1**：
- `backend/services/agent/tools.py` — 新增7个工具 + 增强现有工具
- `backend/services/agent/intent_parser.py` — 为新工具添加检测关键词

**阶段2**：
- `backend/services/agent/intent_parser.py` — 修复Bug + 增强检测
- `backend/services/agent/planner.py` — 修复logger + 更新工具描述
- `backend/services/agent/prompts/planner_system.yaml` — 删除幻觉工具引用

**阶段3**：
- `backend/services/agent/executor.py` — 条件评估 + 执行逻辑增强
- `backend/services/agent/memory.py` — 智能摘要替代截断
- `backend/services/agent/tools.py` — 参数schema校验
- `backend/services/agent/perception.py` — 添加缓存

**阶段4**：
- `backend/services/agent/prompts/planner_system.yaml` — 全面重写
- `backend/services/agent/prompts/planner_user.yaml` — 增强
- `backend/services/agent/planner.py` — 参数校验 + 循环支持

**阶段5**：
- `backend/services/agent/executor.py` — 使用formatters
- `backend/services/agent/engine.py` — 预检查逻辑
- `backend/services/agent/tracer.py` — 增强追踪
- `frontend/src/components/AgentTracePanel.jsx` — 增强前端面板

---

## 九、执行后效果预期

### 优化前（现状）

```
用户：帮我查一下EGFR靶点
Agent：抱歉，我没有找到合适的工具来执行这个任务。

用户：对接一下这个分子
Agent：（只能跑完整Pipeline，耗时10分钟，结果不一定包含对接）

用户：分析一下失败原因
Agent：（如果上下文丢失project_id，直接报错）

用户：如果ADMET>80就继续
Agent：（条件判断可能出错，导致错误执行）
```

### 优化后（预期）

```
用户：帮我查一下EGFR靶点
Agent：EGFR（表皮生长因子受体）是... 已知药物有：吉非替尼（SMILES: ...）、厄洛替尼... 推荐PDB ID: 1M17。

用户：对接一下CCO和AKT1（4EKL）
Agent：正在执行分子对接... 对接完成！最佳结合能：-6.8 kcal/mol，结合模式：氢键... 建议：结合力较弱，可优化结构。

用户：分析一下失败原因
Agent：当前项目（AKT1_auto_0628）共失败1000个分子。主要失败阶段：
- 基础过滤：200个（MW>550或LogP>5）
- ADMET：500个（overall_score<60）
- 合成：300个（availability_score<0.35）
建议：降低ADMET阈值到50或增加生成分子数到2000。

用户：如果ADMET>80就继续优化
Agent：（正确判断ADMET=65<80，跳过优化步骤，报告当前状态）
```

---

*计划编写完成。本计划必须在执行前被确认，确认后严格按照阶段顺序执行，每个阶段完成后必须运行验收测试用例。*
