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
        "admet_threshold": {"type": "float", "description": "ADMET阈值", "required": False, "default": 60}
    }
)
def run_pipeline(project_id: int, num_molecules: int = 500,
                 generation_strategy: str = "crem", similarity_threshold: float = 0.3,
                 admet_threshold: float = 60) -> Dict:
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
            "availability_threshold": 0.5,
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
        
        # 轮询等待
        elapsed = 0
        check_interval = min(poll_interval, 3)
        while latest_run.status == "running" and elapsed < max_wait_seconds:
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
