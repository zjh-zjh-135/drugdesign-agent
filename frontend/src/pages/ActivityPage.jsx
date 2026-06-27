import React, { useState } from 'react'
import { useApp } from '../store/AppContext'
import { api } from '../api/client'
import Molecule3DViewer from '../components/Molecule3DViewer'
import { Activity, Play, AlertCircle, Brain, BarChart3, TrendingUp, Beaker } from 'lucide-react'

/* ── 自定义动画按钮 ── */
function AnimatedPredictButton({ onClick, loading }) {
  return (
    <>
      <style>{`
        .anim-btn-wrap {
          display: flex;
          justify-content: center;
        }
        .anim-btn-wrap button {
          width: 160px;
          height: 48px;
          background-color: white;
          color: #475569;
          position: relative;
          overflow: hidden;
          font-size: 14px;
          letter-spacing: 1px;
          font-weight: 500;
          text-transform: uppercase;
          transition: all 0.3s ease;
          cursor: pointer;
          border: 0;
          display: flex;
          align-items: center;
          justify-content: center;
          border-radius: 6px;
          outline: none;
        }
        .anim-btn-wrap button:disabled {
          opacity: 0.6;
          cursor: not-allowed;
        }
        .anim-btn-wrap button::before, .anim-btn-wrap button::after {
          content: "";
          position: absolute;
          width: 0;
          height: 2px;
          background-color: #44d8a4;
          transition: all 0.3s cubic-bezier(0.35, 0.1, 0.25, 1);
        }
        .anim-btn-wrap button::before {
          right: 0;
          top: 0;
          transition: all 0.5s cubic-bezier(0.35, 0.1, 0.25, 1);
        }
        .anim-btn-wrap button::after {
          left: 0;
          bottom: 0;
        }
        .anim-btn-wrap button span {
          width: 100%;
          height: 100%;
          position: absolute;
          left: 0;
          top: 0;
          margin: 0;
          padding: 0;
          z-index: 1;
        }
        .anim-btn-wrap button span::before, .anim-btn-wrap button span::after {
          content: "";
          position: absolute;
          width: 2px;
          height: 0;
          background-color: #44d8a4;
          transition: all 0.3s cubic-bezier(0.35, 0.1, 0.25, 1);
        }
        .anim-btn-wrap button span::before {
          right: 0;
          top: 0;
          transition: all 0.5s cubic-bezier(0.35, 0.1, 0.25, 1);
        }
        .anim-btn-wrap button span::after {
          left: 0;
          bottom: 0;
        }
        .anim-btn-wrap button p {
          padding: 0;
          margin: 0;
          transition: all 0.4s cubic-bezier(0.35, 0.1, 0.25, 1);
          position: absolute;
          width: 100%;
          height: 100%;
        }
        .anim-btn-wrap button p::before, .anim-btn-wrap button p::after {
          position: absolute;
          width: 100%;
          transition: all 0.4s cubic-bezier(0.35, 0.1, 0.25, 1);
          z-index: 1;
          left: 0;
          text-align: center;
          font-family: ui-sans-serif, system-ui, -apple-system, sans-serif;
        }
        .anim-btn-wrap button p::before {
          content: attr(data-title);
          top: 50%;
          transform: translateY(-50%);
        }
        .anim-btn-wrap button p::after {
          content: attr(data-text);
          top: 150%;
          color: #44d8a4;
        }
        .anim-btn-wrap button:hover::before, .anim-btn-wrap button:hover::after {
          width: 100%;
        }
        .anim-btn-wrap button:hover span {
          z-index: 1;
        }
        .anim-btn-wrap button:hover span::before, .anim-btn-wrap button:hover span::after {
          height: 100%;
        }
        .anim-btn-wrap button:hover p::before {
          top: -50%;
          transform: rotate(5deg);
        }
        .anim-btn-wrap button:hover p::after {
          top: 50%;
          transform: translateY(-50%);
        }
        .anim-btn-wrap button.start {
          background-color: #44d8a4;
          box-shadow: 0px 5px 10px -10px rgba(0, 0, 0, 0.2);
          transition: all 0.2s ease;
        }
        .anim-btn-wrap button.start p::before {
          top: -50%;
          transform: rotate(5deg);
        }
        .anim-btn-wrap button.start p::after {
          color: white;
          transition: all 0s ease;
          content: attr(data-start);
          top: 50%;
          transform: translateY(-50%);
          animation: animStart 0.3s ease;
          animation-fill-mode: forwards;
        }
        @keyframes animStart {
          from { top: -50%; }
        }
        .anim-btn-wrap button.start:hover::before, .anim-btn-wrap button.start:hover::after {
          display: none;
        }
        .anim-btn-wrap button.start:hover span {
          display: none;
        }
        .anim-btn-wrap button:active {
          outline: none;
          border: none;
        }
        .anim-btn-wrap button:focus {
          outline: 0;
        }
      `}</style>
      <div className="anim-btn-wrap">
        <button
          className={loading ? 'start' : ''}
          onClick={onClick}
          disabled={loading}
        >
          <span></span>
          <p
            data-title="运行预测"
            data-text="开始预测"
            data-start="预测中..."
          ></p>
        </button>
      </div>
    </>
  )
}

export default function ActivityPage() {
  const { state } = useApp()
  const [smiles, setSmiles] = useState('')
  const [activityType, setActivityType] = useState('IC50')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [show3D, setShow3D] = useState(false)

  const handlePredict = async () => {
    if (!smiles.trim()) {
      setError('请输入SMILES')
      return
    }
    setLoading(true)
    setError(null)
    setResult(null)

    try {
      const res = await api.predictActivity({
        smiles: smiles.trim(),
        activity_type: activityType,
      })
      setResult(res.data.data)
    } catch (e) {
      setError(e.response?.data?.error || '预测失败')
    } finally {
      setLoading(false)
    }
  }

  const getActivityColor = (value) => {
    if (value >= 6) return 'text-emerald-700'
    return 'text-slate-600'
  }

  const getActivityBg = (value) => {
    if (value >= 6) return 'bg-emerald-50'
    return 'bg-slate-50'
  }

  return (
    <div className="max-w-5xl mx-auto">
      <h2 className="text-2xl font-bold text-slate-800 mb-6">
        活性预测 (QSAR)
      </h2>

      {/* 运行预测按钮 */}
      <div className="flex items-center justify-end mb-4">
        <AnimatedPredictButton onClick={handlePredict} loading={loading} />
      </div>

      {/* 输入区域 */}
      <div className="bg-white rounded-lg shadow-sm border border-slate-200 p-8 mb-8">
        <div className="mb-5">
          <label className="block text-sm font-medium text-slate-700 mb-2">活性类型</label>
          <select
            value={activityType}
            onChange={(e) => setActivityType(e.target.value)}
            className="border border-slate-300 rounded-lg px-4 py-3 text-sm"
          >
            <option value="IC50">IC50 (半数抑制浓度)</option>
            <option value="Ki">Ki (抑制常数)</option>
            <option value="EC50">EC50 (半数有效浓度)</option>
            <option value="KD">KD (解离常数)</option>
          </select>
        </div>

        <div className="mb-5">
          <label className="block text-sm font-medium text-slate-700 mb-2">SMILES</label>
          <input
            type="text"
            value={smiles}
            onChange={(e) => setSmiles(e.target.value)}
            placeholder="例如: c1ccccc1C(=O)Nc1ccc(cc1)Cl"
            className="w-full border border-slate-300 rounded-lg px-4 py-3 text-sm font-mono focus:outline-none focus:border-slate-400"
          />
        </div>

        {error && (
          <div className="mt-4 flex items-center gap-2 text-red-600 bg-red-50 px-4 py-2 rounded-lg text-sm">
            <AlertCircle className="w-4 h-4" />
            {error}
          </div>
        )}
      </div>

      {/* 预测结果 */}
      {result && (
        <div className="bg-white rounded-lg shadow-sm border border-slate-200 p-6">
          <div className="flex justify-between items-center mb-4">
            <div>
              <h3 className="text-lg font-bold text-slate-800">预测结果</h3>
              <p className="text-xs text-slate-400">
                {result.model_used === 'trained' ? '基于训练模型' : '基于描述符估算'}
              </p>
            </div>
            <div className="flex items-center gap-3">
              <div className="text-right">
                <div className="text-xs text-slate-400 mb-1">预测活性值</div>
                <div className={`text-3xl font-bold px-4 py-2 rounded-lg ${getActivityBg(result.predicted_value)} ${getActivityColor(result.predicted_value)}`}>
                  {result.predicted_value}
                </div>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-4 mb-4">
            <div className="bg-slate-50 rounded-lg p-3">
              <div className="text-xs text-slate-500 mb-1">活性类型</div>
              <div className="font-medium text-slate-800">{result.activity_type}</div>
            </div>
            <div className="bg-slate-50 rounded-lg p-3">
              <div className="text-xs text-slate-500 mb-1">单位</div>
              <div className="font-medium text-slate-800">{result.unit}</div>
            </div>
            <div className="bg-slate-50 rounded-lg p-3">
              <div className="text-xs text-slate-500 mb-1">置信度</div>
              <div className="font-medium text-slate-800">{(result.confidence * 100).toFixed(1)}%</div>
            </div>
          </div>

          {result.estimated_ic50_nM && (
            <div className="bg-slate-50 rounded-lg p-3 mb-4">
              <div className="text-xs text-slate-500 mb-1">估算 IC50</div>
              <div className="font-medium text-slate-800">
                {result.estimated_ic50_nM.toFixed(2)} nM
                <span className="text-xs text-slate-400 ml-2">(基于 p{result.activity_type} 转换)</span>
              </div>
            </div>
          )}

          {result.descriptor_contributions && (
            <div>
              <h4 className="text-sm font-medium text-slate-700 mb-2">描述符贡献</h4>
              <div className="grid grid-cols-2 gap-2">
                {Object.entries(result.descriptor_contributions).map(([key, val]) => (
                  <div key={key} className="flex justify-between items-center bg-slate-50 rounded px-3 py-1.5 text-sm">
                    <span className="text-slate-500">{key.toUpperCase()}</span>
                    <span className={`font-medium ${val >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                      {val > 0 ? '+' : ''}{val}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* 3D Viewer */}
      {show3D && (
        <Molecule3DViewer
          smiles={smiles}
          title="预测分子 - 3D结构"
          onClose={() => setShow3D(false)}
        />
      )}
    </div>
  )
}
