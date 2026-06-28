"""分子管理路由"""
import os
from flask import Blueprint, request, jsonify, send_from_directory
from ..models.database import (
    GeneratedMolecule, MoleculeProperty, AdmetPrediction, 
    Project, init_db
)
from ..services.utils import validate_smiles, canonicalize_smiles, save_molecule_svg
from ..config import MOLECULE_IMG_DIR

molecules_bp = Blueprint('molecules', __name__, url_prefix='/api')
_SessionLocal = None

def _get_session():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = init_db()
    return __get_session()

@molecules_bp.route('/projects/<int:project_id>/molecules', methods=['GET'])
def list_molecules(project_id):
    """列出项目中的分子"""
    status = request.args.get('status', '')
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))
    
    db = _get_session()
    try:
        query = db.query(GeneratedMolecule).filter(
            GeneratedMolecule.project_id == project_id
        )
        if status:
            query = query.filter(GeneratedMolecule.pipeline_status == status)
        
        total = query.count()
        molecules = query.offset((page - 1) * per_page).limit(per_page).all()
        
        data = []
        for mol in molecules:
            prop = db.query(MoleculeProperty).filter(
                MoleculeProperty.molecule_id == mol.id
            ).first()
            admet = db.query(AdmetPrediction).filter(
                AdmetPrediction.molecule_id == mol.id
            ).first()
            
            data.append({
                'id': mol.id,
                'smiles': mol.smiles,
                'status': mol.pipeline_status,
                'generation_strategy': mol.generation_strategy,
                'created_at': mol.created_at.isoformat() if mol.created_at else None,
                'properties': {
                    'mw': prop.mw if prop else None,
                    'clogp': prop.clogp if prop else None,
                    'tpsa': prop.tpsa if prop else None,
                    'qed': prop.qed if prop else None,
                    'sa_score': prop.sa_score if prop else None,
                    'similarity_score': prop.similarity_score if prop else None,
                },
                'admet': {
                    'overall_score': admet.overall_score if admet else None,
                } if admet else None,
            })
        
        return jsonify({
            'success': True,
            'data': data,
            'pagination': {
                'total': total,
                'page': page,
                'per_page': per_page,
                'pages': (total + per_page - 1) // per_page
            }
        })
    finally:
        db.close()

@molecules_bp.route('/molecules/<int:molecule_id>', methods=['GET'])
def get_molecule(molecule_id):
    """获取分子详情"""
    db = _get_session()
    try:
        mol = db.query(GeneratedMolecule).filter(GeneratedMolecule.id == molecule_id).first()
        if not mol:
            return jsonify({'success': False, 'error': '分子不存在'}), 404
        
        prop = db.query(MoleculeProperty).filter(
            MoleculeProperty.molecule_id == molecule_id
        ).first()
        admet = db.query(AdmetPrediction).filter(
            AdmetPrediction.molecule_id == molecule_id
        ).first()
        
        return jsonify({
            'success': True,
            'data': {
                'id': mol.id,
                'smiles': mol.smiles,
                'status': mol.pipeline_status,
                'generation_strategy': mol.generation_strategy,
                'generated_from': mol.generated_from,
                'properties': {
                    'mw': prop.mw if prop else None,
                    'clogp': prop.clogp if prop else None,
                    'tpsa': prop.tpsa if prop else None,
                    'hbd': prop.hbd if prop else None,
                    'hba': prop.hba if prop else None,
                    'rotb': prop.rotb if prop else None,
                    'sa_score': prop.sa_score if prop else None,
                    'qed': prop.qed if prop else None,
                    'pass_pains': prop.pass_pains if prop else None,
                    'pass_filters': prop.pass_filters if prop else None,
                    'pass_admet': prop.pass_admet if prop else None,
                    'similarity_score': prop.similarity_score if prop else None,
                },
                'admet': {
                    'solubility': admet.solubility if admet else None,
                    'permeability': admet.permeability if admet else None,
                    'bbb': admet.bbb if admet else None,
                    'herg': admet.herg if admet else None,
                    'ames': admet.ames if admet else None,
                    'dili': admet.dili if admet else None,
                    'cyp_inhibition': admet.cyp_inhibition if admet else None,
                    'oral_bioavailability': admet.oral_bioavailability if admet else None,
                    'overall_score': admet.overall_score if admet else None,
                } if admet else None,
            }
        })
    finally:
        db.close()

@molecules_bp.route('/molecules/<int:molecule_id>/svg', methods=['GET'])
def get_molecule_svg(molecule_id):
    """获取分子SVG图片"""
    filepath = os.path.join(MOLECULE_IMG_DIR, f'{molecule_id}.svg')
    if os.path.exists(filepath):
        return send_from_directory(MOLECULE_IMG_DIR, f'{molecule_id}.svg')
    
    # 如果文件不存在，动态生成
    db = _get_session()
    try:
        mol = db.query(GeneratedMolecule).filter(GeneratedMolecule.id == molecule_id).first()
        if not mol:
            return jsonify({'success': False, 'error': '分子不存在'}), 404
        
        save_molecule_svg(mol.smiles, filepath)
        return send_from_directory(MOLECULE_IMG_DIR, f'{molecule_id}.svg')
    finally:
        db.close()

@molecules_bp.route('/molecules', methods=['POST'])
def create_molecule():
    """创建单个分子"""
    data = request.get_json() or {}
    smi = data.get('smiles', '')
    project_id = data.get('project_id')
    
    canon = canonicalize_smiles(smi)
    if not canon:
        return jsonify({'success': False, 'error': 'SMILES无效'}), 400
    
    db = _get_session()
    try:
        mol = GeneratedMolecule(
            project_id=project_id,
            smiles=canon,
            pipeline_status='generated'
        )
        db.add(mol)
        db.commit()
        db.refresh(mol)
        return jsonify({'success': True, 'data': {'id': mol.id}})
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'error': f'数据库操作失败: {str(e)}'}), 500
    finally:
        db.close()

@molecules_bp.route('/molecules/batch', methods=['POST'])
def batch_upload_molecules():
    """批量上传分子"""
    data = request.get_json() or {}
    smiles_list = data.get('smiles_list', [])
    project_id = data.get('project_id')
    
    if not smiles_list:
        return jsonify({'success': False, 'error': 'SMILES列表为空'}), 400
    
    # P2修复: 限制批量大小，防止DoS
    if len(smiles_list) > 100:
        return jsonify({'success': False, 'error': 'SMILES列表最多100个'}), 413
    
    db = _get_session()
    try:
        added = 0
        for smi in smiles_list:
            canon = canonicalize_smiles(smi)
            if canon:
                mol = GeneratedMolecule(
                    project_id=project_id,
                    smiles=canon,
                    pipeline_status='generated'
                )
                db.add(mol)
                added += 1
        db.commit()
        return jsonify({'success': True, 'data': {'added': added}})
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'error': f'数据库操作失败: {str(e)}'}), 500
    finally:
        db.close()

@molecules_bp.route('/molecules/<int:molecule_id>', methods=['DELETE'])
def delete_molecule(molecule_id):
    """删除分子"""
    db = _get_session()
    try:
        mol = db.query(GeneratedMolecule).filter(GeneratedMolecule.id == molecule_id).first()
        if not mol:
            return jsonify({'success': False, 'error': '分子不存在'}), 404
        db.delete(mol)
        db.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'error': f'数据库操作失败: {str(e)}'}), 500
    finally:
        db.close()
