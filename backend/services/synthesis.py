"""逆合成分析服务 - 专业级逆合成路线模拟"""
import json
import os
from typing import Dict, List, Optional
from .utils import validate_smiles


# ---------- 专业合成反应数据库 ----------

REACTION_TEMPLATES = {
    'amide_formation': {
        'name': '酰胺缩合',
        'type': '偶联反应',
        'reagents': ['HATU', 'DIPEA', 'DMF'],
        'solvent': 'DMF',
        'temperature': '0 °C → 室温',
        'time': '2–4 h',
        'yield_range': (0.70, 0.90),
        'description': '羧酸与胺在HATU/DIPEA作用下缩合生成酰胺',
    },
    'buchwald_hartwig': {
        'name': 'Buchwald–Hartwig 偶联',
        'type': 'C–N 偶联',
        'reagents': ['Pd₂(dba)₃', 'Xantphos', 'Cs₂CO₃', '二氧六环'],
        'solvent': '1,4-二氧六环',
        'temperature': '100 °C',
        'time': '12–18 h',
        'yield_range': (0.60, 0.85),
        'description': '芳基卤与胺/酰胺在钯催化下发生 C–N 偶联',
    },
    'suzuki_coupling': {
        'name': 'Suzuki–Miyaura 偶联',
        'type': 'C–C 偶联',
        'reagents': ['Pd(PPh₃)₄', 'K₂CO₃', '甲苯/水'],
        'solvent': '甲苯/水 (4:1)',
        'temperature': '90 °C',
        'time': '8–16 h',
        'yield_range': (0.65, 0.88),
        'description': '芳基硼酸与芳基卤在钯催化下发生交叉偶联',
    },
    'reductive_amination': {
        'name': '还原胺化',
        'type': '还原反应',
        'reagents': ['NaBH(OAc)₃', 'AcOH', 'DCE'],
        'solvent': '1,2-二氯乙烷 (DCE)',
        'temperature': '室温',
        'time': '4–8 h',
        'yield_range': (0.60, 0.80),
        'description': '醛/酮与胺在还原剂作用下生成仲胺/叔胺',
    },
    'nitration': {
        'name': '硝化反应',
        'type': '亲电取代',
        'reagents': ['浓 HNO₃', '浓 H₂SO₄'],
        'solvent': 'H₂SO₄ (混酸)',
        'temperature': '0–10 °C',
        'time': '1–2 h',
        'yield_range': (0.70, 0.90),
        'description': '芳香环在混酸作用下引入硝基',
    },
    'nitro_reduction': {
        'name': '硝基还原',
        'type': '还原反应',
        'reagents': ['H₂', 'Pd/C', 'EtOAc'],
        'solvent': 'EtOAc',
        'temperature': '室温',
        'time': '2–6 h',
        'yield_range': (0.85, 0.98),
        'description': '硝基在氢气/钯碳催化下还原为氨基',
    },
    'halogenation': {
        'name': '芳基卤化',
        'type': '亲电取代',
        'reagents': ['NBS', 'DMF'],
        'solvent': 'DMF',
        'temperature': '室温',
        'time': '2–4 h',
        'yield_range': (0.65, 0.85),
        'description': '芳香环在NBS作用下发生溴化',
    },
    'esterification': {
        'name': '酯化反应',
        'type': '缩合反应',
        'reagents': ['EDCI', 'DMAP', 'DCM'],
        'solvent': 'DCM',
        'temperature': '0 °C → 室温',
        'time': '4–8 h',
        'yield_range': (0.75, 0.92),
        'description': '羧酸与醇在EDCI/DMAP作用下酯化',
    },
    'williamson_ether': {
        'name': 'Williamson 醚合成',
        'type': 'SN2 取代',
        'reagents': ['NaH', 'THF'],
        'solvent': 'THF',
        'temperature': '0 °C → 室温',
        'time': '2–6 h',
        'yield_range': (0.60, 0.85),
        'description': '酚/醇钠盐与卤代烃发生 SN2 反应生成醚',
    },
    'boc_protection': {
        'name': 'Boc 保护',
        'type': '保护基策略',
        'reagents': ['(Boc)₂O', 'TEA', 'DCM'],
        'solvent': 'DCM',
        'temperature': '0 °C',
        'time': '1–2 h',
        'yield_range': (0.85, 0.98),
        'description': '胺与二碳酸二叔丁酯反应生成 Boc-胺',
    },
    'boc_deprotection': {
        'name': 'Boc 脱保护',
        'type': '脱保护',
        'reagents': ['TFA', 'DCM'],
        'solvent': 'DCM',
        'temperature': '0 °C → 室温',
        'time': '1–3 h',
        'yield_range': (0.85, 0.98),
        'description': 'Boc保护基在TFA酸性条件下脱除',
    },
    'fischer_indole': {
        'name': 'Fischer 吲哚合成',
        'type': '环化反应',
        'reagents': ['PPA', 'EtOH'],
        'solvent': 'EtOH',
        'temperature': '回流',
        'time': '4–8 h',
        'yield_range': (0.50, 0.75),
        'description': '苯肼与酮在酸性条件下缩合生成吲哚环',
    },
    'claisen_condensation': {
        'name': 'Claisen 缩合',
        'type': '缩合反应',
        'reagents': ['NaOEt', 'EtOH'],
        'solvent': 'EtOH',
        'temperature': '回流',
        'time': '2–6 h',
        'yield_range': (0.60, 0.80),
        'description': '酯在碱性条件下发生自身缩合生成 β-酮酯',
    },
    'hydrolysis': {
        'name': '酯水解',
        'type': '水解反应',
        'reagents': ['NaOH', 'H₂O', 'THF'],
        'solvent': 'THF/H₂O',
        'temperature': '50 °C',
        'time': '2–4 h',
        'yield_range': (0.85, 0.98),
        'description': '酯在碱性条件下水解为羧酸盐，再酸化得羧酸',
    },
    'sulfonamide_formation': {
        'name': '磺酰胺形成',
        'type': '缩合反应',
        'reagents': ['磺酰氯', 'TEA', 'DCM'],
        'solvent': 'DCM',
        'temperature': '0 °C → 室温',
        'time': '2–4 h',
        'yield_range': (0.70, 0.90),
        'description': '磺酰氯与胺在碱作用下缩合生成磺酰胺',
    },
    'snAr': {
        'name': '芳香亲核取代 (SNAr)',
        'type': '亲核取代',
        'reagents': ['NaH', 'DMF'],
        'solvent': 'DMF',
        'temperature': '80–100 °C',
        'time': '4–12 h',
        'yield_range': (0.60, 0.85),
        'description': '吸电子基取代芳环上的离去基团与亲核试剂反应',
    },
    'cyclization': {
        'name': '分子内环化',
        'type': '环化反应',
        'reagents': ['CDI', 'DBU', 'THF'],
        'solvent': 'THF',
        'temperature': '回流',
        'time': '6–12 h',
        'yield_range': (0.50, 0.75),
        'description': '线性前体在缩合剂作用下发生分子内环化',
    },
    'grignard': {
        'name': 'Grignard 加成',
        'type': '亲核加成',
        'reagents': ['Mg', 'Et₂O', 'THF'],
        'solvent': 'THF',
        'temperature': '回流',
        'time': '2–4 h',
        'yield_range': (0.60, 0.85),
        'description': '卤代烃与镁生成格氏试剂，再与羰基化合物加成',
    },
    'michael_addition': {
        'name': 'Michael 加成',
        'type': '共轭加成',
        'reagents': ['NaOEt', 'EtOH'],
        'solvent': 'EtOH',
        'temperature': '室温',
        'time': '2–6 h',
        'yield_range': (0.65, 0.85),
        'description': '亲核试剂对α,β-不饱和羰基化合物进行1,4-共轭加成',
    },
    'cycloaddition': {
        'name': 'Diels–Alder 环加成',
        'type': '[4+2] 环加成',
        'reagents': ['甲苯'],
        'solvent': '甲苯',
        'temperature': '回流',
        'time': '4–12 h',
        'yield_range': (0.60, 0.85),
        'description': '共轭二烯与亲双烯体发生 [4+2] 环加成反应',
    },
}


SUBSTRUCTURE_PATTERNS = [
    ('amide_formation', '[C](=O)[N;!$(N-C=O)]'),  # 酰胺键 (C=O)N，且N不连另一个C=O
    ('buchwald_hartwig', '[c][Br,I,Cl]'),  # 芳基卤
    ('suzuki_coupling', '[c][Br,I,Cl]'),  # 芳基卤 (优先级低于Buchwald)
    ('reductive_amination', '[C;H1,H2](=[O])'),  # 醛
    ('nitration', '[a]'),  # 芳环（硝化在芳环上）
    ('nitro_reduction', '[N+](=O)[O-]'),  # 硝基
    ('halogenation', '[a]'),  # 芳环
    ('esterification', '[C](=O)[O;H0]'),  # 酯：羰基碳连无H氧
    ('williamson_ether', '[#6][O;H1]'),  # 酚/醇羟基（用[#6]不限定芳碳）
    ('boc_protection', '[N;H2,H1]'),  # 伯胺/仲胺
    ('sulfonamide_formation', '[S](=O)(=O)[Cl]'),  # 磺酰氯
    ('snAr', '[c][F,Cl,Br,I]'),  # 芳基卤（SNAr需要吸电子基，简化匹配）
    ('cyclization', '[r]'),  # 环状结构（通用环化）
    ('grignard', '[C][Br,I,Cl]'),  # 卤代烃
    ('michael_addition', '[C]=[C]-[C]=[O]'),  # α,β-不饱和羰基
    ('cycloaddition', '[C]=[C]-[C]=[C]'),  # 共轭二烯
    ('fischer_indole', '[c]1[nH][n]cc1'),  # 吲哚相关
    ('claisen_condensation', '[C](=O)[O;H0]'),  # 酯
    ('hydrolysis', '[C](=O)[O;H0]'),  # 酯
]


def _detect_functional_groups(mol) -> List[str]:
    """检测分子中的官能团，返回反应类型列表"""
    from rdkit import Chem
    groups = []
    seen = set()
    
    for reaction_key, smarts in SUBSTRUCTURE_PATTERNS:
        if reaction_key in seen:
            continue
        try:
            patt = Chem.MolFromSmarts(smarts)
            if patt and mol.HasSubstructMatch(patt):
                groups.append(reaction_key)
                seen.add(reaction_key)
        except Exception:
            continue
    
    # 去重并限制数量
    return groups[:6]


def _build_route(mol, groups: List[str]) -> List[Dict]:
    """基于官能团构建专业合成路线"""
    import random
    from rdkit import Chem
    
    route_steps = []
    used_reactions = set()
    
    # 随机种子基于分子结构使结果可重复
    seed = mol.GetNumAtoms() + mol.GetNumBonds()
    rng = random.Random(seed)
    
    for reaction_key in groups:
        if reaction_key in used_reactions:
            continue
        
        template = REACTION_TEMPLATES.get(reaction_key)
        if not template:
            continue
        
        used_reactions.add(reaction_key)
        
        # 生成该步的收率
        y_min, y_max = template['yield_range']
        step_yield = round(rng.uniform(y_min, y_max), 2)
        
        route_steps.append({
            'step': len(route_steps) + 1,
            'reaction_name': template['name'],
            'reaction_type': template['type'],
            'reagents': template['reagents'],
            'solvent': template['solvent'],
            'temperature': template['temperature'],
            'time': template['time'],
            'yield': step_yield,
            'description': template['description'],
        })
    
    # 如果没有检测到任何官能团，生成一个通用路线
    if not route_steps:
        route_steps = _generic_route(rng)
    
    return route_steps


def _generic_route(rng) -> List[Dict]:
    """通用合成路线（当无法识别具体官能团时）"""
    generic = [
        REACTION_TEMPLATES['amide_formation'],
        REACTION_TEMPLATES['buchwald_hartwig'],
        REACTION_TEMPLATES['nitration'],
    ]
    
    steps = []
    for i, template in enumerate(generic[:2 + rng.randint(0, 1)]):
        y_min, y_max = template['yield_range']
        steps.append({
            'step': i + 1,
            'reaction_name': template['name'],
            'reaction_type': template['type'],
            'reagents': template['reagents'],
            'solvent': template['solvent'],
            'temperature': template['temperature'],
            'time': template['time'],
            'yield': round(rng.uniform(y_min, y_max), 2),
            'description': template['description'],
        })
    return steps


class SynthesisAnalyzer:
    """逆合成分析器 - 专业级"""

    def __init__(self):
        self.aizynth_available = False
        try:
            from aizynthfinder.aizynthfinder import AiZynthFinder
            self.aizynth_available = True
        except ImportError:
            pass

    def analyze(self, smiles: str) -> Dict:
        """分析单个分子的合成路线"""
        mol = validate_smiles(smiles)
        if mol is None:
            return {'error': 'SMILES解析失败'}

        if self.aizynth_available:
            try:
                return self._analyze_with_aizynth(smiles)
            except Exception:
                return self._mock_analyze(smiles, mol)
        else:
            return self._mock_analyze(smiles, mol)

    def _analyze_with_aizynth(self, smiles: str) -> Dict:
        """使用AiZynthFinder进行逆合成分析"""
        try:
            from aizynthfinder.aizynthfinder import AiZynthFinder
            finder = AiZynthFinder()
            finder.target_smiles = smiles
            finder.tree_search()

            routes = finder.routes
            if routes:
                best_route = routes[0]
                return {
                    'smiles': smiles,
                    'num_steps': len(best_route.reactions),
                    'route': best_route.to_dict(),
                    'status': 'completed',
                    'availability_score': 0.8,
                    'estimated_cost': 1000.0,
                }
        except Exception:
            pass

        return self._mock_analyze(smiles, validate_smiles(smiles))

    def _mock_analyze(self, smiles: str, mol) -> Dict:
        """基于分子结构生成专业合成路线 - 真实合成难度评估"""
        if mol is None:
            return {
                'smiles': smiles,
                'num_steps': 5,
                'estimated_cost': 500.0,
                'availability_score': 0.0,
                'status': 'simulated',
                'route': {'nodes': [], 'total_yield': 0.0}
            }

        from .utils import _load_descriptors, _load_rdmol_descriptors

        Descriptors = _load_descriptors()
        rdMolDescriptors = _load_rdmol_descriptors()

        try:
            num_atoms = mol.GetNumAtoms()
            if rdMolDescriptors:
                num_rings = rdMolDescriptors.CalcNumRings(mol)
                num_rotatable = rdMolDescriptors.CalcNumRotatableBonds(mol)
                num_stereocenters = rdMolDescriptors.CalcNumAtomStereoCenters(mol)
            else:
                num_rings = 2
                num_rotatable = 3
                num_stereocenters = 0
            if Descriptors:
                mw = Descriptors.MolWt(mol)
                num_heteroatoms = Descriptors.NumHeteroatoms(mol)
                logp = Descriptors.MolLogP(mol)
            else:
                mw = num_atoms * 15.0
                num_heteroatoms = 2
                logp = 2.0
        except Exception:
            num_atoms = 20
            num_rings = 2
            num_rotatable = 3
            num_stereocenters = 0
            mw = 300.0
            num_heteroatoms = 2
            logp = 2.0

        groups = _detect_functional_groups(mol)
        route_nodes = _build_route(mol, groups)

        estimated_steps = len(route_nodes)

        if route_nodes:
            total_yield = 1.0
            for node in route_nodes:
                total_yield *= node['yield']
            total_yield = round(total_yield, 3)
        else:
            total_yield = 0.0

        availability = 0.75
        step_penalty = min(0.25, estimated_steps * 0.05)
        availability -= step_penalty

        complexity_penalty = 0.0
        if num_rings > 4:
            complexity_penalty += (num_rings - 4) * 0.04
        if num_rotatable > 8:
            complexity_penalty += (num_rotatable - 8) * 0.015
        if num_rotatable > 12:
            complexity_penalty += (num_rotatable - 12) * 0.02
        if mw > 500:
            complexity_penalty += (mw - 500) / 3000
        if num_stereocenters > 2:
            complexity_penalty += (num_stereocenters - 2) * 0.03
        complexity_penalty = min(0.25, complexity_penalty)
        availability -= complexity_penalty

        yield_penalty = 0.0
        if total_yield < 0.20:
            yield_penalty = 0.15
        elif total_yield < 0.30:
            yield_penalty = 0.08
        elif total_yield < 0.40:
            yield_penalty = 0.03
        availability -= yield_penalty

        if len(groups) == 0:
            availability -= 0.10

        availability = round(max(0.0, min(1.0, availability)), 2)

        estimated_cost = max(100, mw * 2 + num_atoms * 10 + estimated_steps * 50)

        return {
            'smiles': smiles,
            'num_steps': estimated_steps,
            'estimated_cost': round(estimated_cost, 2),
            'availability_score': availability,
            'status': 'simulated',
            'route': {
                'nodes': route_nodes,
                'total_yield': total_yield,
            },
            'analysis': {
                'step_penalty': round(step_penalty, 2),
                'complexity_penalty': round(complexity_penalty, 2),
                'yield_penalty': yield_penalty,
                'num_groups': len(groups),
                'num_rings': num_rings,
                'num_rotatable': num_rotatable,
                'num_stereocenters': num_stereocenters,
                'mw': round(mw, 1),
            }
        }


def generate_2d_svg(smiles: str, width: int = 320, height: int = 240) -> str:
    """生成分子2D结构图，RDKit rdMolDraw2D不可用时使用手动SVG绘制

    使用RDKit的2D坐标计算，然后手动用SVG绘制原子和键。
    不依赖任何外部DLL，纯Python计算 + SVG字符串。
    """
    try:
        from rdkit import Chem
        from rdkit.Chem import AllChem

        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return _fallback_svg(width, height)

        AllChem.Compute2DCoords(mol)
        conf = mol.GetConformer()

        atoms = []
        for i in range(mol.GetNumAtoms()):
            pos = conf.GetAtomPosition(i)
            atom = mol.GetAtomWithIdx(i)
            symbol = atom.GetSymbol()
            color = _atom_color(symbol)
            atoms.append({
                'x': pos.x,
                'y': pos.y,
                'symbol': symbol,
                'color': color,
                'idx': i,
            })

        bonds = []
        for b in mol.GetBonds():
            i = b.GetBeginAtomIdx()
            j = b.GetEndAtomIdx()
            bt = b.GetBondType()
            bonds.append({
                'i': i, 'j': j,
                'type': str(bt),  # SINGLE, DOUBLE, TRIPLE, AROMATIC
            })

        # 计算边界框，用于缩放和居中
        xs = [a['x'] for a in atoms]
        ys = [a['y'] for a in atoms]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

        padding = 28
        mol_w = max_x - min_x if max_x != min_x else 1
        mol_h = max_y - min_y if max_y != min_y else 1

        scale_x = (width - 2 * padding) / mol_w if mol_w > 0 else 1
        scale_y = (height - 2 * padding) / mol_h if mol_h > 0 else 1
        scale = min(scale_x, scale_y) * 0.82

        cx = (min_x + max_x) / 2
        cy = (min_y + max_y) / 2
        offset_x = width / 2 - cx * scale
        offset_y = height / 2 - cy * scale

        def tx(x): return x * scale + offset_x
        def ty(y): return y * scale + offset_y

        # 收集芳香键，用于后续画内圈
        aromatic_bonds = [b for b in bonds if b['type'] == 'AROMATIC']
        # 检测6元芳香环
        aromatic_rings = _find_aromatic_rings(mol, atoms)

        lines = []
        lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="100%" viewBox="0 0 {width} {height}" style="display:block;">')
        lines.append(f'<rect width="100%" height="100%" fill="#ffffff" rx="6"/>')

        # 小分子特殊处理（1-3个原子）：放大显示
        num_atoms = len(atoms)
        is_small_molecule = num_atoms <= 3

        if is_small_molecule and num_atoms == 1:
            # 单原子：画一个大圆+符号
            x, y = width/2, height/2
            symbol = atoms[0]['symbol']
            color = atoms[0]['color']
            lines.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="40" fill="none" stroke="{color}" stroke-width="2.5"/>')
            lines.append(f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="middle" dominant-baseline="central" fill="{color}" font-size="32" font-weight="bold" font-family="ui-sans-serif,system-ui,sans-serif">{symbol}</text>')
            lines.append('</svg>')
            return ''.join(lines)

        # 绘制芳香环内圈（先画，被键线覆盖）
        for ring in aromatic_rings:
            pts = [(tx(a['x']), ty(a['y'])) for a in ring]
            if len(pts) == 6:
                # 六边形中心
                cx_ring = sum(p[0] for p in pts) / 6
                cy_ring = sum(p[1] for p in pts) / 6
                # 计算平均半径（中心到各点的距离）
                r_sum = sum(((p[0]-cx_ring)**2 + (p[1]-cy_ring)**2)**0.5 for p in pts)
                avg_r = r_sum / 6 * 0.35  # 内圈半径约0.35倍平均半径（更小）
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
                # 芳香键：先画一条较粗的灰线作为背景，再画黑线
                lines.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#1e293b" stroke-width="2.5"/>')
            else:
                lines.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#1e293b" stroke-width="2.5"/>')

        # 绘制原子（不画碳原子的白色圆，避免覆盖键线端点）
        for a in atoms:
            x, y = tx(a['x']), ty(a['y'])
            symbol = a['symbol']
            color = a['color']

            if symbol == 'C':
                # 碳原子不显示标签，也不画圆覆盖（避免截断键线）
                continue

            lines.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="11" fill="white"/>')
            lines.append(f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="middle" dominant-baseline="central" fill="{color}" font-size="14" font-weight="bold" font-family="ui-sans-serif,system-ui,sans-serif">{symbol}</text>')

        lines.append('</svg>')
        return ''.join(lines)

    except Exception:
        return _fallback_svg(width, height)


def _atom_color(symbol: str) -> str:
    """原子颜色映射"""
    colors = {
        'H': '#94a3b8', 'C': '#1e293b', 'N': '#3b82f6', 'O': '#ef4444',
        'S': '#eab308', 'P': '#22c55e', 'F': '#a855f7', 'Cl': '#22c55e',
        'Br': '#a16207', 'I': '#dc2626', 'B': '#f97316', 'Si': '#06b6d4',
    }
    return colors.get(symbol, '#64748b')


def _find_aromatic_rings(mol, atoms) -> list:
    """检测分子中的芳香环（6元环），返回环中原子列表的列表"""
    from rdkit import Chem
    try:
        ssr = Chem.GetSymmSSSR(mol)
        rings = []
        for ring in ssr:
            if len(ring) == 6:
                # 检查是否所有原子都是芳香性的
                all_aromatic = all(mol.GetAtomWithIdx(idx).GetIsAromatic() for idx in ring)
                if all_aromatic:
                    ring_atoms = [atoms[idx] for idx in ring]
                    rings.append(ring_atoms)
        return rings
    except Exception:
        return []


def _fallback_svg(width: int = 320, height: int = 240) -> str:
    """当无法生成分子结构时返回占位SVG"""
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="100%" viewBox="0 0 {width} {height}" style="display:block;"><rect width="100%" height="100%" fill="#f8fafc" rx="8"/><text x="50%" y="40%" text-anchor="middle" dominant-baseline="central" fill="#94a3b8" font-size="11" font-family="ui-sans-serif,system-ui,sans-serif">分子结构生成失败</text><text x="50%" y="60%" text-anchor="middle" dominant-baseline="central" fill="#cbd5e1" font-size="10" font-family="ui-sans-serif,system-ui,sans-serif">请检查 RDKit 安装</text></svg>'


# 反应类型 -> 功能团SMARTS（用于在目标分子中定位可断键位置）
REACTION_REVERSE_PATTERNS = {
    'amide_formation': '[C](=O)[N;!$(N-C=O)]',
    'buchwald_hartwig': '[c][N;!$(N-C=O)]',
    'suzuki_coupling': '[c]-[c]1[c][c][c][c][c]1',
    'reductive_amination': '[C;H1,H2]-[N]',
    'nitration': '[c][N+](=O)[O-]',
    'nitro_reduction': '[c][N+](=O)[O-]',
    'halogenation': '[c][Br,I,Cl]',
    'esterification': '[C](=O)[O;H0]',
    'williamson_ether': '[#6]-[O]-[#6]',
    'boc_protection': '[N]C(=O)OC(C)(C)C',
    'boc_deprotection': '[N;H2,H1]',
    'hydrolysis': '[C](=O)[O;H0]',
    'sulfonamide_formation': '[S](=O)(=O)[N]',
    'snAr': '[c][F,Cl,Br,I]',
    'michael_addition': '[C]-[C]-[C](=O)',
    'grignard': '[C][OH]',
    'fischer_indole': '[c]1[nH][n]cc1',
    'claisen_condensation': '[C](=O)-[C](=O)',
    'cycloaddition': '[C]1[C][C][C][C][C]1',
    'cyclization': '[r]',
}


# 反应类型 -> 典型起始原料/中间体SMILES（作为fallback使用，保证是真实分子结构）
REACTION_TYPICAL_START_MATERIALS = {
    'amide_formation': [
        'c1ccccc1C(=O)O',   # 苯甲酸
        'Nc1ccccc1',         # 苯胺
        'CC(=O)O',           # 乙酸
    ],
    'buchwald_hartwig': [
        'Brc1ccccc1',        # 溴苯
        'Nc1ccccc1',         # 苯胺
        'C1CCNC1',           # 吡咯烷
    ],
    'suzuki_coupling': [
        'Brc1ccccc1',        # 溴苯
        'OB(O)c1ccccc1',     # 苯硼酸
        'Ic1ccccc1',         # 碘苯
    ],
    'reductive_amination': [
        'O=Cc1ccccc1',       # 苯甲醛
        'CN',                # 甲胺
        'CC=O',              # 乙醛
    ],
    'nitration': [
        'c1ccccc1',          # 苯
        'Cc1ccccc1',         # 甲苯
        'Oc1ccccc1',         # 苯酚
    ],
    'nitro_reduction': [
        'O=[N+]([O-])c1ccccc1',  # 硝基苯
        'O=[N+]([O-])c1ccc(C)cc1', # 对硝基甲苯
    ],
    'halogenation': [
        'c1ccccc1',          # 苯
        'Cc1ccccc1',         # 甲苯
    ],
    'esterification': [
        'c1ccccc1C(=O)O',    # 苯甲酸
        'CO',                # 甲醇
        'CCO',               # 乙醇
    ],
    'williamson_ether': [
        'Oc1ccccc1',         # 苯酚
        'CI',                # 碘甲烷
        'CBr',               # 溴甲烷
    ],
    'boc_protection': [
        'Nc1ccccc1',         # 苯胺
        'NCCc1ccccc1',       # 苯乙胺
    ],
    'boc_deprotection': [
        'CC(C)(C)OC(=O)Nc1ccccc1',  # Boc-苯胺
    ],
    'hydrolysis': [
        'COC(=O)c1ccccc1',   # 苯甲酸甲酯
        'CCOC(=O)c1ccccc1',  # 苯甲酸乙酯
    ],
    'sulfonamide_formation': [
        'O=S(=O)(Cl)c1ccccc1',   # 苯磺酰氯
        'Nc1ccccc1',             # 苯胺
    ],
    'snAr': [
        'Fc1ccccc1',         # 氟苯
        'Nc1ccccc1',         # 苯胺
        'Oc1ccccc1',         # 苯酚
    ],
    'michael_addition': [
        'C=CC(=O)c1ccccc1',  # 查尔酮
        'C=CC(=O)C',         # 甲基乙烯基酮
    ],
    'grignard': [
        'O=Cc1ccccc1',       # 苯甲醛
        'CC(C)=O',           # 丙酮
    ],
    'fischer_indole': [
        'NNc1ccccc1',        # 苯肼
        'CC(C)=O',           # 丙酮
    ],
    'claisen_condensation': [
        'CCOC(=O)C',         # 乙酸乙酯
        'CCOC(=O)CC',        # 丙酸乙酯
    ],
    'cycloaddition': [
        'C=CC=C',            # 1,3-丁二烯
        'C=CC=O',            # 丙烯醛
    ],
    'cyclization': [
        'CCCCCC',            # 己烷
        'CCCCC(=O)O',        # 己酸
    ],
}


def _generate_intermediate_smiles(mol, step_index, reaction_key=None):
    """使用RDKit SMARTS反向变换生成合理的中间体SMILES

    1. 首先尝试基于反应类型的SMARTS反向变换（移除功能团）
    2. 如果失败，使用典型中间体库（保证是真实分子结构）
    3. 如果仍失败，返回目标分子骨架
    """
    from rdkit import Chem
    from rdkit.Chem import AllChem

    # 策略1：基于反应类型的SMARTS反向变换
    if reaction_key and reaction_key in REACTION_REVERSE_PATTERNS:
        pattern_smarts = REACTION_REVERSE_PATTERNS[reaction_key]
        try:
            patt = Chem.MolFromSmarts(pattern_smarts)
            if patt and mol.HasSubstructMatch(patt):
                match = mol.GetSubstructMatch(patt)
                if match:
                    emol = Chem.EditableMol(mol)
                    # 按原子索引降序移除，避免索引错乱
                    atoms_to_remove = sorted(set(match), reverse=True)
                    for atom_idx in atoms_to_remove:
                        emol.RemoveAtom(atom_idx)
                    frag = emol.GetMol()
                    try:
                        frag = Chem.AddHs(frag)
                        frag = Chem.RemoveHs(frag)
                        frag_smiles = Chem.MolToSmiles(frag)
                        # 验证生成的SMILES是否有效且有意义
                        test_mol = Chem.MolFromSmiles(frag_smiles)
                        if test_mol and test_mol.GetNumAtoms() >= 3:
                            return frag_smiles
                    except Exception:
                        pass
        except Exception:
            pass

    # 策略2：通用简化——移除末端杂原子官能团
    try:
        emol = Chem.EditableMol(mol)
        atoms = list(range(mol.GetNumAtoms()))
        terminal_atoms = [i for i in atoms if mol.GetAtomWithIdx(i).GetDegree() == 1]
        if terminal_atoms:
            # 优先移除杂原子末端
            hetero_terminal = [i for i in terminal_atoms
                             if mol.GetAtomWithIdx(i).GetAtomicNum() not in [1, 6]]
            if hetero_terminal:
                emol.RemoveAtom(hetero_terminal[0])
            else:
                emol.RemoveAtom(terminal_atoms[0])
            frag = emol.GetMol()
            frag_smiles = Chem.MolToSmiles(frag)
            test_mol = Chem.MolFromSmiles(frag_smiles)
            if test_mol and test_mol.GetNumAtoms() >= 3:
                return frag_smiles
    except Exception:
        pass

    # 策略3：使用典型中间体库
    if reaction_key and reaction_key in REACTION_TYPICAL_START_MATERIALS:
        candidates = REACTION_TYPICAL_START_MATERIALS[reaction_key]
        if candidates:
            # 选择与目标分子最相似的（使用Morgan指纹Tanimoto相似度）
            try:
                target_fp = AllChem.GetMorganFingerprintAsBitVect(mol, 2, nBits=1024)
                best_similarity = 0
                best_smiles = candidates[0]
                for cand_smiles in candidates:
                    cand_mol = Chem.MolFromSmiles(cand_smiles)
                    if cand_mol:
                        cand_fp = AllChem.GetMorganFingerprintAsBitVect(cand_mol, 2, nBits=1024)
                        from rdkit import DataStructs
                        sim = DataStructs.TanimotoSimilarity(target_fp, cand_fp)
                        if sim > best_similarity:
                            best_similarity = sim
                            best_smiles = cand_smiles
                return best_smiles
            except Exception:
                return candidates[0]

    # 最终fallback：返回目标分子本身
    return Chem.MolToSmiles(mol)


def _generate_start_material_smiles(mol, reaction_key=None):
    """生成合理的起始原料SMILES

    1. 首先尝试基于反应类型的典型起始原料库
    2. 如果失败，使用Murcko骨架
    3. 最终fallback：苯环
    """
    from rdkit import Chem
    from rdkit.Chem import AllChem

    # 策略1：使用典型起始原料库
    if reaction_key and reaction_key in REACTION_TYPICAL_START_MATERIALS:
        candidates = REACTION_TYPICAL_START_MATERIALS[reaction_key]
        if candidates:
            try:
                target_fp = AllChem.GetMorganFingerprintAsBitVect(mol, 2, nBits=1024)
                best_similarity = 0
                best_smiles = candidates[0]
                for cand_smiles in candidates:
                    cand_mol = Chem.MolFromSmiles(cand_smiles)
                    if cand_mol:
                        cand_fp = AllChem.GetMorganFingerprintAsBitVect(cand_mol, 2, nBits=1024)
                        from rdkit import DataStructs
                        sim = DataStructs.TanimotoSimilarity(target_fp, cand_fp)
                        if sim > best_similarity:
                            best_similarity = sim
                            best_smiles = cand_smiles
                return best_smiles
            except Exception:
                return candidates[0]

    # 策略2：Murcko骨架
    try:
        from rdkit.Chem import MurckoScaffold
        scaffold = MurckoScaffold.GetScaffoldForMol(mol)
        if scaffold and scaffold.GetNumAtoms() > 3:
            return Chem.MolToSmiles(scaffold)
    except Exception:
        pass

    # 最终fallback
    return 'c1ccccc1'


def generate_route_structures(smiles: str, steps: list) -> dict:
    """为整个合成路线生成所有节点的2D结构图

    返回包含目标分子、中间体和起始原料的结构信息。
    中间体数量 = steps - 1（因为最后一步产物是目标分子），上限3个。
    """
    from rdkit import Chem

    target_svg = generate_2d_svg(smiles)
    target_mol = Chem.MolFromSmiles(smiles)

    intermediate_svgs = []
    start_material_svgs = []

    if target_mol and steps:
        reversed_steps = list(reversed(steps))  # 逆合成：从目标到原料

        # 生成中间体：每一步的产物，最后一步除外（产物是目标分子），上限3个
        num_intermediates = min(len(steps) - 1, 3) if len(steps) > 1 else 0

        for i in range(num_intermediates):
            step = reversed_steps[i]
            reaction_key = None
            # 从反应名称推断反应类型
            for rk, template in REACTION_TEMPLATES.items():
                if template['name'] == step.get('reaction_name'):
                    reaction_key = rk
                    break

            frag_smiles = _generate_intermediate_smiles(target_mol, i, reaction_key)
            if frag_smiles:
                svg = generate_2d_svg(frag_smiles)
                intermediate_svgs.append({
                    'smiles': frag_smiles,
                    'svg': svg
                })

        # 生成起始原料：第一步（forward 中的 step0）的前体
        # step0 在 reversed_steps 中是最后一个元素
        start_reaction_key = None
        if reversed_steps:
            first_step = reversed_steps[-1]  # step0
            for rk, template in REACTION_TEMPLATES.items():
                if template['name'] == first_step.get('reaction_name'):
                    start_reaction_key = rk
                    break

        start_smiles = _generate_start_material_smiles(target_mol, start_reaction_key)
        if start_smiles:
            svg = generate_2d_svg(start_smiles)
            start_material_svgs.append({
                'smiles': start_smiles,
                'svg': svg
            })

    # 填充中间体（如果不足）
    while len(intermediate_svgs) < len(steps) - 1 and len(intermediate_svgs) < 3:
        intermediate_svgs.append({
            'smiles': smiles,
            'svg': target_svg
        })

    # 填充起始原料
    if not start_material_svgs:
        start_material_svgs.append({
            'smiles': 'c1ccccc1',
            'svg': generate_2d_svg('c1ccccc1')
        })

    return {
        'target': {
            'smiles': smiles,
            'svg': target_svg
        },
        'intermediates': intermediate_svgs,
        'start_materials': start_material_svgs
    }
