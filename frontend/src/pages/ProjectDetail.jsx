import React, { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Play, Upload, FlaskConical, ChevronRight, TestTube, BarChart3, RotateCcw } from 'lucide-react'
import { api } from '../api/client'
import { useApp } from '../store/AppContext'
import LoadingSpinner from '../components/LoadingSpinner'
import MoleculeSVG from '../components/MoleculeSVG'

const designGoalLabels = {
  'lead_optimization': 'Lead优化',
  'hit_finding': 'Hit发现',
  'scaffold_hopping': '骨架跃迁',
  'selectivity': '选择性优化',
}

const designGoalDescriptions = {
  'lead_optimization': '在已有先导化合物（hit/lead）基础上，通过系统性的结构修饰来优化分子的综合成药性（ADMET性质）、提高靶点结合活性（IC50/Ki值降低）、改善选择性（降低脱靶风险）。这是药物发现中最常见、最耗时的阶段，通常需要多轮设计-合成-测试-分析（DMTA）循环。',
  'hit_finding': '从零开始发现全新先导化合物，适用于全新靶点（first-in-class）或缺乏已知活性分子的情况。常用策略包括：高通量虚拟筛选（HTVS）、基于片段的筛选（FBDD）、DNA编码化合物库（DEL）筛选、以及AI生成模型大规模枚举。',
  'scaffold_hopping': '保留原分子的关键药效团（pharmacophore），但替换核心骨架结构（scaffold）。目的包括：①规避现有化合物专利壁垒，获得全新知识产权；②改善物化性质（如溶解度、代谢稳定性）；③降低毒性风险。',
  'selectivity': '针对激酶家族、GPCR家族等同源性高的靶点，优化化合物对目标靶点A的选择性同时降低对靶点B/C/D的脱靶效应。策略包括利用不同亚型结合口袋中的非保守氨基酸残基差异，引入特定取代基形成选择性相互作用。',
}

// 靶点 -> 已知活性分子候选库
const targetMoleculeLibrary = {
  'BRAF V600E': [
    { name: '维莫非尼 (Vemurafenib)', smiles: 'CC(C)Oc1ccc(-c2nc3ccccc3o2)cc1NC(=O)c1cccnc1Cl', ic50: 0.031 },
    { name: '达拉非尼 (Dabrafenib)', smiles: 'CC(C)Nc1nc(Nc2ccccc2S(=O)(=O)C(C)C)ncc1C(=O)NCCN1CCOCC1', ic50: 0.005 },
  ],
  'EGFR T790M': [
    { name: '吉非替尼 (Gefitinib)', smiles: 'COc1cc2ncnc(Nc3ccc(F)c(Cl)c3)c2cc1O', ic50: 0.033 },
    { name: '厄洛替尼 (Erlotinib)', smiles: 'COC(=O)c1cc2ncnc(Nc3ccc(Oc4ccccc4)c(C)c3)c2cc1O', ic50: 0.002 },
    { name: '奥希替尼 (Osimertinib)', smiles: 'COC(=O)c1cc(Nc2ncnc3cc(OC)ccc23)c(=O)n(C)c1', ic50: 0.015 },
  ],
  'KRAS G12C': [
    { name: 'Sotorasib', smiles: 'C=CC(=O)Nc1cc(Nc2nccc(-c3cn(C)c4ccccc34)n2)cc(C(C)(C)C)c1', ic50: 0.0009 },
    { name: 'Adagrasib', smiles: 'C=CC(=O)Nc1cccc(Oc2nc(Nc3ccc(C(=O)Nc4ccccn4)cc3)nc3c2cnn3C)c1', ic50: 0.001 },
  ],
  'ALK': [
    { name: '克唑替尼 (Crizotinib)', smiles: 'C[C@@H](Oc1cc(F)cc(F)c1)c1cnc(N)nc1', ic50: 0.011 },
    { name: '阿来替尼 (Alectinib)', smiles: 'COc1cc(Nc2c3ccccc3c3ccccc23)c(=O)c(C)c1', ic50: 0.0019 },
  ],
  'ROS1': [
    { name: '克唑替尼 (Crizotinib)', smiles: 'C[C@@H](Oc1cc(F)cc(F)c1)c1cnc(N)nc1', ic50: 0.0072 },
    { name: '恩曲替尼 (Entrectinib)', smiles: 'COc1cc(N2CCN(C)CC2)ccc1Nc1nc2c(c(N)nc3ccccc32)n1C', ic50: 0.001 },
  ],
  'JAK2': [
    { name: '鲁索替尼 (Ruxolitinib)', smiles: 'CN(C)Cc1cnc(N)c(Nc2ccc(C(=O)NCCN3CCOCC3)cc2)c1', ic50: 0.0028 },
  ],
  'CDK4/6': [
    { name: '帕博西尼 (Palbociclib)', smiles: 'COc1cccc(NC(=O)c2cnc3c(c2)cc(C(F)(F)F)c2[nH]ccc23)c1', ic50: 0.011 },
  ],
  'MEK1': [
    { name: '曲美替尼 (Trametinib)', smiles: 'COc1cc(N(C)c2ccc3nc(NC(=O)c4c(F)cccc4F)cc(C)c3c2)c(Cl)cn1', ic50: 0.0009 },
  ],
  'HER2': [
    { name: '拉帕替尼 (Lapatinib)', smiles: 'CS(=O)(=O)c1ccc(Oc2ccc(Nc3ncc4c(n3)ccnc4c3CCCCC3)cc2)cc1', ic50: 0.0093 },
  ],
  'PI3Kα': [
    { name: 'Alpelisib', smiles: 'COc1cc(N2CCN(C)CC2)ccc1Nc1nc(N)c2ncn(C3CCCC3)c2n1', ic50: 0.005 },
  ],
  'PD-1/PD-L1': [
    { name: '多韦替尼 (Dovitinib)', smiles: 'COc1ccc(CN2CCN(c3nc4ccccc4nc3N)CC2)cc1', ic50: 0.013 },
  ],
  'CSF1R': [
    { name: 'Pexidartinib', smiles: 'Cc1nc(C)nc(Nc2cc(F)c(C(=O)Nc3cc(C(F)(F)F)ccc3N)cc2F)c1', ic50: 0.02 },
  ],
  'FGFR1': [
    { name: 'Erdafitinib', smiles: 'COc1cc(Nc2ncnc3c2ccn3C2CCCC2)c(OC)cc1N1CCN(C)CC1', ic50: 0.0012 },
  ],
  'RET': [
    { name: 'Selpercatinib', smiles: 'COc1cc(Nc2nccc(-c3cn(C)c4ccccc34)n2)cc(C(C)(C)C)c1', ic50: 0.014 },
  ],
}

export default function ProjectDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { state, dispatch } = useApp()
  const [project, setProject] = useState(null)
  const [loading, setLoading] = useState(true)
  const [selectedCandidates, setSelectedCandidates] = useState(new Set())
  const [feedbackStats, setFeedbackStats] = useState(null)
  const [assayResults, setAssayResults] = useState([])
  const [filterCollapsed, setFilterCollapsed] = useState(true)
  const [pipelineConfig, setPipelineConfig] = useState({
    num_molecules: 1000,
    generation_strategy: 'crem',
    similarity_threshold: 0.3,
    admet_threshold: 60,
    top_n: 200,
    availability_threshold: 0.5,
    enable_failed_iteration: false,
    filter_params: {
      mw_min: 200, mw_max: 500,
      clogp_min: 0.5, clogp_max: 4.5,
      tpsa_min: 40, tpsa_max: 120,
      hbd_max: 4,
      hba_max: 10,
      rotb_max: 8,
      sa_score_max: 4.5,
    }
  })

  useEffect(() => {
    loadProject()
  }, [id])

  const loadProject = async () => {
    try {
      const res = await api.getProject(id)
      setProject(res.data.data)
      dispatch({ type: 'SET_PROJECT', payload: res.data.data })
      // 加载实验验证数据
      loadAssayData()
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  const loadAssayData = async () => {
    try {
      const statsRes = await api.getFeedbackStats(id)
      if (statsRes.data.success) {
        setFeedbackStats(statsRes.data.data)
      }
      const listRes = await api.listAssayResults(id)
      if (listRes.data.success) {
        setAssayResults(listRes.data.data || [])
      }
    } catch (e) {
      console.error(e)
    }
  }

  const applyFeedbackFromList = async (assayId) => {
    try {
      const res = await api.applyFeedback(assayId)
      if (res.data.success) {
        alert('数据已回流！')
        loadAssayData()
      }
    } catch (e) {
      alert('回流失败: ' + e.message)
    }
  }

  const toggleCandidate = (smiles) => {
    setSelectedCandidates(prev => {
      const next = new Set(prev)
      if (next.has(smiles)) next.delete(smiles)
      else next.add(smiles)
      return next
    })
  }

  const uploadMolecules = async () => {
    const candidates = targetMoleculeLibrary[project?.target_name] || []
    const selected = candidates.filter(c => selectedCandidates.has(c.smiles))
    if (selected.length === 0) {
      alert('请至少选择1个活性分子')
      return
    }
    const molecules = selected.map(c => ({
      smiles: c.smiles,
      name: c.name,
      ic50: c.ic50
    }))
    try {
      const res = await api.uploadActiveMolecules(id, { molecules })
      setSelectedCandidates(new Set())
      loadProject()
      const { added, skipped } = res.data.data || {}
      if (skipped > 0) {
        alert(`上传完成：新增 ${added} 个，已跳过 ${skipped} 个重复分子`)
      } else {
        alert(`上传成功：新增 ${added} 个活性分子`)
      }
    } catch (e) {
      alert('上传失败: ' + e.message)
    }
  }

  const runPipeline = async () => {
    try {
      const res = await api.runPipeline({
        project_id: parseInt(id),
        ...pipelineConfig
      })
      const jobId = res.data.data.job_id
      dispatch({ type: 'SET_PIPELINE_JOB_ID', payload: jobId })
      dispatch({ type: 'SET_PIPELINE_STATUS', payload: 'running' })
      alert('Pipeline已启动，Job ID: ' + jobId)
      navigate('/pipeline')
    } catch (e) {
      alert('启动失败: ' + e.message)
    }
  }

  if (loading) return <div className="flex justify-center py-20"><LoadingSpinner size="lg" /></div>
  if (!project) return <div className="text-center py-20 text-gray-400">项目不存在</div>

  return (
    <div className="space-y-6">
      {/* 项目信息 */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <div className="flex justify-between items-start">
          <div>
            <h2 className="text-2xl font-bold text-gray-800 mb-2">{project.name}</h2>
            <div className="text-sm text-gray-500 space-y-1">
              <p>靶点: {project.target_name || '-'} {project.target_pdb && `(${project.target_pdb})`}</p>
              <p>目标: {designGoalLabels[project.design_goal] || project.design_goal}</p>
            </div>
          </div>
          <button
            onClick={runPipeline}
            className="btn-action"
          >
            <Play className="w-4 h-4" /> 运行Pipeline
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 已知活性分子上传 */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <h3 className="text-lg font-semibold mb-4">已知活性分子</h3>

          {/* 候选分子列表（复选框选择） */}
          {project.target_name && targetMoleculeLibrary[project.target_name] ? (
            <div className="mb-4">
              <p className="text-sm text-gray-500 mb-3">
                靶点 <b>{project.target_name}</b> 的已知活性分子候选（已加载 {targetMoleculeLibrary[project.target_name].length} 个，请选择 1-3 个）：
              </p>
              <div className="space-y-2 max-h-64 overflow-auto border border-gray-100 rounded-lg p-2">
                {targetMoleculeLibrary[project.target_name].map((cand) => (
                  <label
                    key={cand.smiles}
                    className={`flex items-center gap-3 p-2 rounded-lg cursor-pointer transition ${
                      selectedCandidates.has(cand.smiles)
                        ? 'bg-slate-50 border border-slate-200'
                        : 'bg-gray-50 border border-transparent hover:bg-gray-100'
                    }`}
                  >
                    <input
                      type="checkbox"
                      className="w-4 h-4 text-slate-700 rounded focus:ring-slate-500"
                      checked={selectedCandidates.has(cand.smiles)}
                      onChange={() => toggleCandidate(cand.smiles)}
                    />
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium text-gray-700">{cand.name}</div>
                      <div className="text-xs text-gray-400 font-mono truncate">{cand.smiles}</div>
                      <div className="text-xs text-slate-700">IC50: {cand.ic50} μM</div>
                    </div>
                  </label>
                ))}
              </div>
              <button
                onClick={uploadMolecules}
                disabled={selectedCandidates.size === 0}
                className="mt-3 flex items-center gap-2 bg-slate-700 text-white px-4 py-2 rounded-lg text-sm hover:bg-slate-800 disabled:opacity-50 transition-colors"
              >
                <Upload className="w-4 h-4" /> 上传已选分子 ({selectedCandidates.size})
              </button>
            </div>
          ) : (
            <div className="text-center py-6 text-gray-400 text-sm">
              <FlaskConical className="w-10 h-10 mx-auto mb-2 opacity-50" />
              <p>该靶点暂无预设活性分子库</p>
              <p className="text-xs mt-1">请先在项目设置中关联已知靶点</p>
            </div>
          )}

          {/* 已上传的活性分子 */}
          {project.active_molecules?.length > 0 ? (
            <div className="mt-4">
              <div className="text-sm font-medium text-gray-700 mb-2">已上传的活性分子</div>
              <div className="space-y-2 max-h-48 overflow-auto">
                {project.active_molecules.map((m) => (
                  <div key={m.id} className="flex items-center gap-3 p-2 bg-gray-50 rounded-lg">
                    <MoleculeSVG moleculeId={m.id} smiles={m.smiles} size={50} />
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium text-gray-700">{m.name || `分子 #${m.id}`}</div>
                      <div className="text-xs text-gray-400 font-mono truncate">{m.smiles}</div>
                      {m.ic50 && <div className="text-xs text-slate-700">IC50: {m.ic50} nM</div>}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="text-center py-6 text-gray-400 text-sm">
              <p>暂无已上传的活性分子</p>
            </div>
          )}
        </div>

        {/* Pipeline配置 - 基础配置 + 可折叠过滤参数 */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-5">
          <h3 className="text-lg font-semibold mb-4">Pipeline配置</h3>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-gray-500 block mb-1">生成分子数</label>
              <input
                type="number"
                className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm"
                value={pipelineConfig.num_molecules}
                onChange={(e) => setPipelineConfig({ ...pipelineConfig, num_molecules: parseInt(e.target.value) })}
              />
            </div>
            <div>
              <label className="text-xs text-gray-500 block mb-1">生成策略</label>
              <select
                className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm"
                value={pipelineConfig.generation_strategy}
                onChange={(e) => setPipelineConfig({ ...pipelineConfig, generation_strategy: e.target.value })}
              >
                <option value="crem">CReM</option>
                <option value="rdkit">RDKit</option>
                <option value="scaffold">骨架</option>
              </select>
            </div>
            <div>
              <label className="text-xs text-gray-500 block mb-1">相似性阈值</label>
              <input
                type="number" min="0" max="1" step="0.05"
                className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm"
                value={pipelineConfig.similarity_threshold}
                onChange={(e) => setPipelineConfig({ ...pipelineConfig, similarity_threshold: parseFloat(e.target.value) })}
              />
            </div>
            <div>
              <label className="text-xs text-gray-500 block mb-1">ADMET阈值</label>
              <input
                type="number" min="0" max="100" step="5"
                className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm"
                value={pipelineConfig.admet_threshold}
                onChange={(e) => setPipelineConfig({ ...pipelineConfig, admet_threshold: parseInt(e.target.value) })}
              />
            </div>
            <div>
              <label className="text-xs text-gray-500 block mb-1">精筛Top N</label>
              <input
                type="number"
                className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm"
                value={pipelineConfig.top_n}
                onChange={(e) => setPipelineConfig({ ...pipelineConfig, top_n: parseInt(e.target.value) })}
              />
            </div>
            <div>
              <label className="text-xs text-gray-500 block mb-1">合成可行性</label>
              <input
                type="number" min="0" max="1" step="0.05"
                className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm"
                value={pipelineConfig.availability_threshold}
                onChange={(e) => setPipelineConfig({ ...pipelineConfig, availability_threshold: parseFloat(e.target.value) })}
              />
            </div>
            {/* 迭代学习开关 */}
            <div className="col-span-2">
              <label className="flex items-center gap-2 cursor-pointer p-2 rounded-lg border border-gray-200 hover:bg-gray-50 transition">
                <input
                  type="checkbox"
                  className="w-4 h-4 text-blue-600 rounded"
                  checked={pipelineConfig.enable_failed_iteration}
                  onChange={(e) => setPipelineConfig({ ...pipelineConfig, enable_failed_iteration: e.target.checked })}
                />
                <div>
                  <div className="text-sm font-medium text-gray-700">迭代学习</div>
                  <div className="text-[10px] text-gray-400">加载历史失败分子，避免重复生成相同结构</div>
                </div>
              </label>
            </div>
          </div>

          {/* 可折叠过滤参数 */}
          <div className="mt-4 border-t border-gray-100">
            <button
              onClick={() => setFilterCollapsed(!filterCollapsed)}
              className="w-full flex items-center justify-between py-2 text-sm text-gray-600 hover:text-gray-800 transition"
            >
              <span className="font-medium">过滤参数</span>
              <span className="text-xs text-gray-400">{filterCollapsed ? '展开' : '收起'}</span>
            </button>
            {!filterCollapsed && (
              <div className="pb-3 grid grid-cols-2 gap-3">
                {/* MW */}
                <div>
                  <label className="text-xs text-gray-500 block mb-1">分子量 (MW)</label>
                  <div className="flex items-center gap-1">
                    <input
                      type="number" min="100" max="1000" step="10"
                      className="w-full border border-gray-300 rounded-lg px-2 py-1 text-sm"
                      value={pipelineConfig.filter_params.mw_min}
                      onChange={(e) => setPipelineConfig({
                        ...pipelineConfig,
                        filter_params: { ...pipelineConfig.filter_params, mw_min: parseInt(e.target.value) }
                      })}
                    />
                    <span className="text-gray-400 text-xs">~</span>
                    <input
                      type="number" min="100" max="1000" step="10"
                      className="w-full border border-gray-300 rounded-lg px-2 py-1 text-sm"
                      value={pipelineConfig.filter_params.mw_max}
                      onChange={(e) => setPipelineConfig({
                        ...pipelineConfig,
                        filter_params: { ...pipelineConfig.filter_params, mw_max: parseInt(e.target.value) }
                      })}
                    />
                  </div>
                </div>
                {/* LogP */}
                <div>
                  <label className="text-xs text-gray-500 block mb-1">脂溶性 (logP)</label>
                  <div className="flex items-center gap-1">
                    <input
                      type="number" min="-2" max="8" step="0.1"
                      className="w-full border border-gray-300 rounded-lg px-2 py-1 text-sm"
                      value={pipelineConfig.filter_params.clogp_min}
                      onChange={(e) => setPipelineConfig({
                        ...pipelineConfig,
                        filter_params: { ...pipelineConfig.filter_params, clogp_min: parseFloat(e.target.value) }
                      })}
                    />
                    <span className="text-gray-400 text-xs">~</span>
                    <input
                      type="number" min="-2" max="8" step="0.1"
                      className="w-full border border-gray-300 rounded-lg px-2 py-1 text-sm"
                      value={pipelineConfig.filter_params.clogp_max}
                      onChange={(e) => setPipelineConfig({
                        ...pipelineConfig,
                        filter_params: { ...pipelineConfig.filter_params, clogp_max: parseFloat(e.target.value) }
                      })}
                    />
                  </div>
                </div>
                {/* TPSA */}
                <div>
                  <label className="text-xs text-gray-500 block mb-1">极性表面积 (TPSA)</label>
                  <div className="flex items-center gap-1">
                    <input
                      type="number" min="0" max="300" step="5"
                      className="w-full border border-gray-300 rounded-lg px-2 py-1 text-sm"
                      value={pipelineConfig.filter_params.tpsa_min}
                      onChange={(e) => setPipelineConfig({
                        ...pipelineConfig,
                        filter_params: { ...pipelineConfig.filter_params, tpsa_min: parseInt(e.target.value) }
                      })}
                    />
                    <span className="text-gray-400 text-xs">~</span>
                    <input
                      type="number" min="0" max="300" step="5"
                      className="w-full border border-gray-300 rounded-lg px-2 py-1 text-sm"
                      value={pipelineConfig.filter_params.tpsa_max}
                      onChange={(e) => setPipelineConfig({
                        ...pipelineConfig,
                        filter_params: { ...pipelineConfig.filter_params, tpsa_max: parseInt(e.target.value) }
                      })}
                    />
                  </div>
                </div>
                {/* HBD */}
                <div>
                  <label className="text-xs text-gray-500 block mb-1">氢键供体 (HBD)</label>
                  <div className="flex items-center gap-1">
                    <span className="text-xs text-gray-400">≤</span>
                    <input
                      type="number" min="0" max="15" step="1"
                      className="w-full border border-gray-300 rounded-lg px-2 py-1 text-sm"
                      value={pipelineConfig.filter_params.hbd_max}
                      onChange={(e) => setPipelineConfig({
                        ...pipelineConfig,
                        filter_params: { ...pipelineConfig.filter_params, hbd_max: parseInt(e.target.value) }
                      })}
                    />
                  </div>
                </div>
                {/* HBA */}
                <div>
                  <label className="text-xs text-gray-500 block mb-1">氢键受体 (HBA)</label>
                  <div className="flex items-center gap-1">
                    <span className="text-xs text-gray-400">≤</span>
                    <input
                      type="number" min="0" max="20" step="1"
                      className="w-full border border-gray-300 rounded-lg px-2 py-1 text-sm"
                      value={pipelineConfig.filter_params.hba_max}
                      onChange={(e) => setPipelineConfig({
                        ...pipelineConfig,
                        filter_params: { ...pipelineConfig.filter_params, hba_max: parseInt(e.target.value) }
                      })}
                    />
                  </div>
                </div>
                {/* RotB */}
                <div>
                  <label className="text-xs text-gray-500 block mb-1">旋转键 (RotB)</label>
                  <div className="flex items-center gap-1">
                    <span className="text-xs text-gray-400">≤</span>
                    <input
                      type="number" min="0" max="20" step="1"
                      className="w-full border border-gray-300 rounded-lg px-2 py-1 text-sm"
                      value={pipelineConfig.filter_params.rotb_max}
                      onChange={(e) => setPipelineConfig({
                        ...pipelineConfig,
                        filter_params: { ...pipelineConfig.filter_params, rotb_max: parseInt(e.target.value) }
                      })}
                    />
                  </div>
                </div>
                {/* SA Score */}
                <div className="col-span-2">
                  <label className="text-xs text-gray-500 block mb-1">合成难度 (SA Score)</label>
                  <div className="flex items-center gap-1">
                    <span className="text-xs text-gray-400">≤</span>
                    <input
                      type="number" min="0" max="10" step="0.1"
                      className="w-full border border-gray-300 rounded-lg px-2 py-1 text-sm"
                      value={pipelineConfig.filter_params.sa_score_max}
                      onChange={(e) => setPipelineConfig({
                        ...pipelineConfig,
                        filter_params: { ...pipelineConfig.filter_params, sa_score_max: parseFloat(e.target.value) }
                      })}
                    />
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
