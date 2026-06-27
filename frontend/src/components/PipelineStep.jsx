import React from 'react'
import { Upload, GitBranch, Filter, Atom, Activity, Zap, FlaskConical, Check, RefreshCw } from 'lucide-react'

const stepNames = [
  '输入层',
  '生成层',
  '基础过滤',
  '结构筛选',
  'ADMET',
  'FEP精筛',
  '合成筛选',
  '输出层',
  '数据回流',
]

const stepIcons = [Upload, GitBranch, Filter, Atom, Activity, Zap, FlaskConical, Check, RefreshCw]

// 彩虹色分布：9个步骤对应9种颜色
const stepColors = [
  { name: 'amber', hex: '#F59E0B', light: '#FFFBEB', border: '#FCD34D', text: '#92400E' },   // 0 输入层 - 金
  { name: 'orange', hex: '#F97316', light: '#FFF7ED', border: '#FDBA74', text: '#C2410C' }, // 1 生成层 - 橙
  { name: 'rose', hex: '#F43F5E', light: '#FFF1F2', border: '#FDA4AF', text: '#BE123C' },  // 2 基础过滤 - 红
  { name: 'pink', hex: '#EC4899', light: '#FDF2F8', border: '#F9A8D4', text: '#BE185D' },   // 3 结构筛选 - 粉红
  { name: 'violet', hex: '#8B5CF6', light: '#F5F3FF', border: '#C4B5FD', text: '#6D28D9' },  // 4 ADMET - 紫
  { name: 'blue', hex: '#3B82F6', light: '#EFF6FF', border: '#93C5FD', text: '#1D4ED8' },    // 5 FEP精筛 - 蓝
  { name: 'cyan', hex: '#06B6D4', light: '#ECFEFF', border: '#67E8F9', text: '#0E7490' },   // 6 合成筛选 - 青
  { name: 'emerald', hex: '#10B981', light: '#ECFDF5', border: '#6EE7B7', text: '#047857' },  // 7 输出层 - 绿
  { name: 'amber', hex: '#D97706', light: '#FFFBEB', border: '#FBBF24', text: '#92400E' },     // 8 数据回流 - 琥珀金
]

export default function PipelineStep({ step, status, count, total }) {
  const color = stepColors[step]

  const statusStyles = {
    pending: 'bg-slate-50 border-slate-200 text-slate-400',
    running: `bg-white border-[${color.hex}] text-[${color.hex}]`,
    completed: `bg-[${color.hex}] border-[${color.hex}] text-white`,
    failed: 'bg-white border-slate-200 text-slate-400 border-b-2 border-b-rose-500',
  }

  const Icon = stepIcons[step]

  return (
    <div
      className={`flex flex-col items-center p-2 rounded-lg border-2 min-w-[80px] transition-all ${statusStyles[status] || statusStyles.pending}`}
      style={
        status === 'completed'
          ? { backgroundColor: color.hex, borderColor: color.hex }
          : status === 'running'
          ? { borderColor: color.hex }
          : {}
      }
    >
      <Icon className="w-5 h-5 mb-0.5" style={status === 'running' ? { color: color.hex } : {}} />
      <div className="text-[10px] font-medium">{stepNames[step]}</div>
      {count !== undefined && total !== undefined && (
        <div className="text-[10px] mt-0.5 font-mono">
          {count.toLocaleString()} / {total.toLocaleString()}
        </div>
      )}
    </div>
  )
}
