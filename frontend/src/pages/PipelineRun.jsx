import React, { useState, useEffect } from 'react'
import { useApp } from '../store/AppContext'
import { api } from '../api/client'
import PipelineStep from '../components/PipelineStep'
import CircularPipelineProgress from '../components/CircularPipelineProgress'
import { Play, RotateCw, Terminal, ChevronDown, ChevronUp } from 'lucide-react'

export default function PipelineRun() {
  const { state, dispatch } = useApp()
  const [status, setStatus] = useState(null)
  const [polling, setPolling] = useState(false)
  const [projectId, setProjectId] = useState('')
  const [enableFailedIteration, setEnableFailedIteration] = useState(false)
  const [logsExpanded, setLogsExpanded] = useState(false)

  const jobId = state.pipelineJobId

  useEffect(() => {
    if (state.currentProject) {
      setProjectId(state.currentProject.id)
    }
  }, [state.currentProject])

  useEffect(() => {
    let interval
    if (jobId && polling) {
      interval = setInterval(() => {
        checkStatus()
      }, 3000)
    }
    return () => clearInterval(interval)
  }, [jobId, polling])

  useEffect(() => {
    if (jobId && state.pipelineStatus === 'running') {
      setPolling(true)
    }
  }, [])

  const handleRefresh = () => {
    checkStatus()
    if (state.pipelineStatus === 'running') {
      setPolling(true)
    }
  }

  const checkStatus = async () => {
    if (!jobId) return
    try {
      const res = await api.getPipelineStatus(jobId)
      const data = res.data.data
      setStatus(data)
      dispatch({ type: 'SET_PIPELINE_STATUS', payload: data.status })
      if (data.status === 'completed' || data.status === 'failed') {
        setPolling(false)
      }
    } catch (e) {
      console.error(e)
    }
  }

  const runPipeline = async () => {
    if (!projectId) {
      alert('请先选择一个项目')
      return
    }
    try {
      const res = await api.runPipeline({
        project_id: parseInt(projectId),
        num_molecules: 1000,
        generation_strategy: 'crem',
        similarity_threshold: 0.6,
        qed_threshold: 0.5,
        sa_threshold: 4.0,
        admet_threshold: 60,
        top_n: 200,
        availability_threshold: 0.5,
        enable_failed_iteration: enableFailedIteration,
      })
      const newJobId = res.data.data.job_id
      dispatch({ type: 'SET_PIPELINE_JOB_ID', payload: newJobId })
      dispatch({ type: 'SET_PIPELINE_STATUS', payload: 'running' })
      setPolling(true)
      alert('Pipeline已启动')
    } catch (e) {
      alert('启动失败: ' + e.message)
    }
  }

  const stats = status?.stats || {}
  const stepStatus = (step) => {
    if (!status) return 'pending'
    if (status.status === 'failed') return step <= 1 ? 'completed' : 'failed'
    const thresholds = [
      stats.input > 0,
      stats.generated > 0,
      stats.filtered > 0,
      stats.structure_screened > 0,
      stats.admet_passed > 0,
      stats.refined > 0,
      stats.synthesis_passed > 0,
      stats.final > 0,
      enableFailedIteration && (stats.iterated > 0 || status.status === 'completed'),
    ]
    if (thresholds[step]) return 'completed'
    if (step > 0 && thresholds[step - 1]) return 'running'
    return 'pending'
  }

  const stepCounts = [
    stats.input || 0,
    stats.generated || 0,
    stats.filtered || 0,
    stats.structure_screened || 0,
    stats.admet_passed || 0,
    stats.refined || 0,
    stats.synthesis_passed || 0,
    stats.final || 0,
    enableFailedIteration ? (stats.iterated || 0) : 0,
  ]

  const stepTotals = [
    stats.input || 0,
    stats.generated || 0,
    stats.generated || 0,
    stats.filtered || 0,
    stats.structure_screened || 0,
    stats.admet_passed || 0,
    stats.refined || 0,
    stats.synthesis_passed || 0,
    enableFailedIteration ? (stats.final || 0) : 0,
  ]

  const stepCount = enableFailedIteration ? 9 : 8
  // 卡片环绕参数：9步时半径更大，避免重叠
  const ORBIT_R = stepCount === 9 ? 160 : 150
  const CENTER_X = 200
  const CENTER_Y = 200

  return (
    <div className="flex flex-col h-full">
      {/* 顶部标题栏 */}
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-lg font-bold text-gray-800">Pipeline运行</h2>
        <div className="flex gap-2 items-center">
          {/* 迭代学习开关 */}
          <label className="flex items-center gap-2 cursor-pointer select-none">
            <div className="relative">
              <input
                type="checkbox"
                checked={enableFailedIteration}
                onChange={(e) => setEnableFailedIteration(e.target.checked)}
                className="sr-only"
              />
              <div className={`w-10 h-5 rounded-full transition-colors ${enableFailedIteration ? 'bg-amber-500' : 'bg-gray-300'}`}>
                <div className="w-4 h-4 bg-white rounded-full shadow-sm transition-transform absolute top-0.5 left-0.5" style={{ transform: enableFailedIteration ? 'translateX(18px)' : 'translateX(0)' }}></div>
              </div>
            </div>
            <span className={`text-sm font-semibold ${enableFailedIteration ? 'text-slate-700' : 'text-slate-400'}`}>
              迭代学习
            </span>
          </label>

          {jobId && (
            <button
              onClick={handleRefresh}
              className="flex items-center gap-1 bg-gray-100 text-gray-700 px-3 py-1.5 rounded-lg text-sm hover:bg-gray-200 transition-colors"
            >
              <RotateCw className="w-3.5 h-3.5" /> 刷新
            </button>
          )}
          <button
            onClick={runPipeline}
            disabled={polling}
            className="btn-action"
          >
            <Play className="w-3.5 h-3.5" /> 运行
          </button>
        </div>
      </div>

      {/* 主体内容：左栏环+卡片，右栏日志 */}
      <div className="flex-1 flex flex-row gap-4 min-h-0 overflow-hidden">
        {/* 左栏：环形区域 */}
        <div className="flex-1 flex items-center justify-center min-h-0">
          <div className="relative" style={{ width: 400, height: 400 }}>
            {/* 环在中心 */}
            <div className="absolute" style={{ left: 110, top: 110 }}>
              <CircularPipelineProgress
                status={status?.status}
                stepStatus={stepStatus}
                enableFailedIteration={enableFailedIteration}
              />
            </div>

            {/* 环绕卡片 */}
            {Array.from({ length: stepCount }, (_, i) => {
              const angle = (i * 360 / stepCount - 90) * (Math.PI / 180)
              const x = CENTER_X + ORBIT_R * Math.cos(angle)
              const y = CENTER_Y + ORBIT_R * Math.sin(angle)
              return (
                <div
                  key={i}
                  className="absolute"
                  style={{ left: x - 40, top: y - 28 }}
                >
                  <PipelineStep
                    step={i}
                    status={stepStatus(i)}
                    count={stepCounts[i]}
                    total={stepTotals[i] || stepCounts[i]}
                  />
                </div>
              )
            })}
          </div>
        </div>

        {/* 右栏：日志 */}
        <div className="w-72 shrink-0 flex flex-col">
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 flex flex-col">
            <button
              onClick={() => setLogsExpanded(!logsExpanded)}
              className="w-full flex items-center justify-between text-sm font-semibold text-gray-700 hover:text-gray-900 transition-colors"
            >
              <span className="flex items-center gap-2">
                <Terminal className="w-4 h-4" /> 运行日志
              </span>
              {logsExpanded ? (
                <ChevronUp className="w-4 h-4 text-gray-500" />
              ) : (
                <ChevronDown className="w-4 h-4 text-gray-500" />
              )}
            </button>
            {logsExpanded && (
              <div className="mt-3 flex-1 min-h-0 bg-gray-900 rounded-lg p-3 font-mono text-xs text-green-400 overflow-auto" style={{ maxHeight: 'calc(100vh - 300px)' }}>
                {status?.logs && status.logs.length > 0 ? (
                  status.logs.map((log, idx) => (
                    <div key={idx} className="py-0.5">{log}</div>
                  ))
                ) : (
                  <div className="text-gray-500 py-4 text-center">暂无日志，请先启动 Pipeline</div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
