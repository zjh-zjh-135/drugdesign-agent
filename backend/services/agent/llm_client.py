"""
llm_client.py - Unified LLM Client for DrugDesign Copilot Agent

Provides a single, reusable LLM client with:
- Unified API configuration (URL, key, model)
- Rate limiting (1s between calls)
- Exponential backoff retry (429/503 auto-retry, 400 no retry)
- Response caching (same prompt/model => 60s TTL)
- Metrics tracking (call count, token usage, latency)
- Stream output support (reserved for Phase 3)

Usage:
    client = LLMClient(api_key=..., model=...)
    response = client.call(messages, temperature=0.3)
    
    # With retry and cache
    response = client.retry_call(messages, max_retries=3, cache_ttl=60)
"""

import json
import os
import time
import hashlib
import logging
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


@dataclass
class LLMMetrics:
    """LLM 调用统计"""
    total_calls: int = 0
    total_tokens: int = 0
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


class LLMClient:
    """
    统一 LLM 客户端。
    
    支持：
    - 统一调用（call）
    - 带重试调用（retry_call）
    - 带缓存调用（cached_call）
    - 流式输出（stream_call，预留）
    - 指标监控（metrics）
    """
    
    # 可重试的 HTTP 状态码
    RETRYABLE_STATUS_CODES = {429, 500, 502, 503}
    
    # 可重试的错误关键词（SSL、连接、超时等网络错误）
    RETRYABLE_ERROR_KEYWORDS = [
        "timeout",
        "connection",
        "ssl",
        "eof",
        "reset",
        "refused",
        "unreachable",
    ]
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        api_url: Optional[str] = None,
        timeout: int = 60,
        rate_limit_interval: float = 1.0,
    ):
        from .config import agent_config
        self.api_key = api_key or agent_config.KIMI_API_KEY
        self.model = model or agent_config.DEFAULT_MODEL
        self.api_url = api_url or agent_config.KIMI_API_URL
        self.timeout = timeout or agent_config.LLM_TIMEOUT
        self.rate_limit_interval = rate_limit_interval or agent_config.LLM_RATE_LIMIT_INTERVAL
        
        # 状态
        self._last_call_time: float = 0.0
        self._cache: Dict[str, CacheEntry] = {}
        self.metrics = LLMMetrics()
        
        # 使用 Session 连接池，提高稳定性
        self._session = requests.Session()
        # 配置适配器：连接池 10，最大连接数 10，允许连接复用
        adapter = HTTPAdapter(
            pool_connections=10,
            pool_maxsize=10,
            max_retries=0,  # 我们自己处理重试，这里关闭 urllib3 的自动重试
        )
        self._session.mount("https://", adapter)
        self._session.mount("http://", adapter)
    
    def __del__(self):
        """析构时关闭 session。"""
        if hasattr(self, "_session") and self._session:
            self._session.close()
    
    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    
    def call(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> str:
        """
        基础调用。不缓存、不重试，只负责统一配置和速率限制。
        
        Args:
            messages: OpenAI-style message list
            temperature: Sampling temperature
            **kwargs: 额外参数（如 top_p, max_tokens 等）
        
        Returns:
            Raw text content from LLM, or error message string.
        """
        if not self.api_key:
            return "API Key 未配置，无法调用 LLM 服务。"
        
        # 速率限制
        self._rate_limit_wait()
        
        # 构建请求
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            **kwargs,
        }
        
        # 记录开始时间
        start_time = time.time()
        
        try:
            resp = self._session.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            
            # 提取内容
            content = (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
            )
            
            # 更新指标
            latency_ms = (time.time() - start_time) * 1000
            self._update_metrics(latency_ms=latency_ms, data=data)
            
            return content
            
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response else 0
            latency_ms = (time.time() - start_time) * 1000
            self._update_metrics(latency_ms=latency_ms, error=True)
            error_msg = f"LLM 调用失败 (HTTP {status_code}): {e}"
            logger.error(error_msg)
            return error_msg
        except requests.exceptions.SSLError as e:
            latency_ms = (time.time() - start_time) * 1000
            self._update_metrics(latency_ms=latency_ms, error=True)
            error_msg = f"LLM 调用失败 (SSL 错误): {e}"
            logger.error(error_msg)
            return error_msg
        except requests.exceptions.ConnectionError as e:
            latency_ms = (time.time() - start_time) * 1000
            self._update_metrics(latency_ms=latency_ms, error=True)
            error_msg = f"LLM 调用失败 (连接错误): {e}"
            logger.error(error_msg)
            return error_msg
        except requests.exceptions.Timeout as e:
            latency_ms = (time.time() - start_time) * 1000
            self._update_metrics(latency_ms=latency_ms, error=True)
            error_msg = f"LLM 调用失败 (超时): {e}"
            logger.error(error_msg)
            return error_msg
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            self._update_metrics(latency_ms=latency_ms, error=True)
            error_msg = f"LLM 调用失败: {e}"
            logger.error(error_msg)
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
        带指数退避重试的调用。
        
        - 429/500/502/503: 自动重试（指数退避）
        - 400/401/403: 不重试（参数错误或权限问题）
        - SSL/连接/超时错误: 自动重试（网络波动）
        - 其他异常: 重试一次
        
        Args:
            max_retries: 最大重试次数（不含第一次）
            base_delay: 初始退避延迟（秒）
        
        Returns:
            Raw text content from LLM, or error message string.
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
            
            # 指数退避等待（SSL 错误额外等待更久，让网络恢复）
            delay = base_delay * (2 ** attempt)
            if "SSL" in result or "连接" in result:
                delay += 1.0  # 网络错误额外等待 1 秒
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
        
        Args:
            cache_ttl: 缓存有效期（秒），默认 60s
        
        Returns:
            Raw text content from LLM or cache.
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
    ):
        """
        流式输出调用（预留接口，Phase 3 实现）。
        
        Returns:
            Generator yielding partial text chunks.
        """
        # Phase 3: 实现流式输出
        # 目前 fallback 到普通调用，返回完整文本
        full_text = self.retry_call(messages, temperature, **kwargs)
        yield full_text
    
    # ------------------------------------------------------------------
    # Metrics & Cache Management
    # ------------------------------------------------------------------
    
    def get_metrics(self) -> Dict[str, Any]:
        """获取当前指标统计。"""
        return {
            "total_calls": self.metrics.total_calls,
            "total_tokens": self.metrics.total_tokens,
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
        # HTTP 可重试状态码
        for code in self.RETRYABLE_STATUS_CODES:
            if f"HTTP {code}" in error_msg:
                return True
        # 网络错误关键词（SSL、连接、超时等）
        error_lower = error_msg.lower()
        for keyword in self.RETRYABLE_ERROR_KEYWORDS:
            if keyword in error_lower:
                return True
        return False
    
    def _update_metrics(
        self,
        latency_ms: float,
        data: Optional[Dict] = None,
        error: bool = False,
    ) -> None:
        """更新指标。"""
        self.metrics.total_calls += 1
        self.metrics.total_latency_ms += latency_ms
        
        if error:
            self.metrics.total_errors += 1
        
        if data and "usage" in data:
            usage = data["usage"]
            self.metrics.total_tokens += usage.get("total_tokens", 0)
    
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
