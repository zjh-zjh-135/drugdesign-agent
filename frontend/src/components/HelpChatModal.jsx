import React, { useState, useRef, useEffect, useCallback } from 'react'
import {
  X, Send, HelpCircle, MessageSquarePlus, FlaskConical,
  User, Loader2, Maximize2, Minimize2, GripHorizontal,
  Play, CheckCircle, AlertTriangle, Sliders, Activity,
  GitCompare, Lightbulb, FolderPlus, ChevronDown, ChevronRight,
  Bot, Zap, RotateCcw, Clock, Trash2, StopCircle, Brain,
  CircleDot, CheckCircle2, XCircle, Sparkles, ListChecks
} from 'lucide-react'
import { api } from '../api/client'

const SUGGESTED_QUESTIONS = [
  '创建一个新项目',
  '运行Pipeline生成分子',
  '分析失败分子原因',
  '查看项目状态',
  '给我一些下一步建议',
]

const ACTION_ICONS = {
  'create_project': FolderPlus,
  'run_pipeline': Play,
  'analyze_failures': AlertTriangle,
  'adjust_filters': Sliders,
  'get_project_status': Activity,
  'compare_molecules': GitCompare,
  'suggest_next_step': Lightbulb,
}

const ACTION_COLORS = {
  'create_project': 'bg-emerald-50 border-emerald-200 text-emerald-700 hover:bg-emerald-100',
  'run_pipeline': 'bg-blue-50 border-blue-200 text-blue-700 hover:bg-blue-100',
  'analyze_failures': 'bg-amber-50 border-amber-200 text-amber-700 hover:bg-amber-100',
  'adjust_filters': 'bg-purple-50 border-purple-200 text-purple-700 hover:bg-purple-100',
  'get_project_status': 'bg-slate-50 border-slate-200 text-slate-700 hover:bg-slate-100',
  'compare_molecules': 'bg-cyan-50 border-cyan-200 text-cyan-700 hover:bg-cyan-100',
  'suggest_next_step': 'bg-rose-50 border-rose-200 text-rose-700 hover:bg-rose-100',
}

const MIN_WIDTH = 400
const MIN_HEIGHT = 480
const MAX_WIDTH = 1100
const MAX_HEIGHT = 850

export default function HelpChatModal({ onClose, projectId }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [sessionId, setSessionId] = useState(null)
  const [mode, setMode] = useState('copilot') // 'copilot' | 'chat'
  const [executingAction, setExecutingAction] = useState(null)
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)
  const windowRef = useRef(null)

  /* ── Agent 自主工作流状态 ── */
  const [agentWorking, setAgentWorking] = useState(false)
  const [agentProgress, setAgentProgress] = useState(null) // { step: number, total: number, tool: string, status: string }
  const [agentSteps, setAgentSteps] = useState([])
  const [agentReport, setAgentReport] = useState(null)
  const [agentCancelled, setAgentCancelled] = useState(false)
  const abortControllerRef = useRef(null)

  /* ── 窗口状态 ── */
  const [position, setPosition] = useState({ x: 0, y: 0 })
  const [size, setSize] = useState({ width: 480, height: 600 })
  const [isDragging, setIsDragging] = useState(false)
  const [isResizing, setIsResizing] = useState(false)
  const dragStart = useRef({ x: 0, y: 0, posX: 0, posY: 0 })
  const resizeStart = useRef({ x: 0, y: 0, width: 0, height: 0 })
  const [isMaximized, setIsMaximized] = useState(false)
  const prevState = useRef({ position: { x: 0, y: 0 }, size: { width: 0, height: 0 } })
  const [isMinimized, setIsMinimized] = useState(false)

  /* 初始定位 */
  useEffect(() => {
    const vw = window.innerWidth
    const vh = window.innerHeight
    setPosition({
      x: Math.max(16, vw - 496),
      y: Math.max(16, vh - 636),
    })
  }, [])

  useEffect(() => {
    const handleResize = () => {
      if (isMaximized) return
      setPosition((pos) => ({
        x: Math.min(pos.x, window.innerWidth - 100),
        y: Math.min(pos.y, window.innerHeight - 100),
      }))
    }
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [isMaximized])

  /* ── 拖拽 ── */
  const startDrag = useCallback((e) => {
    if (isMaximized || e.target.closest('button') || e.target.closest('input') || e.target.closest('textarea')) return
    setIsDragging(true)
    dragStart.current = {
      x: e.clientX,
      y: e.clientY,
      posX: position.x,
      posY: position.y,
    }
  }, [isMaximized, position])

  const startResize = useCallback((e) => {
    if (isMaximized) return
    setIsResizing(true)
    resizeStart.current = {
      x: e.clientX,
      y: e.clientY,
      width: size.width,
      height: size.height,
    }
    e.preventDefault()
    e.stopPropagation()
  }, [isMaximized, size])

  useEffect(() => {
    const handleMouseMove = (e) => {
      if (isDragging) {
        const dx = e.clientX - dragStart.current.x
        const dy = e.clientY - dragStart.current.y
        setPosition({
          x: Math.max(0, dragStart.current.posX + dx),
          y: Math.max(0, dragStart.current.posY + dy),
        })
      }
      if (isResizing) {
        const dx = e.clientX - resizeStart.current.x
        const dy = e.clientY - resizeStart.current.y
        setSize({
          width: Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, resizeStart.current.width + dx)),
          height: Math.max(MIN_HEIGHT, Math.min(MAX_HEIGHT, resizeStart.current.height + dy)),
        })
      }
    }
    const handleMouseUp = () => {
      setIsDragging(false)
      setIsResizing(false)
    }
    if (isDragging || isResizing) {
      document.addEventListener('mousemove', handleMouseMove)
      document.addEventListener('mouseup', handleMouseUp)
      return () => {
        document.removeEventListener('mousemove', handleMouseMove)
        document.removeEventListener('mouseup', handleMouseUp)
      }
    }
  }, [isDragging, isResizing])

  const toggleMaximize = () => {
    if (isMaximized) {
      setIsMaximized(false)
      setPosition(prevState.current.position)
      setSize(prevState.current.size)
    } else {
      prevState.current = { position: { ...position }, size: { ...size } }
      setIsMaximized(true)
      setPosition({ x: 0, y: 0 })
      setSize({ width: window.innerWidth, height: window.innerHeight })
    }
  }

  /* ── 聊天逻辑 ── */
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }
  useEffect(() => { scrollToBottom() }, [messages])
  useEffect(() => { inputRef.current?.focus() }, [isMinimized])

  const handleSend = async (text = input) => {
    if (!text.trim() || loading) return
    const userMsg = { role: 'user', content: text.trim() }
    setMessages((prev) => [...prev, userMsg])
    setInput('')
    setLoading(true)

    try {
      if (mode === 'copilot') {
        // Copilot 模式：判断是目标导向还是简单聊天
        const isGoalOriented = checkGoalOriented(text.trim())

        if (isGoalOriented) {
          // 使用自主 Agent 目标执行
          await handleGoal(text.trim(), userMsg)
        } else {
          // 普通 Copilot 聊天
          const res = await api.agentChat({
            message: text.trim(),
            project_id: projectId,
            session_id: sessionId
          })
          
          if (res.data?.success) {
            const data = res.data.data || res.data
            if (data.session_id) setSessionId(data.session_id)
            
            setMessages((prev) => [...prev, {
              role: 'assistant',
              content: data.final_answer || '操作已识别',
              source: 'copilot',
              action_cards: data.action_cards || [],
              steps: data.steps || [],
              type: data.type
            }])
          } else {
            throw new Error(res.data?.error || '请求失败')
          }
        }
      } else {
        // 普通 AI 聊天模式
        const res = await api.aiChat({ messages: [...messages, userMsg] })
        if (res.data?.success) {
          setMessages((prev) => [...prev, {
            ...res.data.data,
            source: res.data.data.source || 'ai'
          }])
        } else {
          throw new Error(res.data?.error || '请求失败')
        }
      }
    } catch (e) {
      const errMsg = e.response?.data?.error || e.message || '网络错误'
      setMessages((prev) => [...prev, {
        role: 'assistant',
        content: `抱歉，暂时无法处理：${errMsg}`,
        source: 'error'
      }])
    } finally {
      setLoading(false)
    }
  }

  // 判断用户消息是否为目标导向（需要自主执行）
  const checkGoalOriented = (text) => {
    const goalKeywords = [
      '优化', '帮我', '帮我优化', '帮我分析', '帮我运行', '帮我调整',
      '帮我查看', '帮我建议', '帮我创建', '自动', '执行', '开始',
      '优化项目', '分析项目', '调整参数', '查看状态', '运行pipeline',
      '执行pipeline', '帮我处理', '处理一下', '搞一下', '弄一下',
    ]
    return goalKeywords.some(kw => text.includes(kw))
  }

  // 自主 Agent 目标执行
  const handleGoal = async (text, userMsg) => {
    setAgentWorking(true)
    setAgentCancelled(false)
    setAgentProgress({ step: 0, total: 0, tool: '', status: 'planning' })
    setAgentSteps([])
    setAgentReport(null)

    // 创建可取消的请求
    abortControllerRef.current = new AbortController()

    try {
      // 添加 "Agent 正在工作中" 系统消息
      setMessages((prev) => [...prev, {
        role: 'system',
        content: '',
        source: 'agent_working',
        agent_working: true,
      }])

      const res = await api.agentGoal({
        message: text.trim(),
        project_id: projectId,
        session_id: sessionId,
      })

      if (agentCancelled) {
        setMessages((prev) => prev.filter(m => !m.agent_working))
        setMessages((prev) => [...prev, {
          role: 'assistant',
          content: '❌ 任务已取消',
          source: 'error'
        }])
        return
      }

      const data = res.data?.data || res.data
      if (res.data?.success) {
        if (data.session_id) setSessionId(data.session_id)

        // 更新执行步骤状态
        const steps = data.execution_report?.steps || []
        setAgentSteps(steps.map((s, i) => ({
          step_number: s.step_number || i + 1,
          tool: s.tool,
          status: s.status,
          reason: s.reason,
          error: s.error,
        })))

        setAgentProgress({
          step: steps.length,
          total: steps.length,
          tool: steps.length > 0 ? steps[steps.length - 1].tool : '',
          status: 'completed',
        })

        setAgentReport({
          final_answer: data.final_answer,
          plan_summary: data.plan_summary,
          success: data.execution_report?.success || false,
        })

        // 替换 working 消息为最终 assistant 消息
        setMessages((prev) => prev.filter(m => !m.agent_working))
        setMessages((prev) => [...prev, {
          role: 'assistant',
          content: data.final_answer || '任务执行完成',
          source: 'copilot',
          action_cards: data.action_cards || [],
          steps: data.steps || [],
          type: 'autonomous',
          plan_summary: data.plan_summary,
          execution_report: data.execution_report,
        }])
      } else {
        throw new Error(res.data?.error || '请求失败')
      }
    } catch (e) {
      if (!agentCancelled) {
        const errMsg = e.response?.data?.error || e.message || '网络错误'
        setMessages((prev) => prev.filter(m => !m.agent_working))
        setMessages((prev) => [...prev, {
          role: 'assistant',
          content: `抱歉，任务执行失败：${errMsg}`,
          source: 'error'
        }])
      }
    } finally {
      setAgentWorking(false)
      setAgentProgress(null)
      abortControllerRef.current = null
    }
  }

  const handleCancelAgent = () => {
    setAgentCancelled(true)
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }
    setAgentWorking(false)
    setMessages((prev) => prev.filter(m => !m.agent_working))
    setMessages((prev) => [...prev, {
      role: 'assistant',
      content: '❌ 已取消当前任务',
      source: 'error'
    }])
  }

  const handleExecuteAction = async (action, params) => {
    setExecutingAction(action)
    try {
      const res = await api.agentExecute({ action, params })
      const data = res.data
      
      // 添加执行结果到消息
      setMessages((prev) => [...prev, {
        role: 'system',
        content: data.success 
          ? `✅ 操作 "${action}" 执行成功`
          : `❌ 操作 "${action}" 执行失败: ${data.error || '未知错误'}`,
        source: 'action_result',
        action_result: data
      }])
    } catch (e) {
      setMessages((prev) => [...prev, {
        role: 'system',
        content: `❌ 执行失败: ${e.message}`,
        source: 'error'
      }])
    } finally {
      setExecutingAction(null)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleNewChat = () => {
    setMessages([])
    setInput('')
    setSessionId(null)
    setAgentWorking(false)
    setAgentProgress(null)
    setAgentSteps([])
    setAgentReport(null)
    setAgentCancelled(false)
    inputRef.current?.focus()
  }

  const isEmpty = messages.length === 0

  /* ── Action Card 组件 ── */
  const ActionCard = ({ card }) => {
    const IconComponent = ACTION_ICONS[card.action] || Zap
    const colorClass = ACTION_COLORS[card.action] || 'bg-slate-50 border-slate-200 text-slate-700'
    const isExecuting = executingAction === card.action

    return (
      <div className={`rounded-lg border p-3 mb-2 ${colorClass} transition-all`}>
        <div className="flex items-center gap-2 mb-1.5">
          <IconComponent className="w-4 h-4" />
          <span className="text-xs font-semibold">{card.title}</span>
          {isExecuting && <Loader2 className="w-3 h-3 animate-spin ml-auto" />}
        </div>
        <p className="text-[11px] opacity-80 mb-2">{card.description}</p>
        <div className="flex gap-1.5">
          <button
            onClick={() => handleExecuteAction(card.action, card.params)}
            disabled={isExecuting}
            className="flex-1 text-[11px] px-2 py-1 rounded bg-white/80 hover:bg-white border border-current/20 font-medium transition disabled:opacity-50"
          >
            {isExecuting ? '执行中...' : '执行'}
          </button>
          <button
            onClick={() => {
              // 显示参数详情
              setMessages((prev) => [...prev, {
                role: 'system',
                content: `参数: ${JSON.stringify(card.params, null, 2)}`,
                source: 'debug'
              }])
            }}
            className="px-2 py-1 rounded bg-white/50 hover:bg-white/80 text-[11px] transition"
          >
            详情
          </button>
        </div>
      </div>
    )
  }

  /* ── Agent 工作进度组件 ── */
  const AgentWorkingIndicator = () => {
    if (!agentWorking) return null

    const progress = agentProgress || { step: 0, total: 0, tool: '', status: 'planning' }

    return (
      <div className="flex gap-2.5">
        <div className="w-7 h-7 rounded-full flex items-center justify-center shrink-0 bg-blue-600 animate-pulse">
          <Brain className="w-3.5 h-3.5 text-white" />
        </div>
        <div className="flex-1 px-3.5 py-2.5 rounded-2xl bg-blue-50 border border-blue-100 rounded-tl-sm">
          <div className="flex items-center gap-2 mb-2">
            <Loader2 className="w-3.5 h-3.5 text-blue-500 animate-spin" />
            <span className="text-xs font-semibold text-blue-700">
              Agent 正在工作中...
            </span>
            <button
              onClick={handleCancelAgent}
              className="ml-auto flex items-center gap-1 text-[10px] px-2 py-0.5 bg-red-50 text-red-500 border border-red-100 rounded hover:bg-red-100 transition"
            >
              <StopCircle className="w-3 h-3" />
              取消
            </button>
          </div>

          {/* 进度条 */}
          <div className="w-full bg-blue-100 rounded-full h-1.5 mb-3">
            <div
              className="bg-blue-500 h-1.5 rounded-full transition-all duration-500"
              style={{ width: progress.total > 0 ? `${(progress.step / progress.total) * 100}%` : '10%' }}
            />
          </div>

          {/* 当前状态 */}
          <div className="text-[10px] text-blue-600 mb-2">
            {progress.status === 'planning' && '正在制定执行计划...'}
            {progress.status === 'running' && `正在执行: ${progress.tool}`}
            {progress.status === 'completed' && '执行完成，正在总结...'}
            {progress.status === 'error' && '执行出错'}
          </div>

          {/* 已执行步骤 */}
          {agentSteps.length > 0 && (
            <div className="space-y-1">
              {agentSteps.map((s, i) => (
                <div key={i} className="flex items-center gap-1.5 text-[10px]">
                  {s.status === 'ok' ? (
                    <CheckCircle2 className="w-3 h-3 text-emerald-500" />
                  ) : s.status === 'error' ? (
                    <XCircle className="w-3 h-3 text-red-500" />
                  ) : s.status === 'running' ? (
                    <Loader2 className="w-3 h-3 text-blue-400 animate-spin" />
                  ) : (
                    <CircleDot className="w-3 h-3 text-slate-300" />
                  )}
                  <span className={`${
                    s.status === 'ok' ? 'text-emerald-600' :
                    s.status === 'error' ? 'text-red-500' :
                    s.status === 'running' ? 'text-blue-600' :
                    'text-slate-400'
                  }`}>
                    Step {s.step_number}: {s.tool}
                    {s.status === 'error' && s.error ? ` (${s.error.slice(0, 40)}${s.error.length > 40 ? '...' : ''})` : ''}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    )
  }

  /* ── Agent 执行报告组件 ── */
  const AgentReport = ({ report }) => {
    if (!report) return null
    return (
      <div className="mt-2 p-3 bg-emerald-50 border border-emerald-100 rounded-lg">
        <div className="flex items-center gap-1.5 mb-1.5">
          <Sparkles className="w-3.5 h-3.5 text-emerald-600" />
          <span className="text-[10px] font-semibold text-emerald-700">执行报告</span>
          {report.success ? (
            <span className="text-[9px] px-1.5 py-0.5 bg-emerald-100 text-emerald-600 rounded">成功</span>
          ) : (
            <span className="text-[9px] px-1.5 py-0.5 bg-amber-100 text-amber-600 rounded">部分完成</span>
          )}
        </div>
        <p className="text-[10px] text-emerald-800 leading-relaxed whitespace-pre-wrap">
          {report.final_answer}
        </p>
      </div>
    )
  }

  /* ── 最小化状态 ── */
  if (isMinimized) {
    return (
      <div
        className="fixed z-50 flex items-center gap-2 px-4 py-3 bg-slate-700 text-white rounded-full shadow-xl cursor-pointer hover:bg-slate-800 transition select-none"
        style={{ right: 24, bottom: 24 }}
        onClick={() => setIsMinimized(false)}
      >
        <Bot className="w-4 h-4" />
        <span className="text-sm font-medium">Copilot</span>
        {agentWorking && (
          <span className="w-2 h-2 bg-blue-400 rounded-full animate-pulse" />
        )}
      </div>
    )
  }

  /* ── 主窗口 ── */
  return (
    <div
      ref={windowRef}
      className={`fixed z-50 flex flex-col rounded-xl border border-slate-200 shadow-2xl overflow-hidden bg-white select-none ${
        isDragging ? 'cursor-grabbing' : ''
      }`}
      style={{
        left: position.x,
        top: position.y,
        width: size.width,
        height: size.height,
      }}
    >
      {/* 顶部栏 */}
      <div
        className="h-11 flex items-center justify-between px-3 border-b border-slate-100 shrink-0 cursor-grab active:cursor-grabbing bg-slate-50/80"
        onMouseDown={startDrag}
      >
        <div className="flex items-center gap-2">
          <GripHorizontal className="w-4 h-4 text-slate-400" />
          <div className="w-6 h-6 rounded-lg bg-slate-700 flex items-center justify-center">
            {mode === 'copilot' ? (
              <Bot className="w-3.5 h-3.5 text-white" />
            ) : (
              <FlaskConical className="w-3.5 h-3.5 text-white" />
            )}
          </div>
          <span className="text-xs font-semibold text-slate-700">
            {mode === 'copilot' ? 'DrugDesign Copilot' : 'DrugDesign AI 助手'}
          </span>
          {agentWorking && (
            <span className="flex items-center gap-1 text-[10px] px-1.5 py-0.5 bg-blue-50 text-blue-600 rounded border border-blue-100">
              <Loader2 className="w-2.5 h-2.5 animate-spin" />
              工作中
            </span>
          )}
          {/* 模式切换 */}
          <div className="flex items-center gap-1 ml-2 px-1.5 py-0.5 bg-slate-100 rounded-md">
            <button
              onClick={() => setMode('copilot')}
              className={`text-[10px] px-1.5 py-0.5 rounded transition ${
                mode === 'copilot' ? 'bg-white text-slate-700 shadow-sm font-medium' : 'text-slate-400'
              }`}
            >
              Copilot
            </button>
            <button
              onClick={() => setMode('chat')}
              className={`text-[10px] px-1.5 py-0.5 rounded transition ${
                mode === 'chat' ? 'bg-white text-slate-700 shadow-sm font-medium' : 'text-slate-400'
              }`}
            >
              聊天
            </button>
          </div>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={handleNewChat}
            title="新对话"
            className="w-7 h-7 rounded-md hover:bg-slate-200 flex items-center justify-center text-slate-400 hover:text-slate-600 transition"
          >
            <MessageSquarePlus className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={toggleMaximize}
            title={isMaximized ? '恢复' : '最大化'}
            className="w-7 h-7 rounded-md hover:bg-slate-200 flex items-center justify-center text-slate-400 hover:text-slate-600 transition"
          >
            {isMaximized ? <Minimize2 className="w-3.5 h-3.5" /> : <Maximize2 className="w-3.5 h-3.5" />}
          </button>
          <button
            onClick={() => setIsMinimized(true)}
            title="最小化"
            className="w-7 h-7 rounded-md hover:bg-slate-200 flex items-center justify-center text-slate-400 hover:text-slate-600 transition"
          >
            <Minimize2 className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={onClose}
            title="关闭"
            className="w-7 h-7 rounded-md hover:bg-red-100 flex items-center justify-center text-slate-400 hover:text-red-500 transition"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* 聊天内容区 */}
      <div className="flex-1 overflow-auto px-4 py-3 min-h-0">
        {isEmpty ? (
          <div className="h-full flex flex-col items-center justify-center text-center">
            <div className="w-12 h-12 rounded-xl bg-slate-700 flex items-center justify-center mb-3">
              {mode === 'copilot' ? (
                <Bot className="w-6 h-6 text-white" />
              ) : (
                <FlaskConical className="w-6 h-6 text-white" />
              )}
            </div>
            <h2 className="text-base font-bold text-slate-800 mb-1">
              {mode === 'copilot' ? 'DrugDesign Copilot' : 'DrugDesign AI 助手'}
            </h2>
            <p className="text-xs text-slate-400 mb-5">
              {mode === 'copilot' 
                ? '我可以帮你创建项目、运行Pipeline、分析失败分子、调整参数'
                : '我可以解答关于小分子药物设计的专业问题'
              }
            </p>

            {/* 快速操作按钮（Copilot 模式） */}
            {mode === 'copilot' && projectId && (
              <div className="grid grid-cols-2 gap-2 w-full mb-4">
                <button
                  onClick={() => handleSend('帮我运行Pipeline')}
                  className="flex items-center justify-center gap-1.5 px-3 py-2 bg-blue-50 border border-blue-200 rounded-lg text-xs text-blue-700 hover:bg-blue-100 transition"
                >
                  <Play className="w-3.5 h-3.5" />
                  运行 Pipeline
                </button>
                <button
                  onClick={() => handleSend('帮我分析失败分子')}
                  className="flex items-center justify-center gap-1.5 px-3 py-2 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-700 hover:bg-amber-100 transition"
                >
                  <AlertTriangle className="w-3.5 h-3.5" />
                  分析失败
                </button>
                <button
                  onClick={() => handleSend('帮我查看项目状态')}
                  className="flex items-center justify-center gap-1.5 px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-xs text-slate-700 hover:bg-slate-100 transition"
                >
                  <Activity className="w-3.5 h-3.5" />
                  项目状态
                </button>
                <button
                  onClick={() => handleSend('帮我优化项目')}
                  className="flex items-center justify-center gap-1.5 px-3 py-2 bg-rose-50 border border-rose-200 rounded-lg text-xs text-rose-700 hover:bg-rose-100 transition"
                >
                  <Sparkles className="w-3.5 h-3.5" />
                  智能优化
                </button>
              </div>
            )}

            <div className="grid grid-cols-1 gap-2 w-full">
              {SUGGESTED_QUESTIONS.slice(0, 4).map((q, i) => (
                <button
                  key={i}
                  onClick={() => handleSend(q)}
                  className="text-left px-3 py-2 border border-slate-200 rounded-lg text-xs text-slate-600 hover:bg-slate-50 hover:border-slate-300 transition"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            {messages.map((msg, idx) => (
              <div
                key={idx}
                className={`flex gap-2.5 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}
              >
                {/* 隐藏 Agent working 系统消息，由独立组件渲染 */}
                {msg.agent_working ? null : (
                  <>
                    <div className={`w-7 h-7 rounded-full flex items-center justify-center shrink-0 ${
                      msg.role === 'user'
                        ? 'bg-slate-200 text-slate-600'
                        : msg.source === 'copilot'
                        ? 'bg-blue-600 text-white'
                        : msg.source === 'error'
                        ? 'bg-red-100 text-red-500'
                        : 'bg-slate-700 text-white'
                    }`}>
                      {msg.role === 'user' ? (
                        <User className="w-3.5 h-3.5" />
                      ) : msg.source === 'copilot' ? (
                        <Bot className="w-3.5 h-3.5" />
                      ) : msg.source === 'error' ? (
                        <AlertTriangle className="w-3.5 h-3.5" />
                      ) : (
                        <FlaskConical className="w-3.5 h-3.5" />
                      )}
                    </div>
                    <div className={`max-w-[80%] px-3.5 py-2.5 rounded-2xl text-xs leading-relaxed ${
                      msg.role === 'user'
                        ? 'bg-slate-700 text-white rounded-tr-sm'
                        : msg.source === 'error'
                        ? 'bg-red-50 text-red-700 border border-red-100 rounded-tl-sm'
                        : 'bg-slate-50 text-slate-700 border border-slate-100 rounded-tl-sm'
                    }`}>
                      <div className="whitespace-pre-wrap">{msg.content}</div>
                      
                      {/* 来源标签 */}
                      {msg.role === 'assistant' && msg.source === 'copilot' && (
                        <div className="mt-1.5 pt-1.5 border-t border-slate-200/60 flex items-center gap-1">
                          <span className="text-[9px] px-1.5 py-0.5 bg-blue-50 text-blue-600 rounded border border-blue-100 font-medium">
                            Copilot
                          </span>
                          <span className="text-[9px] text-slate-400">
                            {msg.type === 'autonomous' ? '自主执行' : 'Agent 执行'}
                          </span>
                        </div>
                      )}
                      {msg.role === 'assistant' && msg.source === 'rag' && (
                        <div className="mt-1.5 pt-1.5 border-t border-slate-200/60 flex items-center gap-1">
                          <span className="text-[9px] px-1.5 py-0.5 bg-emerald-50 text-emerald-600 rounded border border-emerald-100 font-medium">
                            知识库
                          </span>
                        </div>
                      )}
                      {msg.role === 'assistant' && msg.source === 'ai' && (
                        <div className="mt-1.5 pt-1.5 border-t border-slate-200/60 flex items-center gap-1">
                          <span className="text-[9px] px-1.5 py-0.5 bg-blue-50 text-blue-500 rounded border border-blue-100 font-medium">
                            AI
                          </span>
                          <span className="text-[9px] text-slate-400">KIMI</span>
                        </div>
                      )}
                      
                      {/* Action Cards */}
                      {msg.action_cards && msg.action_cards.length > 0 && (
                        <div className="mt-3 pt-2 border-t border-slate-200/60">
                          <div className="flex items-center gap-1 mb-2">
                            <Zap className="w-3 h-3 text-amber-500" />
                            <span className="text-[10px] font-medium text-slate-500">可执行操作</span>
                          </div>
                          {msg.action_cards.map((card, ci) => (
                            <ActionCard key={ci} card={card} />
                          ))}
                        </div>
                      )}
                      
                      {/* ReAct 步骤展示 */}
                      {msg.steps && msg.steps.length > 0 && (
                        <div className="mt-3 pt-2 border-t border-slate-200/60">
                          <div className="flex items-center gap-1 mb-1">
                            <RotateCcw className="w-3 h-3 text-slate-400" />
                            <span className="text-[10px] font-medium text-slate-400">执行步骤</span>
                          </div>
                          {msg.steps.map((step, si) => (
                            <div key={si} className="text-[10px] text-slate-500 mb-1">
                              <span className="font-medium">Step {step.step}:</span> {step.thought}
                              {step.action && (
                                <div className="ml-3 mt-0.5 text-slate-600">
                                  Action: {step.action.tool}({JSON.stringify(step.action.params)})
                                </div>
                              )}
                              {step.status && (
                                <div className={`ml-3 mt-0.5 ${
                                  step.status === 'ok' ? 'text-emerald-600' : 'text-red-500'
                                }`}>
                                  Status: {step.status}
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      )}

                      {/* 自主执行报告 */}
                      {msg.execution_report && msg.type === 'autonomous' && (
                        <AgentReport report={{
                          final_answer: msg.execution_report?.final_answer || msg.content,
                          plan_summary: msg.plan_summary,
                          success: msg.execution_report?.success,
                        }} />
                      )}
                    </div>
                  </>
                )}
              </div>
            ))}

            {/* Agent 正在工作中指示器 */}
            <AgentWorkingIndicator />

            {/* 普通 loading 指示器 */}
            {loading && !agentWorking && (
              <div className="flex gap-2.5">
                <div className={`w-7 h-7 rounded-full flex items-center justify-center shrink-0 ${
                  mode === 'copilot' ? 'bg-blue-600' : 'bg-slate-700'
                }`}>
                  {mode === 'copilot' ? (
                    <Bot className="w-3.5 h-3.5 text-white" />
                  ) : (
                    <FlaskConical className="w-3.5 h-3.5 text-white" />
                  )}
                </div>
                <div className="px-3.5 py-2.5 rounded-2xl bg-slate-50 border border-slate-100 rounded-tl-sm">
                  <div className="flex items-center gap-2">
                    <Loader2 className="w-3.5 h-3.5 text-slate-400 animate-spin" />
                    <span className="text-xs text-slate-400">
                      {mode === 'copilot' ? 'Copilot 正在分析...' : 'AI 正在思考...'}
                    </span>
                  </div>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* 底部输入区 */}
      <div className="shrink-0 px-3 py-2.5 border-t border-slate-100 bg-white">
        <div className="relative">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={mode === 'copilot' ? "输入命令，如：帮我运行Pipeline、分析失败分子..." : "输入问题..."}
            rows={1}
            disabled={agentWorking}
            className="w-full min-h-[40px] max-h-[100px] px-3 py-2 pr-10 bg-slate-50 border border-slate-200 rounded-lg text-xs text-slate-700 placeholder:text-slate-400 focus:outline-none focus:border-slate-400 resize-none transition disabled:opacity-60"
            style={{ lineHeight: '1.5' }}
          />
          <button
            onClick={() => handleSend()}
            disabled={!input.trim() || loading || agentWorking}
            className={`absolute right-1.5 bottom-1.5 w-7 h-7 rounded-md flex items-center justify-center transition ${
              input.trim() && !loading && !agentWorking
                ? mode === 'copilot' ? 'bg-blue-600 text-white hover:bg-blue-700' : 'bg-slate-700 text-white hover:bg-slate-800'
                : 'bg-slate-200 text-slate-400 cursor-not-allowed'
            }`}
          >
            <Send className="w-3.5 h-3.5" />
          </button>
        </div>
        <div className="flex items-center justify-between mt-1.5">
          <div className="text-[10px] text-slate-400">
            {mode === 'copilot' ? 'Copilot 可执行操作' : 'AI 助手基于 KIMI 大模型'}
          </div>
          {sessionId && (
            <div className="flex items-center gap-1 text-[10px] text-slate-400">
              <Clock className="w-3 h-3" />
              <span>会话已保存</span>
            </div>
          )}
        </div>
      </div>

      {/* 缩放把手 */}
      {!isMaximized && (
        <div
          className="absolute bottom-0 right-0 w-4 h-4 cursor-se-resize"
          onMouseDown={startResize}
          title="拖动调整大小"
        >
          <svg width="16" height="16" viewBox="0 0 16 16" className="text-slate-300">
            <path d="M8 16 L16 16 L16 8" fill="none" stroke="currentColor" strokeWidth="1" />
            <path d="M12 16 L16 16 L16 12" fill="none" stroke="currentColor" strokeWidth="1" />
          </svg>
        </div>
      )}
    </div>
  )
}
