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
        'mw_min': 250, 'mw_max': 550,        # 与数据库默认值对齐
        'clogp_min': 0, 'clogp_max': 5,      # 与数据库默认值对齐
        'tpsa_min': 40, 'tpsa_max': 120,     # 与数据库默认值对齐
        'hbd_max': 5,                         # 与数据库默认值对齐
        'hba_max': 10,                        # 与数据库默认值对齐
        'rotb_max': 10,                       # 与数据库默认值对齐
        'sa_score_max': 4.5,                 # 与数据库默认值对齐
    }
    
    def __init__(self, thresholds: Dict = None):
        if thresholds is None:
            self.thresholds = self.DEFAULT_THRESHOLDS.copy()
        else:
            # 合并：传入的参数覆盖默认，缺失的补全
            # 这样空字典 {} 也会使用 DEFAULT_THRESHOLDS（不会回退）
            self.thresholds = {**self.DEFAULT_THRESHOLDS, **thresholds}

    
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
