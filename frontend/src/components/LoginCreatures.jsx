import React, { useEffect, useRef, useState, useCallback } from 'react'

/* ============================================================
   LoginCreatures V5 — 商用级精致动画
   特性：分段身体扭动、z-index重叠层次、弹性跟随、精致极简
   ============================================================ */

// ============ 工具组件 ============

/** 极简眼睛：白底黑瞳 / 纯黑瞳 */
function Eye({ cx, cy, lookAt, size = 13, pupil = 5, darkOnly = false, blinking }) {
  const maxOff = size * 0.20
  const dx = lookAt.x - cx
  const dy = lookAt.y - cy
  const dist = Math.sqrt(dx * dx + dy * dy)
  const ratio = dist < 0.5 ? 0 : (Math.min(dist, 70) / dist) * (maxOff / 5)
  const px = dx * ratio * 0.15
  const py = dy * ratio * 0.15

  if (darkOnly) {
    return (
      <div
        className="absolute rounded-full bg-slate-900 transition-transform duration-75"
        style={{
          width: size, height: size,
          left: cx - size / 2, top: cy - size / 2,
          transform: blinking ? 'scaleY(0.12)' : `translate(${px}px, ${py}px)`,
        }}
      />
    )
  }
  return (
    <div
      className="absolute flex items-center justify-center rounded-full bg-white transition-transform duration-75"
      style={{
        width: size, height: size,
        left: cx - size / 2, top: cy - size / 2,
        transform: blinking ? 'scaleY(0.12)' : 'none',
        boxShadow: 'inset 0 1px 2px rgba(0,0,0,0.06)',
      }}
    >
      <div
        className="rounded-full bg-slate-900"
        style={{ width: pupil, height: pupil, transform: `translate(${px}px, ${py}px)` }}
      />
    </div>
  )
}

/** 闭眼线 */
function ClosedLine({ cx, cy, w = 14, color = '#1f2937' }) {
  return (
    <div className="absolute h-[2.5px] rounded-full" style={{ width: w, left: cx - w / 2, top: cy, background: color }} />
  )
}

/** 微笑 SVG */
function Smile({ cx, cy, w = 14, color = '#1f2937' }) {
  return (
    <svg className="absolute" style={{ left: cx - w / 2, top: cy - 5, width: w, height: 10 }} viewBox={`0 0 ${w} 10`}>
      <path d={`M 2 3 Q ${w / 2} 10, ${w - 2} 3`} fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" />
    </svg>
  )
}

/** 悲伤嘴 SVG */
function Sad({ cx, cy, w = 16, color = '#1f2937' }) {
  return (
    <svg className="absolute" style={{ left: cx - w / 2, top: cy - 4, width: w, height: 10 }} viewBox={`0 0 ${w} 10`}>
      <path d={`M 2 7 Q ${w / 2} -1, ${w - 2} 7`} fill="none" stroke={color} strokeWidth="2.5" strokeLinecap="round" />
    </svg>
  )
}

/** 波浪嘴 */
function Wavy({ cx, cy, w = 18, color = '#1f2937' }) {
  return (
    <svg className="absolute" style={{ left: cx - w / 2, top: cy - 3, width: w, height: 8 }} viewBox={`0 0 ${w} 8`}>
      <path d={`M 2 4 Q 5 1, 9 4 T 17 4`} fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" />
    </svg>
  )
}

/** 耷拉眼（黑色悲伤） */
function Droopy({ cx, cy, size = 13 }) {
  return (
    <div className="absolute" style={{ width: size, height: size, left: cx - size / 2, top: cy - size / 2 }}>
      <div className="w-full h-full rounded-full bg-white" />
      <div className="absolute top-0 left-0 w-full h-[55%] bg-slate-900 rounded-t-full" />
    </div>
  )
}

// ============ 主组件 ============

export default function LoginCreatures({ isPasswordFocused, isEmailFocused, isSad, className = '' }) {
  const ref = useRef(null)
  const [look, setLook] = useState({ x: 150, y: 100 })
  const raw = useRef({ x: 150, y: 100 })
  const raf = useRef(null)
  const [blink, setBlink] = useState({ o: false, p: false, b: false, y: false })

  const [mouseActive, setMouseActive] = useState(false)

  // 平滑追踪
  useEffect(() => {
    const onMove = (e) => {
      if (!ref.current) return
      const r = ref.current.getBoundingClientRect()
      raw.current = { x: e.clientX - r.left, y: e.clientY - r.top }
      if (!mouseActive) setMouseActive(true)
    }
    window.addEventListener('mousemove', onMove)
    const tick = () => {
      setLook(prev => ({
        x: prev.x + (raw.current.x - prev.x) * 0.12,
        y: prev.y + (raw.current.y - prev.y) * 0.12,
      }))
      raf.current = requestAnimationFrame(tick)
    }
    raf.current = requestAnimationFrame(tick)
    return () => { window.removeEventListener('mousemove', onMove); cancelAnimationFrame(raf.current) }
  }, [mouseActive])

  // 随机眨眼
  useEffect(() => {
    const ids = [
      setInterval(() => { setBlink(p => ({ ...p, o: true })); setTimeout(() => setBlink(p => ({ ...p, o: false })), 130) }, 3100 + Math.random() * 1400),
      setInterval(() => { setBlink(p => ({ ...p, p: true })); setTimeout(() => setBlink(p => ({ ...p, p: false })), 130) }, 2700 + Math.random() * 1700),
      setInterval(() => { setBlink(p => ({ ...p, b: true })); setTimeout(() => setBlink(p => ({ ...p, b: false })), 130) }, 3500 + Math.random() * 1500),
      setInterval(() => { setBlink(p => ({ ...p, y: true })); setTimeout(() => setBlink(p => ({ ...p, y: false })), 130) }, 2900 + Math.random() * 1800),
    ]
    return () => ids.forEach(clearInterval)
  }, [])

  const shy = isPasswordFocused
  const sad = isSad
  const curious = isEmailFocused  // 填写邮箱时"靠近看"

  // 计算身体跟随鼠标的旋转（从底部中心起）
  const getBodyRotate = useCallback((baseX, baseY, baseAngle = 0, factor = 0.25) => {
    if (curious) return baseAngle - 8  // email focus: 身体前倾
    if (!mouseActive) return baseAngle  // 初始未移动鼠标：保持中立
    const dx = look.x - baseX
    const dy = look.y - baseY
    const angle = Math.atan2(dy, dx) * (180 / Math.PI)
    const clamped = Math.max(-35, Math.min(35, (angle - 90) * factor))
    return baseAngle + clamped
  }, [look, curious, mouseActive])

  const getFaceRotate = useCallback((baseX, baseY, factor = 0.45) => {
    if (curious) return -5  // email focus: 脸朝前下方
    if (!mouseActive) return 0  // 初始未移动鼠标：保持中立
    const dx = look.x - baseX
    const dy = look.y - baseY
    const angle = Math.atan2(dy, dx) * (180 / Math.PI)
    return Math.max(-45, Math.min(45, (angle - 90) * factor))
  }, [look, curious, mouseActive])

  // 基础位置（整体上移 12px）
  const pBase = { x: 140, y: 108 }
  const bBase = { x: 190, y: 128 }
  const oBase = { x: 65,  y: 148 }
  const yBase = { x: 240, y: 138 }

  // 角度计算
  const pBodyR = shy ? -22 : sad ? 14 : getBodyRotate(pBase.x, pBase.y, 0, 0.20)
  const pFaceR = shy ? -32 : sad ? 20 : getFaceRotate(pBase.x, pBase.y, 0.40)

  const bBodyR = shy ? -16 : sad ? 10 : getBodyRotate(bBase.x, bBase.y, 0, 0.22)
  const bFaceR = shy ? -26 : sad ? 16 : getFaceRotate(bBase.x, bBase.y, 0.42)

  const oBodyR = shy ? -10 : sad ? 8 : getBodyRotate(oBase.x, oBase.y, 0, 0.18)
  const oFaceR = shy ? -16 : sad ? 12 : getFaceRotate(oBase.x, oBase.y, 0.30)

  const yBodyR = shy ? -12 : sad ? 10 : getBodyRotate(yBase.x, yBase.y, 0, 0.20)
  const yFaceR = shy ? -20 : sad ? 14 : getFaceRotate(yBase.x, yBase.y, 0.38)

  // 眼睛偏移微调（curious 时眼睛稍微睁大/更聚焦）
  const eyeScale = curious ? 1.12 : 1

  // shy 时看向左侧固定点，curious 时正常追踪
  const lookLeft = { x: -400, y: 60 }
  const lookTarget = shy ? lookLeft : look

  return (
    <div ref={ref} className={`relative w-full h-full overflow-hidden ${className}`}>
      <style>{`
        @keyframes dropO{0%{transform:translateY(-180px) scale(.5);opacity:0} 58%{transform:translateY(6px) scale(1.05)} 76%{transform:translateY(-5px) scale(.97)} 90%{transform:translateY(2px) scale(1.01)} 100%{transform:translateY(0) scale(1);opacity:1}}
        @keyframes dropP{0%,14%{transform:translateY(-180px) scale(.5);opacity:0} 60%{transform:translateY(6px) scale(1.05)} 78%{transform:translateY(-4px) scale(.97)} 92%{transform:translateY(2px) scale(1.01)} 100%{transform:translateY(0) scale(1);opacity:1}}
        @keyframes dropB{0%,28%{transform:translateY(-180px) scale(.5);opacity:0} 62%{transform:translateY(6px) scale(1.05)} 80%{transform:translateY(-3px) scale(.98)} 93%{transform:translateY(1px) scale(1)} 100%{transform:translateY(0) scale(1);opacity:1}}
        @keyframes dropY{0%,42%{transform:translateY(-180px) scale(.5);opacity:0} 64%{transform:translateY(6px) scale(1.05)} 82%{transform:translateY(-2px) scale(.98)} 94%{transform:translateY(1px) scale(1)} 100%{transform:translateY(0) scale(1);opacity:1}}
        .dO{animation:dropO .9s cubic-bezier(.34,1.56,.64,1) forwards}
        .dP{animation:dropP 1.0s cubic-bezier(.34,1.56,.64,1) forwards}
        .dB{animation:dropB 1.1s cubic-bezier(.34,1.56,.64,1) forwards}
        .dY{animation:dropY 1.2s cubic-bezier(.34,1.56,.64,1) forwards}
      `}</style>

      {/* ========== 紫色（最后层） ========== */}
      <div className="absolute bottom-5 left-[108px] dP" style={{ width: 60, height: 170, zIndex: 1 }}>
        <div className="relative w-full h-full">
          {/* 身体 */}
          <div
            className="absolute bottom-0 left-1 transition-transform duration-300 ease-out"
            style={{
              width: 54, height: 158,
              background: '#7C3AED',
              borderRadius: '3px 3px 5px 5px',
              transform: `rotate(${pBodyR}deg) skewX(${pBodyR * 0.25}deg)`,
              transformOrigin: '50% 90%',
            }}
          />
          {/* 五官 — 旋转更多（扭动效果） */}
          <div
            className="absolute bottom-0 left-1 transition-transform duration-300 ease-out pointer-events-none"
            style={{
              width: 54, height: 158,
              transform: `rotate(${pFaceR}deg) skewX(${pFaceR * 0.3}deg)`,
              transformOrigin: '50% 88%',
            }}
          >
            {sad ? (
              <>
                <Eye lookAt={{ x: 0, y: 0 }} blinking={blink.p} cx={17} cy={28} size={12} pupil={4.5} />
                <Eye lookAt={{ x: 0, y: 0 }} blinking={blink.p} cx={37} cy={28} size={12} pupil={4.5} />
                <Sad cx={27} cy={48} w={16} />
              </>
            ) : shy ? (
              <>
                <Eye lookAt={lookLeft} blinking={blink.p} cx={17} cy={28} size={12} pupil={4.5} />
                <Eye lookAt={lookLeft} blinking={blink.p} cx={37} cy={28} size={12} pupil={4.5} />
                <div className="absolute w-[2px] h-3 bg-slate-900 rounded-full" style={{ left: 26, top: 46 }} />
              </>
            ) : (
              <>
                <Eye lookAt={lookTarget} blinking={blink.p} cx={17} cy={26} size={12} pupil={4.5} />
                <Eye lookAt={lookTarget} blinking={blink.p} cx={37} cy={26} size={12} pupil={4.5} />
                <Smile cx={27} cy={44} w={11} />
              </>
            )}
          </div>
        </div>
      </div>

      {/* ========== 橙色（中间层，底座） ========== */}
      <div className="absolute bottom-5 left-0 dO" style={{ width: 150, height: 100, zIndex: 2 }}>
        <div className="relative w-full h-full">
          {/* 身体 */}
          <div
            className="absolute bottom-0 left-3 transition-transform duration-300 ease-out"
            style={{
              width: 130, height: 82,
              background: '#FB923C',
              borderRadius: '65px 65px 8px 8px',
              transform: `rotate(${oBodyR}deg)`,
              transformOrigin: '50% 90%',
            }}
          />
          {/* 五官 */}
          <div
            className="absolute bottom-0 left-3 transition-transform duration-300 ease-out pointer-events-none"
            style={{
              width: 130, height: 82,
              transform: `rotate(${oFaceR}deg)`,
              transformOrigin: '50% 88%',
            }}
          >
            {sad ? (
              <>
                <ClosedLine cx={42} cy={30} w={11} />
                <ClosedLine cx={88} cy={30} w={11} />
                <Sad cx={65} cy={46} w={20} />
              </>
            ) : shy ? (
              <>
                <div className="absolute w-1.5 h-1.5 bg-slate-900 rounded-full" style={{ left: 38, top: 28 }} />
                <div className="absolute w-1.5 h-1.5 bg-slate-900 rounded-full" style={{ left: 56, top: 26 }} />
                <div className="absolute w-1.5 h-1.5 bg-slate-900 rounded-full" style={{ left: 74, top: 28 }} />
              </>
            ) : (
              <>
                <Eye lookAt={lookTarget} blinking={blink.o} cx={45} cy={30} size={7} darkOnly />
                <Eye lookAt={lookTarget} blinking={blink.o} cx={85} cy={30} size={7} darkOnly />
                <Smile cx={65} cy={44} w={15} />
              </>
            )}
          </div>
        </div>
      </div>

      {/* ========== 黑色（中前层） ========== */}
      <div className="absolute bottom-5 left-[158px] dB" style={{ width: 52, height: 125, zIndex: 3 }}>
        <div className="relative w-full h-full">
          {/* 身体 */}
          <div
            className="absolute bottom-0 left-1 transition-transform duration-300 ease-out"
            style={{
              width: 48, height: 115,
              background: '#1F2937',
              borderRadius: '4px 4px 5px 5px',
              transform: `rotate(${bBodyR}deg) skewX(${bBodyR * 0.2}deg)`,
              transformOrigin: '50% 90%',
            }}
          />
          {/* 五官 */}
          <div
            className="absolute bottom-0 left-1 transition-transform duration-300 ease-out pointer-events-none"
            style={{
              width: 48, height: 115,
              transform: `rotate(${bFaceR}deg) skewX(${bFaceR * 0.25}deg)`,
              transformOrigin: '50% 88%',
            }}
          >
            {sad ? (
              <>
                <Droopy cx={16} cy={26} size={13} />
                <Droopy cx={34} cy={26} size={13} />
              </>
            ) : shy ? (
              <>
                <Eye lookAt={lookLeft} blinking={blink.b} cx={16} cy={26} size={13} pupil={5} />
                <Eye lookAt={lookLeft} blinking={blink.b} cx={34} cy={26} size={13} pupil={5} />
              </>
            ) : (
              <>
                <Eye lookAt={lookTarget} blinking={blink.b} cx={16} cy={24} size={13} pupil={5} />
                <Eye lookAt={lookTarget} blinking={blink.b} cx={34} cy={24} size={13} pupil={5} />
              </>
            )}
          </div>
        </div>
      </div>

      {/* ========== 黄色（最前层） ========== */}
      <div className="absolute bottom-5 left-[208px] dY" style={{ width: 62, height: 110, zIndex: 4 }}>
        <div className="relative w-full h-full">
          {/* 身体 */}
          <div
            className="absolute bottom-0 left-1 transition-transform duration-300 ease-out"
            style={{
              width: 54, height: 95,
              background: '#EAB308',
              borderRadius: '27px 27px 6px 6px',
              transform: `rotate(${yBodyR}deg) skewX(${yBodyR * -0.2}deg)`,
              transformOrigin: '50% 90%',
            }}
          />
          {/* 五官 */}
          <div
            className="absolute bottom-0 left-1 transition-transform duration-300 ease-out pointer-events-none"
            style={{
              width: 54, height: 95,
              transform: `rotate(${yFaceR}deg) skewX(${yFaceR * -0.25}deg)`,
              transformOrigin: '50% 88%',
            }}
          >
            {sad ? (
              <>
                <Eye lookAt={{ x: 0, y: 0 }} blinking={blink.y} cx={18} cy={30} size={12} pupil={4.5} />
                <Eye lookAt={{ x: 0, y: 0 }} blinking={blink.y} cx={36} cy={30} size={12} pupil={4.5} />
                <Wavy cx={27} cy={52} w={16} />
              </>
            ) : shy ? (
              <>
                <Eye lookAt={lookLeft} blinking={blink.y} cx={18} cy={30} size={12} pupil={4.5} />
                <Eye lookAt={lookLeft} blinking={blink.y} cx={36} cy={30} size={12} pupil={4.5} />
                <div className="absolute h-[2px] bg-slate-900 rounded-full" style={{ width: 14, left: 20, top: 52 }} />
              </>
            ) : (
              <>
                <Eye lookAt={lookTarget} blinking={blink.y} cx={18} cy={28} size={12} pupil={4.5} />
                <Eye lookAt={lookTarget} blinking={blink.y} cx={36} cy={28} size={12} pupil={4.5} />
                <div className="absolute h-[2.5px] bg-slate-900 rounded-full" style={{ width: 16, left: 19, top: 50 }} />
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
