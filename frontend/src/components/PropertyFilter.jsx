import React from 'react'
import { useApp } from '../store/AppContext'

export default function PropertyFilter({ onApply }) {
  const { state, dispatch } = useApp()
  const params = state.filterParams

  const handleChange = (key, value) => {
    dispatch({ type: 'SET_FILTER_PARAMS', payload: { [key]: parseFloat(value) } })
  }

  const sliders = [
    { key: 'mw_min', label: 'MW最小值', min: 100, max: 500, step: 10 },
    { key: 'mw_max', label: 'MW最大值', min: 300, max: 1000, step: 10 },
    { key: 'clogp_min', label: 'LogP最小值', min: -2, max: 3, step: 0.5 },
    { key: 'clogp_max', label: 'LogP最大值', min: 2, max: 8, step: 0.5 },
    { key: 'tpsa_min', label: 'TPSA最小值', min: 0, max: 100, step: 5 },
    { key: 'tpsa_max', label: 'TPSA最大值', min: 50, max: 200, step: 5 },
    { key: 'hbd_max', label: 'HBD最大值', min: 0, max: 10, step: 1 },
    { key: 'hba_max', label: 'HBA最大值', min: 0, max: 15, step: 1 },
    { key: 'rotb_max', label: 'RotB最大值', min: 0, max: 15, step: 1 },
    { key: 'sa_score_max', label: 'SA Score最大值', min: 1, max: 10, step: 0.5 },
  ]

  return (
    <div className="bg-white p-4 rounded-lg shadow-sm border border-gray-200">
      <h3 className="text-sm font-semibold text-gray-700 mb-3">过滤参数</h3>
      <div className="space-y-3">
        {sliders.map((s) => (
          <div key={s.key}>
            <div className="flex justify-between text-xs mb-1">
              <span className="text-gray-600">{s.label}</span>
              <span className="font-medium text-slate-700">{params[s.key]}</span>
            </div>
            <input
              type="range"
              min={s.min}
              max={s.max}
              step={s.step}
              value={params[s.key] || 0}
              onChange={(e) => handleChange(s.key, e.target.value)}
              className="w-full h-1.5 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-slate-700"
            />
          </div>
        ))}
      </div>
      <button
        onClick={() => onApply && onApply(params)}
        className="w-full mt-4 bg-slate-700 text-white text-sm py-2 rounded-lg hover:bg-slate-800 transition-colors"
      >
        应用过滤
      </button>
    </div>
  )
}
