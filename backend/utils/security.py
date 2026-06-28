import os
import secrets
import hashlib
from functools import wraps
from datetime import datetime, timedelta
from flask import request, jsonify, current_app
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool
from ..config import DB_PATH

Base = declarative_base()

# ========== 安全常量 ==========

# 允许的来源（默认只允许本地开发环境）
ALLOWED_ORIGINS = os.environ.get('CORS_ORIGINS', 'http://localhost:5173,http://127.0.0.1:5173').split(',')

# 安全头
SECURITY_HEADERS = {
    'X-Content-Type-Options': 'nosniff',
    'X-Frame-Options': 'DENY',
    'X-XSS-Protection': '1; mode=block',
    'Referrer-Policy': 'strict-origin-when-cross-origin',
    'Permissions-Policy': 'geolocation=(), microphone=(), camera=()',
    # P2修复: 添加安全响应头
    'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
    'Content-Security-Policy': "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'; font-src 'self';",
}

# 输入限制
MAX_MESSAGE_LENGTH = 2000
MAX_SMILES_LENGTH = 500
MAX_BATCH_SIZE = 100
MAX_PIPELINE_MOLECULES = 5000

# 速率限制（内存中简单实现，生产环境应使用 Redis）
_rate_limit_store = {}


# ========== 操作审计日志表 ==========

class AuditLog(Base):
    """操作审计日志表"""
    __tablename__ = 'audit_logs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    endpoint = Column(String(200), nullable=False)
    method = Column(String(10), nullable=False)
    ip_address = Column(String(50))
    user_agent = Column(Text)
    request_data = Column(Text)
    response_status = Column(Integer)
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.now)


def _init_audit_db():
    """初始化审计日志数据库"""
    engine = create_engine(
        f'sqlite:///{DB_PATH}',
        echo=False,
        connect_args={'timeout': 30},
        poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def log_action(endpoint, method, ip, user_agent, request_data, status_code, error=None):
    """记录操作日志（P1修复: 自动清理旧日志，防止无限膨胀）"""
    import json
    try:
        Session = _init_audit_db()
        db = Session()
        log = AuditLog(
            endpoint=endpoint,
            method=method,
            ip_address=ip,
            user_agent=user_agent[:500] if user_agent else None,
            request_data=json.dumps(request_data, ensure_ascii=False)[:2000] if request_data else None,
            response_status=status_code,
            error_message=str(error)[:500] if error else None
        )
        db.add(log)
        db.commit()
        
        # P1修复: 自动清理超过10000条的旧日志
        try:
            from sqlalchemy import func
            count = db.query(func.count(AuditLog.id)).scalar()
            if count and count > 10000:
                old_logs = db.query(AuditLog).order_by(AuditLog.created_at.asc()).limit(count - 10000).all()
                for old_log in old_logs:
                    db.delete(old_log)
                db.commit()
        except Exception:
            db.rollback()
        
        db.close()
    except Exception:
        pass  # 日志记录不应阻塞主业务


def get_client_ip():
    """获取客户端真实 IP（支持代理）"""
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    if request.headers.get('X-Real-IP'):
        return request.headers.get('X-Real-IP')
    return request.remote_addr


def check_origin():
    """检查请求来源是否合法"""
    origin = request.headers.get('Origin', '')
    if not origin:
        return True  # 允许非浏览器请求（如 curl、Postman）
    
    for allowed in ALLOWED_ORIGINS:
        if allowed.strip() == origin.strip():
            return True
    return False


def rate_limit(max_requests=60, window_seconds=60):
    """
    简单的速率限制装饰器
    每个 IP 地址在 window_seconds 秒内最多 max_requests 次请求
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            ip = get_client_ip()
            now = datetime.now()
            
            # 清理过期记录（P1修复: 限制清理频率和范围，防止内存泄漏）
            cutoff = now - timedelta(seconds=window_seconds)
            # 每100次请求做一次全量清理，其余只做增量清理
            _cleanup_counter = getattr(rate_limit, '_cleanup_counter', 0) + 1
            rate_limit._cleanup_counter = _cleanup_counter
            
            if _cleanup_counter % 100 == 0 or len(_rate_limit_store) > 10000:
                # 全量清理或达到上限时强制清理
                keys_to_remove = []
                for key, record in list(_rate_limit_store.items()):
                    if record['reset'] < cutoff:
                        keys_to_remove.append(key)
                    if len(keys_to_remove) > 1000:  # 单次最多清理1000条
                        break
                for key in keys_to_remove:
                    del _rate_limit_store[key]
            elif len(_rate_limit_store) > 5000:
                # 达到半量时做一次部分清理
                oldest_keys = sorted(
                    _rate_limit_store.keys(),
                    key=lambda k: _rate_limit_store[k]['reset']
                )[:500]
                for key in oldest_keys:
                    if _rate_limit_store[key]['reset'] < cutoff:
                        del _rate_limit_store[key]
            
            # 检查限制
            key = f"{ip}:{request.endpoint}"
            if key not in _rate_limit_store:
                _rate_limit_store[key] = {
                    'count': 0,
                    'reset': now + timedelta(seconds=window_seconds)
                }
            
            if _rate_limit_store[key]['count'] >= max_requests:
                return jsonify({
                    'success': False, 
                    'error': '请求过于频繁，请稍后再试',
                    'retry_after': int((_rate_limit_store[key]['reset'] - now).total_seconds())
                }), 429
            
            _rate_limit_store[key]['count'] += 1
            return f(*args, **kwargs)
        return wrapper
    return decorator


def require_json_content():
    """要求 POST/PUT 请求必须是 application/json"""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if request.method in ('POST', 'PUT', 'PATCH'):
                content_type = request.headers.get('Content-Type', '')
                if not content_type.startswith('application/json'):
                    return jsonify({
                        'success': False,
                        'error': '请求 Content-Type 必须是 application/json'
                    }), 415
            return f(*args, **kwargs)
        return wrapper
    return decorator


def validate_message_length(max_length=MAX_MESSAGE_LENGTH):
    """验证消息长度"""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            data = request.get_json(silent=True) or {}
            message = data.get('message', '')
            if isinstance(message, str) and len(message) > max_length:
                return jsonify({
                    'success': False,
                    'error': f'消息长度超过 {max_length} 字符限制'
                }), 413
            return f(*args, **kwargs)
        return wrapper
    return decorator


def validate_smiles(smiles):
    """验证 SMILES 字符串安全性"""
    if not smiles or not isinstance(smiles, str):
        return False, 'SMILES 不能为空'
    if len(smiles) > MAX_SMILES_LENGTH:
        return False, f'SMILES 长度超过 {MAX_SMILES_LENGTH} 字符限制'
    # 只允许化学符号相关字符
    allowed_chars = set(r'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789()[]#=@+\-\\/.$:*%&!')
    if any(c not in allowed_chars for c in smiles):
        return False, 'SMILES 包含非法字符'
    return True, None


def sanitize_string(value, max_length=500):
    """清理字符串输入，防止注入"""
    if not isinstance(value, str):
        return str(value)[:max_length]
    # 移除控制字符，只保留基本可打印字符
    cleaned = ''.join(c for c in value if c.isprintable() or c in '\n\t\r')
    return cleaned[:max_length]


def apply_security_headers(response):
    """添加安全响应头"""
    for header, value in SECURITY_HEADERS.items():
        response.headers[header] = value
    return response


def audit_log(f):
    """自动记录操作日志的装饰器"""
    @wraps(f)
    def wrapper(*args, **kwargs):
        start_time = datetime.now()
        status_code = 200
        error = None
        
        try:
            response = f(*args, **kwargs)
            if hasattr(response, 'status_code'):
                status_code = response.status_code
            return response
        except Exception as e:
            status_code = 500
            error = e
            raise
        finally:
            # 异步记录日志（不阻塞响应）
            try:
                import json
                request_data = request.get_json(silent=True)
                if request_data and isinstance(request_data, dict):
                    # 脱敏：移除可能的敏感字段（扩展关键词列表）
                    SENSITIVE_FIELDS = {
                        'password', 'token', 'api_key', 'secret', 'kimi_api_key',
                        'apikey', 'api_secret', 'access_token', 'refresh_token',
                        'auth_token', 'bearer', 'credential', 'private_key',
                        'session_id', 'cookie', 'authorization', 'key'
                    }
                    request_data = {k: v for k, v in request_data.items() 
                                   if k.lower() not in SENSITIVE_FIELDS}
                
                log_action(
                    endpoint=request.endpoint,
                    method=request.method,
                    ip=get_client_ip(),
                    user_agent=request.headers.get('User-Agent'),
                    request_data=request_data,
                    status_code=status_code,
                    error=error
                )
            except Exception:
                pass
    return wrapper


# ========== 请求安全中间件 ==========

def setup_security_middleware(app):
    """在 Flask 应用上设置安全中间件"""
    
    @app.before_request
    def before_request_security():
        # 检查来源（OPTIONS 预检请求不检查）
        if request.method != 'OPTIONS' and not check_origin():
            return jsonify({'success': False, 'error': '非法请求来源'}), 403
        
        # 检查请求体大小（防止过大请求）
        content_length = request.content_length or 0
        if content_length > 10 * 1024 * 1024:  # 10MB
            return jsonify({'success': False, 'error': '请求体超过 10MB 限制'}), 413
    
    @app.after_request
    def after_request_security(response):
        apply_security_headers(response)
        return response
    
    @app.errorhandler(404)
    def handle_404(e):
        return jsonify({'success': False, 'error': '接口不存在'}), 404
    
    @app.errorhandler(500)
    def handle_500(e):
        return jsonify({'success': False, 'error': '服务器内部错误'}), 500
