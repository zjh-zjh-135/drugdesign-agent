from flask import Blueprint, request, jsonify
import uuid
from datetime import datetime

from ..services.agent import CopilotAgent, get_registry
from ..services.agent.memory import (
    get_or_create_session, save_message, get_conversation_history,
    save_project_memory, get_project_memory, get_project_summary
)
from ..models.database import init_db, Project
from ..utils.security import (
    rate_limit, validate_message_length, require_json_content,
    sanitize_string, audit_log, MAX_PIPELINE_MOLECULES
)

agent_bp = Blueprint('agent', __name__, url_prefix='/api')

# 初始化 Agent
agent = CopilotAgent()

# 注册所有工具
from ..services.agent.tools import (
    create_project, list_projects, run_pipeline, analyze_failures,
    adjust_filters, get_project_status, compare_molecules, suggest_next_step,
    get_failed_molecules, get_top_molecules
)

def get_db():
    """获取数据库 session（P1修复: 延迟初始化，避免每次创建新engine）"""
    from ..models.database import init_db
    _SessionLocal = getattr(get_db, '_SessionLocal', None)
    if _SessionLocal is None:
        _SessionLocal = init_db()
        get_db._SessionLocal = _SessionLocal
    return _SessionLocal()


def validate_project_id(project_id):
    """验证项目ID有效性"""
    if not isinstance(project_id, int) or project_id <= 0 or project_id > 999999:
        return False, '项目ID无效'
    return True, None


def get_project_or_404(db, project_id):
    """获取项目，不存在时返回 404"""
    is_valid, error = validate_project_id(project_id)
    if not is_valid:
        return None, error
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return None, '项目不存在'
    return project, None


# ========== Copilot 聊天接口 ==========

@agent_bp.route('/agent/chat', methods=['POST'])
@require_json_content()
@validate_message_length()
@rate_limit(max_requests=30, window_seconds=60)
@audit_log
def agent_chat():
    """
    Copilot 主聊天接口（增强版，支持自主 Agent 工作流）
    
    Request: {
        "message": "用户输入",
        "project_id": 123,  // 可选
        "session_id": "xxx"  // 可选，不传则创建新会话
    }
    
    Response: {
        "success": true,
        "type": "action" | "chat",
        "final_answer": "助手回答",
        "action_cards": [...],  // 可执行操作卡片
        "steps": [...],         // ReAct 步骤
        "session_id": "xxx",
        "autonomous": false,   // 是否为自主执行模式
        "plan_summary": "...",   // 计划摘要（自主模式）
        "execution_report": {} // 完整执行报告（自主模式）
    }
    """
    data = request.get_json() or {}
    message = data.get('message', '').strip()
    project_id = data.get('project_id')
    session_id = data.get('session_id')
    
    if not message:
        return jsonify({'success': False, 'error': '消息不能为空'}), 400
    
    # 验证消息长度（额外检查，防止绕过装饰器）
    if len(message) > 2000:
        return jsonify({'success': False, 'error': '消息长度超过 2000 字符限制'}), 413
    
    # 验证 project_id 范围（如果提供）
    if project_id is not None:
        if not isinstance(project_id, int) or project_id <= 0 or project_id > 999999:
            return jsonify({'success': False, 'error': '项目ID无效'}), 400
    
    # 生成新 session_id
    if not session_id:
        session_id = f"agent_{uuid.uuid4().hex[:16]}"
    else:
        # 验证 session_id 格式（防止注入）
        session_id = sanitize_string(session_id, max_length=100)
    
    db = get_db()
    try:
        # 如果提供了 project_id，验证项目是否存在
        if project_id is not None:
            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                return jsonify({'success': False, 'error': '项目不存在'}), 404
        
        # 确保会话存在
        get_or_create_session(db, session_id, project_id=project_id, title=message[:50])
        
        # 运行 Agent（增强版引擎，传入 db 以支持自动推断）
        result = agent.chat(message, project_id=project_id, session_id=session_id, db=db)
        
        # 如果返回的是 dict
        if isinstance(result, dict):
            return jsonify({
                'success': True,
                'type': result.get('type', 'chat'),
                'form_type': result.get('form_type', ''),
                'final_answer': result.get('final_answer', ''),
                'chat_summary': result.get('chat_summary', ''),
                'steps': result.get('steps', []),
                'session_id': session_id,
                'autonomous': result.get('autonomous', False),
                'plan_summary': result.get('plan_summary', ''),
                'execution_report': result.get('execution_report', {}),
                'actions': result.get('execution_report', {}).get('actions', []),
            })
        
        return jsonify({
            'success': True,
            'type': 'chat',
            'final_answer': str(result),
            'action_cards': [],
            'steps': [],
            'session_id': session_id,
            'autonomous': False,
        })
        
    except Exception as e:
        # P1修复: 生产环境不暴露原始异常，记录到日志
        import logging
        logging.getLogger('agent').error(f"Agent error: {e}", exc_info=True)
        return jsonify({'success': False, 'error': '系统处理异常，请稍后重试'}), 500
    finally:
        db.close()


@agent_bp.route('/agent/goal', methods=['POST'])
@require_json_content()
@validate_message_length()
@rate_limit(max_requests=10, window_seconds=60)
@audit_log
def agent_goal():
    """
    自主 Agent 目标执行接口（非流式，但返回完整执行报告）
    
    Request: {
        "message": "用户目标，如：帮我优化项目",
        "project_id": 123  // 可选
    }
    
    Response: {
        "success": true,
        "type": "autonomous",
        "final_answer": "最终报告",
        "plan_summary": "计划摘要",
        "steps": [...],              // 执行步骤
        "execution_report": {...},   // 完整报告
        "session_id": "xxx"
    }
    """
    data = request.get_json() or {}
    message = data.get('message', '').strip()
    project_id = data.get('project_id')
    session_id = data.get('session_id')
    
    if not message:
        return jsonify({'success': False, 'error': '目标不能为空'}), 400
    
    if len(message) > 2000:
        return jsonify({'success': False, 'error': '目标长度超过 2000 字符限制'}), 413
    
    if project_id is not None:
        if not isinstance(project_id, int) or project_id <= 0 or project_id > 999999:
            return jsonify({'success': False, 'error': '项目ID无效'}), 400
    
    if not session_id:
        session_id = f"agent_{uuid.uuid4().hex[:16]}"
    else:
        session_id = sanitize_string(session_id, max_length=100)
    
    db = get_db()
    try:
        if project_id is not None:
            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                return jsonify({'success': False, 'error': '项目不存在'}), 404
        
        get_or_create_session(db, session_id, project_id=project_id, title=message[:50])
        
        # 运行增强版 Agent（自主模式，传入 db 支持自动推断）
        result = agent.chat(message, project_id=project_id, session_id=session_id, db=db)
        
        return jsonify({
            'success': True,
            'type': 'autonomous',
            'form_type': result.get('form_type', ''),
            'final_answer': result.get('final_answer', ''),
            'chat_summary': result.get('chat_summary', ''),
            'plan_summary': result.get('plan_summary', ''),
            'steps': result.get('steps', []),
            'execution_report': result.get('execution_report', {}),
            'action_cards': result.get('action_cards', []),
            'actions': result.get('execution_report', {}).get('actions', []),  # NEW: 前端动作
            'session_id': session_id,
        })
        
    except Exception as e:
        # P1修复: 生产环境不暴露原始异常，记录到日志
        import logging
        logging.getLogger('agent').error(f"Agent error: {e}", exc_info=True)
        return jsonify({'success': False, 'error': '系统处理异常，请稍后重试'}), 500
    finally:
        db.close()


@agent_bp.route('/agent/execute', methods=['POST'])
@require_json_content()
@rate_limit(max_requests=10, window_seconds=60)
@audit_log
def execute_action():
    """
    执行用户确认的 Action Card
    
    Request: {
        "action": "run_pipeline",
        "params": {"project_id": 1, "num_molecules": 500}
    }
    """
    data = request.get_json() or {}
    action = sanitize_string(data.get('action', ''), max_length=100)
    params = data.get('params', {})
    
    if not action:
        return jsonify({'success': False, 'error': 'action 不能为空'}), 400
    
    # 验证 action 白名单（只允许已知工具）
    allowed_actions = {
        'create_project', 'list_projects', 'run_pipeline', 'analyze_failures',
        'adjust_filters', 'get_project_status', 'compare_molecules',
        'suggest_next_step', 'get_failed_molecules', 'get_top_molecules'
    }
    if action not in allowed_actions:
        return jsonify({'success': False, 'error': '非法操作'}), 400
    
    # 验证 project_id 参数
    project_id = params.get('project_id')
    if project_id is not None:
        if not isinstance(project_id, int) or project_id <= 0 or project_id > 999999:
            return jsonify({'success': False, 'error': '项目ID无效'}), 400
        # 验证项目是否存在
        db = get_db()
        try:
            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                return jsonify({'success': False, 'error': '项目不存在'}), 404
        finally:
            db.close()
    
    # 验证 num_molecules 参数范围
    num_molecules = params.get('num_molecules')
    if num_molecules is not None:
        if not isinstance(num_molecules, int) or num_molecules <= 0 or num_molecules > MAX_PIPELINE_MOLECULES:
            return jsonify({
                'success': False, 
                'error': f'num_molecules 必须在 1-{MAX_PIPELINE_MOLECULES} 之间'
            }), 400
    
    try:
        result = agent.execute_action_card(action, params)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': '执行失败'}), 500


# ========== 会话管理 ==========

@agent_bp.route('/agent/sessions', methods=['GET'])
def list_sessions():
    """列出所有 Agent 会话"""
    db = get_db()
    try:
        from ..models.database import AgentSession
        sessions = db.query(AgentSession).order_by(AgentSession.updated_at.desc()).all()
        return jsonify({
            'success': True,
            'sessions': [
                {
                    'id': s.id,
                    'session_id': s.session_id,
                    'project_id': s.project_id,
                    'title': s.title,
                    'created_at': s.created_at.isoformat(),
                    'updated_at': s.updated_at.isoformat()
                }
                for s in sessions
            ]
        })
    finally:
        db.close()

@agent_bp.route('/agent/sessions/<session_id>/messages', methods=['GET'])
def get_session_messages(session_id):
    """获取会话历史消息"""
    db = get_db()
    try:
        messages = get_conversation_history(db, session_id, limit=50)
        return jsonify({'success': True, 'messages': messages})
    except Exception as e:
        # P1修复: 生产环境不暴露原始异常，记录到日志
        import logging
        logging.getLogger('agent').error(f"Agent error: {e}", exc_info=True)
        return jsonify({'success': False, 'error': '系统处理异常，请稍后重试'}), 500
    finally:
        db.close()

@agent_bp.route('/agent/sessions/<session_id>', methods=['DELETE'])
@rate_limit(max_requests=10, window_seconds=60)
@audit_log
def delete_session(session_id):
    """删除会话"""
    # 验证 session_id 格式（防止注入）
    session_id = sanitize_string(session_id, max_length=100)
    if not session_id:
        return jsonify({'success': False, 'error': 'session_id 无效'}), 400
    
    db = get_db()
    try:
        from ..models.database import AgentSession
        session = db.query(AgentSession).filter(AgentSession.session_id == session_id).first()
        if session:
            db.delete(session)
            db.commit()
            return jsonify({'success': True, 'message': '会话已删除'})
        return jsonify({'success': False, 'error': '会话不存在'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': '删除失败'}), 500
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'error': f'数据库操作失败: {str(e)}'}), 500
    finally:
        db.close()


# ========== 项目记忆 ==========

@agent_bp.route('/agent/projects/<int:project_id>/memory', methods=['GET'])
def get_project_memory_api(project_id):
    """获取项目记忆"""
    memory_type = request.args.get('type')
    if memory_type:
        memory_type = sanitize_string(memory_type, max_length=50)
    
    db = get_db()
    try:
        # 验证项目是否存在
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            return jsonify({'success': False, 'error': '项目不存在'}), 404
        
        memories = get_project_memory(db, project_id, memory_type=memory_type)
        return jsonify({'success': True, 'memories': memories})
    except Exception as e:
        return jsonify({'success': False, 'error': '查询失败'}), 500
    finally:
        db.close()

@agent_bp.route('/agent/projects/<int:project_id>/summary', methods=['GET'])
def get_project_summary_api(project_id):
    """获取项目摘要"""
    db = get_db()
    try:
        # 验证项目是否存在
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            return jsonify({'success': False, 'error': '项目不存在'}), 404
        
        summary = get_project_summary(db, project_id)
        return jsonify({'success': True, 'summary': summary})
    except Exception as e:
        return jsonify({'success': False, 'error': '查询失败'}), 500
    finally:
        db.close()


# ========== 工具列表 ==========

@agent_bp.route('/agent/tools', methods=['GET'])
def list_tools():
    """列出所有可用工具"""
    registry = get_registry()
    tools = registry.list_tools()
    return jsonify({'success': True, 'tools': tools})


# ========== Phase 5: 追踪查询接口 ==========

@agent_bp.route('/agent/traces', methods=['GET'])
def get_traces():
    """
    获取最近 Agent 执行追踪记录。
    
    Query params:
        limit: 返回数量（默认 20）
        session_id: 按会话过滤（可选）
    """
    from ..services.agent.tracer import get_recent_traces, get_trace_stats
    
    limit = request.args.get('limit', 20, type=int)
    session_id = request.args.get('session_id')
    
    if session_id:
        from ..services.agent.tracer import TraceStore
        traces = TraceStore.get_traces_by_session(session_id, limit=limit)
    else:
        traces = get_recent_traces(limit=limit)
    
    stats = get_trace_stats()
    
    return jsonify({
        'success': True,
        'traces': traces,
        'stats': stats,
    })


@agent_bp.route('/agent/traces/<trace_id>', methods=['GET'])
def get_trace_detail(trace_id):
    """获取单个追踪详情"""
    from ..services.agent.tracer import get_trace
    
    trace = get_trace(trace_id)
    if not trace:
        return jsonify({'success': False, 'error': '追踪记录不存在'}), 404
    
    return jsonify({
        'success': True,
        'trace': trace,
    })


@agent_bp.route('/agent/traces', methods=['DELETE'])
@rate_limit(max_requests=5, window_seconds=60)
def clear_traces():
    """清空所有追踪记录（需要确认）"""
    from ..services.agent.tracer import clear_traces
    clear_traces()
    return jsonify({'success': True, 'message': '追踪记录已清空'})
