"""
tracer.py - Agent 执行追踪系统（Phase 5）

替代 LangSmith 的轻量级本地追踪方案。

功能：
- 记录 Agent 每次执行的完整轨迹（ReAct 循环）
- 记录每个步骤的输入、输出、耗时、Token 用量
- 支持内存存储和文件持久化
- 提供可视化数据接口

Usage:
    from .tracer import AgentTracer, trace
    
    # 方式1：上下文管理器
    with AgentTracer(session_id='xxx') as tracer:
        result = agent.run(message)
        trace_record = tracer.get_trace()
    
    # 方式2：装饰器
    @trace(step_type='llm_call')
    def call_llm(messages):
        return llm_client.call(messages)
    
    # 查看追踪
    traces = TraceStore.get_recent_traces(limit=10)
"""

import json
import os
import time
import uuid
import logging
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime
from functools import wraps
from contextlib import contextmanager

logger = logging.getLogger(__name__)


# ============================================================================
# 数据模型
# ============================================================================

@dataclass
class TraceStep:
    """单步执行记录"""
    step_type: str           # "llm_call" / "tool_execution" / "planning" / "parsing" / "intent_parse" / "report"
    name: str                # 步骤名称（如 "planner.plan" / "analyze_single_molecule_admet"）
    start_time: datetime
    end_time: Optional[datetime] = None
    latency_ms: float = 0.0
    input_data: Dict[str, Any] = field(default_factory=dict)
    output_data: Dict[str, Any] = field(default_factory=dict)
    token_usage: Dict[str, int] = field(default_factory=dict)  # {"prompt": 10, "completion": 20, "total": 30}
    error: Optional[str] = None
    status: str = "running"  # running / ok / error
    
    def finish(self, output: Dict = None, error: str = None, token_usage: Dict = None):
        """标记步骤完成"""
        self.end_time = datetime.now()
        self.latency_ms = (self.end_time - self.start_time).total_seconds() * 1000
        self.status = "error" if error else "ok"
        if output:
            self.output_data = output
        if error:
            self.error = error
        if token_usage:
            self.token_usage = token_usage


@dataclass
class AgentTrace:
    """完整 Agent 执行轨迹"""
    trace_id: str
    session_id: Optional[str] = None
    user_message: str = ""
    intent_type: str = ""
    project_id: Optional[int] = None
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    total_latency_ms: float = 0.0
    steps: List[TraceStep] = field(default_factory=list)
    final_result: Dict[str, Any] = field(default_factory=dict)
    success: bool = False
    
    def add_step(self, step: TraceStep):
        """添加步骤"""
        self.steps.append(step)
    
    def finish(self, success: bool = True, final_result: Dict = None):
        """标记追踪完成"""
        self.end_time = datetime.now()
        self.total_latency_ms = (self.end_time - self.start_time).total_seconds() * 1000
        self.success = success
        if final_result:
            self.final_result = final_result
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于 JSON 序列化）"""
        return {
            "trace_id": self.trace_id,
            "session_id": self.session_id,
            "user_message": self.user_message,
            "intent_type": self.intent_type,
            "project_id": self.project_id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "total_latency_ms": round(self.total_latency_ms, 2),
            "success": self.success,
            "steps": [
                {
                    "step_type": s.step_type,
                    "name": s.name,
                    "start_time": s.start_time.isoformat(),
                    "end_time": s.end_time.isoformat() if s.end_time else None,
                    "latency_ms": round(s.latency_ms, 2),
                    "status": s.status,
                    "input_data": s.input_data,
                    "output_data": s.output_data,
                    "token_usage": s.token_usage,
                    "error": s.error,
                }
                for s in self.steps
            ],
            "final_result": self.final_result,
        }


# ============================================================================
# 存储层
# ============================================================================

class TraceStore:
    """
    追踪数据存储层。
    
    支持内存缓存 + 文件持久化（JSON Lines 格式）。
    """
    
    _memory_traces: List[AgentTrace] = []
    _max_memory_size: int = 100  # 内存中最多保留 100 条
    _trace_file: Optional[str] = None
    
    @classmethod
    def initialize(cls, trace_dir: str = None):
        """
        初始化存储层。
        
        Args:
            trace_dir: 追踪文件保存目录，默认使用项目根目录的 .traces/
        """
        if trace_dir is None:
            # 默认保存到项目根目录的 .traces/
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            trace_dir = os.path.join(base_dir, ".traces")
        
        os.makedirs(trace_dir, exist_ok=True)
        cls._trace_file = os.path.join(trace_dir, "agent_traces.jsonl")
        logger.info(f"TraceStore initialized: {cls._trace_file}")
    
    @classmethod
    def save(cls, trace: AgentTrace):
        """保存追踪记录到内存和文件"""
        # 内存缓存
        cls._memory_traces.append(trace)
        if len(cls._memory_traces) > cls._max_memory_size:
            cls._memory_traces = cls._memory_traces[-cls._max_memory_size:]
        
        # 文件持久化
        if cls._trace_file:
            try:
                with open(cls._trace_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(trace.to_dict(), ensure_ascii=False) + "\n")
            except Exception as e:
                logger.warning(f"Failed to write trace to file: {e}")
    
    @classmethod
    def get_recent_traces(cls, limit: int = 20) -> List[Dict]:
        """获取最近的追踪记录（从内存）"""
        traces = [t.to_dict() for t in cls._memory_traces]
        return traces[-limit:][::-1]  # 倒序，最新的在前
    
    @classmethod
    def get_trace_by_id(cls, trace_id: str) -> Optional[Dict]:
        """根据 ID 获取追踪记录"""
        for trace in cls._memory_traces:
            if trace.trace_id == trace_id:
                return trace.to_dict()
        
        # 如果内存中没有，尝试从文件加载
        if cls._trace_file and os.path.exists(cls._trace_file):
            try:
                with open(cls._trace_file, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            data = json.loads(line)
                            if data.get("trace_id") == trace_id:
                                return data
            except Exception as e:
                logger.warning(f"Failed to read trace from file: {e}")
        
        return None
    
    @classmethod
    def get_traces_by_session(cls, session_id: str, limit: int = 20) -> List[Dict]:
        """获取指定会话的追踪记录"""
        traces = [t.to_dict() for t in cls._memory_traces if t.session_id == session_id]
        return traces[-limit:][::-1]
    
    @classmethod
    def clear_all(cls):
        """清空所有追踪记录"""
        cls._memory_traces.clear()
        if cls._trace_file and os.path.exists(cls._trace_file):
            try:
                os.remove(cls._trace_file)
            except Exception as e:
                logger.warning(f"Failed to clear trace file: {e}")
    
    @classmethod
    def get_stats(cls) -> Dict[str, Any]:
        """获取追踪统计信息"""
        traces = cls._memory_traces
        if not traces:
            return {"total_traces": 0}
        
        total_llm_calls = sum(
            1 for t in traces for s in t.steps if s.step_type == "llm_call"
        )
        total_tool_calls = sum(
            1 for t in traces for s in t.steps if s.step_type == "tool_execution"
        )
        total_tokens = sum(
            s.token_usage.get("total", 0) for t in traces for s in t.steps
        )
        avg_latency = sum(t.total_latency_ms for t in traces) / len(traces)
        success_rate = sum(1 for t in traces if t.success) / len(traces) * 100
        
        return {
            "total_traces": len(traces),
            "total_llm_calls": total_llm_calls,
            "total_tool_calls": total_tool_calls,
            "total_tokens": total_tokens,
            "avg_latency_ms": round(avg_latency, 2),
            "success_rate": round(success_rate, 1),
        }


# 初始化存储层（模块加载时自动执行）
TraceStore.initialize()


# ============================================================================
# 追踪器
# ============================================================================

class AgentTracer:
    """
    Agent 执行追踪器。
    
    使用上下文管理器记录整个 ReAct 循环的执行轨迹。
    """
    
    _current_tracer: Optional["AgentTracer"] = None
    
    def __init__(self, session_id: str = None, user_message: str = "", project_id: int = None):
        self.trace = AgentTrace(
            trace_id=str(uuid.uuid4())[:12],
            session_id=session_id,
            user_message=user_message,
            project_id=project_id,
        )
        self._active_step: Optional[TraceStep] = None
    
    def __enter__(self):
        """进入上下文，开始追踪"""
        AgentTracer._current_tracer = self
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出上下文，完成追踪"""
        if exc_type:
            self.trace.finish(success=False, final_result={"error": str(exc_val)})
        else:
            self.trace.finish(success=True)
        
        TraceStore.save(self.trace)
        AgentTracer._current_tracer = None
        return False
    
    def start_step(self, step_type: str, name: str, input_data: Dict = None) -> TraceStep:
        """开始一个步骤"""
        step = TraceStep(
            step_type=step_type,
            name=name,
            start_time=datetime.now(),
            input_data=input_data or {},
        )
        self._active_step = step
        self.trace.add_step(step)
        return step
    
    def finish_step(self, output: Dict = None, error: str = None, token_usage: Dict = None):
        """完成当前步骤"""
        if self._active_step:
            self._active_step.finish(output=output, error=error, token_usage=token_usage)
            self._active_step = None
    
    def set_intent(self, intent_type: str):
        """设置意图类型"""
        self.trace.intent_type = intent_type
    
    def get_trace(self) -> AgentTrace:
        """获取当前追踪记录"""
        return self.trace
    
    @classmethod
    def get_current(cls) -> Optional["AgentTracer"]:
        """获取当前活跃的追踪器（用于跨函数调用）"""
        return cls._current_tracer


# ============================================================================
# 装饰器
# ============================================================================

def trace(step_type: str, name: str = None, record_input: bool = True, record_output: bool = True):
    """
    追踪装饰器。
    
    装饰函数，自动记录调用参数、返回值、耗时。
    
    Args:
        step_type: 步骤类型（llm_call / tool_execution / planning / parsing）
        name: 步骤名称，默认使用函数名
        record_input: 是否记录输入参数
        record_output: 是否记录输出结果
    
    Usage:
        @trace(step_type='llm_call')
        def call_llm(messages, temperature=0.7):
            return llm_client.call(messages, temperature)
    """
    def decorator(func: Callable) -> Callable:
        step_name = name or func.__name__
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            tracer = AgentTracer.get_current()
            step = None
            
            # 开始追踪
            if tracer:
                input_data = {}
                if record_input:
                    # 记录参数（过滤掉大对象和敏感信息）
                    input_data = _sanitize_args(args, kwargs)
                step = tracer.start_step(step_type=step_type, name=step_name, input_data=input_data)
            
            start_time = time.time()
            error = None
            result = None
            
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                error = str(e)
                raise
            finally:
                # 完成追踪
                if tracer and step:
                    latency_ms = (time.time() - start_time) * 1000
                    output_data = {}
                    if record_output and result is not None:
                        output_data = _sanitize_output(result)
                    
                    # Token 用量（如果结果中有）
                    token_usage = {}
                    if isinstance(result, dict) and "usage" in result:
                        usage = result["usage"]
                        token_usage = {
                            "prompt": usage.get("prompt_tokens", 0),
                            "completion": usage.get("completion_tokens", 0),
                            "total": usage.get("total_tokens", 0),
                        }
                    
                    step.finish(
                        output=output_data,
                        error=error,
                        token_usage=token_usage,
                    )
                    # 更新步骤耗时（装饰器计算的更精确）
                    step.latency_ms = latency_ms
        
        return wrapper
    return decorator


# ============================================================================
# 辅助函数
# ============================================================================

def _sanitize_args(args, kwargs) -> Dict[str, Any]:
    """清理参数，过滤大对象和敏感信息"""
    result = {}
    
    # 记录位置参数（用索引作为键）
    for i, arg in enumerate(args):
        if isinstance(arg, (str, int, float, bool)):
            result[f"arg_{i}"] = arg
        elif isinstance(arg, list) and len(arg) < 10:
            result[f"arg_{i}"] = arg[:5]  # 只保留前5个
        elif isinstance(arg, dict):
            result[f"arg_{i}"] = {k: v for k, v in list(arg.items())[:5]}
    
    # 记录关键字参数
    for key, value in kwargs.items():
        if key in ("api_key", "password", "token", "secret"):
            result[key] = "***"
        elif isinstance(value, (str, int, float, bool)):
            result[key] = value
        elif isinstance(value, list) and len(value) < 10:
            result[key] = value[:5]
        elif isinstance(value, dict):
            result[key] = {k: v for k, v in list(value.items())[:5]}
    
    return result


def _sanitize_output(output) -> Any:
    """清理输出，过滤大对象"""
    if isinstance(output, (str, int, float, bool)):
        return output
    elif isinstance(output, dict):
        # 只保留前 10 个键值对，字符串值截断到 500 字符
        sanitized = {}
        for k, v in list(output.items())[:10]:
            if isinstance(v, str) and len(v) > 500:
                sanitized[k] = v[:500] + "..."
            else:
                sanitized[k] = v
        return sanitized
    elif isinstance(output, list) and len(output) < 20:
        return output[:10]
    else:
        return str(output)[:200]


# ============================================================================
# 便捷函数
# ============================================================================

def get_trace_stats() -> Dict[str, Any]:
    """获取追踪统计"""
    return TraceStore.get_stats()


def get_recent_traces(limit: int = 20) -> List[Dict]:
    """获取最近追踪"""
    return TraceStore.get_recent_traces(limit)


def get_trace(trace_id: str) -> Optional[Dict]:
    """获取单个追踪"""
    return TraceStore.get_trace_by_id(trace_id)


def clear_traces():
    """清空所有追踪"""
    TraceStore.clear_all()


__all__ = [
    "AgentTrace",
    "TraceStep",
    "TraceStore",
    "AgentTracer",
    "trace",
    "get_trace_stats",
    "get_recent_traces",
    "get_trace",
    "clear_traces",
]