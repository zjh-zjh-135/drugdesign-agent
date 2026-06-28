"""
Agent 工具注册 - 实现所有 Agent 可调用工具的函数
"""
import json
from datetime import datetime
from typing import Dict, Any, List
from .engine import ToolRegistry
from .memory import save_project_memory, get_project_summary

# 全局工具注册表
_registry = ToolRegistry()

def get_registry() -> ToolRegistry:
    """获取工具注册表实例"""
    return _registry

def register_tool(name: str, description: str, parameters: Dict):
    """装饰器：注册工具"""
    def decorator(func):
        _registry.register(name, func, {
            "description": description,
            "parameters": parameters
        })
        return func
    return decorator

# ========== 工具实现 ==========

def _get_db():
    """获取数据库 session（通过延迟导入避免循环依赖）"""
    from ...models.database import init_db
    Session = init_db()
    return Session()

def _get_project(db, project_id):
    """获取项目"""
    from ...models.database import Project
    return db.query(Project).filter(Project.id == project_id).first()

@register_tool(
    "create_project",
    "创建一个新的药物设计项目",
    {
        "name": {"type": "string", "description": "项目名称（可选，不提供则自动生成）", "required": False},
        "target_name": {"type": "string", "description": "靶点名称", "required": False},
        "target_pdb": {"type": "string", "description": "PDB ID", "required": False},
        "description": {"type": "string", "description": "项目描述", "required": False},
        "design_goal": {"type": "string", "description": "设计目标: hit_finding/lead_optimization/scaffold_hopping", "required": False}
    }
)
def create_project(name: str = None, target_name: str = None, target_pdb: str = None,
                   description: str = None, design_goal: str = "hit_finding") -> Dict:
    """创建新项目，并自动添加靶点对应的已知活性分子"""
    from ...models.database import Project, ActiveMolecule
    db = _get_db()
    try:
        # 自动项目名称：如果未提供，使用靶点名称 + 日期
        auto_name = name
        if not auto_name:
            base_name = target_name or "Project"
            auto_name = f"{base_name}_{datetime.now().strftime('%Y%m%d')}"

        project = Project(
            name=auto_name,
            target_name=target_name or auto_name,
            target_pdb=target_pdb,
            description=description,
            design_goal=design_goal
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        
        # 如果指定了靶点，自动添加该靶点的已知活性分子
        added_molecules = 0
        if target_name:
            from ...services.target_database import get_active_molecules_for_target
            candidates = get_active_molecules_for_target(target_name)
            if candidates:
                for cand in candidates:
                    am = ActiveMolecule(
                        project_id=project.id,
                        smiles=cand.get('smiles', ''),
                        name=cand.get('name', ''),
                        ic50=cand.get('ic50'),
                        activity_type='IC50',
                        source=cand.get('source', 'target_database')
                    )
                    db.add(am)
                db.commit()
                added_molecules = len(candidates)
                save_project_memory(db, project.id, "event", "active_molecules_added", {
                    "target_name": target_name,
                    "count": added_molecules,
                    "molecules": [c.get('name', '') for c in candidates]
                }, importance=4)
        
        # 保存记忆
        save_project_memory(db, project.id, "event", "project_created", {
            "name": auto_name,
            "target_name": target_name,
            "target_pdb": target_pdb,
            "design_goal": design_goal,
            "active_molecules_added": added_molecules,
            "timestamp": datetime.now().isoformat()
        }, importance=5)
        
        return {
            "success": True,
            "project_id": project.id,
            "name": project.name,
            "target_name": project.target_name,
            "target_pdb": project.target_pdb,
            "design_goal": project.design_goal,
            "active_molecules_added": added_molecules,
            "created_at": project.created_at.isoformat()
        }
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()

@register_tool(
    "list_projects",
    "列出所有项目",
    {}
)
def list_projects() -> List[Dict]:
    """列出所有项目"""
    from ...models.database import Project
    db = _get_db()
    try:
        projects = db.query(Project).order_by(Project.created_at.desc()).all()
        return [
            {
                "id": p.id,
                "name": p.name,
                "target_pdb": p.target_pdb,
                "design_goal": p.design_goal,
                "created_at": p.created_at.isoformat(),
                "molecule_count": len(p.generated_molecules) if p.generated_molecules else 0
            }
            for p in projects
        ]
    finally:
        db.close()

@register_tool(
    "run_pipeline",
    "在指定项目中运行分子生成 Pipeline",
    {
        "project_id": {"type": "integer", "description": "项目ID", "required": True},
        "num_molecules": {"type": "integer", "description": "生成数量", "required": False, "default": 500},
        "generation_strategy": {"type": "string", "description": "策略: crem/rnn/scaffold", "required": False, "default": "crem"},
        "similarity_threshold": {"type": "float", "description": "相似度阈值", "required": False, "default": 0.3},
        "admet_threshold": {"type": "float", "description": "ADMET阈值", "required": False, "default": 60},
        "availability_threshold": {"type": "float", "description": "合成可及性阈值", "required": False, "default": 0.35}
    }
)
def run_pipeline(project_id: int, num_molecules: int = 500,
                 generation_strategy: str = "crem", similarity_threshold: float = 0.3,
                 admet_threshold: float = 60, availability_threshold: float = 0.35) -> Dict:
    """运行 Pipeline"""
    db = _get_db()
    try:
        project = _get_project(db, project_id)
        if not project:
            return {"success": False, "error": f"项目 {project_id} 不存在"}
        
        # 获取项目过滤参数
        filter_params = project.filter_params or {}
        
        # 构建 Pipeline 参数
        params = {
            "num_molecules": num_molecules,
            "generation_strategy": generation_strategy,
            "similarity_threshold": similarity_threshold,
            "admet_threshold": admet_threshold,
            "top_n": min(num_molecules // 5, 200),
            "availability_threshold": availability_threshold,
            "filter_params": filter_params,
            "enable_failed_iteration": True
        }
        
        # 创建 PipelineRun 记录
        from ...models.database import PipelineRun
        pipeline_run = PipelineRun(
            project_id=project_id,
            status='pending',
            params_json=params
        )
        db.add(pipeline_run)
        db.commit()
        db.refresh(pipeline_run)
        
        # 保存记忆
        save_project_memory(db, project_id, "event", "pipeline_started", {
            "pipeline_run_id": pipeline_run.id,
            "strategy": generation_strategy,
            "num_molecules": num_molecules,
            "timestamp": datetime.now().isoformat()
        }, importance=4)
        
        # 在后台运行 Pipeline（异步）
        # 这里返回已创建的记录，实际运行在独立的线程/进程中
        from threading import Thread
        def _run_async():
            try:
                from ...models.database import init_db
                from ...services.pipeline import PipelineRunner
                SessionLocal = init_db()
                runner = PipelineRunner(SessionLocal, project_id, params, pipeline_run.id)
                runner.run()
            except Exception as e:
                print(f"Pipeline run error: {e}")
        
        thread = Thread(target=_run_async, daemon=True)
        thread.start()
        
        return {
            "success": True,
            "pipeline_run_id": pipeline_run.id,
            "strategy": generation_strategy,
            "num_molecules": num_molecules,
            "status": "running",
            "message": "Pipeline 已启动，请在项目页面查看进度"
        }
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()

@register_tool(
    "analyze_failures",
    "分析项目中失败分子的原因",
    {
        "project_id": {"type": "integer", "description": "项目ID", "required": True},
        "stage": {"type": "string", "description": "指定阶段(可选): filtering/structure_screening/admet/refinement/synthesis", "required": False}
    }
)
def analyze_failures(project_id: int, stage: str = None) -> Dict:
    """分析失败分子"""
    from ...models.database import GeneratedMolecule
    db = _get_db()
    try:
        query = db.query(GeneratedMolecule).filter(
            GeneratedMolecule.project_id == project_id,
            GeneratedMolecule.pipeline_status == 'failed'
        )
        if stage:
            query = query.filter(GeneratedMolecule.failure_stage == stage)
        
        failed_mols = query.all()
        total = len(failed_mols)
        
        if total == 0:
            return {"total_failed": 0, "reasons": {}, "message": "没有失败分子记录"}
        
        # 统计失败原因
        reasons = {}
        stage_counts = {}
        for mol in failed_mols:
            stage_name = mol.failure_stage or "unknown"
            stage_counts[stage_name] = stage_counts.get(stage_name, 0) + 1
            
            if mol.failure_reason:
                try:
                    reason_dict = json.loads(mol.failure_reason) if isinstance(mol.failure_reason, str) else mol.failure_reason
                    for key, val in reason_dict.items():
                        if val:
                            reasons[key] = reasons.get(key, 0) + 1
                except:
                    pass
        
        # 获取建议
        suggestions = _generate_failure_suggestions(stage_counts, reasons)
        
        # 保存记忆
        save_project_memory(db, project_id, "insight", "failure_analysis", {
            "total_failed": total,
            "stage_counts": stage_counts,
            "reasons": reasons,
            "suggestions": suggestions,
            "timestamp": datetime.now().isoformat()
        }, importance=7)
        
        return {
            "total_failed": total,
            "stage_counts": stage_counts,
            "reasons": reasons,
            "suggestions": suggestions
        }
    finally:
        db.close()

def _generate_failure_suggestions(stage_counts: Dict, reasons: Dict) -> List[str]:
    """基于失败模式生成建议"""
    suggestions = []
    
    # 根据阶段分析
    top_stage = max(stage_counts, key=stage_counts.get) if stage_counts else None
    if top_stage:
        stage_suggestions = {
            "filtering": [
                "大量分子在过滤阶段失败，建议放宽分子量或 LogP 限制",
                "考虑使用更宽松的初始筛选条件",
                "尝试调整 TPSA 或 HBD/HBA 阈值"
            ],
            "structure_screening": [
                "结构筛选失败较多，建议检查靶点结构是否正确",
                "考虑使用不同的对接算法或搜索参数",
                "检查蛋白准备是否有问题"
            ],
            "admet": [
                "ADMET 失败较多，建议适当降低 ADMET 阈值",
                "考虑使用更保守的成药性标准",
                "分析失败分子的 ADMET 特征以优化生成策略"
            ],
            "refinement": [
                "FEP 精筛失败较多，建议增加初始样本数量",
                "检查力场参数设置是否正确",
                "考虑使用更短的模拟时间"
            ],
            "synthesis": [
                "合成可行性评估失败较多，建议调整合成路径算法",
                "考虑使用不同的逆合成工具",
                "放宽合成难度阈值"
            ]
        }
        suggestions.extend(stage_suggestions.get(top_stage, ["分析失败模式并调整策略"]))
    
    # 根据具体原因
    if 'SA_score' in reasons or 'sa_score' in reasons:
        suggestions.append("合成可及性(SA Score)是主要失败原因，建议放宽 SA Score 阈值或调整生成策略")
    if 'MW' in reasons or 'mw' in reasons:
        suggestions.append("分子量超限是主要问题，建议调整分子量范围")
    if 'LogP' in reasons or 'logP' in reasons or 'clogp' in reasons:
        suggestions.append("LogP 超出范围，建议调整亲脂性阈值")
    if 'PAINS' in reasons or 'pains' in reasons:
        suggestions.append("部分分子触发 PAINS 警报，这是正常的筛选结果")
    
    return suggestions[:5]  # 最多5条建议

@register_tool(
    "adjust_filters",
    "调整项目的过滤参数",
    {
        "project_id": {"type": "integer", "description": "项目ID", "required": True},
        "mw_min": {"type": "float", "description": "最小分子量", "required": False},
        "mw_max": {"type": "float", "description": "最大分子量", "required": False},
        "clogp_min": {"type": "float", "description": "最小LogP", "required": False},
        "clogp_max": {"type": "float", "description": "最大LogP", "required": False},
        "tpsa_min": {"type": "float", "description": "最小TPSA", "required": False},
        "tpsa_max": {"type": "float", "description": "最大TPSA", "required": False},
        "hbd_max": {"type": "integer", "description": "最大氢键供体", "required": False},
        "hba_max": {"type": "integer", "description": "最大氢键受体", "required": False},
        "rotb_max": {"type": "integer", "description": "最大可旋转键", "required": False},
        "sa_score_max": {"type": "float", "description": "最大SA Score", "required": False}
    }
)
def adjust_filters(project_id: int, **kwargs) -> Dict:
    """调整过滤参数"""
    db = _get_db()
    try:
        project = _get_project(db, project_id)
        if not project:
            return {"success": False, "error": "项目不存在"}
        
        current = dict(project.filter_params or {})
        updated = {}
        
        valid_keys = ['mw_min', 'mw_max', 'clogp_min', 'clogp_max', 
                     'tpsa_min', 'tpsa_max', 'hbd_max', 'hba_max', 
                     'rotb_max', 'sa_score_max']
        
        for key in valid_keys:
            if key in kwargs and kwargs[key] is not None:
                current[key] = kwargs[key]
                updated[key] = kwargs[key]
        
        project.filter_params = current
        db.commit()
        
        # 保存记忆
        save_project_memory(db, project_id, "decision", "filter_params_updated", {
            "updated": updated,
            "current": current,
            "timestamp": datetime.now().isoformat()
        }, importance=6)
        
        return {"success": True, "updated": updated, "current": current}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()

@register_tool(
    "get_project_status",
    "获取项目当前状态和统计",
    {
        "project_id": {"type": "integer", "description": "项目ID", "required": True}
    }
)
def get_project_status(project_id: int) -> Dict:
    """获取项目状态"""
    from ...models.database import Project, PipelineRun, GeneratedMolecule
    db = _get_db()
    try:
        project = _get_project(db, project_id)
        if not project:
            return {"success": False, "error": "项目不存在"}
        
        # 统计
        total = db.query(GeneratedMolecule).filter(
            GeneratedMolecule.project_id == project_id
        ).count()
        
        failed = db.query(GeneratedMolecule).filter(
            GeneratedMolecule.project_id == project_id,
            GeneratedMolecule.pipeline_status == 'failed'
        ).count()
        
        passed = db.query(GeneratedMolecule).filter(
            GeneratedMolecule.project_id == project_id,
            GeneratedMolecule.pipeline_status == 'synthesis_passed'
        ).count()
        
        # 各阶段统计
        stages = {}
        for status in ['generated', 'filtered', 'structure_screened', 'admet_passed', 'refined', 'synthesis_passed', 'failed']:
            count = db.query(GeneratedMolecule).filter(
                GeneratedMolecule.project_id == project_id,
                GeneratedMolecule.pipeline_status == status
            ).count()
            stages[status] = count
        
        # 最新运行
        latest_run = db.query(PipelineRun).filter(
            PipelineRun.project_id == project_id
        ).order_by(PipelineRun.start_time.desc()).first()
        
        return {
            "success": True,
            "project_id": project_id,
            "project_name": project.name,
            "status": "running" if any(s in stages and stages[s] > 0 for s in ['generated', 'filtered']) else "idle",
            "total_molecules": total,
            "failed": failed,
            "passed": passed,
            "stages": stages,
            "latest_pipeline": {
                "id": latest_run.id,
                "status": latest_run.status,
                "start_time": latest_run.start_time.isoformat() if latest_run.start_time else None
            } if latest_run else None
        }
    finally:
        db.close()

@register_tool(
    "compare_molecules",
    "对比多个分子的性质",
    {
        "smiles_list": {"type": "array", "description": "SMILES 列表", "required": True}
    }
)
def compare_molecules(smiles_list: List[str]) -> Dict:
    """对比分子"""
    try:
        from rdkit import Chem
        from rdkit.Chem import Descriptors, Crippen, rdMolDescriptors
        
        results = []
        for smi in smiles_list:
            mol = Chem.MolFromSmiles(smi)
            if not mol:
                results.append({"smiles": smi, "valid": False})
                continue
            
            results.append({
                "smiles": smi,
                "valid": True,
                "mw": round(Descriptors.MolWt(mol), 2),
                "logp": round(Crippen.MolLogP(mol), 2),
                "tpsa": round(rdMolDescriptors.CalcTPSA(mol), 2),
                "hbd": rdMolDescriptors.CalcNumHBD(mol),
                "hba": rdMolDescriptors.CalcNumHBA(mol),
                "rotb": rdMolDescriptors.CalcNumRotatableBonds(mol),
                "qed": round(Chem.QED.qed(mol), 3)
            })
        
        return {"success": True, "molecules": results}
    except Exception as e:
        return {"success": False, "error": str(e)}

@register_tool(
    "suggest_next_step",
    "根据项目当前状态建议下一步操作",
    {
        "project_id": {"type": "integer", "description": "项目ID", "required": True},
        "current_stage": {"type": "string", "description": "当前阶段", "required": False}
    }
)
def suggest_next_step(project_id: int, current_stage: str = "unknown") -> Dict:
    """建议下一步"""
    db = _get_db()
    try:
        summary = get_project_summary(db, project_id)
        
        total = summary.get("total_molecules", 0)
        failed = summary.get("failed_molecules", 0)
        passed = summary.get("passed_molecules", 0)
        latest_status = summary.get("latest_pipeline_status", "idle")
        
        suggestions = []
        
        if latest_status == "running":
            suggestions.append("Pipeline 正在运行中，请等待完成后再进行下一步操作")
        elif total == 0:
            suggestions.append("项目尚未运行 Pipeline，建议先运行分子生成")
        elif failed > total * 0.5:
            suggestions.append(f"失败率较高 ({failed}/{total})，建议分析失败原因并调整过滤参数")
            suggestions.append("运行失败分析工具查看详细报告")
        elif passed < 10 and total > 0:
            suggestions.append("通过分子数量较少，建议放宽筛选条件或增加生成数量")
        elif passed >= 10:
            suggestions.append("已有足够的候选分子，建议进行分子对接或ADMET分析")
            suggestions.append("考虑使用分子对比工具评估 Top 候选")
        
        # 保存记忆
        save_project_memory(db, project_id, "insight", "next_step_suggestion", {
            "suggestions": suggestions,
            "context": summary,
            "timestamp": datetime.now().isoformat()
        }, importance=3)
        
        return {
            "success": True,
            "suggestions": suggestions,
            "context": summary
        }
    finally:
        db.close()

@register_tool(
    "get_failed_molecules",
    "获取失败分子列表",
    {
        "project_id": {"type": "integer", "description": "项目ID", "required": True},
        "stage": {"type": "string", "description": "失败阶段", "required": False},
        "limit": {"type": "integer", "description": "数量限制", "required": False, "default": 50}
    }
)
def get_failed_molecules(project_id: int, stage: str = None, limit: int = 50) -> Dict:
    """获取失败分子"""
    from ...models.database import GeneratedMolecule
    db = _get_db()
    try:
        query = db.query(GeneratedMolecule).filter(
            GeneratedMolecule.project_id == project_id,
            GeneratedMolecule.pipeline_status == 'failed'
        )
        if stage:
            query = query.filter(GeneratedMolecule.failure_stage == stage)
        
        mols = query.order_by(GeneratedMolecule.failed_at.desc()).limit(limit).all()
        
        return {
            "success": True,
            "count": len(mols),
            "molecules": [
                {
                    "smiles": m.smiles,
                    "stage": m.failure_stage,
                    "reason": m.failure_reason,
                    "failed_at": m.failed_at.isoformat() if m.failed_at else None
                }
                for m in mols
            ]
        }
    finally:
        db.close()


@register_tool(
    "get_top_molecules",
    "获取项目中得分最高的候选分子（已通过合成筛选）",
    {
        "project_id": {"type": "integer", "description": "项目ID", "required": True},
        "limit": {"type": "integer", "description": "返回数量限制", "required": False, "default": 10}
    }
)
def get_top_molecules(project_id: int, limit: int = 10) -> Dict:
    """获取 Top 候选分子（已通过合成筛选）"""
    from ...models.database import GeneratedMolecule, MoleculeProperty, AdmetPrediction
    db = _get_db()
    try:
        # 查询已通过合成筛选的分子，关联属性和ADMET
        query = (
            db.query(GeneratedMolecule, MoleculeProperty, AdmetPrediction)
            .outerjoin(MoleculeProperty, MoleculeProperty.molecule_id == GeneratedMolecule.id)
            .outerjoin(AdmetPrediction, AdmetPrediction.molecule_id == GeneratedMolecule.id)
            .filter(
                GeneratedMolecule.project_id == project_id,
                GeneratedMolecule.pipeline_status == 'synthesis_passed'
            )
        )
        
        results = query.all()
        if not results:
            return {
                "success": True,
                "count": 0,
                "molecules": [],
                "message": "暂无通过合成筛选的分子，Pipeline 可能还在运行中。"
            }
        
        # 计算综合得分并排序
        scored_mols = []
        for mol, prop, admet in results:
            # 综合得分：对接分数（越低越好，取负）+ ADMET分数 + QED
            docking = (prop.docking_score if prop and prop.docking_score is not None else -5.0)
            admet_score = (admet.overall_score if admet and admet.overall_score is not None else 50.0)
            qed = (prop.qed if prop and prop.qed is not None else 0.5)
            # 综合得分：高 = 好
            composite_score = (-docking * 10) + (admet_score * 0.5) + (qed * 20)
            
            scored_mols.append({
                "molecule": mol,
                "properties": prop,
                "admet": admet,
                "score": round(composite_score, 2)
            })
        
        # 按综合得分降序排列
        scored_mols.sort(key=lambda x: x["score"], reverse=True)
        top = scored_mols[:limit]
        
        return {
            "success": True,
            "count": len(top),
            "molecules": [
                {
                    "id": item["molecule"].id,
                    "smiles": item["molecule"].smiles,
                    "score": item["score"],
                    "docking_score": round(item["properties"].docking_score, 2) if item["properties"] and item["properties"].docking_score is not None else None,
                    "admet_score": round(item["admet"].overall_score, 2) if item["admet"] and item["admet"].overall_score is not None else None,
                    "qed": round(item["properties"].qed, 3) if item["properties"] and item["properties"].qed is not None else None,
                    "mw": round(item["properties"].mw, 2) if item["properties"] and item["properties"].mw is not None else None,
                    "logp": round(item["properties"].clogp, 2) if item["properties"] and item["properties"].clogp is not None else None,
                    "tpsa": round(item["properties"].tpsa, 2) if item["properties"] and item["properties"].tpsa is not None else None,
                    "hbd": item["properties"].hbd if item["properties"] and item["properties"].hbd is not None else None,
                    "hba": item["properties"].hba if item["properties"] and item["properties"].hba is not None else None,
                    "sa_score": round(item["properties"].sa_score, 2) if item["properties"] and item["properties"].sa_score is not None else None,
                    "generation_strategy": item["molecule"].generation_strategy,
                    "created_at": item["molecule"].created_at.isoformat() if item["molecule"].created_at else None,
                }
                for item in top
            ]
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        db.close()


@register_tool(
    "format_top_molecules",
    "获取项目中 Top 候选分子的格式化报告（包含完整分子数据、性质分析和下一步建议）",
    {
        "project_id": {"type": "integer", "description": "项目ID", "required": True},
        "limit": {"type": "integer", "description": "返回数量限制", "required": False, "default": 3}
    }
)
def format_top_molecules(project_id: int, limit: int = 3) -> Dict:
    """获取 Top 候选分子的格式化报告"""
    result = get_top_molecules(project_id, limit=limit)
    
    if not result.get("success"):
        return result
    
    top_molecules = result.get("molecules", [])
    count = result.get("count", 0)
    
    if not top_molecules:
        return {
            "success": True,
            "count": 0,
            "molecules": [],
            "final_report": "暂无通过合成筛选的候选分子。Pipeline 可能还在运行中，或没有分子通过所有筛选阶段。",
        }
    
    # 生成 Markdown 报告
    lines = [
        "",
        f"## Top {count} 候选分子详细报告",
        "",
    ]
    
    for i, mol in enumerate(top_molecules, 1):
        score = mol.get("score") if mol.get("score") is not None else "N/A"
        docking = mol.get("docking_score") if mol.get("docking_score") is not None else "待计算"
        admet = mol.get("admet_score") if mol.get("admet_score") is not None else "N/A"
        qed = mol.get("qed") if mol.get("qed") is not None else "N/A"
        mw = mol.get("mw") if mol.get("mw") is not None else "N/A"
        logp = mol.get("logp") if mol.get("logp") is not None else "N/A"
        tpsa = mol.get("tpsa") if mol.get("tpsa") is not None else "N/A"
        hbd = mol.get("hbd") if mol.get("hbd") is not None else "N/A"
        hba = mol.get("hba") if mol.get("hba") is not None else "N/A"
        sa = mol.get("sa_score") if mol.get("sa_score") is not None else "N/A"
        smiles = mol.get("smiles") if mol.get("smiles") is not None else "N/A"
        
        rank_emoji = {1: "1st", 2: "2nd", 3: "3rd"}.get(i, f"#{i}")
        
        lines.append(f"### {rank_emoji} 候选分子 #{i}（综合得分：{score}）")
        lines.append("")
        lines.append(f"- **SMILES**：`{smiles}`")
        lines.append(f"- **分子量 (MW)**：{mw} | **LogP**：{logp} | **QED**：{qed}")
        lines.append(f"- **对接分数**：{docking} | **ADMET 得分**：{admet} | **SA Score**：{sa}")
        lines.append(f"- **TPSA**：{tpsa} | **HBD**：{hbd} | **HBA**：{hba}")
        
        evaluations = []
        if qed is not None and qed != "N/A" and qed > 0.7:
            evaluations.append("QED 优秀")
        if admet is not None and admet != "N/A" and admet > 70:
            evaluations.append("ADMET 良好")
        if docking is not None and docking != "N/A" and docking < -7:
            evaluations.append("对接强")
        if sa is not None and sa != "N/A" and sa < 3.5:
            evaluations.append("合成可及")
        
        if evaluations:
            lines.append(f"- **亮点**：{'、'.join(evaluations)}")
        
        lines.append("")
    
    # 下一步建议
    lines.append("**下一步建议**")
    lines.append("")
    
    if top_molecules:
        top1 = top_molecules[0]
        top1_qed = top1.get("qed")
        top1_admet = top1.get("admet_score")
        top1_sa = top1.get("sa_score")
        
        suggestions = []
        if top1_qed is not None and top1_qed > 0.7:
            suggestions.append(f"候选分子 #1 的 QED（{top1_qed}）表现优秀，药物相似性高，建议优先合成验证")
        if top1_admet is not None and top1_admet > 70:
            suggestions.append(f"ADMET 得分（{top1_admet}）良好，药代动力学风险可控")
        if top1_sa is not None and top1_sa > 4:
            suggestions.append(f"注意：SA Score（{top1_sa}）偏高，合成难度可能较大，建议评估合成路线")
        
        if not suggestions:
            suggestions.append("建议对 Top 候选分子进行 FEP 精修和合成路线评估")
        
        for i, sug in enumerate(suggestions, 1):
            lines.append(f"{i}. {sug}")
        lines.append("")
    
    return {
        "success": True,
        "count": count,
        "molecules": top_molecules,
        "final_report": "\n".join(lines),
    }


@register_tool(
    "get_pipeline_progress",
    "查询指定项目的最新 Pipeline 运行进度",
    {
        "project_id": {"type": "integer", "description": "项目ID", "required": True}
    }
)
def get_pipeline_progress(project_id: int) -> Dict:
    """获取 Pipeline 最新运行状态"""
    from ...models.database import PipelineRun, Project
    db = _get_db()
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            return {"success": False, "error": "项目不存在"}
        
        latest_run = db.query(PipelineRun).filter(
            PipelineRun.project_id == project_id
        ).order_by(PipelineRun.start_time.desc()).first()
        
        if not latest_run:
            return {
                "success": True,
                "status": "no_run",
                "message": "该项目尚未运行过 Pipeline"
            }
        
        # 计算运行时长
        duration = None
        if latest_run.end_time and latest_run.start_time:
            duration = (latest_run.end_time - latest_run.start_time).total_seconds()
        elif latest_run.start_time:
            duration = (datetime.now() - latest_run.start_time).total_seconds()
        
        return {
            "success": True,
            "pipeline_run_id": latest_run.id,
            "status": latest_run.status,
            "num_generated": latest_run.num_generated,
            "num_filtered": latest_run.num_filtered,
            "num_passed": latest_run.num_passed,
            "num_failed": latest_run.num_failed,
            "start_time": latest_run.start_time.isoformat() if latest_run.start_time else None,
            "end_time": latest_run.end_time.isoformat() if latest_run.end_time else None,
            "duration_seconds": round(duration, 1) if duration else None,
            "params": latest_run.params_json or {},
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        db.close()


@register_tool(
    "wait_for_pipeline",
    "等待指定项目的 Pipeline 运行完成（阻塞轮询，最多300秒）",
    {
        "project_id": {"type": "integer", "description": "项目ID", "required": True},
        "max_wait_seconds": {"type": "integer", "description": "最大等待秒数（默认300）", "required": False, "default": 300},
        "poll_interval": {"type": "integer", "description": "轮询间隔秒数（默认3）", "required": False, "default": 3}
    }
)
def wait_for_pipeline(project_id: int, max_wait_seconds: int = 300, poll_interval: int = 3) -> Dict:
    """
    阻塞轮询等待 Pipeline 完成。
    如果 Pipeline 已完成，立即返回结果。
    如果 Pipeline 正在运行，持续轮询直到完成或超时。
    """
    import time
    from ...models.database import PipelineRun, Project, GeneratedMolecule
    db = _get_db()
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            return {"success": False, "error": "项目不存在"}
        
        # 获取最新 PipelineRun
        latest_run = db.query(PipelineRun).filter(
            PipelineRun.project_id == project_id
        ).order_by(PipelineRun.start_time.desc()).first()
        
        if not latest_run:
            return {"success": False, "error": "该项目尚未运行过 Pipeline"}
        
        # 如果已经完成，直接返回
        if latest_run.status in ("completed", "failed"):
            return _build_wait_result(db, latest_run, project_id, elapsed=0, completed=True)
        
        # 轮询等待（包括 pending 状态，因为 Pipeline 启动后可能尚未更新为 running）
        elapsed = 0
        check_interval = min(poll_interval, 3)
        while latest_run.status in ("pending", "running") and elapsed < max_wait_seconds:
            time.sleep(check_interval)
            elapsed += check_interval
            db.refresh(latest_run)
            
            # 每 10 秒打印一次日志（便于调试）
            if elapsed % 10 == 0:
                print(f"[wait_for_pipeline] project={project_id} elapsed={elapsed}s status={latest_run.status}")
        
        completed = latest_run.status in ("completed", "failed")
        return _build_wait_result(db, latest_run, project_id, elapsed, completed)
        
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        db.close()


def _build_wait_result(db, pipeline_run, project_id, elapsed, completed):
    """构建 wait_for_pipeline 返回结果"""
    from ...models.database import GeneratedMolecule
    
    # 统计各阶段分子数
    stage_counts = {}
    for status in ["generated", "filtered", "structure_screened", "admet_passed", "refined", "synthesis_passed", "failed"]:
        count = db.query(GeneratedMolecule).filter(
            GeneratedMolecule.project_id == project_id,
            GeneratedMolecule.pipeline_status == status
        ).count()
        stage_counts[status] = count
    
    result = {
        "success": True,
        "completed": completed,
        "status": pipeline_run.status,
        "pipeline_run_id": pipeline_run.id,
        "elapsed_seconds": elapsed,
        "num_generated": pipeline_run.num_generated,
        "num_filtered": pipeline_run.num_filtered,
        "num_passed": pipeline_run.num_passed,
        "num_failed": pipeline_run.num_failed,
        "stage_counts": stage_counts,
        "message": "Pipeline 运行完成" if completed else f"Pipeline 仍在运行中（已等待 {elapsed} 秒）",
    }
    
    # 如果完成，给出结果摘要
    if completed and pipeline_run.status == "completed":
        if pipeline_run.num_passed and pipeline_run.num_passed > 0:
            result["summary"] = f"Pipeline 成功完成。共生成 {pipeline_run.num_generated} 个分子，通过 {pipeline_run.num_passed} 个，失败 {pipeline_run.num_failed} 个。"
        else:
            result["summary"] = f"Pipeline 完成，但没有分子通过全部筛选。生成 {pipeline_run.num_generated} 个，失败 {pipeline_run.num_failed} 个。建议分析失败原因并调整参数。"
    elif pipeline_run.status == "failed":
        result["summary"] = f"Pipeline 运行失败。已生成 {pipeline_run.num_generated} 个分子。"
    
    return result


# ========== 端到端全流程工具 ==========

@register_tool(
    "run_full_pipeline",
    "端到端运行药物发现全流程：从靶点名称到候选分子。自动获取PDB ID、创建项目、添加已知活性分子、运行Pipeline、等待完成并返回Top候选分子。适合一键式完成从靶点到候选分子的完整流程。",
    {
        "target_name": {"type": "string", "description": "靶点名称（如HER2、EGFR、VEGFR2、AKT1、BRAF等）", "required": True},
        "num_molecules": {"type": "integer", "description": "生成分子数量，默认1000", "required": False, "default": 1000},
        "similarity_threshold": {"type": "number", "description": "相似度阈值（0.0-1.0），默认0.3", "required": False, "default": 0.3},
        "admet_threshold": {"type": "number", "description": "ADMET综合阈值（0-100），默认60", "required": False, "default": 60},
        "availability_threshold": {"type": "number", "description": "合成可及性阈值（0.0-1.0），默认0.35", "required": False, "default": 0.35},
        "limit": {"type": "integer", "description": "返回Top候选分子数量，默认3", "required": False, "default": 3}
    }
)
def run_full_pipeline(target_name: str, num_molecules: int = 1000, 
                       similarity_threshold: float = 0.3, admet_threshold: float = 60,
                       availability_threshold: float = 0.35, limit: int = 3) -> Dict:
    """
    端到端全流程：靶点名称 -> 获取PDB ID -> 创建项目（自动添加活性分子） -> 运行Pipeline -> 等待完成 -> 获取Top分子
    """
    from ...services.target_database import get_pdb_id_for_target, get_active_molecules_for_target
    
    print(f"[run_full_pipeline] 开始全流程：target={target_name}, num={num_molecules}, limit={limit}")
    
    # 1. 获取 PDB ID
    pdb_id = get_pdb_id_for_target(target_name)
    if not pdb_id:
        pdb_id = target_name
        print(f"[run_full_pipeline] 未在数据库中找到 {target_name} 的 PDB ID，使用名称本身")
    else:
        print(f"[run_full_pipeline] 靶点 {target_name} 对应 PDB ID: {pdb_id}")
    
    # 2. 创建项目（自动添加已知活性分子）
    project_result = create_project(
        name=f"{target_name}_auto_{datetime.now().strftime('%m%d%H%M')}",
        target_name=target_name,
        target_pdb=pdb_id,
        description=f"自动全流程项目 - 靶点: {target_name}",
        design_goal="hit_finding"
    )
    
    if not project_result.get("success"):
        return {
            "success": False,
            "stage": "project_creation",
            "error": project_result.get("error", "项目创建失败")
        }
    
    project_id = project_result["project_id"]
    active_count = project_result.get("active_molecules_added", 0)
    print(f"[run_full_pipeline] 项目创建成功: ID={project_id}, 活性分子={active_count}个")
    
    # 3. 运行 Pipeline（后台线程运行，非阻塞）
    pipeline_result = run_pipeline(
        project_id=project_id,
        num_molecules=num_molecules,
        generation_strategy="crem",
        similarity_threshold=similarity_threshold,
        admet_threshold=admet_threshold,
        availability_threshold=availability_threshold
    )
    
    if not pipeline_result.get("success"):
        return {
            "success": False,
            "stage": "pipeline_run",
            "project_id": project_id,
            "error": pipeline_result.get("error", "Pipeline启动失败")
        }
    
    pipeline_run_id = pipeline_result.get("pipeline_run_id")
    print(f"[run_full_pipeline] Pipeline已启动: run_id={pipeline_run_id}")
    
    # 4. 等待 Pipeline 完成（阻塞轮询，最多300秒）
    wait_result = wait_for_pipeline(
        project_id=project_id,
        max_wait_seconds=300,
        poll_interval=3
    )
    
    if not wait_result.get("success"):
        return {
            "success": False,
            "stage": "pipeline_wait",
            "project_id": project_id,
            "error": wait_result.get("error", "等待Pipeline失败")
        }
    
    # 5. 获取 Top 候选分子
    top_result = get_top_molecules(project_id, limit=limit)
    
    top_molecules = top_result.get("molecules", []) if top_result.get("success") else []
    
    # 6. 整合返回完整结果
    final_result = {
        "success": True,
        "project_id": project_id,
        "project_name": project_result.get("name", ""),
        "target_name": target_name,
        "target_pdb": pdb_id,
        "active_molecules_added": active_count,
        "pipeline_run_id": pipeline_run_id,
        "pipeline_status": wait_result.get("status", "unknown"),
        "elapsed_seconds": wait_result.get("elapsed_seconds", 0),
        "num_generated": wait_result.get("num_generated", 0),
        "num_passed": wait_result.get("num_passed", 0),
        "num_failed": wait_result.get("num_failed", 0),
        "stage_counts": wait_result.get("stage_counts", {}),
        "top_molecules": top_molecules,
        "message": (
            f"全流程完成。项目ID={project_id}，生成{wait_result.get('num_generated', 0)}个分子，"
            f"通过{wait_result.get('num_passed', 0)}个，获得Top {len(top_molecules)}候选分子。"
        )
    }
    
    # 如果 pipeline 失败，标记成功但给出警告
    if wait_result.get("status") == "failed":
        final_result["success"] = False
        final_result["stage"] = "pipeline_failed"
        final_result["message"] = f"Pipeline运行失败。已生成{wait_result.get('num_generated', 0)}个分子，但筛选未通过。"
    
    # 生成 Markdown 格式化报告
    final_result["final_report"] = _build_full_pipeline_report(final_result)

    return final_result


def _build_full_pipeline_report(obs):
    """生成 run_full_pipeline 的 Markdown 报告"""
    if not obs.get("success"):
        return f"**全流程执行失败**：{obs.get('error', '未知错误')}"
    
    target_name = obs.get("target_name", "N/A")
    target_pdb = obs.get("target_pdb", "N/A")
    project_name = obs.get("project_name", "N/A")
    project_id = obs.get("project_id", "N/A")
    active_count = obs.get("active_molecules_added", 0)
    
    num_generated = obs.get("num_generated", 0)
    num_passed = obs.get("num_passed", 0)
    num_failed = obs.get("num_failed", 0)
    elapsed = obs.get("elapsed_seconds", 0)
    status = obs.get("pipeline_status", "unknown")
    
    top_molecules = obs.get("top_molecules", [])
    
    lines = [
        "",
        f"## {target_name} 全流程完成 — 候选分子报告",
        "",
        f"**项目信息**：ID={project_id} | 靶点：**{target_name}** | PDB：**{target_pdb}** | 项目名称：{project_name}",
        "",
        "**Pipeline 执行结果**",
        "",
        f"| 指标 | 数值 |",
        f"|------|------|",
        f"| 生成总数 | {num_generated} 个 |",
        f"| 通过筛选 | {num_passed} 个 |",
        f"| 失败 | {num_failed} 个 |",
        f"| 执行耗时 | {elapsed} 秒 |",
        f"| 状态 | {'完成' if status == 'completed' else status} |",
        "",
    ]
    
    if active_count > 0:
        lines.append(f"**已知活性分子**：已自动添加 {active_count} 个作为参考")
        lines.append("")
    
    if top_molecules:
        lines.append(f"**Top {len(top_molecules)} 候选分子**")
        lines.append("")
        
        for i, mol in enumerate(top_molecules, 1):
            score = mol.get("score") if mol.get("score") is not None else "N/A"
            docking = mol.get("docking_score") if mol.get("docking_score") is not None else "待计算"
            admet = mol.get("admet_score") if mol.get("admet_score") is not None else "N/A"
            qed = mol.get("qed") if mol.get("qed") is not None else "N/A"
            mw = mol.get("mw") if mol.get("mw") is not None else "N/A"
            logp = mol.get("logp") if mol.get("logp") is not None else "N/A"
            tpsa = mol.get("tpsa") if mol.get("tpsa") is not None else "N/A"
            hbd = mol.get("hbd") if mol.get("hbd") is not None else "N/A"
            hba = mol.get("hba") if mol.get("hba") is not None else "N/A"
            sa = mol.get("sa_score") if mol.get("sa_score") is not None else "N/A"
            smiles = mol.get("smiles") if mol.get("smiles") is not None else "N/A"
            
            rank_emoji = {1: "1st", 2: "2nd", 3: "3rd"}.get(i, f"#{i}")
            
            lines.append(f"### {rank_emoji} 候选分子 #{i}（综合得分：{score}）")
            lines.append("")
            lines.append(f"- **SMILES**：`{smiles}`")
            lines.append(f"- **分子量 (MW)**：{mw} | **LogP**：{logp} | **QED**：{qed}")
            lines.append(f"- **对接分数**：{docking} | **ADMET 得分**：{admet} | **SA Score**：{sa}")
            lines.append(f"- **TPSA**：{tpsa} | **HBD**：{hbd} | **HBA**：{hba}")
            
            evaluations = []
            if qed is not None and qed != "N/A" and qed > 0.7:
                evaluations.append("QED 优秀")
            if admet is not None and admet != "N/A" and admet > 70:
                evaluations.append("ADMET 良好")
            if docking is not None and docking != "N/A" and docking < -7:
                evaluations.append("对接强")
            if sa is not None and sa != "N/A" and sa < 3.5:
                evaluations.append("合成可及")
            
            if evaluations:
                lines.append(f'- **亮点**：{", ".join(evaluations)}')
            
            lines.append("")
        
        lines.append("**下一步建议**")
        lines.append("")
        
        if top_molecules:
            top1 = top_molecules[0]
            top1_qed = top1.get("qed")
            top1_admet = top1.get("admet_score")
            top1_sa = top1.get("sa_score")
            
            suggestions = []
            if top1_qed is not None and top1_qed > 0.7:
                suggestions.append(f"候选分子 #1 的 QED（{top1_qed}）表现优秀，建议优先合成验证")
            if top1_admet is not None and top1_admet > 70:
                suggestions.append(f"ADMET 得分（{top1_admet}）良好，药代动力学风险可控")
            if top1_sa is not None and top1_sa > 4:
                suggestions.append(f"注意：SA Score（{top1_sa}）偏高，合成难度可能较大，建议评估合成路线")
            
            if not suggestions:
                suggestions.append("建议对 Top 候选分子进行 FEP 精修和合成路线评估")
            
            for i, sug in enumerate(suggestions, 1):
                lines.append(f"{i}. {sug}")
            lines.append("")
    else:
        lines.append("**暂无通过合成筛选的候选分子**")
        lines.append("")
        if num_failed > 0:
            lines.append(f"- 所有 {num_failed} 个分子在筛选中失败，建议分析失败原因并调整参数")
            lines.append("- 可尝试：降低 ADMET 阈值、放宽相似度限制、增加生成分子数量")
        lines.append("")
    
    return "\n".join(lines)


# ========== 单分子 ADMET 分析工具（直接分析，不依赖 Pipeline）==========

@register_tool(
    "analyze_single_molecule_admet",
    "直接对单个 SMILES 分子进行完整的 ADMET 五分类分析（吸收、分布、代谢、排泄、毒性），无需运行 Pipeline。返回分子量、LogP、QED、hERG、AMES 等所有关键药代动力学和毒性指标。",
    {
        "smiles": {"type": "string", "description": "分子的 SMILES 字符串", "required": True}
    }
)
def analyze_single_molecule_admet(smiles: str) -> Dict:
    """直接对单个 SMILES 进行 ADMET 分析，不依赖项目或 Pipeline"""
    from ..admet import AdmetPredictor
    from ..utils import validate_smiles, canonicalize_smiles
    
    # 验证 SMILES
    if not validate_smiles(smiles):
        return {
            "success": False,
            "error": f"无效的 SMILES: {smiles}",
            "message": "请提供有效的 SMILES 字符串。"
        }
    
    try:
        # 直接调用 ADMET 预测器
        result = AdmetPredictor.predict(smiles)
        
        # 提取基础理化性质（ADMET-AI 不返回，需要额外计算）
        from rdkit import Chem
        from rdkit.Chem import Descriptors, rdMolDescriptors
        mol = Chem.MolFromSmiles(smiles)
        if mol:
            mw = round(Descriptors.MolWt(mol), 2)
            logp = round(Descriptors.MolLogP(mol), 2)
            tpsa = round(Descriptors.TPSA(mol), 2)
            hbd = rdMolDescriptors.CalcNumHBD(mol)
            hba = rdMolDescriptors.CalcNumHBA(mol)
            rotb = rdMolDescriptors.CalcNumRotatableBonds(mol)
            qed_val = round(Descriptors.qed(mol), 3)
        else:
            mw = logp = tpsa = hbd = hba = rotb = qed_val = None
        
        # 从嵌套结构中提取关键指标
        absorption = result.get('absorption', {})
        distribution = result.get('distribution', {})
        metabolism = result.get('metabolism', {})
        excretion = result.get('excretion', {})
        toxicity = result.get('toxicity', {})
        drug_likeness = result.get('drug_likeness', {})
        alerts = result.get('alerts', {})
        
        key_metrics = {
            "MW": mw,
            "LogP": logp,
            "TPSA": tpsa,
            "HBD": hbd,
            "HBA": hba,
            "RotB": rotb,
            "QED": qed_val,
            "hERG": toxicity.get('herg'),
            "AMES": toxicity.get('ames'),
            "DILI": toxicity.get('dili'),
            "BBB": distribution.get('bbb'),
            "CYP2D6": metabolism.get('cyp2d6'),
            "CYP3A4": metabolism.get('cyp3a4'),
            "Solubility": absorption.get('solubility'),
            "Lipinski": drug_likeness.get('lipinski_violations', 0),
            "PAINS": alerts.get('pains', 0),
            "BRENK": alerts.get('brenk', 0),
        }
        
        # 药物五分类评价
        lipinski_v = drug_likeness.get('lipinski_violations', 0)
        five_rule = '通过' if lipinski_v == 0 else f'违反 {lipinski_v} 条'
        
        return {
            "success": True,
            "smiles": smiles,
            "canonical_smiles": canonicalize_smiles(smiles),
            "admet_result": result,
            "key_metrics": key_metrics,
            "drug_likeness": five_rule,
            "message": "ADMET 分析完成",
            "overall_score": result.get('overall_score'),
            "source": result.get('source', 'unknown'),
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"ADMET 分析失败: {e}"
        }


# ============================================================================
# Phase 2: LangChain 工具兼容层（新增，不影响原有代码）
# ============================================================================

"""
LangChain 工具标准化接口

在原有工具基础上，提供 LangChain 兼容的 Tool 对象，
可接入 LangChain Agent、Chain 等生态组件。

原有接口（register_tool / get_registry）完全保留，前端无感知。
"""

from typing import Callable
from pydantic import BaseModel, Field

# 延迟导入 LangChain（避免循环依赖）
_lc_tools_available = False
try:
    from langchain.tools import tool as lc_tool_decorator
    from langchain.tools import BaseTool as LCBaseTool
    _lc_tools_available = True
except ImportError:
    pass


def _tool_wrapper(func: Callable, name: str, description: str) -> Callable:
    """包装工具函数为 LangChain 兼容格式。
    
    LangChain 的 @tool 期望函数返回字符串，但我们的工具返回 dict。
    这里统一将 dict 转为 JSON 字符串。
    """
    def wrapped(*args, **kwargs):
        result = func(*args, **kwargs)
        if isinstance(result, dict):
            return json.dumps(result, ensure_ascii=False, default=str)
        return str(result)
    
    wrapped.__name__ = func.__name__
    wrapped.__doc__ = description or func.__doc__
    return wrapped


def to_langchain_tools() -> list:
    """
    将现有工具注册表转换为 LangChain Tool 列表。
    
    Returns:
        List[BaseTool]: LangChain 兼容的工具对象列表
    """
    if not _lc_tools_available:
        logger.warning("LangChain tools not available, skipping conversion")
        return []
    
    tools = []
    registry = get_registry()
    
    for name, func in registry._tools.items():
        schema = registry._schemas.get(name, {})
        description = schema.get("description", f"Tool: {name}")
        
        # 包装函数为字符串返回
        wrapped = _tool_wrapper(func, name, description)
        
        # 使用 LangChain 的 @tool 装饰器
        tool_obj = lc_tool_decorator(wrapped)
        tools.append(tool_obj)
    
    return tools


# ── 直接导出关键工具（供 LangChain 直接使用）──
# 这些工具保留原有 dict 返回格式，供内部代码使用
# LangChain 外部使用 to_langchain_tools() 获取字符串版本

__all__ = [
    # 原有接口
    "get_registry",
    "register_tool",
    # Phase 2 新增
    "to_langchain_tools",
    # 工具函数（保留原有导出）
    "create_project",
    "list_projects",
    "run_pipeline",
    "analyze_failures",
    "adjust_filters",
    "get_project_status",
    "compare_molecules",
    "suggest_next_step",
    "get_failed_molecules",
    "get_top_molecules",
    "analyze_single_molecule_admet",
]
