import React from 'react'
import { Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer } from 'recharts'

function safeVal(val) {
  if (val === null || val === undefined || Number.isNaN(val)) return 0
  const n = Number(val)
  return Number.isFinite(n) ? n : 0
}

function normalize(value, min, max) {
  const v = safeVal(value)
  const pct = (v - min) / (max - min) * 100
  return Math.max(0, Math.min(100, pct))
}

// 将风险概率转换为安全分（0-100）
function safetyScore(risk) {
  const r = safeVal(risk)
  // 如果值 >1，可能已经是百分比（0-100），转为概率
  const p = r > 1 ? r / 100 : r
  return (1 - p) * 100
}

// 从5分类或旧结构提取数据
function extractData(raw) {
  if (!raw) return {}
  const abs = raw.absorption || {}
  const dist = raw.distribution || {}
  const met = raw.metabolism || {}
  const tox = raw.toxicity || {}

  return {
    solubility: abs.solubility !== undefined ? abs.solubility : raw.solubility,
    permeability: abs.permeability !== undefined ? abs.permeability : raw.permeability,
    oral_bioavailability: abs.oral_bioavailability !== undefined ? abs.oral_bioavailability : raw.oral_bioavailability,
    bbb: dist.bbb !== undefined ? dist.bbb : raw.bbb,
    herg: tox.herg !== undefined ? tox.herg : raw.herg,
    ames: tox.ames !== undefined ? tox.ames : raw.ames,
    dili: tox.dili !== undefined ? tox.dili : raw.dili,
    cyp_inhibition: met.cyp_inhibition !== undefined ? met.cyp_inhibition : raw.cyp_inhibition,
  }
}

export default function AdmetRadar({ data }) {
  if (!data) return null

  const d = extractData(data)

  // 溶解度 logS 范围约 -5 到 +2，归一化到 0-100（-5→0, 2→100）
  const solNorm = normalize(d.solubility, -5, 2)
  // 渗透性 logCaco2 范围约 -8 到 0，归一化到 0-100（-8→0, 0→100）
  const permNorm = normalize(d.permeability, -8, 0)
  // BBB: 0-1，越高通透性越好
  const bbbNorm = Math.max(0, Math.min(100, safeVal(d.bbb) > 1 ? safeVal(d.bbb) : safeVal(d.bbb) * 100))
  // 口服BA: 0-1，越高越好
  const oralNorm = Math.max(0, Math.min(100, safeVal(d.oral_bioavailability) > 1 ? safeVal(d.oral_bioavailability) : safeVal(d.oral_bioavailability) * 100))
  // 毒性指标：转换为安全分
  const hERGSafe = safetyScore(d.herg)
  const AmesSafe = safetyScore(d.ames)
  const DILISafe = safetyScore(d.dili)
  const CYPSafe = safetyScore(d.cyp_inhibition)

  const chartData = [
    { subject: '溶解度', A: solNorm, fullMark: 100 },
    { subject: '渗透性', A: permNorm, fullMark: 100 },
    { subject: 'BBB', A: bbbNorm, fullMark: 100 },
    { subject: '口服BA', A: oralNorm, fullMark: 100 },
    { subject: 'hERG', A: hERGSafe, fullMark: 100 },
    { subject: 'Ames', A: AmesSafe, fullMark: 100 },
    { subject: 'DILI', A: DILISafe, fullMark: 100 },
    { subject: 'CYP', A: CYPSafe, fullMark: 100 },
  ]

  // 如果没有任何数据，显示空提示
  const hasAny = chartData.some(item => item.A > 0)
  if (!hasAny) return (
    <div className="w-full h-48 flex items-center justify-center text-xs text-slate-400">
      暂无ADMET数据
    </div>
  )

  return (
    <div className="w-full h-64">
      <ResponsiveContainer width="100%" height="100%">
        <RadarChart cx="50%" cy="50%" outerRadius="70%" data={chartData}>
          <PolarGrid />
          <PolarAngleAxis dataKey="subject" tick={{ fontSize: 11, fill: '#64748b' }} />
          <PolarRadiusAxis angle={30} domain={[0, 100]} tick={{ fontSize: 10, fill: '#94a3b8' }} />
          <Radar name="ADMET" dataKey="A" stroke="#475569" fill="#475569" fillOpacity={0.2} />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  )
}
