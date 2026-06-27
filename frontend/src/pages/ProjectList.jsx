import React, { useState, useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus, Trash2, Search, SlidersHorizontal, ArrowUpDown, LayoutGrid, List, ChevronDown, Check } from 'lucide-react'
import { api } from '../api/client'
import { useApp } from '../store/AppContext'
import LoadingSpinner from '../components/LoadingSpinner'
import TargetSelector from '../components/TargetSelector'

const DESIGN_GOAL_MAP = {
  lead_optimization: 'Lead优化',
  hit_finding: 'Hit发现',
  scaffold_hopping: '骨架跃迁',
  selectivity: '选择性优化',
}

const DESIGN_GOAL_OPTIONS = [
  { key: 'all', label: '全部目标' },
  { key: 'lead_optimization', label: 'Lead优化' },
  { key: 'hit_finding', label: 'Hit发现' },
  { key: 'scaffold_hopping', label: '骨架跃迁' },
  { key: 'selectivity', label: '选择性优化' },
]

export default function ProjectList() {
  const navigate = useNavigate()
  const { dispatch } = useApp()

  const [projects, setProjects] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [filterGoal, setFilterGoal] = useState('all')
  const [sortKey, setSortKey] = useState('created_at')
  const [sortDesc, setSortDesc] = useState(true)
  const [viewMode, setViewMode] = useState('table')
  const [selectedIds, setSelectedIds] = useState(new Set())
  const [showFilterDropdown, setShowFilterDropdown] = useState(false)
  const [showSortDropdown, setShowSortDropdown] = useState(false)

  // 新建项目弹窗
  const [showModal, setShowModal] = useState(false)
  const [showCandidateModal, setShowCandidateModal] = useState(false)
  const [formData, setFormData] = useState({
    name: '', target_name: '', target_pdb: '', design_goal: 'lead_optimization'
  })
  const [candidates, setCandidates] = useState([])
  const [selectedCandidates, setSelectedCandidates] = useState([])
  const [candidateLoading, setCandidateLoading] = useState(false)
  const [candidateTarget, setCandidateTarget] = useState('')
  const [justCreatedProject, setJustCreatedProject] = useState(null)

  useEffect(() => { loadProjects() }, [])

  const loadProjects = async () => {
    try {
      const res = await api.listProjects()
      setProjects(res.data.data || [])
    } catch (e) { console.error(e) }
    finally { setLoading(false) }
  }

  // 搜索 + 筛选 + 排序
  const filtered = useMemo(() => {
    let list = [...projects]
    if (search.trim()) {
      const q = search.trim().toLowerCase()
      list = list.filter(p =>
        p.name.toLowerCase().includes(q) ||
        (p.target_name && p.target_name.toLowerCase().includes(q)) ||
        (p.target_pdb && p.target_pdb.toLowerCase().includes(q))
      )
    }
    if (filterGoal !== 'all') {
      list = list.filter(p => p.design_goal === filterGoal)
    }
    list.sort((a, b) => {
      let cmp = 0
      if (sortKey === 'name') cmp = (a.name || '').localeCompare(b.name || '')
      else if (sortKey === 'created_at') cmp = new Date(a.created_at) - new Date(b.created_at)
      else if (sortKey === 'target') cmp = (a.target_name || '').localeCompare(b.target_name || '')
      return sortDesc ? -cmp : cmp
    })
    return list
  }, [projects, search, filterGoal, sortKey, sortDesc])

  const toggleSelect = (id) => {
    setSelectedIds(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const toggleSelectAll = () => {
    if (selectedIds.size === filtered.length && filtered.length > 0) {
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set(filtered.map(p => p.id)))
    }
  }

  const deleteProject = async (id) => {
    if (!confirm('确定删除此项目？所有关联数据将被删除。')) return
    try {
      await api.deleteProject(id)
      setSelectedIds(prev => { const next = new Set(prev); next.delete(id); return next })
      loadProjects()
    } catch (e) { alert('删除失败: ' + e.message) }
  }

  const batchDelete = async () => {
    if (!confirm(`确定删除选中的 ${selectedIds.size} 个项目？所有关联数据将被删除。`)) return
    const ids = Array.from(selectedIds)
    for (const id of ids) {
      try { await api.deleteProject(id) } catch (e) { console.error(e) }
    }
    setSelectedIds(new Set())
    loadProjects()
  }

  const selectProject = (p) => {
    dispatch({ type: 'SET_PROJECT', payload: p })
    navigate(`/projects/${p.id}`)
  }

  const createProject = async () => {
    if (!formData.name.trim()) return
    try {
      const res = await api.createProject(formData)
      const newProject = res.data.data
      setShowModal(false)
      setFormData({ name: '', target_name: '', target_pdb: '', design_goal: 'lead_optimization' })
      if (formData.target_name) {
        setJustCreatedProject(newProject)
        loadCandidates(formData.target_name)
      } else { loadProjects() }
    } catch (e) { alert('创建失败: ' + e.message) }
  }

  const loadCandidates = async (targetName) => {
    setCandidateLoading(true)
    setCandidateTarget(targetName)
    try {
      const res = await api.getTargetCandidates(targetName)
      const data = res.data.data
      setCandidates(data.candidates || [])
      setSelectedCandidates((data.candidates || []).map((_, i) => i))
      setShowCandidateModal(true)
    } catch (e) {
      alert('加载候选分子失败: ' + e.message)
      loadProjects()
    }
    setCandidateLoading(false)
  }

  const toggleCandidate = (index) => {
    setSelectedCandidates(prev => prev.includes(index) ? prev.filter(i => i !== index) : [...prev, index])
  }
  const selectAllCandidates = () => setSelectedCandidates(candidates.map((_, i) => i))
  const selectNoneCandidates = () => setSelectedCandidates([])
  const confirmAddCandidates = async () => {
    if (!justCreatedProject || selectedCandidates.length === 0) {
      setShowCandidateModal(false)
      loadProjects()
      return
    }
    try {
      await api.batchAddActiveMolecules(justCreatedProject.id, { molecules: selectedCandidates.map(idx => candidates[idx]) })
      setShowCandidateModal(false)
      setCandidates([])
      setSelectedCandidates([])
      setJustCreatedProject(null)
      loadProjects()
    } catch (e) { alert('添加分子失败: ' + e.message) }
  }

  const handleTargetChange = ({ target_name, target_pdb }) => {
    setFormData(prev => ({ ...prev, target_name, target_pdb }))
  }

  const handleSort = (key) => {
    if (sortKey === key) { setSortDesc(!sortDesc) }
    else { setSortKey(key); setSortDesc(true) }
    setShowSortDropdown(false)
  }

  if (loading) return <div className="flex justify-center pt-32 pb-20"><LoadingSpinner size="lg" /></div>

  return (
    <div>
      {/* 标题栏 */}
      <div className="flex items-center justify-between mb-2">
        <div>
          <h2 className="text-lg font-bold text-slate-800">项目列表</h2>
          <p className="text-xs text-slate-400 mt-0.5">管理您的药物设计项目，共 {projects.length} 个</p>
        </div>
        <button
          onClick={() => setShowModal(true)}
          className="flex items-center gap-2 bg-slate-800 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-slate-900 transition"
        >
          <Plus className="w-4 h-4" /> 新建项目
        </button>
      </div>

      {/* 工具栏：搜索 + 筛选 + 排序 + 视图 */}
      <div className="flex items-center gap-3 mb-4 flex-wrap">
        <div className="relative flex-1 min-w-[200px] max-w-md">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="搜索项目名称、靶点..."
            className="w-full border border-slate-200 rounded-lg pl-9 pr-3 py-2 text-sm focus:outline-none focus:border-slate-400"
          />
        </div>

        {/* 筛选下拉 */}
        <div className="relative">
          <button
            onClick={() => { setShowFilterDropdown(!showFilterDropdown); setShowSortDropdown(false) }}
            className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm border transition ${
              filterGoal !== 'all' ? 'bg-slate-50 border-slate-300 text-slate-800' : 'border-slate-200 text-slate-600 hover:bg-slate-50'
            }`}
          >
            <SlidersHorizontal className="w-4 h-4" />
            目标
            {filterGoal !== 'all' && <span className="w-2 h-2 rounded-full bg-slate-600" />}
            <ChevronDown className="w-3.5 h-3.5" />
          </button>
          {showFilterDropdown && (
            <div className="absolute top-full mt-1 left-0 bg-white border border-slate-200 rounded-lg shadow-lg z-10 py-1 min-w-[140px]">
              {DESIGN_GOAL_OPTIONS.map(opt => (
                <button
                  key={opt.key}
                  onClick={() => { setFilterGoal(opt.key); setShowFilterDropdown(false) }}
                  className="w-full text-left px-3 py-2 text-sm text-slate-600 hover:bg-slate-50 flex items-center gap-2"
                >
                  {filterGoal === opt.key ? <Check className="w-3.5 h-3.5" /> : <span className="w-3.5" />}
                  {opt.label}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* 排序下拉 */}
        <div className="relative">
          <button
            onClick={() => { setShowSortDropdown(!showSortDropdown); setShowFilterDropdown(false) }}
            className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm border border-slate-200 text-slate-600 hover:bg-slate-50 transition"
          >
            <ArrowUpDown className="w-4 h-4" />
            排序
            <ChevronDown className="w-3.5 h-3.5" />
          </button>
          {showSortDropdown && (
            <div className="absolute top-full mt-1 left-0 bg-white border border-slate-200 rounded-lg shadow-lg z-10 py-1 min-w-[160px]">
              {[
                { key: 'created_at', label: '创建时间' },
                { key: 'name', label: '项目名称' },
                { key: 'target', label: '靶点' },
              ].map(opt => (
                <button
                  key={opt.key}
                  onClick={() => handleSort(opt.key)}
                  className="w-full text-left px-3 py-2 text-sm text-slate-600 hover:bg-slate-50 flex items-center gap-2"
                >
                  {sortKey === opt.key ? <Check className="w-3.5 h-3.5" /> : <span className="w-3.5" />}
                  {opt.label}
                  {sortKey === opt.key && <span className="text-[10px] text-slate-400 ml-auto">{sortDesc ? '↓' : '↑'}</span>}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* 视图切换 */}
        <div className="flex items-center border border-slate-200 rounded-lg overflow-hidden ml-auto">
          <button
            onClick={() => setViewMode('table')}
            className={`px-3 py-2 text-sm ${viewMode === 'table' ? 'bg-slate-800 text-white' : 'text-slate-500 hover:bg-slate-50'}`}
            title="表格视图"
          >
            <List className="w-4 h-4" />
          </button>
          <button
            onClick={() => setViewMode('card')}
            className={`px-3 py-2 text-sm ${viewMode === 'card' ? 'bg-slate-800 text-white' : 'text-slate-500 hover:bg-slate-50'}`}
            title="卡片视图"
          >
            <LayoutGrid className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* 批量操作栏 */}
      {selectedIds.size > 0 && (
        <div className="flex items-center gap-3 mb-3 px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm">
          <span className="text-slate-600 font-medium">已选择 {selectedIds.size} 项</span>
          <button
            onClick={batchDelete}
            className="flex items-center gap-1.5 text-rose-600 hover:text-rose-700 px-2 py-1 rounded hover:bg-rose-50 transition"
          >
            <Trash2 className="w-3.5 h-3.5" />
            批量删除
          </button>
          <button
            onClick={() => setSelectedIds(new Set())}
            className="text-slate-400 hover:text-slate-600 ml-auto text-xs"
          >
            取消选择
          </button>
        </div>
      )}

      {/* 内容 */}
      {projects.length === 0 ? (
        <div className="text-center py-20 text-slate-400">
          <div className="text-5xl mb-4">🧪</div>
          <p>暂无项目，点击"新建项目"开始</p>
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-20 text-slate-400">
          <Search className="w-12 h-12 mx-auto mb-4 opacity-30" />
          <p>未找到匹配的项目</p>
          <button
            onClick={() => { setSearch(''); setFilterGoal('all') }}
            className="text-sm text-slate-500 hover:text-slate-700 mt-2 underline"
          >
            清除筛选
          </button>
        </div>
      ) : viewMode === 'table' ? (
        <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50/60">
                <th className="py-3 px-4 w-10">
                  <button onClick={toggleSelectAll} className="w-4 h-4 rounded border border-slate-300 flex items-center justify-center">
                    {selectedIds.size === filtered.length && filtered.length > 0 && (
                      <Check className="w-3 h-3 text-slate-600" />
                    )}
                  </button>
                </th>
                <th className="text-left py-3 px-4 text-xs font-semibold text-slate-500 cursor-pointer hover:text-slate-700"
                    onClick={() => handleSort('name')}>
                  <span className="flex items-center gap-1">项目名称 {sortKey === 'name' && <span className="text-slate-400">{sortDesc ? '↓' : '↑'}</span>}</span>
                </th>
                <th className="text-left py-3 px-4 text-xs font-semibold text-slate-500 cursor-pointer hover:text-slate-700"
                    onClick={() => handleSort('target')}>
                  <span className="flex items-center gap-1">靶点 {sortKey === 'target' && <span className="text-slate-400">{sortDesc ? '↓' : '↑'}</span>}</span>
                </th>
                <th className="text-left py-3 px-4 text-xs font-semibold text-slate-500">设计目标</th>
                <th className="text-left py-3 px-4 text-xs font-semibold text-slate-500 cursor-pointer hover:text-slate-700"
                    onClick={() => handleSort('created_at')}>
                  <span className="flex items-center gap-1">创建时间 {sortKey === 'created_at' && <span className="text-slate-400">{sortDesc ? '↓' : '↑'}</span>}</span>
                </th>
                <th className="text-right py-3 px-4 text-xs font-semibold text-slate-500 w-16">操作</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(p => {
                const isSelected = selectedIds.has(p.id)
                return (
                  <tr
                    key={p.id}
                    className={`border-b border-slate-100 hover:bg-slate-50/60 transition cursor-pointer ${isSelected ? 'bg-slate-50' : ''}`}
                    onClick={() => selectProject(p)}
                  >
                    <td className="py-3 px-4" onClick={(e) => { e.stopPropagation(); toggleSelect(p.id) }}>
                      <div className={`w-4 h-4 rounded border flex items-center justify-center ${isSelected ? 'bg-slate-700 border-slate-700' : 'border-slate-300'}`}>
                        {isSelected && <Check className="w-3 h-3 text-white" />}
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      <div className="font-medium text-slate-800">{p.name}</div>
                    </td>
                    <td className="py-3 px-4">
                      <div className="text-slate-600">
                        {p.target_name || '-'}
                        {p.target_pdb && <span className="text-slate-400 text-xs ml-1 font-mono">({p.target_pdb})</span>}
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      <span className="text-xs px-2 py-0.5 rounded bg-slate-100 text-slate-600 font-medium">
                        {DESIGN_GOAL_MAP[p.design_goal] || p.design_goal}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-slate-500 text-xs">
                      {new Date(p.created_at).toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <button
                        onClick={(e) => { e.stopPropagation(); deleteProject(p.id) }}
                        className="p-1.5 text-slate-400 hover:text-rose-500 transition rounded hover:bg-rose-50"
                        title="删除"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      ) : (
        /* 卡片视图 */
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {filtered.map(p => (
            <div
              key={p.id}
              className="bg-white rounded-lg border border-slate-200 p-4 hover:border-slate-300 transition cursor-pointer relative"
              onClick={() => selectProject(p)}
            >
              <div className="flex items-start justify-between">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1.5">
                    <h3 className="font-semibold text-slate-800 truncate">{p.name}</h3>
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 font-medium whitespace-nowrap">
                      {DESIGN_GOAL_MAP[p.design_goal] || p.design_goal}
                    </span>
                  </div>
                  <div className="text-sm text-slate-500 mb-1">
                    靶点: {p.target_name || '-'} {p.target_pdb && <span className="text-slate-400 font-mono text-xs">({p.target_pdb})</span>}
                  </div>
                  <div className="text-xs text-slate-400">
                    {new Date(p.created_at).toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })}
                  </div>
                </div>
                <button
                  onClick={(e) => { e.stopPropagation(); deleteProject(p.id) }}
                  className="p-1.5 text-slate-400 hover:text-rose-500 transition rounded hover:bg-rose-50 ml-2"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* 创建项目弹窗（保持不变） */}
      {showModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl p-6 w-full max-w-lg">
            <h3 className="text-lg font-bold mb-4">新建项目</h3>
            <div className="space-y-3">
              <div>
                <label className="text-sm text-slate-600 block mb-1">项目名称 *</label>
                <input
                  type="text"
                  className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-slate-400"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="例如: BRAF抑制剂优化项目"
                />
              </div>
              <div>
                <label className="text-sm text-slate-600 block mb-1">靶点名称</label>
                <TargetSelector value={formData.target_name} onChange={handleTargetChange} />
              </div>
              <div>
                <label className="text-sm text-slate-600 block mb-1">PDB ID</label>
                <input
                  type="text"
                  className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-slate-400 font-mono"
                  value={formData.target_pdb}
                  onChange={(e) => setFormData({ ...formData, target_pdb: e.target.value })}
                  placeholder="选择靶点后自动填充，或手动输入"
                />
              </div>
              <div>
                <label className="text-sm text-slate-600 block mb-1">设计目标</label>
                <select
                  className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-slate-400"
                  value={formData.design_goal}
                  onChange={(e) => setFormData({ ...formData, design_goal: e.target.value })}
                >
                  <option value="lead_optimization">Lead优化（优化已有先导化合物）</option>
                  <option value="hit_finding">Hit发现（从零寻找新化合物）</option>
                  <option value="scaffold_hopping">骨架跃迁（保留药效团换骨架）</option>
                  <option value="selectivity">选择性优化（降低脱靶效应）</option>
                </select>
              </div>
            </div>
            <div className="flex gap-3 mt-6">
              <button onClick={() => setShowModal(false)} className="flex-1 py-2 text-sm text-slate-600 hover:bg-slate-100 rounded-lg transition">取消</button>
              <button onClick={createProject} className="flex-1 py-2 text-sm bg-slate-800 text-white rounded-lg hover:bg-slate-900 transition">创建</button>
            </div>
          </div>
        </div>
      )}

      {/* 候选分子弹窗（保持不变） */}
      {showCandidateModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl p-6 w-full max-w-2xl max-h-[90vh] flex flex-col">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-lg font-bold text-slate-800">选择已知活性分子</h3>
                <p className="text-sm text-slate-500 mt-0.5">
                  靶点: <span className="font-medium text-slate-700">{candidateTarget}</span>
                  <span className="mx-2 text-slate-300">|</span>
                  共 {candidates.length} 个候选分子
                </p>
              </div>
              <div className="flex gap-2">
                <button onClick={selectAllCandidates} className="text-xs px-3 py-1.5 bg-slate-100 text-slate-600 rounded hover:bg-slate-200 transition">全选</button>
                <button onClick={selectNoneCandidates} className="text-xs px-3 py-1.5 bg-slate-100 text-slate-600 rounded hover:bg-slate-200 transition">全不选</button>
              </div>
            </div>
            {candidateLoading ? (
              <div className="flex-1 flex items-center justify-center py-20"><LoadingSpinner size="lg" /></div>
            ) : (
              <div className="flex-1 overflow-y-auto space-y-2 pr-1">
                {candidates.map((mol, idx) => {
                  const isSelected = selectedCandidates.includes(idx)
                  return (
                    <div
                      key={idx}
                      onClick={() => toggleCandidate(idx)}
                      className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-all ${
                        isSelected ? 'border-slate-300 bg-slate-50' : 'border-slate-200 hover:border-slate-300 hover:bg-slate-50/50'
                      }`}
                    >
                      <div className={`w-5 h-5 rounded border flex items-center justify-center mt-0.5 flex-shrink-0 ${isSelected ? 'bg-slate-700 border-slate-700' : 'border-slate-300'}`}>
                        {isSelected && <Check className="w-3.5 h-3.5 text-white" />}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-sm font-medium text-slate-800">{mol.name}</span>
                          <span className="text-xs text-emerald-600 bg-emerald-50 px-1.5 py-0.5 rounded font-mono">IC50: {mol.ic50} μM</span>
                        </div>
                        <div className="font-mono text-xs text-slate-400 break-all">{mol.smiles}</div>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
            <div className="flex gap-3 mt-4 pt-4 border-t border-slate-100">
              <button onClick={() => { setShowCandidateModal(false); loadProjects() }} className="flex-1 py-2 text-sm text-slate-600 hover:bg-slate-100 rounded-lg transition">跳过，不添加</button>
              <button onClick={confirmAddCandidates} disabled={selectedCandidates.length === 0} className="flex-1 py-2 text-sm bg-slate-800 text-white rounded-lg hover:bg-slate-900 disabled:opacity-50 transition">添加 {selectedCandidates.length} 个分子</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
