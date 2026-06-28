import sys, os

base_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, base_dir)

# ========== 加载 .env 环境变量 ==========
# 在导入任何后端模块之前加载，确保 KIMI_API_KEY 等配置可用
env_path = os.path.join(base_dir, '.env')
if os.path.exists(env_path):
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                # 去除可能存在的引号
                if (value.startswith('"') and value.endswith('"')) or \
                   (value.startswith("'") and value.endswith("'")):
                    value = value[1:-1]
                if key and key not in os.environ:
                    os.environ[key] = value
    print("[OK] .env 环境变量已加载")
else:
    print("[WARNING] 未找到 .env 文件，使用系统环境变量")

from backend.app import create_app

app = create_app()

if __name__ == '__main__':
    print("=" * 60)
    print("  小分子药物设计Agent - 后端服务 (已修复线程安全)")
    print("  访问: http://localhost:5000")
    print("  API:  http://localhost:5000/api/health")
    print("=" * 60)
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
