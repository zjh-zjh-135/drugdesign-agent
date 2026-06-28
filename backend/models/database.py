from datetime import datetime
import json
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, ForeignKey, Boolean
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from sqlalchemy import JSON
from sqlalchemy.pool import StaticPool
from ..config import DB_PATH

Base = declarative_base()

class Project(Base):
    __tablename__ = 'projects'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    target_name = Column(String(200))
    target_pdb = Column(String(20))
    description = Column(Text)
    design_goal = Column(String(100))  # hit_finding, lead_optimization, scaffold_hopping
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    filter_params = Column(JSON, default=lambda: {
        'mw_min': 200, 'mw_max': 600,
        'clogp_min': -1, 'clogp_max': 6,
        'tpsa_min': 20, 'tpsa_max': 140,
        'hbd_max': 6, 'hba_max': 12,
        'rotb_max': 12, 'sa_score_max': 5.5,
    })
    
    active_molecules = relationship("ActiveMolecule", back_populates="project", cascade="all, delete-orphan")
    generated_molecules = relationship("GeneratedMolecule", back_populates="project", cascade="all, delete-orphan")
    pipeline_runs = relationship("PipelineRun", back_populates="project", cascade="all, delete-orphan")
    assay_results = relationship("AssayResult", back_populates="project", cascade="all, delete-orphan")

class ActiveMolecule(Base):
    __tablename__ = 'active_molecules'
    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False)
    smiles = Column(String(1000), nullable=False)
    name = Column(String(200))
    ic50 = Column(Float)
    activity_type = Column(String(50))  # IC50, Ki, EC50
    source = Column(String(200))
    created_at = Column(DateTime, default=datetime.now)
    
    project = relationship("Project", back_populates="active_molecules")

class GeneratedMolecule(Base):
    __tablename__ = 'generated_molecules'
    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False)
    smiles = Column(String(1000), nullable=False)
    inchi = Column(String(2000))
    generated_from = Column(String(1000))  # 来源SMILES
    generation_strategy = Column(String(50))  # crem, rdkit, scaffold
    generation_step = Column(Integer, default=0)
    pipeline_status = Column(String(50), default='generated')  # generated, filtered, structure_screened, admet_passed, refined, synthesis_passed, failed
    pipeline_run_id = Column(Integer, ForeignKey('pipeline_runs.id'), nullable=True)  # 关联 PipelineRun
    failure_reason = Column(Text)  # 失败原因 JSON 描述
    failure_stage = Column(String(50))  # 失败阶段
    failed_at = Column(DateTime, nullable=True)  # 失败时间
    created_at = Column(DateTime, default=datetime.now)
    
    project = relationship("Project", back_populates="generated_molecules")
    properties = relationship("MoleculeProperty", back_populates="molecule", uselist=False, cascade="all, delete-orphan")
    admet = relationship("AdmetPrediction", back_populates="molecule", uselist=False, cascade="all, delete-orphan")
    synthesis_routes = relationship("SynthesisRoute", back_populates="molecule", cascade="all, delete-orphan")
    assay_results = relationship("AssayResult", back_populates="molecule", cascade="all, delete-orphan")
    pipeline_run = relationship("PipelineRun", back_populates="generated_molecules")

class MoleculeProperty(Base):
    __tablename__ = 'molecule_properties'
    id = Column(Integer, primary_key=True, autoincrement=True)
    molecule_id = Column(Integer, ForeignKey('generated_molecules.id'), nullable=False)
    mw = Column(Float)
    clogp = Column(Float)
    tpsa = Column(Float)
    hbd = Column(Integer)
    hba = Column(Integer)
    rotb = Column(Integer)
    sa_score = Column(Float)
    qed = Column(Float)
    pass_pains = Column(Boolean)
    pass_filters = Column(Boolean)
    pass_admet = Column(Boolean)
    similarity_score = Column(Float)
    docking_score = Column(Float)
    pose_rmsd = Column(Float)
    mmgbsa_score = Column(Float)
    fep_ddg = Column(Float)
    interaction_score = Column(Float)
    overall_fep_rank = Column(Integer)
    failure_reason = Column(Text)  # 失败原因详细描述
    failure_stage = Column(String(50))  # 失败阶段
    
    molecule = relationship("GeneratedMolecule", back_populates="properties")

class AdmetPrediction(Base):
    __tablename__ = 'admet_predictions'
    id = Column(Integer, primary_key=True, autoincrement=True)
    molecule_id = Column(Integer, ForeignKey('generated_molecules.id'), nullable=False)
    solubility = Column(Float)  # 0-100
    permeability = Column(Float)
    bbb = Column(Float)  # 血脑屏障通透性
    herg = Column(Float)  # hERG抑制风险 0-1
    ames = Column(Float)  # Ames突变风险 0-1
    dili = Column(Float)  # DILI风险 0-1
    cyp_inhibition = Column(Float)
    oral_bioavailability = Column(Float)
    overall_score = Column(Float)
    
    molecule = relationship("GeneratedMolecule", back_populates="admet")

class SynthesisRoute(Base):
    __tablename__ = 'synthesis_routes'
    id = Column(Integer, primary_key=True, autoincrement=True)
    molecule_id = Column(Integer, ForeignKey('generated_molecules.id'), nullable=False)
    route_json = Column(Text)
    num_steps = Column(Integer)
    estimated_cost = Column(Float)
    availability_score = Column(Float)
    status = Column(String(50), default='pending')
    created_at = Column(DateTime, default=datetime.now)
    
    molecule = relationship("GeneratedMolecule", back_populates="synthesis_routes")

class PipelineRun(Base):
    __tablename__ = 'pipeline_runs'
    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False)
    status = Column(String(50), default='pending')  # pending, running, completed, failed
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    num_generated = Column(Integer, default=0)
    num_filtered = Column(Integer, default=0)
    num_passed = Column(Integer, default=0)
    num_failed = Column(Integer, default=0)  # 失败分子数量
    params_json = Column(JSON)
    
    project = relationship("Project", back_populates="pipeline_runs")
    generated_molecules = relationship("GeneratedMolecule", back_populates="pipeline_run")

class AssayResult(Base):
    """实验验证结果 - 数据回流核心表"""
    __tablename__ = 'assay_results'
    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False)
    molecule_id = Column(Integer, ForeignKey('generated_molecules.id'), nullable=True)  # 关联生成分子
    smiles = Column(String(1000), nullable=False)
    name = Column(String(200))  # 分子名称
    assay_type = Column(String(50), default='IC50')  # IC50, Ki, EC50, KD
    predicted_value = Column(Float)  # AI预测值
    actual_value = Column(Float)  # 实验实测值
    unit = Column(String(50), default='nM')  # nM, uM, mM
    status = Column(String(50), default='pending')  # pending, running, completed, cancelled
    notes = Column(Text)  # 实验备注
    feedback_applied = Column(Boolean, default=False)  # 是否已回流到下一轮
    error_rate = Column(Float)  # 预测误差率 = |pred-actual|/actual
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    project = relationship("Project", back_populates="assay_results")
    molecule = relationship("GeneratedMolecule", back_populates="assay_results")


# ========== Agent 记忆表 ==========

class AgentSession(Base):
    """Agent 会话表 - Buffer Memory"""
    __tablename__ = 'agent_sessions'
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(100), unique=True, nullable=False, index=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=True)
    title = Column(String(200), default="新对话")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    messages = relationship("AgentMessage", back_populates="session", cascade="all, delete-orphan")
    project = relationship("Project")

class AgentMessage(Base):
    """Agent 消息表 - 对话历史"""
    __tablename__ = 'agent_messages'
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(100), ForeignKey('agent_sessions.session_id'), nullable=False, index=True)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=True)
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.now)
    
    session = relationship("AgentSession", back_populates="messages")

class AgentMemory(Base):
    """项目记忆表 - Project Memory"""
    __tablename__ = 'agent_memory'
    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False, index=True)
    memory_type = Column(String(50), nullable=False)
    key = Column(String(200), nullable=False)
    value = Column(Text, nullable=False)
    importance = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.now)
    
    project = relationship("Project")

class LongTermMemory(Base):
    """长期记忆表 - Long-term Memory"""
    __tablename__ = 'long_term_memory'
    id = Column(Integer, primary_key=True, autoincrement=True)
    category = Column(String(100), nullable=False)
    key = Column(String(200), nullable=False)
    value = Column(Text, nullable=False)
    tags = Column(JSON, default=list)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=True)
    use_count = Column(Integer, default=0)
    last_accessed = Column(DateTime, default=datetime.now)
    created_at = Column(DateTime, default=datetime.now)


# ========== 数据库迁移 ==========

def init_db():
    # 增加SQLite超时，避免并发锁冲突
    # P0修复: 使用NullPool替代StaticPool，避免多线程共享同一连接
    engine = create_engine(
        f'sqlite:///{DB_PATH}',
        echo=False,
        connect_args={'timeout': 30},
        poolclass=NullPool
    )
    Base.metadata.create_all(engine)
    
    # === 数据库迁移：为旧表添加缺失的字段 ===
    from sqlalchemy import inspect, text
    inspector = inspect(engine)
    
    # 1. generated_molecules 表新增字段
    gm_cols = {c['name'] for c in inspector.get_columns('generated_molecules')}
    with engine.begin() as conn:
        if 'pipeline_run_id' not in gm_cols:
            conn.execute(text("ALTER TABLE generated_molecules ADD COLUMN pipeline_run_id INTEGER"))
        if 'failure_reason' not in gm_cols:
            conn.execute(text("ALTER TABLE generated_molecules ADD COLUMN failure_reason TEXT"))
        if 'failure_stage' not in gm_cols:
            conn.execute(text("ALTER TABLE generated_molecules ADD COLUMN failure_stage VARCHAR(50)"))
        if 'failed_at' not in gm_cols:
            conn.execute(text("ALTER TABLE generated_molecules ADD COLUMN failed_at DATETIME"))
    
    # 2. molecule_properties 表新增字段
    mp_cols = {c['name'] for c in inspector.get_columns('molecule_properties')}
    with engine.begin() as conn:
        if 'failure_reason' not in mp_cols:
            conn.execute(text("ALTER TABLE molecule_properties ADD COLUMN failure_reason TEXT"))
        if 'failure_stage' not in mp_cols:
            conn.execute(text("ALTER TABLE molecule_properties ADD COLUMN failure_stage VARCHAR(50)"))
    
    # 3. pipeline_runs 表新增字段
    # SECURITY NOTE: 以下 ALTER TABLE 语句使用静态字符串，不依赖用户输入。
    # 列名通过 SQLAlchemy inspect 获取，不存在 SQL 注入风险。
    pr_cols = {c['name'] for c in inspector.get_columns('pipeline_runs')}
    with engine.begin() as conn:
        if 'num_failed' not in pr_cols:
            conn.execute(text("ALTER TABLE pipeline_runs ADD COLUMN num_failed INTEGER DEFAULT 0"))
    
    # === 4. Agent 记忆表创建（新版本首次初始化）===
    # 这些表在 Base.metadata.create_all 中已自动创建
    # 以下为旧版本兼容：如不存在则创建
    from sqlalchemy import MetaData
    meta = MetaData()
    meta.reflect(bind=engine)
    required_tables = {'agent_sessions', 'agent_messages', 'agent_memory', 'long_term_memory', 'audit_logs'}
    existing_tables = set(meta.tables.keys())
    missing = required_tables - existing_tables
    if missing:
        # 只创建缺失的表，保留已有数据
        Base.metadata.create_all(engine, tables=[
            Base.metadata.tables[t] for t in missing if t in Base.metadata.tables
        ])
    
    return sessionmaker(bind=engine, expire_on_commit=False)
