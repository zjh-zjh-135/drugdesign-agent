import React, { useState, useEffect } from 'react'
import { useApp } from '../store/AppContext'
import { api } from '../api/client'
import MoleculeCard from '../components/MoleculeCard'
import LoadingSpinner from '../components/LoadingSpinner'
import { LayoutGrid, List } from 'lucide-react'

export default function MoleculeBrowser() {
  const { state } = useApp()
  const [molecules, setMolecules] = useState([])
  const [loading, setLoading] = useState(true)
  const [viewMode, setViewMode] = useState('list') // grid | list
  const [page, setPage] = useState(1)
  const [perPage] = useState(20)
  const [total, setTotal] = useState(0)
  const [statusFilter, setStatusFilter] = useState('')

  const projectId = state.currentProject?.id

  useEffect(() => {
    if (projectId) loadMolecules()
  }, [projectId, page, statusFilter])

  const loadMolecules = async () => {
    if (!projectId) return
    setLoading(true)
    try {
      const res = await api.listMolecules(projectId, {
        page,
        per_page: perPage,
        status: statusFilter
      })
      setMolecules(res.data.data || [])
      setTotal(res.data.pagination?.total || 0)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  const totalPages = Math.ceil(total / perPage)

  if (!projectId) {
    return (
      <div className="text-center py-20 text-gray-400">
        <p>请先选择一个项目</p>
      </div>
    )
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-xl font-bold text-gray-800">分子浏览器</h2>
        <div className="flex items-center gap-3">
          <select
            className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm"
            value={statusFilter}
            onChange={(e) => { setStatusFilter(e.target.value); setPage(1) }}
          >
            <option value="">全部状态</option>
            <option value="generated">已生成</option>
            <option value="filtered">已过滤</option>
            <option value="structure_screened">结构筛选</option>
            <option value="admet_passed">ADMET通过</option>
            <option value="refined">已精筛</option>
            <option value="synthesis_passed">合成通过</option>
          </select>
          <div className="flex border border-slate-200 rounded-lg overflow-hidden">
            <button
              onClick={() => setViewMode('grid')}
              className={`p-1.5 ${viewMode === 'grid' ? 'bg-slate-800 text-white' : 'text-slate-400 hover:text-slate-600'}`}
            >
              <LayoutGrid className="w-4 h-4" />
            </button>
            <button
              onClick={() => setViewMode('list')}
              className={`p-1.5 ${viewMode === 'list' ? 'bg-slate-800 text-white' : 'text-slate-400 hover:text-slate-600'}`}
            >
              <List className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

        <div>
          {loading ? (
            <div className="flex justify-center pt-32 pb-20"><LoadingSpinner size="lg" /></div>
          ) : molecules.length === 0 ? (
            <div className="text-center py-20 text-gray-400">暂无分子数据</div>
          ) : viewMode === 'grid' ? (
            <div className="grid grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 gap-4">
              {molecules.map((m) => (
                <MoleculeCard key={m.id} molecule={m} />
              ))}
            </div>
          ) : (
            <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left font-medium text-gray-600">ID</th>
                    <th className="px-4 py-3 text-left font-medium text-gray-600">结构</th>
                    <th className="px-4 py-3 text-left font-medium text-gray-600">SMILES</th>
                    <th className="px-4 py-3 text-left font-medium text-gray-600">MW</th>
                    <th className="px-4 py-3 text-left font-medium text-gray-600">LogP</th>
                    <th className="px-4 py-3 text-left font-medium text-gray-600">QED</th>
                    <th className="px-4 py-3 text-left font-medium text-gray-600">ADMET</th>
                    <th className="px-4 py-3 text-left font-medium text-gray-600">状态</th>
                  </tr>
                </thead>
                <tbody>
                  {molecules.map((m) => (
                    <tr key={m.id} className="border-t border-gray-100 hover:bg-gray-50">
                      <td className="px-4 py-3">{m.id}</td>
                      <td className="px-4 py-3"><img src={api.getMoleculeSvg(m.id)} alt="" className="w-12 h-12 object-contain" /></td>
                      <td className="px-4 py-3 font-mono text-xs text-gray-500 truncate max-w-[200px]">{m.smiles}</td>
                      <td className="px-4 py-3">{m.properties?.mw?.toFixed(1)}</td>
                      <td className="px-4 py-3">{m.properties?.clogp?.toFixed(2)}</td>
                      <td className="px-4 py-3">{m.properties?.qed?.toFixed(3)}</td>
                      <td className="px-4 py-3">
                        <span className={`font-medium ${(m.admet?.overall_score || 0) >= 70 ? 'text-green-600' : (m.admet?.overall_score || 0) >= 50 ? 'text-yellow-600' : 'text-red-600'}`}>
                          {m.admet?.overall_score?.toFixed(1) || '-'}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span className={`text-xs px-2 py-0.5 rounded-full ${
                          m.status === 'synthesis_passed' ? 'bg-green-100 text-green-700' :
                          m.status === 'failed' ? 'bg-red-100 text-red-700' :
                          'bg-blue-100 text-blue-700'
                        }`}>
                          {m.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* 分页 */}
          {totalPages > 1 && (
            <div className="flex justify-center gap-2 mt-6">
              <button
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1}
                className="px-3 py-1 rounded-lg border border-gray-300 text-sm disabled:opacity-50"
              >
                上一页
              </button>
              <span className="px-3 py-1 text-sm text-gray-600">
                {page} / {totalPages}
              </span>
              <button
                onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                className="px-3 py-1 rounded-lg border border-gray-300 text-sm disabled:opacity-50"
              >
                下一页
              </button>
            </div>
          )}
        </div>
    </div>
  )
}
