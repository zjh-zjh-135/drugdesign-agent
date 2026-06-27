"""3D分子结构路由"""
from flask import Blueprint, request, jsonify
from ..models.database import GeneratedMolecule, init_db
from ..services.structure import get_molecule_structure, get_structure_info

structure_bp = Blueprint('structure', __name__, url_prefix='/api')
SessionLocal = init_db()


@structure_bp.route('/molecules/<int:molecule_id>/structure', methods=['GET'])
def get_molecule_structure_endpoint(molecule_id):
    """获取分子3D结构（SDF/PDB/XYZ格式）"""
    format_type = request.args.get('format', 'sdf').lower()
    
    db = SessionLocal()
    try:
        mol = db.query(GeneratedMolecule).filter(
            GeneratedMolecule.id == molecule_id
        ).first()
        if not mol:
            return jsonify({'success': False, 'error': '分子不存在'}), 404
        
        structure = get_molecule_structure(mol.smiles, format=format_type)
        if structure is None:
            return jsonify({'success': False, 'error': '3D结构生成失败'}), 500
        
        # 根据格式返回适当的内容类型
        mime_types = {
            'sdf': 'chemical/x-mdl-molfile',
            'pdb': 'chemical/x-pdb',
            'xyz': 'chemical/x-xyz',
        }
        mime = mime_types.get(format_type, 'text/plain')
        
        from flask import Response
        return Response(structure, mimetype=mime)
    finally:
        db.close()


@structure_bp.route('/molecules/<int:molecule_id>/structure3d', methods=['GET'])
def get_molecule_structure3d(molecule_id):
    """获取分子3D结构信息和JSON格式坐标（供3Dmol.js使用）"""
    db = SessionLocal()
    try:
        mol = db.query(GeneratedMolecule).filter(
            GeneratedMolecule.id == molecule_id
        ).first()
        if not mol:
            return jsonify({'success': False, 'error': '分子不存在'}), 404
        
        # 生成SDF格式
        sdf = get_molecule_structure(mol.smiles, format='sdf')
        if sdf is None:
            return jsonify({'success': False, 'error': '3D结构生成失败'}), 500
        
        # 获取结构信息
        info = get_structure_info(mol.smiles)
        
        return jsonify({
            'success': True,
            'data': {
                'molecule_id': molecule_id,
                'smiles': mol.smiles,
                'format': 'sdf',
                'sdf': sdf,
                'structure_info': info,
            }
        })
    finally:
        db.close()


@structure_bp.route('/molecules/structure/from_smiles', methods=['POST'])
def get_structure_from_smiles():
    """从SMILES直接获取3D结构（不依赖数据库）"""
    data = request.get_json() or {}
    smiles = data.get('smiles', '')
    format_type = data.get('format', 'sdf').lower()
    
    if not smiles:
        return jsonify({'success': False, 'error': 'SMILES为空'}), 400
    
    structure = get_molecule_structure(smiles, format=format_type)
    if structure is None:
        return jsonify({'success': False, 'error': '3D结构生成失败'}), 500
    
    info = get_structure_info(smiles)
    
    return jsonify({
        'success': True,
        'data': {
            'smiles': smiles,
            'format': format_type,
            'structure': structure,
            'structure_info': info,
        }
    })
