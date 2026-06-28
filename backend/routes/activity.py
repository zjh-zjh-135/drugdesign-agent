"""活性预测路由"""
from flask import Blueprint, request, jsonify
from ..services.activity import (
    train_qsar_model, predict_activity, batch_predict,
    list_available_models, MODEL_DIR
)

activity_bp = Blueprint('activity', __name__, url_prefix='/api')


@activity_bp.route('/activity/predict', methods=['POST'])
def predict_single():
    """预测单个分子活性"""
    data = request.get_json() or {}
    smiles = data.get('smiles', '')
    model_name = data.get('model_name', 'default')
    activity_type = data.get('activity_type', 'IC50')
    
    if not smiles:
        return jsonify({'success': False, 'error': 'SMILES为空'}), 400
    
    result = predict_activity(smiles, model_name, activity_type)
    if result is None:
        return jsonify({'success': False, 'error': '预测失败'}), 500
    
    return jsonify({'success': True, 'data': result})


@activity_bp.route('/activity/predict_batch', methods=['POST'])
def predict_batch_endpoint():
    """批量预测分子活性"""
    data = request.get_json() or {}
    smiles_list = data.get('smiles_list', [])
    model_name = data.get('model_name', 'default')
    activity_type = data.get('activity_type', 'IC50')
    
    if not smiles_list:
        return jsonify({'success': False, 'error': 'SMILES列表为空'}), 400
    
    results = batch_predict(smiles_list, model_name, activity_type)
    
    return jsonify({
        'success': True,
        'data': {
            'results': results,
            'summary': {
                'total': len(results),
                'successful': sum(1 for r in results if 'error' not in r),
                'estimated': sum(1 for r in results if r.get('model_used') == 'estimated'),
                'model_used': sum(1 for r in results if r.get('model_used') == 'trained'),
            }
        }
    })


@activity_bp.route('/activity/train', methods=['POST'])
def train_model():
    """训练QSAR模型"""
    data = request.get_json() or {}
    smiles_list = data.get('smiles_list', [])
    activity_list = data.get('activity_list', [])
    model_name = data.get('model_name', 'default')
    activity_type = data.get('activity_type', 'IC50')
    
    if len(smiles_list) < 5:
        return jsonify({'success': False, 'error': '需要至少5个训练样本'}), 400
    if len(smiles_list) != len(activity_list):
        return jsonify({'success': False, 'error': 'SMILES和活性值数量不匹配'}), 400
    
    result = train_qsar_model(smiles_list, activity_list, model_name, activity_type)
    if result is None:
        return jsonify({'success': False, 'error': '模型训练失败'}), 500
    
    return jsonify({'success': True, 'data': result})


@activity_bp.route('/activity/models', methods=['GET'])
def list_models():
    """列出可用模型"""
    models = list_available_models()
    return jsonify({'success': True, 'data': models})


@activity_bp.route('/activity/models/<model_name>', methods=['DELETE'])
def delete_model(model_name):
    """删除模型"""
    import os, re
    
    # P2修复: 验证模型名称格式
    if not re.match(r'^[a-zA-Z0-9_-]+$', model_name) or len(model_name) > 64:
        return jsonify({'success': False, 'error': '模型名称格式无效'}), 400
    
    # 删除所有匹配该模型名的文件
    deleted = []
    for filename in os.listdir(MODEL_DIR):
        if filename.startswith(model_name + '_') and filename.endswith('.pkl'):
            os.remove(os.path.join(MODEL_DIR, filename))
            deleted.append(filename)
    
    return jsonify({
        'success': True,
        'data': {'deleted': deleted}
    })
