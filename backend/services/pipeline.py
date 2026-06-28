import logging

logger = logging.getLogger(__name__)
"""Pipeline编排器 - 串联8层药物设计流程"""
import threading
import time
import json
from typing import Dict, List, Optional
from datetime import datetime

from .generation import MoleculeGenerator
from .filtering import MoleculeFilter
from .admet import AdmetPredictor
from .docking import DockingScreen
from .synthesis import SynthesisAnalyzer
from .fep_refinement import FEPRefiner, FEPReportGenerator
from .utils import validate_smiles, canonicalize_smiles, inchi_from_smiles


class PipelineRunner:
    """Pipeline运行器 - 每个线程使用独立数据库session"""
    
    # 全局运行状态存储
    _running_jobs = {}
    _lock = threading.Lock()
    
    def __init__(self, session_factory, project_id: int, params: Dict, pipeline_run_id=None):
        self.session_factory = session_factory  # 工厂函数，线程内创建新session
        self.project_id = project_id
        self.params = params
        self.pipeline_run_id = pipeline_run_id  # 可选：已有 PipelineRun ID（由外部工具创建）
        self.job_id = None
        self.status = 'pending'
        self.logs = []
        self.stats = {
            'input': 0,
            'generated': 0,
            'filtered': 0,
            'structure_screened': 0,
            'admet_passed': 0,
            'refined': 0,
            'synthesis_passed': 0,
            'final': 0,
        }
        self._db = None  # 线程内创建的session（在_run_pipeline中设置）
        self.pipeline_run = None  # 初始化，避免AttributeError
    
    def _log(self, message: str):
        """记录日志"""
        self.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
    
    def run(self) -> str:
        """启动Pipeline运行"""
        self.job_id = f"pipeline_{self.project_id}_{int(time.time())}"
        
        with PipelineRunner._lock:
            PipelineRunner._running_jobs[self.job_id] = self
        
        # 在后台线程运行
        thread = threading.Thread(target=self._run_pipeline)
        thread.daemon = True
        thread.start()
        
        return self.job_id
    
    def _run_pipeline(self):
        """执行Pipeline的8个阶段 - 在线程内创建独立session"""
        self._db = self.session_factory()
        try:
            self.status = 'running'
            self._log("Pipeline启动")
            
            # 创建或复用 PipelineRun 记录，用于关联失败分子
            from ..models.database import PipelineRun
            if self.pipeline_run_id:
                self.pipeline_run = self._db.query(PipelineRun).filter(
                    PipelineRun.id == self.pipeline_run_id
                ).first()
                if self.pipeline_run:
                    self.pipeline_run.status = 'running'
                    self.pipeline_run.params_json = self.params
                    if not self.pipeline_run.start_time:
                        self.pipeline_run.start_time = datetime.now()
                    self._db.commit()
            
            if not self.pipeline_run:
                self.pipeline_run = PipelineRun(
                    project_id=self.project_id,
                    status='running',
                    start_time=datetime.now(),
                    num_generated=0,
                    num_filtered=0,
                    num_passed=0,
                    num_failed=0,
                    params_json=self.params
                )
                self._db.add(self.pipeline_run)
                self._db.commit()
                self.pipeline_run_id = self.pipeline_run.id
            
            # 清理该项目之前的非失败生成数据
            self._cleanup_previous_runs()
            
            # 8个阶段
            self._stage_input()
            self._stage_generation()
            self._stage_filtering()
            self._stage_structure_screening()
            self._stage_admet()
            self._stage_refinement()
            self._stage_synthesis()
            self._stage_output()
            
            self.status = 'completed'
            self._log("Pipeline完成")
            
        except Exception as e:
            import traceback
            self.status = 'failed'
            self._log(f"Pipeline失败: {str(e)}")
            self._log(traceback.format_exc())
            if hasattr(self, 'pipeline_run'):
                self.pipeline_run.status = 'failed'
                self._db.commit()
        finally:
            if self._db:
                try:
                    self._db.close()
                except Exception as e:
                    logger.exception(f'Pipeline错误: {e}')
                    pass
                self._db = None
    
    def _cleanup_previous_runs(self):
        """清理该项目之前的非失败生成分子"""
        from ..models.database import GeneratedMolecule
        try:
            enable_iteration = self.params.get('enable_failed_iteration', False)
            
            if enable_iteration:
                # 迭代模式：保留失败分子和已通过的分子，删除其他中间状态
                count = self._db.query(GeneratedMolecule).filter(
                    GeneratedMolecule.project_id == self.project_id,
                    GeneratedMolecule.pipeline_status.notin_(['failed', 'synthesis_passed'])
                ).delete(synchronize_session=False)
                self._db.commit()
                if count > 0:
                    self._log(f"清理 {count} 个中间状态历史生成分子")
                
                passed_count = self._db.query(GeneratedMolecule).filter(
                    GeneratedMolecule.project_id == self.project_id,
                    GeneratedMolecule.pipeline_status == 'synthesis_passed'
                ).count()
                if passed_count > 0:
                    self._log(f"保留 {passed_count} 个历史通过分子")
                
                failed_count = self._db.query(GeneratedMolecule).filter(
                    GeneratedMolecule.project_id == self.project_id,
                    GeneratedMolecule.pipeline_status == 'failed'
                ).count()
                if failed_count > 0:
                    self._log(f"保留 {failed_count} 个历史失败分子用于迭代学习")
            else:
                # 传统模式：删除所有历史生成分子
                count = self._db.query(GeneratedMolecule).filter(
                    GeneratedMolecule.project_id == self.project_id
                ).delete(synchronize_session=False)
                self._db.commit()
                if count > 0:
                    self._log(f"清理 {count} 个历史生成分子")
        except Exception as e:
            logger.exception(f'Pipeline错误: {e}')
            self._db.rollback()
            self._log(f"清理历史数据失败: {e}")
    
    def _record_failure(self, molecule, stage_name, reasons_dict):
        """记录分子失败原因到数据库"""
        from ..models.database import MoleculeProperty
        try:
            molecule.pipeline_status = 'failed'
            molecule.failure_stage = stage_name
            molecule.failure_reason = json.dumps(reasons_dict, ensure_ascii=False, default=str)
            molecule.failed_at = datetime.now()
            if hasattr(self, 'pipeline_run_id'):
                molecule.pipeline_run_id = self.pipeline_run_id
            
            prop = self._db.query(MoleculeProperty).filter(
                MoleculeProperty.molecule_id == molecule.id
            ).first()
            if prop:
                prop.failure_stage = stage_name
                prop.failure_reason = json.dumps(reasons_dict, ensure_ascii=False, default=str)
        except Exception as e:
            logger.exception(f'Pipeline错误: {e}')
            pass

    def _stage_input(self):
        """阶段1：输入层"""
        self._log("阶段1: 输入层 - 获取已知活性分子")
        from ..models.database import ActiveMolecule
        try:
            active_mols = self._db.query(ActiveMolecule).filter(
                ActiveMolecule.project_id == self.project_id
            ).all()
            self.reference_smiles = [m.smiles for m in active_mols]
            self.stats['input'] = len(self.reference_smiles)
            self._log(f"获取 {len(self.reference_smiles)} 个已知活性分子")
            if not self.reference_smiles:
                self._log("警告: 没有已知活性分子，使用默认模板")
                self.reference_smiles = ['c1ccccc1']
        except Exception as e:
            self._log(f"输入层失败: {e}")
            self.reference_smiles = ['c1ccccc1']
    
    def _stage_generation(self):
        """阶段2：生成层"""
        enable_iteration = self.params.get('enable_failed_iteration', False)
        if enable_iteration:
            self._log("阶段2: 生成层 - 生成分子变体（参考历史失败数据）")
        else:
            self._log("阶段2: 生成层 - 生成分子变体")
        
        num_target = self.params.get('num_molecules', 5000)
        strategy = self.params.get('generation_strategy', 'crem')
        try:
            failed_smiles = []
            
            # 仅在开启迭代模式时加载历史失败分子
            if enable_iteration:
                from ..models.database import GeneratedMolecule
                try:
                    failed_molecules = self._db.query(GeneratedMolecule).filter(
                        GeneratedMolecule.project_id == self.project_id,
                        GeneratedMolecule.pipeline_status == 'failed'
                    ).all()
                    failed_smiles = [m.smiles for m in failed_molecules]
                    if failed_smiles:
                        self._log(f"已加载 {len(failed_smiles)} 个历史失败分子用于迭代学习")
                except Exception as e:
                    logger.exception(f'Pipeline错误: {e}')
                    pass
            
            generator = MoleculeGenerator()
            generated = generator.generate(
                self.reference_smiles,
                num_variants=num_target,
                strategy=strategy,
                failed_smiles=failed_smiles if enable_iteration else None
            )
            self.stats['generated'] = len(generated)
            self._log(f"生成 {len(generated)} 个分子变体")
            self._save_molecules(generated, 'generated')
        except Exception as e:
            self._log(f"生成层失败: {e}")
            self._save_molecules(['c1ccccc1'], 'generated')
            self.stats['generated'] = 1
    
    def _stage_filtering(self):
        """阶段3：基础过滤层"""
        self._log("阶段3: 基础过滤层 - 应用PAINS和药物样性过滤")
        from ..models.database import GeneratedMolecule
        try:
            molecules = self._db.query(GeneratedMolecule).filter(
                GeneratedMolecule.project_id == self.project_id,
                GeneratedMolecule.pipeline_status == 'generated'
            ).all()
            filter_engine = MoleculeFilter(self.params.get('filter_params', {}))
            passed_count = 0
            failed_count = 0
            for mol in molecules:
                try:
                    ok, desc, reason = filter_engine.filter_single(mol.smiles)
                    self._save_properties(mol.id, desc, ok)
                    if ok:
                        mol.pipeline_status = 'filtered'
                        passed_count += 1
                    else:
                        failed_count += 1
                        self._record_failure(mol, 'filtering', {
                            'reason': '基础过滤未通过',
                            'detail': reason or '不符合PAINS或药物规则',
                            'metrics': {
                                'qed': desc.get('qed'),
                                'sa_score': desc.get('sa_score'),
                                'pass_pains': desc.get('pass_pains'),
                                'pass_filters': desc.get('pass_filters')
                            }
                        })
                except Exception as e:
                    logger.exception(f'Pipeline错误: {e}')
                    failed_count += 1
                    self._record_failure(mol, 'filtering', {
                        'reason': '过滤计算异常',
                        'detail': 'SMILES解析或描述符计算失败'
                    })
            self._db.commit()
            self.stats['filtered'] = passed_count
            self.stats['failed_filtering'] = failed_count
            self._log(f"过滤后通过 {passed_count}/{len(molecules)} 个分子，失败 {failed_count} 个")
        except Exception as e:
            logger.exception(f'Pipeline错误: {e}')
            self._db.rollback()
            self._log(f"过滤层失败: {e}")
            self.stats['filtered'] = 0
    
    def _stage_structure_screening(self):
        """阶段4：结构筛选层 - 基于分子特征多维度筛选"""
        self._log("阶段4: 结构筛选层 - 基于相似性 + QED + SA + 复杂度筛选")
        from ..models.database import GeneratedMolecule, MoleculeProperty
        try:
            molecules = self._db.query(GeneratedMolecule).filter(
                GeneratedMolecule.project_id == self.project_id,
                GeneratedMolecule.pipeline_status == 'filtered'
            ).all()
            if not molecules or not self.reference_smiles:
                self.stats['structure_screened'] = len(molecules)
                return
            screener = DockingScreen()
            passed_count = 0
            failed_count = 0
            for mol in molecules:
                try:
                    mol_obj = validate_smiles(mol.smiles)
                    if not mol_obj:
                        failed_count += 1
                        self._record_failure(mol, 'structure_screening', {
                            'reason': 'SMILES解析失败',
                            'detail': '无法解析分子结构'
                        })
                        continue
                    
                    # 1. 相似度筛选（与参考分子对比）
                    max_sim = 0
                    for ref_smi in self.reference_smiles:
                        ref_obj = validate_smiles(ref_smi)
                        if ref_obj:
                            from .utils import compute_morgan_similarity
                            sim = compute_morgan_similarity(mol_obj, ref_obj)
                            max_sim = max(max_sim, sim)
                    
                    prop = self._db.query(MoleculeProperty).filter(
                        MoleculeProperty.molecule_id == mol.id
                    ).first()
                    if prop: prop.similarity_score = round(max_sim, 4)
                    
                    # 2. 获取分子的QED和SA值
                    qed_score = prop.qed if prop and prop.qed else 0.5
                    sa_score = prop.sa_score if prop and prop.sa_score else 5.0
                    
                    # 3. 计算分子复杂度
                    from rdkit import Chem
                    from rdkit.Chem import Descriptors, rdMolDescriptors
                    num_rings = rdMolDescriptors.CalcNumRings(mol_obj)
                    num_rotatable = rdMolDescriptors.CalcNumRotatableBonds(mol_obj)
                    num_heteroatoms = Descriptors.NumHeteroatoms(mol_obj)
                    mw = Descriptors.MolWt(mol_obj)
                    
                    # 4. 多维度综合判断（强制阈值在合理范围，防止极端参数）
                    similarity_threshold = min(self.params.get('similarity_threshold', 0.3), 0.5)  # 最高0.5
                    qed_threshold = min(self.params.get('qed_threshold', 0.3), 0.3)  # 最高0.3
                    sa_threshold = max(self.params.get('sa_threshold', 5.0), 5.0)  # 最低5.0
                    
                    reasons = []
                    if max_sim < similarity_threshold:
                        reasons.append(f"相似度{max_sim:.2f} < {similarity_threshold}")
                    if qed_score < qed_threshold:
                        reasons.append(f"QED{qed_score:.2f} < {qed_threshold}")
                    if sa_score > sa_threshold:
                        reasons.append(f"SA{sa_score:.2f} > {sa_threshold}")
                    # 复杂度软性限制：大幅放宽
                    if num_rings > 6:
                        reasons.append(f"环数{num_rings} > 6")
                    if num_rotatable > 12:
                        reasons.append(f"旋转键{num_rotatable} > 12")
                    if mw > 600:
                        reasons.append(f"MW{mw:.0f} > 600")
                    
                    if not reasons:
                        mol.pipeline_status = 'structure_screened'
                        passed_count += 1
                    else:
                        failed_count += 1
                        self._record_failure(mol, 'structure_screening', {
                            'reason': '结构筛选未通过',
                            'details': reasons,
                            'metrics': {
                                'similarity': round(max_sim, 4),
                                'qed': round(qed_score, 4),
                                'sa_score': round(sa_score, 4),
                                'num_rings': num_rings,
                                'num_rotatable': num_rotatable,
                                'mw': round(mw, 1)
                            }
                        })
                except Exception as e:
                    logger.exception(f'Pipeline错误: {e}')
                    failed_count += 1
                    self._record_failure(mol, 'structure_screening', {
                        'reason': '结构筛选计算异常',
                        'detail': '计算过程中发生错误'
                    })
            self._db.commit()
            self.stats['structure_screened'] = passed_count
            self.stats['failed_structure_screening'] = failed_count
            self._log(f"结构筛选后通过 {passed_count}/{len(molecules)} 个分子，失败 {failed_count} 个")
        except Exception as e:
            logger.exception(f'Pipeline错误: {e}')
            self._db.rollback()
            self._log(f"结构筛选层失败: {e}")
            self.stats['structure_screened'] = 0

    def _stage_admet(self):
        """阶段5：ADMET层"""
        self._log("阶段5: ADMET层 - 预测ADMET性质")
        from ..models.database import GeneratedMolecule, MoleculeProperty
        try:
            molecules = self._db.query(GeneratedMolecule).filter(
                GeneratedMolecule.project_id == self.project_id,
                GeneratedMolecule.pipeline_status == 'structure_screened'
            ).all()
            
            if not molecules:
                self.stats['admet_passed'] = 0
                self._log("ADMET: 无需要预测的分子")
                return
            
            # 批量收集SMILES，一次子进程预测所有（避免逐个启动子进程导致极慢）
            smiles_list = [mol.smiles for mol in molecules]
            self._log(f"ADMET: 批量预测 {len(smiles_list)} 个分子（约30秒）")
            
            predictor = AdmetPredictor()
            admet_results = predictor.predict_batch(smiles_list)
            
            passed_count = 0
            failed_count = 0
            overall_threshold = min(self.params.get('admet_threshold', 50), 50)  # 强制最高50
            if overall_threshold < 1:
                overall_threshold = 50  # 如果传入0-1范围的异常值，强制回退到50
            
            for mol, admet in zip(molecules, admet_results):
                try:
                    self._save_admet(mol.id, admet)
                    if admet.get('overall_score', 0) >= overall_threshold:
                        mol.pipeline_status = 'admet_passed'
                        passed_count += 1
                        prop = self._db.query(MoleculeProperty).filter(
                            MoleculeProperty.molecule_id == mol.id
                        ).first()
                        if prop: prop.pass_admet = True
                    else:
                        failed_count += 1
                        self._record_failure(mol, 'admet', {
                            'reason': 'ADMET预测未通过',
                            'detail': f"综合评分 {admet.get('overall_score', 0):.1f} < 阈值 {overall_threshold}",
                            'metrics': {
                                'overall_score': admet.get('overall_score', 0),
                                'solubility': admet.get('solubility'),
                                'permeability': admet.get('permeability'),
                                'herg': admet.get('herg'),
                                'ames': admet.get('ames'),
                                'dili': admet.get('dili'),
                                'bbb': admet.get('bbb')
                            }
                        })
                except Exception as e:
                    logger.exception(f'Pipeline错误: {e}')
                    failed_count += 1
                    self._record_failure(mol, 'admet', {
                        'reason': 'ADMET预测异常',
                        'detail': 'ADMET批量预测过程中发生错误'
                    })
            
            self._db.commit()
            self.stats['admet_passed'] = passed_count
            self.stats['failed_admet'] = failed_count
            self._log(f"ADMET预测后通过 {passed_count}/{len(molecules)} 个分子，失败 {failed_count} 个")
        except Exception as e:
            logger.exception(f'Pipeline错误: {e}')
            self._db.rollback()
            self._log(f"ADMET层失败: {e}")
            self.stats['admet_passed'] = 0
    
    def _stage_refinement(self):
        """阶段6：精筛层 - 综合评分排序"""
        self._log("阶段6: 精筛层 - 综合评分排序")
        from ..models.database import GeneratedMolecule, MoleculeProperty, AdmetPrediction
        try:
            molecules = self._db.query(GeneratedMolecule).filter(
                GeneratedMolecule.project_id == self.project_id,
                GeneratedMolecule.pipeline_status == 'admet_passed'
            ).all()
            scored = []
            for mol in molecules:
                try:
                    prop = self._db.query(MoleculeProperty).filter(
                        MoleculeProperty.molecule_id == mol.id
                    ).first()
                    admet = self._db.query(AdmetPrediction).filter(
                        AdmetPrediction.molecule_id == mol.id
                    ).first()
                    if prop and admet:
                        score = (
                            prop.qed * 0.3 +
                            admet.overall_score / 100 * 0.3 +
                            (prop.similarity_score or 0) * 0.2 +
                            (1 - prop.sa_score / 10) * 0.2
                        ) * 100
                        scored.append((mol.id, score, mol, prop, admet))
                except Exception as e:
                    logger.exception(f'Pipeline错误: {e}')
                    continue
            scored.sort(key=lambda x: x[1], reverse=True)
            top_n = self.params.get('top_n', 200)
            top_ids = [item[0] for item in scored[:top_n]]
            failed_count = 0
            for item in scored:
                sid, score, mol, prop, admet = item
                if mol.id in top_ids:
                    mol.pipeline_status = 'refined'
                else:
                    failed_count += 1
                    self._record_failure(mol, 'refinement', {
                        'reason': '精筛未进入Top',
                        'detail': f"综合评分 {score:.1f} 未进入前 {top_n} 名",
                        'metrics': {
                            'score': round(score, 2),
                            'qed': round(prop.qed, 4) if prop else None,
                            'admet_overall': round(admet.overall_score, 2) if admet else None,
                            'similarity': round(prop.similarity_score, 4) if prop else None,
                            'sa_score': round(prop.sa_score, 4) if prop else None
                        }
                    })
            self._db.commit()
            self.stats['refined'] = len(top_ids)
            self.stats['failed_refinement'] = failed_count
            self._log(f"精筛后保留 Top {len(top_ids)} 个分子，淘汰 {failed_count} 个")
        except Exception as e:
            logger.exception(f'Pipeline错误: {e}')
            self._db.rollback()
            self._log(f"精筛层失败: {e}")
            self.stats['refined'] = 0

    def _stage_synthesis(self):
        """阶段7：合成层"""
        self._log("阶段7: 合成层 - 分析合成可及性")
        from ..models.database import GeneratedMolecule
        try:
            molecules = self._db.query(GeneratedMolecule).filter(
                GeneratedMolecule.project_id == self.project_id,
                GeneratedMolecule.pipeline_status == 'refined'
            ).all()
            analyzer = SynthesisAnalyzer()
            passed_count = 0
            failed_count = 0
            for mol in molecules:
                try:
                    result = analyzer.analyze(mol.smiles)
                    self._save_synthesis(mol.id, result)
                    availability_threshold = min(self.params.get('availability_threshold', 0.2), 0.3)  # 强制最高0.3
                    if result.get('availability_score', 0) >= availability_threshold:
                        mol.pipeline_status = 'synthesis_passed'
                        passed_count += 1
                    else:
                        failed_count += 1
                        analysis = result.get('analysis', {})
                        self._record_failure(mol, 'synthesis', {
                            'reason': '合成可及性不足',
                            'detail': f"合成可及性评分 {result.get('availability_score', 0):.2f} < 阈值 {availability_threshold}",
                            'metrics': {
                                'availability_score': round(result.get('availability_score', 0), 2),
                                'num_steps': result.get('num_steps'),
                                'estimated_cost': result.get('estimated_cost'),
                                'step_penalty': analysis.get('step_penalty'),
                                'complexity_penalty': analysis.get('complexity_penalty'),
                                'yield_penalty': analysis.get('yield_penalty'),
                                'num_groups': analysis.get('num_groups')
                            }
                        })
                except Exception as e:
                    logger.exception(f'Pipeline错误: {e}')
                    failed_count += 1
                    self._record_failure(mol, 'synthesis', {
                        'reason': '合成分析异常',
                        'detail': '合成分析过程中发生错误'
                    })
            self._db.commit()
            self.stats['synthesis_passed'] = passed_count
            self.stats['failed_synthesis'] = failed_count
            self._log(f"合成分析后通过 {passed_count} 个分子，失败 {failed_count} 个")
        except Exception as e:
            logger.exception(f'Pipeline错误: {e}')
            self._db.rollback()
            self._log(f"合成层失败: {e}")
            self.stats['synthesis_passed'] = 0
    
    def _stage_output(self):
        """阶段8：输出层"""
        self._log("阶段8: 输出层 - 生成最终结果")
        try:
            from ..models.database import GeneratedMolecule
            from ..config import MOLECULE_IMG_DIR
            import os
            
            final_molecules = self._db.query(GeneratedMolecule).filter(
                GeneratedMolecule.project_id == self.project_id,
                GeneratedMolecule.pipeline_status == 'synthesis_passed'
            ).all()
            
            for mol in final_molecules:
                try:
                    filepath = os.path.join(MOLECULE_IMG_DIR, f'{mol.id}.svg')
                    from .utils import save_molecule_svg
                    save_molecule_svg(mol.smiles, filepath)
                except Exception as e:
                    logger.exception(f'Pipeline错误: {e}')
                    pass
            
            self.stats['final'] = len(final_molecules)
            self._log(f"最终输出 {len(final_molecules)} 个候选分子")
            
            # 更新 PipelineRun 记录
            if hasattr(self, 'pipeline_run') and self.pipeline_run:
                self.pipeline_run.status = 'completed'
                self.pipeline_run.end_time = datetime.now()
                self.pipeline_run.num_generated = self.stats['generated']
                self.pipeline_run.num_filtered = self.stats['filtered']
                self.pipeline_run.num_passed = self.stats['final']
                # 计算总失败数
                total_failed = (
                    self.stats.get('failed_filtering', 0) +
                    self.stats.get('failed_structure_screening', 0) +
                    self.stats.get('failed_admet', 0) +
                    self.stats.get('failed_refinement', 0) +
                    self.stats.get('failed_synthesis', 0)
                )
                self.pipeline_run.num_failed = total_failed
                self._db.commit()
        except Exception as e:
            logger.exception(f'Pipeline错误: {e}')
            self._db.rollback()
            self._log(f"输出层失败: {e}")
    
    def _save_molecules(self, smiles_list: List[str], status: str):
        """保存生成的分子到数据库"""
        from ..models.database import GeneratedMolecule
        for smi in smiles_list:
            try:
                inchi = inchi_from_smiles(smi)
                mol = GeneratedMolecule(
                    project_id=self.project_id,
                    smiles=smi,
                    inchi=inchi,
                    generated_from=self.reference_smiles[0] if self.reference_smiles else '',
                    generation_strategy=self.params.get('generation_strategy', 'crem'),
                    pipeline_status=status
                )
                self._db.add(mol)
            except Exception as e:
                logger.exception(f'Pipeline错误: {e}')
                continue
        try:
            self._db.commit()
        except Exception as e:
            logger.exception(f'Pipeline错误: {e}')
            self._db.rollback()
    
    def _save_properties(self, molecule_id: int, desc: Dict, pass_filter: bool):
        """保存分子性质"""
        from ..models.database import MoleculeProperty
        try:
            prop = MoleculeProperty(
                molecule_id=molecule_id,
                mw=desc.get('mw'),
                clogp=desc.get('clogp'),
                tpsa=desc.get('tpsa'),
                hbd=desc.get('hbd'),
                hba=desc.get('hba'),
                rotb=desc.get('rotb'),
                sa_score=desc.get('sa_score'),
                qed=desc.get('qed'),
                pass_pains=desc.get('pass_pains'),
                pass_filters=pass_filter,
            )
            self._db.add(prop)
        except Exception as e:
            logger.exception(f'Pipeline错误: {e}')
            pass
    
    def _save_admet(self, molecule_id: int, admet: Dict):
        """保存ADMET预测结果"""
        from ..models.database import AdmetPrediction
        try:
            pred = AdmetPrediction(
                molecule_id=molecule_id,
                solubility=admet.get('solubility'),
                permeability=admet.get('permeability'),
                bbb=admet.get('bbb'),
                herg=admet.get('herg'),
                ames=admet.get('ames'),
                dili=admet.get('dili'),
                cyp_inhibition=admet.get('cyp_inhibition'),
                oral_bioavailability=admet.get('oral_bioavailability'),
                overall_score=admet.get('overall_score'),
            )
            self._db.add(pred)
        except Exception as e:
            logger.exception(f'Pipeline错误: {e}')
            pass
    
    def _save_synthesis(self, molecule_id: int, result: Dict):
        """保存合成分析结果"""
        from ..models.database import SynthesisRoute
        try:
            route = SynthesisRoute(
                molecule_id=molecule_id,
                route_json=json.dumps(result.get('route', {})),
                num_steps=result.get('num_steps'),
                estimated_cost=result.get('estimated_cost'),
                availability_score=result.get('availability_score'),
                status=result.get('status', 'pending')
            )
            self._db.add(route)
        except Exception as e:
            logger.exception(f'Pipeline错误: {e}')
            pass
    
    @classmethod
    def get_status(cls, job_id: str) -> Dict:
        """获取Pipeline运行状态"""
        with cls._lock:
            runner = cls._running_jobs.get(job_id)
        if runner is None:
            return {'status': 'not_found', 'error': 'Job ID not found'}
        return {
            'status': runner.status,
            'logs': runner.logs[-50:],
            'stats': runner.stats,
        }
    
    @classmethod
    def get_results(cls, job_id: str, db_session, top_n: int = 50) -> List[Dict]:
        """获取Pipeline最终Top分子"""
        with cls._lock:
            runner = cls._running_jobs.get(job_id)
        if runner is None or runner.status != 'completed':
            return []
        from ..models.database import GeneratedMolecule, MoleculeProperty, AdmetPrediction
        try:
            molecules = db_session.query(GeneratedMolecule).filter(
                GeneratedMolecule.project_id == runner.project_id,
                GeneratedMolecule.pipeline_status == 'synthesis_passed'
            ).limit(top_n).all()
            results = []
            for mol in molecules:
                prop = db_session.query(MoleculeProperty).filter(
                    MoleculeProperty.molecule_id == mol.id
                ).first()
                admet = db_session.query(AdmetPrediction).filter(
                    AdmetPrediction.molecule_id == mol.id
                ).first()
                results.append({
                    'id': mol.id,
                    'smiles': mol.smiles,
                    'properties': {
                        'mw': prop.mw if prop else None,
                        'clogp': prop.clogp if prop else None,
                        'tpsa': prop.tpsa if prop else None,
                        'qed': prop.qed if prop else None,
                        'sa_score': prop.sa_score if prop else None,
                        'similarity_score': prop.similarity_score if prop else None,
                    },
                    'admet': {
                        'overall_score': admet.overall_score if admet else None,
                        'herg': admet.herg if admet else None,
                        'ames': admet.ames if admet else None,
                        'dili': admet.dili if admet else None,
                    } if admet else None,
                    'svg_url': f'/static/molecules/{mol.id}.svg'
                })
            return results
        except Exception as e:
            logger.exception(f'Pipeline错误: {e}')
            return []
