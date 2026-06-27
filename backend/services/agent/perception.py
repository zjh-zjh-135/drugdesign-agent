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
        else:
            state["projects"] = self._list_projects()
            state["project_summary"] = None
            state["pipeline_status"] = None
            state["failure_analysis"] = None
            state["suggestions"] = None

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
