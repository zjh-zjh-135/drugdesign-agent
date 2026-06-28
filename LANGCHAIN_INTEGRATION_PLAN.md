# Agent 渐进式接入 LangChain 计划

## 核心理念

**"给手术刀装上瑞士军刀的配件"**——保留核心 ReAct 循环（engine.py 的 run() 方法），只替换外围基础设施（LLM 调用、工具注册、记忆管理、Prompt 模板）。

**不重构、不替换核心逻辑，只增强外围能力。**

---

## 当前架构

```
用户输入
    ↓
intent_parser（手写）→ 多意图拆分、上下文记忆
    ↓
planner（手写）→ 任务规划、条件步骤
    ↓
executor（手写）→ 工具执行、输出格式化
    ↓
engine.py（手写 ReAct 循环）→ 表单处理、Action Cards
    ↓
用户
```

---

## 目标架构

```
用户输入
    ↓
intent_parser（手写）→ 多意图拆分、上下文记忆（LangChain Memory 增强）
    ↓
planner（手写）→ 任务规划（LangChain PromptTemplate 管理）
    ↓
executor（手写）→ 工具执行（LangChain Tool 标准化）→ 输出格式化
    ↓
engine.py（手写 ReAct 循环）→ 表单处理、Action Cards（LangSmith 追踪）
    ↓
用户

外围增强：
- LLM 调用：langchain.chat_models.ChatMoonshot（替换 llm_client.py）
- 工具注册：@tool 装饰器（标准化接口）
- 记忆管理：ConversationBufferMemory（替代手写 memory.py）
- Prompt 管理：ChatPromptTemplate（可管理、可版本化）
- 追踪监控：LangSmith（可视化 ReAct 轨迹）
```

---

## 实施阶段

### Phase 1：LLM 调用层标准化（3-4 天）

**目标**：用 LangChain 的 `ChatModel` 替换 `llm_client.py`，获得标准化接口、自动重试、流式输出。

**修改点**：
- `backend/services/agent/llm_client.py`：重写为 LangChain 兼容层
- `backend/services/agent/engine.py`：调用方式改为 LangChain 接口
- `backend/services/agent/planner.py`：调用方式改为 LangChain 接口
- `backend/services/agent/executor.py`：调用方式改为 LangChain 接口

**具体方案**：

```python
# llm_client.py 新实现
from langchain.chat_models import ChatOpenAI  # 或 ChatMoonshot
from langchain.schema import HumanMessage, SystemMessage

class LLMClient:
    def __init__(self, api_key=None, model=None, api_url=None, timeout=60):
        self.chat_model = ChatMoonshot(
            api_key=api_key or agent_config.KIMI_API_KEY,
            model=model or agent_config.DEFAULT_MODEL,
            temperature=0.7,
            request_timeout=timeout,
            max_retries=3,
            # LangChain 自动处理指数退避重试
        )
    
    def call(self, messages: list, temperature=0.7):
        """统一调用接口"""
        lc_messages = self._convert_to_langchain(messages)
        response = self.chat_model(lc_messages, temperature=temperature)
        return response.content
    
    def call_with_tracking(self, messages: list, metadata: dict = None):
        """带 LangSmith 追踪的调用"""
        # 自动记录每个 LLM 调用的输入、输出、延迟
        pass
```

**收益**：
- 标准化 LLM 接口，支持一键切换模型（Kimi → GPT-4 → Claude）
- 自动重试、指数退避（无需手写 `retry_call`）
- 流式输出（SSE）支持，前端可实时显示"思考中..."
- Token 用量自动统计

**风险**：
- LangChain 的 `ChatMoonshot` 依赖可能不够稳定（需确认 kimi 官方 SDK 兼容性）
- 连接池逻辑可能需要保留（LangChain 的 HTTP 连接管理不如手写灵活）

**验证方式**：
- 现有测试用例全部通过（`analyze_single_molecule_admet`、`run_pipeline` 等）
- 流式输出正常（前端显示"Agent 正在思考..."）
- Token 统计准确

---

### Phase 2：工具层标准化（2-3 天）

**目标**：用 LangChain 的 `@tool` 装饰器重构 `tools.py`，标准化工具接口，可接入 LangChain 生态（1000+ 工具）。

**修改点**：
- `backend/services/agent/tools.py`：工具注册方式改为 `@tool` 装饰器
- `backend/services/agent/executor.py`：工具调用方式改为 LangChain `Tool` 接口

**具体方案**：

```python
# tools.py 新实现
from langchain.tools import tool, BaseTool
from pydantic import BaseModel, Field

# 1. 简单工具（@tool 装饰器）
@tool
def analyze_single_molecule_admet(smiles: str) -> dict:
    """
    直接对单个 SMILES 进行 ADMET 五分类分析。
    
    Args:
        smiles: 分子的 SMILES 字符串
    
    Returns:
        包含 absorption/distribution/metabolism/excretion/toxicity 的 dict
    """
    from ..admet import AdmetPredictor
    return AdmetPredictor.predict(smiles)

# 2. 复杂工具（带参数校验）
class RunPipelineInput(BaseModel):
    project_id: int = Field(description="项目 ID")
    num_molecules: int = Field(default=500, description="生成分子数量")
    
class RunPipelineTool(BaseTool):
    name = "run_pipeline"
    description = "运行 Pipeline 生成分子"
    args_schema = RunPipelineInput
    
    def _run(self, project_id: int, num_molecules: int = 500):
        # 调用原有逻辑
        return run_pipeline(project_id, num_molecules)
    
    async def _arun(self, project_id: int, num_molecules: int = 500):
        # 异步版本（支持并发）
        return await asyncio.to_thread(run_pipeline, project_id, num_molecules)

# 3. 工具注册（兼容现有注册表）
tools = [
    analyze_single_molecule_admet,
    RunPipelineTool(),
    # ... 其他工具
]

# 4. 兼容层（保留现有 get_registry() 接口）
_registry = None

def get_registry():
    global _registry
    if _registry is None:
        from .tool_registry import ToolRegistry
        _registry = ToolRegistry()
        for tool in tools:
            _registry.register(tool.name, tool)
    return _registry
```

**收益**：
- 工具描述自动生成（`@tool` 装饰器从 docstring 提取描述）
- 参数自动校验（Pydantic 模型）
- 可接入 LangChain 的 `Tool` 生态（如 `SerpAPI`、`Wikipedia`）
- LLM 更容易理解工具用途（标准化描述格式）

**风险**：
- 现有工具注册表（`ToolRegistry`）需要保留兼容层
- 工具返回类型可能需调整（LangChain 偏好字符串，但我们的工具返回 dict）
- 前端 Action Cards 依赖现有工具名，不能改

**验证方式**：
- 所有工具调用正常（`analyze_single_molecule_admet`、`run_pipeline` 等）
- 工具描述在 LangSmith 中可见
- 参数校验错误能正确返回

---

### Phase 3：记忆层升级（2-3 天）

**目标**：用 LangChain 的 `ConversationBufferMemory` 替换手写的 `memory.py`，支持窗口记忆、摘要记忆、向量检索。

**修改点**：
- `backend/services/agent/memory.py`：重写为 LangChain 兼容层
- `backend/services/agent/engine.py`：调用方式改为 LangChain 接口

**具体方案**：

```python
# memory.py 新实现
from langchain.memory import (
    ConversationBufferMemory,
    ConversationBufferWindowMemory,
    ConversationSummaryMemory,
    VectorStoreRetrieverMemory,
)
from langchain.schema import AIMessage, HumanMessage, SystemMessage

class AgentMemory:
    """LangChain 增强版记忆管理"""
    
    def __init__(self, session_id: str, db=None, max_token_limit=4000):
        self.session_id = session_id
        self.db = db
        
        # 1. 短期记忆：最近 5 条对话（已有）
        self.short_term = ConversationBufferWindowMemory(
            k=5,
            return_messages=True,
            memory_key="chat_history",
        )
        
        # 2. 长期记忆：摘要化（超过 5 条后自动摘要）
        self.long_term = ConversationSummaryMemory(
            llm=LLMClient().chat_model,  # 用 LLM 生成摘要
            memory_key="summary",
            return_messages=True,
        )
        
        # 3. 项目记忆：向量检索（未来扩展）
        # self.vector_memory = VectorStoreRetrieverMemory(
        #     retriever=vector_store.as_retriever(),
        #     memory_key="project_memory",
        # )
    
    def save_user_message(self, content: str):
        self.short_term.chat_memory.add_user_message(content)
    
    def save_assistant_message(self, content: str, metadata: dict = None):
        self.short_term.chat_memory.add_ai_message(content)
        
        # 同时保存到数据库（保留原有持久化）
        if self.db:
            save_message(self.db, self.session_id, "assistant", content, metadata=metadata)
    
    def get_history(self, limit=50) -> list:
        """获取对话历史（混合短期 + 长期记忆）"""
        messages = []
        
        # 添加长期摘要（如果有）
        if self.long_term.buffer:
            messages.append(SystemMessage(content=f"历史摘要：{self.long_term.buffer}"))
        
        # 添加短期记忆
        for msg in self.short_term.chat_memory.messages[-limit:]:
            messages.append(msg)
        
        return messages
    
    def get_context_for_llm(self) -> str:
        """生成适合 LLM 的上下文字符串"""
        return self.short_term.load_memory_variables({})["chat_history"]
```

**收益**：
- 自动 Token 管理（超预算时自动摘要，无需手写 `_summarize_history`）
- 支持多种记忆策略（窗口、摘要、向量检索）
- 记忆持久化与 LangChain 生态兼容

**风险**：
- 数据库表结构（`AgentMessage`）可能需要微调（LangChain 的消息格式有额外字段）
- `session_id` 与 `project_id` 的关联逻辑需要保留
- 上下文记忆（`last_project_id`、`last_target`）需要额外处理

**验证方式**：
- 对话历史正确保存和读取
- 超过 5 条后自动摘要（Token 管理）
- 上下文记忆（`last_project_id`）正常工作

---

### Phase 4：Prompt 管理（2-3 天）

**目标**：用 LangChain 的 `ChatPromptTemplate` 管理提示词，支持版本化、可追踪、可复用。

**修改点**：
- `backend/services/agent/prompts/`：新建目录，存放所有提示词模板
- `backend/services/agent/planner.py`：改为加载模板文件
- `backend/services/agent/executor.py`：改为加载模板文件

**具体方案**：

```
backend/services/agent/prompts/
├── __init__.py
├── planner.yaml          # 任务规划提示词
├── executor.yaml          # 执行决策提示词
├── intent_parser.yaml     # 意图解析提示词
├── chat_response.yaml     # 简单聊天提示词
└── versions/
    ├── planner_v1.yaml    # 版本历史
    ├── planner_v2.yaml
    └── executor_v1.yaml
```

```python
# prompts/__init__.py
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.schema import SystemMessage, HumanMessage
import yaml

def load_prompt(name: str, version: str = "latest") -> ChatPromptTemplate:
    """加载提示词模板"""
    if version == "latest":
        path = f"backend/services/agent/prompts/{name}.yaml"
    else:
        path = f"backend/services/agent/prompts/versions/{name}_{version}.yaml"
    
    with open(path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    messages = []
    for msg in config["messages"]:
        if msg["role"] == "system":
            messages.append(SystemMessage(content=msg["content"]))
        elif msg["role"] == "human":
            messages.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "history":
            messages.append(MessagesPlaceholder(variable_name="chat_history"))
    
    return ChatPromptTemplate.from_messages(messages)

# planner.py 中使用
from .prompts import load_prompt

planner_prompt = load_prompt("planner")

# 填充变量
messages = planner_prompt.format_messages(
    goal=user_message,
    project_id=project_id,
    env_state=env_report,
    available_tools=tools_description,
    chat_history=memory.get_context_for_llm(),
)
response = llm_client.call(messages)
```

**planner.yaml 示例**：

```yaml
name: task_planner
version: "1.0"
description: "任务规划提示词"

messages:
  - role: system
    content: |
      你是一位药物设计 AI Agent 的任务规划专家。
      
      目标：将用户请求转化为可执行的任务计划。
      
      可用工具：
      {available_tools}
      
      环境状态：
      {env_state}
      
      规则：
      1. 如果用户提供了 SMILES，优先使用 analyze_single_molecule_admet
      2. 如果涉及项目操作，需要 project_id
      3. 步骤之间可以有依赖关系
      
  - role: history
    name: chat_history
    
  - role: human
    content: |
      用户请求：{goal}
      
      请制定执行计划，输出 JSON 格式。
```

**收益**：
- 提示词与代码分离，非技术人员也可修改
- 版本化管理（A/B 测试不同提示词效果）
- 可追踪（LangSmith 显示每个提示词的输入/输出）
- 可复用（多个 Agent 共享同一套提示词）

**风险**：
- 提示词文件格式需要设计（YAML/JSON）
- 变量替换逻辑需要测试（确保 `{goal}` 等变量正确填充）
- 中文编码问题（YAML 文件需 UTF-8）

**验证方式**：
- 所有提示词正确加载
- 变量替换无遗漏
- LLM 输出格式与之前一致

---

### Phase 5：追踪与监控（1-2 天）

**目标**：引入 LangSmith，可视化 ReAct 轨迹、监控 LLM 调用性能、调试 Agent 行为。

**修改点**：
- `backend/services/agent/engine.py`：添加 LangSmith 追踪
- `backend/services/agent/executor.py`：添加步骤追踪
- 环境变量配置：`.env` 添加 `LANGCHAIN_API_KEY`

**具体方案**：

```python
# 在 engine.py 中
from langchain.callbacks import LangSmithCallbackHandler

def run(self, user_message: str, context: Dict = None):
    # 创建追踪回调
    callbacks = []
    if os.environ.get("LANGCHAIN_API_KEY"):
        callbacks.append(LangSmithCallbackHandler(
            project_name="drugdesign-agent",
            tags=["production"],
        ))
    
    # 每个 LLM 调用都带追踪
    trace_id = str(uuid.uuid4())[:8]
    
    with tracing_v2_enabled(project_name="drugdesign-agent"):
        # 意图解析
        parsed_intent = parser.parse(user_message, context)
        
        # 规划
        plan = planner.plan(...)
        
        # 执行
        execution_log = executor.execute_plan(...)
        
        # 所有步骤自动记录到 LangSmith
        # 可在 https://smith.langchain.com 查看：
        # - 每个 LLM 调用的输入/输出
        # - 执行耗时
        # - Token 用量
        # - 错误信息
    
    return result
```

**LangSmith 面板展示**：

```
Trace: drugdesign-agent
├── Run: intent_parser.parse
│   ├── Input: "测试 xxx 的 ADMET 数据"
│   ├── Output: IntentType.SINGLE_ACTION
│   └── Latency: 1.2s
├── Run: planner.plan
│   ├── Input: goal="测试 xxx 的 ADMET", env_state={...}
│   ├── Output: {"steps": [{"tool": "analyze_single_molecule_admet"}]}
│   └── Latency: 2.1s
├── Run: executor.execute_plan
│   ├── Step 1: analyze_single_molecule_admet
│   │   ├── Input: smiles="xxx"
│   │   ├── Output: {"absorption": {...}, ...}
│   │   └── Latency: 0.5s
│   └── Latency: 0.8s
└── Total Latency: 4.1s
```

**收益**：
- 可视化 ReAct 轨迹（每个步骤的输入/输出/耗时）
- 性能监控（哪个 LLM 调用最慢、Token 用量最多）
- 错误调试（快速定位失败步骤）
- 数据集构建（收集成功的执行轨迹，用于微调）

**风险**：
- 需要 LangSmith 账号（免费版有额度限制）
- 数据隐私（LLM 调用内容会上传到 LangSmith 服务器）
- 网络依赖（国内访问可能不稳定）

**验证方式**：
- LangSmith 面板可见完整 Trace
- 每个 LLM 调用的输入/输出正确
- 耗时统计准确

---

## 实施顺序

```
Phase 1: LLM 调用层（3-4 天）
    ↓
Phase 2: 工具层（2-3 天）
    ↓
Phase 3: 记忆层（2-3 天）
    ↓
Phase 4: Prompt 管理（2-3 天）
    ↓
Phase 5: 追踪监控（1-2 天）

总计：10-15 天
```

**每阶段之间可以独立回滚**，不影响核心逻辑。

---

## 兼容性策略

### 保留的接口（不改动）

```python
# engine.py 的 run() 方法签名不变
def run(self, user_message: str, context: Dict = None) -> Dict[str, Any]:
    pass

# CopilotAgent.chat() 方法签名不变
def chat(self, message: str, project_id: int = None, session_id: str = None, db=None) -> Dict[str, Any]:
    pass

# API 端点返回格式不变（/agent/chat、/agent/goal）
{
    "success": True,
    "final_answer": "...",
    "chat_summary": "...",
    "execution_report": {...},
}
```

### 新增的能力（可选启用）

```python
#  LangChain 增强功能（可选）
- 流式输出（SSE）
- Token 自动统计
- 提示词版本切换
- LangSmith 追踪
- 外部工具接入（PubChem、Wikipedia）
```

---

## 风险评估

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| LangChain 版本升级导致 API 变更 | 高 | 中 | 锁定版本（`langchain==0.3.x`），每季度评估升级 |
| 国内访问 LangSmith 不稳定 | 中 | 低 | 可选功能，不启用时不影响核心功能 |
| 性能下降（LangChain 抽象层开销） | 低 | 低 | 压测对比，必要时保留手写热路径 |
| 团队学习成本 | 中 | 低 | 逐步引入，核心逻辑不变 |

---

## 成功标准

1. **所有现有测试通过**：`analyze_single_molecule_admet`、`run_pipeline`、`analyze_failures` 等功能正常
2. **API 兼容**：前端 `HelpChatModal.jsx` 无需修改（或仅需微调）
3. **性能不降级**：平均响应时间与之前持平（±10%）
4. **新能力可用**：至少启用 1 项新能力（如 LangSmith 追踪或流式输出）

---

## 下一步

如果你认可这个计划，可以：
1. 先确认 Phase 1（LLM 调用层）是否值得做
2. 我编写 `IMPLEMENTATION_PLAN.md` 并立即开始 Phase 1
3. 或先评估现有代码，确认哪些部分最急需 LangChain 增强

**你的决定？**