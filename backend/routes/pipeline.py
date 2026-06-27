"""Pipeline路由 - 新增失败分子库接口"""
import json
from flask import Blueprint, request, jsonify
from sqlalchemy import func
from ..models.database import init_db, PipelineRun, GeneratedMolecule, MoleculeProperty, AdmetPrediction
from ..services.pipeline import PipelineRunner

pipeline_bp = Blueprint('pipeline', __name__, url_prefix='/api')
SessionLocal = init_db()

@pipeline_bp.route('/pipeline/run', methods=['POST'])
def run_pipeline():
    """一键运行Pipeline"""
    data = request.get_json() or {}
    project_id = data.get('project_id')
    
    if not project_id:
        return jsonify({'success': False, 'error': 'project_id必填'}), 400
    
    params = {
        'num_molecules': data.get('num_molecules', 5000),
        'generation_strategy': data.get('generation_strategy', 'crem'),
        'filter_params': data.get('filter_params', {}),
        'similarity_threshold': data.get('similarity_threshold', 0.3),
        'admet_threshold': data.get('admet_threshold', 60),
        'top_n': data.get('top_n', 200),
        'availability_threshold': data.get('availability_threshold', 0.5),
        'enable_failed_iteration': data.get('enable_failed_iteration', False),
    }
    
    try:
        runner = PipelineRunner(SessionLocal, project_id, params)
        job_id = runner.run()
        return jsonify({'success': True, 'data': {'job_id': job_id}})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@pipeline_bp.route('/pipeline/status/<run_id>', methods=['GET'])
def get_pipeline_status(run_id):
    """获取Pipeline状态"""
    status = PipelineRunner.get_status(run_id)
    return jsonify({'success': True, 'data': status})

@pipeline_bp.route('/pipeline/results/<run_id>', methods=['GET'])
def get_pipeline_results(run_id):
    """获取Pipeline结果"""
    top_n = int(request.args.get('top_n', 50))
    
    db = SessionLocal()
    try:
        results = PipelineRunner.get_results(run_id, db, top_n)
        return jsonify({'success': True, 'data': results})
    finally:
        db.close()


# ============ 失败分子库接口 ============

@pipeline_bp.route('/projects/<int:project_id>/failed-molecules', methods=['GET'])
def get_failed_molecules(project_id):
    """获取失败分子库 - 分页、筛选、搜索"""
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 50))
    stage = request.args.get('stage')  # 按失败阶段筛选
    search = request.args.get('search')  # 关键词搜索
    
    db = SessionLocal()
    try:
        query = db.query(GeneratedMolecule).filter(
            GeneratedMolecule.project_id == project_id,
            GeneratedMolecule.pipeline_status == 'failed'
        )
        
        if stage:
            query = query.filter(GeneratedMolecule.failure_stage == stage)
        
        # 关键词搜索（在失败原因中搜索）
        if search:
            query = query.filter(GeneratedMolecule.failure_reason.contains(search))
        
        total = query.count()
        molecules = query.order_by(GeneratedMolecule.failed_at.desc()).offset((page - 1) * per_page).limit(per_page).all()
        
        data = []
        for mol in molecules:
            try:
                failure_reason = json.loads(mol.failure_reason) if mol.failure_reason else {}
            except:
                failure_reason = {'raw': mol.failure_reason}
            
            data.append({
                'id': mol.id,
                'smiles': mol.smiles,
                'failure_stage': mol.failure_stage,
                'failure_reason': failure_reason,
                'failed_at': mol.failed_at.isoformat() if mol.failed_at else None,
                'generation_strategy': mol.generation_strategy,
            })
        
        return jsonify({
            'success': True,
            'data': {
                'items': data,
                'total': total,
                'page': page,
                'per_page': per_page,
                'pages': (total + per_page - 1) // per_page
            }
        })
    finally:
        db.close()

@pipeline_bp.route('/projects/<int:project_id>/failed-analysis', methods=['GET'])
def get_failed_analysis(project_id):
    """获取失败数据分析报告 - 各阶段统计、常见原因"""
    db = SessionLocal()
    try:
        # 1. 各阶段失败统计
        stage_stats = db.query(
            GeneratedMolecule.failure_stage,
            func.count(GeneratedMolecule.id).label('count')
        ).filter(
            GeneratedMolecule.project_id == project_id,
            GeneratedMolecule.pipeline_status == 'failed'
        ).group_by(GeneratedMolecule.failure_stage).all()
        
        stage_data = [{'stage': s, 'count': c} for s, c in stage_stats]
        
        # 2. 最近失败分子
        recent = db.query(GeneratedMolecule).filter(
            GeneratedMolecule.project_id == project_id,
            GeneratedMolecule.pipeline_status == 'failed'
        ).order_by(GeneratedMolecule.failed_at.desc()).limit(10).all()
        
        recent_data = []
        for mol in recent:
            try:
                reason = json.loads(mol.failure_reason) if mol.failure_reason else {}
            except:
                reason = {'raw': mol.failure_reason}
            recent_data.append({
                'id': mol.id,
                'smiles': mol.smiles,
                'failure_stage': mol.failure_stage,
                'reason_summary': reason.get('reason', '未知'),
                'failed_at': mol.failed_at.isoformat() if mol.failed_at else None
            })
        
        # 3. 总失败数
        total_failed = db.query(GeneratedMolecule).filter(
            GeneratedMolecule.project_id == project_id,
            GeneratedMolecule.pipeline_status == 'failed'
        ).count()
        
        # 4. PipelineRun 统计
        runs = db.query(PipelineRun).filter(
            PipelineRun.project_id == project_id
        ).order_by(PipelineRun.start_time.desc()).limit(5).all()
        
        run_stats = []
        for run in runs:
            run_stats.append({
                'id': run.id,
                'status': run.status,
                'num_generated': run.num_generated,
                'num_passed': run.num_passed,
                'num_failed': run.num_failed,
                'start_time': run.start_time.isoformat() if run.start_time else None
            })
        
        return jsonify({
            'success': True,
            'data': {
                'total_failed': total_failed,
                'stage_distribution': stage_data,
                'recent_failures': recent_data,
                'pipeline_runs': run_stats
            }
        })
    finally:
        db.close()

@pipeline_bp.route('/projects/<int:project_id>/failed-molecules/<int:molecule_id>', methods=['GET'])
def get_failed_molecule_detail(project_id, molecule_id):
    """获取单个失败分子的详细原因"""
    db = SessionLocal()
    try:
        mol = db.query(GeneratedMolecule).filter(
            GeneratedMolecule.id == molecule_id,
            GeneratedMolecule.project_id == project_id
        ).first()
        
        if not mol:
            return jsonify({'success': False, 'error': '分子不存在'}), 404
        
        try:
            failure_reason = json.loads(mol.failure_reason) if mol.failure_reason else {}
        except:
            failure_reason = {'raw': mol.failure_reason}
        
        # 获取详细属性
        prop = db.query(MoleculeProperty).filter(
            MoleculeProperty.molecule_id == mol.id
        ).first()
        
        admet = db.query(AdmetPrediction).filter(
            AdmetPrediction.molecule_id == mol.id
        ).first()
        
        return jsonify({
            'success': True,
            'data': {
                'id': mol.id,
                'smiles': mol.smiles,
                'failure_stage': mol.failure_stage,
                'failure_reason': failure_reason,
                'failed_at': mol.failed_at.isoformat() if mol.failed_at else None,
                'properties': {
                    'mw': prop.mw if prop else None,
                    'qed': prop.qed if prop else None,
                    'sa_score': prop.sa_score if prop else None,
                    'similarity_score': prop.similarity_score if prop else None,
                },
                'admet': {
                    'overall_score': admet.overall_score if admet else None,
                    'herg': admet.herg if admet else None,
                    'ames': admet.ames if admet else None,
                    'dili': admet.dili if admet else None,
                    'bbb': admet.bbb if admet else None,
                } if admet else None
            }
        })
    finally:
        db.close()
