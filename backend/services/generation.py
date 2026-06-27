"""分子生成引擎 - CReM + RDKit"""
import random
from typing import List, Dict, Optional
from rdkit import Chem
from .utils import validate_smiles, canonicalize_smiles


class MoleculeGenerator:
    """分子生成器"""
    
    def __init__(self):
        self.crem_available = False
        try:
            import crem
            self.crem_available = True
        except ImportError:
            pass
    
    def generate(self, 
                 reference_smiles: List[str], 
                 num_variants: int = 100,
                 strategy: str = 'crem',
                 generation_depth: int = 1,
                 failed_smiles: List[str] = None
    ) -> List[str]:
        """
        基于已知活性分子生成analogs，并参考历史失败数据避免重复
        
        Args:
            reference_smiles: 已知活性分子SMILES列表
            num_variants: 目标生成分子数
            strategy: 生成策略 'crem' | 'scaffold' | 'rdkit'
            generation_depth: 变异深度
            failed_smiles: 历史失败分子SMILES列表，用于避免重复生成
        
        Returns:
            生成的SMILES列表（已排除历史失败分子）
        """
        # 标准化失败分子列表
        failed_set = set()
        if failed_smiles:
            for s in failed_smiles:
                canon = canonicalize_smiles(s)
                if canon:
                    failed_set.add(canon)
        
        if strategy == 'crem' and self.crem_available:
            result = self._generate_with_crem(reference_smiles, num_variants, failed_set)
        elif strategy == 'scaffold':
            result = self._generate_by_scaffold(reference_smiles, num_variants, failed_set)
        else:
            result = self._generate_with_rdkit(reference_smiles, num_variants, failed_set)
        
        # 最终过滤：确保没有失败分子混入
        filtered = [s for s in result if canonicalize_smiles(s) not in failed_set]
        
        if len(filtered) < len(result):
            self._log_skip = len(result) - len(filtered)
        
        return filtered
    
    def _generate_with_crem(self, reference_smiles: List[str], num_variants: int, failed_set: set = None) -> List[str]:
        """使用CReM进行片段替换生成 - 基于数据库的分子变异"""
        try:
            from crem.crem import mutate_mol
        except ImportError:
            # 如果CReM不可用，直接回退到RDKit
            return self._generate_with_rdkit(reference_smiles, num_variants)
        
        import os
        # 数据库路径：backend/chembl33_sa2_f5.db（ChEMBL33 预构建片段数据库，~200万分子）
        db_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            'backend', 'chembl33_sa2_f5.db'
        )
        if not os.path.exists(db_path):
            # 尝试相对于当前文件的备用路径
            db_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                'chembl33_sa2_f5.db'
            )
        
        # 如果新数据库不存在，尝试使用旧版 replacements.db
        if not os.path.exists(db_path):
            db_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                'backend', 'replacements.db'
            )
        
        generated = []
        for ref_smi in reference_smiles:
            mol = validate_smiles(ref_smi)
            if mol is None:
                continue
            
            try:
                # CReM变异：使用mutate_mol生成完整分子
                # min_freq=0 因为数据库较小，片段频率不高
                variants = list(mutate_mol(
                    mol, 
                    db_name=db_path,
                    radius=3,
                    min_size=1,
                    max_size=10,
                    min_freq=0,
                    max_replacements=num_variants
                ))
                
                for var in variants:
                    if isinstance(var, str):
                        smi = var
                    else:
                        smi = str(var)
                    
                    canon = canonicalize_smiles(smi)
                    if canon and canon not in generated and canon != ref_smi:
                        generated.append(canon)
                    if len(generated) >= num_variants:
                        break
                        
            except Exception as e:
                # 如果CReM失败，记录错误并跳过
                import logging
                logging.getLogger(__name__).warning(f'CReM generation failed for {ref_smi}: {e}')
                continue
            
            if len(generated) >= num_variants:
                break
        
        # 如果CReM没有生成足够分子，用RDKit补充
        if len(generated) < num_variants:
            extra = self._generate_with_rdkit(reference_smiles, num_variants - len(generated), failed_set)
            generated.extend(extra)
        
        return generated[:num_variants]
    
    def _generate_with_rdkit(self, reference_smiles: List[str], num_variants: int, failed_set: set = None) -> List[str]:
        """使用RDKit进行分子变异 - 原子替换和基团添加，自动过滤历史失败分子"""
        generated = []
        import random
        import logging
        random.seed(42)
        
        skipped_count = 0
        
        for ref_smi in reference_smiles:
            mol = validate_smiles(ref_smi)
            if mol is None:
                continue
            
            base_smi = Chem.MolToSmiles(mol, isomericSmiles=True)
            
            # 策略1: 随机单原子替换 (C->N, N->O, etc.)
            for _ in range(min(30, num_variants)):
                try:
                    rw_mol = Chem.RWMol(mol)
                    idx = random.randint(0, rw_mol.GetNumAtoms() - 1)
                    atom = rw_mol.GetAtomAtIdx(idx)
                    old_elem = atom.GetAtomicNum()
                    if old_elem == 1:  # 跳过氢
                        continue
                    
                    # 可替换的原子类型
                    replacements = {
                        6: [7, 8, 9, 16],   # C -> N, O, F, S
                        7: [6, 8, 16],      # N -> C, O, S
                        8: [7, 16],         # O -> N, S
                        16: [6, 7, 8],      # S -> C, N, O
                        9: [17, 35],        # F -> Cl, Br
                        17: [9, 35],        # Cl -> F, Br
                    }
                    new_elem = random.choice(replacements.get(old_elem, [6, 7, 8]))
                    atom.SetAtomicNum(new_elem)
                    
                    Chem.SanitizeMol(rw_mol)
                    new_smi = Chem.MolToSmiles(rw_mol, isomericSmiles=True)
                    if new_smi and new_smi != base_smi and new_smi not in generated:
                        if failed_set and canonicalize_smiles(new_smi) in failed_set:
                            skipped_count += 1
                            continue
                        generated.append(new_smi)
                except:
                    continue
                if len(generated) >= num_variants:
                    break
            
            # 策略2: 使用RDKit的MolFromSmiles + 修饰符拼接（确保化学正确）
            # 常见药物骨架 + 修饰
            modifications = [
                # 在苯环上添加常见取代基（用有效SMILES片段）
                ('c1ccccc1', 'Cc1ccccc1'),           # 苯 -> 甲苯
                ('c1ccccc1', 'Oc1ccccc1'),           # 苯 -> 苯酚
                ('c1ccccc1', 'Nc1ccccc1'),           # 苯 -> 苯胺
                ('c1ccccc1', 'Fc1ccccc1'),           # 苯 -> 氟苯
                ('c1ccccc1', 'Clc1ccccc1'),          # 苯 -> 氯苯
                ('CC(=O)O', 'CC(=O)N'),             # 羧酸 -> 酰胺
                ('CC(=O)O', 'CCN'),                 # 羧酸 -> 胺
                ('CC(=O)Oc1ccccc1', 'CCOc1ccccc1'), # 酯 -> 醚
                ('CC(=O)Oc1ccccc1', 'c1ccc(O)cc1'), # 酯 -> 苯酚
            ]
            
            for pattern, replacement in modifications:
                try:
                    patt = Chem.MolFromSmarts(pattern)
                    repl = Chem.MolFromSmiles(replacement)
                    if patt and repl and mol.HasSubstructMatch(patt):
                        new_mols = Chem.ReplaceSubstructs(mol, patt, repl, replaceAll=False)
                        for nm in new_mols[:2]:
                            if nm:
                                Chem.SanitizeMol(nm)
                                smi = Chem.MolToSmiles(nm, isomericSmiles=True)
                                if smi and smi != base_smi and smi not in generated:
                                    if failed_set and canonicalize_smiles(smi) in failed_set:
                                        skipped_count += 1
                                        continue
                                    generated.append(smi)
                except:
                    continue
                if len(generated) >= num_variants:
                    break
            
            # 策略3: 枚举常见药物片段组合
            common_fragments = [
                'c1ccccc1', 'c1ccc(O)cc1', 'c1ccc(N)cc1', 'c1ccc(F)cc1',
                'CC(=O)O', 'CC(=O)N', 'CCN', 'CCO',
                'c1ccncc1', 'c1cncnc1', 'c1ncccn1',
                'O=c1[nH]c2ccccc2s1', 'c1ccc2c(c1)OCO2',
            ]
            for frag in common_fragments:
                try:
                    fm = Chem.MolFromSmiles(frag)
                    if fm and fm.GetNumAtoms() > 3:
                        smi = Chem.MolToSmiles(fm, isomericSmiles=True)
                        if smi not in generated and smi != base_smi:
                            if failed_set and canonicalize_smiles(smi) in failed_set:
                                skipped_count += 1
                                continue
                            generated.append(smi)
                except:
                    continue
                if len(generated) >= num_variants:
                    break
            
            if len(generated) >= num_variants:
                break
        
        if skipped_count > 0:
            logging.getLogger(__name__).info(f'RDKit生成跳过了 {skipped_count} 个已知失败分子')
        
        return generated[:num_variants]
    
    def _generate_by_scaffold(self, reference_smiles: List[str], num_variants: int, failed_set: set = None) -> List[str]:
        """基于骨架进行系统性的取代基枚举，自动过滤历史失败分子"""
        try:
            from rdkit.Chem.Scaffolds import MurckoScaffold
        except ImportError:
            import rdkit.Chem.Scaffolds.MurckoScaffold as MurckoScaffold
        
        generated = []
        import logging
        skipped_count = 0
        common_r_groups = [
            'C', 'CC', 'CCC', 'c1ccccc1',
            'N', 'CN', 'NC', 'N(C)C',
            'O', 'CO', 'OC', 'OCC',
            'F', 'Cl', 'Br', 'CF3',
            'OH', 'NH2', 'COOH', 'NO2',
        ]
        
        for ref_smi in reference_smiles:
            mol = validate_smiles(ref_smi)
            if mol is None:
                continue
            
            scaffold = MurckoScaffold.GetScaffoldForMol(mol)
            scaffold_smi = Chem.MolToSmiles(scaffold)
            
            # 在骨架上添加不同的R基团
            for r_group in common_r_groups:
                try:
                    # 简化：将骨架SMILES和R基团组合
                    # 实际应该用更复杂的化学逻辑
                    new_smi = scaffold_smi.replace('*', r_group, 1)
                    new_mol = validate_smiles(new_smi)
                    if new_mol:
                        canon = canonicalize_smiles(new_smi)
                        if canon and canon not in generated:
                            if failed_set and canon in failed_set:
                                skipped_count += 1
                                continue
                            generated.append(canon)
                except:
                    continue
                
                if len(generated) >= num_variants:
                    break
            
            if len(generated) >= num_variants:
                break
        
        if skipped_count > 0:
            logging.getLogger(__name__).info(f'Scaffold生成跳过了 {skipped_count} 个已知失败分子')
        
        return generated[:num_variants]
