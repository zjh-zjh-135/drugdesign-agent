import React, { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import MoleculeSVG from '../components/MoleculeSVG'
import AdmetRadar from '../components/AdmetRadar'
import LoadingSpinner from '../components/LoadingSpinner'
import StatusBadge from '../components/StatusBadge'
import { ArrowLeft } from 'lucide-react'

// 将5分类ADMET数据扁平化，兼容旧显示
function flattenAdmet(data) {
  if (!data) return {}
  if (data.absorption || data.distribution || data.metabolism || data.toxicity) {
    // 新5分类结构
    const abs = data.absorption || {}
    const dist = data.distribution || {}
    const met = data.metabolism || {}
    const tox = data.toxicity || {}
    return {
      solubility: abs.solubility,
      permeability: abs.permeability,
      oral_bioavailability: abs.oral_bioavailability,
      bbb: dist.bbb,
      herg: tox.herg,
      ames: tox.ames,
      dili: tox.dili,
      cyp_inhibition: met.cyp_inhibition,
      overall_score: data.overall_score,
      source: data.source,
    }
  }
  // 旧扁平结构
  return data
}

export default function MoleculeDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [molecule, setMolecule] = useState(null)
  const [loading, setLoading] = useState(true)
  const [renderError, setRenderError] = useState(null)
  const [admetAnalyzing, setAdmetAnalyzing] = useState(false)

  useEffect(() => {
    loadMolecule()
  }, [id])

  const loadMolecule = async () => {
    try {
      const res = await api.getMolecule(id)
      const mol = res.data.data

      // 如果 ADMET 数据不完整，自动分析获取完整5分类数据
      if (mol.smiles && (!mol.admet || mol.admet.solubility === null || mol.admet.solubility === undefined)) {
        setAdmetAnalyzing(true)
        try {
          const admetRes = await api.analyzeAdmet({ smiles: mol.smiles })
          if (admetRes.data.success) {
            mol.admet = admetRes.data.data
          }
        } catch (e) {
          console.error('ADMET分析失败:', e)
        } finally {
          setAdmetAnalyzing(false)
        }
      }

      setMolecule(mol)
    } catch (e) {
      console.error(e)
      setRenderError(e.message || '加载分子失败')
    } finally {
      setLoading(false)
    }
  }

  if (loading) return <div className="flex justify-center pt-32 pb-20"><LoadingSpinner size="lg" /></div>
  if (renderError) return <div className="text-center py-20 text-slate-400">{renderError}</div>
  if (!molecule) return <div className="text-center py-20 text-slate-400">分子不存在</div>

  const props = molecule.properties || {}
  const rawAdmet = molecule.admet || {}
  const admet = flattenAdmet(rawAdmet)

  // 安全获取数值
  const safeNumber = (val) => {
    if (val === null || val === undefined || Number.isNaN(val)) return null
    const n = Number(val)
    return Number.isFinite(n) ? n : null
  }
  const fmt = (val, digits = 1) => {
    const n = safeNumber(val)
    return n !== null ? n.toFixed(digits) : '-'
  }
  const fmtInt = (val) => {
    const n = safeNumber(val)
    return n !== null ? String(Math.round(n)) : '-'
  }
  const fmtPct = (val) => {
    const n = safeNumber(val)
    return n !== null ? `${n.toFixed(1)}%` : '-'
  }

  const overallScore = safeNumber(admet.overall_score)

  return (
    <div className="space-y-6">
      <button
        onClick={() => navigate('/molecules')}
        className="flex items-center gap-2 text-sm text-slate-500 hover:text-slate-800 transition-colors"
      >
        <ArrowLeft className="w-4 h-4" /> 返回分子列表
      </button>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-stretch">
        {/* 左侧：分子结构 */}
        <div className="lg:col-span-1">
          <div className="bg-white rounded-lg border border-slate-200 p-5 h-full flex flex-col hover:border-slate-300 transition-colors">
            <div className="flex items-center gap-2 mb-4">
              <h3 className="text-sm font-bold text-slate-800">分子结构</h3>
              <div className="ml-auto">
                <StatusBadge status={molecule.status} />
              </div>
            </div>
            <div className="flex-1 flex flex-col">
              <div className="flex-1 flex items-center justify-center py-2">
                <MoleculeSVG moleculeId={molecule.id} smiles={molecule.smiles} size={260} className="w-full max-w-[260px]" />
              </div>
              <div className="font-mono text-[10px] text-slate-400 break-all text-center bg-slate-50 rounded-lg px-3 py-2.5 mt-2">
                {molecule.smiles}
              </div>
            </div>
          </div>
        </div>

        {/* 中间：性质 */}
        <div className="lg:col-span-1">
          <div className="bg-white rounded-lg border border-slate-200 p-5 h-full flex flex-col hover:border-slate-300 transition-colors">
            <div className="flex items-center gap-2 mb-4">
              <h3 className="text-sm font-bold text-slate-800">分子性质</h3>
            </div>
            <div className="flex-1 flex flex-col justify-between">
              {[
                { label: '分子量 (MW)', value: fmt(props.mw, 1), unit: 'Da' },
                { label: 'LogP', value: fmt(props.clogp, 2) },
                { label: 'TPSA', value: fmt(props.tpsa, 1), unit: 'Å²' },
                { label: 'HBD (氢键供体)', value: fmtInt(props.hbd) },
                { label: 'HBA (氢键受体)', value: fmtInt(props.hba) },
                { label: 'RotB (可旋转键)', value: fmtInt(props.rotb) },
                { label: 'SA Score (合成可及性)', value: fmt(props.sa_score, 2) },
                { label: 'QED (药物相似性)', value: fmt(props.qed, 3) },
                { label: '相似性', value: fmt(props.similarity_score, 3) },
              ].map((item) => (
                <div key={item.label} className="flex justify-between items-center py-2 border-b border-slate-100 last:border-0">
                  <span className="text-xs text-slate-500">{item.label}</span>
                  <span className="text-xs font-semibold text-slate-800">
                    {item.value}
                    {item.unit && <span className="text-slate-400 ml-1">{item.unit}</span>}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* 右侧：ADMET */}
        <div className="lg:col-span-1">
          <div className="bg-white rounded-lg border border-slate-200 p-5 h-full flex flex-col hover:border-slate-300 transition-colors">
            <div className="flex items-center gap-2 mb-4">
              <h3 className="text-sm font-bold text-slate-800">ADMET 预测</h3>
              {admetAnalyzing && (
                <span className="text-[10px] text-slate-400 ml-auto">分析中...</span>
              )}
            </div>
            <div className="flex-1 flex flex-col">
              {/* 雷达图 */}
              <div className="mb-4">
                <AdmetRadar data={rawAdmet} />
              </div>
              {/* 综合评分 */}
              {overallScore !== null && (
                <div className="mb-3">
                  <div className="flex justify-between text-xs mb-1.5">
                    <span className="text-slate-400">综合评分</span>
                    <span className={`font-bold ${overallScore >= 70 ? 'text-emerald-700' : overallScore >= 50 ? 'text-amber-700' : 'text-slate-600'}`}>
                      {overallScore.toFixed(1)}
                    </span>
                  </div>
                  <div className="w-full h-1.5 bg-slate-100 rounded-full overflow-hidden">
                    <div 
                      className={`h-full rounded-full ${overallScore >= 70 ? 'bg-emerald-600' : overallScore >= 50 ? 'bg-amber-600' : 'bg-slate-400'}`}
                      style={{ width: `${Math.min(overallScore, 100)}%` }}
                    />
                  </div>
                </div>
              )}
              {/* 其他属性 */}
              <div className="space-y-0 flex-1">
                {[
                  { label: '溶解度', value: fmt(admet.solubility, 2), unit: 'logS' },
                  { label: '渗透性', value: fmt(admet.permeability, 2), unit: 'logCaco2' },
                  { label: '口服生物利用度', value: fmtPct(admet.oral_bioavailability) },
                  { label: 'BBB 通透性', value: fmtPct(admet.bbb) },
                  { label: 'hERG 抑制', value: fmtPct(admet.herg) },
                  { label: 'Ames 致突变', value: fmtPct(admet.ames) },
                ].map((item) => (
                  <div key={item.label} className="flex justify-between items-center py-2 border-b border-slate-100 last:border-0">
                    <span className="text-xs text-slate-500">{item.label}</span>
                    <span className="text-xs font-semibold text-slate-800">
                      {item.value}
                      {item.unit && <span className="text-slate-400 ml-1">{item.unit}</span>}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
