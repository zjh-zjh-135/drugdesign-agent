# P0 优化计划：隐藏工具调用 + 修复重复输出 + None 值处理

## 一、问题诊断（从用户测试结果）

### 问题1：暴露工具调用内部实现（前端渲染问题）

**当前输出：**
```
## 🎯 AKT1 全流程完成 — 候选分子报告 ... 执行完成，详见下方报告。

Copilot
自主执行

执行步骤
Step 1: 用户请求运行 AKT1 的全流程...
Action: run_full_pipeline({"target_name":"AKT1"})
Status: ok

执行报告
成功
```

**问题：** 用户看到了 "Step 1"、"Action"、"Status"、"执行报告" 等内部工具调用细节。这不是用户关心的内容，这是工程师的调试输出，不应该出现在用户界面中。

**根因：** 前端渲染了 `steps` 数组和 `action_cards`，同时显示了 "Copilot 自主执行" 标签和 "执行报告" 标签。这些原本是为了展示 Agent 的 "工作过程"，但实际上增加了信息噪音，干扰了用户对最终结果的阅读。

### 问题2：重复内容输出

**当前输出：**
```
## 🎯 AKT1 全流程完成 — 候选分子报告 ... 执行完成，详见下方报告。

[中间夹杂了工具调用步骤]

## 🎯 AKT1 全流程完成 — 候选分子报告
[完整的报告内容再次出现]
```

**问题：** 报告内容出现了两次——第一次是 `final_answer`（LLM 总结）的预览，第二次是 `final_report`（详细报告）的完整展示。中间还被工具调用步骤打断。

**根因：** 前端同时渲染了 `final_answer`（在消息卡片中）和 `final_report`（可能展开在下方）。当 `final_report` 存在时，`final_answer` 应该退化为一句话摘要，不应该展示完整内容。

### 问题3：None 值显示

**当前输出：**
```
- **对接分数**：None | **ADMET 得分**：81.86 | **SA Score**：3.8
```

**问题：** 数据库中对接分数为空时直接显示 `None`，这既不专业也不友好。用户可能困惑：是对接分数还没算？还是算出来就是 None？

**根因：** 格式化报告中没有处理 `None` 值，直接传递了 Python 的 `None` 到 Markdown 中。同样的问题也存在于 `get_top_molecules` 的格式化输出中。

---

## 二、优化方案

### 方案1：隐藏工具调用过程（前端 + 后端）

**目标：** 用户只看到一个简洁的状态提示和最终报告，看不到任何内部工具调用。

**具体做法：**

**前端（聊天组件）：**
1. 当后端返回包含 `final_report` 时，隐藏整个 "执行步骤" 展开区域（或默认折叠）
2. 移除 "Copilot 自主执行" 的独立标签，改为在消息顶部显示一个小的状态徽章（如 🟢 已完成）
3. "执行报告" 标题改为更简洁的 "分析结果" 或直接省略标题
4. 只展示 `final_answer` 的摘要（一句话）和 `final_report` 的完整内容

**后端（engine.py）：**
1. 当执行单个工具且该工具返回 `final_report` 时，在 `final_answer` 中只返回一句话摘要
2. 保留 `steps` 和 `action_cards` 在 JSON 中（供前端调试用），但默认不展示

**预期效果：**
```
🤖 正在分析 AKT1 全流程...

→ 显示：AKT1 全流程完成，生成 50 个分子，通过 7 个。查看下方详细报告。

[展开后的完整报告]
## 🎯 AKT1 全流程完成 — 候选分子报告
...
```

---

### 方案2：修复重复输出（前端优先 + 后端辅助）

**目标：** 当存在 `final_report` 时，`final_answer` 只显示一句话，不重复报告内容。

**具体做法：**

**后端（executor.py）：**
1. 在 `to_report` 中，如果 `log.final_answer` 很长（>200字）且包含 `final_report`（或通过工具类型判断），将 `chat_summary` 限制为一句话摘要
2. 修改摘要逻辑：`if final_answer contains "候选分子报告" and has final_report: chat_summary = "分析完成，请查看下方详细报告。"`

**前端（聊天组件）：**
1. 当消息数据中包含 `final_report` 时，`final_answer` 的渲染只显示前 100 字 + "..."，不展开完整内容
2. `final_report` 作为主要渲染内容，始终展开显示
3. 如果 `final_answer` 和 `final_report` 开头内容相似（>50% 重叠），优先只展示 `final_report`

**预期效果：** 用户只看到一个简洁的摘要和一份完整的报告，没有重复。

---

### 方案3：None 值显示修复（后端格式化）

**目标：** 所有空值统一显示为 "待计算" 或 "N/A"，不暴露 Python 的 `None`。

**具体做法：**

**后端（tools.py 的 `_build_full_pipeline_report` 和 `format_top_molecules`）：**
1. 在格式化报告函数中，所有字段统一使用安全取值函数：
   ```python
   def _safe_value(val, default="N/A", suffix=""):
       if val is None or val == "N/A":
           return default
       return f"{val}{suffix}"
   ```
2. 对接分数、ADMET 得分、SA Score 等字段，如果为 `None`：
   - 如果是因为 Pipeline 中该模块未启用 → 显示 "待计算（对接模块未启用）"
   - 如果是其他原因 → 显示 "N/A"
3. 在 `get_top_molecules` 返回的 JSON 中也做同样处理，防止 `executor.py` 中的格式化器也遇到问题

**后端（executor.py 的各格式化函数）：**
1. `_format_top_molecules` 中同样修复 `None` 值处理
2. `_format_run_full_pipeline` 中同样修复（已在上一轮修复过，但可能有遗漏）

**预期效果：**
```
- **对接分数**：待计算（对接模块未启用） | **ADMET 得分**：81.86 | **SA Score**：3.8
```

---

## 三、实施顺序（共 4 个阶段，预计 90 分钟）

### Stage 1：后端 None 值修复（20分钟）

1. 在 `tools.py` 中，为 `_build_full_pipeline_report` 和 `format_top_molecules` 添加 `_safe_value` 辅助函数
2. 替换所有 `mol.get(

---

## 三、实施顺序（共 4 个阶段，预计 90 分钟）

### Stage 1：后端 None 值修复（20分钟）

**文件：** `backend/services/agent/tools.py` + `backend/services/agent/executor.py`

**具体步骤：**
1. 在 `tools.py` 中，为 `_build_full_pipeline_report` 和 `format_top_molecules` 添加 `_safe_value` 辅助函数
2. 替换所有直接取值，改为安全取值：
   - `mol.get("docking_score", "N/A")` → `mol.get("docking_score")` 或 `"N/A"`（如果为 None）
   - 在格式化字符串中，统一显示 "待计算" 或 "N/A"
3. 在 `executor.py` 的 `_format_top_molecules` 和 `_format_run_full_pipeline` 中同样修复

**验收标准：** 测试时所有字段为 `None` 时不报错，显示为 "N/A" 或 "待计算"。

---

### Stage 2：后端修复重复输出（15分钟）

**文件：** `backend/services/agent/executor.py`（`to_report` 方法）

**具体步骤：**
1. 在 `to_report` 中，检查 `log.final_answer` 是否被 `_enrich_final_answer` 增强过（即是否被强制格式化）
2. 如果被增强过，将 `chat_summary` 设置为一句话摘要：
   ```python
   if enriched_answer and len(enriched_answer) > 200:
       chat_summary = "分析完成，请查看下方详细报告。"
   ```
3. 或者直接：如果 `log.steps` 最后一步的工具是 `run_full_pipeline` 或 `analyze_single_molecule_admet`，强制 `chat_summary` 为一句话摘要

**验收标准：** 用户收到后端返回时，`final_answer` 不超过 30 字，而 `final_report` 包含完整报告。

---

### Stage 3：前端隐藏工具调用（30分钟）

**文件：** `frontend/src/components/HelpChatModal.jsx`（或前端消息渲染组件）

**具体步骤：**
1. 找到消息渲染逻辑，当消息数据包含 `final_report` 时：
   - 隐藏 "执行步骤" 展开区域（或默认折叠为可点击的小箭头）
   - 隐藏 "Copilot 自主执行" 标签
   - 隐藏 "执行报告" 标题
2. 将 `final_report` 作为主要渲染内容，直接展开显示
3. `final_answer` 只渲染为一句话摘要（顶部显示）

**如果无法找到前端组件：** 改为在后端处理——当 `final_report` 存在时，将 `final_answer` 设为一句话，并将 `steps` 设为空数组。

**验收标准：** 用户界面只显示 "分析完成，请查看下方详细报告。" + 完整报告，不显示任何步骤。

---

### Stage 4：验证测试（25分钟）

**测试用例：**
1. ✅ 用户输入："帮我跑一遍 AKT1 的全流程" → 只显示一句话摘要 + 完整报告，不显示步骤
2. ✅ 用户输入："测试 XXX 的 ADMET 数据" → 只显示一句话摘要 + 完整报告，不显示步骤
3. ✅ 报告中没有 `None` 值，所有空值显示为 "N/A" 或 "待计算"
4. ✅ 没有重复内容（final_answer 不重复 final_report 的内容）
5. ✅ 正常对话（如 "你好"）不受影响，仍然正常显示

---

## 四、回滚策略

- **Stage 1：** 只修改格式化函数中的取值逻辑，不涉及工具核心逻辑。回滚：删除 `_safe_value` 调用，恢复原来的取值方式。
- **Stage 2：** 只修改 `to_report` 中的摘要生成逻辑。回滚：恢复原来的 `chat_summary` 生成逻辑。
- **Stage 3：** 前端修改。回滚：恢复原来的渲染条件判断。

---

## 五、预期效果（优化后）

### 用户输入："帮我跑一遍 AKT1 的全流程"

**优化前：**
```
## 🎯 AKT1 全流程完成 — 候选分子报告 ... 执行完成，详见下方报告。

Copilot
自主执行

执行步骤
Step 1: 用户请求运行 AKT1 的全流程...
Action: run_full_pipeline({"target_name":"AKT1"})
Status: ok

执行报告
成功

## 🎯 AKT1 全流程完成 — 候选分子报告
[完整报告内容]
```

**优化后：**
```
✅ 分析完成，请查看下方详细报告。

## 🎯 AKT1 全流程完成 — 候选分子报告

**项目信息**：ID=47 | 靶点：AKT1 | PDB：4EKL
...

### 🥇 候选分子 #1（综合得分：109.29）
- **SMILES**：`CC(C)n1nccc1NC(=O)c1ccc2c(c1)CCN(C1CCC1)C2=O`
- **分子量 (MW)**：352.44 | **LogP**：3.27 | **QED**：0.918
- **对接分数**：待计算 | **ADMET 得分**：81.86 | **SA Score**：3.8
...
```

---

## 六、执行确认

请确认此计划后，按 **Stage 1 → Stage 2 → Stage 3 → Stage 4** 顺序执行。

**确认方式：** 回复 "执行" 或提出修改意见。
