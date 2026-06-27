import React, { useRef, useEffect, useState } from 'react'

export default function MoleculeSVG({ moleculeId, smiles, size = 200, className = '' }) {
  const canvasRef = useRef(null)
  const [loading, setLoading] = useState(true)
  const [useFallback, setUseFallback] = useState(false)
  const [imgError, setImgError] = useState(false)

  // 1. 直接用 <img> 加载 SVG，更简单可靠
  const svgUrl = `/api/molecules/${moleculeId}/svg`

  // 2. 后端失败 → 用 smiles-drawer 前端渲染
  useEffect(() => {
    if (!useFallback || !smiles || !canvasRef.current) return
    let cancelled = false
    const render = async () => {
      try {
        const SmilesDrawer = await import('smiles-drawer')
        const SMD = SmilesDrawer.default || SmilesDrawer
        const drawer = new SMD.Drawer({ width: size, height: size })
        SMD.parse(smiles, (tree) => {
          if (!cancelled) {
            drawer.draw(tree, canvasRef.current, 'light')
          }
        })
      } catch (e) {
        // smiles-drawer 也失败，什么都不做，显示占位符
      }
    }
    render()
    return () => { cancelled = true }
  }, [useFallback, smiles, size])

  if (loading && !useFallback) {
    return (
      <div className={`bg-gray-100 animate-pulse rounded ${className}`} style={{ width: size, height: size }}>
        <img
          src={svgUrl}
          alt="molecule"
          className="opacity-0"
          style={{ width: size, height: size }}
          onLoad={() => setLoading(false)}
          onError={() => { setLoading(false); setUseFallback(true); setImgError(true) }}
        />
      </div>
    )
  }

  if (!useFallback && !imgError) {
    return (
      <img
        src={svgUrl}
        alt="molecule"
        className={className}
        style={{ width: size, height: size }}
        onLoad={() => setLoading(false)}
        onError={() => { setLoading(false); setUseFallback(true); setImgError(true) }}
      />
    )
  }

  if (useFallback) {
    return <canvas ref={canvasRef} width={size} height={size} className={className} />
  }

  return (
    <div className={`bg-gray-50 flex items-center justify-center text-gray-400 text-xs rounded ${className}`} style={{ width: size, height: size }}>
      无图片
    </div>
  )
}
