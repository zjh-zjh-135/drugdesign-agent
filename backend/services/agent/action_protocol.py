"""
action_protocol.py - 前端动作协议 v2

根据 Agent 实际执行结果（而非用户目标）生成前端动作，避免状态不一致。
"""

from enum import Enum
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field


class ActionType(Enum):
    """前端动作类型"""
    NAVIGATE = "navigate"
    SET_STATE = "set_state"
    SET_FILTER = "set_filter"
    HIGHLIGHT = "highlight"
    TOAST = "toast"
    CONFIRM = "confirm"
    REFRESH = "refresh"
    SHOW_DATA = "show_data"
    SHOW_CHART = "show_chart"
    OPEN_MODAL = "open_modal"
    SCROLL_TO = "scroll_to"


@dataclass
class FrontendAction:
    """前端动作"""
    type: str
    payload: Dict[str, Any] = field(default_factory=dict)
    priority: int = 0
    description: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "payload": self.payload,
            "priority": self.priority,
            "description": self.description,
        }


class ActionGenerator:
    """
    根据 Agent 实际执行结果生成前端动作。
    核心原则：只根据"实际执行了什么"生成动作，不根据"用户想做什么"。
    """
    
    def __init__(self, tool_registry=None):
        self.tools = tool_registry
    
    def generate_from_result(
        self,
        execution_report: Dict[str, Any],
        env_state: Dict[str, Any],
        goal: str,
    ) -> List[FrontendAction]:
        """
        根据实际执行结果生成前端动作。
        """
        actions = []
        
        # 防御：确保 execution_report 和 env_state 是字典
        if not isinstance(execution_report, dict):
            execution_report = {}
        if not isinstance(env_state, dict):
            env_state = {}
        
        project_id = execution_report.get("project_id") or env_state.get("project_id")
        steps = execution_report.get("steps", [])
        success = execution_report.get("success", False)
        
        # 防御：确保 steps 是列表，且每个元素是字典
        if not isinstance(steps, list):
            steps = []
        steps = [s for s in steps if isinstance(s, dict)]
        
        # 如果执行失败，不生成任何导航/数据展示动作（只生成 Toast 通知）
        if not success and not steps:
            return [FrontendAction(
                type=ActionType.TOAST.value,
                payload={
                    "message": "执行失败，请重试或提供更多信息",
                    "type": "error",
                    "duration": 5000,
                },
                priority=10,
                description="显示失败通知",
            )]
        
        # 1. 检查实际执行了哪些工具（基于 steps 中的实际执行结果）
        executed_tools = {s.get("tool", "") for s in steps if s.get("status") == "ok"}
        
        # 2. 导航动作：只根据实际执行的工具，不根据 goal
        nav_actions = self._generate_nav_actions(executed_tools, project_id)
        actions.extend(nav_actions)
        
        # 3. 状态更新
        state_actions = self._generate_state_actions(executed_tools, steps, execution_report)
        actions.extend(state_actions)
        
        # 4. 数据展示
        data_actions = self._generate_data_actions(executed_tools, steps)
        actions.extend(data_actions)
        
        # 5. 通知
        toast_actions = self._generate_toast_actions(execution_report, steps)
        actions.extend(toast_actions)
        
        # 按优先级排序
        actions.sort(key=lambda a: a.priority, reverse=True)
        
        return actions
    
    def _generate_nav_actions(
        self, executed_tools: set, project_id: int
    ) -> List[FrontendAction]:
        """根据实际执行的工具生成导航（避免状态不一致）"""
        actions = []
        
        # 实际执行了 analyze_failures → 跳转到失败分子库
        if "analyze_failures" in executed_tools:
            actions.append(FrontendAction(
                type=ActionType.NAVIGATE.value,
                payload={"path": "/failed-molecules", "project_id": project_id},
                priority=8,
                description="跳转到失败分子库",
            ))
        
        # 实际执行了 run_pipeline → 跳转到 Pipeline 页面
        if "run_pipeline" in executed_tools:
            actions.append(FrontendAction(
                type=ActionType.NAVIGATE.value,
                payload={"path": "/pipeline", "project_id": project_id},
                priority=8,
                description="跳转到 Pipeline 运行页面",
            ))
        
        # 实际执行了 create_project → 跳转到项目列表
        if "create_project" in executed_tools:
            actions.append(FrontendAction(
                type=ActionType.NAVIGATE.value,
                payload={"path": "/projects", "project_id": project_id},
                priority=8,
                description="跳转到项目列表",
            ))
        
        # 实际执行了 compare_molecules → 跳转到分子浏览器
        if "compare_molecules" in executed_tools:
            actions.append(FrontendAction(
                type=ActionType.NAVIGATE.value,
                payload={"path": "/molecules", "mode": "compare"},
                priority=7,
                description="跳转到分子浏览器进行对比",
            ))
        
        # 实际执行了 get_project_status（且没有执行更具体的工具）→ 跳转到结果页
        if "get_project_status" in executed_tools and not any(t in executed_tools for t in ["analyze_failures", "run_pipeline"]):
            actions.append(FrontendAction(
                type=ActionType.NAVIGATE.value,
                payload={"path": "/results", "project_id": project_id},
                priority=6,
                description="跳转到结果分析页面",
            ))
        
        return actions
    
    def _generate_state_actions(
        self, executed_tools: set, steps: List[Dict], execution_report: Dict
    ) -> List[FrontendAction]:
        """根据实际执行结果生成状态更新"""
        actions = []
        
        # 查找 adjust_filters 的成功步骤
        for s in steps:
            if s.get("tool") == "adjust_filters" and s.get("status") == "ok":
                obs = s.get("observation", {})
                updated = obs.get("updated", {}) if isinstance(obs, dict) else {}
                if updated:
                    actions.append(FrontendAction(
                        type=ActionType.SET_FILTER.value,
                        payload={"filters": updated},
                        priority=7,
                        description="更新筛选条件",
                    ))
        
        # 查找 create_project 的成功步骤
        for s in steps:
            if s.get("tool") == "create_project" and s.get("status") == "ok":
                obs = s.get("observation", {})
                if obs and obs.get("success"):
                    actions.append(FrontendAction(
                        type=ActionType.SET_STATE.value,
                        payload={
                            "key": "currentProject",
                            "value": {
                                "id": obs.get("project_id"),
                                "name": obs.get("name"),
                                "target_pdb": obs.get("target_pdb"),
                            }
                        },
                        priority=9,
                        description="设置当前项目",
                    ))
        
        # 查找 run_pipeline 的成功步骤
        for s in steps:
            if s.get("tool") == "run_pipeline" and s.get("status") == "ok":
                obs = s.get("observation", {})
                if obs and obs.get("success"):
                    actions.append(FrontendAction(
                        type=ActionType.SET_STATE.value,
                        payload={
                            "key": "pipelineJobId",
                            "value": obs.get("pipeline_run_id"),
                        },
                        priority=7,
                        description="设置 Pipeline Job ID",
                    ))
                    actions.append(FrontendAction(
                        type=ActionType.SET_STATE.value,
                        payload={
                            "key": "pipelineStatus",
                            "value": "running",
                        },
                        priority=7,
                        description="更新 Pipeline 状态为运行中",
                    ))
        
        return actions
    
    def _generate_data_actions(
        self, executed_tools: set, steps: List[Dict]
    ) -> List[FrontendAction]:
        """根据实际执行结果生成数据展示"""
        actions = []
        
        # 实际执行了 analyze_failures 且有结果
        for s in steps:
            if s.get("tool") == "analyze_failures" and s.get("status") == "ok":
                obs = s.get("observation", {})
                if obs and obs.get("total_failed", 0) > 0:
                    actions.append(FrontendAction(
                        type=ActionType.SHOW_DATA.value,
                        payload={
                            "title": "失败分子分析",
                            "data": {
                                "total_failed": obs.get("total_failed"),
                                "stage_counts": obs.get("stage_counts"),
                                "reasons": obs.get("reasons"),
                                "suggestions": obs.get("suggestions", []),
                            }
                        },
                        priority=5,
                        description="展示失败分子分析数据",
                    ))
        
        # 实际执行了 compare_molecules 且有结果
        for s in steps:
            if s.get("tool") == "compare_molecules" and s.get("status") == "ok":
                obs = s.get("observation", {})
                if obs and obs.get("success"):
                    molecules = obs.get("molecules", [])
                    if molecules:
                        actions.append(FrontendAction(
                            type=ActionType.SHOW_CHART.value,
                            payload={
                                "title": "分子对比分析",
                                "type": "molecule_comparison",
                                "data": molecules,
                            },
                            priority=5,
                            description="展示分子对比图表",
                        ))
        
        # 实际执行了 suggest_next_step 且有结果
        for s in steps:
            if s.get("tool") == "suggest_next_step" and s.get("status") == "ok":
                obs = s.get("observation", {})
                if obs and obs.get("success"):
                    suggestions = obs.get("suggestions", [])
                    if suggestions:
                        actions.append(FrontendAction(
                            type=ActionType.SHOW_DATA.value,
                            payload={
                                "title": "下一步建议",
                                "type": "suggestions",
                                "data": suggestions,
                            },
                            priority=4,
                            description="展示下一步操作建议",
                        ))
        
        return actions
    
    def _generate_toast_actions(
        self, execution_report: Dict, steps: List[Dict]
    ) -> List[FrontendAction]:
        """根据执行结果生成 Toast 通知"""
        actions = []
        success = execution_report.get("success", False)
        
        ok_count = sum(1 for s in steps if s.get("status") == "ok")
        error_count = sum(1 for s in steps if s.get("status") == "error")
        total = len(steps)
        
        if success and total > 0 and ok_count == total:
            actions.append(FrontendAction(
                type=ActionType.TOAST.value,
                payload={
                    "message": f"任务完成。所有 {total} 个步骤执行成功",
                    "type": "success",
                    "duration": 5000,
                },
                priority=10,
                description="显示成功通知",
            ))
        elif success and error_count > 0:
            actions.append(FrontendAction(
                type=ActionType.TOAST.value,
                payload={
                    "message": f"任务部分完成：{ok_count}/{total} 步骤成功，{error_count} 步骤失败",
                    "type": "warning",
                    "duration": 6000,
                },
                priority=10,
                description="显示部分成功通知",
            ))
        elif not success:
            actions.append(FrontendAction(
                type=ActionType.TOAST.value,
                payload={
                    "message": f"任务执行失败，请检查错误信息或补充项目信息",
                    "type": "error",
                    "duration": 5000,
                },
                priority=10,
                description="显示失败通知",
            ))
        
        # 项目创建成功
        for s in steps:
            if s.get("tool") == "create_project" and s.get("status") == "ok":
                obs = s.get("observation", {})
                if obs and obs.get("success"):
                    actions.append(FrontendAction(
                        type=ActionType.TOAST.value,
                        payload={
                            "message": f"项目「{obs.get('name', '新项目')}」创建成功",
                            "type": "success",
                            "duration": 4000,
                        },
                        priority=10,
                        description="显示项目创建成功通知",
                    ))
        
        # Pipeline 启动
        for s in steps:
            if s.get("tool") == "run_pipeline" and s.get("status") == "ok":
                obs = s.get("observation", {})
                if obs and obs.get("success"):
                    actions.append(FrontendAction(
                        type=ActionType.TOAST.value,
                        payload={
                            "message": f"Pipeline 已启动。策略：{obs.get('strategy', 'default')}，目标：{obs.get('num_molecules', 500)} 个分子",
                            "type": "info",
                            "duration": 5000,
                        },
                        priority=10,
                        description="显示 Pipeline 启动通知",
                    ))
        
        return actions
