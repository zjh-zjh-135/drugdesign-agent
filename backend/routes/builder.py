"""分子构建器高级功能路由 — 5大核心API"""
from flask import Blueprint, request, jsonify
import io
import math
import numpy as np

builder_bp = Blueprint('builder', __name__, url_prefix='/api')


# ========== 工具函数 ==========

def atoms_bonds_to_smiles(atoms, bonds):
    """使用 RDKit 将前端原子/键结构转为 SMILES 字符串（最可靠方式）"""
    from rdkit import Chem
    if not atoms:
        return ''
    
    mol = Chem.EditableMol(Chem.Mol())
    id_map = {}
    for a in atoms:
        atom = Chem.Atom(a['element'])
        if a.get('charge', 0) != 0:
            atom.SetFormalCharge(a['charge'])
        idx = mol.AddAtom(atom)
        id_map[a['id']] = idx
    
    for b in bonds:
        i = id_map.get(b['from'], -1)
        j = id_map.get(b['to'], -1)
        if i < 0 or j < 0:
            continue
        bt = b.get('type', 1)
        bond_type = Chem.BondType.SINGLE if bt == 1 else Chem.BondType.DOUBLE if bt == 2 else Chem.BondType.TRIPLE
        mol.AddBond(i, j, bond_type)
    
    try:
        m = mol.GetMol()
        Chem.SanitizeMol(m)
        return Chem.MolToSmiles(m)
    except Exception:
        return ''


def smiles_to_mol(smiles):
    """SMILES转RDKit Mol对象"""
    from rdkit import Chem
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        mol = Chem.MolFromSmiles(smiles, sanitize=False)
    return mol


# ========== 1. 3D 构象生成 ==========

@builder_bp.route('/builder/conformer', methods=['POST'])
def generate_conformer():
    """接收2D原子/键结构，生成3D构象，返回坐标和能量"""
    from rdkit import Chem
    from rdkit.Chem import AllChem
    data = request.get_json() or {}
    atoms = data.get('atoms', [])
    bonds = data.get('bonds', [])
    
    if not atoms:
        return jsonify({'success': False, 'error': '没有原子'}), 400
    
    try:
        # 构建SMILES
        smi = atoms_bonds_to_smiles(atoms, bonds)
        if not smi:
            return jsonify({'success': False, 'error': '无法解析结构'}), 400
        
        mol = Chem.MolFromSmiles(smi)
        if mol is None:
            return jsonify({'success': False, 'error': f'SMILES解析失败: {smi}'}), 400
        
        mol = Chem.AddHs(mol)
        
        # 使用 ETKDGv3 生成3D构象
        params = AllChem.ETKDGv3()
        params.randomSeed = 42
        err = AllChem.EmbedMolecule(mol, params)
        if err != 0:
            # 回退到简单嵌入
            err = AllChem.EmbedMolecule(mol, randomSeed=42)
        
        if err != 0:
            return jsonify({'success': False, 'error': '3D构象生成失败'}), 400
        
        # MMFF 力场优化
        try:
            AllChem.MMFFOptimizeMolecule(mol, mmffVariant='MMFF94')
        except:
            pass
        
        conf = mol.GetConformer()
        
        # 计算能量
        energy = 0.0
        try:
            mmff_props = AllChem.MMFFGetMoleculeProperties(mol, mmffVariant='MMFF94')
            if mmff_props:
                energy = AllChem.MMFFGetMoleculeForceField(mol, mmff_props).CalcEnergy()
        except:
            pass
        
        coords = []
        for i in range(mol.GetNumAtoms()):
            pos = conf.GetAtomPosition(i)
            coords.append({
                'x': round(pos.x, 3),
                'y': round(pos.y, 3),
                'z': round(pos.z, 3),
            })
        
        return jsonify({
            'success': True,
            'smiles': smi,
            'coords': coords,
            'energy': round(energy, 2),
            'num_atoms': mol.GetNumAtoms()
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ========== 2. ADMET 规则检查 ==========

@builder_bp.route('/builder/admet', methods=['POST'])
def check_admet_rules():
    """实时计算 Lipinski、Veber 规则及 PAINS 警告"""
    from rdkit import Chem
    from rdkit.Chem import Descriptors, Crippen, rdMolDescriptors
    data = request.get_json() or {}
    smiles = data.get('smiles', '')
    
    if not smiles:
        return jsonify({'success': False, 'error': 'SMILES 为空'}), 400
    
    try:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return jsonify({'success': False, 'error': 'SMILES 解析失败'}), 400
        
        mol = Chem.AddHs(mol)
        
        # 基础描述符
        mw = round(Descriptors.MolWt(mol), 2)
        logp = round(Crippen.MolLogP(mol), 2)
        tpsa = round(rdMolDescriptors.CalcTPSA(mol), 2)
        hbd = rdMolDescriptors.CalcNumHBD(mol)
        hba = rdMolDescriptors.CalcNumHBA(mol)
        rot_bonds = Descriptors.NumRotatableBonds(mol)
        
        # Lipinski 五规则
        lipinski_pass = (mw <= 500 and logp <= 5 and hbd <= 5 and hba <= 10)
        lipinski_violations = []
        if mw > 500: lipinski_violations.append(f'分子量 {mw} > 500')
        if logp > 5: lipinski_violations.append(f'logP {logp} > 5')
        if hbd > 5: lipinski_violations.append(f'HBD {hbd} > 5')
        if hba > 10: lipinski_violations.append(f'HBA {hba} > 10')
        
        # Veber 规则
        veber_pass = (rot_bonds <= 10 and tpsa <= 140)
        veber_violations = []
        if rot_bonds > 10: veber_violations.append(f'旋转键 {rot_bonds} > 10')
        if tpsa > 140: veber_violations.append(f'TPSA {tpsa} > 140')
        
        # 简单 PAINS 检查（常见干扰结构片段）
        pains_warnings = []
        # 定义一些常见PAINS SMARTS模式（简化版）
        pains_patterns = [
            ('c1ccc2c(c1)ncn2', '苯并咪唑类'),
            ('c1ccc2c(c1)nc[nH]2', '苯并咪唑类'),
            ('c1ccc2c(c1)ncn2C', '苯并咪唑N-烷基'),
            ('[N+](=O)[O-]', '硝基'),
            ('c1ccc(cc1)S(=O)(=O)N', '磺胺类'),
            ('C(=O)N1CCCC1', '内酰胺'),
            ('c1cc(ccc1O)O', '邻苯二酚'),
            ('c1cc(ccc1N)N', '邻苯二胺'),
            ('C(=C)C(=O)', 'α,β-不饱和羰基'),
            ('c1csc(c1)C(=O)', '噻吩酮'),
        ]
        
        for smarts, name in pains_patterns:
            try:
                patt = Chem.MolFromSmarts(smarts)
                if patt and mol.HasSubstructMatch(patt):
                    pains_warnings.append(name)
            except:
                pass
        
        return jsonify({
            'success': True,
            'smiles': smiles,
            'mw': mw,
            'logp': logp,
            'tpsa': tpsa,
            'hbd': hbd,
            'hba': hba,
            'rotatable_bonds': rot_bonds,
            'lipinski': {
                'pass': lipinski_pass,
                'violations': lipinski_violations
            },
            'veber': {
                'pass': veber_pass,
                'violations': veber_violations
            },
            'pains': {
                'warnings': list(set(pains_warnings)),
                'count': len(set(pains_warnings))
            },
            'overall_pass': lipinski_pass and veber_pass and len(pains_warnings) == 0,
            'druglikeness_score': max(0, 100 - len(lipinski_violations) * 20 - len(veber_violations) * 15 - len(pains_warnings) * 10)
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ========== 3. 骨架跃迁 ==========

# 模板定义：骨架元素和连接点位置
SCAFFOLD_TEMPLATES = {
    'benzene': {
        'elements': ['C', 'C', 'C', 'C', 'C', 'C'],
        'bonds': [(0,1,1), (1,2,1), (2,3,1), (3,4,1), (4,5,1), (5,0,1)],
        'attachment_points': [0, 1, 2, 3, 4, 5],  # 6个连接点
        'name': '苯环',
        'is_aromatic': True
    },
    'pyridine': {
        'elements': ['C', 'N', 'C', 'C', 'C', 'C'],
        'bonds': [(0,1,1), (1,2,1), (2,3,1), (3,4,1), (4,5,1), (5,0,1)],
        'attachment_points': [0, 2, 3, 4, 5],
        'name': '吡啶',
        'is_aromatic': True
    },
    'pyrimidine': {
        'elements': ['C', 'N', 'C', 'N', 'C', 'C'],
        'bonds': [(0,1,1), (1,2,1), (2,3,1), (3,4,1), (4,5,1), (5,0,1)],
        'attachment_points': [0, 2, 4, 5],
        'name': '嘧啶',
        'is_aromatic': True
    },
    'thiophene': {
        'elements': ['C', 'C', 'S', 'C', 'C'],
        'bonds': [(0,1,1), (1,2,1), (2,3,1), (3,4,1), (4,0,1)],
        'attachment_points': [0, 1, 3, 4],
        'name': '噻吩',
        'is_aromatic': True
    },
    'furan': {
        'elements': ['C', 'C', 'O', 'C', 'C'],
        'bonds': [(0,1,1), (1,2,1), (2,3,1), (3,4,1), (4,0,1)],
        'attachment_points': [0, 1, 3, 4],
        'name': '呋喃',
        'is_aromatic': True
    },
    'imidazole': {
        'elements': ['C', 'N', 'C', 'N', 'C'],
        'bonds': [(0,1,1), (1,2,1), (2,3,1), (3,4,1), (4,0,1)],
        'attachment_points': [0, 2, 4],
        'name': '咪唑',
        'is_aromatic': True
    },
    'cyclohexane': {
        'elements': ['C', 'C', 'C', 'C', 'C', 'C'],
        'bonds': [(0,1,1), (1,2,1), (2,3,1), (3,4,1), (4,5,1), (5,0,1)],
        'attachment_points': [0, 1, 2, 3, 4, 5],
        'name': '环己烷',
        'is_aromatic': False
    },
    'cyclopentane': {
        'elements': ['C', 'C', 'C', 'C', 'C'],
        'bonds': [(0,1,1), (1,2,1), (2,3,1), (3,4,1), (4,0,1)],
        'attachment_points': [0, 1, 2, 3, 4],
        'name': '环戊烷',
        'is_aromatic': False
    },
    'naphthalene': {
        'elements': ['C', 'C', 'C', 'C', 'C', 'C', 'C', 'C', 'C', 'C'],
        'bonds': [(0,1,1), (1,2,1), (2,3,1), (3,4,1), (4,5,1), (5,0,1), (1,6,1), (6,7,1), (7,8,1), (8,9,1), (9,4,1)],
        'attachment_points': [0, 2, 3, 5, 6, 7, 8, 9],
        'name': '萘',
        'is_aromatic': True
    },
}


@builder_bp.route('/builder/scaffold', methods=['POST'])
def scaffold_hop():
    """骨架跃迁：将选中环替换为目标骨架"""
    data = request.get_json() or {}
    atoms = data.get('atoms', [])
    bonds = data.get('bonds', [])
    target = data.get('target_scaffold', '')
    ring_atoms = data.get('ring_atoms', [])  # 要替换的环的原子ID列表
    
    if not ring_atoms or not target:
        return jsonify({'success': False, 'error': '缺少环原子或目标骨架'}), 400
    
    tpl = SCAFFOLD_TEMPLATES.get(target)
    if not tpl:
        return jsonify({'success': False, 'error': f'未知骨架: {target}'}), 400
    
    try:
        # 找到环上的原子
        ring_atoms_data = [a for a in atoms if a['id'] in ring_atoms]
        if len(ring_atoms_data) < 3:
            return jsonify({'success': False, 'error': '环原子数不足'}), 400
        
        # 计算环中心
        cx = sum(a['x'] for a in ring_atoms_data) / len(ring_atoms_data)
        cy = sum(a['y'] for a in ring_atoms_data) / len(ring_atoms_data)
        
        # 环外键：与环原子相连但另一端不在环中的键
        external_bonds = []
        for b in bonds:
            f_in = b['from'] in ring_atoms
            t_in = b['to'] in ring_atoms
            if f_in != t_in:  # 一端在环内，一端在环外
                external_bonds.append(b)
        
        # 删除旧环原子和键
        new_atoms = [a for a in atoms if a['id'] not in ring_atoms]
        new_bonds = [b for b in bonds if b['from'] not in ring_atoms and b['to'] not in ring_atoms]
        
        # 创建新骨架原子
        n_ring = len(tpl['elements'])
        R = 80  # 环半径
        new_ring_atoms = []
        for i, el in enumerate(tpl['elements']):
            angle = -Math.PI/2 + (2 * Math.PI * i) / n_ring  # 从上方开始
            # 使用 Python 的 math
            import math
            angle = -math.pi/2 + (2 * math.pi * i) / n_ring
            new_ring_atoms.append({
                'id': f'sc_{i}_{hash(target)}',
                'element': el,
                'x': cx + math.cos(angle) * R,
                'y': cy + math.sin(angle) * R,
                'z': 0,
                'charge': 0,
                'implicitH': 0
            })
        
        # 创建骨架内键
        for f, t, bt in tpl['bonds']:
            new_bonds.append({
                'id': f'scb_{f}_{t}_{hash(target)}',
                'from': new_ring_atoms[f]['id'],
                'to': new_ring_atoms[t]['id'],
                'type': bt,
                'stereo': 'none'
            })
        
        # 重新连接外部键
        # 将外部键连接到新骨架的最近连接点
        ext_connections = []
        for b in external_bonds:
            ring_id = b['from'] if b['from'] in ring_atoms else b['to']
            ext_id = b['to'] if b['from'] in ring_atoms else b['from']
            ring_atom = next((a for a in ring_atoms_data if a['id'] == ring_id), None)
            if ring_atom:
                ext_connections.append({
                    'ext_id': ext_id,
                    'ring_x': ring_atom['x'],
                    'ring_y': ring_atom['y'],
                    'type': b['type']
                })
        
        # 将外部键连接到最近的连接点
        ap = tpl['attachment_points']
        for conn in ext_connections:
            min_dist = float('inf')
            best_idx = 0
            for idx in ap:
                a = new_ring_atoms[idx]
                d = (a['x'] - conn['ring_x'])**2 + (a['y'] - conn['ring_y'])**2
                if d < min_dist:
                    min_dist = d
                    best_idx = idx
            new_bonds.append({
                'id': f'ext_{conn["ext_id"]}_{new_ring_atoms[best_idx]["id"]}',
                'from': conn['ext_id'],
                'to': new_ring_atoms[best_idx]['id'],
                'type': conn['type'],
                'stereo': 'none'
            })
        
        new_atoms.extend(new_ring_atoms)
        
        return jsonify({
            'success': True,
            'atoms': new_atoms,
            'bonds': new_bonds,
            'replaced_ring_size': len(ring_atoms),
            'new_ring_size': n_ring,
            'external_connections': len(ext_connections)
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ========== 4. 分子对齐 ==========

@builder_bp.route('/builder/align', methods=['POST'])
def align_molecules():
    """多分子公共子结构对齐"""
    from rdkit import Chem
    from rdkit.Chem import rdFMCS
    data = request.get_json() or {}
    molecules = data.get('molecules', [])
    reference_index = data.get('reference_index', 0)
    
    if not molecules or len(molecules) < 2:
        return jsonify({'success': False, 'error': '至少需要2个分子'}), 400
    
    try:
        result_molecules = []
        
        # 将每个分子转为SMILES再转为RDKit Mol
        mols = []
        for mol_data in molecules:
            smi = atoms_bonds_to_smiles(mol_data.get('atoms', []), mol_data.get('bonds', []))
            mol = Chem.MolFromSmiles(smi) if smi else None
            if mol is None:
                return jsonify({'success': False, 'error': f'分子 {len(mols)} 解析失败: {smi}'}), 400
            mols.append(mol)
        
        # 参考分子
        ref_mol = mols[reference_index]
        
        # 计算每个分子与参考分子的MCS
        aligned = []
        for i, mol in enumerate(mols):
            if i == reference_index:
                aligned.append({
                    'index': i,
                    'smiles': Chem.MolToSmiles(mol),
                    'atoms': molecules[i]['atoms'],
                    'bonds': molecules[i]['bonds'],
                    'rmsd': 0.0,
                    'mcs_atoms': mol.GetNumAtoms()
                })
                continue
            
            # 使用FMCS找公共子结构
            mcs_result = rdFMCS.FindMCS([ref_mol, mol])
            mcs_smarts = mcs_result.smartsString
            
            # 计算MCS原子数
            mcs_mol = Chem.MolFromSmarts(mcs_smarts) if mcs_smarts else None
            mcs_atom_count = mcs_mol.GetNumAtoms() if mcs_mol else 0
            
            # 简单对齐：将分子i的坐标平移使MCS中心与参考分子重合
            ref_atoms = molecules[reference_index]['atoms']
            mol_atoms = molecules[i]['atoms']
            
            # 计算两个分子的中心
            ref_cx = sum(a['x'] for a in ref_atoms) / len(ref_atoms)
            ref_cy = sum(a['y'] for a in ref_atoms) / len(ref_atoms)
            mol_cx = sum(a['x'] for a in mol_atoms) / len(mol_atoms)
            mol_cy = sum(a['y'] for a in mol_atoms) / len(mol_atoms)
            
            dx = ref_cx - mol_cx
            dy = ref_cy - mol_cy
            
            aligned_atoms = [{**a, 'x': a['x'] + dx, 'y': a['y'] + dy} for a in mol_atoms]
            
            # 估算 RMSD
            rmsd = math.sqrt((dx**2 + dy**2)) / max(1, len(mol_atoms)) if len(mol_atoms) > 0 else 0
            
            aligned.append({
                'index': i,
                'smiles': Chem.MolToSmiles(mol),
                'atoms': aligned_atoms,
                'bonds': molecules[i]['bonds'],
                'rmsd': round(rmsd, 3),
                'mcs_atoms': mcs_atom_count
            })
        
        return jsonify({
            'success': True,
            'aligned_molecules': aligned,
            'reference_index': reference_index,
            'num_molecules': len(molecules)
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ========== 5. 蛋白质口袋加载 ==========

@builder_bp.route('/builder/pocket', methods=['POST'])
def load_pocket():
    """解析 PDB 内容，提取蛋白质口袋重原子"""
    data = request.get_json() or {}
    pdb_content = data.get('pdb_content', '')
    
    # P1修复: DoS防护，限制PDB内容大小
    if len(pdb_content) > 10 * 1024 * 1024:  # 10MB
        return jsonify({'success': False, 'error': 'PDB内容过大，限制10MB'}), 413
        return jsonify({'success': False, 'error': 'PDB 内容为空'}), 400
    
    try:
        pocket_atoms = []
        
        for line in pdb_content.split('\n'):
            if not line.startswith('ATOM ') and not line.startswith('HETATM'):
                continue
            
            # 解析 PDB 行
            # 标准格式：ATOM  serial  name  resName  chain  resSeq  x  y  z  ...
            try:
                serial = int(line[6:11].strip())
                name = line[12:16].strip()
                res_name = line[17:20].strip()
                x = float(line[30:38].strip())
                y = float(line[38:46].strip())
                z = float(line[46:54].strip())
                element = line[76:78].strip() if len(line) > 76 else name[0]
                
                # 只保留重原子（非H）
                if element == 'H':
                    continue
                
                # 只保留蛋白质残基（排除水、配体）
                if res_name in ['HOH', 'WAT', 'SOL', 'LIG']:
                    continue
                
                # 将pm转为显示坐标（缩放）
                pocket_atoms.append({
                    'serial': serial,
                    'element': element,
                    'name': name,
                    'residue': res_name,
                    'x': x,  # 单位：pm (PDB坐标是埃，乘以100)
                    'y': y,
                    'z': z,
                    'is_surface': False  # 简化：标记所有为非表面
                })
            except (ValueError, IndexError):
                continue
        
        if not pocket_atoms:
            return jsonify({'success': False, 'error': '未解析到有效原子'}), 400
        
        # 计算中心
        cx = sum(a['x'] for a in pocket_atoms) / len(pocket_atoms)
        cy = sum(a['y'] for a in pocket_atoms) / len(pocket_atoms)
        cz = sum(a['z'] for a in pocket_atoms) / len(pocket_atoms)
        
        # 简单的表面检测：计算每个原子周围邻居数，少的为表面
        from collections import defaultdict
        neighbors = defaultdict(int)
        for i, a in enumerate(pocket_atoms):
            for j, b in enumerate(pocket_atoms):
                if i != j:
                    d = math.sqrt((a['x']-b['x'])**2 + (a['y']-b['y'])**2 + (a['z']-b['z'])**2)
                    if d < 500:  # 5埃以内
                        neighbors[i] += 1
        
        # 邻居少于8个的原子标记为表面
        for i, a in enumerate(pocket_atoms):
            a['is_surface'] = neighbors[i] < 8
        
        return jsonify({
            'success': True,
            'atoms': pocket_atoms,
            'center': {'x': round(cx, 2), 'y': round(cy, 2), 'z': round(cz, 2)},
            'num_atoms': len(pocket_atoms),
            'num_surface': sum(1 for a in pocket_atoms if a['is_surface'])
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
