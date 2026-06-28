import React from 'react'
import AgentTracePanel from '../components/AgentTracePanel'

/**
 * AgentTracePage - Agent 执行追踪独立页面
 * 全屏展示 Agent 追踪面板，用于监控 AI 决策过程
 */
export default function AgentTracePage() {
  return (
    <div className="flex-1 p-6 bg-gray-50 overflow-y-auto">
      <div className="max-w-7xl mx-auto">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-slate-800">Agent 执行追踪</h1>
          <p className="text-sm text-slate-500 mt-1">
            实时监控 AI 决策过程、工具调用、LLM 交互和 Pipeline 执行状态
          </p>
        </div>
        <AgentTracePanel maxHeight={800} />
      </div>
    </div>
  )
}
