import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# 支持环境变量覆盖数据库路径（Docker/Render 部署用）
DB_PATH = os.environ.get('DB_PATH', os.path.join(BASE_DIR, 'drugdesign.db'))
STATIC_DIR = os.path.join(BASE_DIR, 'static')
MOLECULE_IMG_DIR = os.path.join(STATIC_DIR, 'molecules')

# 确保目录存在
os.makedirs(os.path.dirname(DB_PATH) if os.path.dirname(DB_PATH) else '.', exist_ok=True)
os.makedirs(MOLECULE_IMG_DIR, exist_ok=True)

# 默认过滤阈值
DEFAULT_THRESHOLDS = {
    'mw_min': 250, 'mw_max': 550,
    'clogp_min': 0, 'clogp_max': 5,
    'tpsa_min': 40, 'tpsa_max': 120,
    'hbd_max': 5,
    'hba_max': 10,
    'rotb_max': 10,
    'sa_score_max': 4.5,
}

# 毒性预警SMARTS（简化版）
TOXICITY_PATTERNS = {
    'herg': ['[n+]'],  # 含季铵氮
    'ames': ['c1ccccc1[N+](=O)[O-]', 'c1ccccc1N'],  # 芳香硝基/胺
    'dili': ['c1ccccc1N', 'N-N'],  # 苯胺/肼
}
