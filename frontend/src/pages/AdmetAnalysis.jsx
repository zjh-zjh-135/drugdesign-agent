import React, { useState } from 'react'
import { api } from '../api/client'
import {
  AlertTriangle, CheckCircle2, XCircle, MinusCircle, ChevronDown, ChevronUp,
  Beaker, Brain, FlaskConical, Droplets, Shield,
  RotateCcw
} from 'lucide-react'

// ===================== ADMET 指标元数据 =====================

const ADMET_SCHEMA = [
  {
    key: 'absorption',
    label: '吸收',
    icon: Beaker,
    desc: '药物从给药部位进入血液循环的能力',
    metrics: [
      { key: 'solubility', label: '水溶性', unit: 'logS', type: 'value', range: '>-4', good: '>-2', desc: '在水中溶解的能力，影响口服吸收' },
      { key: 'permeability', label: '肠道渗透性', unit: 'log Caco2', type: 'value', range: '>-7', good: '>-5', desc: '穿过肠上皮细胞膜的能力' },
      { key: 'oral_bioavailability', label: '口服生物利用度', unit: '', type: 'prob_good', desc: '口服后进入体循环的比例' },
      { key: 'hia', label: '人肠道吸收率', unit: '', type: 'prob_good', desc: '人肠道吸收的概率' },
      { key: 'pampa', label: 'PAMPA渗透性', unit: '', type: 'prob_good', desc: '人工膜平行渗透性' },
      { key: 'lipophilicity', label: '亲脂性', unit: 'logP', type: 'logp', range: '1-5', good: '1-4', desc: '脂溶性程度，影响膜通透性' },
      { key: 'hydration_free_energy', label: '水合自由能', unit: 'kcal/mol', type: 'value', desc: '水合过程中的能量变化' },
    ]
  },
  {
    key: 'distribution',
    label: '分布',
    icon: Brain,
    desc: '药物从血液向组织和器官转运的过程',
    metrics: [
      { key: 'bbb', label: '血脑屏障通透性', unit: '', type: 'prob_good', desc: '穿过血脑屏障进入中枢神经系统的概率' },
      { key: 'ppbr', label: '血浆蛋白结合率', unit: '', type: 'prob_good', desc: '与血浆蛋白结合的比例' },
      { key: 'vdss', label: '稳态分布体积', unit: 'L/kg', type: 'value', range: '0.1-5', good: '0.2-3', desc: '药物在体内分布范围的指标' },
    ]
  },
  {
    key: 'metabolism',
    label: '代谢',
    icon: FlaskConical,
    desc: '药物在体内经酶催化发生的化学结构变化',
    metrics: [
      { key: 'cyp1a2', label: 'CYP1A2 抑制', unit: '', type: 'prob_bad', desc: 'CYP1A2 代谢酶抑制概率' },
      { key: 'cyp2c19', label: 'CYP2C19 抑制', unit: '', type: 'prob_bad', desc: 'CYP2C19 代谢酶抑制概率' },
      { key: 'cyp2c9', label: 'CYP2C9 抑制', unit: '', type: 'prob_bad', desc: 'CYP2C9 代谢酶抑制概率' },
      { key: 'cyp2d6', label: 'CYP2D6 抑制', unit: '', type: 'prob_bad', desc: 'CYP2D6 代谢酶抑制概率' },
      { key: 'cyp3a4', label: 'CYP3A4 抑制', unit: '', type: 'prob_bad', desc: 'CYP3A4 代谢酶抑制概率（最重要）' },
      { key: 'cyp_inhibition', label: 'CYP 综合抑制', unit: '', type: 'prob_bad', desc: 'CYP 家族平均抑制概率' },
    ]
  },
  {
    key: 'excretion',
    label: '排泄',
    icon: Droplets,
    desc: '药物及其代谢物从体内排出的过程',
    metrics: [
      { key: 'clearance_hep', label: '肝细胞清除率', unit: 'mL/min/kg', type: 'value', range: '0.5-15', desc: '肝细胞清除药物的速度' },
      { key: 'clearance_mic', label: '肝微粒体清除率', unit: 'mL/min/kg', type: 'value', range: '0.5-15', desc: '肝微粒体清除药物的速度' },
      { key: 'half_life', label: '半衰期', unit: 'h', type: 'value', range: '0.5-48', good: '1-12', desc: '血浆药物浓度下降一半所需时间' },
    ]
  },
  {
    key: 'toxicity',
    label: '毒性',
    icon: Shield,
    desc: '药物对机体产生的不良反应和安全性评估',
    metrics: [
      { key: 'herg', label: 'hERG 抑制', unit: '', type: 'prob_bad', desc: '心脏钾离子通道抑制，QT间期延长风险' },
      { key: 'ames', label: 'Ames 致突变性', unit: '', type: 'prob_bad', desc: '细菌回复突变试验，遗传毒性初筛' },
      { key: 'dili', label: 'DILI 肝损伤', unit: '', type: 'prob_bad', desc: '药物性肝损伤风险' },
      { key: 'clintox', label: '临床毒性', unit: '', type: 'prob_bad', desc: '临床毒性综合预测' },
      { key: 'skin_reaction', label: '皮肤反应', unit: '', type: 'prob_bad', desc: '皮肤过敏反应风险' },
      { key: 'carcinogens', label: '致癌性', unit: '', type: 'prob_bad', desc: '潜在致癌风险评估' },
      { key: 'ld50', label: 'LD50', unit: 'log mol/kg', type: 'value', desc: '半数致死剂量' },
    ]
  },
]

// ===================== 辅助函数 =====================

function parseRange(rangeStr) {
  if (!rangeStr) return null
  const s = rangeStr.trim()
  if (s.startsWith('>')) {
    const val = parseFloat(s.slice(1))
    return { type: 'gt', val }
  }
  if (s.startsWith('<')) {
    const val = parseFloat(s.slice(1))
    return { type: 'lt', val }
  }
  const dash = s.indexOf('-')
  if (dash > 0) {
    const min = parseFloat(s.slice(0, dash))
    const max = parseFloat(s.slice(dash + 1))
    return { type: 'range', min, max }
  }
  const num = parseFloat(s)
  if (!isNaN(num)) return { type: 'gt', val: num }
  return null
}

function checkInRange(v, rangeSpec) {
  const r = parseRange(rangeSpec)
  if (!r) return null
  if (r.type === 'gt') return v > r.val
  if (r.type === 'lt') return v < r.val
  if (r.type === 'range') return v >= r.min && v <= r.max
  return null
}

function getProbStatus(value, type, metric) {
  if (value === null || value === undefined) return { label: '—', color: 'text-slate-400', bg: 'bg-slate-50', border: 'border-slate-200', flag: 'neutral' }
  const v = parseFloat(value)
  if (isNaN(v)) return { label: '—', color: 'text-slate-400', bg: 'bg-slate-50', border: 'border-slate-200', flag: 'neutral' }

  if (type === 'prob_good') {
    if (v >= 0.7) return { label: '良好', color: 'text-emerald-700', bg: 'bg-emerald-50', border: 'border-emerald-200', flag: 'good' }
    if (v >= 0.3) return { label: '中等', color: 'text-amber-700', bg: 'bg-amber-50', border: 'border-amber-200', flag: 'warn' }
    return { label: '较差', color: 'text-rose-700', bg: 'bg-rose-50', border: 'border-rose-200', flag: 'bad' }
  }
  if (type === 'prob_bad') {
    if (v <= 0.3) return { label: '安全', color: 'text-emerald-700', bg: 'bg-emerald-50', border: 'border-emerald-200', flag: 'good' }
    if (v <= 0.7) return { label: '中等', color: 'text-amber-700', bg: 'bg-amber-50', border: 'border-amber-200', flag: 'warn' }
    return { label: '高风险', color: 'text-rose-700', bg: 'bg-rose-50', border: 'border-rose-200', flag: 'bad' }
  }
  if (type === 'solubility') {
    if (v >= -2) return { label: '良好', color: 'text-emerald-700', bg: 'bg-emerald-50', border: 'border-emerald-200', flag: 'good' }
    if (v >= -4) return { label: '中等', color: 'text-amber-700', bg: 'bg-amber-50', border: 'border-amber-200', flag: 'warn' }
    return { label: '较差', color: 'text-rose-700', bg: 'bg-rose-50', border: 'border-rose-200', flag: 'bad' }
  }
  if (type === 'permeability') {
    if (v >= -5) return { label: '良好', color: 'text-emerald-700', bg: 'bg-emerald-50', border: 'border-emerald-200', flag: 'good' }
    if (v >= -7) return { label: '中等', color: 'text-amber-700', bg: 'bg-amber-50', border: 'border-amber-200', flag: 'warn' }
    return { label: '较差', color: 'text-rose-700', bg: 'bg-rose-50', border: 'border-rose-200', flag: 'bad' }
  }
  if (type === 'logp') {
    if (v >= 1 && v <= 4) return { label: '良好', color: 'text-emerald-700', bg: 'bg-emerald-50', border: 'border-emerald-200', flag: 'good' }
    if (v > 4 && v <= 5) return { label: '偏高', color: 'text-amber-700', bg: 'bg-amber-50', border: 'border-amber-200', flag: 'warn' }
    if (v > 5) return { label: '过高', color: 'text-rose-700', bg: 'bg-rose-50', border: 'border-rose-200', flag: 'bad' }
    return { label: '偏低', color: 'text-amber-700', bg: 'bg-amber-50', border: 'border-amber-200', flag: 'warn' }
  }
  if (type === 'value' && metric) {
    const good = metric.good ? checkInRange(v, metric.good) : null
    const inRange = metric.range ? checkInRange(v, metric.range) : null
    if (good === true) return { label: '良好', color: 'text-emerald-700', bg: 'bg-emerald-50', border: 'border-emerald-200', flag: 'good' }
    if (good === false && inRange === true) return { label: '中等', color: 'text-amber-700', bg: 'bg-amber-50', border: 'border-amber-200', flag: 'warn' }
    if (inRange === false) return { label: '需关注', color: 'text-rose-700', bg: 'bg-rose-50', border: 'border-rose-200', flag: 'bad' }
  }
  return { label: '—', color: 'text-slate-400', bg: 'bg-slate-50', border: 'border-slate-200', flag: 'neutral' }
}

function formatValue(value, type) {
  if (value === null || value === undefined) return '—'
  const v = parseFloat(value)
  if (isNaN(v)) return '—'
  if (type === 'prob_good' || type === 'prob_bad') return (v * 100).toFixed(1) + '%'
  if (type === 'solubility' || type === 'permeability' || type === 'logp') return v.toFixed(2)
  return v.toFixed(2)
}

function getOverallRating(score) {
  if (score >= 70) return { label: '优秀', color: 'text-emerald-700', bg: 'bg-emerald-50', border: 'border-emerald-200', bar: 'bg-emerald-600' }
  if (score >= 50) return { label: '良好', color: 'text-slate-700', bg: 'bg-slate-50', border: 'border-slate-200', bar: 'bg-slate-600' }
  if (score >= 30) return { label: '一般', color: 'text-amber-700', bg: 'bg-amber-50', border: 'border-amber-200', bar: 'bg-amber-600' }
  return { label: '较差', color: 'text-rose-700', bg: 'bg-rose-50', border: 'border-rose-200', bar: 'bg-rose-600' }
}

function getCategorySummary(cat, result) {
  const catData = result[cat.key] || {}
  const good = cat.metrics.filter(m => {
    const v = catData[m.key]
    if (v === null || v === undefined) return false
    const s = getProbStatus(v, m.type, m)
    return s.flag === 'good'
  }).length
  const bad = cat.metrics.filter(m => {
    const v = catData[m.key]
    if (v === null || v === undefined) return false
    const s = getProbStatus(v, m.type, m)
    return s.flag === 'bad'
  }).length
  const total = cat.metrics.filter(m => catData[m.key] !== null && catData[m.key] !== undefined).length
  return { good, bad, total, pending: total - good - bad }
}

// ===================== 主组件 =====================

export default function AdmetAnalysis() {
  const [smiles, setSmiles] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [activeTab, setActiveTab] = useState('absorption')
  const [inputCollapsed, setInputCollapsed] = useState(false)

  const handleAnalyze = async () => {
    if (!smiles.trim()) { setError('请输入SMILES'); return }

    setLoading(true)
    setError(null)
    setResult(null)
    setActiveTab('absorption')

    try {
      const res = await api.analyzeAdmet({ smiles: smiles.trim() })
      if (res.data.success) {
        setResult(res.data.data)
        setInputCollapsed(true)
      } else {
        setError(res.data.error || '分析失败')
      }
    } catch (e) {
      setError(e.response?.data?.error || '请求失败')
    } finally {
      setLoading(false)
    }
  }

  const handleReset = () => {
    setResult(null)
    setError(null)
    setSmiles('')
    setActiveTab('absorption')
  }

  return (
    <div className="max-w-5xl mx-auto">
      {/* 初始状态：无结果时显示居中输入 */}
      {!result && (
        <div className="min-h-[55vh] flex flex-col items-center justify-center py-16">
          <div className="text-center mb-10">
            <h1 className="text-3xl font-bold text-slate-800 mb-2">ADMET 成药性分析</h1>
            <p className="text-sm text-slate-400">基于 ADMET-AI 深度学习模型的完整药物性质评估</p>
          </div>

          <div className="w-full max-w-2xl px-4">
            <div className="relative">
              <input
                type="text"
                value={smiles}
                onChange={(e) => setSmiles(e.target.value)}
                placeholder="输入 SMILES 字符串..."
                className="w-full h-12 pl-4 pr-28 bg-white border border-slate-200 rounded-lg text-sm font-mono text-slate-700 placeholder:text-slate-400 focus:outline-none focus:border-slate-400 transition"
                onKeyDown={(e) => e.key === 'Enter' && !loading && handleAnalyze()}
              />
              <button
                onClick={handleAnalyze}
                disabled={loading}
                className="absolute right-1.5 top-1/2 -translate-y-1/2 h-9 px-5 bg-slate-700 text-white text-sm font-medium rounded-md hover:bg-slate-800 disabled:opacity-50 disabled:cursor-not-allowed transition"
              >
                {loading ? '分析中...' : '开始分析'}
              </button>
            </div>

            {error && (
              <div className="mt-3 flex items-center gap-2 text-rose-600 bg-rose-50 px-3 py-2.5 rounded-lg text-sm">
                <AlertTriangle className="w-4 h-4 flex-shrink-0" />
                <span>{error}</span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* 有结果时的标题 + 折叠输入 */}
      {result && (
        <>
          <div className="flex items-center justify-between mb-6">
            <div>
              <h2 className="text-lg font-bold text-slate-800">ADMET 成药性分析</h2>
              <p className="text-xs text-slate-400">基于 ADMET-AI 深度学习模型的完整药物性质评估</p>
            </div>
            <button
              onClick={handleReset}
              className="flex items-center gap-1.5 px-2.5 py-1.5 border border-slate-200 rounded-md text-xs text-slate-500 hover:bg-slate-50 transition"
            >
              <RotateCcw className="w-3 h-3" />
              重新分析
            </button>
          </div>

          {/* 输入区域 */}
          <div className="bg-white rounded-lg border border-slate-200 mb-5 overflow-hidden">
            {/* 折叠标题栏 */}
            {inputCollapsed && (
              <div className="flex items-center justify-between px-4 py-3 cursor-pointer hover:bg-slate-50 transition"
                   onClick={() => setInputCollapsed(false)}>
                <div className="flex items-center gap-2.5">
                  <span className="text-sm text-slate-700 font-medium font-mono">
                    {smiles.substring(0, 60)}{smiles.length > 60 ? '...' : ''}
                  </span>
                  <span className="text-[10px] text-slate-400 bg-slate-100 px-1.5 py-0.5 rounded">已分析</span>
                </div>
                <button
                  onClick={(e) => { e.stopPropagation(); setInputCollapsed(false) }}
                  className="flex items-center gap-1 text-xs text-slate-500 hover:text-slate-700 px-2 py-1 rounded-md hover:bg-slate-100 transition"
                >
                  <span>展开</span>
                  <ChevronDown className="w-3.5 h-3.5" />
                </button>
              </div>
            )}

            {/* 展开输入 */}
            {!inputCollapsed && (
              <div className="p-4">
                <div className="flex items-center gap-3">
                  <input
                    type="text"
                    value={smiles}
                    onChange={(e) => setSmiles(e.target.value)}
                    placeholder="输入 SMILES..."
                    className="flex-1 h-10 px-4 bg-slate-50 border border-slate-200 rounded-lg text-sm font-mono text-slate-700 placeholder:text-slate-400 focus:outline-none focus:border-slate-400 transition"
                    onKeyDown={(e) => e.key === 'Enter' && !loading && handleAnalyze()}
                  />
                  <button
                    onClick={handleAnalyze}
                    disabled={loading}
                    className="h-10 px-5 bg-slate-700 text-white text-sm font-medium rounded-md hover:bg-slate-800 disabled:opacity-50 disabled:cursor-not-allowed transition shrink-0"
                  >
                    {loading ? '分析中...' : '重新分析'}
                  </button>
                  <button
                    onClick={() => setInputCollapsed(true)}
                    className="h-10 px-3 border border-slate-200 rounded-lg text-sm text-slate-500 hover:bg-slate-50 transition shrink-0"
                  >
                    收起
                  </button>
                </div>
                {error && (
                  <div className="mt-3 flex items-center gap-2 text-rose-600 bg-rose-50 px-3 py-2.5 rounded-lg text-sm">
                    <AlertTriangle className="w-4 h-4 flex-shrink-0" />
                    <span>{error}</span>
                  </div>
                )}
              </div>
            )}
          </div>
        </>
      )}

      {/* 加载中 */}
      {loading && (
        <div className="bg-white rounded-lg border border-slate-200 p-12 text-center">
          <style>{`
            .admet-loader {
              width: 48px;
              height: 48px;
              margin: 0 auto 20px;
              position: relative;
            }
            .admet-loader:before {
              content: '';
              width: 48px;
              height: 5px;
              background: #f0808050;
              position: absolute;
              top: 60px;
              left: 0;
              border-radius: 50%;
              animation: admet-shadow324 0.5s linear infinite;
            }
            .admet-loader:after {
              content: '';
              width: 100%;
              height: 100%;
              background: #f08080;
              position: absolute;
              top: 0;
              left: 0;
              border-radius: 4px;
              animation: admet-jump7456 0.5s linear infinite;
            }
            @keyframes admet-jump7456 {
              15% { border-bottom-right-radius: 3px; }
              25% { transform: translateY(9px) rotate(22.5deg); }
              50% { transform: translateY(18px) scale(1, .9) rotate(45deg); border-bottom-right-radius: 40px; }
              75% { transform: translateY(9px) rotate(67.5deg); }
              100% { transform: translateY(0) rotate(90deg); }
            }
            @keyframes admet-shadow324 {
              0%, 100% { transform: scale(1, 1); }
              50% { transform: scale(1.2, 1); }
            }
          `}</style>
          <div className="admet-loader" />
          <p className="text-sm text-slate-500">ADMET 分析中...</p>
          <p className="text-xs text-slate-400 mt-1">模型正在计算分子的完整药物性质</p>
        </div>
      )}

      {/* 分析结果 */}
      {result && !loading && (
        <div className="space-y-4">

          {/* 综合评分 */}
          <div className="bg-white rounded-lg border border-slate-200 p-4">
            <div className="flex items-center gap-4">
              <div>
                <div className="flex items-baseline gap-2">
                  <span className={`text-3xl font-bold tracking-tight ${getOverallRating(result.overall_score).color}`}>
                    {result.overall_score?.toFixed(1) ?? '—'}
                  </span>
                  <span className="text-sm text-slate-400 font-medium">/ 100</span>
                </div>
                <div className="flex items-center gap-2 mt-0.5">
                    <span className={`text-xs font-semibold px-2 py-0.5 rounded-md ${getOverallRating(result.overall_score).bg} ${getOverallRating(result.overall_score).color} border ${getOverallRating(result.overall_score).border}`}>
                      {getOverallRating(result.overall_score).label}
                    </span>
                    <span className="text-[10px] text-slate-400">ADMET 加权评估</span>
                  </div>
                </div>
              <div className="flex-1 min-w-0">
                <div className="w-full h-2 bg-slate-100 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-700 ${getOverallRating(result.overall_score).bar}`}
                    style={{ width: `${Math.min(100, Math.max(0, result.overall_score || 0))}%` }}
                  />
                </div>
                <div className="flex justify-between mt-1">
                  <span className="text-[10px] text-slate-400">0</span>
                  <span className="text-[10px] text-slate-400">25</span>
                  <span className="text-[10px] text-slate-400">50</span>
                  <span className="text-[10px] text-slate-400">75</span>
                  <span className="text-[10px] text-slate-400">100</span>
                </div>
              </div>
            </div>
          </div>

          {/* 选项卡导航 */}
          <div className="bg-white rounded-lg border border-slate-200 p-3">
            <div className="flex items-center gap-1 overflow-x-auto pb-0.5">
              {ADMET_SCHEMA.map(cat => {
                const CatIcon = cat.icon
                const summary = getCategorySummary(cat, result)
                const isActive = activeTab === cat.key
                return (
                  <button
                    key={cat.key}
                    onClick={() => setActiveTab(cat.key)}
                    className={`flex items-center gap-1.5 px-3.5 py-2 rounded-full text-xs font-medium whitespace-nowrap transition-all duration-200 ${
                      isActive
                        ? 'bg-slate-800 text-white shadow-sm'
                        : 'bg-white text-slate-600 border border-slate-200 hover:border-slate-300 hover:bg-slate-50'
                    }`}
                  >
                    <CatIcon className={`w-3.5 h-3.5 ${isActive ? 'text-white' : 'text-slate-400'}`} />
                    <span>{cat.label}</span>
                    <span className={`text-[10px] ${isActive ? 'text-slate-300' : 'text-slate-400'}`}>({cat.metrics.length})</span>
                    {summary.bad > 0 && (
                      <span className="w-4 h-4 rounded-full bg-rose-500 text-white flex items-center justify-center text-[8px] font-bold ml-0.5">
                        {summary.bad}
                      </span>
                    )}
                  </button>
                )
              })}
            </div>
          </div>

          {/* 当前分类详情 */}
          {ADMET_SCHEMA.filter(cat => cat.key === activeTab).map(cat => {
            const catData = result[cat.key] || {}
            const summary = getCategorySummary(cat, result)
            const CatIcon = cat.icon

            return (
              <div key={cat.key} className="bg-white rounded-lg border border-slate-200 overflow-hidden">
                {/* 分类标题 */}
                <div className="flex items-center gap-3 px-5 py-4 border-b border-slate-100">
                  <div className="w-9 h-9 rounded-lg bg-slate-100 flex items-center justify-center">
                    <CatIcon className="w-[18px] h-[18px] text-slate-600" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-bold text-slate-800">{cat.label}</span>
                      {summary.bad > 0 && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-rose-50 text-rose-700 font-medium border border-rose-200">
                          {summary.bad} 项需关注
                        </span>
                      )}
                      {summary.bad === 0 && summary.total > 0 && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-emerald-50 text-emerald-700 font-medium border border-emerald-200">
                          全部良好
                        </span>
                      )}
                    </div>
                    <p className="text-[11px] text-slate-400 mt-0.5">{cat.desc}</p>
                  </div>
                  <span className="text-[10px] font-medium px-2.5 py-1 rounded-md bg-slate-50 text-slate-500 border border-slate-100">
                    {cat.metrics.length} 个指标
                  </span>
                </div>

                {/* 指标表格 */}
                <div className="px-5 py-4">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-slate-200">
                        <th className="text-left py-2 pr-4 text-xs font-semibold text-slate-500 w-2/5">指标</th>
                        <th className="text-left py-2 pr-4 text-xs font-semibold text-slate-500 w-1/5">数值</th>
                        <th className="text-left py-2 pr-4 text-xs font-semibold text-slate-500 w-1/5">评价</th>
                        <th className="text-left py-2 text-xs font-semibold text-slate-500 w-1/5">参考范围</th>
                      </tr>
                    </thead>
                    <tbody>
                      {cat.metrics.map(metric => {
                        const value = catData[metric.key]
                        const status = getProbStatus(value, metric.type, metric)
                        const formatted = formatValue(value, metric.type)
                        return (
                          <tr key={metric.key} className="border-b border-slate-50 last:border-b-0">
                            <td className="py-3 pr-4">
                              <div>
                                <div className="font-medium text-slate-700">{metric.label}</div>
                                <div className="text-[11px] text-slate-400 mt-0.5">{metric.desc}</div>
                              </div>
                            </td>
                            <td className="py-3 pr-4">
                              <span className="font-mono font-semibold text-slate-800">
                                {formatted}
                              </span>
                              {metric.unit && (
                                <span className="text-[10px] text-slate-400 ml-1">{metric.unit}</span>
                              )}
                            </td>
                            <td className="py-3 pr-4">
                              <span className={`text-xs font-medium ${status.color}`}>
                                {status.label}
                              </span>
                            </td>
                            <td className="py-3">
                              <span className="text-xs text-slate-400 font-mono">
                                {metric.range || '—'}
                              </span>
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>

                {/* 分类总结 */}
                <div className="px-5 py-3 border-t border-slate-100 bg-slate-50/40">
                  <div className="flex items-center gap-4 text-xs">
                    <span className="text-slate-500">总计 {summary.total} 项</span>
                    <span className="flex items-center gap-1 text-emerald-700">
                      <CheckCircle2 className="w-3 h-3" /> {summary.good} 良好
                    </span>
                    {summary.pending > 0 && (
                      <span className="flex items-center gap-1 text-amber-700">
                        <MinusCircle className="w-3 h-3" /> {summary.pending} 中等
                      </span>
                    )}
                    {summary.bad > 0 && (
                      <span className="flex items-center gap-1 text-rose-700">
                        <XCircle className="w-3 h-3" /> {summary.bad} 需关注
                      </span>
                    )}
                  </div>
                </div>
              </div>
            )
          })}

          {/* 数据来源 */}
          <div className="text-center text-[10px] text-slate-400 py-1">
            数据来源: {result.source === 'admet_ai' ? 'ADMET-AI 深度学习模型' : 'RDKit 描述符规则估算'}
          </div>
        </div>
      )}
    </div>
  )
}
