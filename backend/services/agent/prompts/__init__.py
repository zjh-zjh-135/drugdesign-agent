"""
Prompts 管理模块（Phase 4）

提供 LangChain 兼容的提示词模板加载与管理。

Usage:
    from .prompts import load_prompt
    
    template = load_prompt("planner_system")
    system_prompt = template.format(
        intent_type="single_action",
        complexity=2,
        conditions_text="无",
        tools_text="...",
        max_steps=8,
    )
"""

import os
import yaml
import re
from typing import Dict, Any, Optional


_PROMPT_DIR = os.path.dirname(os.path.abspath(__file__))


def load_prompt(name: str, version: str = "latest") -> "PromptTemplate":
    """
    加载提示词模板。
    
    Args:
        name: 模板名称（对应 prompts/ 目录下的 YAML 文件名）
        version: 版本号，"latest" 表示最新版
    
    Returns:
        PromptTemplate 对象，支持 format() 方法
    """
    if version == "latest":
        path = os.path.join(_PROMPT_DIR, f"{name}.yaml")
    else:
        path = os.path.join(_PROMPT_DIR, "versions", f"{name}_v{version}.yaml")
    
    if not os.path.exists(path):
        raise FileNotFoundError(f"Prompt template not found: {path}")
    
    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    
    return PromptTemplate(config)


class PromptTemplate:
    """
    提示词模板类。
    
    支持多消息模板（system + user + assistant 等）。
    使用 {variable} 语法进行变量替换，但自动保护 JSON 中的花括号。
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.name = config.get("name", "unnamed")
        self.version = config.get("version", "1.0")
        self.description = config.get("description", "")
        self.variables = config.get("variables", [])
        self.messages = config.get("messages", [])
    
    def format(self, **kwargs) -> str:
        """
        格式化单消息模板（返回字符串）。
        
        适用于只有一条消息的简单模板。
        """
        if not self.messages:
            return ""
        
        content = self.messages[0].get("content", "")
        return self._safe_format(content, **kwargs)
    
    def format_messages(self, **kwargs) -> list:
        """
        格式化多消息模板（返回 OpenAI 风格消息列表）。
        
        Returns:
            [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]
        """
        result = []
        for msg in self.messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            formatted = self._safe_format(content, **kwargs)
            result.append({"role": role, "content": formatted})
        
        return result
    
    def _safe_format(self, content: str, **kwargs) -> str:
        """
        安全格式化：替换 {variable} 但保留 JSON 中的花括号。
        
        策略：先标记 JSON 中的 { 和 }，替换变量，再恢复标记。
        """
        # 简单策略：使用正则替换已知的变量名
        result = content
        for key, value in kwargs.items():
            pattern = r'\{' + re.escape(key) + r'\}'
            result = re.sub(pattern, str(value), result)
        return result
    
    def list_variables(self) -> list:
        """返回模板所需的变量列表。"""
        return self.variables
    
    def __repr__(self) -> str:
        return f"PromptTemplate(name={self.name}, version={self.version})"


# 便捷函数：加载 planner 的完整提示词
def load_planner_prompts(tools_desc: str, intent_context: dict, max_steps: int) -> tuple:
    """
    加载 planner 的系统提示词和用户提示词模板。
    
    Args:
        tools_desc: 工具描述文本
        intent_context: 意图解析上下文
        max_steps: 最大步骤数
    
    Returns:
        (system_prompt: str, user_prompt_template: PromptTemplate)
    """
    # 系统提示词
    system_template = load_prompt("planner_system")
    intent_type = intent_context.get("intent_type", "single_action") if intent_context else "single_action"
    complexity = intent_context.get("estimated_complexity", 2) if intent_context else 2
    conditions = intent_context.get("conditions", []) if intent_context else []
    conditions_text = yaml.dump(conditions, allow_unicode=True) if conditions else "无"
    
    system_prompt = system_template.format(
        intent_type=intent_type,
        complexity=complexity,
        conditions_text=conditions_text,
        tools_text=tools_desc,
        max_steps=max_steps,
    )
    
    # 用户提示词模板（延迟格式化）
    user_template = load_prompt("planner_user")
    
    return system_prompt, user_template


__all__ = [
    "load_prompt",
    "PromptTemplate",
    "load_planner_prompts",
]
