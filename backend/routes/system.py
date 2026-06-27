"""系统路由 - 健康检查、配置"""
from flask import Blueprint, jsonify
from ..config import DEFAULT_THRESHOLDS

system_bp = Blueprint('system', __name__, url_prefix='/api')

@system_bp.route('/health', methods=['GET'])
def health():
    """健康检查"""
    return jsonify({'success': True, 'status': 'ok', 'service': 'drugdesign-agent'})

@system_bp.route('/config/filters', methods=['GET'])
def get_filter_config():
    """获取默认过滤参数"""
    return jsonify({'success': True, 'data': DEFAULT_THRESHOLDS})
