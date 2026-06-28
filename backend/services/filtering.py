"""分子过滤引擎 - PAINS + 药物样性 + SA Score"""
from typing import Dict, List, Tuple
from rdkit import Chem
from .utils import (
    validate_smiles, compute_descriptors, compute_sa_score, 
    check_pains, check_brenk, canonicalize_smiles, inchi_from_smiles
)


class MoleculeFilter:
    """分子过滤引擎"""
    
    DEFAULT_THRESHOLDS = {
        'mw_min': 200, 'mw_max': 600,        # 放宽: 最小200, 最大600
        'clogp_min': -1, 'clogp_max': 6,     # 放宽: 最小-1(极性), 最大6
        'tpsa_min': 20, 'tpsa_max': 140,     # 放宽: 最小20(小分子可20+), 最大140
        'hbd_max': 6,                         # 放宽: 6个氢键供体
        'hba_max': 12,                        # 放宽: 12个氢键受体
        'rotb_max': 12,                       # 放宽: 12个可旋转键
        'sa_score_max': 5.5,                 # 放宽: 合成难度容忍到5.5
    }
    
    def __init__(self, thresholds: Dict = None):
        if thresholds is None:
            self.thresholds = self.DEFAULT_THRESHOLDS.copy()
        else:
            # 智能合并：传入的参数不能覆盖默认值为更严格的值
            # 这样可以防止旧项目存储的严格阈值覆盖新放宽的默认值
            merged = self.DEFAULT_THRESHOLDS.copy()
            for key, value in thresholds.items():
                if key in merged and value is not None:
                    if 'min' in key:
                        # min 值取更小（更宽松）
                        merged[key] = min(merged[key], value)
                    elif 'max' in key:
                        # max 值取更大（更宽松）
                        merged[key] = max(merged[key], value)
                    else:
                        merged[key] = value
                elif value is not None:
                    merged[key] = value
            self.thresholds = merged

    
    def filter_single(self, smiles: str) -> Tuple[bool, Dict, str]:
        """
        对单个分子进行过滤
        返回: (是否通过, 描述符字典, 失败原因)
        """
        mol = validate_smiles(smiles)
        if mol is None:
            return False, {}, "SMILES解析失败"
        
        # 计算描述符
        desc = compute_descriptors(mol)
        if not desc:
            return False, {}, "描述符计算失败"
        
        desc['sa_score'] = compute_sa_score(mol)
        
        # 1. PAINS过滤
        if not check_pains(mol):
            desc['pass_pains'] = False
            return False, desc, "PAINS过滤失败"
        desc['pass_pains'] = True
        
        # 2. Brenk过滤
        if not check_brenk(mol):
            return False, desc, "Brenk过滤失败"
        
        # 3. 药物样性规则
        reasons = []
        if desc['mw'] < self.thresholds['mw_min'] or desc['mw'] > self.thresholds['mw_max']:
            reasons.append(f"MW {desc['mw']:.1f} 超出范围 [{self.thresholds['mw_min']}-{self.thresholds['mw_max']}]")
        if desc['clogp'] < self.thresholds['clogp_min'] or desc['clogp'] > self.thresholds['clogp_max']:
            reasons.append(f"LogP {desc['clogp']:.2f} 超出范围 [{self.thresholds['clogp_min']}-{self.thresholds['clogp_max']}]")
        if desc['tpsa'] < self.thresholds['tpsa_min'] or desc['tpsa'] > self.thresholds['tpsa_max']:
            reasons.append(f"TPSA {desc['tpsa']:.1f} 超出范围 [{self.thresholds['tpsa_min']}-{self.thresholds['tpsa_max']}]")
        if desc['hbd'] > self.thresholds['hbd_max']:
            reasons.append(f"HBD {desc['hbd']} > {self.thresholds['hbd_max']}")
        if desc['hba'] > self.thresholds['hba_max']:
            reasons.append(f"HBA {desc['hba']} > {self.thresholds['hba_max']}")
        if desc['rotb'] > self.thresholds['rotb_max']:
            reasons.append(f"RotB {desc['rotb']} > {self.thresholds['rotb_max']}")
        if desc['sa_score'] > self.thresholds['sa_score_max']:
            reasons.append(f"SA Score {desc['sa_score']:.2f} > {self.thresholds['sa_score_max']}")
        
        if reasons:
            desc['pass_filters'] = False
            return False, desc, "; ".join(reasons)
        
        desc['pass_filters'] = True
        return True, desc, ""
    
    def filter_batch(self, smiles_list: List[str]) -> Tuple[List[str], List[Dict], List[str]]:
        """批量过滤"""
        passed = []
        descriptors = []
        failed = []
        
        for smi in smiles_list:
            ok, desc, reason = self.filter_single(smi)
            if ok:
                passed.append(smi)
            descriptors.append(desc)
            if not ok:
                failed.append(f"{smi}: {reason}")
        
        return passed, descriptors, failed
    
    def deduplicate(self, smiles_list: List[str]) -> List[str]:
        """基于InChI去重"""
        seen = set()
        unique = []
        for smi in smiles_list:
            inchi_key = inchi_from_smiles(smi)
            if inchi_key and inchi_key not in seen:
                seen.add(inchi_key)
                unique.append(smi)
        return unique
