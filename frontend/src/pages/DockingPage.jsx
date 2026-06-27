import React, { useState, useEffect } from 'react'
import { useApp } from '../store/AppContext'
import { api } from '../api/client'
import Molecule3DViewer from '../components/Molecule3DViewer'
import { 
  Play, Settings, Activity, AlertCircle, 
  ChevronDown, ChevronUp, Database, 
  Atom, ArrowDownToLine, CheckCircle2
} from 'lucide-react'

export default function DockingPage() {
  const { state } = useApp()
  const [smiles, setSmiles] = useState('')
  const [receptorPdb, setReceptorPdb] = useState('')
  const [targetInfo, setTargetInfo] = useState(null)
  const [pdbId, setPdbId] = useState('')
  const [fetchingPdb, setFetchingPdb] = useState(false)
  const [pdbStatus, setPdbStatus] = useState('')
  const [center, setCenter] = useState({ x: 0, y: 0, z: 0 })
  const [boxSize, setBoxSize] = useState({ x: 20, y: 20, z: 20 })
  const [exhaustiveness, setExhaustiveness] = useState(8)
  const [numModes, setNumModes] = useState(9)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [showSettings, setShowSettings] = useState(false)
  const [show3D, setShow3D] = useState(false)

  const projectId = state.currentProject?.id
  const projectName = state.currentProject?.name
  const targetName = state.currentProject?.target_name
  const targetPdb = state.currentProject?.target_pdb

  // 加载靶点信息
  useEffect(() => {
    if (!projectId) return

    // 如果项目有靶点，自动获取靶点信息
    if (targetName) {
      loadTargetInfo(targetName)
    }
  }, [projectId, targetName])

  const loadTargetInfo = async (name) => {
    try {
      const res = await api.getTargetDetail(name)
      const info = res.data.data
      setTargetInfo(info)
      if (info?.pdb_id) {
        setPdbId(info.pdb_id)
      }
    } catch (e) {
      console.error('加载靶点信息失败:', e)
    }
  }

  const handleFetchPdb = async () => {
    if (!pdbId) {
      setError('请先输入PDB ID')
      return
    }
    setFetchingPdb(true)
    setError(null)
    setPdbStatus('正在从RCSB PDB下载...')
    try {
      const res = await api.fetchPdb(pdbId)
      if (res.data.success) {
        setReceptorPdb(res.data.data.content)
        setPdbStatus(`已获取: ${pdbId} (${res.data.data.atom_count} 个原子)`)
      } else {
        setError(res.data.error || '下载失败')
        setPdbStatus('')
      }
    } catch (e) {
      setError(e.response?.data?.error || 'PDB下载失败')
      setPdbStatus('')
    }
    setFetchingPdb(false)
  }

  const handleDock = async () => {
    const finalSmiles = smiles.trim()
    if (!finalSmiles) {
      setError('请输入配体SMILES')
      return
    }
    if (!receptorPdb.trim()) {
      setError('请先获取受体PDB结构')
      return
    }

    setLoading(true)
    setError(null)
    setResult(null)

    try {
      const res = await api.dockFromSmiles({
        smiles: finalSmiles,
        receptor_pdb: receptorPdb.trim(),
        center_x: center.x,
        center_y: center.y,
        center_z: center.z,
        size_x: boxSize.x,
        size_y: boxSize.y,
        size_z: boxSize.z,
        exhaustiveness: exhaustiveness,
        num_modes: numModes,
      })
      setResult(res.data.data)
    } catch (e) {
      setError(e.response?.data?.error || '对接请求失败')
    } finally {
      setLoading(false)
    }
  }

  const getAffinityColor = (affinity) => {
    if (affinity <= -7) return 'text-green-600 bg-green-50 border-green-200'
    if (affinity <= -5) return 'text-slate-700 bg-slate-50 border-slate-200'
    if (affinity <= -3) return 'text-amber-600 bg-amber-50 border-amber-200'
    return 'text-red-600 bg-red-50 border-red-200'
  }

  const getAffinityLabel = (affinity) => {
    if (affinity <= -7) return '极强'
    if (affinity <= -5) return '强'
    if (affinity <= -3) return '中等'
    return '弱'
  }

  const getAffinityBarColor = (affinity) => {
    if (affinity <= -7) return 'bg-green-500'
    if (affinity <= -5) return 'bg-slate-500'
    if (affinity <= -3) return 'bg-amber-500'
    return 'bg-red-500'
  }

  const getPoseDescription = (pose, bestPose) => {
    if (pose.mode === 1) {
      return { label: '全局最优', detail: '能量最低的最稳定构象，作为对接首选结果' }
    }
    const rmsd = pose.rmsd_lower || pose.rmsd_upper || 0
    if (rmsd < 1.5) {
      return { label: '高度相似', detail: '与最佳构象空间位置接近，可能为局部最优或旋转异构体' }
    } else if (rmsd < 3.0) {
      return { label: '翻转/旋转构象', detail: '分子在结合口袋中发生了明显翻转或旋转，但仍保持有效结合' }
    } else if (rmsd < 5.0) {
      return { label: '显著不同构象', detail: '分子在口袋中的结合方向显著不同，可能为不同的结合模式' }
    } else {
      return { label: '替代结合模式', detail: '与最佳构象差异较大，可能代表次优的结合模式或噪声' }
    }
  }

  const affinityRanges = [
    { label: '极强', min: '-10', max: '≤ -7', color: 'bg-green-500', desc: '优异的靶点结合能力，通常具有良好的成药性' },
    { label: '强', min: '>-7', max: '≤ -5', color: 'bg-slate-500', desc: '良好的靶点结合能力，值得进一步优化的候选分子' },
    { label: '中等', min: '>-5', max: '≤ -3', color: 'bg-amber-500', desc: '适中的结合能力，可通过结构优化提升' },
    { label: '弱', min: '>-3', max: '-1', color: 'bg-red-500', desc: '结合能力较弱，建议优化或替换候选分子' },
  ]

  const columnDescriptions = {
    rank: '按结合能排序的构象排名，1为最佳结合构象',
    affinity: '配体-受体结合自由能（ΔG），负值越大代表结合越强',
    rmsd_lower: '构象与最佳构象的重叠偏差（下界），用于衡量构象一致性',
    rmsd_upper: '构象与最佳构象的重叠偏差（上界），用于衡量构象一致性',
    rating: '基于结合能的综合定性评价，分为极强/强/中等/弱四档',
  }

  const [showHelp, setShowHelp] = useState(false)

  if (!projectId) {
    return (
      <div className="text-center py-20 text-gray-400">
        <Database className="w-12 h-12 mx-auto mb-4 text-gray-300" />
        <p>请先选择一个项目</p>
      </div>
    )
  }

  return (
    <div className="max-w-4xl mx-auto">
      <h2 className="text-2xl font-bold text-gray-800 mb-6 flex items-center gap-2">
        <Atom className="w-7 h-7 text-slate-700" />
        分子对接 (AutoDock Vina)
      </h2>

      {/* 项目信息卡片 */}
      <div className="bg-white rounded-lg border border-slate-200 p-4 mb-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div>
              <div className="text-sm font-semibold text-gray-800">{projectName}</div>
              {targetName && (
                <div className="text-xs text-slate-500 mt-0.5">
                  靶点: {targetName}
                  {targetInfo?.pdb_id && ` · PDB: ${targetInfo.pdb_id}`}
                </div>
              )}
            </div>
          </div>
          {targetInfo?.pdb_id && (
            <a 
              href={`https://www.rcsb.org/structure/${targetInfo.pdb_id}`}
              target="_blank"
              rel="noopener noreferrer"
              className="rcsb-send"
            >
              <span className="rcsb-svg-wrapper">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="16" height="16">
                  <path fill="none" d="M0 0h24v24H0z" />
                  <path fill="currentColor" d="M1.946 9.315c-.522-.174-.527-.455.01-.634l19.087-6.362c.529-.176.832.12.684.638l-5.454 19.086c-.15.529-.455.547-.679.045L12 14l6-8-8 6-8.054-2.685z" />
                </svg>
              </span>
              <span className="rcsb-send-text">查看RCSB</span>
            </a>
          )}
          <style>{`
            .rcsb-send {
              font-size: 13px;
              background: royalblue;
              color: white;
              padding: 0.7em 1em;
              padding-left: 0.9em;
              display: inline-flex;
              align-items: center;
              border: none;
              border-radius: 16px;
              overflow: hidden;
              transition: all 0.2s;
              cursor: pointer;
              text-decoration: none;
            }
            .rcsb-send-text {
              display: block;
              margin-left: 0.5em;
              transition: all 0.3s ease-in-out;
            }
            .rcsb-svg-wrapper {
              display: block;
              transform-origin: center center;
              transition: transform 0.3s ease-in-out;
            }
            .rcsb-send:hover .rcsb-svg-wrapper {
              animation: rcsb-fly 0.6s ease-in-out infinite alternate;
            }
            .rcsb-send:hover svg {
              transform: translateX(1.2em) rotate(45deg) scale(1.1);
            }
            .rcsb-send:hover .rcsb-send-text {
              transform: translateX(5em);
            }
            .rcsb-send:active {
              transform: scale(0.95);
            }
            @keyframes rcsb-fly {
              from { transform: translateY(0.1em); }
              to { transform: translateY(-0.1em); }
            }
          `}</style>
        </div>
      </div>

      {/* 输入区域 */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
        
        {/* 配体选择 */}
        <div className="mb-5">
          <label className="text-sm font-medium text-gray-700 mb-2 block">
            配体选择
          </label>
          <input
            type="text"
            value={smiles}
            onChange={(e) => setSmiles(e.target.value)}
            placeholder="输入配体SMILES，例如: c1ccccc1C(=O)Nc1ccc(cc1)Cl"
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:border-slate-400"
          />
        </div>

        {/* 受体PDB */}
        <div className="mb-5">
          <label className="text-sm font-medium text-gray-700 mb-2">
            受体结构
          </label>
          
          {/* PDB ID 输入 + 获取按钮 */}
          <div className="flex gap-2 mb-3">
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  value={pdbId}
                  onChange={(e) => {
                    setPdbId(e.target.value.toUpperCase().trim())
                    setPdbStatus('')
                  }}
                  placeholder={targetPdb || '输入PDB ID (如 4MBS)'}
                  className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm font-mono uppercase focus:outline-none focus:border-slate-400"
                />
                <div
                  onClick={fetchingPdb || !pdbId ? undefined : handleFetchPdb}
                  className={`btn-tooltip ${fetchingPdb || !pdbId ? 'disabled' : ''}`}
                  data-tooltip="RCSB PDB"
                >
                  <div className="btn-tooltip-wrapper">
                    <div className="btn-tooltip-text">
                      {fetchingPdb ? '获取中...' : '获取PDB'}
                    </div>
                    <span className="btn-tooltip-icon">
                      <ArrowDownToLine className="w-4 h-4" />
                    </span>
                  </div>
                </div>
              </div>
              <p className="text-xs text-gray-400 mt-1.5">
                {targetPdb 
                  ? `项目靶点推荐PDB: ${targetPdb}。可自动从 RCSB PDB (https://www.rcsb.org) 下载结构。`
                  : '请输入PDB ID，从RCSB PDB下载受体结构。'
                }
              </p>
            </div>
          </div>

          {/* PDB状态 */}
          {pdbStatus && (
            <div className="flex items-center gap-2 text-green-600 bg-green-50 px-3 py-2 rounded-lg text-xs mb-2">
              <CheckCircle2 className="w-4 h-4" />
              {pdbStatus}
            </div>
          )}

          {/* PDB内容展示（可折叠） */}
          {receptorPdb && (
            <div className="border border-gray-200 rounded-lg overflow-hidden">
              <div className="bg-gray-50 px-3 py-2 flex items-center justify-between">
                <span className="text-xs text-gray-500 font-medium">PDB结构内容</span>
                <span className="text-xs text-gray-400">{receptorPdb.length} 字符</span>
              </div>
              <textarea
                value={receptorPdb}
                onChange={(e) => setReceptorPdb(e.target.value)}
                rows={4}
                className="w-full px-3 py-2 text-xs font-mono bg-white border-0 resize-y focus:ring-0"
              />
            </div>
          )}
        </div>

          {/* 运行对接按钮 */}
          <div className="flex justify-end mt-3">
            <button
              onClick={handleDock}
              disabled={loading || !smiles || !receptorPdb}
              className="btn-action"
            >
              <Play className="w-4 h-4" />
              {loading ? '对接中...' : '运行对接'}
            </button>
          </div>

        {/* 高级设置 */}
        <div className="mb-5">
          <button
            onClick={() => setShowSettings(!showSettings)}
            className="flex items-center gap-2 text-sm text-slate-600 hover:text-slate-800"
          >
            <Settings className="w-4 h-4" />
            对接盒子参数
            {showSettings ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>

          {showSettings && (
            <div className="mt-3 grid grid-cols-2 gap-4 p-4 bg-gray-50 rounded-lg">
              <div>
                <label className="text-xs text-gray-500 mb-1 block">盒子中心 X</label>
                <input type="number" value={center.x} onChange={(e) => setCenter({...center, x: parseFloat(e.target.value)})} className="w-full border rounded px-2 py-1 text-sm" />
              </div>
              <div>
                <label className="text-xs text-gray-500 mb-1 block">盒子大小 X (Å)</label>
                <input type="number" value={boxSize.x} onChange={(e) => setBoxSize({...boxSize, x: parseFloat(e.target.value)})} className="w-full border rounded px-2 py-1 text-sm" />
              </div>
              <div>
                <label className="text-xs text-gray-500 mb-1 block">盒子中心 Y</label>
                <input type="number" value={center.y} onChange={(e) => setCenter({...center, y: parseFloat(e.target.value)})} className="w-full border rounded px-2 py-1 text-sm" />
              </div>
              <div>
                <label className="text-xs text-gray-500 mb-1 block">盒子大小 Y (Å)</label>
                <input type="number" value={boxSize.y} onChange={(e) => setBoxSize({...boxSize, y: parseFloat(e.target.value)})} className="w-full border rounded px-2 py-1 text-sm" />
              </div>
              <div>
                <label className="text-xs text-gray-500 mb-1 block">盒子中心 Z</label>
                <input type="number" value={center.z} onChange={(e) => setCenter({...center, z: parseFloat(e.target.value)})} className="w-full border rounded px-2 py-1 text-sm" />
              </div>
              <div>
                <label className="text-xs text-gray-500 mb-1 block">盒子大小 Z (Å)</label>
                <input type="number" value={boxSize.z} onChange={(e) => setBoxSize({...boxSize, z: parseFloat(e.target.value)})} className="w-full border rounded px-2 py-1 text-sm" />
              </div>
              <div>
                <label className="text-xs text-gray-500 mb-1 block">详尽度 (1-32)</label>
                <input type="number" min={1} max={32} value={exhaustiveness} onChange={(e) => setExhaustiveness(parseInt(e.target.value))} className="w-full border rounded px-2 py-1 text-sm" />
              </div>
              <div>
                <label className="text-xs text-gray-500 mb-1 block">构象数</label>
                <input type="number" min={1} max={20} value={numModes} onChange={(e) => setNumModes(parseInt(e.target.value))} className="w-full border rounded px-2 py-1 text-sm" />
              </div>
            </div>
          )}
        </div>

        {error && (
          <div className="mt-4 flex items-center gap-2 text-red-600 bg-red-50 px-4 py-3 rounded-lg text-sm">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}
      </div>

      {/* 结果区域 */}
      {result && (
        <div className="space-y-6">

          {/* 结合能总览卡片 */}
          <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-4">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-slate-50 flex items-center justify-center">
                  <Activity className="w-4 h-4 text-slate-700" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-gray-800">对接结果</h3>
                  <p className="text-[10px] text-gray-400">AutoDock Vina</p>
                </div>
              </div>
            </div>

            {/* 构象列表 */}
            <div className="border border-gray-200 rounded-2xl overflow-hidden bg-white">
              <div className="px-5 py-3 border-b border-gray-200 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold text-gray-700">构象排名</span>
                  <span className="text-xs text-gray-400">共 {result.docking_result.poses.length} 个</span>
                </div>
                <button
                  onClick={() => setShowHelp(!showHelp)}
                  className="text-xs text-blue-600 hover:text-blue-700 underline"
                >
                  {showHelp ? '收起说明' : '数据说明'}
                </button>
              </div>

              {showHelp && (
                <div className="bg-slate-50/60 border-b border-blue-100 px-5 py-3.5">
                  <div className="grid grid-cols-1 gap-1.5 text-xs text-slate-600">
                    <div className="flex gap-2"><span className="font-semibold min-w-[70px] text-slate-700">排名</span>按结合能排序，1为最佳构象</div>
                    <div className="flex gap-2"><span className="font-semibold min-w-[70px] text-slate-700">结合能</span>配体-受体结合自由能（ΔG），负值越大结合越强</div>
                    <div className="flex gap-2"><span className="font-semibold min-w-[70px] text-slate-700">RMSD</span>构象与最佳构象的重叠偏差（Å），衡量空间差异</div>
                    <div className="flex gap-2"><span className="font-semibold min-w-[70px] text-slate-700">构象类型</span>基于RMSD的构象分类描述</div>
                  </div>
                </div>
              )}

              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-100">
                    <th className="px-5 py-2.5 text-left text-xs font-medium text-gray-400 w-14">排名</th>
                    <th className="px-5 py-2.5 text-left text-xs font-medium text-gray-400">结合能</th>
                    <th className="px-5 py-2.5 text-left text-xs font-medium text-gray-400 w-32">RMSD</th>
                    <th className="px-5 py-2.5 text-left text-xs font-medium text-gray-400">构象类型</th>
                    <th className="px-5 py-2.5 text-left text-xs font-medium text-gray-400 w-20">评价</th>
                  </tr>
                </thead>
                <tbody>
                  {result.docking_result.poses.map((pose, idx) => {
                    const bestPose = result.docking_result.poses[0]
                    const desc = getPoseDescription(pose, bestPose)
                    const isFirst = pose.mode === 1
                    const rmsd = pose.rmsd_lower || pose.rmsd_upper || 0
                    
                    // 构象类型颜色
                    let typeColor = 'text-gray-500'
                    let typeBg = 'bg-gray-100'
                    if (isFirst) { typeColor = 'text-amber-700'; typeBg = 'bg-amber-50' }
                    else if (desc.label === '高度相似') { typeColor = 'text-emerald-700'; typeBg = 'bg-emerald-50' }
                    else if (desc.label === '翻转/旋转构象') { typeColor = 'text-cyan-700'; typeBg = 'bg-cyan-50' }
                    else if (desc.label === '显著不同构象') { typeColor = 'text-purple-700'; typeBg = 'bg-purple-50' }
                    else { typeColor = 'text-gray-600'; typeBg = 'bg-gray-100' }
                    
                    return (
                      <tr
                        key={pose.mode}
                        className={`border-b border-gray-50 last:border-b-0 transition hover:bg-gray-50/60 ${isFirst ? 'bg-amber-50/20' : ''}`}
                      >
                        {/* 排名 */}
                        <td className="px-5 py-3">
                          {isFirst ? (
                            <span className="text-xs font-bold text-amber-600">1</span>
                          ) : (
                            <span className="text-gray-500 text-xs font-medium">{pose.mode}</span>
                          )}
                        </td>
                        
                        {/* 结合能 */}
                        <td className="px-5 py-3">
                          <div className="flex items-center gap-2">
                            <span className={`font-bold text-sm ${getAffinityColor(pose.affinity).split(' ')[0]}`}>
                              {pose.affinity}
                            </span>
                            <span className="text-[10px] text-gray-400">kcal/mol</span>
                          </div>
                        </td>
                        
                        {/* RMSD */}
                        <td className="px-5 py-3">
                          <div className="text-xs font-mono text-gray-600">
                            {pose.rmsd_lower !== null && pose.rmsd_lower !== undefined
                              ? (
                                <div className="flex items-center gap-1.5">
                                  <span>{pose.rmsd_lower.toFixed(2)} Å</span>
                                  {pose.rmsd_upper !== null && pose.rmsd_upper !== undefined && (
                                    <span className="text-gray-400 text-[10px]"> / {pose.rmsd_upper.toFixed(2)} Å</span>
                                  )}
                                </div>
                              )
                              : <span className="text-gray-300">—</span>
                            }
                          </div>
                        </td>
                        
                        {/* 构象类型 */}
                        <td className="px-5 py-3">
                          <span className={`inline-block text-[10px] px-2 py-0.5 rounded font-medium ${typeBg} ${typeColor}`}>
                            {desc.label}
                          </span>
                        </td>
                        
                        {/* 评价 */}
                        <td className="px-5 py-3">
                          <span className={`inline-block text-[10px] font-medium ${getAffinityColor(pose.affinity).split(' ')[0]}`}>
                            {getAffinityLabel(pose.affinity)}
                          </span>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>

            {/* 对接盒子信息 */}
            {result.docking_result.box && result.docking_result.box.center && (
              <div className="mt-4 p-4 bg-gray-50 rounded-lg text-xs text-gray-500">
                <div className="flex items-center gap-2 mb-1">
                  <Settings className="w-3.5 h-3.5 text-gray-400" />
                  <span className="font-medium text-gray-600">搜索空间参数</span>
                </div>
                <div className="grid grid-cols-2 gap-2 mt-1">
                  <div>中心: ({result.docking_result.box.center.x}, {result.docking_result.box.center.y}, {result.docking_result.box.center.z}) Å</div>
                  <div>尺寸: ({result.docking_result.box.size?.x}, {result.docking_result.box.size?.y}, {result.docking_result.box.size?.z}) Å</div>
                </div>
              </div>
            )}

            {/* 对接说明 */}
            <div className="mt-4 p-4 bg-slate-50 rounded-lg border border-slate-200">
              <div className="flex items-center gap-2 mb-2">
                <Atom className="w-4 h-4 text-slate-500" />
                <span className="text-sm font-semibold text-slate-700">分子对接说明</span>
              </div>
              <p className="text-xs text-slate-600 leading-relaxed">
                分子对接模拟配体（小分子药物）与受体（靶点蛋白）的结合过程。AutoDock Vina 通过计算配体-受体的结合自由能（ΔG）来评估结合强度。
                负值越大，结合越强。<strong>排名1</strong>代表最佳结合构象，后续的排名代表其他可能的结合方式。
                RMSD 衡量不同构象之间的空间差异，数值越小表示构象越相似。
              </p>
            </div>
          </div>
        </div>
      )}

      {/* 3D Viewer */}
      {show3D && (
        <Molecule3DViewer
          smiles={smiles}
          title="对接构象 - 3D结构"
          dockingData={result.docking_result}
          onClose={() => setShow3D(false)}
        />
      )}
    </div>
  )
}
