"""
llm_client.py - LangChain-Compatible LLM Client for DrugDesign Copilot Agent

Phase 1: LLM 调用层标准化

核心设计：
- 保留原有接口（call/retry_call/cached_call/stream_call），前端无感知
- 底层替换为 LangChain ChatOpenAI（兼容 Moonshot/Kimi API）
- 获得 LangChain 能力：流式输出、Token 统计、标准消息格式
- 保留缓存层、指标监控、指数退避重试（我们的业务逻辑更精细）
- 预留 LangSmith 追踪接口（Phase 5）

Usage:
    client = LLMClient(api_key=..., model=...)
    response = client.call(messages, temperature=0.3)
    
    # 流式输出（新增能力）
    for chunk in client.stream_call(messages):
        yield chunk
    
    # 获取指标（增强）
    metrics = client.get_metrics()
"""

import json
import os
import time
import hashlib
import logging
from typing import Dict, Any, List, Optional, Iterator
from dataclasses import dataclass, field
from datetime import datetime, timedelta

# ── LangChain 核心 ──
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, BaseMessage
from langchain_core.callbacks import CallbackManager

logger = logging.getLogger(__name__)


# ============================================================================
# 数据模型
# ============================================================================

@dataclass
class LLMMetrics:
    """LLM 调用统计"""
    total_calls: int = 0
    total_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_errors: int = 0
    total_cache_hits: int = 0
    total_latency_ms: float = 0.0
    
    @property
    def avg_latency_ms(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return self.total_latency_ms / self.total_calls


@dataclass
class CacheEntry:
    """缓存条目"""
    response: str
    timestamp: datetime
    ttl_seconds: int = 60
    
    def is_expired(self) -> bool:
        return datetime.now() - self.timestamp > timedelta(seconds=self.ttl_seconds)


# ============================================================================
# LLM Client（LangChain 兼容版）
# ============================================================================

class LLMClient:
    """
    LangChain 兼容的统一 LLM 客户端。
    
    底层使用 LangChain ChatOpenAI（兼容 Moonshot API），保留原有接口不变。
    """
    
    # 可重试的 HTTP 状态码
    RETRYABLE_STATUS_CODES = {429, 500, 502, 503}
    
    # 可重试的错误关键词（SSL、连接、超时等网络错误）
    RETRYABLE_ERROR_KEYWORDS = [
        "timeout", "connection", "ssl", "eof", "reset", "refused", "unreachable",
    ]
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        api_url: Optional[str] = None,
        timeout: int = 60,
        rate_limit_interval: float = 1.0,
        max_retries: int = 3,
    ):
        from .config import agent_config
        
        self.api_key = api_key or agent_config.KIMI_API_KEY
        self.model = model or agent_config.DEFAULT_MODEL
        self.api_url = api_url or agent_config.KIMI_API_URL
        self.timeout = timeout or agent_config.LLM_TIMEOUT
        self.rate_limit_interval = rate_limit_interval or agent_config.LLM_RATE_LIMIT_INTERVAL
        self.max_retries = max_retries
        
        # 状态
        self._last_call_time: float = 0.0
        self._cache: Dict[str, CacheEntry] = {}
        self.metrics = LLMMetrics()
        
        # ── LangChain ChatOpenAI 实例（兼容 Moonshot）──
        # Moonshot API 是 OpenAI 兼容格式，使用 openai 包 + base_url
        self._chat_model = ChatOpenAI(
            model_name=self.model,
            openai_api_key=self.api_key,
            openai_api_base=self.api_url.replace("/chat/completions", ""),  # 去掉路径后缀
            request_timeout=self.timeout,
            temperature=0.7,
            max_tokens=4096,
            max_retries=0,  # 我们自己处理重试，更精细
            # 可选：启用流式输出
            streaming=False,
        )
        
        logger.info(f"LLMClient initialized (LangChain): model={self.model}, base={self.api_url}")
    
    # ------------------------------------------------------------------
    # 消息转换：OpenAI 风格 → LangChain 消息
    # ------------------------------------------------------------------
    
    @staticmethod
    def _convert_messages(messages: List[Dict[str, str]]) -> List[BaseMessage]:
        """将 OpenAI 风格的消息列表转换为 LangChain 消息对象。"""
        lc_messages = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                lc_messages.append(SystemMessage(content=content))
            elif role == "assistant":
                lc_messages.append(AIMessage(content=content))
            else:
                lc_messages.append(HumanMessage(content=content))
        return lc_messages
    
    # ------------------------------------------------------------------
    # Public API（保留原有接口）
    # ------------------------------------------------------------------
    
    def call(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> str:
        """
        基础调用。LangChain 驱动，保留原有接口和指标统计。
        
        Args:
            messages: OpenAI-style message list
            temperature: Sampling temperature
            **kwargs: 额外参数（如 top_p, max_tokens 等）
        
        Returns:
            Raw text content from LLM, or error message string.
        """
        # Phase 5: 追踪 LLM 调用
        tracer = None
        step = None
        try:
            from .tracer import AgentTracer
            tracer = AgentTracer.get_current()
            if tracer:
                step = tracer.start_step(
                    step_type="llm_call",
                    name=f"LLMCall({self.model})",
                    input_data={"messages": str(messages)[:500], "temperature": temperature}
                )
        except Exception:
            pass
        
        if not self.api_key:
            return "API Key 未配置，无法调用 LLM 服务。"
        
        # 速率限制
        self._rate_limit_wait()
        
        # 记录开始时间
        start_time = time.time()
        
        try:
            # 转换为 LangChain 消息
            lc_messages = self._convert_messages(messages)
            
            # 调用 LangChain Chat Model
            response = self._chat_model.invoke(
                lc_messages,
                temperature=temperature,
                **kwargs,
            )
            
            # 提取内容
            content = response.content.strip() if response.content else ""
            
            # ── 更新指标（LangChain 自动提供 Token 统计）──
            latency_ms = (time.time() - start_time) * 1000
            usage = response.response_metadata.get("token_usage", {}) if hasattr(response, "response_metadata") else {}
            self._update_metrics(
                latency_ms=latency_ms,
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
            )
            
            # Phase 5: 完成追踪
            if tracer and step:
                step.finish(
                    output={"content": content[:500]},
                    token_usage={
                        "prompt": usage.get("prompt_tokens", 0),
                        "completion": usage.get("completion_tokens", 0),
                        "total": usage.get("total_tokens", 0),
                    }
                )
            
            return content
            
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            self._update_metrics(latency_ms=latency_ms, error=True)
            error_msg = f"LLM 调用失败: {e}"
            logger.error(error_msg)
            
            # Phase 5: 记录错误
            if tracer and step:
                step.finish(error=error_msg)
            
            return error_msg
    
    def retry_call(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_retries: int = 3,
        base_delay: float = 1.0,
        **kwargs: Any,
    ) -> str:
        """
        带指数退避重试的调用。保留原有业务逻辑。
        
        - 429/500/502/503: 自动重试（指数退避）
        - 400/401/403: 不重试（参数错误或权限问题）
        - SSL/连接/超时错误: 自动重试（网络波动）
        - 其他异常: 重试一次
        """
        last_error = ""
        
        for attempt in range(max_retries + 1):
            result = self.call(messages, temperature, **kwargs)
            
            # 检查是否成功
            if not result.startswith("LLM 调用失败"):
                return result
            
            # 解析错误类型，判断是否可重试
            is_retryable = self._is_retryable_error(result)
            if not is_retryable or attempt >= max_retries:
                return result
            
            # 指数退避等待
            delay = base_delay * (2 ** attempt)
            if "SSL" in result or "连接" in result:
                delay += 1.0
            logger.warning(f"LLM 调用失败，第 {attempt + 1} 次重试，等待 {delay:.1f}s...")
            time.sleep(delay)
            last_error = result
        
        return last_error
    
    def cached_call(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        cache_ttl: int = 60,
        **kwargs: Any,
    ) -> str:
        """
        带缓存的调用。相同 (messages + model + temperature) 在 TTL 内复用响应。
        """
        cache_key = self._make_cache_key(messages, temperature, **kwargs)
        
        # 检查缓存
        entry = self._cache.get(cache_key)
        if entry and not entry.is_expired():
            self.metrics.total_cache_hits += 1
            return entry.response
        
        # 缓存未命中，执行调用（使用 retry_call 增强稳定性）
        result = self.retry_call(messages, temperature, **kwargs)
        
        # 存入缓存（只缓存成功结果）
        if not result.startswith("LLM 调用失败"):
            self._cache[cache_key] = CacheEntry(
                response=result,
                timestamp=datetime.now(),
                ttl_seconds=cache_ttl,
            )
        
        return result
    
    def stream_call(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> Iterator[str]:
        """
        流式输出调用（LangChain 原生支持，Phase 1 启用）。
        
        Returns:
            Generator yielding partial text chunks.
        """
        if not self.api_key:
            yield "API Key 未配置，无法调用 LLM 服务。"
            return
        
        # 速率限制
        self._rate_limit_wait()
        
        start_time = time.time()
        
        try:
            # 转换为 LangChain 消息
            lc_messages = self._convert_messages(messages)
            
            # 使用流式模式
            stream_model = self._chat_model.bind(streaming=True)
            
            for chunk in stream_model.stream(lc_messages, temperature=temperature, **kwargs):
                content = chunk.content if hasattr(chunk, "content") else str(chunk)
                if content:
                    yield content
            
            # 更新指标
            latency_ms = (time.time() - start_time) * 1000
            self._update_metrics(latency_ms=latency_ms)
            
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            self._update_metrics(latency_ms=latency_ms, error=True)
            error_msg = f"LLM 流式调用失败: {e}"
            logger.error(error_msg)
            yield error_msg
    
    # ------------------------------------------------------------------
    # 高级接口：LangChain 原生消息
    # ------------------------------------------------------------------
    
    def invoke_lc(
        self,
        messages: List[BaseMessage],
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> Any:
        """
        直接接受 LangChain 消息对象的调用接口。
        
        用于与 LangChain 其他组件（如 Chain、Agent）集成。
        """
        self._rate_limit_wait()
        return self._chat_model.invoke(messages, temperature=temperature, **kwargs)
    
    # ------------------------------------------------------------------
    # Metrics & Cache Management
    # ------------------------------------------------------------------
    
    def get_metrics(self) -> Dict[str, Any]:
        """获取当前指标统计。"""
        return {
            "total_calls": self.metrics.total_calls,
            "total_tokens": self.metrics.total_tokens,
            "prompt_tokens": self.metrics.prompt_tokens,
            "completion_tokens": self.metrics.completion_tokens,
            "total_errors": self.metrics.total_errors,
            "total_cache_hits": self.metrics.total_cache_hits,
            "avg_latency_ms": round(self.metrics.avg_latency_ms, 2),
            "cache_size": len(self._cache),
        }
    
    def clear_cache(self) -> None:
        """清空缓存。"""
        self._cache.clear()
    
    def clean_expired_cache(self) -> int:
        """清理过期缓存。返回清理的条目数。"""
        expired_keys = [k for k, v in self._cache.items() if v.is_expired()]
        for k in expired_keys:
            del self._cache[k]
        return len(expired_keys)
    
    # ------------------------------------------------------------------
    # Private Helpers
    # ------------------------------------------------------------------
    
    def _rate_limit_wait(self) -> None:
        """确保两次调用之间至少间隔 rate_limit_interval 秒。"""
        elapsed = time.time() - self._last_call_time
        if elapsed < self.rate_limit_interval:
            time.sleep(self.rate_limit_interval - elapsed)
        self._last_call_time = time.time()
    
    def _is_retryable_error(self, error_msg: str) -> bool:
        """判断错误是否可重试。"""
        for code in self.RETRYABLE_STATUS_CODES:
            if f"HTTP {code}" in error_msg:
                return True
        error_lower = error_msg.lower()
        for keyword in self.RETRYABLE_ERROR_KEYWORDS:
            if keyword in error_lower:
                return True
        return False
    
    def _update_metrics(
        self,
        latency_ms: float,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        error: bool = False,
    ) -> None:
        """更新指标。"""
        self.metrics.total_calls += 1
        self.metrics.total_latency_ms += latency_ms
        self.metrics.prompt_tokens += prompt_tokens
        self.metrics.completion_tokens += completion_tokens
        self.metrics.total_tokens += prompt_tokens + completion_tokens
        
        if error:
            self.metrics.total_errors += 1
    
    def _make_cache_key(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        **kwargs: Any,
    ) -> str:
        """生成缓存键。"""
        key_data = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            **kwargs,
        }
        key_str = json.dumps(key_data, sort_keys=True, ensure_ascii=False)
        return hashlib.md5(key_str.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Singleton / Factory (for dependency injection)
# ---------------------------------------------------------------------------

_DEFAULT_CLIENT: Optional[LLMClient] = None


def get_default_client(
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> LLMClient:
    """
    获取默认 LLMClient 单例。
    
    首次调用时创建，后续复用。
    """
    global _DEFAULT_CLIENT
    if _DEFAULT_CLIENT is None:
        _DEFAULT_CLIENT = LLMClient(api_key=api_key, model=model)
    return _DEFAULT_CLIENT


def reset_default_client() -> None:
    """重置默认客户端（用于测试）。"""
    global _DEFAULT_CLIENT
    _DEFAULT_CLIENT = None
