import React, { useRef, useEffect, useState } from 'react'
import {
  X, RotateCcw, ZoomIn, ZoomOut, Maximize,
  Rotate3D, Move, Palette, Camera, Play, Pause,
  Atom, Info, Eye, Layers, Box, Sparkles
} from 'lucide-react'

export default function Molecule3DViewer({ moleculeId, smiles, onClose, title = '3D分子结构', dockingData = null }) {
  const containerRef = useRef(null)
  const viewerRef = useRef(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [style, setStyle] = useState('stick')
  const [bgColor, setBgColor] = useState('white')
  const [autoRotate, setAutoRotate] = useState(false)
  const [showInfo, setShowInfo] = useState(true)
  const [moleculeInfo, setMoleculeInfo] = useState({
    atoms: 0, bonds: 0, mw: null, formula: ''
  })
  const [hoverAtom, setHoverAtom] = useState(null)
  const rotateTimerRef = useRef(null)

  useEffect(() => {
    let cancelled = false

    const initViewer = async () => {
      try {
        if (!window.$3Dmol) {
          await load3DmolScript()
        }
        if (cancelled) return

        let sdfData
        if (moleculeId) {
          const res = await fetch(`/api/molecules/${moleculeId}/structure?format=sdf`)
          if (!res.ok) throw new Error('获取结构数据失败')
          sdfData = await res.text()
        } else if (smiles) {
          const res = await fetch('/api/molecules/structure/from_smiles', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ smiles, format: 'sdf' })
          })
          if (!res.ok) throw new Error('生成结构数据失败')
          const json = await res.json()
          sdfData = json.data?.structure
        }

        if (!sdfData) throw new Error('无结构数据')
        if (cancelled) return

        // 解析分子信息
        const info = parseMoleculeInfo(sdfData)
        setMoleculeInfo(info)

        const config = { backgroundColor: bgColor }
        const viewer = window.$3Dmol.createViewer(containerRef.current, config)
        viewerRef.current = viewer

        // 添加模型
        viewer.addModel(sdfData, 'sdf')
        applyStyle(viewer, style)
        viewer.zoomTo()
        viewer.render()

        // 添加鼠标悬停事件
        viewer.setClickable({}, true, (atom) => {
          if (atom) {
            setHoverAtom({
              elem: atom.elem,
              serial: atom.serial,
              x: atom.x.toFixed(2),
              y: atom.y.toFixed(2),
              z: atom.z.toFixed(2),
            })
          } else {
            setHoverAtom(null)
          }
        })

        setLoading(false)
      } catch (err) {
        if (!cancelled) {
          setError(err.message || '3D查看器初始化失败')
          setLoading(false)
        }
      }
    }

    initViewer()

    return () => {
      cancelled = true
      if (rotateTimerRef.current) {
        clearInterval(rotateTimerRef.current)
      }
      if (viewerRef.current) {
        viewerRef.current.removeAllModels()
        viewerRef.current = null
      }
    }
  }, [moleculeId, smiles])

  // 样式切换
  useEffect(() => {
    if (!viewerRef.current) return
    applyStyle(viewerRef.current, style)
    viewerRef.current.render()
  }, [style])

  // 背景色切换
  useEffect(() => {
    if (!viewerRef.current) return
    viewerRef.current.setBackgroundColor(bgColor)
    viewerRef.current.render()
  }, [bgColor])

  // 自动旋转
  useEffect(() => {
    if (!viewerRef.current) return
    if (autoRotate) {
      rotateTimerRef.current = setInterval(() => {
        if (viewerRef.current) {
          viewerRef.current.rotate(1, { x: 0, y: 1, z: 0 })
        }
      }, 50)
    } else {
      if (rotateTimerRef.current) {
        clearInterval(rotateTimerRef.current)
        rotateTimerRef.current = null
      }
    }
    return () => {
      if (rotateTimerRef.current) {
        clearInterval(rotateTimerRef.current)
      }
    }
  }, [autoRotate])

  const applyStyle = (viewer, s) => {
    viewer.removeAllLabels()
    viewer.removeAllSurfaces()

    if (s === 'stick') {
      viewer.setStyle({}, { stick: { radius: 0.2, colorscheme: 'Jmol' } })
    } else if (s === 'sphere') {
      viewer.setStyle({}, { sphere: { scale: 0.3, colorscheme: 'Jmol' } })
    } else if (s === 'line') {
      viewer.setStyle({}, { line: { colorscheme: 'Jmol' } })
    } else if (s === 'ballStick') {
      viewer.setStyle({}, { stick: { radius: 0.15 }, sphere: { scale: 0.25 } })
    } else if (s === 'surface') {
      viewer.setStyle({}, { stick: { radius: 0.15 } })
      viewer.addSurface(window.$3Dmol.SurfaceType.VDW, { opacity: 0.7, colorscheme: 'whiteCarbon' }, {})
    }
  }

  const handleZoomIn = () => {
    if (viewerRef.current) viewerRef.current.zoom(1.2)
  }
  const handleZoomOut = () => {
    if (viewerRef.current) viewerRef.current.zoom(0.8)
  }
  const handleReset = () => {
    if (viewerRef.current) {
      viewerRef.current.zoomTo()
      viewerRef.current.rotate(0, { x: 0, y: 0, z: 0 })
    }
  }
  const handleFullscreen = () => {
    if (containerRef.current) {
      if (containerRef.current.requestFullscreen) {
        containerRef.current.requestFullscreen()
      }
    }
  }
  const handleScreenshot = () => {
    if (viewerRef.current) {
      const png = viewerRef.current.pngURI()
      const link = document.createElement('a')
      link.href = png
      link.download = `${title.replace(/\s+/g, '_')}_3d.png`
      link.click()
    }
  }

  const bgColors = [
    { label: '白', value: 'white' },
    { label: '黑', value: 'black' },
    { label: '灰', value: '#f3f4f6' },
  ]

  const styles = [
    { key: 'stick', label: '棍状', icon: '📏' },
    { key: 'ballStick', label: '球棍', icon: '⚽' },
    { key: 'sphere', label: '空间填充', icon: '🔮' },
    { key: 'line', label: '线框', icon: '📐' },
    { key: 'surface', label: '表面', icon: '🔮' },
  ]

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-2xl w-[95vw] max-w-5xl h-[90vh] flex overflow-hidden">

        {/* 左侧主区域 */}
        <div className="flex-1 flex flex-col min-w-0">
          {/* 标题栏 */}
          <div className="flex justify-between items-center px-5 py-3 border-b border-gray-200 bg-white">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-lg bg-slate-50 flex items-center justify-center">
                <Atom className="w-5 h-5 text-slate-700" />
              </div>
              <div>
                <h3 className="text-base font-bold text-gray-800">{title}</h3>
                {smiles && (
                  <p className="text-[10px] text-gray-400 font-mono mt-0.5 truncate max-w-md">
                    {smiles}
                  </p>
                )}
              </div>
            </div>
            <div className="flex items-center gap-1">
              <button
                onClick={() => setShowInfo(!showInfo)}
                className={`p-2 rounded-lg transition ${showInfo ? 'bg-slate-50 text-slate-700' : 'hover:bg-gray-100 text-gray-500'}`}
                title="信息面板"
              >
                <Info className="w-4 h-4" />
              </button>
              <button onClick={onClose} className="p-2 hover:bg-gray-100 rounded-lg transition">
                <X className="w-5 h-5 text-gray-500" />
              </button>
            </div>
          </div>

          {/* 工具栏 */}
          <div className="flex items-center gap-1.5 px-4 py-2 border-b border-gray-100 bg-gray-50/80">
            {/* 渲染样式 */}
            <div className="flex items-center gap-1 mr-3">
              <Layers className="w-3.5 h-3.5 text-gray-400 mr-1" />
              {styles.map((s) => (
                <button
                  key={s.key}
                  onClick={() => setStyle(s.key)}
                  className={`px-2.5 py-1 text-[11px] rounded-lg transition font-medium ${
                    style === s.key
                      ? 'bg-slate-700 text-white shadow-sm'
                      : 'bg-white border border-gray-200 text-gray-600 hover:bg-gray-50 hover:border-gray-300'
                  }`}
                >
                  {s.label}
                </button>
              ))}
            </div>

            <div className="w-px h-6 bg-gray-200 mx-1" />

            {/* 背景色 */}
            <div className="flex items-center gap-1 mr-3">
              <Palette className="w-3.5 h-3.5 text-gray-400 mr-1" />
              {bgColors.map((c) => (
                <button
                  key={c.value}
                  onClick={() => setBgColor(c.value)}
                  className={`w-6 h-6 rounded-lg border-2 transition ${
                    bgColor === c.value ? 'border-blue-500 ring-1 ring-blue-200' : 'border-gray-200 hover:border-gray-400'
                  }`}
                  style={{ backgroundColor: c.value === 'white' ? '#fff' : c.value === 'black' ? '#1a1a1a' : c.value }}
                  title={c.label}
                />
              ))}
            </div>

            <div className="w-px h-6 bg-gray-200 mx-1" />

            {/* 操作按钮 */}
            <div className="flex items-center gap-1">
              <button onClick={handleZoomIn} className="p-1.5 hover:bg-gray-200 rounded-lg transition" title="放大">
                <ZoomIn className="w-3.5 h-3.5 text-gray-600" />
              </button>
              <button onClick={handleZoomOut} className="p-1.5 hover:bg-gray-200 rounded-lg transition" title="缩小">
                <ZoomOut className="w-3.5 h-3.5 text-gray-600" />
              </button>
              <button onClick={handleReset} className="p-1.5 hover:bg-gray-200 rounded-lg transition" title="重置视角">
                <RotateCcw className="w-3.5 h-3.5 text-gray-600" />
              </button>
              <button
                onClick={() => setAutoRotate(!autoRotate)}
                className={`p-1.5 rounded-lg transition ${autoRotate ? 'bg-blue-100 text-slate-700' : 'hover:bg-gray-200 text-gray-600'}`}
                title="自动旋转"
              >
                {autoRotate ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
              </button>
              <button onClick={handleScreenshot} className="p-1.5 hover:bg-gray-200 rounded-lg transition" title="截图">
                <Camera className="w-3.5 h-3.5 text-gray-600" />
              </button>
              <button onClick={handleFullscreen} className="p-1.5 hover:bg-gray-200 rounded-lg transition" title="全屏">
                <Maximize className="w-3.5 h-3.5 text-gray-600" />
              </button>
            </div>
          </div>

          {/* 3D Viewer 区域 */}
          <div className="flex-1 relative bg-white overflow-hidden">
            {loading && (
              <div className="absolute inset-0 flex items-center justify-center bg-white z-10">
                <div className="text-center">
                  <div className="w-10 h-10 border-4 border-blue-100 border-t-blue-500 rounded-full animate-spin mx-auto mb-3" />
                  <p className="text-sm text-gray-500">正在加载3D结构...</p>
                  <p className="text-xs text-gray-400 mt-1">请稍候</p>
                </div>
              </div>
            )}
            {error && (
              <div className="absolute inset-0 flex items-center justify-center bg-white z-10">
                <div className="text-center">
                  <div className="w-12 h-12 rounded-full bg-red-50 flex items-center justify-center mx-auto mb-3">
                    <X className="w-6 h-6 text-red-400" />
                  </div>
                  <p className="text-red-500 font-medium mb-2">{error}</p>
                  <p className="text-sm text-gray-400">请尝试刷新或检查SMILES是否有效</p>
                </div>
              </div>
            )}
            <div
              ref={containerRef}
              style={{ width: '100%', height: '100%', position: 'relative', cursor: 'crosshair' }}
            />

            {/* 底部状态栏 */}
            <div className="absolute bottom-0 left-0 right-0 px-3 py-1.5 bg-white/80 backdrop-blur border-t border-gray-100 flex items-center justify-between text-[10px] text-gray-400">
              <div className="flex items-center gap-3">
                <span>原子: <span className="font-mono text-gray-600">{moleculeInfo.atoms}</span></span>
                <span>键: <span className="font-mono text-gray-600">{moleculeInfo.bonds}</span></span>
                {moleculeInfo.mw && (
                  <span>MW: <span className="font-mono text-gray-600">{moleculeInfo.mw.toFixed(1)}</span></span>
                )}
              </div>
              {hoverAtom && (
                <div className="flex items-center gap-2 text-slate-700">
                  <span>元素: <span className="font-mono font-bold">{hoverAtom.elem}</span></span>
                  <span>坐标: ({hoverAtom.x}, {hoverAtom.y}, {hoverAtom.z}) Å</span>
                </div>
              )}
              <div className="flex items-center gap-1">
                <Eye className="w-3 h-3" />
                <span>鼠标拖动旋转，滚轮缩放</span>
              </div>
            </div>
          </div>
        </div>

        {/* 右侧信息面板 */}
        {showInfo && (
          <div className="w-56 border-l border-gray-200 bg-gray-50/50 flex flex-col overflow-hidden">
            <div className="px-4 py-3 border-b border-gray-200">
              <div className="flex items-center gap-2">
                <Box className="w-4 h-4 text-gray-500" />
                <span className="text-sm font-semibold text-gray-700">分子信息</span>
              </div>
            </div>

            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {/* 基本信息 */}
              <div className="bg-white rounded-lg p-3 border border-gray-100">
                <div className="text-xs font-semibold text-gray-500 mb-2 flex items-center gap-1">
                  <Sparkles className="w-3 h-3" />
                  基本属性
                </div>
                <div className="space-y-1.5">
                  <div className="flex justify-between text-xs">
                    <span className="text-gray-400">原子数</span>
                    <span className="font-mono text-gray-700">{moleculeInfo.atoms}</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-gray-400">化学键</span>
                    <span className="font-mono text-gray-700">{moleculeInfo.bonds}</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-gray-400">分子量</span>
                    <span className="font-mono text-gray-700">{moleculeInfo.mw ? moleculeInfo.mw.toFixed(2) : '—'}</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-gray-400">分子式</span>
                    <span className="font-mono text-gray-700">{moleculeInfo.formula || '—'}</span>
                  </div>
                </div>
              </div>

              {/* 对接数据 */}
              {dockingData && (
                <div className="bg-white rounded-lg p-3 border border-gray-100">
                  <div className="text-xs font-semibold text-gray-500 mb-2 flex items-center gap-1">
                    <Atom className="w-3 h-3" />
                    对接数据
                  </div>
                  <div className="space-y-1.5">
                    <div className="flex justify-between text-xs">
                      <span className="text-gray-400">最佳结合能</span>
                      <span className="font-mono text-slate-700 font-bold">{dockingData.best_affinity} kcal/mol</span>
                    </div>
                    <div className="flex justify-between text-xs">
                      <span className="text-gray-400">构象数</span>
                      <span className="font-mono text-gray-700">{dockingData.num_poses}</span>
                    </div>
                    <div className="flex justify-between text-xs">
                      <span className="text-gray-400">搜索详尽度</span>
                      <span className="font-mono text-gray-700">{dockingData.exhaustiveness}</span>
                    </div>
                  </div>
                </div>
              )}

              {/* 操作提示 */}
              <div className="bg-white rounded-lg p-3 border border-gray-100">
                <div className="text-xs font-semibold text-gray-500 mb-2">操作指南</div>
                <div className="space-y-1 text-[10px] text-gray-400">
                  <div className="flex items-center gap-1.5">
                    <Rotate3D className="w-3 h-3" />
                    <span>左键拖动旋转视角</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <Move className="w-3 h-3" />
                    <span>右键拖动平移视角</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <ZoomIn className="w-3 h-3" />
                    <span>滚轮缩放大小</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <Eye className="w-3 h-3" />
                    <span>点击原子查看信息</span>
                  </div>
                </div>
              </div>
            </div>

            {/* 底部 */}
            <div className="px-4 py-2 border-t border-gray-200 bg-white text-[10px] text-gray-400 text-center">
              Powered by 3Dmol.js
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

// 解析分子基本信息
function parseMoleculeInfo(sdfData) {
  const info = { atoms: 0, bonds: 0, mw: null, formula: '' }
  try {
    const lines = sdfData.split('\n')
    let atomCount = 0, bondCount = 0, atomStartIndex = -1

    // 找到 V2000 行并提取原子数和键数
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i].trim()
      if (line.includes('V2000')) {
        const parts = line.split(/\s+/)
        if (parts.length >= 2) {
          atomCount = parseInt(parts[0]) || 0
          bondCount = parseInt(parts[1]) || 0
        }
        atomStartIndex = i + 1
        break
      }
    }

    info.atoms = atomCount
    info.bonds = bondCount

    if (atomStartIndex === -1 || atomCount === 0) {
      return info
    }

    // 从 V2000 行后开始读取原子坐标
    const atomCounts = {}
    for (let i = atomStartIndex; i < Math.min(atomStartIndex + atomCount, lines.length); i++) {
      const line = lines[i]
      // 方法1：按列宽解析（V2000 标准格式：第31-34列是元素符号）
      if (line.length >= 34) {
        const elem = line.substring(30, 34).trim()
        if (elem && elem.length <= 2 && elem[0] >= 'A' && elem[0] <= 'Z') {
          atomCounts[elem] = (atomCounts[elem] || 0) + 1
          continue
        }
      }
      // 方法2：按空格分隔解析（fallback）
      const parts = line.trim().split(/\s+/)
      if (parts.length >= 4) {
        // 元素符号通常在第4个位置（前3个是x,y,z坐标）
        // 但也可能是第3个（如果第一个坐标前面没有空格）
        for (let j = 2; j < Math.min(parts.length, 6); j++) {
          const p = parts[j]
          if (p.length >= 1 && p.length <= 2 && p[0] >= 'A' && p[0] <= 'Z') {
            // 排除看起来像数字的
            if (!/^[\-\d.]+$/.test(p)) {
              atomCounts[p] = (atomCounts[p] || 0) + 1
              break
            }
          }
        }
      }
    }

    // 计算分子式
    const formulaParts = []
    const order = ['C', 'H', 'N', 'O', 'S', 'P', 'F', 'Cl', 'Br', 'I', 'B', 'Si', 'Se']
    for (const elem of order) {
      if (atomCounts[elem]) {
        formulaParts.push(atomCounts[elem] > 1 ? `${elem}${atomCounts[elem]}` : elem)
      }
    }
    for (const elem of Object.keys(atomCounts).sort()) {
      if (!order.includes(elem)) {
        formulaParts.push(atomCounts[elem] > 1 ? `${elem}${atomCounts[elem]}` : elem)
      }
    }
    info.formula = formulaParts.join('')

    // 粗略估算分子量
    const weights = { C: 12.01, H: 1.008, N: 14.01, O: 16.00, S: 32.06, P: 30.97, F: 19.00, Cl: 35.45, Br: 79.90, I: 126.9, B: 10.81, Si: 28.09, Se: 78.96 }
    let mw = 0
    for (const [elem, count] of Object.entries(atomCounts)) {
      mw += (weights[elem] || 0) * count
    }
    info.mw = mw > 0 ? mw : null
  } catch (e) {
    console.error('解析分子信息失败:', e)
  }
  return info
}

// 动态加载3Dmol.js
function load3DmolScript() {
  return new Promise((resolve, reject) => {
    if (window.$3Dmol) {
      resolve()
      return
    }
    const script = document.createElement('script')
    script.src = 'https://3Dmol.csb.pitt.edu/build/3Dmol-min.js'
    script.onload = () => resolve()
    script.onerror = () => reject(new Error('3Dmol.js加载失败'))
    document.head.appendChild(script)
  })
}
