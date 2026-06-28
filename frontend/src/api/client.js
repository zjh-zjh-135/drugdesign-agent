import axios from 'axios'

// 生产环境自动检测 API 地址
const getBaseURL = () => {
  if (import.meta.env.PROD) {
    // 生产环境：使用完整后端 URL
    // 部署时替换为实际后端地址，例如：
    // return 'https://drugdesign-api.onrender.com/api'
    return import.meta.env.VITE_API_URL || '/api'
  }
  // 开发环境：使用 Vite 代理
  return '/api'
}

const client = axios.create({
  baseURL: getBaseURL(),
  timeout: 120000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器
client.interceptors.request.use(
  (config) => {
    console.log('API请求:', config.method.toUpperCase(), config.url)
    return config
  },
  (error) => {
    console.error('请求错误:', error)
    return Promise.reject(error)
  }
)

// 响应拦截器
client.interceptors.response.use(
  (response) => {
    const data = response.data
    if (!data.success) {
      console.error('API返回错误:', data.error)
    }
    return response
  },
  (error) => {
    const message = error.response?.data?.error || error.message || '网络错误'
    console.error('API错误:', message)
    return Promise.reject(error)
  }
)

export default client

export const api = {
  // 系统
  health: () => client.get('/health'),
  getFilterConfig: () => client.get('/config/filters'),

  // 项目
  listProjects: () => client.get('/projects'),
  createProject: (data) => client.post('/projects', data),
  getProject: (id) => client.get(`/projects/${id}`),
  updateProject: (id, data) => client.put(`/projects/${id}`, data),
  deleteProject: (id) => client.delete(`/projects/${id}`),
  uploadActiveMolecules: (id, data) => client.post(`/projects/${id}/active_molecules`, data),
  // 靶点
  listTargets: (params) => client.get('/targets', { params }),
  getTargetDetail: (targetName) => client.get(`/targets/${encodeURIComponent(targetName)}`),
  getTargetCandidates: (targetName) => client.get(`/targets/${encodeURIComponent(targetName)}/candidates`),
  batchAddActiveMolecules: (projectId, data) => client.post(`/projects/${projectId}/active_molecules/batch`, data),

  // 分子
  listMolecules: (projectId, params) => client.get(`/projects/${projectId}/molecules`, { params }),
  getMolecule: (id) => client.get(`/molecules/${id}`),
  getMoleculeSvg: (id) => `/api/molecules/${id}/svg`,
  batchUploadMolecules: (data) => client.post('/molecules/batch', data),
  deleteMolecule: (id) => client.delete(`/molecules/${id}`),
  filterMolecules: (data) => client.post('/molecules/filter', data),
  computeSimilarity: (data) => client.post('/molecules/similarity', data),

  // 生成
  generateMolecules: (projectId, data) => client.post(`/projects/${projectId}/generate`, data),
  getGenerationStatus: (jobId) => client.get(`/generate/status/${jobId}`),

  // ADMET
  getAdmet: (id) => client.get(`/molecules/${id}/admet`),
  batchAdmet: (data) => client.post('/molecules/batch_admet', data),
  analyzeAdmet: (data) => client.post('/admet/analyze', data),

  // 合成
  analyzeSynthesis: (id) => client.post(`/molecules/${id}/synthesis`),
  analyzeSynthesisFromSmiles: (data) => client.post('/synthesis/analyze', data),
  getSynthesisStatus: (jobId) => client.get(`/synthesis/status/${jobId}`),
  getSynthesisResults: (jobId) => client.get(`/synthesis/results/${jobId}`),

  // Pipeline
  runPipeline: (data) => client.post('/pipeline/run', data),
  getPipelineStatus: (runId) => client.get(`/pipeline/status/${runId}`),
  getPipelineResults: (runId, params) => client.get(`/pipeline/results/${runId}`, { params }),

  // 3D结构
  getMoleculeStructure: (id, format = 'sdf') => `/api/molecules/${id}/structure?format=${format}`,
  getMoleculeStructure3d: (id) => client.get(`/molecules/${id}/structure3d`),
  getStructureFromSmiles: (data) => client.post('/molecules/structure/from_smiles', data),

  // 3D结构
  getMoleculeStructure: (id, format = 'sdf') => `/api/molecules/${id}/structure?format=${format}`,
  getMoleculeStructure3d: (id) => client.get(`/molecules/${id}/structure3d`),
  getStructureFromSmiles: (data) => client.post('/molecules/structure/from_smiles', data),

  // 分子对接
  dockMolecule: (id, data) => client.post(`/molecules/${id}/dock`, data),
  batchDock: (data) => client.post('/docking/batch', data),
  dockFromSmiles: (data) => client.post('/docking/from_smiles', data),
  getVinaStatus: () => client.get('/docking/vina_status'),
  fetchPdb: (pdbId) => client.get(`/docking/fetch_pdb/${pdbId}`),

  // 活性预测
  predictActivity: (data) => client.post('/activity/predict', data),
  predictBatchActivity: (data) => client.post('/activity/predict_batch', data),
  trainActivityModel: (data) => client.post('/activity/train', data),
  listActivityModels: () => client.get('/activity/models'),

  // 实验验证与数据回流
  listAssayResults: (projectId) => client.get(`/projects/${projectId}/assay_results`),
  createAssayResult: (projectId, data) => client.post(`/projects/${projectId}/assay_results`, data),
  updateAssayResult: (assayId, data) => client.put(`/assay_results/${assayId}`, data),
  applyFeedback: (assayId) => client.post(`/assay_results/${assayId}/feedback`),
  getFeedbackStats: (projectId) => client.get(`/projects/${projectId}/feedback_stats`),

  // 失败分子库
  getFailedMolecules: (projectId, params) => client.get(`/projects/${projectId}/failed-molecules`, { params }),
  getFailedAnalysis: (projectId) => client.get(`/projects/${projectId}/failed-analysis`),
  getFailedMoleculeDetail: (projectId, moleculeId) => client.get(`/projects/${projectId}/failed-molecules/${moleculeId}`),

  // AI助手
  aiChat: (data) => client.post('/ai_chat', data),

  // Agent Copilot
  agentChat: (data) => client.post('/agent/chat', data),
  agentGoal: (data) => client.post('/agent/goal', data),  // 自主 Agent 目标执行
  agentExecute: (data) => client.post('/agent/execute', data),
  listAgentSessions: () => client.get('/agent/sessions'),
  getAgentSessionMessages: (sessionId) => client.get(`/agent/sessions/${sessionId}/messages`),
  deleteAgentSession: (sessionId) => client.delete(`/agent/sessions/${sessionId}`),
  getProjectMemory: (projectId, params) => client.get(`/agent/projects/${projectId}/memory`, { params }),
  saveProjectMemory: (projectId, data) => client.post(`/agent/projects/${projectId}/memory`, data),
  getProjectSummary: (projectId) => client.get(`/agent/projects/${projectId}/summary`),
  listAgentTools: () => client.get('/agent/tools'),
  getTopMolecules: (projectId, limit = 10) => client.get(`/projects/${projectId}/top-molecules`, { params: { limit } }),
  
  // Phase 5: Agent 追踪
  getAgentTraces: (params) => client.get('/agent/traces', { params }),
  getAgentTraceDetail: (traceId) => client.get(`/agent/traces/${traceId}`),
  clearAgentTraces: () => client.delete('/agent/traces'),
}
