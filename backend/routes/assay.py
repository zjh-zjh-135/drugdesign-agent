"""实验验证与数据回流路由"""
from flask import Blueprint, request, jsonify
from sqlalchemy.orm import Session
from ..models.database import AssayResult, GeneratedMolecule, ActiveMolecule, init_db

assay_bp = Blueprint('assay', __name__, url_prefix='/api')
SessionLocal = init_db()

@assay_bp.route('/projects/<int:project_id>/assay_results', methods=['GET'])
def list_assay_results(project_id):
    """列出项目所有实验验证记录"""
    db = SessionLocal()
    try:
        results = db.query(AssayResult).filter(
            AssayResult.project_id == project_id
        ).order_by(AssayResult.created_at.desc()).all()
        
        return jsonify({
            'success': True,
            'data': [{
                'id': r.id,
                'smiles': r.smiles,
                'name': r.name,
                'assay_type': r.assay_type,
                'predicted_value': r.predicted_value,
                'actual_value': r.actual_value,
                'unit': r.unit,
                'status': r.status,
                'notes': r.notes,
                'feedback_applied': r.feedback_applied,
                'error_rate': r.error_rate,
                'created_at': r.created_at.isoformat() if r.created_at else None,
            } for r in results]
        })
    finally:
        db.close()

@assay_bp.route('/projects/<int:project_id>/assay_results', methods=['POST'])
def create_assay_result(project_id):
    """创建实验验证记录"""
    data = request.get_json() or {}
    
    if not data.get('smiles'):
        return jsonify({'success': False, 'error': 'SMILES必填'}), 400
    
    predicted = data.get('predicted_value')
    actual = data.get('actual_value')
    error_rate = None
    if predicted is not None and actual is not None and actual != 0:
        error_rate = abs(predicted - actual) / abs(actual)
    
    db = SessionLocal()
    try:
        result = AssayResult(
            project_id=project_id,
            molecule_id=data.get('molecule_id'),
            smiles=data['smiles'],
            name=data.get('name', ''),
            assay_type=data.get('assay_type', 'IC50'),
            predicted_value=predicted,
            actual_value=actual,
            unit=data.get('unit', 'nM'),
            status=data.get('status', 'pending'),
            notes=data.get('notes', ''),
            error_rate=error_rate
        )
        db.add(result)
        db.commit()
        db.refresh(result)
        return jsonify({
            'success': True,
            'data': {'id': result.id}
        })
    finally:
        db.close()

@assay_bp.route('/assay_results/<int:assay_id>', methods=['PUT'])
def update_assay_result(assay_id):
    """更新实验结果（填入实测值）"""
    data = request.get_json() or {}
    db = SessionLocal()
    try:
        r = db.query(AssayResult).filter(AssayResult.id == assay_id).first()
        if not r:
            return jsonify({'success': False, 'error': '记录不存在'}), 404
        
        if 'actual_value' in data:
            r.actual_value = data['actual_value']
        if 'predicted_value' in data:
            r.predicted_value = data['predicted_value']
        if 'status' in data:
            r.status = data['status']
        if 'notes' in data:
            r.notes = data['notes']
        
        # 重新计算误差
        if r.predicted_value is not None and r.actual_value is not None and r.actual_value != 0:
            r.error_rate = abs(r.predicted_value - r.actual_value) / abs(r.actual_value)
        
        db.commit()
        return jsonify({'success': True})
    finally:
        db.close()

@assay_bp.route('/assay_results/<int:assay_id>/feedback', methods=['POST'])
def apply_feedback(assay_id):
    """数据回流：将实验验证结果加入已知活性分子库"""
    db = SessionLocal()
    try:
        r = db.query(AssayResult).filter(AssayResult.id == assay_id).first()
        if not r:
            return jsonify({'success': False, 'error': '记录不存在'}), 404
        
        if r.feedback_applied:
            return jsonify({'success': False, 'error': '该记录已回流'}), 400
        
        if r.actual_value is None:
            return jsonify({'success': False, 'error': '实测值尚未填写，无法回流'}), 400
        
        # 1. 标记为已回流
        r.feedback_applied = True
        
        # 2. 创建ActiveMolecule记录
        am = ActiveMolecule(
            project_id=r.project_id,
            smiles=r.smiles,
            name=r.name or f"验证分子#{r.id}",
            ic50=r.actual_value if r.assay_type == 'IC50' else None,
            activity_type=r.assay_type,
            source=f'实验验证回流(AssayResult#{r.id})'
        )
        db.add(am)
        db.commit()
        
        return jsonify({
            'success': True,
            'data': {
                'active_molecule_id': am.id,
                'message': '数据已回流，下一轮Pipeline将使用此实验数据'
            }
        })
    finally:
        db.close()

@assay_bp.route('/projects/<int:project_id>/feedback_stats', methods=['GET'])
def get_feedback_stats(project_id):
    """获取数据回流统计"""
    db = SessionLocal()
    try:
        total = db.query(AssayResult).filter(AssayResult.project_id == project_id).count()
        completed = db.query(AssayResult).filter(
            AssayResult.project_id == project_id,
            AssayResult.status == 'completed'
        ).count()
        feedback = db.query(AssayResult).filter(
            AssayResult.project_id == project_id,
            AssayResult.feedback_applied == True
        ).count()
        
        # 计算平均误差
        error_rates = [r.error_rate for r in db.query(AssayResult).filter(
            AssayResult.project_id == project_id,
            AssayResult.error_rate != None
        ).all()]
        avg_error = sum(error_rates) / len(error_rates) if error_rates else None
        
        return jsonify({
            'success': True,
            'data': {
                'total_assays': total,
                'completed_assays': completed,
                'feedback_applied': feedback,
                'avg_error_rate': avg_error,
                'pending_count': total - completed
            }
        })
    finally:
        db.close()
