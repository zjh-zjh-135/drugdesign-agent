import React from 'react'

const SUCCESS_STATUSES = ['completed', 'admet_passed', 'synthesis_passed']
const FAILED_STATUSES = ['failed']

const statusLabels = {
  'pending': '待执行',
  'running': '运行中',
  'completed': '已完成',
  'failed': '失败',
  'generated': '已生成',
  'filtered': '已过滤',
  'structure_screened': '结构筛选',
  'admet_passed': 'ADMET通过',
  'refined': '已精筛',
  'synthesis_passed': '合成通过',
}

const themeMap = {
  success: { bg: 'bg-emerald-50', text: 'text-emerald-700', border: 'border-emerald-200' },
  failed: { bg: 'bg-rose-50', text: 'text-rose-700', border: 'border-rose-200' },
  default: { bg: 'bg-slate-50', text: 'text-slate-600', border: 'border-slate-200' },
}

function getTheme(status) {
  if (SUCCESS_STATUSES.includes(status)) return themeMap.success
  if (FAILED_STATUSES.includes(status)) return themeMap.failed
  return themeMap.default
}

export default function StatusBadge({ status }) {
  const theme = getTheme(status)
  const label = statusLabels[status] || statusLabels['pending']
  return (
    <span className={`inline-flex px-2 py-0.5 rounded-md text-[10px] font-semibold border ${theme.bg} ${theme.text} ${theme.border}`}>
      {label}
    </span>
  )
}
