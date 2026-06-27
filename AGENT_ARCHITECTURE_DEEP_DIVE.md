# AI Agent 底层架构全解析

> 本文档深度解析 DrugDesign Copilot Agent 的底层实现，包括：从用户输入到输出的完整链路、技术栈、自动化边界、以及未来优化路径。

---

## 一、整体架构概览

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              用户（前端/聊天界面）                           │
└──────────────────────────────┬──────────────────────────────────────────────┘
                               │ HTTP POST /chat
                               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  CopilotAgent.chat()                                                        │
│  ├── 自动推断 project_id（显式传入 > session 记忆 > 实例记忆）                 │
│  ├── 保存用户消息到 Buffer Memory                                            │
│  ├── 调用 ReActEngine.run()                                                  │
│  └── 保存助手回复 + 更新实例记忆                                             │
└──────────────────────────────┬──────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  ReActEngine.run() — 主执行引擎（核心决策流程）                              │
│  │                                                                           │
│  ├─ 1. 意图解析（IntentParser）                                             │
│  │   ├── _quick_detect：关键词快速匹配（低成本）                              │
│  │   ├── 实体提取：project_id / target / SMILES / 属性名                    │
│  │   └── LLM 深度解析：复杂/模糊输入的意图理解                                │
│  │                                                                           │
│  ├─ 2. 判断是否需要澄清（needs_clarification）                               │
│  │   ├── 置信度 < 0.6 → 缺少参数 → 返回澄清问题                              │
│  │   └── 上下文有 project_id → 跳过澄清                                       │
│  │                                                                           │
│  ├─ 3. 判断是否为简单聊天（simple_chat）                                    │
│  │   └── 是 → 直接返回聊天响应（不走后续流程）                                │
│  │                                                                           │
│  ├─ 4. 判断是否需要表单（needs_form）                                        │
│  │   └── 是 → 返回表单/澄清（不执行工具）                                    │
│  │                                                                           │
│  ├─ 5. 多意图处理（multi_intent）                                           │
│  │   └── 拆分多个子意图 → 并行/串行执行                                       │
│  │                                                                           │
│  └─ 6. 目标导向执行（goal_oriented） ← 核心执行链路                         │
│      ├── Perceive：环境感知（项目状态、Pipeline 状态、分子数据）             │
│      ├── Plan：LLM 规划（将目标拆解为可执行步骤）                            │
│      ├── Execute：逐步骤执行（工具调用 + 自适应决策）                         │
│      └── Report：生成最终回答（格式化执行结果）                               │
└──────────────────────────────┬──────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  结果 → 返回给 CopilotAgent → 保存到 Memory → 返回给前端                     │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 二、核心模块深度解析

### 2.1 意图解析层（IntentParser）

**位置**：`intent_parser.py`

**三层解析策略**（从快到慢，成本递增）：

```
用户输入 "帮我分析项目 35 的失败分子"
    │
    ├─ Stage 1: _quick_detect（本地关键词匹配，0 成本）
    │   ├── 检查 "失败分子/失败原因/分析失败" → 匹配 COMPLEX_ANALYSIS
    │   ├── 检查 "再优化/分析结果/下一步" → 匹配 FOLLOW_UP（上下文有 project_id 时）
    │   └── 检查 "你好/谢谢/在吗" → 匹配 SIMPLE_CHAT
    │
    ├─ Stage 2: 实体提取（正则 + 字典）
    │   ├── 数字匹配 → project_id = 35
    │   ├── 靶点字典匹配 → target = EGFR/BRAF/...
    │   └── SMILES 正则匹配 → SMILES = CC(=O)Oc1ccccc1C(=O)O
    │
    └─ Stage 3: LLM 深度解析（高成本，仅前两级不确定时触发）
        ├── LLM 分析用户输入的语义
        ├── 返回意图类型 + 置信度 + 实体列表
        └── 判断是否需要澄清
```

**关键设计**：
- 先快后慢：80% 的常见意图用关键词匹配（0 LLM 成本），只有模糊的才调用 LLM
- 上下文感知：`_quick_detect` 会检查 `context["project_id"]`，有上下文时"帮我分析" → 直接执行，不是澄清
- 实体提取：独立于 LLM 的正则提取，即使 LLM 不触发也能获取关键参数

**数据流**：
```python
ParsedIntent(
    primary_type=IntentType.COMPLEX_ANALYSIS,  # 意图类型
    confidence=0.9,                            # 置信度
    entities=[                                   # 提取的实体
        ExtractedEntity(type="project_id", value="35", confidence=0.95),
    ],
    detected_actions=["analyze_failures", "get_project_status"],  # 检测到的动作
    suggested_tools=["analyze_failures", "get_project_status"],   # 建议工具
    needs_clarification=False,                   # 是否需要澄清
    estimated_complexity=3,                      # 预估复杂度 1-5
)
```

---

### 2.2 规划层（TaskPlanner）

**位置**：`planner.py`

**核心逻辑**：将用户目标 + 环境状态 → 拆解为可执行的步骤序列

```
输入：
  - goal: "分析失败分子原因"
  - project_id: 35
  - env_state: {项目状态、Pipeline 状态、失败分子列表、ADMET 统计...}
  - available_tools: [create_project, run_pipeline, analyze_failures, ...]
  - intent_context: {意图类型: COMPLEX_ANALYSIS, 检测到的动作: [analyze_failures], ...}

输出：
  {
    "steps": [
      {
        "tool": "analyze_failures",
        "params": {"project_id": 35},
        "reason": "分析项目中失败的分子的原因",
        "expected_outcome": "得到失败分子的分类和失败原因",
        "condition": null
      },
      {
        "tool": "suggest_next_step",
        "params": {"project_id": 35},
        "reason": "基于失败分析给出优化建议",
        "expected_outcome": "得到优化建议",
        "condition": null
      }
    ],
    "summary": "分析失败分子原因并提供优化建议"
  }
```

**Prompt 设计（关键）**：
- 系统提示：包含 9 种规划策略（单一操作、多意图、复杂分析、条件、对比、优化、follow_up、探索、靶点直通）
- 意图上下文注入：将 `intent_context` 中的 `detected_actions`、`suggested_tools` 显式传递给 LLM
- 强制 JSON 输出：要求 LLM 返回纯 JSON，不输出 Markdown 代码块

**关键优化**：`intent_context` 的 `detected_actions` 字段，让 Planner 知道意图解析器已经识别了哪些动作，避免过度保守的"先获取状态再执行"策略。

---

### 2.3 执行层（TaskExecutor）

**位置**：`executor.py`

**核心流程**：遍历计划步骤，执行 + 自适应决策

```python
for step in plan_steps:
    # 1. 条件评估
    if step.condition and not evaluate_condition(step.condition):
        continue  # 跳过此步骤
    
    # 2. 执行工具
    result = tool_registry.execute(step.tool, step.params)
    
    # 3. 记录执行结果
    execution_log.add_step(tool, params, result, status)
    
    # 4. 自适应决策（简单工具跳过 LLM，复杂工具/失败时调用 LLM）
    if step.tool in SIMPLE_TOOLS:
        decision = "continue"  # 直接继续，不浪费 LLM
    else:
        decision = llm_decide(execution_history, result, goal)
        # decision 可能是: continue / modify / finish / error
    
    # 5. 根据决策调整下一步
    if decision == "finish":
        break
    elif decision == "modify":
        # LLM 生成新步骤
        new_steps = llm_generate_new_steps()
        plan_steps.extend(new_steps)
```

**关键设计**：
- **SIMPLE_TOOLS 集合**：`get_project_status`、`list_projects`、`get_top_molecules` 等 7 个工具跳过 LLM 决策，直接 `continue`，减少 LLM 调用次数
- **执行历史压缩**：超过 5 步时，早期步骤压缩为摘要，只保留最近 3 步完整信息，避免超出 LLM 上下文窗口
- **特殊处理**：`wait_for_pipeline` 使用 `ThreadPoolExecutor` + 10 秒超时，避免阻塞主线程
- **条件执行**：支持条件步骤（如"如果 ADMET 分数 < 3 则调整过滤"），支持简单数值比较和 LLM 评估

---

### 2.4 工具层（ToolRegistry）

**位置**：`tools.py`

**12 个已注册工具**：

| 工具 | 功能 | 参数 |
|------|------|------|
| `create_project` | 创建项目（从靶点数据库获取已知活性分子） | `target_name`, `name` |
| `list_projects` | 列出所有项目 | 无 |
| `run_pipeline` | 启动 Pipeline（8 阶段分子生成） | `project_id` |
| `analyze_failures` | 分析失败分子的原因和分类 | `project_id` |
| `adjust_filters` | 调整 Pipeline 过滤参数 | `project_id`, `admet_threshold`, `docking_threshold` |
| `get_project_status` | 获取项目整体状态 | `project_id` |
| `compare_molecules` | 对比多个分子的 ADMET 属性 | `project_id`, `molecule_ids` |
| `suggest_next_step` | 基于项目状态给出建议 | `project_id` |
| `get_failed_molecules` | 获取失败分子列表 | `project_id`, `stage` |
| `get_top_molecules` | 获取排名 Top 的分子 | `project_id`, `limit` |
| `get_pipeline_progress` | 获取 Pipeline 实时进度 | `project_id` |
| `wait_for_pipeline` | 等待 Pipeline 完成 | `project_id`, `max_wait` |

**工具注册方式**（装饰器）：
```python
@register_tool(
    name="analyze_failures",
    description="分析项目中失败的分子的原因...",
    parameters={"project_id": "integer"}
)
def analyze_failures(project_id: int, stage: str = None) -> Dict:
    # 查询数据库中 failed 状态的分子
    # 按失败阶段分类统计
    # 返回失败原因摘要
    ...
```

**工具执行流程**：
```
ToolRegistry.execute("analyze_failures", {"project_id": 35})
    ├── 查找工具函数 → analyze_failures
    ├── 参数校验 → project_id 必填
    ├── 创建独立数据库 session
    ├── 执行工具逻辑
    ├── 保存项目记忆（save_project_memory）
    └── 返回 {"success": True, "failed_by_stage": {...}, "total_failed": 10}
```

---

### 2.5 记忆系统（Memory）

**位置**：`memory.py`

**三层记忆架构**：

```
┌──────────────────────────────────────────────────────────┐
│  Buffer Memory（短期记忆）                                │
│  ├── 对话历史（user/assistant 交替）                       │
│  ├── Token 预算管理（超预算保留最近 5 条）                │
│  └── 用于：多轮对话上下文保持                             │
└──────────────────────────────────────────────────────────┘
                              │
┌──────────────────────────────────────────────────────────┐
│  Project Memory（项目记忆）                                 │
│  ├── 事件记录（Pipeline 启动/完成/失败）                  │
│  ├── 洞察（失败分析、ADMET 趋势）                         │
│  ├── 决策（参数调整、优化策略）                           │
│  └── 用于：跨轮次项目状态跟踪                             │
└──────────────────────────────────────────────────────────┘
                              │
┌──────────────────────────────────────────────────────────┐
│  Long-term Memory（长期记忆）                               │
│  ├── 跨项目通用知识（靶点特性、分子设计经验）              │
│  ├── 使用计数（高频查询优先）                             │
│  └── 用于：全局知识积累                                   │
└──────────────────────────────────────────────────────────┘
```

**关键功能**：
- `get_session_project_id()`：从数据库读取 session 关联的 project_id，实现上下文记忆
- `update_session_project_id()`：当用户创建项目或显式指定项目时，更新 session 关联
- `save_project_memory()`：工具执行后自动保存结果，用于后续分析

---

### 2.6 环境感知（Perception）

**位置**：`perception.py`

**职责**：收集项目的完整环境状态，注入到 Planner 的提示词中

**收集的信息**：
1. 项目概况（名称、靶点、状态）
2. Pipeline 状态（运行中/完成/失败、进度）
3. 失败分析（失败分子数量、失败阶段分布）
4. 智能建议（基于当前状态的下一步建议）
5. 分子详情（Top 分子、属性、ADMET 分数）
6. ADMET 统计（各阶段通过/失败数量）

**数据流**：
```
EnvironmentPerception.get_state(project_id=35)
    ├── 调用 ToolRegistry.execute("get_project_status", ...)
    ├── 调用 ToolRegistry.execute("get_top_molecules", ...)
    ├── 查询数据库获取 ADMET 统计
    ├── 查询数据库获取失败分子列表
    └── 返回结构化字典

EnvironmentPerception.format_for_llm(state)
    └── 将字典转为纯文本报告，直接注入 LLM 提示词
```

---

### 2.7 LLM 客户端（LLMClient）

**位置**：`llm_client.py`

**统一封装了所有 LLM 调用**：

```python
class LLMClient:
    def call(messages, temperature=0.7)        → 基础调用（无重试）
    def retry_call(messages, max_retries=3)    → 带指数退避重试
    def cached_call(messages, cache_ttl=60)    → 带缓存（60秒 TTL）
    def stream_call(messages)                    → 流式输出（预留）
```

**关键设计**：
- **连接池**：使用 `requests.Session`，连接复用，减少新建连接失败概率
- **指数退避重试**：429/500/502/503/SSL/连接/超时 自动重试，延迟 1s → 2s → 4s
- **响应缓存**：相同 prompt + model + temperature 在 60s 内复用响应
- **指标监控**：调用次数、token 消耗、延迟、缓存命中、错误率
- **全局单例**：`get_default_client()` 确保所有模块复用同一个客户端实例

---

### 2.8 配置中心（Config）

**位置**：`config.py`

**集中管理所有配置**：

| 类别 | 配置项 | 默认值 |
|------|--------|--------|
| LLM API | `KIMI_API_KEY` | 环境变量 `KIMI_API_KEY` |
| | `DEFAULT_MODEL` | `moonshot-v1-8k` |
| | `KIMI_API_URL` | `https://api.moonshot.cn/v1/chat/completions` |
| Agent 行为 | `MAX_STEPS` | 10 |
| | `DEFAULT_TEMPERATURE` | 0.3 |
| LLM 客户端 | `LLM_TIMEOUT` | 60s |
| | `LLM_RATE_LIMIT_INTERVAL` | 1.0s |
| | `LLM_CACHE_TTL` | 60s |
| 执行 | `STEP_TIMEOUT` | 120s |
| | `MAX_RETRIES` | 3 |
| Pipeline | `MAX_PIPELINE_WAIT` | 300s |
| | `PIPELINE_POLL_INTERVAL` | 5s |
| 记忆 | `CONVERSATION_HISTORY_LIMIT` | 20 |
| | `MAX_CONVERSATION_TOKENS` | 4000 |

---

## 三、技术栈全览

| 层次 | 技术/框架 | 用途 |
|------|-----------|------|
| **后端框架** | Flask | HTTP API 服务 |
| **数据库** | SQLAlchemy + SQLite/PostgreSQL | ORM + 数据库操作 |
| **AI 模型** | Kimi (Moonshot) API | LLM 推理（意图解析、规划、决策、生成） |
| **架构模式** | ReAct (Reasoning + Acting) | 思考-行动-观察循环 |
| **并发** | threading + ThreadPoolExecutor | 后台 Pipeline 执行、并行等待 |
| **HTTP 客户端** | requests + Session 连接池 | LLM API 调用 |
| **配置管理** | pydantic-style dataclass + 环境变量 | 集中配置 |
| **缓存** | 内存缓存（Dict + MD5 哈希键） | LLM 响应缓存 |
| **监控** | 自定义 metrics 统计 | 调用次数、延迟、错误率、token 消耗 |
| **分子处理** | RDKit（通过工具层调用） | SMILES 验证、规范化、分子属性 |
| **靶点数据** | 内置靶点数据库（JSON） | 已知靶点名称、ID、已知活性分子 |

---

## 四、能否保证全自动化？

### 4.1 当前已经全自动化的场景 ✅

| 场景 | 自动化程度 | 说明 |
|------|-----------|------|
| 创建项目 → 运行 Pipeline | 100% | 用户提供靶点名称，Agent 自动创建项目并运行 Pipeline |
| 查看项目状态 | 100% | 自动获取项目状态、Pipeline 进度、分子统计 |
| 获取 Top 分子 | 100% | 自动查询并排序，返回最佳候选分子 |
| 分析失败分子 | 100% | 自动查询失败分子，按阶段分类，统计失败原因 |
| 对比分子 | 100% | 自动获取多个分子的 ADMET 属性，生成对比报告 |
| 多意图并行 | 100% | 如"查看项目A状态并对比项目B"，自动拆分并行执行 |
| 上下文记忆 | 100% | 连续对话中自动保持 project_id，不需要重复提供 |
| 条件执行 | 90% | 支持条件步骤（如"如果 ADMET 分数<3 则调整"），条件判断可自动完成 |

### 4.2 当前部分自动化、需要人工确认的场景 ⚠️

| 场景 | 自动化程度 | 需要人工确认的原因 |
|------|-----------|-------------------|
| 调整过滤参数 | 70% | Agent 可以建议参数调整，但涉及专业判断（如阈值的医学意义） |
| 分子优化建议 | 60% | Agent 可以给出建议，但最终的合成决策需要化学家确认 |
| 专利新颖性 | 50% | PubChem 查询自动化，但专利解读需要专业知识 |
| 合成路线评估 | 60% | 可以初步评估，但复杂合成路线需要人工审核 |
| 药物最终选择 | 30% | 候选分子排名自动化，但最终成药决策涉及大量临床前/临床因素 |

### 4.3 当前无法全自动化的场景 ❌

| 场景 | 原因 | 未来可能的突破 |
|------|------|--------------|
| 全新靶点（无已知结构） | 需要先进行结构生物学实验（冷冻电镜/X射线） | 结合 AlphaFold 预测结构 |
| 实验验证（合成/活性测试） | 需要物理实验，AI 无法替代 | 结合自动化实验室（如机器人合成平台） |
| 临床前/临床实验 | 需要动物/人体实验，受法规监管 | 无法完全自动化，但可辅助设计实验方案 |
| 知识产权决策 | 涉及法律和商业判断 | 可辅助检索和分析，但决策需律师确认 |
| 跨领域知识整合 | 如"这个靶点与某种疾病的关联" | 需要更强大的知识图谱和多模态理解 |

### 4.4 自动化的瓶颈分析

```
全自动化药物设计链路：

靶点发现 → 结构获取 → 分子生成 → 虚拟筛选 → ADMET 评估 → 合成评估 → 实验验证 → 临床前 → 临床
  │          │          │          │           │           │          │         │
  │          │          ✅         ✅          ✅          ⚠️        ❌       ❌
  │          │        (已自动)  (已自动)   (已自动)    (部分)    (无法)   (无法)
  │          │
  │          │  结构生物学实验（AlphaFold 可部分替代）
  │          │
  │  疾病关联研究（AI 可辅助文献挖掘）
  │
  全新靶点发现（需要生物学家判断）
```

**结论**：
- **分子设计阶段（生成→筛选→评估）**：80% 以上可以自动化
- **实验验证阶段**：当前无法自动化，但 Agent 可以辅助设计实验方案
- **最终决策阶段**：需要人机协作，Agent 提供数据支持，人类做最终判断

---

## 五、当前架构的优势

### 5.1 分层解耦

```
用户接口层（CopilotAgent）
    ↓ 调用
决策层（ReActEngine）
    ↓ 调用
解析层（IntentParser）    ← 可独立替换
    ↓ 调用
规划层（TaskPlanner）    ← 可独立替换
    ↓ 调用
执行层（TaskExecutor）   ← 可独立替换
    ↓ 调用
工具层（ToolRegistry）    ← 可扩展新工具
    ↓ 调用
业务层（Pipeline/Database）← 与 AI 逻辑解耦
```

**好处**：任何一层可以独立升级或替换，不影响其他层。

### 5.2 混合策略（规则 + LLM）

- **规则兜底**：80% 的常见意图用关键词匹配（0 成本、0 延迟）
- **LLM 增强**：复杂模糊输入用 LLM 理解（准确但成本高）
- **缓存优化**：常见意图的 LLM 响应缓存 60s，减少重复调用

### 5.3 上下文感知

- **会话记忆**：自动保持 project_id，连续对话无需重复提供
- **项目记忆**：跨轮次跟踪项目状态，支持"分析失败→优化→再运行→对比"的完整流程
- **环境感知**：Planner 决策前自动获取项目状态，做出基于当前状态的决策

### 5.4 自适应执行

- **简单工具跳过 LLM**：`get_project_status`、`list_projects` 等直接执行，不浪费 LLM 调用
- **复杂工具 LLM 决策**：执行失败或结果不确定时，LLM 自适应调整计划
- **执行历史压缩**：长对话不超出 LLM 上下文窗口

---

## 六、未来优化路径：让 Agent 更出色

### 6.1 意图理解增强（让 Agent "更懂"用户）

#### 6.1.1 引入意图 Few-Shot 示例库

**当前问题**：LLM 意图解析依赖通用能力，对药物设计专业术语理解不够精准

**优化方案**：
```python
# 在 IntentParser 的 LLM Prompt 中增加 few-shot 示例
INTENT_FEW_SHOT_EXAMPLES = [
    {
        "input": "帮我分析项目 35 的失败分子",
        "output": {
            "intent_type": "complex_analysis",
            "detected_actions": ["analyze_failures"],
            "entities": [{"type": "project_id", "value": "35"}]
        }
    },
    {
        "input": "EGFR 的 Pipeline 跑得怎么样了",
        "output": {
            "intent_type": "follow_up",
            "detected_actions": ["get_project_status"],
            "entities": [{"type": "target", "value": "EGFR"}]
        }
    },
    # 更多专业场景示例...
]
```

#### 6.1.2 引入用户画像和偏好记忆

**当前**：Agent 只记住 project_id，不知道用户的偏好

**优化**：
```python
# 长期记忆新增：用户偏好
user_preferences = {
    "favorite_targets": ["EGFR", "BRAF"],      # 常用靶点
    "default_admet_threshold": 3.0,              # 默认 ADMET 阈值
    "preferred_output_format": "table",          # 偏好表格输出
    "expertise_level": "expert",                 # 专家/新手，影响解释深度
    "last_used_project_id": 35,                  # 最后使用的项目
}
```

**效果**：用户说"再运行一下"，Agent 知道"用我上次用的参数"；用户说"分析"，Agent 知道"用我偏好的详细程度"。

#### 6.1.3 引入多轮对话意图追踪

**当前**：每轮独立解析意图，不考虑对话历史中的意图变化

**优化**：
```python
class ConversationTracker:
    """追踪对话中的意图演变"""
    
    def track_intent_evolution(self, current_intent, history):
        # 上一轮：用户说 "分析失败分子"
        # 当前轮：用户说 "那怎么优化"
        # → 当前意图应继承上一轮的 project_id，且类型为 "optimization"
        
        if current_intent.primary_type == IntentType.FOLLOW_UP:
            # 从上一轮获取上下文
            last_intent = history[-1].intent
            if "失败" in last_intent.keywords:
                current_intent.inferred_goal = "基于失败分析优化"
                current_intent.suggested_tools = ["adjust_filters", "run_pipeline"]
```

#### 6.1.4 引入否定和修正意图理解

**当前**：用户说"不是这个意思"，Agent 无法识别是否定

**优化**：
```python
negation_patterns = [
    "不是", "不对", "错了", "换一个", "重新", "不是这个",
    "我说的不是", "你理解错了", "不是分析失败",
]

# 当检测到否定，回退到上一轮意图，重新解析
if any(p in message for p in negation_patterns):
    return ParsedIntent(
        primary_type=IntentType.CORRECTION,
        correction_target=history[-1].intent,  # 要修正的上一轮意图
        # 重新解析用户的真正意图
    )
```

---

### 6.2 规划能力增强（让 Agent "更会规划"）

#### 6.2.1 引入计划模板库

**当前**：Planner 每次从零生成计划，对于常见任务（如"靶点直通"）应该复用标准模板

**优化**：
```python
PLAN_TEMPLATES = {
    "target_to_molecules": [
        {"tool": "create_project", "params": {"target_name": "{target}"}},
        {"tool": "run_pipeline", "params": {"project_id": "{project_id}"}},
        {"tool": "wait_for_pipeline", "params": {"project_id": "{project_id}"}},
        {"tool": "get_top_molecules", "params": {"project_id": "{project_id}", "limit": 5}},
    ],
    "optimize_after_failure": [
        {"tool": "analyze_failures", "params": {"project_id": "{project_id}"}},
        {"tool": "suggest_next_step", "params": {"project_id": "{project_id}"}},
        {"tool": "adjust_filters", "params": {"project_id": "{project_id}"}},
        {"tool": "run_pipeline", "params": {"project_id": "{project_id}"}},
    ],
}

# 当意图匹配模板时，直接填充模板，减少 LLM 调用
template = PLAN_TEMPLATES.get(intent.template_key)
if template:
    plan = fill_template(template, entities)  # 0 成本
else:
    plan = llm_plan(goal, ...)  # 高成本
```

#### 6.2.2 引入计划执行的成功率预测

**当前**：Planner 生成计划，但不评估计划的成功概率

**优化**：
```python
class PlanEvaluator:
    """评估计划的可行性"""
    
    def evaluate(self, plan, env_state):
        success_factors = []
        
        for step in plan.steps:
            if step.tool == "run_pipeline":
                # 检查是否有足够的参考分子
                if env_state.get("reference_molecules", 0) < 5:
                    success_factors.append({
                        "step": step,
                        "risk": "high",
                        "reason": "参考分子不足，Pipeline 可能生成质量低",
                        "suggestion": "先添加更多参考分子或使用不同的靶点",
                    })
            
            if step.tool == "analyze_failures":
                if env_state.get("failed_molecules", 0) == 0:
                    success_factors.append({
                        "step": step,
                        "risk": "high",
                        "reason": "没有失败分子，分析无意义",
                        "suggestion": "先运行 Pipeline 生成失败分子",
                    })
        
        return {
            "overall_success_probability": calculate_probability(success_factors),
            "risks": success_factors,
        }
```

**效果**：Agent 在生成计划后，先评估可行性，如果风险高，主动提醒用户"建议先运行 Pipeline"，而不是盲目执行。

#### 6.2.3 引入动态计划调整（基于实时反馈）

**当前**：计划一旦生成，执行过程中不调整（除了 adaptive decision 的简单 continue/modify/finish）

**优化**：
```python
class DynamicPlanner:
    """执行过程中动态调整计划"""
    
    def adjust_plan(self, current_plan, execution_result, env_state):
        # 示例：如果 analyze_failures 发现 80% 失败在 ADMET 阶段
        # 原计划：analyze → suggest → adjust → run → wait → get_top
        # 调整：增加 "analyze_admet_sar" 步骤，深入分析结构-活性关系
        
        if execution_result.tool == "analyze_failures":
            failed_by_stage = execution_result.data.get("failed_by_stage", {})
            if failed_by_stage.get("admet", 0) / total > 0.8:
                # 插入新步骤：深入分析 ADMET
                current_plan.insert_next_step({
                    "tool": "analyze_admet_sar",
                    "reason": "ADMET 失败率过高，需要深入分析结构问题",
                })
        
        return current_plan
```

---

### 6.3 执行能力增强（让 Agent "更会执行"）

#### 6.3.1 引入工具执行的成功率预测

**当前**：工具执行失败后才处理，没有预执行风险评估

**优化**：
```python
# 执行前预检查
def pre_check(tool_name, params, env_state):
    if tool_name == "run_pipeline":
        # 检查是否已有运行中的 Pipeline
        if env_state.get("pipeline_status") == "running":
            return {
                "can_execute": False,
                "reason": "已有 Pipeline 在运行中",
                "suggestion": "等待当前 Pipeline 完成或取消",
            }
    return {"can_execute": True}
```

#### 6.3.2 引入工具链依赖图

**当前**：工具之间的依赖关系隐含在代码中，不直观

**优化**：
```python
TOOL_DEPENDENCIES = {
    "analyze_failures": {
        "requires": ["run_pipeline"],  # 需要先运行 Pipeline 才有失败分子
        "provides": ["failure_analysis"],  # 提供失败分析数据
    },
    "run_pipeline": {
        "requires": ["create_project"],  # 需要先创建项目
        "provides": ["pipeline_job_id"],
    },
    "wait_for_pipeline": {
        "requires": ["run_pipeline"],
        "provides": ["pipeline_results"],
    },
}

# Planner 在生成计划时，自动检查依赖关系
```

#### 6.3.3 引入并行执行优化

**当前**：多意图并行最多 3 个，没有智能调度

**优化**：
```python
class ParallelScheduler:
    """智能调度并行执行"""
    
    def schedule(self, sub_plans):
        # 分析依赖关系
        dependency_graph = build_dependency_graph(sub_plans)
        
        # 找出无依赖的步骤，并行执行
        independent_steps = find_independent_steps(dependency_graph)
        
        # 有依赖的步骤，按拓扑排序串行执行
        dependent_steps = topological_sort(dependency_graph)
        
        return {
            "parallel_batches": independent_steps,  # 可以并行的批次
            "sequential_chain": dependent_steps,    # 必须串行的链
        }
```

---

### 6.4 记忆系统增强（让 Agent "更有记忆"）

#### 6.4.1 引入向量数据库（长期记忆检索）

**当前**：长期记忆用关键词搜索，召回率低

**优化**：
```python
# 引入向量数据库（如 ChromaDB、Pinecone）
from sentence_transformers import SentenceTransformer

class VectorMemory:
    def __init__(self):
        self.encoder = SentenceTransformer('all-MiniLM-L6-v2')
        self.vector_db = ChromaDB()  # 或 Pinecone
    
    def save(self, text, metadata):
        embedding = self.encoder.encode(text)
        self.vector_db.add(embedding, metadata)
    
    def search(self, query, top_k=5):
        query_embedding = self.encoder.encode(query)
        return self.vector_db.similarity_search(query_embedding, top_k)

# 使用场景：
# 用户问："上次那个 EGFR 项目用的什么参数？"
# 向量检索 → 找到历史 EGFR 项目的参数记录
```

#### 6.4.2 引入知识图谱（关系型记忆）

**当前**：记忆是扁平的，没有实体关系

**优化**：
```python
# 构建药物设计知识图谱
knowledge_graph = {
    "EGFR": {
        "type": "target",
        "known_inhibitors": ["Gefitinib", "Erlotinib", "Osimertinib"],
        "related_targets": ["HER2", "HER3"],
        "common_admet_issues": ["hERG 抑制", "肝毒性"],
        "successful_scaffolds": ["Quinazoline", "Pyrimidine"],
    },
    "ADMET_failure": {
        "type": "failure_pattern",
        "common_causes": ["LogP 过高", "分子量过大", "hERG 抑制"],
        "optimization_strategies": ["增加极性基团", "降低 LogP", "减少芳香环"],
    },
}

# 用户问："EGFR 项目失败了怎么办？"
# Agent 查询知识图谱：
# 1. EGFR 的常见失败模式 → ADMET 问题
# 2. ADMET 失败的常见原因 → LogP 过高
# 3. 优化策略 → 增加极性基团
# → 给出精准建议，而不是泛泛的 "suggest_next_step"
```

#### 6.4.3 引入跨项目经验迁移

**当前**：每个项目独立，不共享经验

**优化**：
```python
class ExperienceTransfer:
    """跨项目经验迁移"""
    
    def find_similar_projects(self, target, current_project_id):
        # 查询历史项目中，相同靶点的项目
        similar_projects = db.query(
            Project.target == target,
            Project.id != current_project_id,
        ).all()
        
        # 提取这些项目的成功经验
        successful_params = []
        for proj in similar_projects:
            if proj.status == "success":
                successful_params.append(proj.final_params)
        
        # 推荐参数
        if successful_params:
            best_params = consensus_params(successful_params)
            return {
                "recommendation": f"历史 {target} 项目成功参数：{best_params}",
                "source_projects": [p.id for p in similar_projects if p.status == "success"],
            }
        
        return None
```

**效果**：用户创建 EGFR 项目，Agent 自动推荐"历史上 EGFR 项目最成功的参数配置"。

---

### 6.5 输出质量增强（让 Agent "更会表达"）

#### 6.5.1 引入输出模板系统

**当前**：最终答案由 LLM 自由生成，格式不稳定

**优化**：
```python
OUTPUT_TEMPLATES = {
    "failure_analysis": """
## 失败分子分析报告

### 概况
- 项目：{project_name}
- 总生成分子：{total_generated}
- 失败分子：{total_failed} ({failure_rate}%)

### 失败分类
| 失败阶段 | 数量 | 占比 | 主要原因 |
|---------|------|------|----------|
{failure_table}

### 建议
{recommendations}

### 下一步
{next_steps}
""",
    "molecule_comparison": """
## 分子对比报告

| 分子 | MW | LogP | hERG | Solubility | 合成难度 |
|------|-----|------|------|------------|----------|
{comparison_table}

### 推荐
{best_choice}
""",
}
```

**效果**：输出格式稳定、专业、可直接用于报告。

#### 6.5.2 引入解释性输出（XAI）

**当前**：Agent 给出结果，但不解释为什么

**优化**：
```python
class ExplainableOutput:
    """生成可解释的输出"""
    
    def explain_decision(self, plan, execution_log):
        explanations = []
        
        for step in execution_log.steps:
            if step.tool == "analyze_failures":
                explanations.append(
                    f"分析失败原因：因为用户在 {step.timestamp} 询问失败分析，"
                    f"且项目 {step.project_id} 有 {step.result['total_failed']} 个失败分子"
                )
            
            if step.tool == "suggest_next_step":
                explanations.append(
                    f"建议优化：基于失败分析结果，{step.result['suggestion']}"
                )
        
        return "\n".join(explanations)
```

**效果**：用户问"为什么给我这个建议？"，Agent 能解释决策路径。

---

### 6.6 引入新架构模式（革命性升级）

#### 6.6.1 引入 Reflection 机制（自我反思）

**当前**：Agent 执行一次就结束，不反思执行效果

**优化**：
```python
class ReflectionAgent:
    """执行后自我反思"""
    
    def reflect(self, execution_log, user_feedback):
        # 1. 分析执行过程
        reflection_prompt = f"""
        你刚刚执行了以下计划：
        {execution_log.to_text()}
        
        用户反馈：{user_feedback}
        
        请反思：
        1. 计划是否最优？是否有更好的执行路径？
        2. 工具选择是否正确？是否遗漏了关键工具？
        3. 参数是否合理？
        4. 输出是否满足用户期望？
        
        请给出改进建议。
        """
        
        reflection = llm_call(reflection_prompt)
        
        # 保存反思结果到长期记忆
        save_to_long_term_memory(reflection)
        
        return reflection
```

**效果**：每次执行后，Agent 反思"我做得好不好？下次怎么改进？"，形成自我进化。

#### 6.6.2 引入 Multi-Agent 协作

**当前**：单个 Agent 处理所有任务

**优化**：
```python
# 专家 Agent 团队
agents = {
    "intent_specialist": IntentAgent(),      # 专门理解用户意图
    "planning_specialist": PlanningAgent(),   # 专门生成最优计划
    "chemistry_specialist": ChemistryAgent(), # 化学专家，负责分子设计
    "admet_specialist": AdmetAgent(),        # ADMET 专家，负责药代评估
    "synthesis_specialist": SynthesisAgent(), # 合成专家，负责合成路线
}

# 协调器分配任务
coordinator = CoordinatorAgent()
result = coordinator.delegate(user_input, agents)
```

**效果**：不同任务由不同专家 Agent 处理，每个 Agent 在自己的领域更专业。

#### 6.6.3 引入 Function Calling（结构化工具调用）

**当前**：工具调用是文本解析（正则匹配 JSON），不稳定

**优化**：
```python
# 使用 OpenAI 的 Function Calling API（或类似机制）
# 让 LLM 直接输出结构化函数调用，而不是自由文本

functions = [
    {
        "name": "analyze_failures",
        "description": "分析项目中失败的分子的原因",
        "parameters": {
            "type": "object",
            "properties": {
                "project_id": {"type": "integer", "description": "项目ID"},
            },
            "required": ["project_id"],
        },
    },
]

# LLM 输出：
# {"role": "assistant", "tool_calls": [{"function": {"name": "analyze_failures", "arguments": {"project_id": 35}}}]}
```

**效果**：工具调用更稳定、更可靠，不需要解析自由文本。

---

## 七、总结：从当前到未来的演进路径

```
当前架构（已实现）
    │
    ├──→ 意图理解增强（Few-Shot + 用户画像 + 多轮追踪）
    │      → 意图准确率从 70% → 90%+
    │
    ├──→ 规划能力增强（模板库 + 计划评估 + 动态调整）
    │      → 计划质量从"可用" → "最优"
    │
    ├──→ 执行能力增强（预检查 + 依赖图 + 智能调度）
    │      → 执行成功率从 80% → 95%+
    │
    ├──→ 记忆系统增强（向量数据库 + 知识图谱 + 经验迁移）
    │      → 从"记住 project_id" → "积累专业知识"
    │
    ├──→ 输出质量增强（模板 + 解释 + 可视化）
    │      → 从"文本输出" → "专业报告"
    │
    └──→ 架构升级（Reflection + Multi-Agent + Function Calling）
           → 从"单 Agent" → "专业团队"
```

**核心原则**：
1. **分层演进**：每层可以独立升级，不影响整体稳定性
2. **数据驱动**：每次优化基于用户反馈数据，不是拍脑袋
3. **最小改动**：每次优化只改最必要的地方，避免大重构
4. **持续验证**：每个优化都有明确的测试用例和验证标准

**最终目标**：让 Agent 成为真正的"药物设计智能助手"——不仅能理解用户意图、自动执行工具，还能积累专业知识、给出精准建议、自我进化提升。
