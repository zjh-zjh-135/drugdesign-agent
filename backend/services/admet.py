"""ADMET预测服务 - 基于ADMET-AI真实ML模型 + RDKit描述符fallback"""
import subprocess
import json
import os
import sys
from typing import Dict, List
from rdkit import Chem
from .utils import validate_smiles, check_pains, check_brenk

# ADMET-AI子进程脚本路径
_ADMET_PREDICTOR_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'admet_predictor.py'
)

# 模型是否可用
_admet_ai_available = os.path.exists(_ADMET_PREDICTOR_PATH)

# ADMET-AI列名到完整五分类API的映射
_ADMET_AI_MAP = {
    'absorption.solubility': 'Solubility_AqSolDB',
    'absorption.permeability': 'Caco2_Wang',
    'absorption.oral_bioavailability': 'Bioavailability_Ma',
    'absorption.hia': 'HIA_Hou',
    'absorption.pampa': 'PAMPA_NCATS',
    'absorption.lipophilicity': 'Lipophilicity_AstraZeneca',
    'absorption.hydration_free_energy': 'HydrationFreeEnergy_FreeSolv',
    'distribution.bbb': 'BBB_Martins',
    'distribution.ppbr': 'PPBR_AZ',
    'distribution.vdss': 'VDss_Lombardo',
    'metabolism.cyp1a2': 'CYP1A2_Veith',
    'metabolism.cyp2c19': 'CYP2C19_Veith',
    'metabolism.cyp2c9': 'CYP2C9_Veith',
    'metabolism.cyp2d6': 'CYP2D6_Veith',
    'metabolism.cyp3a4': 'CYP3A4_Veith',
    'excretion.clearance_hep': 'Clearance_Hepatocyte_AZ',
    'excretion.clearance_mic': 'Clearance_Microsome_AZ',
    'excretion.half_life': 'Half_Life_Obach',
    'toxicity.herg': 'hERG',
    'toxicity.ames': 'AMES',
    'toxicity.dili': 'DILI',
    'toxicity.clintox': 'ClinTox',
    'toxicity.skin_reaction': 'Skin_Reaction',
    'toxicity.carcinogens': 'Carcinogens_Lagunin',
    'toxicity.ld50': 'LD50_Zhu',
    'alerts.pains': 'PAINS_alert',
    'alerts.brenk': 'BRENK_alert',
    'alerts.nih': 'NIH_alert',
    'drug_likeness.qed': 'QED',
    'drug_likeness.lipinski_violations': 'Lipinski',
}


def _load_descriptors():
    """尝试加载RDKit Descriptors作为fallback"""
    try:
        from rdkit.Chem import Descriptors
        return Descriptors
    except Exception:
        return None


def _load_rdmol_descriptors():
    """尝试加载RDKit rdMolDescriptors作为fallback"""
    try:
        from rdkit.Chem import rdMolDescriptors
        return rdMolDescriptors
    except Exception:
        return None


class AdmetPredictor:
    """ADMET预测器 - 优先使用ADMET-AI真实ML模型，失败时回退到RDKit规则"""
    
    @staticmethod
    def predict(smiles: str) -> Dict:
        """预测单个分子的完整五分类ADMET性质"""
        # 优先使用ADMET-AI
        if _admet_ai_available:
            try:
                result = AdmetPredictor._predict_with_admet_ai([smiles])
                if result and len(result) > 0:
                    return AdmetPredictor._map_admet_ai_result(result[0])
            except Exception:
                # ADMET-AI失败，回退到RDKit
                pass
        
        # Fallback: RDKit描述符+规则
        return AdmetPredictor._predict_with_rdkit(smiles)
    
    @staticmethod
    def _predict_with_admet_ai(smiles_list: List[str]) -> List[Dict]:
        """使用ADMET-AI子进程进行真实ML预测"""
        input_str = '\n'.join(smiles_list)
        proc = subprocess.run(
            [sys.executable, _ADMET_PREDICTOR_PATH],
            input=input_str,
            capture_output=True,
            text=True,
            timeout=120
        )
        
        # 解析JSON输出（stdout最后一行是JSON）
        lines = [l for l in proc.stdout.strip().split('\n') if l.strip()]
        if not lines:
            return []
        
        last_line = lines[-1]
        try:
            data = json.loads(last_line)
            if isinstance(data, dict) and 'error' in data:
                return []
            return data if isinstance(data, list) else []
        except json.JSONDecodeError:
            return []
    
    @staticmethod
    def _map_admet_ai_result(row: Dict) -> Dict:
        """将ADMET-AI结果映射到完整五分类API格式"""
        # CYP综合抑制概率（取CYP家族的平均值）
        cyp_values = [
            row.get('CYP1A2_Veith', 0),
            row.get('CYP2C19_Veith', 0),
            row.get('CYP2C9_Veith', 0),
            row.get('CYP2D6_Veith', 0),
            row.get('CYP3A4_Veith', 0),
        ]
        cyp_inhibition = sum(cyp_values) / len(cyp_values) if cyp_values else 0
        
        # 综合评分（加权平均）
        # 高值=好: solubility, permeability, bbb, oral_bio, hia, pampa
        # 低值=好: herg, ames, dili, cyp, clintox, carcinogens, skin_reaction
        good_scores = [
            min(100, max(0, 50 - row.get('Solubility_AqSolDB', 0) * 10)),  # Solubility (logS, higher=better)
            min(100, max(0, row.get('Caco2_Wang', -10) + 10) * 10),  # Caco2 (log, higher=better)
            row.get('BBB_Martins', 0) * 100,
            row.get('Bioavailability_Ma', 0) * 100,
            row.get('HIA_Hou', 0) * 100,
            row.get('PAMPA_NCATS', 0) * 100,
        ]
        bad_scores = [
            (1 - row.get('hERG', 0)) * 100,
            (1 - row.get('AMES', 0)) * 100,
            (1 - row.get('DILI', 0)) * 100,
            (1 - cyp_inhibition) * 100,
            (1 - row.get('ClinTox', 0)) * 100,
            (1 - row.get('Carcinogens_Lagunin', 0)) * 100,
            (1 - row.get('Skin_Reaction', 0)) * 100,
        ]
        
        all_scores = good_scores + bad_scores
        overall = sum(all_scores) / len(all_scores) if all_scores else 50
        
        # Lipinski violations
        lipinski = int(row.get('Lipinski', 0))
        
        return {
            'absorption': {
                'solubility': round(row.get('Solubility_AqSolDB', 0), 2),
                'permeability': round(row.get('Caco2_Wang', 0), 2),
                'oral_bioavailability': round(row.get('Bioavailability_Ma', 0), 3),
                'hia': round(row.get('HIA_Hou', 0), 3),
                'pampa': round(row.get('PAMPA_NCATS', 0), 3),
                'lipophilicity': round(row.get('Lipophilicity_AstraZeneca', 0), 2),
                'hydration_free_energy': round(row.get('HydrationFreeEnergy_FreeSolv', 0), 2),
            },
            'distribution': {
                'bbb': round(row.get('BBB_Martins', 0), 3),
                'ppbr': round(row.get('PPBR_AZ', 0), 3),
                'vdss': round(row.get('VDss_Lombardo', 0), 2),
            },
            'metabolism': {
                'cyp1a2': round(row.get('CYP1A2_Veith', 0), 3),
                'cyp2c19': round(row.get('CYP2C19_Veith', 0), 3),
                'cyp2c9': round(row.get('CYP2C9_Veith', 0), 3),
                'cyp2d6': round(row.get('CYP2D6_Veith', 0), 3),
                'cyp3a4': round(row.get('CYP3A4_Veith', 0), 3),
                'cyp_inhibition': round(cyp_inhibition, 3),
            },
            'excretion': {
                'clearance_hep': round(row.get('Clearance_Hepatocyte_AZ', 0), 2),
                'clearance_mic': round(row.get('Clearance_Microsome_AZ', 0), 2),
                'half_life': round(row.get('Half_Life_Obach', 0), 2),
            },
            'toxicity': {
                'herg': round(row.get('hERG', 0), 3),
                'ames': round(row.get('AMES', 0), 3),
                'dili': round(row.get('DILI', 0), 3),
                'clintox': round(row.get('ClinTox', 0), 3),
                'skin_reaction': round(row.get('Skin_Reaction', 0), 3),
                'carcinogens': round(row.get('Carcinogens_Lagunin', 0), 3),
                'ld50': round(row.get('LD50_Zhu', 0), 2),
            },
            'overall_score': round(overall, 2),
            'alerts': {
                'pains': int(row.get('PAINS_alert', 0)),
                'brenk': int(row.get('BRENK_alert', 0)),
                'nih': int(row.get('NIH_alert', 0)),
            },
            'drug_likeness': {
                'qed': round(row.get('QED', 0), 3),
                'lipinski_violations': lipinski,
                'is_drug_like': row.get('QED', 0) > 0.3 and lipinski <= 4,
            },
            'source': 'admet_ai',
        }
    
    @staticmethod
    def _predict_with_rdkit(smiles: str) -> Dict:
        """RDKit描述符+规则fallback - 返回完整五分类结构"""
        mol = validate_smiles(smiles)
        if mol is None:
            return {'error': 'SMILES解析失败'}
        
        Descriptors = _load_descriptors()
        rdMolDescriptors = _load_rdmol_descriptors()
        
        if Descriptors is None or rdMolDescriptors is None:
            return {'error': 'RDKit描述符模块不可用'}
        
        try:
            desc = {
                'mw': Descriptors.MolWt(mol),
                'logp': Descriptors.MolLogP(mol),
                'tpsa': Descriptors.TPSA(mol),
                'hbd': rdMolDescriptors.CalcNumHBD(mol),
                'hba': rdMolDescriptors.CalcNumHBA(mol),
                'rotb': rdMolDescriptors.CalcNumRotatableBonds(mol),
                'qed': Descriptors.qed(mol),
            }
        except Exception:
            return {'error': '描述符计算失败'}
        
        # Lipinski violations
        lipinski_violations = 0
        if desc['mw'] > 500: lipinski_violations += 1
        if desc['logp'] > 5: lipinski_violations += 1
        if desc['hbd'] > 5: lipinski_violations += 1
        if desc['hba'] > 10: lipinski_violations += 1
        
        # --- Absorption ---
        logS = -0.5 - 0.5 * desc['logp']  # rough logS estimate
        log_caco2 = desc['logp'] * 0.5 - desc['tpsa'] * 0.01 - 5.5  # rough log Caco2
        
        oral_bio = 0
        if desc['mw'] <= 500: oral_bio += 25
        if desc['logp'] <= 5: oral_bio += 25
        if desc['hbd'] <= 5: oral_bio += 15
        if desc['hba'] <= 10: oral_bio += 15
        if desc['rotb'] <= 10: oral_bio += 10
        if desc['tpsa'] <= 140: oral_bio += 10
        oral_bio = min(1.0, oral_bio / 100.0)
        
        hia = min(1.0, oral_bio * 0.95 + 0.05)
        pampa = max(0, min(1.0, desc['logp'] * 0.15 - desc['tpsa'] * 0.003 + 0.3))
        hydration_free_energy = -desc['tpsa'] * 0.05 - desc['hbd'] * 0.5
        
        # --- Distribution ---
        bbb = 0.3 if 1 <= desc['logp'] <= 4 else 0.0
        bbb += 0.4 if desc['tpsa'] < 90 else 0.0
        bbb += 0.3 if desc['mw'] < 450 else 0.0
        bbb = min(1.0, bbb)
        
        ppbr = min(1.0, max(0, desc['logp'] * 0.1 + 0.2))
        vdss = 0.5 + desc['logp'] * 0.3
        
        # --- Metabolism ---
        cyp_base = 0.3 if desc['logp'] > 3.5 else 0.1
        cyp1a2 = min(1.0, cyp_base + (0.1 if desc['logp'] > 3 else 0))
        cyp2c19 = min(1.0, cyp_base + 0.05)
        cyp2c9 = min(1.0, cyp_base + 0.15)
        cyp2d6 = min(1.0, cyp_base + (0.05 if desc['logp'] > 3.5 else 0))
        cyp3a4 = min(1.0, cyp_base + 0.2)
        cyp_inhibition = sum([cyp1a2, cyp2c19, cyp2c9, cyp2d6, cyp3a4]) / 5.0
        
        # --- Excretion ---
        clearance_hep = max(0, 5 + desc['logp'] * 2 - desc['mw'] * 0.01)
        clearance_mic = max(0, 10 + desc['logp'] * 3 - desc['mw'] * 0.005)
        half_life = max(0.5, 2 + desc['logp'] * 0.5)
        
        # --- Toxicity ---
        herg = 0.4 if desc['logp'] > 3.5 else 0.1
        ames = 0.3
        dili = 0.3 if desc['logp'] > 4 and desc['mw'] > 500 else 0.1
        clintox = (ames + dili + herg) / 3.0
        skin_reaction = 0.2 if desc['logp'] > 4 else 0.1
        carcinogens = ames * 0.8
        ld50 = max(0.1, 3.0 - desc['logp'] * 0.2)
        
        # --- Overall score ---
        good_scores = [
            min(100, max(0, 50 - logS * 10)),
            min(100, max(0, (log_caco2 + 10) * 10)),
            bbb * 100,
            oral_bio * 100,
            hia * 100,
            pampa * 100,
        ]
        bad_scores = [
            (1 - herg) * 100,
            (1 - ames) * 100,
            (1 - dili) * 100,
            (1 - cyp_inhibition) * 100,
            (1 - clintox) * 100,
            (1 - carcinogens) * 100,
            (1 - skin_reaction) * 100,
        ]
        
        all_scores = good_scores + bad_scores
        overall = sum(all_scores) / len(all_scores) if all_scores else 50
        
        # --- Alerts ---
        try:
            pains_alert = 0 if check_pains(mol) else 1
        except Exception:
            pains_alert = 0
        try:
            brenk_alert = 0 if check_brenk(mol) else 1
        except Exception:
            brenk_alert = 0
        
        return {
            'absorption': {
                'solubility': round(logS, 2),
                'permeability': round(log_caco2, 2),
                'oral_bioavailability': round(oral_bio, 3),
                'hia': round(hia, 3),
                'pampa': round(pampa, 3),
                'lipophilicity': round(desc['logp'], 2),
                'hydration_free_energy': round(hydration_free_energy, 2),
            },
            'distribution': {
                'bbb': round(bbb, 3),
                'ppbr': round(ppbr, 3),
                'vdss': round(vdss, 2),
            },
            'metabolism': {
                'cyp1a2': round(cyp1a2, 3),
                'cyp2c19': round(cyp2c19, 3),
                'cyp2c9': round(cyp2c9, 3),
                'cyp2d6': round(cyp2d6, 3),
                'cyp3a4': round(cyp3a4, 3),
                'cyp_inhibition': round(cyp_inhibition, 3),
            },
            'excretion': {
                'clearance_hep': round(clearance_hep, 2),
                'clearance_mic': round(clearance_mic, 2),
                'half_life': round(half_life, 2),
            },
            'toxicity': {
                'herg': round(herg, 3),
                'ames': round(ames, 3),
                'dili': round(dili, 3),
                'clintox': round(clintox, 3),
                'skin_reaction': round(skin_reaction, 3),
                'carcinogens': round(carcinogens, 3),
                'ld50': round(ld50, 2),
            },
            'overall_score': round(overall, 2),
            'alerts': {
                'pains': pains_alert,
                'brenk': brenk_alert,
                'nih': 0,
            },
            'drug_likeness': {
                'qed': round(desc['qed'], 3),
                'lipinski_violations': lipinski_violations,
                'is_drug_like': desc['qed'] > 0.3 and lipinski_violations <= 4,
            },
            'source': 'rdkit_fallback',
        }
    
    @staticmethod
    def predict_batch(smiles_list: List[str]) -> List[Dict]:
        """批量预测 - 优先使用ADMET-AI一次预测所有"""
        if _admet_ai_available and len(smiles_list) > 0:
            try:
                results = AdmetPredictor._predict_with_admet_ai(smiles_list)
                if results and len(results) == len(smiles_list):
                    return [AdmetPredictor._map_admet_ai_result(r) for r in results]
            except Exception:
                pass
        
        # Fallback: 逐个用RDKit
        return [AdmetPredictor._predict_with_rdkit(smi) for smi in smiles_list]
