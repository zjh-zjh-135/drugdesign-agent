import React, { useState, useEffect, useCallback } from 'react'
import {
  Activity, Clock, Zap, Wrench, CheckCircle, XCircle,
  Database, TrendingUp, ChevronDown, ChevronUp, RefreshCw,
  Trash2, Search, MessageSquare, Cpu, AlertTriangle,
  BarChart3, Timer, Hash, Layers, ArrowRight, Sparkles
} from 'lucide-react'
import { api } from '../api/client'

/**
 * AgentTracePanel - Agent 执行追踪时间线可视化组件
 * 
 * 功能：
 * - 展示 Agent 最近执行的追踪记录
 * - 统计面板：总追踪数、LLM 调用、工具执行、成功率、Token 用量
 * - 时间线卡片：每个追踪的意图、耗时、步骤数、成功状态
 * - 详情展开：点击展开查看每个步骤的输入/输出/耗时/Token/错误
 * - 操作：刷新、清空、按会话过滤
 */

export default function AgentTracePanel({ sessionId = null, maxHeight = 600 }) {
  const [traces, setTraces] = useState([])
  const [stats, setStats] = useState({})
  const [loading, setLoading] = useState(false)
  const [expandedTraceId, setExpandedTraceId] = useState(null)
  const [filterSessionId, setFilterSessionId] = useState(sessionId || '')
  const [limit, setLimit] = useState(20)
  const [error, setError] = useState(null)

  // 获取追踪数据
  const fetchTraces = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const params = { limit }
      if (filterSessionId) params.session_id = filterSessionId
      
      const res = await api.getAgentTraces(params)
      if (res.data?.success) {
        setTraces(res.data.traces || [])
        setStats(res.data.stats || {})
      } else {
        setError(res.data?.error || '获取追踪失败')
      }
    } catch (e) {
      setError(e.message || '网络错误')
    } finally {
      setLoading(false)
    }
  }, [filterSessionId, limit])

  // 初始加载 + 自动刷新
  useEffect(() => {
    fetchTraces()
    const interval = setInterval(fetchTraces, 10000) // 10秒自动刷新
    return () => clearInterval(interval)
  }, [fetchTraces])

  // 清空追踪
  const handleClear = async () => {
    if (!window.confirm('确定要清空所有追踪记录吗？')) return
    try {
      await api.clearAgentTraces()
      setTraces([])
      setStats({})
    } catch (e) {
      setError(e.message || '清空失败')
    }
  }

  // 展开/收起追踪详情
  const toggleExpand = (traceId) => {
    setExpandedTraceId(expandedTraceId === traceId ? null : traceId)
  }

  // 格式化时间
  const formatTime = (isoString) => {
    if (!isoString) return '--'
    const date = new Date(isoString)
    return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  }

  const formatDate = (isoString) => {
    if (!isoString) return '--'
    const date = new Date(isoString)
    return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
  }

  // 格式化耗时
  const formatDuration = (ms) => {
    if (!ms && ms !== 0) return '--'
    if (ms < 1000) return `${Math.round(ms)}ms`
    if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`
    return `${(ms / 60000).toFixed(1)}min`
  }

  // 获取意图类型图标和颜色
  const getIntentStyle = (intentType) => {
    const styles = {
      'single_action': { color: 'text-blue-600', bg: 'bg-blue-50', label: '单一操作' },
      'multi_intent': { color: 'text-purple-600', bg: 'bg-purple-50', label: '多意图' },
      'complex_analysis': { color: 'text-amber-600', bg: 'bg-amber-50', label: '复杂分析' },
      'conditional': { color: 'text-orange-600', bg: 'bg-orange-50', label: '条件请求' },
      'comparison': { color: 'text-teal-600', bg: 'bg-teal-50', label: '对比' },
      'optimization': { color: 'text-emerald-600', bg: 'bg-emerald-50', label: '优化' },
      'follow_up': { color: 'text-indigo-600', bg: 'bg-indigo-50', label: '上下文' },
      'exploration': { color: 'text-slate-600', bg: 'bg-slate-50', label: '探索' },
    }
    return styles[intentType] || { color: 'text-slate-600', bg: 'bg-slate-50', label: intentType || '未知' }
  }

  // 获取步骤类型图标
  const StepIcon = ({ stepType }) => {
    const iconProps = { className: 'w-3.5 h-3.5' }
    switch (stepType) {
      case 'llm_call': return <Zap {...iconProps} className='w-3.5 h-3.5 text-amber-500' />
      case 'tool_execution': return <Wrench {...iconProps} className='w-3.5 h-3.5 text-blue-500' />
      case 'planning': return <Layers {...iconProps} className='w-3.5 h-3.5 text-purple-500' />
      case 'parsing': return <Cpu {...iconProps} className='w-3.5 h-3.5 text-teal-500' />
      case 'intent_parse': return <Search {...iconProps} className='w-3.5 h-3.5 text-indigo-500' />
      case 'report': return <BarChart3 {...iconProps} className='w-3.5 h-3.5 text-emerald-500' />
      default: return <Activity {...iconProps} className='w-3.5 h-3.5 text-slate-400' />
    }
  }

  // 获取状态图标
  const StatusIcon = ({ status }) => {
    if (status === 'ok' || status === true) {
      return <CheckCircle className='w-3.5 h-3.5 text-emerald-500' />
    }
    if (status === 'error' || status === false) {
      return <XCircle className='w-3.5 h-3.5 text-red-400' />
    }
    return <Activity className='w-3.5 h-3.5 text-slate-400' />
  }

  return (
    <div className='flex flex-col h-full bg-white rounded-xl border border-slate-200 overflow-hidden'>
      {/* ── 顶部标题栏 ── */}
      <div className='flex items-center justify-between px-4 py-3 border-b border-slate-100 bg-slate-50/50'>
        <div className='flex items-center gap-2'>
          <div className='w-7 h-7 rounded-lg bg-slate-700 flex items-center justify-center'>
            <Activity className='w-3.5 h-3.5 text-white' />
          </div>
          <div>
            <h2 className='text-sm font-semibold text-slate-700'>Agent 执行追踪</h2>
            <p className='text-[10px] text-slate-400'>实时记录 ReAct 循环的每个步骤</p>
          </div>
        </div>
        <div className='flex items-center gap-1.5'>
          <button
            onClick={fetchTraces}
            disabled={loading}
            className='flex items-center gap-1 px-2.5 py-1.5 text-[10px] font-medium bg-white border border-slate-200 rounded-lg text-slate-600 hover:bg-slate-50 hover:border-slate-300 transition disabled:opacity-50'
          >
            <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
            刷新
          </button>
          <button
            onClick={handleClear}
            className='flex items-center gap-1 px-2.5 py-1.5 text-[10px] font-medium bg-white border border-slate-200 rounded-lg text-red-500 hover:bg-red-50 hover:border-red-200 transition'
          >
            <Trash2 className='w-3 h-3' />
            清空
          </button>
        </div>
      </div>

      {/* ── 统计面板 ── */}
      {stats.total_traces > 0 && (
        <div className='grid grid-cols-5 gap-2 px-4 py-3 border-b border-slate-100 bg-white'>
          <StatCard
            icon={<Hash className='w-3.5 h-3.5 text-blue-500' />}
            label='总追踪数'
            value={stats.total_traces}
            sub={`成功率 ${stats.success_rate || 0}%`}
          />
          <StatCard
            icon={<Zap className='w-3.5 h-3.5 text-amber-500' />}
            label='LLM 调用'
            value={stats.total_llm_calls}
            sub={`Token ${(stats.total_tokens || 0).toLocaleString()}`}
          />
          <StatCard
            icon={<Wrench className='w-3.5 h-3.5 text-blue-500' />}
            label='工具执行'
            value={stats.total_tool_calls}
            sub='平均耗时 --'
          />
          <StatCard
            icon={<Timer className='w-3.5 h-3.5 text-emerald-500' />}
            label='平均耗时'
            value={formatDuration(stats.avg_latency_ms)}
            sub='毫秒级响应'
          />
          <StatCard
            icon={<TrendingUp className='w-3.5 h-3.5 text-purple-500' />}
            label='成功率'
            value={`${stats.success_rate || 0}%`}
            sub={`${stats.total_traces - Math.round((stats.total_traces * (stats.success_rate || 0)) / 100)} 失败`}
          />
        </div>
      )}

      {/* ── 过滤栏 ── */}
      <div className='flex items-center gap-2 px-4 py-2 border-b border-slate-100 bg-white'>
        <div className='flex items-center gap-1.5 flex-1'>
          <Search className='w-3 h-3 text-slate-400' />
          <input
            type='text'
            value={filterSessionId}
            onChange={(e) => setFilterSessionId(e.target.value)}
            placeholder='输入会话 ID 过滤...'
            className='flex-1 text-xs text-slate-600 placeholder:text-slate-300 bg-transparent outline-none'
          />
        </div>
        <select
          value={limit}
          onChange={(e) => setLimit(Number(e.target.value))}
          className='text-[10px] px-2 py-1 border border-slate-200 rounded-md text-slate-600 bg-white outline-none'
        >
          <option value={10}>10 条</option>
          <option value={20}>20 条</option>
          <option value={50}>50 条</option>
          <option value={100}>100 条</option>
        </select>
      </div>

      {/* ── 错误提示 ── */}
      {error && (
        <div className='mx-4 mt-2 px-3 py-2 bg-red-50 border border-red-100 rounded-lg text-[10px] text-red-600 flex items-center gap-1.5'>
          <AlertTriangle className='w-3 h-3' />
          {error}
        </div>
      )}

      {/* ── 追踪列表 ── */}
      <div className='flex-1 overflow-auto px-4 py-3 space-y-3' style={{ maxHeight }}>
        {traces.length === 0 ? (
          <div className='flex flex-col items-center justify-center py-12 text-center'>
            <div className='w-12 h-12 rounded-xl bg-slate-100 flex items-center justify-center mb-3'>
              <Activity className='w-5 h-5 text-slate-300' />
            </div>
            <p className='text-xs text-slate-400'>暂无追踪记录</p>
            <p className='text-[10px] text-slate-300 mt-1'>Agent 执行后自动记录</p>
          </div>
        ) : (
          traces.map((trace) => (
            <TraceCard
              key={trace.trace_id}
              trace={trace}
              isExpanded={expandedTraceId === trace.trace_id}
              onToggle={() => toggleExpand(trace.trace_id)}
              formatTime={formatTime}
              formatDuration={formatDuration}
              formatDate={formatDate}
              getIntentStyle={getIntentStyle}
              StepIcon={StepIcon}
              StatusIcon={StatusIcon}
            />
          ))
        )}
      </div>
    </div>
  )
}

// ── 统计卡片子组件 ──
function StatCard({ icon, label, value, sub }) {
  return (
    <div className='p-2.5 bg-slate-50 border border-slate-100 rounded-lg'>
      <div className='flex items-center gap-1.5 mb-1'>
        {icon}
        <span className='text-[10px] text-slate-500 font-medium'>{label}</span>
      </div>
      <div className='text-sm font-bold text-slate-700'>{value}</div>
      <div className='text-[9px] text-slate-400 mt-0.5'>{sub}</div>
    </div>
  )
}

// ── 追踪卡片子组件 ──
function TraceCard({ trace, isExpanded, onToggle, formatTime, formatDuration, formatDate, getIntentStyle, StepIcon, StatusIcon }) {
  const intentStyle = getIntentStyle(trace.intent_type)
  const stepCount = trace.steps?.length || 0
  const llmCalls = trace.steps?.filter(s => s.step_type === 'llm_call').length || 0
  const toolCalls = trace.steps?.filter(s => s.step_type === 'tool_execution').length || 0

  return (
    <div className={`border rounded-lg transition-all ${isExpanded ? 'border-slate-300 shadow-sm' : 'border-slate-200 hover:border-slate-300'}`}>
      {/* 卡片头部 */}
      <div
        className={`flex items-center gap-3 px-3 py-2.5 cursor-pointer ${isExpanded ? 'bg-slate-50/80' : 'bg-white hover:bg-slate-50/50'}`}
        onClick={onToggle}
      >
        {/* 状态图标 */}
        <div className='shrink-0'>
          <StatusIcon status={trace.success} />
        </div>

        {/* 主要信息 */}
        <div className='flex-1 min-w-0'>
          <div className='flex items-center gap-1.5 mb-0.5'>
            <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${intentStyle.bg} ${intentStyle.color}`}>
              {intentStyle.label}
            </span>
            {trace.project_id && (
              <span className='text-[9px] px-1.5 py-0.5 bg-slate-100 text-slate-500 rounded'>
                项目 #{trace.project_id}
              </span>
            )}
          </div>
          <p className='text-[11px] text-slate-700 truncate'>
            {trace.user_message || '无消息'}
          </p>
          <div className='flex items-center gap-2 mt-1'>
            <span className='text-[9px] text-slate-400 flex items-center gap-0.5'>
              <Clock className='w-2.5 h-2.5' />
              {formatDate(trace.start_time)}
            </span>
            <span className='text-[9px] text-slate-400 flex items-center gap-0.5'>
              <Timer className='w-2.5 h-2.5' />
              {formatDuration(trace.total_latency_ms)}
            </span>
            <span className='text-[9px] text-slate-400 flex items-center gap-0.5'>
              <Layers className='w-2.5 h-2.5' />
              {stepCount} 步骤
            </span>
          </div>
        </div>

        {/* 右侧摘要 */}
        <div className='flex items-center gap-2 shrink-0'>
          {llmCalls > 0 && (
            <span className='text-[9px] px-1.5 py-0.5 bg-amber-50 text-amber-600 rounded flex items-center gap-0.5'>
              <Zap className='w-2.5 h-2.5' />
              {llmCalls}
            </span>
          )}
          {toolCalls > 0 && (
            <span className='text-[9px] px-1.5 py-0.5 bg-blue-50 text-blue-600 rounded flex items-center gap-0.5'>
              <Wrench className='w-2.5 h-2.5' />
              {toolCalls}
            </span>
          )}
          <button className='p-0.5 hover:bg-slate-100 rounded transition'>
            {isExpanded ? (
              <ChevronUp className='w-3.5 h-3.5 text-slate-400' />
            ) : (
              <ChevronDown className='w-3.5 h-3.5 text-slate-400' />
            )}
          </button>
        </div>
      </div>

      {/* 展开详情 */}
      {isExpanded && (
        <div className='border-t border-slate-100 px-3 py-3 space-y-2'>
          {/* Trace ID */}
          <div className='flex items-center gap-1.5 text-[9px] text-slate-400 mb-2'>
            <Hash className='w-2.5 h-2.5' />
            <span className='font-mono'>Trace ID: {trace.trace_id}</span>
            {trace.session_id && (
              <>
                <span className='mx-1'>|</span>
                <MessageSquare className='w-2.5 h-2.5' />
                <span className='font-mono'>Session: {trace.session_id}</span>
              </>
            )}
          </div>

          {/* 步骤时间线 */}
          <div className='space-y-1.5'>
            {trace.steps?.map((step, index) => (
              <StepDetail
                key={index}
                step={step}
                index={index}
                isLast={index === trace.steps.length - 1}
                StepIcon={StepIcon}
                StatusIcon={StatusIcon}
                formatDuration={formatDuration}
              />
            ))}
          </div>

          {/* 最终结果 */}
          {trace.final_result && (
            <div className='mt-2 p-2.5 bg-slate-50 border border-slate-200 rounded-lg'>
              <div className='flex items-center gap-1.5 mb-1'>
                <Sparkles className='w-3 h-3 text-slate-400' />
                <span className='text-[10px] font-medium text-slate-600'>最终结果</span>
              </div>
              <pre className='text-[10px] text-slate-600 leading-relaxed whitespace-pre-wrap overflow-x-auto'>
                {JSON.stringify(trace.final_result, null, 2).slice(0, 500)}
                {JSON.stringify(trace.final_result).length > 500 ? '...' : ''}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── 步骤详情子组件 ──
function StepDetail({ step, index, isLast, StepIcon, StatusIcon, formatDuration }) {
  const [showDetails, setShowDetails] = useState(false)

  return (
    <div className='relative'>
      {/* 时间线连接线 */}
      {!isLast && (
        <div className='absolute left-[13px] top-7 w-px h-[calc(100%-24px)] bg-slate-200' />
      )}

      <div className='flex items-start gap-2.5'>
        {/* 步骤图标 */}
        <div className='relative z-10 shrink-0 w-7 h-7 rounded-full bg-white border border-slate-200 flex items-center justify-center'>
          <StepIcon stepType={step.step_type} />
        </div>

        {/* 步骤内容 */}
        <div className='flex-1 min-w-0 pb-2'>
          <div className='flex items-center gap-1.5 mb-0.5'>
            <span className='text-[10px] font-medium text-slate-700'>
              {step.name}
            </span>
            <span className={`text-[9px] px-1 py-0.5 rounded ${
              step.status === 'ok' ? 'bg-emerald-50 text-emerald-600' :
              step.status === 'error' ? 'bg-red-50 text-red-500' :
              'bg-slate-50 text-slate-500'
            }`}>
              {step.status === 'ok' ? '成功' : step.status === 'error' ? '失败' : step.status}
            </span>
            {step.latency_ms > 0 && (
              <span className='text-[9px] text-slate-400 flex items-center gap-0.5'>
                <Timer className='w-2.5 h-2.5' />
                {formatDuration(step.latency_ms)}
              </span>
            )}
            {step.token_usage?.total > 0 && (
              <span className='text-[9px] text-slate-400 flex items-center gap-0.5'>
                <Database className='w-2.5 h-2.5' />
                {step.token_usage.total} tokens
              </span>
            )}
          </div>

          {/* 输入/输出切换 */}
          <button
            onClick={() => setShowDetails(!showDetails)}
            className='text-[9px] text-slate-400 hover:text-slate-600 flex items-center gap-0.5 transition'
          >
            {showDetails ? (
              <>
                <ChevronUp className='w-2.5 h-2.5' />
                收起详情
              </>
            ) : (
              <>
                <ChevronDown className='w-2.5 h-2.5' />
                查看详情
              </>
            )}
          </button>

          {/* 详情展开 */}
          {showDetails && (
            <div className='mt-1.5 space-y-1.5'>
              {/* 输入数据 */}
              {Object.keys(step.input_data || {}).length > 0 && (
                <div className='p-2 bg-slate-50 border border-slate-200 rounded-lg'>
                  <div className='text-[9px] font-medium text-slate-500 mb-1 flex items-center gap-1'>
                    <ArrowRight className='w-2.5 h-2.5' />
                    输入
                  </div>
                  <pre className='text-[9px] text-slate-600 leading-relaxed whitespace-pre-wrap overflow-x-auto'>
                    {JSON.stringify(step.input_data, null, 2).slice(0, 400)}
                    {JSON.stringify(step.input_data).length > 400 ? '...' : ''}
                  </pre>
                </div>
              )}

              {/* 输出数据 */}
              {Object.keys(step.output_data || {}).length > 0 && (
                <div className='p-2 bg-slate-50 border border-slate-200 rounded-lg'>
                  <div className='text-[9px] font-medium text-slate-500 mb-1 flex items-center gap-1'>
                    <CheckCircle className='w-2.5 h-2.5' />
                    输出
                  </div>
                  <pre className='text-[9px] text-slate-600 leading-relaxed whitespace-pre-wrap overflow-x-auto'>
                    {JSON.stringify(step.output_data, null, 2).slice(0, 400)}
                    {JSON.stringify(step.output_data).length > 400 ? '...' : ''}
                  </pre>
                </div>
              )}

              {/* 错误信息 */}
              {step.error && (
                <div className='p-2 bg-red-50 border border-red-100 rounded-lg'>
                  <div className='text-[9px] font-medium text-red-500 mb-1 flex items-center gap-1'>
                    <AlertTriangle className='w-2.5 h-2.5' />
                    错误
                  </div>
                  <p className='text-[9px] text-red-600 leading-relaxed'>
                    {step.error}
                  </p>
                </div>
              )}

              {/* Token 用量明细 */}
              {step.token_usage && Object.keys(step.token_usage).length > 0 && (
                <div className='flex items-center gap-3 text-[9px] text-slate-500'>
                  {step.token_usage.prompt > 0 && (
                    <span>Prompt: {step.token_usage.prompt.toLocaleString()}</span>
                  )}
                  {step.token_usage.completion > 0 && (
                    <span>Completion: {step.token_usage.completion.toLocaleString()}</span>
                  )}
                  {step.token_usage.total > 0 && (
                    <span className='font-medium'>Total: {step.token_usage.total.toLocaleString()}</span>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
