import React, { useEffect, useState, useRef } from 'react'

const RAINBOW = [
  '#F59E0B', '#F97316', '#EF4444', '#EC4899',
  '#8B5CF6', '#3B82F6', '#06B6D4', '#10B981',
  '#D97706', // 第9步：数据回流 - 琥珀金
]

const CENTER = 90
const RING_R = 70
const RING_WIDTH = 16
const GAP = 3

function arcPath(cx, cy, r, startAngle, endAngle) {
  const toRad = (deg) => (deg - 90) * (Math.PI / 180)
  const start = toRad(startAngle)
  const end = toRad(endAngle)
  const x1 = cx + r * Math.cos(start)
  const y1 = cy + r * Math.sin(start)
  const x2 = cx + r * Math.cos(end)
  const y2 = cy + r * Math.sin(end)
  const largeArc = endAngle - startAngle > 180 ? 1 : 0
  return `M ${x1} ${y1} A ${r} ${r} 0 ${largeArc} 1 ${x2} ${y2}`
}

export default function CircularPipelineProgress({ status, stepStatus, enableFailedIteration }) {
  const [progress, setProgress] = useState(0)
  const targetRef = useRef(0)
  const rafRef = useRef(null)

  const stepCount = enableFailedIteration ? 9 : 8
  const stepAngle = 360 / stepCount

  useEffect(() => {
    const statuses = Array.from({ length: stepCount }, (_, i) => stepStatus(i))
    const completed = statuses.filter((s) => s === 'completed').length
    const runningIdx = statuses.findIndex((s) => s === 'running')
    let target = 0
    if (completed > 0) target = completed * (100 / stepCount)
    if (runningIdx !== -1) target += (100 / stepCount) * 0.5
    if (status === 'completed') target = 100
    targetRef.current = target
  }, [status, stepStatus, stepCount])

  useEffect(() => {
    const animate = () => {
      setProgress((prev) => {
        const diff = targetRef.current - prev
        if (Math.abs(diff) < 0.3) return targetRef.current
        return prev + diff * 0.04
      })
      rafRef.current = requestAnimationFrame(animate)
    }
    rafRef.current = requestAnimationFrame(animate)
    return () => cancelAnimationFrame(rafRef.current)
  }, [status])

  const stepFill = (stepIndex) => {
    const stepStart = stepIndex * (100 / stepCount)
    const stepEnd = (stepIndex + 1) * (100 / stepCount)
    if (progress >= stepEnd) return 1
    if (progress <= stepStart) return 0
    return (progress - stepStart) / (100 / stepCount)
  }

  return (
    <div className="relative" style={{ width: 180, height: 180 }}>
      <svg width="180" height="180" viewBox={`0 0 ${CENTER * 2} ${CENTER * 2}`}>
        <defs>
          {Array.from({ length: stepCount }, (_, i) => {
            const c1 = RAINBOW[i]
            const c2 = RAINBOW[(i + 1) % stepCount]
            const midAngle = (i * stepAngle + stepAngle / 2) * (Math.PI / 180)
            const dx = Math.cos(midAngle) * 50
            const dy = Math.sin(midAngle) * 50
            return (
              <linearGradient
                key={`grad-${i}`}
                id={`grad-${i}`}
                x1={`${50 - dx}%`}
                y1={`${50 - dy}%`}
                x2={`${50 + dx}%`}
                y2={`${50 + dy}%`}
              >
                <stop offset="0%" stopColor={c1} />
                <stop offset="100%" stopColor={c2} />
              </linearGradient>
            )
          })}
        </defs>

        {/* 背景环段 — 灰色 */}
        {Array.from({ length: stepCount }, (_, i) => {
          const start = i * stepAngle
          const end = (i + 1) * stepAngle - GAP
          return (
            <path
              key={`bg-${i}`}
              d={arcPath(CENTER, CENTER, RING_R, start, end)}
              fill="none"
              stroke="#e2e8f0"
              strokeWidth={RING_WIDTH}
              strokeLinecap="round"
            />
          )
        })}

        {/* 进度环段 — 彩虹渐变 */}
        {Array.from({ length: stepCount }, (_, i) => {
          const fill = stepFill(i)
          if (fill <= 0) return null
          const start = i * stepAngle
          const end = start + (stepAngle - GAP) * fill
          return (
            <path
              key={`fg-${i}`}
              d={arcPath(CENTER, CENTER, RING_R, start, end)}
              fill="none"
              stroke={`url(#grad-${i})`}
              strokeWidth={RING_WIDTH}
              strokeLinecap="round"
              style={{ transition: 'all 0.3s ease-out' }}
            />
          )
        })}

        {/* 中心白色圆底 */}
        <circle cx={CENTER} cy={CENTER} r="35" fill="white" />
        <circle cx={CENTER} cy={CENTER} r="35" fill="none" stroke="#e2e8f0" strokeWidth="1.5" />

        {/* 百分比 */}
        <text
          x={CENTER}
          y={CENTER - 3}
          textAnchor="middle"
          dominantBaseline="central"
          fill="#1e293b"
          style={{ fontSize: '24px', fontWeight: 800, fontFamily: 'ui-sans-serif, system-ui, sans-serif' }}
        >
          {Math.round(progress)}%
        </text>

        {/* 状态标签 */}
        <text
          x={CENTER}
          y={CENTER + 18}
          textAnchor="middle"
          dominantBaseline="central"
          fill="#64748b"
          style={{ fontSize: '10px', fontWeight: 600, letterSpacing: '0.06em', fontFamily: 'ui-sans-serif, system-ui, sans-serif' }}
        >
          {status === 'running' ? 'RUNNING' : status === 'completed' ? 'COMPLETED' : status === 'failed' ? 'FAILED' : 'READY'}
        </text>
      </svg>
    </div>
  )
}
