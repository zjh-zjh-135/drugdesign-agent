"""分子生成路由"""
from flask import Blueprint, request, jsonify
from ..models.database import init_db
from ..services.pipeline import PipelineRunner
from ..services.generation import MoleculeGenerator
from ..services.filtering import MoleculeFilter
from ..services.utils import canonicalize_smiles
from ..services.admet import AdmetPredictor
from ..services.docking import DockingScreen
from ..services.synthesis import SynthesisAnalyzer
from ..services.utils import save_molecule_svg
from ..config import MOLECULE_IMG_DIR

import os

generation_bp = Blueprint('generation', __name__, url_prefix='/api')
_SessionLocal = None

def _get_session():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = init_db()
    return __get_session()

@generation_bp.route('/projects/<int:project_id>/generate', methods=['POST'])
def generate_molecules(project_id):
    """启动分子生成Pipeline"""
    data = request.get_json() or {}
    
    params = {
        'num_molecules': data.get('num_molecules', 5000),
        'generation_strategy': data.get('generation_strategy', 'crem'),
        'filter_params': data.get('filter_params', {}),
        'similarity_threshold': data.get('similarity_threshold', 0.3),
        'admet_threshold': data.get('admet_threshold', 60),
        'top_n': data.get('top_n', 200),
        'availability_threshold': data.get('availability_threshold', 0.5),
    }
    
    db = _get_session()
    try:
        runner = PipelineRunner(SessionLocal, project_id, params)
        job_id = runner.run()
        return jsonify({'success': True, 'data': {'job_id': job_id}})
    finally:
        db.close()

@generation_bp.route('/generate/status/<job_id>', methods=['GET'])
def get_generation_status(job_id):
    """获取生成状态"""
    status = PipelineRunner.get_status(job_id)
    return jsonify({'success': True, 'data': status})

@generation_bp.route('/molecules/filter', methods=['POST'])
def apply_filter():
    """应用过滤规则"""
    data = request.get_json() or {}
    molecule_ids = data.get('molecule_ids', [])
    filter_params = data.get('filter_params', {})
    
    db = _get_session()
    try:
        from ..models.database import GeneratedMolecule, MoleculeProperty
        filter_engine = MoleculeFilter(filter_params)
        
        results = []
        for mid in molecule_ids:
            mol = db.query(GeneratedMolecule).filter(GeneratedMolecule.id == mid).first()
            if not mol:
                continue
            
            ok, desc, reason = filter_engine.filter_single(mol.smiles)
            
            # 保存或更新性质
            prop = db.query(MoleculeProperty).filter(MoleculeProperty.molecule_id == mid).first()
            if not prop:
                prop = MoleculeProperty(molecule_id=mid)
                db.add(prop)
            
            prop.mw = desc.get('mw')
            prop.clogp = desc.get('clogp')
            prop.tpsa = desc.get('tpsa')
            prop.hbd = desc.get('hbd')
            prop.hba = desc.get('hba')
            prop.rotb = desc.get('rotb')
            prop.sa_score = desc.get('sa_score')
            prop.qed = desc.get('qed')
            prop.pass_pains = desc.get('pass_pains')
            prop.pass_filters = ok
            
            mol.pipeline_status = 'filtered' if ok else 'failed'
            results.append({'id': mid, 'pass': ok, 'reason': reason})
        
        db.commit()
        return jsonify({'success': True, 'data': results})
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'error': f'数据库操作失败: {str(e)}'}), 500
    finally:
        db.close()

@generation_bp.route('/molecules/similarity', methods=['POST'])
def compute_similarity():
    """计算分子相似性"""
    data = request.get_json() or {}
    ref_smi = data.get('reference_smiles', '')
    target_smi = data.get('target_smiles', '')
    
    from ..services.utils import validate_smiles, compute_morgan_similarity
    
    ref_mol = validate_smiles(ref_smi)
    target_mol = validate_smiles(target_smi)
    
    if ref_mol is None or target_mol is None:
        return jsonify({'success': False, 'error': 'SMILES无效'}), 400
    
    sim = compute_morgan_similarity(ref_mol, target_mol)
    return jsonify({'success': True, 'data': {'similarity': round(sim, 4)}})
