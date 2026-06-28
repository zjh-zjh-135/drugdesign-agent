# DrugDesign Agent 商用级安全与稳定性审计报告

**审计日期**: 2026-06-28
**审计范围**: 全项目代码（backend + frontend + 部署配置）
**审计维度**: 安全、稳定性、AI Agent可靠性、数据一致性、前端安全、部署配置、第三方依赖、密码学、日志安全、业务逻辑
**总计风险**: 81项
**P0（致命）**: 17项
**P1（高危）**: 32项
**P2（中危）**: 32项

---

## 一、P0 致命风险（17项）—— 必须立即修复

### 1.1 认证授权完全缺失（安全）
- **文件**: `backend/routes/*.py` 全量
- **风险**: 所有API公开暴露，无JWT/Session/API Key。任何人可读写删任意项目、执行Agent、删除数据
- **修复**: 引入JWT Bearer Token认证，所有敏感路由添加 `@require_auth` 装饰器

### 1.2 Pickle反序列化RCE（安全）
- **文件**: `backend/services/activity.py:140`
- **风险**: `pickle.load(f)` 加载用户可控路径的`.pkl`文件，可导致任意代码执行
- **修复**: 禁用pickle，改用`skops`或JSON保存模型参数

### 1.3 路径遍历+任意文件读取（安全）
- **文件**: `backend/services/activity.py:103`
- **风险**: `model_name`未sanitize即拼接路径，可构造`../../../etc/passwd`读取任意文件
- **修复**: 对model_name实施白名单：`^[a-zA-Z0-9_-]+$`

### 1.4 subprocess参数注入（安全）
- **文件**: `backend/services/fep_refinement.py:376`
- **风险**: OpenBabel调用中`receptor_pdb`来自用户输入，可能参数注入
- **修复**: 使用subprocess.run的`args`列表而非shell字符串，对输入做sanitize

### 1.5 DEBUG模式开启（安全/部署）
- **文件**: `backend/app.py:87`, `run.py:39`
- **风险**: `debug=True`启用Werkzeug交互式调试器，可导致RCE
- **修复**: `debug = os.environ.get('FLASK_ENV') == 'development'`

### 1.6 dangerouslySetInnerHTML XSS（前端安全）
- **文件**: `frontend/src/pages/SynthesisView.jsx:297`
- **风险**: 直接渲染后端返回的SVG，可内嵌JavaScript，导致存储型XSS
- **修复**: 使用`<img src="data:image/svg+xml;base64,...">`替代内嵌SVG，或DOMPurify消毒

### 1.7 执行循环无全局步数上限（AI Agent）
- **文件**: `backend/services/agent/executor.py:129-191`
- **风险**: `execute_plan()`的while循环没有全局最大步数上限。LLM可通过`decision="modify"`动态追加新步骤，导致"修改-执行-再修改"无限循环
- **修复**: 引入全局`max_execution_steps=15`，超限强制break

### 1.8 工具调用无超时（AI Agent）
- **文件**: `backend/services/agent/executor.py:306-404`
- **风险**: 普通工具调用无任何超时包装。若工具内部阻塞（数据库死锁、外部API无响应），Agent线程永久挂起
- **修复**: 所有工具调用使用`ThreadPoolExecutor`+`future.result(timeout=60)`包装

### 1.9 LLM无max_tokens限制（AI Agent）
- **文件**: `backend/services/agent/llm_client.py:119-242`
- **风险**: 未设置`max_tokens`。LLM可能生成数万token，导致上下文溢出、API费用暴增、响应极长
- **修复**: `ChatOpenAI`初始化时设置`max_tokens=4096`

### 1.10 条件评估回退逻辑缺陷（AI Agent）
- **文件**: `backend/services/agent/executor.py:706-708`
- **风险**: `fallback = "true" in raw.lower() and "false" not in raw.lower()`。LLM返回"The condition is not true"时，`"true"`存在但`"false"`不存在，回退为True，实际应为False
- **修复**: 使用正则`re.search(r'\bresult\b.*?\btrue\b', raw, re.I)`或确定性规则引擎

### 1.11 多意图并行无超时（AI Agent）
- **文件**: `backend/services/agent/engine.py:488-500`
- **风险**: `_execute_multi_intent()`使用`ThreadPoolExecutor`，`as_completed()`无timeout。任一子意图阻塞则整个处理无限等待
- **修复**: `as_completed(futures, timeout=60)`

### 1.12 Token估算不准确导致上下文溢出（AI Agent）
- **文件**: `backend/services/agent/memory.py:42-102`
- **风险**: 使用`total_chars * 0.5`估算token，对中文极不准确。单条超长消息（如完整Pipeline报告）可能远超限制，触发`context length exceeded`
- **修复**: 使用`tiktoken`精确计算token，或引入滑动窗口截断

### 1.13 并发可见性缺陷（稳定性）
- **文件**: `backend/services/pipeline.py:22-62, 706-719`
- **风险**: `_run_pipeline`后台线程修改`self.status`、`self.logs`时不持有锁，而`get_status()`读取时持有锁。可能读取到不一致状态
- **修复**: 所有状态修改操作在`_lock`内执行

### 1.14 SQLite连接共享（稳定性）
- **文件**: `backend/models/database.py:224-229`
- **风险**: `poolclass=StaticPool`使所有线程共享同一连接。SQLite单线程写模型，多线程并发写入导致"database is locked"或长时间阻塞
- **修复**: 使用`QueuePool`或`NullPool`替代`StaticPool`

### 1.15 裸异常吞没关键错误（稳定性）
- **文件**: `backend/services/pipeline.py` 多处（126-127, 188-189, 233, 282-283等）
- **风险**: `_save_molecules`、`_record_failure`等核心操作使用`except Exception: pass`静默失败，数据丢失且无法察觉
- **修复**: 所有裸异常至少记录日志`logger.exception(...)`

### 1.16 LLMClient单例无线程锁（稳定性）
- **文件**: `backend/services/agent/llm_client.py:465-480`
- **风险**: `_DEFAULT_CLIENT`全局变量，`get_default_client()`无锁保护。高并发下可能创建多个实例，缓存不一致、指标统计错乱
- **修复**: 使用`threading.Lock()`保护单例创建

### 1.17 ThreadPoolExecutor并发失控（稳定性）
- **文件**: `backend/services/agent/engine.py:488-499`
- **风险**: 多个线程同时访问数据库和共享`context`字典，加剧SQLite锁竞争
- **修复**: 为每个子意图创建独立的数据库session，不共享context

---

## 二、P1 高危风险（32项）—— 本周修复

### 2.1 数据库事务不完整
- **文件**: `backend/routes/admet.py`, `assay.py`, `molecules.py`, `projects.py`, `synthesis.py`, `generation.py`, `agent.py` 等
- **风险**: 几乎所有写入路由只使用`try...finally`，缺少`except`中的`db.rollback()`。异常时事务未可靠回滚
- **修复**: 统一改为`try...except...finally`结构

### 2.2 SQLite外键约束未启用
- **文件**: `backend/models/database.py:224`
- **风险**: 默认`PRAGMA foreign_keys = OFF`，级联删除依赖ORM而非数据库
- **修复**: 在`create_engine`时添加`connect_args={'timeout': 30}`

### 2.3 批量删除导致孤儿数据
- **文件**: `backend/services/pipeline.py:141-142, 161-164`
- **风险**: `query.delete(synchronize_session=False)`绕过ORM级联，关联的`molecule_properties`、`admet_predictions`等成为孤儿数据
- **修复**: 使用`for mol in query.all(): db.delete(mol)`替代批量删除

### 2.4 Pipeline中断后僵尸状态
- **文件**: `backend/services/pipeline.py:114-121`
- **风险**: 进程崩溃后`PipelineRun`永远停留在`status='running'`，无心跳检测或超时恢复
- **修复**: 启动时扫描`status='running' AND start_time < now - 1 hour`的记录并标记为`failed`

### 2.5 重复数据插入风险
- **文件**: `backend/routes/molecules.py`, `backend/services/pipeline.py:624-644`
- **风险**: 插入前不检查SMILES是否已存在。`Project.name`未设置`unique=True`
- **修复**: 添加唯一约束，插入前查询已存在记录

### 2.6 Vina可执行路径可控
- **文件**: `backend/services/docking.py:76, 277`
- **风险**: `VINA_EXE`来自环境变量，被篡改可执行任意程序
- **修复**: 对VINA_EXE做路径验证，只允许白名单目录

### 2.7 服务器信息泄露
- **文件**: `backend/routes/docking.py:183-196`
- **风险**: `/docking/vina_status`公开返回Vina绝对路径及文件存在性
- **修复**: 返回脱敏信息，不暴露绝对路径

### 2.8 DoS风险
- **文件**: `builder.py:503`, `docking.py:74`
- **风险**: `pdb_content`/`smiles_list`无大小限制，超大输入可导致内存/CPU耗尽
- **修复**: 添加大小限制（如10MB）

### 2.9 弱示例密钥
- **文件**: `.env.example:20`
- **风险**: 硬编码`FLASK_SECRET_KEY=changeme...`，用户复制后易被伪造Session
- **修复**: 在`create_app()`中检测弱密钥并抛出警告

### 2.10 CSRF防护缺失
- **文件**: `backend/app.py:32-39`
- **风险**: `supports_credentials=True`但无CSRF Token
- **修复**: 对写操作路由添加CSRF Token验证

### 2.11 日志脱敏不完整
- **文件**: `backend/utils/security.py:235`
- **风险**: 仅排除`password/token/api_key/secret`，未覆盖`kimi_api_key`等变体
- **修复**: 扩展脱敏关键词列表

### 2.12 追踪数据明文存储
- **文件**: `backend/services/agent/tracer.py:371`
- **风险**: 敏感参数可能以明文写入`.traces/agent_traces.jsonl`
- **修复**: 对敏感字段做脱敏处理

### 2.13 审计日志无管理
- **文件**: `backend/utils/security.py:40`
- **风险**: 无查询接口、无自动清理、无加密
- **修复**: 添加日志轮转和清理策略

### 2.14 LIKE模糊查询性能/DoS
- **文件**: `backend/services/pipeline.py:79`, `memory.py:257`
- **风险**: `contains()`生成`%search%`，无长度限制，大数据量全表扫描
- **修复**: 添加搜索长度限制，使用全文索引

### 2.15 模块级init_db
- **文件**: `backend/routes/pipeline.py:9`
- **风险**: `SessionLocal = init_db()`在导入时执行，数据库故障导致应用无法启动
- **修复**: 延迟初始化，首次请求时创建

### 2.16 Session创建不一致
- **文件**: `backend/routes/agent.py`等
- **风险**: `get_db()`每次请求创建新engine，与`pipeline.py`全局`SessionLocal`混用
- **修复**: 统一使用依赖注入的`get_db()`

### 2.17 子进程不检查returncode
- **文件**: `backend/services/admet.py:95-115`
- **风险**: 不检查ADMET-AI子进程退出码，无法区分"无数据"和"子进程崩溃"
- **修复**: 检查`proc.returncode != 0`时记录错误

### 2.18 重试判断脆弱
- **文件**: `backend/services/agent/llm_client.py:260-267`
- **风险**: `result.startswith("LLM 调用失败")`判断成功/失败，格式变化即失效
- **修复**: 使用异常类替代字符串匹配

### 2.19 rate_limit_store内存泄漏
- **文件**: `backend/utils/security.py:35, 121-125`
- **风险**: 全局字典无上限，每次请求遍历所有key清理过期记录
- **修复**: 使用TTL缓存库替代全局字典

### 2.20 异常信息暴露
- **文件**: `backend/routes/agent.py:145-146, 221-222`
- **风险**: `return jsonify({'error': str(e)})`将原始异常返回客户端，可能泄露敏感路径
- **修复**: 生产环境返回通用错误消息，详细错误记录日志

### 2.21 临时目录清理失败静默忽略
- **文件**: `backend/services/docking.py:298-304`
- **风险**: `shutil.rmtree`失败被`except Exception: pass`吞没，长期磁盘泄漏
- **修复**: 记录清理失败日志

### 2.22 流式响应异常不完整
- **文件**: `backend/routes/ai_chat.py:145-181`
- **风险**: 异常时yield错误消息，但客户端可能仍等待SSE终止标记
- **修复**: 确保异常时yield终止标记

### 2.23 _is_simple_chat重复调用LLM
- **文件**: `backend/services/agent/engine.py:665-744`
- **风险**: 每次分类都调用`call_llM()`，消耗API配额和延迟
- **修复**: 缓存分类结果，相同消息不重复调用

### 2.24 清理操作无事务保护
- **文件**: `backend/services/pipeline.py:130-169`
- **风险**: `synchronize_session=False`的delete在异常中无日志，并发删除可能冲突
- **修复**: 添加事务保护和日志

### 2.25 上下文膨胀
- **文件**: `backend/services/agent/executor.py:711-744`
- **风险**: `_format_execution_history`将完整执行历史拼接为提示词，单条observation可能数千token
- **修复**: observation限制到1000字符，大数组只保留前3个元素

### 2.26 实例非线程安全
- **文件**: `backend/services/agent/engine.py:988-1000`
- **风险**: `_last_project_id`和`_last_target`无线程锁，多用户同时调用可能被覆盖
- **修复**: 使用`threading.Lock()`保护或改为session级存储

### 2.27 单例metrics竞争
- **文件**: `backend/services/agent/llm_client.py:465-480`
- **风险**: `metrics`通过`+=`实现，非原子操作，多线程并发时统计值竞争污染
- **修复**: 使用`threading.Lock()`保护metrics更新

### 2.28 追踪器全局覆盖
- **文件**: `backend/services/agent/tracer.py:269`
- **风险**: `_current_tracer`是类级变量，多线程下被最后一个线程覆盖
- **修复**: 使用`threading.local()`存储当前tracer

### 2.29 daemon线程不可靠
- **文件**: `backend/services/agent/tools.py:226-252`
- **风险**: `daemon=True`，主进程退出时强制终止，Pipeline可能执行到一半中断
- **修复**: 使用Celery/RQ替代daemon线程

### 2.30 新步骤未校验工具名
- **文件**: `backend/services/agent/executor.py:174-181`
- **风险**: `decision="modify"`时新步骤仅过滤`s.get("tool")`，未验证工具名是否在注册表中
- **修复**: 对新步骤执行工具名校验

### 2.31 第三方依赖漏洞（新增）
- **文件**: `requirements.txt:1-17`
- **风险**: `urllib3==2.2.0`存在CVE-2024-37891（代理授权头泄露），`pillow==10.2.0`存在多个漏洞，整体依赖未定期更新
- **修复**: 升级`urllib3>=2.2.2`，`pillow>=10.3.0`，定期运行`pip-audit`

### 2.32 端口绑定暴露在所有接口（新增）
- **文件**: `docker-compose.yml:9`, `render.yaml:11`, `Dockerfile:31`, `app.py:87`, `run.py:39`
- **风险**: `ports: - "5000:5000"`未绑定到`127.0.0.1`，`gunicorn -b 0.0.0.0:5000`暴露在所有接口，配合`debug=True`可能导致生产环境RCE
- **修复**: Docker绑定`127.0.0.1:5000:5000`，生产环境`gunicorn -b 127.0.0.1:5000`

### 2.1 数据库事务不完整
- **文件**: `backend/routes/admet.py`, `assay.py`, `molecules.py`, `projects.py`, `synthesis.py`, `generation.py`, `agent.py` 等
- **风险**: 几乎所有写入路由只使用`try...finally`，缺少`except`中的`db.rollback()`。异常时事务未可靠回滚
- **修复**: 统一改为`try...except...finally`结构

### 2.2 SQLite外键约束未启用
- **文件**: `backend/models/database.py:224`
- **风险**: 默认`PRAGMA foreign_keys = OFF`，级联删除依赖ORM而非数据库
- **修复**: 在`create_engine`时添加`connect_args={'timeout': 30}`

### 2.3 批量删除导致孤儿数据
- **文件**: `backend/services/pipeline.py:141-142, 161-164`
- **风险**: `query.delete(synchronize_session=False)`绕过ORM级联，关联的`molecule_properties`、`admet_predictions`等成为孤儿数据
- **修复**: 使用`for mol in query.all(): db.delete(mol)`替代批量删除

### 2.4 Pipeline中断后僵尸状态
- **文件**: `backend/services/pipeline.py:114-121`
- **风险**: 进程崩溃后`PipelineRun`永远停留在`status='running'`，无心跳检测或超时恢复
- **修复**: 启动时扫描`status='running' AND start_time < now - 1 hour`的记录并标记为`failed`

### 2.5 重复数据插入风险
- **文件**: `backend/routes/molecules.py`, `backend/services/pipeline.py:624-644`
- **风险**: 插入前不检查SMILES是否已存在。`Project.name`未设置`unique=True`
- **修复**: 添加唯一约束，插入前查询已存在记录

### 2.6 Vina可执行路径可控
- **文件**: `backend/services/docking.py:76, 277`
- **风险**: `VINA_EXE`来自环境变量，被篡改可执行任意程序
- **修复**: 对VINA_EXE做路径验证，只允许白名单目录

### 2.7 服务器信息泄露
- **文件**: `backend/routes/docking.py:183-196`
- **风险**: `/docking/vina_status`公开返回Vina绝对路径及文件存在性
- **修复**: 返回脱敏信息，不暴露绝对路径

### 2.8 DoS风险
- **文件**: `builder.py:503`, `docking.py:74`
- **风险**: `pdb_content`/`smiles_list`无大小限制，超大输入可导致内存/CPU耗尽
- **修复**: 添加大小限制（如10MB）

### 2.9 弱示例密钥
- **文件**: `.env.example:20`
- **风险**: 硬编码`FLASK_SECRET_KEY=changeme...`，用户复制后易被伪造Session
- **修复**: 在`create_app()`中检测弱密钥并抛出警告

### 2.10 CSRF防护缺失
- **文件**: `backend/app.py:32-39`
- **风险**: `supports_credentials=True`但无CSRF Token
- **修复**: 对写操作路由添加CSRF Token验证

### 2.11 日志脱敏不完整
- **文件**: `backend/utils/security.py:235`
- **风险**: 仅排除`password/token/api_key/secret`，未覆盖`kimi_api_key`等变体
- **修复**: 扩展脱敏关键词列表

### 2.12 追踪数据明文存储
- **文件**: `backend/services/agent/tracer.py:371`
- **风险**: 敏感参数可能以明文写入`.traces/agent_traces.jsonl`
- **修复**: 对敏感字段做脱敏处理

### 2.13 审计日志无管理
- **文件**: `backend/utils/security.py:40`
- **风险**: 无查询接口、无自动清理、无加密
- **修复**: 添加日志轮转和清理策略

### 2.14 LIKE模糊查询性能/DoS
- **文件**: `backend/services/pipeline.py:79`, `memory.py:257`
- **风险**: `contains()`生成`%search%`，无长度限制，大数据量全表扫描
- **修复**: 添加搜索长度限制，使用全文索引

### 2.15 模块级init_db
- **文件**: `backend/routes/pipeline.py:9`
- **风险**: `SessionLocal = init_db()`在导入时执行，数据库故障导致应用无法启动
- **修复**: 延迟初始化，首次请求时创建

### 2.16 Session创建不一致
- **文件**: `backend/routes/agent.py`等
- **风险**: `get_db()`每次请求创建新engine，与`pipeline.py`全局`SessionLocal`混用
- **修复**: 统一使用依赖注入的`get_db()`

### 2.17 子进程不检查returncode
- **文件**: `backend/services/admet.py:95-115`
- **风险**: 不检查ADMET-AI子进程退出码，无法区分"无数据"和"子进程崩溃"
- **修复**: 检查`proc.returncode != 0`时记录错误

### 2.18 重试判断脆弱
- **文件**: `backend/services/agent/llm_client.py:260-267`
- **风险**: `result.startswith("LLM 调用失败")`判断成功/失败，格式变化即失效
- **修复**: 使用异常类替代字符串匹配

### 2.19 rate_limit_store内存泄漏
- **文件**: `backend/utils/security.py:35, 121-125`
- **风险**: 全局字典无上限，每次请求遍历所有key清理过期记录
- **修复**: 使用TTL缓存库替代全局字典

### 2.20 异常信息暴露
- **文件**: `backend/routes/agent.py:145-146, 221-222`
- **风险**: `return jsonify({'error': str(e)})`将原始异常返回客户端，可能泄露敏感路径
- **修复**: 生产环境返回通用错误消息，详细错误记录日志

### 2.21 临时目录清理失败静默忽略
- **文件**: `backend/services/docking.py:298-304`
- **风险**: `shutil.rmtree`失败被`except Exception: pass`吞没，长期磁盘泄漏
- **修复**: 记录清理失败日志

### 2.22 流式响应异常不完整
- **文件**: `backend/routes/ai_chat.py:145-181`
- **风险**: 异常时yield错误消息，但客户端可能仍等待SSE终止标记
- **修复**: 确保异常时yield终止标记

### 2.23 _is_simple_chat重复调用LLM
- **文件**: `backend/services/agent/engine.py:665-744`
- **风险**: 每次分类都调用`call_llm()`，消耗API配额和延迟
- **修复**: 缓存分类结果，相同消息不重复调用

### 2.24 清理操作无事务保护
- **文件**: `backend/services/pipeline.py:130-169`
- **风险**: `synchronize_session=False`的delete在异常中无日志，并发删除可能冲突
- **修复**: 添加事务保护和日志

### 2.25 上下文膨胀
- **文件**: `backend/services/agent/executor.py:711-744`
- **风险**: `_format_execution_history`将完整执行历史拼接为提示词，单条observation可能数千token
- **修复**: observation限制到1000字符，大数组只保留前3个元素

### 2.26 实例非线程安全
- **文件**: `backend/services/agent/engine.py:988-1000`
- **风险**: `_last_project_id`和`_last_target`无线程锁，多用户同时调用可能被覆盖
- **修复**: 使用`threading.Lock()`保护或改为session级存储

### 2.27 单例metrics竞争
- **文件**: `backend/services/agent/llm_client.py:465-480`
- **风险**: `metrics`通过`+=`实现，非原子操作，多线程并发时统计值竞争污染
- **修复**: 使用`threading.Lock()`保护metrics更新

### 2.28 追踪器全局覆盖
- **文件**: `backend/services/agent/tracer.py:269`
- **风险**: `_current_tracer`是类级变量，多线程下被最后一个线程覆盖
- **修复**: 使用`threading.local()`存储当前tracer

### 2.29 daemon线程不可靠
- **文件**: `backend/services/agent/tools.py:226-252`
- **风险**: `daemon=True`，主进程退出时强制终止，Pipeline可能执行到一半中断
- **修复**: 使用Celery/RQ替代daemon线程

### 2.30 新步骤未校验工具名
- **文件**: `backend/services/agent/executor.py:174-181`
- **风险**: `decision="modify"`时新步骤仅过滤`s.get("tool")`，未验证工具名是否在注册表中
- **修复**: 对新步骤执行工具名校验

---

## 三、P2 中危风险（28项）—— 后续修复

### 3.1-3.5 大量裸异常无日志
- **文件**: `engine.py`, `executor.py`, `tools.py`, `pipeline.py`, `utils.py`等
- **风险**: 几十个文件中裸异常捕获不记录日志，无法追溯
- **修复**: 统一日志记录

### 3.6 json.loads无防护
- **文件**: `backend/services/agent/memory.py:171, 267`
- **风险**: `json.loads(r.value)`数据损坏时抛出JSONDecodeError
- **修复**: 添加try/except并记录错误

### 3.7 代码错误
- **文件**: `backend/routes/builder.py:336-339`
- **风险**: `Math.PI`（JavaScript风格）在Python中应为`math.pi`
- **修复**: 修正为`math.pi`

### 3.8 init_db重复调用
- **文件**: `backend/models/database.py`等
- **风险**: 多处创建新engine，资源浪费
- **修复**: 缓存engine实例

### 3.9 job_id冲突
- **文件**: `backend/services/pipeline.py:51`
- **风险**: 秒级时间戳，同一秒内提交会覆盖`_running_jobs`
- **修复**: 使用`uuid`或纳秒级时间戳

### 3.10 审计日志二次读取请求体
- **文件**: `backend/utils/security.py:232`
- **风险**: `request.get_json()`在finally中可能二次读取
- **修复**: 提前读取并缓存请求体

### 3.11 MMFF优化失败被忽略
- **文件**: `backend/routes/builder.py:91-105`
- **风险**: 无日志记录，无法排查RDKit配置问题
- **修复**: 记录失败原因

### 3.12 知识问答误判
- **文件**: `backend/services/agent/engine.py:689-691`
- **风险**: 只要消息含靶点名就判定为非聊天，"什么是EGFR？"被误判
- **修复**: 结合上下文关键词双重判断

### 3.13 输入无截断
- **文件**: `backend/services/agent/executor.py:528-569`
- **风险**: `_query_llm_final`对输入无长度限制
- **修复**: 强制截断到最大token预算

### 3.14 无连接池
- **文件**: `backend/services/agent/tools.py:29-33`
- **风险**: `_get_db()`每次创建新session
- **修复**: 使用SQLAlchemy连接池

### 3.15 对象重复创建
- **文件**: `backend/services/agent/engine.py:270-272`
- **风险**: 每次请求新建`IntentParser`实例
- **修复**: 预创建并复用

### 3.16 配置不一致
- **文件**: `config.py:38` + `executor.py:26`
- **风险**: `STEP_TIMEOUT`硬编码300，不读取环境变量
- **修复**: 从配置读取

### 3.17 记忆无限增长
- **文件**: `backend/services/agent/memory.py:104-127, 223-247`
- **风险**: 只增不减，长期运行后无限膨胀
- **修复**: 添加自动清理策略（90天保留期）

### 3.18 条件评估范围窄
- **文件**: `backend/services/agent/executor.py:611-709`
- **风险**: 只检查`last_obs`，无法引用更早步骤数据
- **修复**: 遍历所有历史步骤

### 3.19 异常笼统捕获
- **文件**: `backend/services/agent/engine.py:337-467`
- **风险**: 系统异常被当作业务异常返回，掩盖严重问题
- **修复**: 区分业务异常和系统异常

### 3.20 步骤重复执行
- **文件**: `backend/services/agent/executor.py:129-191`
- **风险**: `decision="modify"`时可能重复执行相同工具
- **修复**: 记录已执行工具签名，检测到重复时跳过

### 3.21 缺少Content-Security-Policy
- **文件**: `backend/utils/security.py:20-26`
- **风险**: 缺少CSP，XSS发生时无第二道防线
- **修复**: 添加CSP头

### 3.22 CORS允许空Origin
- **文件**: `backend/utils/security.py:98-107`
- **风险**: 允许无Origin头的请求
- **修复**: 生产环境拒绝空Origin

### 3.23 .env文件权限
- **文件**: `run.py:8-24`
- **风险**: 手动解析.env，权限配置不当可被其他用户读取
- **修复**: 使用python-dotenv，确保文件权限600

### 3.24 API Key延迟读取
- **文件**: `backend/services/agent/config.py:21`
- **风险**: 导入时读取环境变量，可能.env未加载完
- **修复**: 延迟读取（property方式）

### 3.25 缺少HTTPS强制
- **文件**: `docker-compose.yml:8-9`, `render.yaml:11`
- **风险**: 明文HTTP传输，API Key可能被窃听
- **修复**: 添加HSTS头，配置反向代理HTTPS

### 3.26 代码错误导致信息泄露
- **文件**: `backend/routes/docking.py:196`
- **风险**: 缺少`import os`，访问时触发NameError，debug=True下泄露堆栈
- **修复**: 添加`import os`，关闭debug模式

### 3.27 工具返回字符串而非异常
- **文件**: `backend/services/agent/llm_client.py:232-242`
- **风险**: 错误返回字符串，调用方当作正常JSON解析，默认返回"continue"
- **修复**: 定义异常类，失败时抛出

### 3.28 主入口无整体超时
- **文件**: `backend/services/agent/engine.py:232-335`
- **风险**: `run()`无整体超时，任一阶段卡住则HTTP请求永久阻塞
- **修复**: 添加120秒整体超时

### 3.29 MD5弱哈希使用（密码学）
- **文件**: `backend/services/agent/llm_client.py:458`
- **风险**: 使用`hashlib.md5`生成缓存键，MD5属于密码学弱哈希
- **修复**: 改用`hashlib.sha256`或`blake2b`

### 3.30 日志文件无轮转（日志安全）
- **文件**: `backend.log`（根目录）
- **风险**: 无`RotatingFileHandler`，日志文件无限增长
- **修复**: 添加日志轮转，最大10MB保留5个备份

### 3.31 日志文件权限未限制（日志安全）
- **文件**: `backend.log`
- **风险**: Windows默认所有人可读，可能泄露敏感信息
- **修复**: 限制文件权限为600

### 3.32 删除操作缺少确认（业务逻辑）
- **文件**: `backend/routes/projects.py:228`, `backend/routes/molecules.py:199`
- **风险**: DELETE直接级联删除，无二次确认或软删除
- **修复**: 添加软删除（deleted_at字段）或要求确认Token

---

## 四、修复优先级矩阵

| 优先级 | 风险数 | 核心问题 | 预计工作量 |
|--------|--------|----------|------------|
| P0（立即） | 17 | 安全漏洞、无限循环、无超时、token溢出、并发缺陷 | ~40h |
| P1（本周） | 32 | 事务不完整、外键缺失、僵尸任务、信息泄露、依赖漏洞、端口暴露 | ~28h |
| P2（后续） | 32 | 日志缺失、配置不一致、性能优化、代码错误、MD5弱哈希、日志无轮转 | ~18h |
| **总计** | **81** | | **~86h** |

---

## 五、商用达标 checklist

要达到商用级别，必须完成：

- [ ] P0全部修复（17项）
- [ ] P1全部修复（30项）
- [ ] 添加自动化安全测试（SAST/DAST）
- [ ] 添加性能基准测试
- [ ] 添加负载测试（并发用户）
- [ ] 添加灾难恢复测试（进程崩溃后数据一致性）
- [ ] 通过第三方安全审计
- [ ] 获得SOC 2或ISO 27001合规认证（如面向企业客户）

当前状态：距离商用级别还有**约80小时**的开发工作量。
