"""分子对接路由"""
import os
from flask import Blueprint, request, jsonify
from ..models.database import GeneratedMolecule, Project, init_db
from ..services.docking import run_docking, batch_docking

docking_bp = Blueprint('docking', __name__, url_prefix='/api')
SessionLocal = init_db()


@docking_bp.route('/molecules/<int:molecule_id>/dock', methods=['POST'])
def dock_molecule(molecule_id):
    """对单个分子进行对接"""
    data = request.get_json() or {}
    
    db = SessionLocal()
    try:
        mol = db.query(GeneratedMolecule).filter(
            GeneratedMolecule.id == molecule_id
        ).first()
        if not mol:
            return jsonify({'success': False, 'error': '分子不存在'}), 404
        
        # 获取受体PDB（从项目或请求参数）
        receptor_pdb = data.get('receptor_pdb')
        if not receptor_pdb:
            project = db.query(Project).filter(
                Project.id == mol.project_id
            ).first()
            if project and project.target_pdb:
                # 尝试从PDB ID获取结构（简化：从请求中获取或返回错误）
                return jsonify({'success': False, 'error': '请提供受体PDB内容'}), 400
        
        # 对接参数
        center_x = float(data.get('center_x', 0.0))
        center_y = float(data.get('center_y', 0.0))
        center_z = float(data.get('center_z', 0.0))
        size_x = float(data.get('size_x', 20.0))
        size_y = float(data.get('size_y', 20.0))
        size_z = float(data.get('size_z', 20.0))
        exhaustiveness = int(data.get('exhaustiveness', 8))
        num_modes = int(data.get('num_modes', 9))
        
        result = run_docking(
            mol.smiles,
            receptor_pdb,
            center_x=center_x,
            center_y=center_y,
            center_z=center_z,
            size_x=size_x,
            size_y=size_y,
            size_z=size_z,
            exhaustiveness=exhaustiveness,
            num_modes=num_modes,
        )
        
        if result is None:
            return jsonify({'success': False, 'error': '对接失败'}), 500
        
        return jsonify({
            'success': True,
            'data': {
                'molecule_id': molecule_id,
                'smiles': mol.smiles,
                'docking_result': result,
            }
        })
    finally:
        db.close()


@docking_bp.route('/docking/batch', methods=['POST'])
def batch_dock():
    """批量对接"""
    data = request.get_json() or {}
    smiles_list = data.get('smiles_list', [])
    receptor_pdb = data.get('receptor_pdb')
    
    # P1修复: DoS防护，限制批量大小和PDB大小
    if len(smiles_list) > 100:
        return jsonify({'success': False, 'error': 'SMILES列表最多100个'}), 413
    if len(receptor_pdb) > 10 * 1024 * 1024:
        return jsonify({'success': False, 'error': '受体PDB内容过大，限制10MB'}), 413
    
    if not smiles_list:
        return jsonify({'success': False, 'error': 'SMILES列表为空'}), 400
    if not receptor_pdb:
        return jsonify({'success': False, 'error': '请提供受体PDB内容'}), 400
    
    center_x = float(data.get('center_x', 0.0))
    center_y = float(data.get('center_y', 0.0))
    center_z = float(data.get('center_z', 0.0))
    size_x = float(data.get('size_x', 20.0))
    size_y = float(data.get('size_y', 20.0))
    size_z = float(data.get('size_z', 20.0))
    exhaustiveness = int(data.get('exhaustiveness', 8))
    
    results = batch_docking(
        smiles_list, receptor_pdb,
        center_x, center_y, center_z,
        size_x, size_y, size_z,
        exhaustiveness,
    )
    
    return jsonify({
        'success': True,
        'data': {
            'results': results,
            'summary': {
                'total': len(results),
                'successful': sum(1 for r in results if r.get('result') is not None),
            }
        }
    })


@docking_bp.route('/docking/from_smiles', methods=['POST'])
def dock_from_smiles():
    """直接从SMILES对接（不依赖数据库）"""
    data = request.get_json() or {}
    smiles = data.get('smiles', '')
    receptor_pdb = data.get('receptor_pdb', '')
    
    if not smiles:
        return jsonify({'success': False, 'error': 'SMILES为空'}), 400
    if not receptor_pdb:
        return jsonify({'success': False, 'error': '请提供受体PDB内容'}), 400
    
    center_x = float(data.get('center_x', 0.0))
    center_y = float(data.get('center_y', 0.0))
    center_z = float(data.get('center_z', 0.0))
    size_x = float(data.get('size_x', 20.0))
    size_y = float(data.get('size_y', 20.0))
    size_z = float(data.get('size_z', 20.0))
    exhaustiveness = int(data.get('exhaustiveness', 8))
    num_modes = int(data.get('num_modes', 9))
    
    result = run_docking(
        smiles, receptor_pdb,
        center_x, center_y, center_z,
        size_x, size_y, size_z,
        exhaustiveness, num_modes,
    )
    
    if result is None:
        return jsonify({'success': False, 'error': '对接失败'}), 500
    
    return jsonify({
        'success': True,
        'data': {
            'smiles': smiles,
            'docking_result': result,
        }
    })


@docking_bp.route('/docking/fetch_pdb/<pdb_id>', methods=['GET'])
def fetch_pdb_from_rcsb(pdb_id):
    """从RCSB PDB下载受体结构"""
    import urllib.request
    
    pdb_id = pdb_id.upper().strip()
    url = f'https://files.rcsb.org/download/{pdb_id}.pdb'
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as response:
            content = response.read().decode('utf-8')
            
        # 过滤ATOM和HETATM记录，去除水分子和杂原子（可选）
        lines = content.split('\n')
        atom_lines = [l for l in lines if l.startswith('ATOM') or l.startswith('HETATM') or l.startswith('TER') or l.startswith('END')]
        
        return jsonify({
            'success': True,
            'data': {
                'pdb_id': pdb_id,
                'content': content,
                'atom_count': len([l for l in atom_lines if l.startswith('ATOM')]),
                'source_url': url,
            }
        })
    except Exception as e:
        return jsonify({
            'success': False, 
            'error': f'下载PDB失败: {str(e)}。请手动从 https://www.rcsb.org/structure/{pdb_id} 下载并粘贴内容。'
        }), 500


@docking_bp.route('/docking/vina_status', methods=['GET'])
def get_vina_status():
    """检查Vina安装状态"""
    from ..services.docking import VINA_EXE, _check_vina_available
    
    available = _check_vina_available()
    
    return jsonify({
        'success': True,
        'data': {
            'available': available,
            'path': VINA_EXE,
            'path_exists': os.path.exists(VINA_EXE),
        }
    })
