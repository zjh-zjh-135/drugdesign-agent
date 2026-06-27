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
        'mw_min': 200, 'mw_max': 500,        # 收紧：排除过小和过大分子
        'clogp_min': 0.5, 'clogp_max': 4.5,  # 收紧：更严格的药物样性范围
        'tpsa_min': 40, 'tpsa_max': 120,      # 收紧：中等极性范围
        'hbd_max': 4,                         # 收紧：减少氢键供体
        'hba_max': 10,                        # 收紧：减少氢键受体
        'rotb_max': 8,                        # 收紧：减少柔性
        'sa_score_max': 4.5,                 # 收紧：合成难度要求更高
    }
    
    def __init__(self, thresholds: Dict = None):
        self.thresholds = thresholds or self.DEFAULT_THRESHOLDS.copy()
    
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
