# 小分子药物设计Agent

面向真实落地的闭环Pipeline方案，从 Hit/Lead Generation 到 Lead Optimization。

## 项目架构

### 8层闭环Pipeline（参考PPT架构）
1. **输入层**: 靶点与项目定义 + 已知活性分子上传
2. **生成层**: 基于CReM/RDKit的分子变异生成
3. **基础过滤层**: PAINS + 药物样性规则（Lipinski/Veber）+ SA Score
4. **结构筛选层**: Morgan指纹Tanimoto相似性
5. **ADMET层**: 溶解度/渗透性/BBB/hERG/Ames/DILI/CYP/口服BA预测
6. **精筛层**: 综合评分排序（QED + ADMET + 相似性 + SA Score）
7. **合成层**: 逆合成路线分析（AiZynthFinder接口）
8. **输出层**: Top候选分子导出 + SVG结构可视化

## 技术栈

### 后端
- **框架**: Flask 3.1 + Flask-CORS
- **数据库**: SQLite + SQLAlchemy 2.0 ORM
- **化学计算**: RDKit 2023.9, CReM, AiZynthFinder
- **机器学习**: scikit-learn, torch
- **Python**: 3.11

### 前端
- **框架**: React 19 + Vite 6
- **样式**: Tailwind CSS 3.4
- **图表**: Recharts 2.15
- **图标**: Lucide React
- **HTTP**: Axios

## 目录结构

```
drugdesign-agent/
├── backend/                    # Flask后端
│   ├── app.py                  # 主入口
│   ├── config.py             # 配置
│   ├── models/
│   │   └── database.py       # SQLAlchemy模型
│   ├── services/             # 业务逻辑
│   │   ├── utils.py          # RDKit工具函数
│   │   ├── generation.py     # 分子生成引擎
│   │   ├── filtering.py      # 过滤引擎
│   │   ├── admet.py          # ADMET预测
│   │   ├── docking.py        # 结构筛选
│   │   ├── synthesis.py      # 逆合成分析
│   │   └── pipeline.py       # Pipeline编排器
│   ├── routes/               # API路由
│   │   ├── system.py
│   │   ├── projects.py
│   │   ├── molecules.py
│   │   ├── generation.py
│   │   ├── admet.py
│   │   ├── synthesis.py
│   │   ├── pipeline.py
│   │   └── filtering.py
│   └── static/molecules/     # 分子SVG图片
├── frontend/                   # React前端
│   ├── src/
│   │   ├── main.jsx
│   │   ├── App.jsx
│   │   ├── api/client.js
│   │   ├── store/AppContext.jsx
│   │   ├── components/       # 共享组件
│   │   └── pages/            # 页面
│   └── dist/                 # 构建产物
├── run.py                      # 启动脚本
└── plan.md                     # 开发计划
```

## 快速启动

### 1. 环境要求
- conda (Anaconda/Miniconda)
- Node.js 18+ (前端开发)
- Python 3.11 (在conda虚拟环境 `drugdesign` 中)

### 2. 启动后端

```bash
# 激活conda环境
conda activate drugdesign

# 进入项目目录
cd C:\Users\31517\Desktop\KIMIPRO\drugdesign-agent

# 启动Flask后端
python run.py
```

后端将在 http://localhost:5000 运行。

### 3. 启动前端（开发模式）

```bash
# 进入前端目录
cd frontend

# 安装依赖（如未安装）
npm install

# 启动开发服务器
npm run dev
```

前端将在 http://localhost:5173 运行，API请求自动代理到 localhost:5000。

### 4. 构建前端（生产环境）

```bash
cd frontend
npm run build
```

## API端点

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | /api/health | 健康检查 |
| GET | /api/projects | 项目列表 |
| POST | /api/projects | 创建项目 |
| GET | /api/projects/:id | 项目详情 |
| POST | /api/projects/:id/active_molecules | 上传活性分子 |
| GET | /api/projects/:id/molecules | 分子列表 |
| POST | /api/projects/:id/generate | 启动生成 |
| GET | /api/molecules/:id | 分子详情 |
| GET | /api/molecules/:id/svg | 分子SVG图片 |
| GET | /api/molecules/:id/admet | ADMET预测 |
| POST | /api/molecules/:id/synthesis | 逆合成分析 |
| POST | /api/pipeline/run | 运行完整Pipeline |
| GET | /api/pipeline/status/:id | Pipeline状态 |
| GET | /api/pipeline/results/:id | Pipeline结果 |

## 使用流程

1. **创建项目**: 进入"项目列表"，点击"新建项目"，填写靶点信息
2. **上传活性分子**: 在项目详情页，输入SMILES列表并上传
3. **配置Pipeline**: 设置生成分子数、策略、过滤参数等
4. **运行Pipeline**: 点击"运行Pipeline"，等待8层处理完成
5. **浏览分子**: 在"分子浏览器"中查看筛选后的分子
6. **ADMET分析**: 查看毒性风险、性质分布、散点图
7. **合成分析**: 选择候选分子进行逆合成路线评估
8. **结果导出**: 导出CSV格式的Top候选分子列表

## 默认过滤阈值

| 参数 | 最小值 | 最大值 |
|------|--------|--------|
| MW | 250 | 550 |
| LogP | 0 | 5 |
| TPSA | 40 | 120 |
| HBD | - | 5 |
| HBA | - | 10 |
| RotB | - | 10 |
| SA Score | - | 4.5 |

## 核心功能说明

### 分子生成
- 支持CReM片段替换、RDKit枚举、骨架替换三种策略
- 基于已知活性分子生成analogs
- 默认生成1000-5000个变体

### 过滤引擎
- PAINS过滤（使用RDKit FilterCatalog）
- Brenk过滤（毒性基团检测）
- Lipinski/Veber药物样性规则
- 基于InChI的去重

### ADMET预测
- 基于RDKit描述符和结构规则的简化版QSAR
- 毒性预警：hERG（含N+）、Ames（芳香硝基/胺）、DILI（苯胺/肼）
- BBB/口服生物利用度评估
- 综合ADMET评分（0-100）

### Pipeline编排
- 8层异步处理，支持实时状态查询
- 每层分子数递减：生成(1000) → 过滤(500) → 结构筛选(200) → ADMET(50) → 精筛(20) → 合成(10-20)
- 自动生成分子SVG图片

## 环境依赖（conda虚拟环境 `drugdesign`）

```
rdkit (2023.9.6), datamol (0.12.5), chemprop (2.2.3), aizynthfinder (4.4.1)
crem (0.3.0), openmm (8.5.2), selfies (2.2.0), mordred (2.0.7)
descriptastorus (2.8.0), aimsim (2.2.3), torch (2.12.1), scikit-learn (1.9.0)
pandas (2.3.3), flask (3.1.3), flask-cors (6.0.5), sqlalchemy (2.0.51)
numpy (1.26.4), openbabel (3.1.1), meeko (0.7.1)
```

## 作者
基于PPT《小分子药物设计Agent》方案构建
