import React, { useState, useEffect } from 'react'
import { useApp } from '../store/AppContext'
import { api } from '../api/client'
import { ChevronDown, ChevronUp, Search, BarChart, PieChart as PieChartIcon } from 'lucide-react'

/* ── 简易 SVG 饼图 ── */
function SimplePieChart({ data }) {
  const total = data.reduce((s, d) => s + d.count, 0)
  const radius = 70
  const cx = 80
  const cy = 80
  let startAngle = -90

  const colors = [
    '#94a3b8',  // slate-400
    '#64748b',  // slate-500
    '#475569',  // slate-600
    '#cbd5e1',  // slate-300
    '#1e293b',  // slate-800
  ]

  return (
    <svg width="160" height="160" viewBox="0 0 160 160" style={{ display: 'block' }}>
      {data.map((d, i) => {
        const angle = total > 0 ? (d.count / total) * 360 : 0
        if (angle === 0) return null
        const endAngle = startAngle + angle
        const startRad = (startAngle * Math.PI) / 180
        const endRad = (endAngle * Math.PI) / 180
        const x1 = cx + radius * Math.cos(startRad)
        const y1 = cy + radius * Math.sin(startRad)
        const x2 = cx + radius * Math.cos(endRad)
        const y2 = cy + radius * Math.sin(endRad)
        const largeArc = angle > 180 ? 1 : 0
        const path = `M ${cx} ${cy} L ${x1} ${y1} A ${radius} ${radius} 0 ${largeArc} 1 ${x2} ${y2} Z`
        startAngle += angle
        return (
          <path
            key={d.stage}
            d={path}
            fill={colors[i % colors.length]}
            stroke="white"
            strokeWidth="2"
          />
        )
      })}
      {/* 中心白色圆，做成环形图 */}
      <circle cx={cx} cy={cy} r="35" fill="white" />
      <text x={cx} y={cy - 5} textAnchor="middle" dominantBaseline="central" fontSize="12" fontWeight="bold" fill="#1e293b">{total}</text>
      <text x={cx} y={cy + 10} textAnchor="middle" dominantBaseline="central" fontSize="9" fill="#64748b">总失败</text>
    </svg>
  )
}

export default function FailedMolecules() {
  const { state } = useApp()
  const [molecules, setMolecules] = useState([])
  const [analysis, setAnalysis] = useState(null)
  const [loading, setLoading] = useState(false)
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [stageFilter, setStageFilter] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [expandedId, setExpandedId] = useState(null)
  const [statsCollapsed, setStatsCollapsed] = useState(true)  // 默认收起

  const projectId = state.currentProject?.id

  useEffect(() => {
    if (projectId) {
      loadFailedMolecules()
      loadAnalysis()
    }
  }, [projectId, page, stageFilter])

  const loadFailedMolecules = async () => {
    if (!projectId) return
    setLoading(true)
    try {
      const res = await api.getFailedMolecules(projectId, { page, per_page: 50, stage: stageFilter })
      setMolecules(res.data.data?.items || [])
      setTotal(res.data.data?.total || 0)
    } catch (e) {
      console.error(e)
    }
    setLoading(false)
  }

  const loadAnalysis = async () => {
    if (!projectId) return
    try {
      const res = await api.getFailedAnalysis(projectId)
      setAnalysis(res.data.data)
    } catch (e) {
      console.error(e)
    }
  }

  const handleSearch = () => {
    setPage(1)
    loadFailedMolecules()
  }

  const stageLabels = {
    filtering: '基础过滤',
    structure_screening: '结构筛选',
    admet: 'ADMET',
    refinement: '精筛',
    synthesis: '合成',
  }

  const pieColors = [
    '#94a3b8', '#64748b', '#475569', '#cbd5e1', '#1e293b',
  ]

  if (!projectId) {
    return <div className="text-center py-20 text-slate-400">请先选择一个项目</div>
  }

  return (
    <div>
      {/* 失败统计 — 按钮 + 可展开饼图 */}
      {analysis && (
        <div className="mb-4">
          {/* 按钮 */}
          <button
            onClick={() => setStatsCollapsed(!statsCollapsed)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition ${
              statsCollapsed
                ? 'bg-white border border-slate-200 text-slate-600 hover:border-slate-300 hover:bg-slate-50'
                : 'bg-slate-700 text-white border border-slate-700'
            }`}
          >
            {statsCollapsed ? <BarChart className="w-4 h-4" /> : <PieChartIcon className="w-4 h-4" />}
            失败统计
            {statsCollapsed ? (
              <ChevronDown className="w-4 h-4" />
            ) : (
              <ChevronUp className="w-4 h-4" />
            )}
          </button>

          {/* 展开内容：饼图 + 图例 + 统计卡片 */}
          {!statsCollapsed && (
            <div className="mt-3 bg-white rounded-lg border border-slate-200 p-5">
              {/* 饼图 + 图例 */}
              {analysis.stage_distribution && analysis.stage_distribution.length > 0 && (
                <div className="flex items-center gap-6 mb-5">
                  <SimplePieChart data={analysis.stage_distribution} />
                  <div className="flex-1 space-y-2">
                    {analysis.stage_distribution.map((s, i) => {
                      const pct = analysis.total_failed > 0 ? ((s.count / analysis.total_failed) * 100).toFixed(1) : '0.0'
                      return (
                        <div key={s.stage} className="flex items-center gap-3">
                          <span
                            className="w-3 h-3 rounded-sm shrink-0"
                            style={{ backgroundColor: pieColors[i % pieColors.length] }}
                          />
                          <span className="text-sm text-slate-600 w-20">{stageLabels[s.stage] || s.stage}</span>
                          <span className="text-sm font-bold text-slate-800 w-8">{s.count}</span>
                          <span className="text-xs text-slate-400">{pct}%</span>
                          <div className="flex-1 h-1.5 bg-slate-100 rounded-full overflow-hidden">
                            <div
                              className="h-full rounded-full"
                              style={{
                                width: `${pct}%`,
                                backgroundColor: pieColors[i % pieColors.length],
                              }}
                            />
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}

              {/* 各阶段卡片行 */}
              <div className="flex gap-2 overflow-x-auto pb-1">
                <div className="min-w-[120px] flex-1 bg-white rounded-lg border border-slate-200 p-3 relative">
                  <div className="absolute top-0 left-0 right-0 h-0.5 bg-slate-700" />
                  <span className="text-[11px] text-slate-500">总失败</span>
                  <div className="text-xl font-bold text-slate-800 mt-0.5">{analysis.total_failed}</div>
                </div>
                {analysis.stage_distribution?.map((s) => {
                  const pct = analysis.total_failed > 0 ? ((s.count / analysis.total_failed) * 100).toFixed(1) : '0.0'
                  return (
                    <div key={s.stage} className="min-w-[120px] flex-1 bg-white rounded-lg border border-slate-200 p-3 relative">
                      <div className="absolute top-0 left-0 right-0 h-0.5 bg-slate-400" />
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-[11px] text-slate-600">{stageLabels[s.stage] || s.stage}</span>
                        <span className="text-[10px] font-medium text-slate-500">{pct}%</span>
                      </div>
                      <div className="text-xl font-bold text-slate-700">{s.count}</div>
                      <div className="w-full h-1 bg-slate-100 rounded-full mt-1.5 overflow-hidden">
                        <div className="h-full bg-slate-400 rounded-full transition-all" style={{ width: `${pct}%` }} />
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          )}
        </div>
      )}

      {/* 筛选栏 */}
      <div className="flex gap-3 mb-4">
        <div className="flex-1 relative">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            placeholder="搜索失败原因..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            className="w-full pl-10 pr-4 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:border-slate-400"
          />
        </div>
        <select
          value={stageFilter}
          onChange={(e) => { setStageFilter(e.target.value); setPage(1) }}
          className="px-4 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:border-slate-400"
        >
          <option value="">所有阶段</option>
          <option value="filtering">基础过滤</option>
          <option value="structure_screening">结构筛选</option>
          <option value="admet">ADMET</option>
          <option value="refinement">精筛</option>
          <option value="synthesis">合成</option>
        </select>
      </div>

      {/* 分子列表 */}
      {loading ? (
        <div className="text-center py-20 text-slate-400">加载中...</div>
      ) : molecules.length === 0 ? (
        <div className="text-center py-20 text-slate-400">暂无失败分子数据</div>
      ) : (
        <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 border-b border-slate-200">
              <tr>
                <th className="text-left px-4 py-3 text-slate-500 font-medium">SMILES</th>
                <th className="text-left px-4 py-3 text-slate-500 font-medium">失败阶段</th>
                <th className="text-left px-4 py-3 text-slate-500 font-medium">失败原因</th>
                <th className="text-left px-4 py-3 text-slate-500 font-medium">失败时间</th>
                <th className="w-16"></th>
              </tr>
            </thead>
            <tbody>
              {molecules.map((mol, idx) => {
                const isExpanded = expandedId === mol.id
                const reason = mol.failure_reason || {}
                const rowBg = idx % 2 === 0 ? 'bg-white' : 'bg-blue-50/60'
                return (
                  <React.Fragment key={mol.id}>
                    <tr className={`border-b border-slate-100 hover:bg-slate-50 ${rowBg}`}>
                      <td className="px-4 py-3 font-mono text-xs text-slate-600 max-w-[300px] truncate">
                        {mol.smiles}
                      </td>
                      <td className="px-4 py-3">
                        <span className="text-xs px-2 py-1 rounded-full font-medium bg-slate-100 text-slate-600">
                          {stageLabels[mol.failure_stage] || mol.failure_stage}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-slate-600 max-w-[300px] truncate">
                        {reason.reason || '未知'}
                      </td>
                      <td className="px-4 py-3 text-slate-400 text-xs">
                        {mol.failed_at ? new Date(mol.failed_at).toLocaleString() : '—'}
                      </td>
                      <td className="px-4 py-3">
                        <button
                          onClick={() => setExpandedId(isExpanded ? null : mol.id)}
                          className="p-1 hover:bg-slate-200 rounded transition-colors"
                        >
                          {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                        </button>
                      </td>
                    </tr>
                    {isExpanded && (
                      <tr className="bg-slate-50">
                        <td colSpan={5} className="px-4 py-4">
                          <div className="text-sm space-y-2">
                            <div className="font-medium text-slate-700">详细失败原因</div>
                            <div className="bg-white rounded-lg border border-slate-200 p-3">
                              <div className="text-slate-600">{reason.detail || reason.reason || '无详细原因'}</div>
                              {reason.details && (
                                <ul className="mt-2 space-y-1">
                                  {reason.details.map((d, i) => (
                                    <li key={i} className="text-xs text-slate-500 flex items-center gap-2">
                                      <span className="w-1 h-1 rounded-full bg-slate-400" />
                                      {d}
                                    </li>
                                  ))}
                                </ul>
                              )}
                              {reason.metrics && (
                                <div className="mt-3 grid grid-cols-3 gap-2 text-xs">
                                  {Object.entries(reason.metrics).map(([k, v]) => (
                                    <div key={k} className="bg-slate-50 rounded px-2 py-1">
                                      <span className="text-slate-400">{k}:</span>{' '}
                                      <span className="font-mono text-slate-700">{v !== null ? v : '—'}</span>
                                    </div>
                                  ))}
                                </div>
                              )}
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                )
              })}
            </tbody>
          </table>

          {/* 分页 */}
          <div className="flex items-center justify-between px-4 py-3 border-t border-slate-200">
            <div className="text-xs text-slate-400">
              共 {total} 条，第 {page} 页
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => setPage(Math.max(1, page - 1))}
                disabled={page === 1}
                className="px-3 py-1 text-xs border border-slate-200 rounded hover:bg-slate-50 disabled:opacity-50 transition-colors"
              >
                上一页
              </button>
              <button
                onClick={() => setPage(page + 1)}
                disabled={page * 50 >= total}
                className="px-3 py-1 text-xs border border-slate-200 rounded hover:bg-slate-50 disabled:opacity-50 transition-colors"
              >
                下一页
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
