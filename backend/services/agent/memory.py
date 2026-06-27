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

def get_conversation_history(db, session_id: str, limit: int = 20) -> List[Dict]:
    """获取最近 N 条对话历史"""
    messages = db.query(AgentMessage).filter(
        AgentMessage.session_id == session_id
    ).order_by(AgentMessage.created_at.desc()).limit(limit).all()
    
    return [
        {
            "role": m.role,
            "content": m.content,
            "metadata": m.metadata_json,
            "created_at": m.created_at.isoformat()
        }
        for m in reversed(messages)  # 按时间正序
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
