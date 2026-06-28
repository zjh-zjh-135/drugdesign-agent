"""项目路由 - CRUD"""
from flask import Blueprint, request, jsonify
from sqlalchemy.orm import Session
from ..models.database import Project, ActiveMolecule, init_db
from ..services.utils import validate_smiles, canonicalize_smiles
from ..services.target_database import (
    get_target_info, get_active_molecules_for_target, 
    get_pdb_id_for_target, search_targets, SORTED_TARGET_NAMES, TARGET_DATABASE
)

projects_bp = Blueprint('projects', __name__, url_prefix='/api')
_SessionLocal = None

def _get_session():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = init_db()
    return __get_session()

@projects_bp.route('/projects', methods=['GET'])
def list_projects():
    """列出所有项目"""
    db = _get_session()
    try:
        projects = db.query(Project).order_by(Project.created_at.desc()).all()
        return jsonify({
            'success': True,
            'data': [{
                'id': p.id,
                'name': p.name,
                'target_name': p.target_name,
                'target_pdb': p.target_pdb,
                'design_goal': p.design_goal,
                'created_at': p.created_at.isoformat() if p.created_at else None,
                'updated_at': p.updated_at.isoformat() if p.updated_at else None,
            } for p in projects]
        })
    finally:
        db.close()

@projects_bp.route('/projects', methods=['POST'])
def create_project():
    """创建项目"""
    data = request.get_json() or {}
    if not data.get('name'):
        return jsonify({'success': False, 'error': '项目名称必填'}), 400
    
    target_name = data.get('target_name', '').strip()
    target_pdb = data.get('target_pdb', '').strip()
    
    # 如果用户选择了靶点但没有指定PDB，自动使用推荐的PDB ID
    if target_name and not target_pdb:
        target_pdb = get_pdb_id_for_target(target_name)
    
    db = _get_session()
    try:
        # P1修复: 检查项目名称是否已存在
        existing = db.query(Project).filter(Project.name == data['name']).first()
        if existing:
            return jsonify({'success': False, 'error': f'项目"{data["name"]}"已存在'}), 409
        
        project = Project(
            name=data['name'],
            target_name=target_name,
            target_pdb=target_pdb,
            description=data.get('description', ''),
            design_goal=data.get('design_goal', 'lead_optimization'),
            filter_params=data.get('filter_params', {})
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        
        return jsonify({'success': True, 'data': {'id': project.id, 'name': project.name}})
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'error': f'数据库操作失败: {str(e)}'}), 500
    finally:
        db.close()


@projects_bp.route('/targets/<target_name>/candidates', methods=['GET'])
def get_target_candidates(target_name):
    """获取靶点的候选活性分子（供用户选择添加）"""
    info = get_target_info(target_name)
    if not info:
        return jsonify({'success': False, 'error': '靶点不存在'}), 404
    
    candidates = info.get('active_molecules', [])
    return jsonify({
        'success': True,
        'data': {
            'target_name': target_name,
            'description': info.get('description', '')[:200] + '...' if len(info.get('description', '')) > 200 else info.get('description', ''),
            'pdb_id': info.get('pdb_id', ''),
            'candidates': candidates,
        }
    })


@projects_bp.route('/projects/<int:project_id>/active_molecules/batch', methods=['POST'])
def batch_add_active_molecules(project_id):
    """批量添加选中的活性分子到项目"""
    data = request.get_json() or {}
    molecules = data.get('molecules', [])
    
    if not molecules:
        return jsonify({'success': False, 'error': '分子列表为空'}), 400
    
    db = _get_session()
    try:
        p = db.query(Project).filter(Project.id == project_id).first()
        if not p:
            return jsonify({'success': False, 'error': '项目不存在'}), 404
        
        # 获取已存在的SMILES
        existing = set()
        for am in db.query(ActiveMolecule).filter(ActiveMolecule.project_id == project_id).all():
            if am.smiles:
                existing.add(canonicalize_smiles(am.smiles) or am.smiles)
        
        added = 0
        skipped = 0
        for m in molecules:
            smi = m.get('smiles', '')
            canon = canonicalize_smiles(smi)
            if not canon:
                continue
            if canon in existing:
                skipped += 1
                continue
            am = ActiveMolecule(
                project_id=project_id,
                smiles=canon,
                name=m.get('name', ''),
                ic50=m.get('ic50'),
                activity_type=m.get('activity_type', 'IC50'),
                source=m.get('source', f'Target: {p.target_name}')
            )
            db.add(am)
            existing.add(canon)
            added += 1
        
        db.commit()
        return jsonify({'success': True, 'data': {'added': added, 'skipped': skipped}})
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'error': f'数据库操作失败: {str(e)}'}), 500
    finally:
        db.close()

@projects_bp.route('/targets', methods=['GET'])
def list_targets():
    """获取所有靶点列表（按字母排序）"""
    query = request.args.get('q', '').strip()
    if query:
        results = search_targets(query)
    else:
        results = [{
            'name': name,
            'description': TARGET_DATABASE[name].get('description', '')[:120] + '...' 
                           if len(TARGET_DATABASE[name].get('description', '')) > 120 
                           else TARGET_DATABASE[name].get('description', ''),
            'pdb_id': TARGET_DATABASE[name].get('pdb_id', ''),
            'molecule_count': len(TARGET_DATABASE[name].get('active_molecules', [])),
        } for name in SORTED_TARGET_NAMES]
    
    return jsonify({'success': True, 'data': results})

@projects_bp.route('/targets/<target_name>', methods=['GET'])
def get_target_detail(target_name):
    """获取靶点详细信息"""
    info = get_target_info(target_name)
    if not info:
        return jsonify({'success': False, 'error': '靶点不存在'}), 404
    
    return jsonify({
        'success': True,
        'data': {
            'name': target_name,
            'description': info.get('description', ''),
            'pdb_id': info.get('pdb_id', ''),
            'active_molecules': info.get('active_molecules', []),
        }
    })

@projects_bp.route('/projects/<int:project_id>', methods=['GET'])
def get_project(project_id):
    """获取项目详情"""
    db = _get_session()
    try:
        p = db.query(Project).filter(Project.id == project_id).first()
        if not p:
            return jsonify({'success': False, 'error': '项目不存在'}), 404
        
        active_mols = db.query(ActiveMolecule).filter(
            ActiveMolecule.project_id == project_id
        ).all()
        
        return jsonify({
            'success': True,
            'data': {
                'id': p.id,
                'name': p.name,
                'target_name': p.target_name,
                'target_pdb': p.target_pdb,
                'description': p.description,
                'design_goal': p.design_goal,
                'filter_params': p.filter_params,
                'created_at': p.created_at.isoformat() if p.created_at else None,
                'active_molecules': [{
                    'id': m.id,
                    'smiles': m.smiles,
                    'name': m.name,
                    'ic50': m.ic50,
                    'activity_type': m.activity_type,
                } for m in active_mols]
            }
        })
    finally:
        db.close()

@projects_bp.route('/projects/<int:project_id>', methods=['PUT'])
def update_project(project_id):
    """更新项目"""
    data = request.get_json() or {}
    db = _get_session()
    try:
        p = db.query(Project).filter(Project.id == project_id).first()
        if not p:
            return jsonify({'success': False, 'error': '项目不存在'}), 404
        
        if 'name' in data: p.name = data['name']
        if 'target_name' in data: p.target_name = data['target_name']
        if 'target_pdb' in data: p.target_pdb = data['target_pdb']
        if 'description' in data: p.description = data['description']
        if 'design_goal' in data: p.design_goal = data['design_goal']
        if 'filter_params' in data: p.filter_params = data['filter_params']
        
        db.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'error': f'数据库操作失败: {str(e)}'}), 500
    finally:
        db.close()

@projects_bp.route('/projects/<int:project_id>', methods=['DELETE'])
def delete_project(project_id):
    """删除项目（级联删除）"""
    db = _get_session()
    try:
        p = db.query(Project).filter(Project.id == project_id).first()
        if not p:
            return jsonify({'success': False, 'error': '项目不存在'}), 404
        db.delete(p)
        db.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'error': f'数据库操作失败: {str(e)}'}), 500
    finally:
        db.close()

@projects_bp.route('/projects/<int:project_id>/active_molecules', methods=['POST'])
def upload_active_molecules(project_id):
    """上传已知活性分子"""
    data = request.get_json() or {}
    molecules = data.get('molecules', [])
    
    if not molecules:
        return jsonify({'success': False, 'error': '分子列表为空'}), 400
    
    # P2修复: 限制批量大小，防止DoS
    if len(molecules) > 100:
        return jsonify({'success': False, 'error': '分子列表最多100个'}), 413
    
    db = _get_session()
    try:
        # 验证项目存在
        p = db.query(Project).filter(Project.id == project_id).first()
        if not p:
            return jsonify({'success': False, 'error': '项目不存在'}), 404
        
        # 获取当前项目已存在的 SMILES（去重）
        existing = set()
        for am in db.query(ActiveMolecule).filter(ActiveMolecule.project_id == project_id).all():
            if am.smiles:
                existing.add(am.smiles)
        
        added = 0
        skipped = 0
        for m in molecules:
            smi = m.get('smiles', '')
            canon = canonicalize_smiles(smi)
            if not canon:
                continue
            if canon in existing:
                skipped += 1
                continue
            am = ActiveMolecule(
                project_id=project_id,
                smiles=canon,
                name=m.get('name', ''),
                ic50=m.get('ic50'),
                activity_type=m.get('activity_type', 'IC50'),
                source=m.get('source', '')
            )
            db.add(am)
            existing.add(canon)
            added += 1
        
        db.commit()
        return jsonify({'success': True, 'data': {'added': added, 'skipped': skipped}})
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'error': f'数据库操作失败: {str(e)}'}), 500
    finally:
        db.close()

from ..services.agent.tools import get_top_molecules as get_top_molecules_tool
from ..utils.security import rate_limit, audit_log

@projects_bp.route('/projects/<int:project_id>/top-molecules', methods=['GET'])
@rate_limit(max_requests=30, window_seconds=60)
@audit_log
def get_top_molecules_route(project_id):
    """获取项目中得分最高的候选分子（已通过合成筛选）"""
    limit = request.args.get('limit', 10, type=int)
    if limit <= 0 or limit > 100:
        limit = 10
    
    result = get_top_molecules_tool(project_id=project_id, limit=limit)
    if result.get('success'):
        return jsonify({'success': True, 'data': result})
    return jsonify({'success': False, 'error': result.get('error', '查询失败')}), 500
