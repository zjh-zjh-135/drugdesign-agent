"""ADMET预测路由"""
from flask import Blueprint, request, jsonify
from ..models.database import init_db, GeneratedMolecule, AdmetPrediction, MoleculeProperty
from ..services.admet import AdmetPredictor

admet_bp = Blueprint('admet', __name__, url_prefix='/api')
SessionLocal = init_db()

@admet_bp.route('/molecules/<int:molecule_id>/admet', methods=['GET'])
def get_admet(molecule_id):
    """获取分子完整五分类ADMET预测"""
    db = SessionLocal()
    try:
        mol = db.query(GeneratedMolecule).filter(GeneratedMolecule.id == molecule_id).first()
        if not mol:
            return jsonify({'success': False, 'error': '分子不存在'}), 404
        
        predictor = AdmetPredictor()
        result = predictor.predict(mol.smiles)
        
        if 'error' in result:
            return jsonify({'success': False, 'error': result['error']}), 400
        
        # 检查是否已有预测记录（兼容旧schema，仅存储核心字段）
        admet = db.query(AdmetPrediction).filter(
            AdmetPrediction.molecule_id == molecule_id
        ).first()
        
        if not admet:
            # 兼容旧schema：概率值存入数据库时转为0-100
            bbb_val = result['distribution']['bbb']
            oral_val = result['absorption']['oral_bioavailability']
            admet = AdmetPrediction(
                molecule_id=molecule_id,
                solubility=result['absorption']['solubility'],
                permeability=result['absorption']['permeability'],
                bbb=bbb_val * 100 if bbb_val <= 1 else bbb_val,
                herg=result['toxicity']['herg'],
                ames=result['toxicity']['ames'],
                dili=result['toxicity']['dili'],
                cyp_inhibition=result['metabolism']['cyp_inhibition'],
                oral_bioavailability=oral_val * 100 if oral_val <= 1 else oral_val,
                overall_score=result['overall_score'],
            )
            db.add(admet)
            db.commit()
        
        return jsonify({
            'success': True,
            'data': result
        })
    finally:
        db.close()

@admet_bp.route('/molecules/batch_admet', methods=['POST'])
def batch_admet():
    """批量ADMET预测 - 返回完整五分类数据"""
    data = request.get_json() or {}
    molecule_ids = data.get('molecule_ids', [])
    
    db = SessionLocal()
    try:
        predictor = AdmetPredictor()
        results = []
        
        for mid in molecule_ids:
            mol = db.query(GeneratedMolecule).filter(GeneratedMolecule.id == mid).first()
            if not mol:
                continue
            
            result = predictor.predict(mol.smiles)
            if 'error' in result:
                continue
            
            # 检查是否已有预测
            existing = db.query(AdmetPrediction).filter(
                AdmetPrediction.molecule_id == mid
            ).first()
            
            if not existing:
                bbb_val = result['distribution']['bbb']
                oral_val = result['absorption']['oral_bioavailability']
                admet = AdmetPrediction(
                    molecule_id=mid,
                    solubility=result['absorption']['solubility'],
                    permeability=result['absorption']['permeability'],
                    bbb=bbb_val * 100 if bbb_val <= 1 else bbb_val,
                    herg=result['toxicity']['herg'],
                    ames=result['toxicity']['ames'],
                    dili=result['toxicity']['dili'],
                    cyp_inhibition=result['metabolism']['cyp_inhibition'],
                    oral_bioavailability=oral_val * 100 if oral_val <= 1 else oral_val,
                    overall_score=result['overall_score'],
                )
                db.add(admet)
            
            results.append({
                'molecule_id': mid,
                'data': result,
            })
        
        db.commit()
        return jsonify({'success': True, 'data': results})
    finally:
        db.close()

@admet_bp.route('/admet/analyze', methods=['POST'])
def analyze_admet():
    """直接分析SMILES的完整五分类ADMET（不存入数据库）"""
    data = request.get_json() or {}
    smiles = data.get('smiles', '')
    
    if not smiles:
        return jsonify({'success': False, 'error': 'SMILES不能为空'}), 400
    
    predictor = AdmetPredictor()
    result = predictor.predict(smiles)
    
    if 'error' in result:
        return jsonify({'success': False, 'error': result['error']}), 400
    
    return jsonify({
        'success': True,
        'data': result
    })
