import React, { useState, useEffect, useRef } from 'react'
import { Search, ChevronDown, Atom, Database, Info } from 'lucide-react'
import { api } from '../api/client'

// 按首字母分组显示靶点
const alphabetGroups = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('')

export default function TargetSelector({ value, onChange }) {
  const [showDropdown, setShowDropdown] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [targets, setTargets] = useState([])
  const [loading, setLoading] = useState(false)
  const [selectedTarget, setSelectedTarget] = useState(null)
  const [activeLetter, setActiveLetter] = useState('')
  const dropdownRef = useRef(null)

  // 加载靶点列表
  useEffect(() => {
    loadTargets()
  }, [])

  // 监听搜索
  useEffect(() => {
    const timer = setTimeout(() => {
      loadTargets(searchQuery)
    }, 300)
    return () => clearTimeout(timer)
  }, [searchQuery])

  // 点击外部关闭下拉
  useEffect(() => {
    const handleClick = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setShowDropdown(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  const loadTargets = async (query = '') => {
    setLoading(true)
    try {
      const res = await api.listTargets({ q: query })
      const items = res.data.data || []
      setTargets(items)
    } catch (e) {
      console.error('加载靶点失败:', e)
    }
    setLoading(false)
  }

  const handleSelect = (target) => {
    setSelectedTarget(target)
    onChange({
      target_name: target.name,
      target_pdb: target.pdb_id,
    })
    setShowDropdown(false)
    setSearchQuery('')
  }

  const handleCustomInput = (e) => {
    const val = e.target.value
    setSearchQuery(val)
    if (val) {
      setSelectedTarget(null)
      onChange({ target_name: val, target_pdb: '' })
    }
  }

  // 按首字母过滤
  const filteredByLetter = activeLetter
    ? targets.filter(t => t.name.startsWith(activeLetter))
    : targets

  // 首字母分组
  const grouped = {}
  filteredByLetter.forEach(t => {
    const first = t.name.charAt(0).toUpperCase()
    if (!grouped[first]) grouped[first] = []
    grouped[first].push(t)
  })

  return (
    <div className="relative" ref={dropdownRef}>
      {/* 显示框 */}
      <div
        className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm cursor-pointer flex items-center justify-between hover:border-blue-400 transition-colors"
        onClick={() => setShowDropdown(!showDropdown)}
      >
        <div className="flex items-center gap-2 min-w-0">
          {selectedTarget ? (
            <>
              <span className="font-medium text-gray-800 truncate">{selectedTarget.name}</span>
              <span className="text-xs text-slate-700 bg-slate-50 px-1.5 py-0.5 rounded">PDB: {selectedTarget.pdb_id}</span>
            </>
          ) : value ? (
            <span className="text-gray-800 truncate">{value}</span>
          ) : (
            <span className="text-gray-400">点击选择靶点...</span>
          )}
        </div>
        <ChevronDown className={`w-4 h-4 text-gray-400 flex-shrink-0 transition-transform ${showDropdown ? 'rotate-180' : ''}`} />
      </div>

      {/* 下拉面板 */}
      {showDropdown && (
        <div className="absolute z-50 w-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg overflow-hidden" style={{ maxHeight: '420px' }}>
          {/* 搜索栏 */}
          <div className="p-3 border-b border-gray-100 sticky top-0 bg-white z-10">
            <div className="relative">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                type="text"
                value={searchQuery}
                onChange={handleCustomInput}
                placeholder="搜索靶点名称或输入自定义靶点..."
                className="w-full pl-9 pr-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:border-slate-400"
                autoFocus
              />
            </div>
          </div>

          {/* 首字母索引 */}
          {!searchQuery && (
            <div className="flex flex-wrap gap-1 px-3 py-2 border-b border-gray-100 bg-gray-50">
              <button
                onClick={() => setActiveLetter('')}
                className={`px-2 py-0.5 text-xs rounded ${activeLetter === '' ? 'bg-slate-700 text-white' : 'text-gray-500 hover:bg-gray-200'}`}
              >
                全部
              </button>
              {alphabetGroups.map(letter => {
                const hasTargets = targets.some(t => t.name.charAt(0).toUpperCase() === letter)
                return (
                  <button
                    key={letter}
                    onClick={() => setActiveLetter(activeLetter === letter ? '' : letter)}
                    disabled={!hasTargets}
                    className={`px-2 py-0.5 text-xs rounded transition-colors ${
                      activeLetter === letter ? 'bg-slate-700 text-white' :
                      hasTargets ? 'text-gray-500 hover:bg-gray-200' : 'text-gray-300 cursor-not-allowed'
                    }`}
                  >
                    {letter}
                  </button>
                )
              })}
            </div>
          )}

          {/* 靶点列表 */}
          <div className="overflow-y-auto" style={{ maxHeight: '300px' }}>
            {loading ? (
              <div className="p-4 text-center text-sm text-gray-400">加载中...</div>
            ) : targets.length === 0 ? (
              <div className="p-4 text-center text-sm text-gray-400">
                未找到匹配的靶点，可输入自定义名称
              </div>
            ) : (
              <div className="divide-y divide-gray-50">
                {Object.keys(grouped).sort().map(letter => (
                  <div key={letter}>
                    <div className="px-3 py-1 text-xs font-semibold text-gray-400 bg-gray-50 sticky top-0">
                      {letter}
                    </div>
                    {grouped[letter].map(target => (
                      <button
                        key={target.name}
                        onClick={() => handleSelect(target)}
                        className="w-full text-left px-3 py-2.5 hover:bg-slate-50 transition-colors flex items-start gap-3"
                      >
                        <div className="mt-0.5">
                          <Atom className="w-4 h-4 text-blue-500" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-medium text-gray-800">{target.name}</span>
                            <span className="text-[10px] text-slate-700 bg-slate-50 px-1.5 py-0.5 rounded font-mono">
                              PDB:{target.pdb_id}
                            </span>
                          </div>
                          <div className="text-xs text-gray-500 mt-0.5 line-clamp-2">
                            {target.description}
                          </div>
                          <div className="text-[10px] text-gray-400 mt-0.5 flex items-center gap-1">
                            <Database className="w-3 h-3" />
                            {target.molecule_count} 个已知活性分子
                          </div>
                        </div>
                      </button>
                    ))}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* 选中后的详情 */}
      {selectedTarget && (
        <div className="mt-2 p-3 bg-slate-50 rounded-lg border border-blue-100">
          <div className="flex items-start gap-2">
            <Info className="w-4 h-4 text-blue-500 mt-0.5 flex-shrink-0" />
            <div className="text-xs text-blue-800 leading-relaxed">
              {selectedTarget.description}
            </div>
          </div>
          <div className="mt-2 flex items-center gap-3 text-xs">
            <span className="text-slate-700 font-mono">PDB: {selectedTarget.pdb_id}</span>
            <span className="text-blue-500">{selectedTarget.molecule_count} 个已知活性分子</span>
          </div>
        </div>
      )}
    </div>
  )
}
