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
        "name": {"type": "string", "description": "项目名称", "required": True},
        "target_name": {"type": "string", "description": "靶点名称", "required": False},
        "target_pdb": {"type": "string", "description": "PDB ID", "required": False},
        "description": {"type": "string", "description": "项目描述", "required": False},
        "design_goal": {"type": "string", "description": "设计目标: hit_finding/lead_optimization/scaffold_hopping", "required": False}
    }
)
def create_project(name: str, target_name: str = None, target_pdb: str = None,
                   description: str = None, design_goal: str = "hit_finding") -> Dict:
    """创建新项目"""
    from ...models.database import Project
    db = _get_db()
    try:
        project = Project(
            name=name,
            target_name=target_name or name,
            target_pdb=target_pdb,
            description=description,
            design_goal=design_goal
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        
        # 保存记忆
        save_project_memory(db, project.id, "event", "project_created", {
            "name": name,
            "target_pdb": target_pdb,
            "design_goal": design_goal,
            "timestamp": datetime.now().isoformat()
        }, importance=5)
        
        return {
            "success": True,
            "project_id": project.id,
            "name": project.name,
            "target_pdb": project.target_pdb,
            "design_goal": project.design_goal,
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
            _db = _get_db()
            try:
                from ...services.pipeline import PipelineRunner
                runner = PipelineRunner(project_id, params, pipeline_run.id)
                runner.run()
            except Exception as e:
                print(f"Pipeline run error: {e}")
            finally:
                _db.close()
        
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
