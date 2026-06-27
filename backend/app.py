from flask import Flask, send_from_directory
from flask_cors import CORS
import os

from .config import STATIC_DIR, MOLECULE_IMG_DIR
from .models.database import init_db
from .utils.security import setup_security_middleware, ALLOWED_ORIGINS
from .routes.system import system_bp
from .routes.projects import projects_bp
from .routes.molecules import molecules_bp
from .routes.generation import generation_bp
from .routes.admet import admet_bp
from .routes.synthesis import synthesis_bp
from .routes.pipeline import pipeline_bp
from .routes.filtering import filtering_bp
from .routes.assay import assay_bp
from .routes.structure import structure_bp
from .routes.docking import docking_bp
from .routes.activity import activity_bp
from .routes.ai_chat import ai_chat_bp
from .routes.builder import builder_bp
from .routes.agent import agent_bp

def create_app():
    app = Flask(__name__)
    
    # 生成密钥（用于 Session 签名等）
    app.secret_key = os.environ.get('FLASK_SECRET_KEY', os.urandom(32))
    
    # CORS 配置：仅允许指定来源（默认 localhost:5173）
    # 可通过环境变量 CORS_ORIGINS 配置多个来源，逗号分隔
    CORS(app, resources={
        r"/api/*": {
            "origins": ALLOWED_ORIGINS,
            "supports_credentials": True,
            "allow_headers": ["Content-Type", "Authorization"],
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
        }
    })
    
    # 设置安全中间件（请求来源检查、请求体大小限制、安全响应头）
    setup_security_middleware(app)
    
    # 初始化数据库
    init_db()
    
    # 确保静态目录存在
    os.makedirs(MOLECULE_IMG_DIR, exist_ok=True)
    os.makedirs(STATIC_DIR, exist_ok=True)
    
    # 注册蓝图
    app.register_blueprint(system_bp)
    app.register_blueprint(projects_bp)
    app.register_blueprint(molecules_bp)
    app.register_blueprint(generation_bp)
    app.register_blueprint(admet_bp)
    app.register_blueprint(synthesis_bp)
    app.register_blueprint(pipeline_bp)
    app.register_blueprint(filtering_bp)
    app.register_blueprint(assay_bp)
    app.register_blueprint(structure_bp)
    app.register_blueprint(docking_bp)
    app.register_blueprint(activity_bp)
    app.register_blueprint(ai_chat_bp)
    app.register_blueprint(builder_bp)
    app.register_blueprint(agent_bp)
    
    # 静态文件服务
    @app.route('/static/<path:filename>')
    def serve_static(filename):
        return send_from_directory(STATIC_DIR, filename)
    
    @app.route('/')
    def index():
        return {
            'service': '小分子药物设计Agent',
            'version': '0.1.0',
            'status': 'running',
            'docs': '/api/health',
            'security': 'enhanced'  # 标记安全版本
        }
    
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=5000, debug=True)
