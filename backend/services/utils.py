"""RDKit工具函数 - 分子操作、验证、可视化"""
import base64
import os
from io import BytesIO
from typing import List, Optional, Dict
from rdkit import Chem

# ---------- 懒加载RDKit子模块（处理版本兼容性问题） ----------

_allchem_available = None

def _load_allchem():
    """尝试加载AllChem，返回是否可用"""
    global _allchem_available
    if _allchem_available is not None:
        return _allchem_available
    try:
        from rdkit.Chem import AllChem
        _allchem_available = True
        return True
    except Exception:
        try:
            import rdkit.Chem.AllChem
            _allchem_available = True
            return True
        except Exception:
            _allchem_available = False
            return False

def _get_allchem():
    """获取AllChem模块，不可用则返回None"""
    if _load_allchem():
        try:
            from rdkit.Chem import AllChem
            return AllChem
        except Exception:
            import rdkit.Chem.AllChem
            return rdkit.Chem.AllChem
    return None

def _load_descriptors():
    """尝试加载Descriptors"""
    try:
        from rdkit.Chem import Descriptors
        return Descriptors
    except Exception:
        try:
            import rdkit.Chem.Descriptors
            return rdkit.Chem.Descriptors
        except Exception:
            return None

def _load_rdmol_descriptors():
    """尝试加载rdMolDescriptors"""
    try:
        from rdkit.Chem import rdMolDescriptors
        return rdMolDescriptors
    except Exception:
        try:
            import rdkit.Chem.rdMolDescriptors
            return rdkit.Chem.rdMolDescriptors
        except Exception:
            return None

def _load_draw():
    """尝试加载Draw"""
    try:
        from rdkit.Chem import Draw
        return Draw
    except Exception:
        try:
            import rdkit.Chem.Draw
            return rdkit.Chem.Draw
        except Exception:
            return None

def _load_filter_catalog():
    """尝试加载FilterCatalog"""
    try:
        from rdkit.Chem import FilterCatalog
        return FilterCatalog
    except Exception:
        try:
            import rdkit.Chem.FilterCatalog
            return rdkit.Chem.FilterCatalog
        except Exception:
            return None

def _load_fp_generator():
    """尝试加载rdFingerprintGenerator"""
    try:
        from rdkit.Chem import rdFingerprintGenerator
        return rdFingerprintGenerator
    except Exception:
        try:
            import rdkit.Chem.rdFingerprintGenerator
            return rdkit.Chem.rdFingerprintGenerator
        except Exception:
            return None

def _load_murcko():
    """尝试加载MurckoScaffold"""
    try:
        from rdkit.Chem.Scaffolds import MurckoScaffold
        return MurckoScaffold
    except Exception:
        try:
            import rdkit.Chem.Scaffolds.MurckoScaffold
            return rdkit.Chem.Scaffolds.MurckoScaffold
        except Exception:
            return None


def validate_smiles(smiles: str) -> Optional[Chem.Mol]:
    """验证并返回RDKit Mol对象"""
    if not smiles or not isinstance(smiles, str):
        return None
    mol = Chem.MolFromSmiles(smiles.strip())
    return mol


def canonicalize_smiles(smiles: str) -> Optional[str]:
    """将SMILES转换为canonical形式"""
    mol = validate_smiles(smiles)
    if mol is None:
        return None
    return Chem.MolToSmiles(mol, canonical=True)


def inchi_from_smiles(smiles: str) -> Optional[str]:
    """从SMILES计算InChI"""
    mol = validate_smiles(smiles)
    if mol is None:
        return None
    try:
        return Chem.MolToInchi(mol)
    except Exception:
        return None


def smiles_to_svg(smiles: str, size: int = 300) -> str:
    """将SMILES转换为SVG图片（手动绘制，不依赖rdMolDraw2D）"""
    mol = validate_smiles(smiles)
    if mol is None:
        return ""
    
    # 尝试计算2D坐标，如果失败则尝试替代方案
    try:
        Chem.Compute2DCoords(mol)
    except Exception:
        pass
    
    # 如果仍然没有构象，尝试 rdDepictor
    if mol.GetNumConformers() == 0:
        try:
            from rdkit.Chem import rdDepictor
            rdDepictor.Compute2DCoords(mol)
        except Exception:
            pass
    
    # 最终检查：是否有可用构象
    if mol.GetNumConformers() == 0:
        return ""
    
    # 提取原子坐标和类型
    atoms = []
    for atom in mol.GetAtoms():
        idx = atom.GetIdx()
        pos = mol.GetConformer().GetAtomPosition(idx)
        symbol = atom.GetSymbol()
        
        # 颜色映射
        color_map = {
            'C': '#1e293b', 'H': '#94a3b8', 'O': '#ef4444',
            'N': '#3b82f6', 'S': '#eab308', 'Cl': '#22c55e',
            'F': '#f97316', 'Br': '#a16207', 'I': '#6366f1',
            'P': '#ec4899',
        }
        atoms.append({
            'idx': idx,
            'x': pos.x,
            'y': pos.y,
            'symbol': symbol,
            'color': color_map.get(symbol, '#1e293b'),
            'is_aromatic': atom.GetIsAromatic(),
        })
    
    # 提取键
    bonds = []
    for b in mol.GetBonds():
        i = b.GetBeginAtomIdx()
        j = b.GetEndAtomIdx()
        bt = str(b.GetBondType())
        bonds.append({'i': i, 'j': j, 'type': bt})
    
    # 计算边界框
    xs = [a['x'] for a in atoms]
    ys = [a['y'] for a in atoms]
    if not xs or not ys:
        return ""
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    
    padding = 28
    mol_w = max_x - min_x if max_x != min_x else 1
    mol_h = max_y - min_y if max_y != min_y else 1
    
    scale_x = (size - 2 * padding) / mol_w if mol_w > 0 else 1
    scale_y = (size - 2 * padding) / mol_h if mol_h > 0 else 1
    scale = min(scale_x, scale_y) * 0.82
    
    cx = (min_x + max_x) / 2
    cy = (min_y + max_y) / 2
    offset_x = size / 2 - cx * scale
    offset_y = size / 2 - cy * scale
    
    def tx(x): return x * scale + offset_x
    def ty(y): return y * scale + offset_y
    
    # 检测芳香环
    aromatic_rings = []
    try:
        ssr = Chem.GetSymmSSSR(mol)
        for ring in ssr:
            if len(ring) == 6:
                all_aromatic = all(mol.GetAtomWithIdx(idx).GetIsAromatic() for idx in ring)
                if all_aromatic:
                    ring_atoms = [atoms[idx] for idx in ring]
                    aromatic_rings.append(ring_atoms)
    except Exception:
        pass
    
    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="100%" viewBox="0 0 {size} {size}" style="display:block;">')
    lines.append(f'<rect width="100%" height="100%" fill="#ffffff" rx="6"/>')
    
    # 小分子特殊处理
    num_atoms = len(atoms)
    if num_atoms <= 3:
        if num_atoms == 1:
            x, y = size/2, size/2
            symbol = atoms[0]['symbol']
            color = atoms[0]['color']
            lines.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="40" fill="none" stroke="{color}" stroke-width="2.5"/>')
            lines.append(f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="middle" dominant-baseline="central" fill="{color}" font-size="32" font-weight="bold" font-family="ui-sans-serif,system-ui,sans-serif">{symbol}</text>')
            lines.append('</svg>')
            return ''.join(lines)
    
    # 绘制芳香环内圈
    for ring in aromatic_rings:
        pts = [(tx(a['x']), ty(a['y'])) for a in ring]
        if len(pts) == 6:
            cx_ring = sum(p[0] for p in pts) / 6
            cy_ring = sum(p[1] for p in pts) / 6
            r_sum = sum(((p[0]-cx_ring)**2 + (p[1]-cy_ring)**2)**0.5 for p in pts)
            avg_r = r_sum / 6 * 0.35
            lines.append(f'<circle cx="{cx_ring:.1f}" cy="{cy_ring:.1f}" r="{avg_r:.1f}" fill="none" stroke="#1e293b" stroke-width="1.5"/>')
    
    # 绘制键
    for b in bonds:
        a1 = atoms[b['i']]
        a2 = atoms[b['j']]
        x1, y1 = tx(a1['x']), ty(a1['y'])
        x2, y2 = tx(a2['x']), ty(a2['y'])
        bond_type = b['type']
        
        if bond_type == 'DOUBLE':
            dx, dy = x2 - x1, y2 - y1
            length = (dx**2 + dy**2)**0.5
            if length > 0:
                perp_x = -dy / length * 3.0
                perp_y = dx / length * 3.0
                lines.append(f'<line x1="{x1+perp_x:.1f}" y1="{y1+perp_y:.1f}" x2="{x2+perp_x:.1f}" y2="{y2+perp_y:.1f}" stroke="#1e293b" stroke-width="2"/>')
                lines.append(f'<line x1="{x1-perp_x:.1f}" y1="{y1-perp_y:.1f}" x2="{x2-perp_x:.1f}" y2="{y2-perp_y:.1f}" stroke="#1e293b" stroke-width="2"/>')
        elif bond_type == 'TRIPLE':
            lines.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#1e293b" stroke-width="2.5"/>')
        elif bond_type == 'AROMATIC':
            lines.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#1e293b" stroke-width="2.5"/>')
        else:
            lines.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#1e293b" stroke-width="2.5"/>')
    
    # 绘制原子
    for a in atoms:
        x, y = tx(a['x']), ty(a['y'])
        symbol = a['symbol']
        color = a['color']
        
        if symbol == 'C':
            # 碳原子：不画圆，只画标签（如果连接氢或没有显式氢）
            continue
        
        # 非碳原子：画白色圆背景 + 标签
        r = 10 if symbol in ('N', 'O', 'S') else 8
        lines.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="white"/>')
        lines.append(f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="middle" dominant-baseline="central" fill="{color}" font-size="13" font-weight="bold" font-family="ui-sans-serif,system-ui,sans-serif">{symbol}</text>')
    
    lines.append('</svg>')
    return ''.join(lines)


def save_molecule_svg(smiles: str, filepath: str, size: int = 300) -> bool:
    """保存分子SVG到文件"""
    svg = smiles_to_svg(smiles, size)
    if not svg:
        return False
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(svg)
    return True


def compute_descriptors(mol: Chem.Mol) -> Dict:
    """计算分子描述符"""
    if mol is None:
        return {}
    
    Descriptors = _load_descriptors()
    rdMolDescriptors = _load_rdmol_descriptors()
    
    if Descriptors is None or rdMolDescriptors is None:
        return {}
    
    try:
        return {
            'mw': Descriptors.MolWt(mol),
            'clogp': Descriptors.MolLogP(mol),
            'tpsa': Descriptors.TPSA(mol),
            'hbd': rdMolDescriptors.CalcNumHBD(mol),
            'hba': rdMolDescriptors.CalcNumHBA(mol),
            'rotb': rdMolDescriptors.CalcNumRotatableBonds(mol),
            'qed': Descriptors.qed(mol),
            'num_rings': rdMolDescriptors.CalcNumRings(mol),
            'num_aromatic_rings': rdMolDescriptors.CalcNumAromaticRings(mol),
        }
    except Exception:
        return {}


def compute_sa_score(mol: Chem.Mol) -> float:
    """计算合成可及性评分 (SA Score) - 简化版"""
    if mol is None:
        return 10.0
    
    rdMolDescriptors = _load_rdmol_descriptors()
    
    num_atoms = mol.GetNumAtoms()
    num_rings = rdMolDescriptors.CalcNumRings(mol) if rdMolDescriptors else 0
    num_rotatable = rdMolDescriptors.CalcNumRotatableBonds(mol) if rdMolDescriptors else 0
    num_stereo = len(Chem.FindMolChiralCenters(mol, includeUnassigned=True))
    
    sa_score = 1.0 + (
        num_rings * 0.5 + 
        num_rotatable * 0.2 + 
        num_stereo * 0.3 + 
        max(0, num_atoms - 30) * 0.05
    )
    return min(sa_score, 10.0)


def check_pains(mol: Chem.Mol) -> bool:
    """检查是否通过PAINS过滤（无PAINS子结构）"""
    if mol is None:
        return False
    
    FilterCatalog = _load_filter_catalog()
    if FilterCatalog is None:
        # 如果FilterCatalog不可用，默认通过
        return True
    
    try:
        params = FilterCatalog.FilterCatalogParams()
        params.AddCatalog(FilterCatalog.FilterCatalogParams.FilterCatalogs.PAINS)
        catalog = FilterCatalog.FilterCatalog(params)
        return not catalog.HasMatch(mol)
    except Exception:
        return True


def check_brenk(mol: Chem.Mol) -> bool:
    """检查Brenk过滤规则"""
    if mol is None:
        return False
    toxic_patterns = [
        'C(=O)N=[N+]=[N-]',
        'N#C',
        'S(=O)(=O)Cl',
    ]
    for pattern in toxic_patterns:
        try:
            patt = Chem.MolFromSmarts(pattern)
            if patt and mol.HasSubstructMatch(patt):
                return False
        except Exception:
            continue
    return True


def compute_morgan_similarity(mol1: Chem.Mol, mol2: Chem.Mol, radius: int = 2) -> float:
    """计算Morgan指纹Tanimoto相似性"""
    if mol1 is None or mol2 is None:
        return 0.0
    
    rdFingerprintGenerator = _load_fp_generator()
    if rdFingerprintGenerator is None:
        return 0.0
    
    try:
        fp_gen = rdFingerprintGenerator.GetMorganGenerator(radius=radius, fpSize=2048)
        fp1 = fp_gen.GetFingerprint(mol1)
        fp2 = fp_gen.GetFingerprint(mol2)
        from rdkit import DataStructs
        return DataStructs.TanimotoSimilarity(fp1, fp2)
    except Exception:
        return 0.0


def generate_3d_conformer(mol: Chem.Mol, num_confs: int = 1) -> Optional[Chem.Mol]:
    """生成3D构象"""
    if mol is None:
        return None
    
    AllChem = _get_allchem()
    if AllChem is None:
        return None
    
    try:
        mol = Chem.AddHs(mol)
        AllChem.EmbedMolecule(mol, randomSeed=42)
        AllChem.MMFFOptimizeMolecule(mol)
        return mol
    except Exception:
        return None


def get_scaffold(mol: Chem.Mol) -> Optional[str]:
    """获取Murcko骨架SMILES"""
    if mol is None:
        return None
    
    MurckoScaffold = _load_murcko()
    if MurckoScaffold is None:
        return None
    
    try:
        scaffold = MurckoScaffold.GetScaffoldForMol(mol)
        if scaffold.GetNumAtoms() == 0:
            return None
        return Chem.MolToSmiles(scaffold)
    except Exception:
        return None


def check_lipinski(mol: Chem.Mol) -> Dict:
    """检查Lipinski五规则"""
    if mol is None:
        return {'pass': False, 'violations': 5}
    
    Descriptors = _load_descriptors()
    rdMolDescriptors = _load_rdmol_descriptors()
    
    if Descriptors is None or rdMolDescriptors is None:
        return {'pass': False, 'violations': 5}
    
    try:
        mw = Descriptors.MolWt(mol)
        logp = Descriptors.MolLogP(mol)
        hbd = rdMolDescriptors.CalcNumHBD(mol)
        hba = rdMolDescriptors.CalcNumHBA(mol)
        
        violations = 0
        if mw > 500: violations += 1
        if logp > 5: violations += 1
        if hbd > 5: violations += 1
        if hba > 10: violations += 1
        
        return {
            'pass': violations <= 1,
            'violations': violations,
            'mw': mw, 'logp': logp, 'hbd': hbd, 'hba': hba
        }
    except Exception:
        return {'pass': False, 'violations': 5}
