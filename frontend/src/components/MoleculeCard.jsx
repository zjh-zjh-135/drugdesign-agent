import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import MoleculeSVG from './MoleculeSVG'
import Molecule3DViewer from './Molecule3DViewer'
import StatusBadge from './StatusBadge'
import { Box, Activity } from 'lucide-react'

export default function MoleculeCard({ molecule }) {
  const navigate = useNavigate()
  const [show3D, setShow3D] = useState(false)
  const props = molecule.properties || {}

  // 计算属性值的颜色
  const getPropColor = (value, type) => {
    if (value === undefined || value === null) return 'text-gray-400'
    switch (type) {
      case 'mw':
        return value < 500 ? 'text-emerald-700' : 'text-slate-600'
      case 'clogp':
        return value < 5 ? 'text-emerald-700' : 'text-slate-600'
      case 'qed':
        return value > 0.5 ? 'text-emerald-700' : 'text-slate-600'
      default:
        return 'text-slate-700'
    }
  }

  // ADMET 分数颜色
  const admetScore = molecule.admet?.overall_score
  const admetColor = admetScore >= 70 ? 'text-emerald-700' : 'text-slate-600'
  const admetBg = 'bg-slate-50'
  const admetBar = admetScore >= 70 ? 'bg-emerald-600' : 'bg-slate-400'

  // 截断 SMILES
  const displaySmiles = molecule.smiles?.length > 35 
    ? molecule.smiles.slice(0, 32) + '...' 
    : molecule.smiles

  return (
    <>
      <div
        className="bg-white rounded-lg border border-slate-100 hover:border-slate-300 transition-colors duration-150 cursor-pointer group overflow-hidden"
        onClick={() => navigate(`/molecules/${molecule.id}`)}
      >
        {/* 顶部：结构图区域 */}
        <div className="relative bg-slate-50/60 p-3 flex justify-center items-center min-h-[120px]">
          <MoleculeSVG moleculeId={molecule.id} smiles={molecule.smiles} size={140} />
          
          {/* 3D 浮动按钮 */}
          <button
            onClick={(e) => { e.stopPropagation(); setShow3D(true) }}
            className="absolute top-2 right-2 w-7 h-7 bg-white rounded-lg shadow-sm border border-slate-200 flex items-center justify-center hover:bg-slate-50 hover:border-slate-300 transition-all opacity-0 group-hover:opacity-100"
            title="查看3D结构"
          >
            <Box className="w-3.5 h-3.5 text-slate-500 hover:text-blue-500" />
          </button>

          {/* ID 标签 */}
          <div className="absolute top-2 left-2">
            <span className="text-[10px] font-medium text-slate-400 bg-white/80 px-1.5 py-0.5 rounded">
              #{molecule.id}
            </span>
          </div>
        </div>

        {/* 内容区域 */}
        <div className="p-3">
          {/* SMILES */}
          <div className="text-[10px] text-slate-400 font-mono truncate mb-2" title={molecule.smiles}>
            {displaySmiles}
          </div>

          {/* 属性网格 - 紧凑优雅 */}
          <div className="grid grid-cols-4 gap-1.5 mb-2">
            <div className="text-center">
              <div className="text-[10px] text-slate-400 mb-0.5">MW</div>
              <div className={`text-xs font-semibold ${getPropColor(props.mw, 'mw')}`}>
                {props.mw ? Math.round(props.mw) : '-'}
              </div>
            </div>
            <div className="text-center">
              <div className="text-[10px] text-slate-400 mb-0.5">LogP</div>
              <div className={`text-xs font-semibold ${getPropColor(props.clogp, 'clogp')}`}>
                {props.clogp !== undefined ? props.clogp.toFixed(1) : '-'}
              </div>
            </div>
            <div className="text-center">
              <div className="text-[10px] text-slate-400 mb-0.5">TPSA</div>
              <div className="text-xs font-semibold text-slate-700">
                {props.tpsa ? Math.round(props.tpsa) : '-'}
              </div>
            </div>
            <div className="text-center">
              <div className="text-[10px] text-slate-400 mb-0.5">QED</div>
              <div className={`text-xs font-semibold ${getPropColor(props.qed, 'qed')}`}>
                {props.qed !== undefined ? props.qed.toFixed(2) : '-'}
              </div>
            </div>
          </div>

          {/* ADMET 分数条 */}
          {admetScore !== undefined && (
            <div className={`${admetBg} rounded-lg px-2.5 py-1.5`}>
              <div className="flex items-center justify-between mb-1">
                <span className="text-[10px] text-slate-500 font-medium">ADMET</span>
                <span className={`text-xs font-bold ${admetColor}`}>
                  {admetScore.toFixed(0)}
                </span>
              </div>
              <div className="w-full h-1.5 bg-slate-200 rounded-full overflow-hidden">
                <div 
                  className={`h-full ${admetBar} rounded-full transition-all duration-500`}
                  style={{ width: `${Math.min(admetScore, 100)}%` }}
                />
              </div>
            </div>
          )}

          {/* 状态 */}
          <div className="mt-2 flex justify-center">
            <StatusBadge status={molecule.status} />
          </div>
        </div>
      </div>
      
      {show3D && (
        <Molecule3DViewer
          moleculeId={molecule.id}
          smiles={molecule.smiles}
          title={`分子 #${molecule.id} - 3D结构`}
          onClose={() => setShow3D(false)}
        />
      )}
    </>
  )
}
