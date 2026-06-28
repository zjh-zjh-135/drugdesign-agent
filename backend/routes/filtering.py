"""过滤路由"""
from flask import Blueprint, request, jsonify
from ..services.filtering import MoleculeFilter
from ..models.database import init_db, GeneratedMolecule, MoleculeProperty
from ..config import DEFAULT_THRESHOLDS

filtering_bp = Blueprint('filtering', __name__, url_prefix='/api')
_SessionLocal = None

def _get_session():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = init_db()
    return __get_session()

@filtering_bp.route('/molecules/pains', methods=['GET'])
def get_pains_info():
    """获取PAINS信息"""
    return jsonify({
        'success': True,
        'data': {
            'description': 'PAINS (Pan-Assay Interference Compounds) 过滤',
            'patterns': ['含有硫醇、儿茶酚、醌、氢化喹啉等干扰基团的分子将被过滤']
        }
    })

@filtering_bp.route('/molecules/batch_filter', methods=['POST'])
def batch_filter():
    """批量应用过滤"""
    data = request.get_json() or {}
    molecule_ids = data.get('molecule_ids', [])
    filter_params = data.get('filter_params', DEFAULT_THRESHOLDS)
    
    db = _get_session()
    try:
        filter_engine = MoleculeFilter(filter_params)
        molecules = db.query(GeneratedMolecule).filter(
            GeneratedMolecule.id.in_(molecule_ids)
        ).all()
        
        passed = []
        failed = []
        for mol in molecules:
            ok, desc, reason = filter_engine.filter_single(mol.smiles)
            if ok:
                passed.append({'id': mol.id, 'smiles': mol.smiles})
            else:
                failed.append({'id': mol.id, 'smiles': mol.smiles, 'reason': reason})
        
        return jsonify({'success': True, 'data': {'passed': passed, 'failed': failed}})
    finally:
        db.close()
