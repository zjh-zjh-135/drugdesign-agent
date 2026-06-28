# Agent 输出体验优化计划

## 一、问题回顾

当前 Agent 体验存在三个致命问题，直接影响用户从 "跑 Pipeline" 到 "看懂结果" 的完整闭环：

### 问题1：一键全流程返回质量极差

- **用户输入：** `帮我跑一遍AKT1的全流程`
- **实际返回：** `全流程完成。项目ID=42，生成50个分子，通过8个，获得Top 3候选分子。`
- **问题：** 用户等待数分钟，只得到一句话摘要。没有分子结构、没有性质数据、没有排名对比。数据在 `top_molecules` 数组里，但从未被格式化给用户看。

### 问题2：后续追问直接失败

- **用户输入：** `给出详细的这三个分子数据`
- **实际返回：** `Step 1: LLM 规划失败，先获取项目状态` → `Action: get_project_status` → `Status: ok` → 没有返回任何分子数据
- **问题：** 用户要的是数据，Agent 去获取项目状态和空建议，没有返回任何分子数据。这是**上下文断链**——Agent 没有理解"这三个分子"指的是上一步的结果。

### 问题3：无输入时自动触发（Copilot 自主执行）

- **用户没有输入**，系统却自动执行 `get_project_status + suggest_next_step`，输出空内容。
- **问题：** 前端 Copilot 自动轮询/空消息触发了不必要的后端调用。

---

## 二、优化目标

| 目标 | 描述 | 验收标准 |
|------|------|----------|
| T1 | 一键全流程返回专业报告 | 用户说"跑一遍 XXX" → 返回包含 Top 3 分子完整数据的 Markdown 报告 |
| T2 | 追问直接返回数据 | 用户说"详细数据/给我看看/具体分析" → 返回上一步的格式化报告 |
| T3 | 阻止无输入触发 | 用户没有输入时，系统绝不执行任何动作 |
| T4 | 失败时诚实告知 | 不再用 `suggest_next_step` 作为兜底，失败时返回诚实提示 |
| T5 | 前后端统一拦截 | 空消息、无意义输入在前端和后端都被拦截 |

---

## 三、实施计划（共 5 个阶段，预计 3 小时）

### Stage 1: 为 `run_full_pipeline` 增加内置格式化（P0，60分钟）

**目标：** 解决"跑完只给一句话"的核心痛点。

**具体步骤：**
1. 在 `run_full_pipeline` 函数中，获取到 `top_molecules` 后，调用新的内部格式化函数 `_build_molecule_report()`
2. 格式化函数生成 Markdown 报告，包含：
   - 项目基本信息（靶点、PDB、生成分子数、通过数、失败数）
   - Top 3 分子详细卡片（排名、SMILES、分子量、LogP、QED、对接分数、ADMET得分、综合得分）
   - 结构相似性分析（与已知活性分子的对比，如果能获取到的话）
   - 下一步建议（基于数据自动生成，如"候选1 QED最佳，建议优先合成"）
3. 将 Markdown 报告作为 `final_report` 字段放入返回字典
4. 在 `engine.py` 的 `_execute_goal_oriented` 中，当工具返回包含 `final_report` 时，优先展示报告而非默认 `message`

**文件修改：**
- `backend/services/agent/tools.py`：新增 `_build_molecule_report()` 函数，修改 `run_full_pipeline` 返回值
- `backend/services/agent/engine.py`：工具调用后优先使用 `final_report` 字段

**预期效果：** 用户说"跑一遍 AKT1" → 立即返回专业报告，包含 3 个分子的完整数据。

---

### Stage 2: 新增 `format_top_molecules` 格式化工具（P1，30分钟）

**目标：** 解决用户追问"详细数据"时的上下文断链问题。

**具体步骤：**
1. 在 `tools.py` 中新增 `format_top_molecules(project_id, limit=3)` 工具
2. 该工具查询数据库中的 `synthesis_passed` 分子，按综合得分排序，生成 Markdown 报告
3. 逻辑与 `run_full_pipeline` 内的格式化函数复用（抽取公共函数）
4. 注册为 Agent 工具，供 ReAct 循环调用

**文件修改：**
- `backend/services/agent/tools.py`：新增 `format_top_molecules` 函数和 `_build_molecule_report` 公共函数

**预期效果：** 用户说"给我详细数据" → Agent 调用 `format_top_molecules` → 返回完整报告。

---

### Stage 3: 修复意图解析器——识别"格式化追问"（P1，30分钟）

**目标：** 让 Agent 理解用户不是在要求新操作，而是在要求"把已有结果格式化给我看"。

**具体步骤：**
1. 在 `intent_parser.py` 的 `_quick_detect` 中新增规则：
   - 检测关键词：`详细数据`、`详细结果`、`具体数据`、`给我看看`、`详细点`、`展开说说`、`数据给我`、`报告`
   - 如果命中 + 上下文有 `project_id` → 返回 `FOLLOW_UP` 意图，但 `detected_actions = ["format_top_molecules"]`
2. 在 `intent_parser.py` 的 `_detect_missing_params` 中，`format_top_molecules` 需要 `project_id`
3. 在 `engine.py` 的 `_needs_form` 中，`FOLLOW_UP` 意图如果上下文有 `project_id` 且动作是 `format_top_molecules`，不需要表单

**文件修改：**
- `backend/services/agent/intent_parser.py`：新增格式化追问检测规则
- `backend/services/agent/engine.py`：表单检测支持 `format_top_molecules`

**预期效果：** 用户说"详细数据" → 直接调用格式化工具，不走 `suggest_next_step`。

---

### Stage 4: 移除 `suggest_next_step` 的兜底触发 + 修复空消息（P0，20分钟）

**目标：** 失败时诚实告知，不假装成功；无输入时绝不触发。

**具体步骤：**
1. **后端空消息拦截：** 在 `engine.py` 的 `run` 方法入口，增加 `if not user_message or not user_message.strip(): return {"success": False, "error": "消息不能为空"}`
2. **移除兜底调用：** 在 `engine.py` 中，当 LLM 规划失败或没有匹配动作时，不再默认调用 `suggest_next_step`。改为返回：
   ```json
   {"success": false, "type": "need_clarification", "final_answer": "抱歉，我没有理解您的需求。请告诉我：您想查看分子数据、分析失败原因，还是调整参数重新运行？"}
   ```
3. **前端空消息拦截：** 在 `HelpChatModal`（或 Copilot 组件）的发送函数中，增加 `if (!message.trim()) return;` 的空消息拦截
4. **可选：** 检查前端是否有自动轮询（如定时器发送空消息），如果有则移除

**文件修改：**
- `backend/services/agent/engine.py`：入口空消息拦截 + 移除 suggest_next_step 兜底
- `frontend/src/components/HelpChatModal.jsx`（或相关 Copilot 组件）：空消息拦截

**预期效果：** 
- 用户无输入时，系统静默。
- 当 Agent 无法规划时，返回诚实提示而非空的成功。

---

### Stage 5: 验证与集成测试（P1，30分钟）

**目标：** 确保所有修改协同工作，不引入回归问题。

**测试用例：**
1. ✅ 用户输入："帮我跑一遍 AKT1 的全流程" → 返回专业报告（含 Top 3 分子数据）
2. ✅ 用户输入："详细数据"（上下文有 project_id=42）→ 返回 Top 3 分子报告
3. ✅ 用户输入："详细报告"（无上下文）→ 返回澄清提示："请提供项目 ID 或靶点名称"
4. ✅ 用户无输入 → 前端不发送，后端不处理（静默）
5. ✅ 用户输入："分析失败原因" → 正常调用 `analyze_failures`
6. ✅ 用户输入："对比分子1和分子2" → 正常调用 `compare_molecules`
7. ✅ 用户输入："hello" → 返回简单聊天回复（不触发任何工具）

**文件修改：** 无新文件，纯测试验证。

---

## 四、时间估算

| 阶段 | 内容 | 时间 | 优先级 |
|------|------|------|--------|
| Stage 1 | 内置格式化报告 | 60分钟 | P0（必须） |
| Stage 2 | 新增格式化工具 | 30分钟 | P1（推荐） |
| Stage 3 | 追问意图解析 | 30分钟 | P1（推荐） |
| Stage 4 | 空消息 + 兜底修复 | 20分钟 | P0（必须） |
| Stage 5 | 验证测试 | 30分钟 | P1（必须） |
| **总计** | | **约170分钟（3小时）** | |

---

## 五、回滚策略

每个阶段修改都是**增量式**的，不影响原有工具逻辑：
- `run_full_pipeline`：只新增 `final_report` 字段，原有字段不变。回滚：去掉 `final_report` 字段即可。
- `format_top_molecules`：新增工具，不影响已有工具。回滚：去掉注册装饰器即可。
- 意图解析：新增 `format_top_molecules` 的映射，原有映射不变。回滚：删除新增规则即可。
- 空消息拦截：新增入口检查。回滚：删除 if 语句即可。
- 兜底修复：移除 `suggest_next_step` 调用。回滚：恢复原来的调用即可。

---

## 六、预期效果（优化后）

### 场景1：一键全流程
```
用户：帮我跑一遍 AKT1 的全流程

Agent：
## AKT1 全流程完成 — 候选分子报告

**项目信息：** ID=42 | 靶点：AKT1 | PDB：4EKL
**执行结果：** 生成50个分子，通过8个，进入 Top 3 候选：

### 🥇 候选分子 #1（综合得分：82.5）
- **SMILES：** `CC(C)N1CCC(Oc2ccc3c(c2)CCN(C2CCC2)C3=O)CC1`
- **分子量：** 342.5 | **LogP：** 3.2 | **QED：** 0.85
- **对接分数：** -9.5 | **ADMET得分：** 78 | **合成难度：** 中等（SA=3.2）
- **特征：** 与已知活性分子 MK-2206 骨架相似，环丙基降低 hERG 风险

### 🥈 候选分子 #2（综合得分：79.2）
...

### 💡 下一步建议
- 候选分子 #1 的 QED（0.85）和 ADMET（78）表现最佳，建议优先进行合成验证
- 分子 #2 的对接分数略低但合成可及性更高（SA=2.8），可作为成本优先的备选
```

### 场景2：追问详细数据
```
用户：给我详细数据

Agent：
（直接返回和上面一样的报告，因为上下文有 project_id=42，自动调用 format_top_molecules）
```

### 场景3：无输入
```
用户：（无输入）

Agent：（静默，无动作）
```

### 场景4：无法理解
```
用户：blablabla

Agent：抱歉，我没有理解您的需求。请告诉我：您想查看分子数据、分析失败原因，还是调整参数重新运行？
```

---

## 七、执行确认

请确认此计划后，我将按 **Stage 1 → Stage 4 → Stage 2 → Stage 3 → Stage 5** 的顺序执行：
1. 先做 P0（内置格式化 + 空消息拦截）——30分钟见效
2. 再做 P1（格式化工具 + 追问意图）——完整体验
3. 最后测试验证

**请确认或提出修改意见。**
