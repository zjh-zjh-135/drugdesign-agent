# DrugDesign Copilot Agent 优化计划

> **制定日期：** 2026-06-27  
> **目标：** 系统稳定化 + 性能提升 + 可扩展性增强  
> **执行周期：** 预计 3-4 周（可根据实际情况调整）

---

## 一、当前问题诊断

经过系统审查，当前系统处于 **"能跑但脆弱"** 阶段。核心瓶颈集中在：

1. **LLM 调用链爆炸** — 单次请求最坏触发 12+ 次 LLM 调用，无缓存、无批量决策
2. **重复代码严重** — `call_llm` 在 4 个文件中重复，数据库连接无池化
3. **条件逻辑不完整** — 用户说 "如果...就..." 时无法正确执行条件分支
4. **响应延迟不可控** — `wait_for_pipeline` 阻塞 300 秒，PubChem 串行查询 500 秒
5. **可扩展性不足** — 新增工具需改 3-5 个文件，硬编码映射多

---

## 二、优化原则

- **小步快跑**：每阶段产出可独立验证的改进，不阻塞主流程
- **向后兼容**：不改现有接口签名，不破坏前端交互协议
- **可度量**：每个优化项都有明确的 KPI 指标
- **低风险**：先改基础设施，再改业务逻辑，最后改架构

---

## 三、Phase 1：稳定化（第 1-2 周）

> **目标：** 消除级联失败风险，修复核心逻辑缺陷，让系统 "稳得住"

### 3.1 任务 P1.1：统一 LLM 客户端

**优先级：** P0（最高）  
**涉及的文件：** 新建 `llm_client.py`，修改 `engine.py`、`planner.py`、`executor.py`、`intent_parser.py`  
**问题：** 4 个模块各自实现 `_call_llm()`，API URL、密钥、限流逻辑完全重复  
**方案：**

```
llm_client.py
├── class LLMClient
│   ├── call()          # 统一调用入口
│   ├── cached_call()   # 带缓存的调用（相同 prompt 60s 复用）
│   ├── retry_call()    # 带指数退避重试的调用
│   ├── stream_call()   # 流式输出（为 Phase 3 预留）
│   └── metrics         # 调用次数、token 消耗、延迟统计
```

**具体改动：**
1. 新建 `backend/services/agent/llm_client.py`
2. 删除 `engine.py` 的 `call_llm()` 方法，改为注入 `LLMClient`
3. 删除 `planner.py`、`executor.py`、`intent_parser.py` 的 `_call_llm()` 方法
4. 所有子模块通过 `__init__` 接收 `llm_client` 实例

**预期效果：**
- 消除重复代码（-3 个重复方法）
- 统一缓存策略（常用 prompt 命中缓存，减少 20-30% 调用）
- 统一重试策略（429/503 自动退避，失败率降低 50%）
- 为后续流式输出预留接口

**验证方式：** 运行测试用例，确认所有子模块调用正常，无 API 错误。

---

### 3.2 任务 P1.2：修复条件步骤逻辑

**优先级：** P0  
**涉及的文件：** `executor.py`、`planner.py`  
**问题：** 用户说 "如果 ADMET 不好就优化" 时，条件步骤在 executor 中被标记为 `status="ok"` 但没有真正评估，后续也没有跳过逻辑  
**方案：**

1. **planner.py** — 在 `plan()` 中，如果意图上下文有 `conditions`，在对应步骤中标记 `condition` 字段
2. **executor.py** — 在 `execute_plan()` 循环中：
   - 遇到 `condition` 字段时，先评估条件（使用 LLM 或规则）
   - 如果条件不满足，标记 `status="skipped"` 并跳过该步骤
   - 如果条件满足，正常执行步骤

**预期效果：** 条件性请求（如 "如果...就...否则..."）能够正确执行，不再被误判为执行成功。

**验证方式：** 测试 "如果 ADMET 分数低于3，就调整过滤条件重新运行" → 确认条件正确评估。

---

### 3.3 任务 P1.3：统一数据库连接池

**优先级：** P0  
**涉及的文件：** `tools.py`  
**问题：** `_get_db()` 每次都创建新 session，高并发时连接数会爆炸  
**方案：**

1. 修改 `_get_db()` 使用 `scoped_session` 或单例 Session
2. 所有工具函数使用上下文管理器 `with get_db() as db:`
3. 确保 session 在使用后正确关闭

**预期效果：** 消除数据库连接泄漏，支持高并发请求。

**验证方式：** 模拟 10 个并发请求，确认数据库连接数不超过 5。

---

### 3.4 任务 P1.4：修复 `wait_for_pipeline` 阻塞

**优先级：** P0  
**涉及的文件：** `executor.py`、`tools.py`  
**问题：** `wait_for_pipeline` 在 executor 中阻塞线程 300 秒，期间整个请求被挂起  
**方案：**

1. 在 `executor.py` 中，将 `wait_for_pipeline` 改为非阻塞调用
2. 改为返回 "已启动 Pipeline，正在等待完成" 状态，executor 在后台轮询
3. 或者：缩短默认超时，增加 "Pipeline 已启动，请稍后查看结果" 的提示

**预期效果：** 单次请求响应时间不再受 Pipeline 运行时间影响，用户体验不再"卡死"。

**验证方式：** 运行 `create_project → run_pipeline → wait` 流程，确认请求 5 秒内返回，不阻塞。

---

### 3.5 任务 P1.5：提取配置中心

**优先级：** P1  
**涉及的文件：** 新建 `config.py`，修改 `engine.py`、`planner.py`、`executor.py`、`intent_parser.py`  
**问题：** `DEFAULT_MODEL`、`KIMI_API_URL`、`KIMI_API_KEY` 在 4 个文件中重复定义  
**方案：**

```python
# config.py
from pydantic_settings import BaseSettings

class AgentConfig(BaseSettings):
    KIMI_API_KEY: str = ""
    KIMI_API_URL: str = "https://api.moonshot.cn/v1/chat/completions"
    DEFAULT_MODEL: str = "moonshot-v1-8k"
    MAX_STEPS: int = 10
    LLM_CACHE_TTL: int = 60
    STEP_TIMEOUT: int = 30
    PUBCHEM_TIMEOUT: int = 10
    PUBCHEM_MAX_WORKERS: int = 5
```

**预期效果：** 配置集中管理，一处修改全局生效，支持环境变量覆盖。

---

### 3.6 任务 P1.6：添加请求追踪（trace_id）

**优先级：** P1  
**涉及的文件：** `engine.py` + 所有模块  
**问题：** 无法追踪单个请求在各个模块中的流转，排查问题困难  
**方案：**

1. 在 `engine.run()` 中为每个请求生成 `trace_id`（UUID）
2. 将 `trace_id` 通过 `context` 传递到所有子模块
3. 在 LLM 调用、工具调用、错误日志中打印 `trace_id`

**预期效果：** 支持请求链路追踪，便于排查问题和性能分析。

---

### 3.7 任务 P1.7：修复 SMILES 实体提取

**优先级：** P1  
**涉及的文件：** `intent_parser.py`  
**问题：** 当前正则几乎无法匹配真实 SMILES（如 `CC(C)Oc1ccc(...)`）  
**方案：**

1. 使用更完善的正则组合（支持标准 SMILES 特征）
2. 使用 RDKit 的 `Chem.MolFromSmiles` 预验证（如果已安装）
3. 支持显式 `SMILES: xxx` 格式和隐式 SMILES 格式

**预期效果：** 提高实体提取准确率，用户可以直接粘贴 SMILES。

---

## 四、Phase 2：性能提升（第 3-4 周）

> **目标：** 将平均响应时间从分钟级降到秒级，减少 LLM 调用次数，支持并发

### 4.1 任务 P2.1：减少 LLM 决策调用次数

**优先级：** P0  
**涉及的文件：** `executor.py`  
**问题：** 10 步计划触发 12 次 LLM 调用，成本和时间都不可控  
**方案：**

**方案 A：批量决策（推荐）**
- 执行 2-3 步后再问 LLM "继续/修改/结束"
- 10 步计划从 12 次 LLM 调用降到 5 次

**方案 B：确定性模式识别**
- 对标准流程（`create_project → run_pipeline → wait → get_top`）直接执行，不每步 LLM 确认
- 遇到非标准步骤（如 `analyze_admet_sar`）时才触发 LLM 决策

**方案 C：智能决策间隔**
- 简单步骤（如 `get_project_status`）跳过决策
- 复杂步骤（如 `run_pipeline`）后必做决策
- 连续成功时放宽决策频率，连续失败时收紧

**预期效果：** 单次请求 LLM 调用次数从 12+ 降到 5-7 次，响应时间减少 40-60%。

---

### 4.2 任务 P2.2：添加缓存层

**优先级：** P1  
**涉及的文件：** `intent_parser.py`、`perception.py`、`llm_client.py`  
**方案：**

1. **意图解析缓存**：`{hash(message): ParsedIntent, TTL=60s}`
2. **环境感知缓存**：`{project_id + last_modified: env_state, TTL=10s}`
3. **LLM 调用缓存**：`{hash(prompt + model): response, TTL=60s}`

**预期效果：** 连续提问时减少 1-2 次 LLM 调用和数据库查询，响应速度提升 30-50%。

---

### 4.3 任务 P2.3：多意图并行执行

**优先级：** P1  
**涉及的文件：** `engine.py`  
**问题：** "分析A项目然后查看B项目" 两个子意图串行，总延迟翻倍  
**方案：**

1. 在 `engine._execute_multi_intent()` 中，检测子意图之间是否有数据依赖
2. 无依赖的子意图使用 `asyncio.gather` 或 `ThreadPoolExecutor` 并行执行
3. 有依赖的保持串行

**预期效果：** 独立子意图并行执行，延迟降低 30-50%。

---

### 4.4 任务 P2.4：异步 PubChem 查询

**优先级：** P1  
**涉及的文件：** `tools.py`  
**问题：** `check_patent_novelty` 串行调用，50 个分子最坏 500 秒  
**方案：**

1. 使用 `asyncio.gather` 或 `ThreadPoolExecutor(max_workers=5)` 并行查询
2. 设置整体超时 30 秒（而非单个 10 秒）
3. 失败的查询返回 `"timeout"` 而不是让整个请求失败

**预期效果：** 专利检查速度提升 5-10 倍，50 个分子从 500 秒降到 30 秒。

---

### 4.5 任务 P2.5：对话历史 Token 管理

**优先级：** P1  
**涉及的文件：** `memory.py`、`engine.py`  
**问题：** 直接返回最近 20 条消息，可能超过 8K 模型上下文限制  
**方案：**

1. 使用 tiktoken（或简单估算）计算对话历史 token 数
2. 超预算时对早期对话自动摘要化（保留最近 5 条完整，其余压缩为摘要）
3. 在 `engine.run()` 中将对话历史注入到 `context`

**预期效果：** 避免 LLM 上下文截断，保证对话连贯性，支持长对话（50+ 轮）。

---

### 4.6 任务 P2.6：执行历史摘要化

**优先级：** P2  
**涉及的文件：** `executor.py`  
**问题：** 长计划执行时，`_format_execution_history` 包含所有步骤，可能超出 token 限制  
**方案：**

1. 当步骤超过 5 步时，对前 N-5 步做压缩摘要
2. 只保留最近 3 步的完整信息（工具名、参数、结果、状态）
3. 早期步骤压缩为："步骤 X: tool_name → status → result_summary"

**预期效果：** 长计划执行时 LLM 上下文可控，不再出现 "context too long" 错误。

---

## 五、Phase 3：可扩展性（第 5-6 周，可选）

> **目标：** 支持快速新增工具/意图，提升系统健壮性

### 5.1 任务 P3.1：工具基类抽象

**优先级：** P1  
**涉及的文件：** 新建 `tools/base.py`，重构 `tools.py`  
**方案：**

```python
class BaseTool:
    name: str
    description: str
    parameters: dict
    depends_on: list[str] = []
    
    def validate(self, params: dict) -> bool: ...
    def execute(self, **params) -> dict: ...
    def handle_error(self, error: Exception) -> dict: ...
```

所有工具继承 `BaseTool`，新增工具只需实现一个 `execute()` 方法。

**预期效果：** 新增工具从改 3-5 个文件降到 1-2 个文件。

---

### 5.2 任务 P3.2：拆分 tools.py 为模块

**优先级：** P1  
**涉及的文件：** `tools.py` → `tools/` 目录  
**方案：**

```
tools/
├── __init__.py          # 注册中心，向后兼容
├── base.py              # BaseTool 基类
├── project.py           # 项目管理工具（create_project, get_project_status 等）
├── pipeline.py          # Pipeline 工具（run_pipeline, wait_for_pipeline 等）
├── analysis.py          # 分子分析工具（analyze_*, check_*, assess_* 等）
├── external.py          # 外部 API 工具（PubChem 查询等）
└── helper.py            # 通用辅助函数（get_db, calculate_composite_score 等）
```

**预期效果：** 代码结构清晰，团队可并行开发不同领域工具。

---

### 5.3 任务 P3.3：Prompt 模板化与版本管理

**优先级：** P2  
**涉及的文件：** `planner.py`  
**方案：**

1. 将 system prompt 外置为 `prompts/planner.yaml`（支持 Jinja2 模板）
2. 支持版本号（`v1`, `v2`）和环境变量覆盖
3. 支持 A/B 测试不同 prompt 策略

**预期效果：** 支持快速迭代 prompt 策略，无需修改代码即可测试新策略。

---

### 5.4 任务 P3.4：引入 Function Calling / Structured Output

**优先级：** P2  
**涉及的文件：** `planner.py`、`llm_client.py`  
**问题：** 当前依赖 LLM 自觉遵守 "纯 JSON" 指令，解析失败率约 15%  
**方案：**

1. 将规划目标从 "让 LLM 输出 JSON" 改为 "调用 `create_plan` function"
2. 使用 KIMI API 的 `tools` / `functions` 参数
3. 返回结构化 JSON，解析失败率降到 <2%

**预期效果：** 计划 JSON 解析失败率从 ~15% 降到 <2%。

---

### 5.5 任务 P3.5：向量语义搜索（长期记忆）

**优先级：** P2  
**涉及的文件：** `memory.py`  
**问题：** `search_long_term_memory` 使用 `LIKE` 匹配，无法处理同义词  
**方案：**

1. 引入轻量级向量库（如 `sqlite-vec` 或 `faiss`）
2. 将长期记忆文本转为嵌入向量，支持语义搜索
3. 支持同义词和语义相似查询（如 "药物设计" ≈ "分子设计"）

**预期效果：** 长期记忆支持语义搜索，召回率提升 50%+。

---

### 5.6 任务 P3.6：流式输出支持

**优先级：** P3  
**涉及的文件：** `engine.py`、`llm_client.py`  
**方案：**

1. `LLMClient.stream_call()` 支持流式输出
2. 用户可以看到 "正在分析..." "正在获取数据..." 的实时反馈
3. 最终答案在流式输出中逐步构建

**预期效果：** 用户体验提升，感知等待时间减少 60%。

---

## 六、执行顺序建议

### 执行优先级（从上到下，先做依赖少的）

```
Phase 1（第 1-2 周）
├── P1.5 配置中心（被后续所有任务依赖）
├── P1.1 统一 LLM 客户端（被后续任务依赖）
├── P1.2 修复条件步骤（逻辑修复）
├── P1.3 数据库连接池（稳定性）
├── P1.4 修复 wait_for_pipeline（用户体验）
├── P1.6 请求追踪（可观测性）
└── P1.7 修复 SMILES 提取（准确率）

Phase 2（第 3-4 周）
├── P2.1 减少 LLM 决策调用（核心性能）
├── P2.2 添加缓存层（性能）
├── P2.3 多意图并行（性能）
├── P2.4 异步 PubChem（性能）
├── P2.5 对话 Token 管理（稳定性）
└── P2.6 执行历史摘要（稳定性）

Phase 3（第 5-6 周，可选）
├── P3.1 工具基类（可扩展性）
├── P3.2 拆分 tools.py（可维护性）
├── P3.3 Prompt 版本管理（可迭代性）
├── P3.4 Function Calling（可靠性）
├── P3.5 向量语义搜索（长期记忆）
└── P3.6 流式输出（用户体验）
```

---

## 七、核心 KPI 目标

| 指标 | 当前估计 | Phase 1 目标 | Phase 2 目标 | Phase 3 目标 |
|------|----------|-------------|-------------|-------------|
| 单次请求 LLM 调用次数（最坏） | 12+ | 12+ | ≤ 5 | ≤ 5 |
| 简单意图平均延迟 | 15-30s | 10-15s | ≤ 5s | ≤ 5s |
| 复杂意图平均延迟 | 60-180s | 60-120s | ≤ 30s | ≤ 30s |
| 计划 JSON 解析失败率 | ~15% | ~15% | ≤ 5% | ≤ 2% |
| 新增工具所需修改文件数 | 3-5 | 3-5 | 3-5 | 1-2 |
| 系统异常崩溃率 | 无监控 | 可监控 | ≤ 0.1% | ≤ 0.01% |

---

## 八、风险评估与缓解

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|----------|
| 统一 LLM 客户端引入新 bug | 中 | 高 | 保留旧方法作为 fallback，灰度切换 |
| 缓存导致数据不一致 | 低 | 中 | 缓存 TTL 短（10-60s），关键操作不走缓存 |
| 数据库连接池配置不当 | 低 | 高 | 先测试环境验证，监控连接数 |
| Function Calling 不支持 | 低 | 中 | 保留原有 JSON 解析作为 fallback |
| 并行执行导致数据竞争 | 中 | 中 | 只并行无依赖的操作，依赖项串行 |

---

## 九、下一步行动

如果你确认这个计划，我将按以下顺序执行：

1. **先执行 Phase 1.1（统一 LLM 客户端）** — 这是所有后续优化的基础设施
2. 每完成一个任务，我会立即验证并汇报结果
3. 你随时可以叫停、调整优先级或跳过某个任务

请确认是否开始执行。
