import React from 'react'

export default function FunnelViz({ data }) {
  const maxCount = data[0]?.value || 1
  const colorScale = [
    'bg-slate-700',
    'bg-slate-600',
    'bg-slate-500',
    'bg-slate-400',
    'bg-slate-300',
    'bg-slate-300',
    'bg-slate-200',
    'bg-slate-200',
  ]

  return (
    <div className="flex flex-col items-center gap-1.5 py-2">
      {data.map((d, i) => {
        const pct = Math.max(20, (d.value / maxCount) * 100)
        const colorClass = colorScale[i] || colorScale[7]
        return (
          <div
            key={i}
            style={{ width: `${pct}%` }}
            className="min-w-[240px]"
          >
            <div className="flex items-center bg-white rounded-md border border-slate-200 overflow-hidden">
              <div className={`w-1 self-stretch ${colorClass}`} />
              <div className="flex-1 flex items-center px-4 py-2.5">
                {/* 左侧阶段名 */}
                <div className="flex-1">
                  <span className="text-sm font-medium text-gray-800">{d.name}</span>
                </div>
                {/* 中间竖线 + 数字 */}
                <div className="flex items-center gap-2">
                  <div className="w-px h-5 bg-gray-200" />
                  <span className="text-sm font-mono font-bold text-gray-900 w-12 text-center">
                    {d.value.toLocaleString()}
                  </span>
                </div>
                {/* 右侧百分比 */}
                {d.rate && d.rate !== '100%' && (
                  <div className="ml-3 text-xs font-medium text-gray-500 w-10 text-right">
                    {d.rate}
                  </div>
                )}
                {d.rate === '100%' && (
                  <div className="ml-3 text-xs font-medium text-gray-400 w-10 text-right">
                    —
                  </div>
                )}
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}
