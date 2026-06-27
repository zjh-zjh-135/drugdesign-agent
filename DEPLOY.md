# DrugDesign Copilot Agent - 部署指南

## 架构概览

```
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│   前端      │      │   后端      │      │   数据库    │
│  React+Vite │ ──── │ Flask API   │ ──── │  SQLite     │
│  Vercel     │      │ Render/Docker│     │  文件型      │
└─────────────┘      └─────────────┘      └─────────────┘
```

## 部署方式

### 方式一：Vercel (前端) + Render (后端) - 推荐

#### 1. 部署后端到 Render

**A. 创建 Render 账号**
- 访问 https://render.com 注册账号
- 连接 GitHub 仓库

**B. 创建 Web Service**
- 点击 "New Web Service"
- 选择 `zjh-zjh-135/drugdesign-agent` 仓库
- 配置：
  - **Name**: `drugdesign-api`
  - **Runtime**: `Python 3`
  - **Build Command**: `pip install -r requirements.txt`
  - **Start Command**: `gunicorn -w 2 -b 0.0.0.0:5000 wsgi:app`
  - **Plan**: Free (有 15分钟休眠限制) 或 Starter ($7/月)

**C. 设置环境变量**
在 Render Dashboard → Environment 中添加：
```
FLASK_ENV=production
FLASK_SECRET_KEY=your-random-secret-key-here
KIMI_API_KEY=your-kimi-api-key
CORS_ORIGINS=https://your-frontend-domain.vercel.app
DB_PATH=/opt/render/project/src/backend/drugdesign.db
```

**D. 部署完成**
- 记录 Render 分配的 URL，如 `https://drugdesign-api.onrender.com`

#### 2. 部署前端到 Vercel

**A. 创建 Vercel 账号**
- 访问 https://vercel.com 注册账号
- 连接 GitHub 仓库

**B. 导入项目**
- 点击 "Add New Project"
- 选择 `zjh-zjh-135/drugdesign-agent`
- 配置：
  - **Framework Preset**: `Vite`
  - **Root Directory**: `frontend`
  - **Build Command**: `npm run build`
  - **Output Directory**: `dist`

**C. 设置环境变量**
在 Vercel Dashboard → Settings → Environment Variables 中添加：
```
VITE_API_URL=https://drugdesign-api.onrender.com/api
```

**D. 重新部署**
- 添加环境变量后，Vercel 会自动重新部署

### 方式二：Docker 部署（自有服务器）

#### 1. 构建镜像
```bash
cd drugdesign-agent
docker build -t drugdesign-agent:latest .
```

#### 2. 运行容器
```bash
docker run -d \
  -p 5000:5000 \
  -e FLASK_ENV=production \
  -e FLASK_SECRET_KEY=your-secret-key \
  -e KIMI_API_KEY=your-kimi-api-key \
  -e CORS_ORIGINS=https://yourdomain.com \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/static:/app/static \
  --name drugdesign \
  drugdesign-agent:latest
```

#### 3. 使用 Docker Compose
```bash
cd drugdesign-agent
docker-compose up -d
```

### 方式三：本地部署（开发/测试）

```bash
# 1. 克隆仓库
git clone https://github.com/zjh-zjh-135/drugdesign-agent.git
cd drugdesign-agent

# 2. 创建 Python 环境（推荐 conda）
conda create -n drugdesign python=3.11
conda activate drugdesign
conda install -c conda-forge rdkit

# 3. 安装依赖
pip install -r requirements.txt

# 4. 设置环境变量
cp .env.example .env
# 编辑 .env 填入 KIMI_API_KEY

# 5. 启动后端
python backend/run.py

# 6. 启动前端（新终端）
cd frontend
npm install
npm run dev
```

## 生产环境检查清单

### 安全
- [ ] `FLASK_SECRET_KEY` 已设置为随机长字符串
- [ ] `KIMI_API_KEY` 已设置且未提交到 Git
- [ ] CORS 白名单已配置为实际域名
- [ ] 输入验证和速率限制已启用

### 性能
- [ ] Gunicorn worker 数量 ≥ 2
- [ ] 前端构建已启用代码分割
- [ ] 静态资源使用 CDN（可选）

### 数据
- [ ] SQLite 数据库已持久化（Docker volume）
- [ ] 定期备份数据库文件
- [ ]  molecule 图片目录已持久化

### 监控
- [ ] 应用健康检查端点 `/api/health`
- [ ] 日志收集配置
- [ ] 错误追踪（Sentry 等，可选）

## 常见问题

### Q: Render Free 计划有 15 分钟休眠限制，怎么办？
A: 升级到 Starter 计划（$7/月）或使用 cron 服务每 10 分钟 ping 一次保持活跃。

### Q: 如何更新已部署的应用？
A: 推送代码到 GitHub 主分支，Vercel 和 Render 会自动重新部署。

### Q: 数据库文件会丢失吗？
A: Render Free 计划每次部署会重置文件系统。建议使用：
- Render PostgreSQL 附加组件（$7/月起）
- 或升级到 Render 付费计划保持文件系统持久化
- 或 Docker 部署 + 外部卷

### Q: 前端调用后端 404？
A: 检查 `VITE_API_URL` 环境变量是否正确指向后端 URL。

### Q: CORS 错误？
A: 确保后端 `CORS_ORIGINS` 包含前端完整域名（含 `https://`）。

## 环境变量参考

| 变量名 | 必需 | 说明 | 示例 |
|--------|------|------|------|
| `FLASK_ENV` | 是 | 运行环境 | `production` |
| `FLASK_SECRET_KEY` | 是 | Flask 安全密钥 | 随机32+字符 |
| `KIMI_API_KEY` | 是 | Kimi API 密钥 | `sk-...` |
| `CORS_ORIGINS` | 是 | 前端域名白名单 | `https://app.example.com` |
| `DB_PATH` | 否 | 数据库文件路径 | `/app/data/db.sqlite` |
| `VITE_API_URL` | 前端必需 | 后端 API 地址 | `https://api.example.com/api` |

## 技术支持

- GitHub Issues: https://github.com/zjh-zjh-135/drugdesign-agent/issues
- 部署问题请提供 Render/Vercel 日志截图
