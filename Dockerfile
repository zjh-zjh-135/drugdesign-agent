# DrugDesign Copilot Agent - Docker 部署

FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    libsqlite3-dev \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目代码
COPY backend/ ./backend/
COPY wsgi.py .

# 创建数据目录
RUN mkdir -p /app/data

# 环境变量
ENV FLASK_ENV=production
ENV PYTHONPATH=/app
ENV DB_PATH=/app/data/drugdesign.db
ENV STATIC_DIR=/app/backend/static

# 暴露端口
EXPOSE 5000

# 使用 Gunicorn 运行
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:5000", "wsgi:app"]
