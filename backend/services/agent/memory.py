"""
三层记忆系统：Buffer Memory + Project Memory + Long-term Memory
"""
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
import json

# 从 database.py 导入模型（避免重复定义）
from ...models.database import (
    AgentSession, AgentMessage, AgentMemory, LongTermMemory
)

# ========== 记忆操作函数 ==========

def get_or_create_session(db, session_id: str, project_id: int = None, title: str = None) -> AgentSession:
    """获取或创建会话"""
    session = db.query(AgentSession).filter(AgentSession.session_id == session_id).first()
    if not session:
        session = AgentSession(
            session_id=session_id,
            project_id=project_id,
            title=title or "新对话"
        )
        db.add(session)
        db.commit()
    return session

def save_message(db, session_id: str, role: str, content: str, 
               project_id: int = None, metadata: Dict = None) -> AgentMessage:
    """保存消息到对话历史"""
    msg = AgentMessage(
        session_id=session_id,
        role=role,
        content=content,
        project_id=project_id,
        metadata_json=metadata or {}
    )
    db.add(msg)
    db.commit()
    return msg

def get_conversation_history(db, session_id: str, limit: int = 20, max_tokens: int = 4000) -> List[Dict]:
    """获取最近 N 条对话历史，支持 Token 预算控制。
    
    Args:
        max_tokens: 最大 token 预算，超出时对早期消息做摘要或截断。
    """
    messages = db.query(AgentMessage).filter(
        AgentMessage.session_id == session_id
    ).order_by(AgentMessage.created_at.desc()).limit(limit).all()
    
    messages = list(reversed(messages))  # 按时间正序
    
    result = []
    total_chars = 0
    # 简单估算：每字符约 0.5 token（混合中英文）
    for m in messages:
        content_len = len(m.content) if m.content else 0
        total_chars += content_len
    
    # 如果超出预算，只保留最近的消息
    estimated_tokens = total_chars * 0.5
    if estimated_tokens > max_tokens and len(messages) > 5:
        # 保留最近 5 条完整，其余丢弃
        messages = messages[-5:]
    
    return [
        {
            "role": m.role,
            "content": m.content,
            "metadata": m.metadata_json,
            "created_at": m.created_at.isoformat()
        }
        for m in messages
    ]

def save_project_memory(db, project_id: int, memory_type: str, key: str, 
                       value: Any, importance: int = 1):
    """保存项目级记忆"""
    # 检查是否已存在
    existing = db.query(AgentMemory).filter(
        AgentMemory.project_id == project_id,
        AgentMemory.key == key
    ).first()
    
    if existing:
        existing.value = json.dumps(value, ensure_ascii=False)
        existing.importance = max(existing.importance, importance)
        existing.created_at = datetime.now()
    else:
        mem = AgentMemory(
            project_id=project_id,
            memory_type=memory_type,
            key=key,
            value=json.dumps(value, ensure_ascii=False),
            importance=importance
        )
        db.add(mem)
    
    db.commit()

def get_session_project_id(db, session_id: str) -> Optional[int]:
    """从会话中推断当前项目ID（支持记忆持久化）"""
    session = db.query(AgentSession).filter(AgentSession.session_id == session_id).first()
    if session and session.project_id:
        return session.project_id
    
    # 如果 session 没有 project_id，查找该 session 最近的消息中关联的 project_id
    latest_msg = db.query(AgentMessage).filter(
        AgentMessage.session_id == session_id,
        AgentMessage.project_id.isnot(None)
    ).order_by(AgentMessage.created_at.desc()).first()
    
    if latest_msg and latest_msg.project_id:
        return latest_msg.project_id
    
    return None

def update_session_project_id(db, session_id: str, project_id: int):
    """更新会话关联的项目ID"""
    session = db.query(AgentSession).filter(AgentSession.session_id == session_id).first()
    if session:
        session.project_id = project_id
        db.commit()
    return session

def get_project_memory(db, project_id: int, key: str = None, 
                       memory_type: str = None, limit: int = 50) -> List[Dict]:
    """获取项目记忆"""
    query = db.query(AgentMemory).filter(AgentMemory.project_id == project_id)
    
    if key:
        query = query.filter(AgentMemory.key == key)
    if memory_type:
        query = query.filter(AgentMemory.memory_type == memory_type)
    
    results = query.order_by(AgentMemory.importance.desc(), 
                            AgentMemory.created_at.desc()).limit(limit).all()
    
    return [
        {
            "key": r.key,
            "type": r.memory_type,
            "value": json.loads(r.value) if r.value else None,
            "importance": r.importance,
            "created_at": r.created_at.isoformat()
        }
        for r in results
    ]

def get_project_summary(db, project_id: int) -> Dict[str, Any]:
    """
    获取项目记忆摘要，供 Agent 在思考时参考
    """
    from ...models.database import Project, PipelineRun, GeneratedMolecule
    
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return {}
    
    # 最近运行
    latest_run = db.query(PipelineRun).filter(
        PipelineRun.project_id == project_id
    ).order_by(PipelineRun.start_time.desc()).first()
    
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
    
    # 记忆
    memories = get_project_memory(db, project_id, limit=10)
    
    return {
        "project_name": project.name,
        "target": project.target_pdb,
        "design_goal": project.design_goal,
        "latest_pipeline_id": latest_run.id if latest_run else None,
        "latest_pipeline_status": latest_run.status if latest_run else None,
        "total_molecules": total,
        "failed_molecules": failed,
        "passed_molecules": passed,
        "recent_memories": memories
    }

def save_long_term_memory(db, category: str, key: str, value: Any, 
                          tags: List[str] = None, project_id: int = None):
    """保存长期记忆"""
    existing = db.query(LongTermMemory).filter(
        LongTermMemory.category == category,
        LongTermMemory.key == key
    ).first()
    
    if existing:
        existing.value = json.dumps(value, ensure_ascii=False)
        existing.use_count += 1
        existing.last_accessed = datetime.now()
        if tags:
            existing.tags = list(set((existing.tags or []) + tags))
    else:
        mem = LongTermMemory(
            category=category,
            key=key,
            value=json.dumps(value, ensure_ascii=False),
            tags=tags or [],
            project_id=project_id
        )
        db.add(mem)
    
    db.commit()

def search_long_term_memory(db, query: str, category: str = None, limit: int = 10) -> List[Dict]:
    """搜索长期记忆（简单关键词匹配）"""
    q = db.query(LongTermMemory)
    
    if category:
        q = q.filter(LongTermMemory.category == category)
    
    # 简单 LIKE 搜索
    q = q.filter(
        (LongTermMemory.key.contains(query)) | 
        (LongTermMemory.value.contains(query)) |
        (LongTermMemory.tags.contains(query))
    )
    
    results = q.order_by(LongTermMemory.use_count.desc(),
                        LongTermMemory.last_accessed.desc()).limit(limit).all()
    
    return [
        {
            "category": r.category,
            "key": r.key,
            "value": json.loads(r.value) if r.value else None,
            "tags": r.tags,
            "use_count": r.use_count
        }
        for r in results
    ]


# ============================================================================
# Phase 3: LangChain 记忆兼容层（新增，不影响原有代码）
# ============================================================================

"""
LangChain 记忆标准化接口

在原有数据库记忆基础上，提供 LangChain 兼容的 Memory 对象，
可接入 LangChain Chain、Agent 等生态组件。

原有接口（save_message / get_conversation_history）完全保留。

注意：LangChain 1.x 已重构 Memory 体系，这里不继承 BaseMemory，
      而是提供与 LangChain 0.x 兼容的接口（load_memory_variables / save_context / clear）。
"""

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage


class AgentConversationMemory:
    """
    LangChain 兼容的对话记忆管理器。
    
    底层使用数据库持久化，上层提供与 LangChain 兼容的接口。
    """
    
    def __init__(self, session_id: str, db=None, max_token_limit: int = 4000):
        self.memory_key = "chat_history"
        self.session_id = session_id
        self.db = db
        self._max_token_limit = max_token_limit
    
    @property
    def memory_variables(self) -> List[str]:
        """返回记忆变量名列表。"""
        return [self.memory_key]
    
    def load_memory_variables(self, inputs: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        加载记忆变量。
        
        Returns:
            {memory_key: [HumanMessage, AIMessage, ...]}
        """
        if not self.db or not self.session_id:
            return {self.memory_key: []}
        
        # 使用原有函数获取历史
        history = get_conversation_history(
            self.db, self.session_id, limit=20, max_tokens=self._max_token_limit
        )
        
        # 转换为 LangChain 消息对象
        lc_messages = []
        for msg in history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                lc_messages.append(SystemMessage(content=content))
            elif role == "assistant":
                lc_messages.append(AIMessage(content=content))
            else:
                lc_messages.append(HumanMessage(content=content))
        
        return {self.memory_key: lc_messages}
    
    def save_context(self, inputs: Dict[str, Any], outputs: Dict[str, str]) -> None:
        """
        保存对话上下文。
        
        Args:
            inputs: 通常包含 {"input": "用户输入"}
            outputs: 通常包含 {"output": "助手回复"}
        """
        if not self.db or not self.session_id:
            return
        
        # 保存用户输入
        user_input = inputs.get("input", "")
        if user_input:
            save_message(self.db, self.session_id, "user", user_input)
        
        # 保存助手输出
        assistant_output = outputs.get("output", "")
        if assistant_output:
            save_message(self.db, self.session_id, "assistant", assistant_output)
    
    def clear(self) -> None:
        """清空记忆。"""
        # 数据库层面不删除，仅标记
        if self.db and self.session_id:
            save_message(self.db, self.session_id, "system", "[Memory cleared]")


class AgentSummaryMemory:
    """
    LangChain 兼容的摘要记忆管理器。
    
    当对话历史超过 token 限制时，自动对早期消息生成摘要。
    """
    
    def __init__(self, session_id: str, db=None, llm_client=None):
        self.memory_key = "summary"
        self.session_id = session_id
        self.db = db
        self.llm_client = llm_client  # LLMClient 实例，用于生成摘要
    
    @property
    def memory_variables(self) -> List[str]:
        return [self.memory_key]
    
    def load_memory_variables(self, inputs: Dict[str, Any] = None) -> Dict[str, Any]:
        """加载摘要记忆。"""
        if not self.db or not self.session_id:
            return {self.memory_key: ""}
        
        # 获取历史并检查是否需要摘要
        history = get_conversation_history(self.db, self.session_id, limit=50)
        
        # 简单估算 token
        total_chars = sum(len(m.get("content", "")) for m in history)
        estimated_tokens = total_chars * 0.5
        
        # 如果超过预算，生成摘要
        if estimated_tokens > 4000 and len(history) > 5 and self.llm_client:
            early_messages = history[:-5]  # 早期消息
            summary = self._generate_summary(early_messages)
            return {self.memory_key: summary}
        
        return {self.memory_key: ""}
    
    def _generate_summary(self, messages: List[Dict]) -> str:
        """使用 LLM 生成摘要。"""
        content = "\n".join([f"{m['role']}: {m['content'][:100]}" for m in messages])
        prompt = f"请对以下对话历史进行简要摘要（100字以内）：\n\n{content}"
        try:
            return self.llm_client.call([{"role": "user", "content": prompt}], temperature=0.3)
        except Exception:
            return "[对话历史摘要]"
    
    def save_context(self, inputs: Dict[str, Any], outputs: Dict[str, str]) -> None:
        """摘要记忆不需要每次保存，由数据库层处理。"""
        pass
    
    def clear(self) -> None:
        """清空摘要。"""
        pass


# ── 便捷工厂函数 ──

def create_langchain_memory(session_id: str, db=None, llm_client=None) -> Dict[str, Any]:
    """
    创建一套 LangChain 兼容的记忆对象。
    
    Returns:
        {
            "conversation": AgentConversationMemory,  # 短期对话记忆
            "summary": AgentSummaryMemory,             # 长期摘要记忆
        }
    """
    return {
        "conversation": AgentConversationMemory(session_id=session_id, db=db),
        "summary": AgentSummaryMemory(session_id=session_id, db=db, llm_client=llm_client),
    }


# 原有导出 + Phase 3 新增
__all__ = [
    # 原有接口
    "get_or_create_session",
    "save_message",
    "get_conversation_history",
    "save_project_memory",
    "get_project_memory",
    "get_project_summary",
    "save_long_term_memory",
    "search_long_term_memory",
    # Phase 3 新增
    "AgentConversationMemory",
    "AgentSummaryMemory",
    "create_langchain_memory",
]
