"""
config.py - Centralized configuration for DrugDesign Copilot Agent

All hardcoded constants from engine.py, planner.py, executor.py, intent_parser.py
are consolidated here. Supports environment variable overrides.

Usage:
    from .config import agent_config
    model = agent_config.DEFAULT_MODEL
    timeout = agent_config.STEP_TIMEOUT
"""

import os
from typing import Optional


class AgentConfig:
    """Agent configuration with environment variable support."""
    
    # LLM API
    KIMI_API_KEY: str = os.environ.get("KIMI_API_KEY", "")
    KIMI_API_URL: str = os.environ.get("KIMI_API_URL", "https://api.moonshot.cn/v1/chat/completions")
    DEFAULT_MODEL: str = os.environ.get("KIMI_DEFAULT_MODEL", "moonshot-v1-8k")
    
    # Agent behavior
    MAX_STEPS: int = int(os.environ.get("KIMI_MAX_STEPS", "10"))
    DEFAULT_TEMPERATURE: float = float(os.environ.get("KIMI_DEFAULT_TEMPERATURE", "0.3"))
    CHAT_TEMPERATURE: float = float(os.environ.get("KIMI_CHAT_TEMPERATURE", "0.7"))
    
    # LLM client
    LLM_TIMEOUT: int = int(os.environ.get("KIMI_LLM_TIMEOUT", "60"))
    LLM_CACHE_TTL: int = int(os.environ.get("KIMI_LLM_CACHE_TTL", "60"))
    LLM_RATE_LIMIT_INTERVAL: float = float(os.environ.get("KIMI_LLM_RATE_LIMIT", "1.0"))
    LLM_MAX_RETRIES: int = int(os.environ.get("KIMI_LLM_MAX_RETRIES", "3"))
    LLM_RETRY_BASE_DELAY: float = float(os.environ.get("KIMI_LLM_RETRY_DELAY", "1.0"))
    
    # Execution
    STEP_TIMEOUT: int = int(os.environ.get("KIMI_STEP_TIMEOUT", "30"))
    MAX_RETRIES: int = int(os.environ.get("KIMI_MAX_RETRIES", "2"))
    LLM_CALL_INTERVAL: float = float(os.environ.get("KIMI_LLM_CALL_INTERVAL", "1.0"))
    
    # Pipeline
    PIPELINE_MAX_WAIT: int = int(os.environ.get("KIMI_PIPELINE_MAX_WAIT", "300"))
    PIPELINE_POLL_INTERVAL: int = int(os.environ.get("KIMI_PIPELINE_POLL_INTERVAL", "3"))
    PIPELINE_EXECUTOR_TIMEOUT: int = int(os.environ.get("KIMI_PIPELINE_EXEC_TIMEOUT", "10"))
    
    # External APIs
    PUBCHEM_TIMEOUT: int = int(os.environ.get("KIMI_PUBCHEM_TIMEOUT", "10"))
    PUBCHEM_MAX_WORKERS: int = int(os.environ.get("KIMI_PUBCHEM_MAX_WORKERS", "5"))
    
    # Cache
    INTENT_CACHE_TTL: int = int(os.environ.get("KIMI_INTENT_CACHE_TTL", "60"))
    PERCEPTION_CACHE_TTL: int = int(os.environ.get("KIMI_PERCEPTION_CACHE_TTL", "10"))
    
    # Memory
    CONVERSATION_HISTORY_LIMIT: int = int(os.environ.get("KIMI_CONV_HISTORY_LIMIT", "20"))
    CONVERSATION_TOKEN_BUDGET: int = int(os.environ.get("KIMI_CONV_TOKEN_BUDGET", "4000"))
    
    # Debug
    DEBUG: bool = os.environ.get("KIMI_AGENT_DEBUG", "").lower() in ("true", "1", "yes")
    
    def to_dict(self) -> dict:
        """Export all config values as dict."""
        return {
            k: v for k, v in self.__class__.__dict__.items() 
            if not k.startswith("_") and not callable(v)
        }


# Global singleton
agent_config = AgentConfig()
