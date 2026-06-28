"""逆合成路由"""
import json
from flask import Blueprint, request, jsonify
from ..models.database import init_db, GeneratedMolecule, SynthesisRoute
from ..services.synthesis import SynthesisAnalyzer, generate_route_structures

synthesis_bp = Blueprint('synthesis', __name__, url_prefix='/api')
_SessionLocal = None

def _get_session():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = init_db()
    return __get_session()


@synthesis_bp.route('/synthesis/analyze', methods=['POST'])
def analyze_synthesis_from_smiles():
    """直接从SMILES进行逆合成分析，返回结构化合成路线+2D结构图"""
    data = request.get_json()
    smiles = data.get('smiles', '')

    if not smiles:
        return jsonify({'success': False, 'error': 'SMILES不能为空'}), 400

    try:
        analyzer = SynthesisAnalyzer()
        result = analyzer.analyze(smiles)

        if 'error' in result:
            return jsonify({'success': False, 'error': result['error']}), 400

        route = result.get('route', {})
        nodes = route.get('nodes', [])

        # 构建正向合成步骤（从起始原料到目标分子）
        steps = []
        reversed_nodes = list(reversed(nodes)) if nodes else []

        for i, node in enumerate(reversed_nodes):
            steps.append({
                'step': i + 1,
                'reaction_name': node.get('reaction_name', ''),
                'reaction_type': node.get('reaction_type', ''),
                'reagents': node.get('reagents', []),
                'solvent': node.get('solvent', ''),
                'temperature': node.get('temperature', ''),
                'time': node.get('time', ''),
                'yield': node.get('yield', 0),
                'description': node.get('description', ''),
            })

        # 使用新的 generate_route_structures 生成所有节点2D结构图
        structures = generate_route_structures(smiles, steps)

        return jsonify({
            'success': True,
            'data': {
                'smiles': smiles,
                'num_steps': result.get('num_steps', 0),
                'estimated_cost': result.get('estimated_cost', 0),
                'availability_score': result.get('availability_score', 0),
                'total_yield': route.get('total_yield', 0),
                'status': result.get('status', 'simulated'),
                'analysis': result.get('analysis', {}),
                'steps': steps,
                'structures': structures
            }
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': f'合成分析失败: {str(e)}'}), 500


@synthesis_bp.route('/molecules/<int:molecule_id>/synthesis', methods=['POST'])
def analyze_synthesis(molecule_id):
    """启动逆合成分析"""
    db = _get_session()
    try:
        mol = db.query(GeneratedMolecule).filter(GeneratedMolecule.id == molecule_id).first()
        if not mol:
            return jsonify({'success': False, 'error': '分子不存在'}), 404

        if not mol.smiles:
            return jsonify({'success': False, 'error': '分子SMILES为空'}), 400

        analyzer = SynthesisAnalyzer()
        result = analyzer.analyze(mol.smiles)

        if 'error' in result:
            return jsonify({'success': False, 'error': result['error']}), 400

        route = SynthesisRoute(
            molecule_id=molecule_id,
            route_json=json.dumps(result.get('route'), ensure_ascii=False),
            num_steps=result.get('num_steps'),
            estimated_cost=result.get('estimated_cost'),
            availability_score=result.get('availability_score'),
            status=result.get('status', 'completed')
        )
        db.add(route)
        db.commit()

        return jsonify({'success': True, 'data': result})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': f'合成分析失败: {str(e)}'}), 500
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'error': f'数据库操作失败: {str(e)}'}), 500
    finally:
        db.close()


@synthesis_bp.route('/synthesis/status/<job_id>', methods=['GET'])
def get_synthesis_status(job_id):
    """获取合成分析状态"""
    return jsonify({'success': True, 'data': {'status': 'completed'}})


@synthesis_bp.route('/synthesis/results/<job_id>', methods=['GET'])
def get_synthesis_results(job_id):
    """获取合成分析结果"""
    return jsonify({'success': True, 'data': {}})
