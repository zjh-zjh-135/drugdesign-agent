import React, { useState, useRef } from 'react'
import { api } from '../api/client'
import {
  FlaskConical, Search, ArrowRight, Thermometer,
  Clock, AlertCircle, Loader2, Info, RotateCcw,
} from 'lucide-react'

export default function SynthesisView() {
  const [smiles, setSmiles] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const scrollRef = useRef(null)

  const EXAMPLE_SMILES = [
    { label: '阿司匹林', smiles: 'CC(=O)Oc1ccccc1C(=O)O' },
    { label: '对乙酰氨基酚', smiles: 'CC(=O)Nc1ccc(O)cc1' },
    { label: '布洛芬', smiles: 'CC(C)Cc1ccc(C(C)C(=O)O)cc1' },
  ]

  const handleAnalyze = async () => {
    if (!smiles.trim()) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const res = await api.analyzeSynthesisFromSmiles({ smiles: smiles.trim() })
      if (res.data.success) {
        setResult(res.data.data)
        setTimeout(() => {
          scrollRef.current?.scrollIntoView({ behavior: 'smooth' })
        }, 200)
      } else {
        setError(res.data.error || '分析失败')
      }
    } catch (e) {
      setError(e.response?.data?.error || '网络错误，请重试')
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleAnalyze()
    }
  }

  const loadExample = (s) => {
    setSmiles(s)
    setError(null)
  }

  return (
    <div className="max-w-7xl mx-auto">
      {/* 页面标题 */}
      <div className="mb-6">
        <h2 className="text-xl font-bold text-slate-800 mb-1.5 flex items-center gap-2">
          <FlaskConical className="w-5 h-5 text-slate-600" />
          合成路线分析
        </h2>
        <p className="text-sm text-slate-400">
          输入分子 SMILES，AI 自动进行逆合成分析并展示推荐合成路线
        </p>
      </div>

      {/* 输入区 */}
      <div className="bg-white rounded-xl border border-slate-200 p-5 mb-6">
        <div className="relative">
          <div className="flex items-center gap-3 border border-slate-200 rounded-xl px-4 py-3 bg-white focus-within:border-slate-400 transition">
            <Search className="w-5 h-5 text-slate-400 shrink-0" />
            <input
              type="text"
              value={smiles}
              onChange={(e) => setSmiles(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="输入分子 SMILES，例如：CC(=O)Oc1ccccc1C(=O)O"
              className="flex-1 bg-transparent outline-none text-sm text-slate-700 placeholder:text-slate-300"
            />
            {smiles && (
              <button
                onClick={() => { setSmiles(''); setResult(null); setError(null) }}
                className="text-slate-400 hover:text-slate-600 transition"
              >
                <RotateCcw className="w-4 h-4" />
              </button>
            )}
          </div>
        </div>

        {/* 示例按钮 */}
        <div className="flex items-center gap-2 mt-3">
          <span className="text-xs text-slate-400">示例：</span>
          {EXAMPLE_SMILES.map((ex) => (
            <button
              key={ex.label}
              onClick={() => loadExample(ex.smiles)}
              className="text-xs px-2.5 py-1 bg-slate-50 text-slate-600 rounded-lg border border-slate-200 hover:bg-slate-100 hover:border-slate-300 transition"
            >
              {ex.label}
            </button>
          ))}
        </div>

        {/* 分析按钮 */}
        <div className="mt-4">
          <button
            onClick={handleAnalyze}
            disabled={!smiles.trim() || loading}
            className={`flex items-center gap-2 px-6 py-2.5 rounded-lg text-sm font-medium transition ${
              smiles.trim() && !loading
                ? 'bg-slate-700 text-white hover:bg-slate-800'
                : 'bg-slate-200 text-slate-400 cursor-not-allowed'
            }`}
          >
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                分析中...
              </>
            ) : (
              <>
                <FlaskConical className="w-4 h-4" />
                分析合成路线
              </>
            )}
          </button>
        </div>
      </div>

      {/* 错误提示 */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 mb-6 flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-red-500 shrink-0 mt-0.5" />
          <div>
            <div className="text-sm font-medium text-red-700">分析失败</div>
            <div className="text-sm text-red-600 mt-1">{error}</div>
          </div>
        </div>
      )}

      {/* 结果区 */}
      {result && (
        <div ref={scrollRef} className="space-y-5">
          {/* 概览卡片 */}
          <SynthesisOverview result={result} />

          {/* 合成路线图 */}
          <SynthesisRouteMap result={result} />

          {/* 免责声明 */}
          <div className="bg-white border border-slate-200 rounded-xl p-4 flex items-start gap-3">
            <Info className="w-4 h-4 text-slate-400 shrink-0 mt-0.5" />
            <div className="text-xs text-slate-500 leading-relaxed">
              <span className="font-medium text-slate-600">说明：</span>
              以上合成路线由 AI 基于分子结构和反应模板模拟生成，仅供参考。
              实际合成可行性需结合具体实验条件验证。
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

/* ── 概览卡片 ── */
function SynthesisOverview({ result }) {
  const analysis = result.analysis || {}

  const cards = [
    {
      label: '合成步数',
      value: `${result.num_steps} 步`,
      sub: analysis.num_rings !== undefined ? `${analysis.num_rings} 环 · ${analysis.num_rotatable || 0} 旋转键` : '多步反应路线',
      color: 'slate',
    },
    {
      label: '总收率',
      value: `${(result.total_yield * 100).toFixed(1)}%`,
      sub: result.num_steps > 0 ? `平均每步 ${((result.total_yield ** (1 / result.num_steps)) * 100).toFixed(0)}%` : '单步收率',
      color: 'emerald',
    },
    {
      label: '合成可及性',
      value: result.availability_score.toFixed(2),
      sub: result.availability_score >= 0.7 ? '较易合成' : result.availability_score >= 0.4 ? '中等难度' : '较难合成',
      color: result.availability_score >= 0.7 ? 'emerald' : result.availability_score >= 0.4 ? 'amber' : 'rose',
    },
    {
      label: '估算成本',
      value: `¥${result.estimated_cost.toFixed(0)}`,
      sub: `MW ${analysis.mw ? analysis.mw.toFixed(0) : '—'}`,
      color: 'slate',
    },
  ]

  const colorMap = {
    slate: { text: 'text-slate-700' },
    emerald: { text: 'text-emerald-600' },
    amber: { text: 'text-amber-500' },
    rose: { text: 'text-rose-500' },
  }

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
      {cards.map((card, i) => {
        const c = colorMap[card.color]
        return (
          <div key={i} className="bg-white border border-slate-200 rounded-lg p-3">
            <div className="text-xs text-slate-400 font-medium mb-1">{card.label}</div>
            <div className={`text-lg font-bold ${c.text} mb-0.5`}>{card.value}</div>
            {card.sub && <div className="text-[11px] text-slate-400">{card.sub}</div>}
          </div>
        )
      })}
    </div>
  )
}

/* ── 合成路线图（横向流程） ── */
function SynthesisRouteMap({ result }) {
  const { structures, steps } = result
  const target = structures?.target
  const intermediates = structures?.intermediates || []
  const startMaterials = structures?.start_materials || []

  const molecules = [
    ...(startMaterials.length > 0
      ? [{ ...startMaterials[0], kind: 'start', label: '起始原料' }]
      : []),
    ...intermediates.map((inter, i) => ({
      ...inter,
      kind: 'intermediate',
      label: `中间体 ${i + 1}`,
    })),
    ...(target ? [{ ...target, kind: 'target', label: '目标分子' }] : []),
  ]

  const numReactions = Math.min(molecules.length - 1, steps.length)

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5">
      <h3 className="text-base font-bold text-slate-800 mb-5">
        合成路线图
      </h3>

      <div className="overflow-x-auto">
        <div className="flex items-center gap-0 min-w-max px-2 py-2">
          {molecules.map((mol, idx) => (
            <React.Fragment key={`node-${idx}`}>
              <MoleculeNode
                data={mol}
                kind={mol.kind}
                label={mol.label}
              />
              {idx < numReactions && (
                <ReactionArrow step={steps[idx]} />
              )}
            </React.Fragment>
          ))}
        </div>
      </div>
    </div>
  )
}

/* 分子节点卡片 */
function MoleculeNode({ data, kind, label }) {
  const borderColor =
    kind === 'target' ? 'border-slate-700' :
    'border-slate-300'

  const bgColor =
    kind === 'target' ? 'bg-slate-50' :
    'bg-white'

  const labelColor =
    kind === 'target' ? 'bg-slate-700 text-white' :
    'bg-slate-100 text-slate-600'

  return (
    <div className="flex flex-col items-center shrink-0">
      <div className={`rounded-xl border-2 ${borderColor} ${bgColor} p-3 w-[300px]`}>
        {/* 标签 */}
        <div className="flex justify-center mb-2">
          <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${labelColor}`}>
            {label}
          </span>
        </div>

        {/* 2D 结构图 */}
        <div className="bg-white rounded-lg border border-slate-100 overflow-hidden h-[200px] flex items-center justify-center">
          {data?.svg ? (
            // P1修复: 使用img+base64替代dangerouslySetInnerHTML，防止XSS
            <img
              src={`data:image/svg+xml;base64,${btoa(unescape(encodeURIComponent(data.svg)))}`}
              alt="2D Structure"
              className="w-full h-full object-contain"
            />
          ) : (
            <span className="text-xs text-slate-300 font-mono px-2 text-center break-all">
              {data?.smiles || 'N/A'}
            </span>
          )}
        </div>

        {/* SMILES 文本 */}
        <div className="mt-2 text-[10px] text-slate-400 font-mono text-center truncate px-1">
          {data?.smiles || ''}
        </div>
      </div>
    </div>
  )
}

/* 反应箭头 — 整合所有步骤信息 */
function ReactionArrow({ step }) {
  const reagents = Array.isArray(step?.reagents) ? step.reagents : []
  const reagentStr = reagents.slice(0, 2).join(', ')
  const moreCount = reagents.length > 2 ? `+${reagents.length - 2}` : ''

  return (
    <div className="flex flex-col items-center justify-center shrink-0 px-2 py-4 w-[180px]">
      {/* 反应名称 — 最突出 */}
      <div className="bg-slate-700 text-white rounded-lg px-3 py-1.5 mb-2 w-full text-center">
        <div className="text-xs font-bold leading-tight">
          {step?.reaction_name}
        </div>
      </div>

      {/* 试剂 + 溶剂 */}
      <div className="bg-white border border-slate-200 rounded-lg px-2.5 py-2 mb-2 w-full">
        <div className="text-[10px] font-semibold text-slate-700 text-center leading-tight">
          {reagentStr}
          {moreCount && <span className="text-slate-400"> {moreCount}</span>}
        </div>
        <div className="text-[9px] text-slate-400 text-center mt-0.5 leading-tight">
          {step?.solvent}
        </div>
      </div>

      {/* 箭头 */}
      <div className="flex items-center gap-0.5 mb-2">
        <div className="w-8 h-[2px] bg-slate-400" />
        <ArrowRight className="w-4 h-4 text-slate-400" />
      </div>

      {/* 条件 + 收率 */}
      <div className="space-y-1.5 text-center w-full">
        <div className="flex items-center justify-center gap-2">
          <span className="text-[10px] text-slate-500 flex items-center gap-0.5">
            <Thermometer className="w-3 h-3" />
            {step?.temperature}
          </span>
          <span className="text-slate-300">·</span>
          <span className="text-[10px] text-slate-500 flex items-center gap-0.5">
            <Clock className="w-3 h-3" />
            {step?.time}
          </span>
        </div>
        <span className="text-[11px] px-2 py-0.5 bg-emerald-50 text-emerald-600 rounded-full font-medium border border-emerald-100 inline-block">
          {(step?.yield * 100).toFixed(0)}% 收率
        </span>
      </div>
    </div>
  )
}
