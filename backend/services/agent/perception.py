import time
"""
perception.py - Environment Perception Module

Queries the current project state, pipeline results, failures, and other
relevant information via the ToolRegistry, then formats a structured
environment summary suitable for LLM consumption.
"""

import json
from typing import Dict, Any, Optional

from .tools import get_registry
from .engine import Action


class EnvironmentPerception:
    """
    Environment perception for the DrugDesign Copilot Agent.

    Usage:
        perception = EnvironmentPerception()
        state = perception.get_state(project_id=1)
    """

    def __init__(self, tool_registry=None):
        self.tools = tool_registry or get_registry()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_state(self, project_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Gather a comprehensive environment summary.

        Returns a dict with:
            - project_summary
            - pipeline_status
            - failure_analysis
            - recent_memories
            - available_tools
            - molecule_details    # 新增：分子详细信息
            - admet_summary       # 新增：ADMET统计
            - timestamp
        """
        state = {
            "timestamp": __import__("datetime").datetime.now().isoformat(),
            "project_id": project_id,
            "available_tools": [t["name"] for t in self.tools.list_tools()],
        }

        if project_id:
            state["project_summary"] = self._get_project_summary(project_id)
            state["pipeline_status"] = self._get_pipeline_status(project_id)
            state["failure_analysis"] = self._get_failure_analysis(project_id)
            state["suggestions"] = self._get_suggestions(project_id)
            state["molecule_details"] = self._get_molecule_details(project_id)  # 新增
            state["admet_summary"] = self._get_admet_summary(project_id)       # 新增
        else:
            state["projects"] = self._list_projects()
            state["project_summary"] = None
            state["pipeline_status"] = None
            state["failure_analysis"] = None
            state["suggestions"] = None
            state["molecule_details"] = None
            state["admet_summary"] = None

        return state

    def format_for_llm(self, state: Dict[str, Any]) -> str:
        """
        Convert the structured state dict into a plain-text report
        that can be fed directly into an LLM prompt.
        """
        lines = ["=== 环境感知报告 ===", ""]

        lines.append(f"时间: {state.get('timestamp', 'unknown')}")
        lines.append(f"项目ID: {state.get('project_id', '未指定')}")
        lines.append("")

        # Project summary
        summary = state.get("project_summary")
        if summary:
            lines.append("--- 项目概况 ---")
            if isinstance(summary, dict):
                for k, v in summary.items():
                    if k == "stages" and isinstance(v, dict):
                        lines.append(f"  {k}:")
                        for sk, sv in v.items():
                            lines.append(f"    {sk}: {sv}")
                    else:
                        lines.append(f"  {k}: {v}")
            else:
                lines.append(f"  {json.dumps(summary, ensure_ascii=False)}")
            lines.append("")
        elif "projects" in state:
            lines.append("--- 现有项目 ---")
            projects = state["projects"]
            if isinstance(projects, list):
                for p in projects[:10]:
                    if isinstance(p, dict):
                        lines.append(
                            f"  ID={p.get('id', '?')} 名称={p.get('name', '?')} "
                            f"靶点={p.get('target_pdb', '?')} "
                            f"分子数={p.get('molecule_count', 0)}"
                        )
                    else:
                        lines.append(f"  {p}")
            else:
                lines.append(f"  {projects}")
            lines.append("")

        # Pipeline status
        pipeline = state.get("pipeline_status")
        if pipeline:
            lines.append("--- Pipeline 状态 ---")
            if isinstance(pipeline, dict):
                for k, v in pipeline.items():
                    lines.append(f"  {k}: {v}")
            else:
                lines.append(f"  {pipeline}")
            lines.append("")

        # Failure analysis
        failures = state.get("failure_analysis")
        if failures:
            lines.append("--- 失败分析 ---")
            if isinstance(failures, dict):
                total = failures.get("total_failed", 0)
                lines.append(f"  失败总数: {total}")
                reasons = failures.get("reasons", {})
                if reasons:
                    lines.append("  失败原因统计:")
                    for r, c in reasons.items():
                        lines.append(f"    {r}: {c}")
                suggestions = failures.get("suggestions", [])
                if suggestions:
                    lines.append("  建议:")
                    for s in suggestions[:5]:
                        lines.append(f"    - {s}")
            else:
                lines.append(f"  {failures}")
            lines.append("")

        # Suggestions
        suggestions = state.get("suggestions")
        if suggestions:
            lines.append("--- 智能建议 ---")
            if isinstance(suggestions, dict):
                for k, v in suggestions.items():
                    lines.append(f"  {k}: {v}")
            elif isinstance(suggestions, list):
                for s in suggestions[:5]:
                    lines.append(f"  - {s}")
            else:
                lines.append(f"  {suggestions}")
            lines.append("")

        # Molecule details (NEW)
        mol_details = state.get("molecule_details")
        if mol_details and not mol_details.get("error"):
            lines.append("--- 分子详情 ---")
            count = mol_details.get("count", 0)
            lines.append(f"  分子数量: {count}")
            for mol in mol_details.get("molecules", [])[:5]:
                lines.append(f"  ID={mol.get('id')} SMILES={mol.get('smiles')[:50]}... Status={mol.get('status')}")
                props = mol.get("properties")
                if props:
                    lines.append(f"    MW={props.get('mw')} LogP={props.get('logp')} TPSA={props.get('tpsa')} QED={props.get('qed')}")
                admet = mol.get("admet")
                if admet:
                    lines.append(f"    ADMET: overall={admet.get('overall_score')} solubility={admet.get('solubility')} BBB={admet.get('bbb')}")
            lines.append("")

        # ADMET Summary (NEW)
        admet_summary = state.get("admet_summary")
        if admet_summary and not admet_summary.get("error"):
            lines.append("--- ADMET 统计 ---")
            lines.append(f"  有 ADMET 数据的分子数: {admet_summary.get('count', 0)}")
            pass_rate = admet_summary.get("pass_rate")
            if pass_rate is not None:
                lines.append(f"  ADMET 通过率: {pass_rate}%")
            overall = admet_summary.get("overall_score")
            if overall:
                lines.append(f"  综合得分: 均值={overall.get('mean')} 范围=[{overall.get('min')}-{overall.get('max')}]")
            lines.append("")
        elif admet_summary and admet_summary.get("error"):
            lines.append("--- ADMET 统计 ---")
            lines.append(f"  获取失败: {admet_summary.get('error')}")
            lines.append("")

        # Available tools
        lines.append("--- 可用工具 ---")
        for tool_name in state.get("available_tools", []):
            lines.append(f"  - {tool_name}")
        lines.append("")

        lines.append("=== 环境感知报告结束 ===")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Internal tool wrappers
    # ------------------------------------------------------------------

    def _safe_execute(self, tool_name: str, params: Optional[Dict] = None) -> Any:
        """Execute a tool and return its result, swallowing exceptions."""
        params = params or {}
        func = self.tools.get(tool_name)
        if not func:
            return {"error": f"工具 '{tool_name}' 未注册"}
        try:
            return func(**params)
        except Exception as e:
            return {"error": str(e)}

    def _get_project_summary(self, project_id: int) -> Dict[str, Any]:
        return self._safe_execute("get_project_status", {"project_id": project_id})

    def _get_pipeline_status(self, project_id: int) -> Dict[str, Any]:
        # Reuse project status for pipeline info
        status = self._safe_execute("get_project_status", {"project_id": project_id})
        if isinstance(status, dict):
            return {
                "latest_pipeline": status.get("latest_pipeline"),
                "total_molecules": status.get("total_molecules", 0),
                "failed": status.get("failed", 0),
                "passed": status.get("passed", 0),
                "stages": status.get("stages", {}),
            }
        return {"error": "无法获取 pipeline 状态"}

    def _get_failure_analysis(self, project_id: int) -> Dict[str, Any]:
        return self._safe_execute("analyze_failures", {"project_id": project_id})

    def _get_suggestions(self, project_id: int) -> Any:
        return self._safe_execute("suggest_next_step", {"project_id": project_id})

    def _list_projects(self) -> Any:
        return self._safe_execute("list_projects")

    # ------------------------------------------------------------------
    # 新增：分子和 ADMET 详细数据获取
    # ------------------------------------------------------------------

    def _get_molecule_details(self, project_id: int, limit: int = 20) -> Dict[str, Any]:
        """获取项目的分子详细信息（包括属性和 ADMET）"""
        try:
            # 通过延迟导入避免循环依赖
            from ...models.database import init_db
            from ...models.database import GeneratedMolecule, MoleculeProperty, AdmetPrediction
            
            Session = init_db()
            db = Session()
            
            try:
                molecules = db.query(GeneratedMolecule).filter(
                    GeneratedMolecule.project_id == project_id
                ).order_by(GeneratedMolecule.created_at.desc()).limit(limit).all()
                
                results = []
                for mol in molecules:
                    mol_data = {
                        "id": mol.id,
                        "smiles": mol.smiles,
                        "status": mol.pipeline_status,
                        "strategy": mol.generation_strategy,
                    }
                    
                    # 获取属性
                    if mol.properties:
                        props = mol.properties
                        mol_data["properties"] = {
                            "mw": props.mw,
                            "logp": props.clogp,
                            "tpsa": props.tpsa,
                            "hbd": props.hbd,
                            "hba": props.hba,
                            "rotb": props.rotb,
                            "sa_score": props.sa_score,
                            "qed": props.qed,
                            "pass_filters": props.pass_filters,
                            "pass_admet": props.pass_admet,
                            "docking_score": props.docking_score,
                        }
                    
                    # 获取 ADMET
                    if mol.admet:
                        admet = mol.admet
                        mol_data["admet"] = {
                            "solubility": admet.solubility,
                            "permeability": admet.permeability,
                            "bbb": admet.bbb,
                            "herg": admet.herg,
                            "ames": admet.ames,
                            "dili": admet.dili,
                            "oral_bioavailability": admet.oral_bioavailability,
                            "overall_score": admet.overall_score,
                        }
                    
                    results.append(mol_data)
                
                return {
                    "count": len(results),
                    "limit": limit,
                    "molecules": results,
                }
            finally:
                db.close()
        except Exception as e:
            return {"error": str(e)}

    def _get_admet_summary(self, project_id: int) -> Dict[str, Any]:
        """获取项目 ADMET 统计摘要"""
        try:
            from ...models.database import init_db
            from ...models.database import GeneratedMolecule, AdmetPrediction
            
            Session = init_db()
            db = Session()
            
            try:
                # 获取所有分子的 ADMET 数据
                mols_with_admet = db.query(GeneratedMolecule, AdmetPrediction).join(
                    AdmetPrediction, GeneratedMolecule.id == AdmetPrediction.molecule_id
                ).filter(
                    GeneratedMolecule.project_id == project_id
                ).all()
                
                if not mols_with_admet:
                    return {"count": 0, "message": "暂无 ADMET 数据"}
                
                # 统计各指标
                scores = []
                solubility_vals = []
                bbb_vals = []
                herg_vals = []
                
                for mol, admet in mols_with_admet:
                    if admet.overall_score is not None:
                        scores.append(admet.overall_score)
                    if admet.solubility is not None:
                        solubility_vals.append(admet.solubility)
                    if admet.bbb is not None:
                        bbb_vals.append(admet.bbb)
                    if admet.herg is not None:
                        herg_vals.append(admet.herg)
                
                def _stats(vals):
                    if not vals:
                        return {}
                    import statistics
                    return {
                        "mean": round(statistics.mean(vals), 2),
                        "median": round(statistics.median(vals), 2),
                        "min": round(min(vals), 2),
                        "max": round(max(vals), 2),
                    }
                
                return {
                    "count": len(mols_with_admet),
                    "overall_score": _stats(scores),
                    "solubility": _stats(solubility_vals),
                    "bbb": _stats(bbb_vals),
                    "herg": _stats(herg_vals),
                    "pass_rate": round(
                        sum(1 for _, a in mols_with_admet if a.overall_score and a.overall_score >= 60) / len(mols_with_admet) * 100, 1
                    ) if mols_with_admet else 0,
                }
            finally:
                db.close()
        except Exception as e:
            return {"error": str(e)}
