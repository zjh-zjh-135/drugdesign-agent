import React, { useState, useRef, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  X, Send, HelpCircle, MessageSquarePlus, FlaskConical,
  User, Loader2, Maximize2, Minimize2, GripHorizontal,
  Play, CheckCircle, AlertTriangle, Sliders, Activity,
  GitCompare, Lightbulb, FolderPlus, ChevronDown, ChevronRight,
  Bot, Zap, RotateCcw, Clock, Trash2, StopCircle, Brain,
  CircleDot, CheckCircle2, XCircle, Sparkles, ListChecks,
  Navigation, Filter, Bell, RefreshCw, BarChart3, Eye
} from 'lucide-react'
import { api } from '../api/client'
import { useApp } from '../store/AppContext'
import TargetSelector from './TargetSelector'

const SUGGESTED_QUESTIONS = [
  '创建一个新项目',
  '运行Pipeline生成分子',
  '分析失败分子原因',
  '查看项目状态',
  '给我一些下一步建议',
]

const MIN_WIDTH = 400
const MIN_HEIGHT = 480
const MAX_WIDTH = 1100
const MAX_HEIGHT = 850

export default function HelpChatModal({ onClose, projectId }) {
  const navigate = useNavigate()
  const { dispatch } = useApp()
  
  /* ── 项目创建表单（内嵌组件） ── */
  const ProjectCreationForm = ({ onCreated, onAutoRun }) => {
    const [target, setTarget] = useState(null)
    const [projectName, setProjectName] = useState('')
    const [creating, setCreating] = useState(false)
    const [createError, setCreateError] = useState(null)
    
    // 选择靶点后自动生成项目名称
    useEffect(() => {
      if (target?.target_name) {
        const date = new Date().toISOString().slice(0, 10).replace(/-/g, '')
        setProjectName(`${target.target_name}_${date}`)
      }
    }, [target])
    
    const handleCreate = async () => {
      if (!target?.target_name) {
        setCreateError('请先选择靶点蛋白')
        return
      }
      if (!projectName.trim()) {
        setCreateError('请输入项目名称')
        return
      }
      setCreating(true)
      setCreateError(null)
      try {
        const res = await api.createProject({
          name: projectName.trim(),
          target_name: target.target_name,
          target_pdb: target.target_pdb || '',
          design_goal: 'hit_finding',
        })
        if (res.data?.success) {
          const newProject = res.data.project
          onCreated(newProject)
        } else {
          setCreateError(res.data?.error || '创建失败')
        }
      } catch (e) {
        setCreateError(e.response?.data?.error || e.message || '创建失败')
      } finally {
        setCreating(false)
      }
    }

    const handleAutoRun = async () => {
      if (!target?.target_name) {
        setCreateError('请先选择靶点蛋白')
        return
      }
      setCreating(true)
      setCreateError(null)
      try {
        const res = await api.createProject({
          name: projectName.trim() || undefined,
          target_name: target.target_name,
          target_pdb: target.target_pdb || '',
          design_goal: 'hit_finding',
        })
        if (res.data?.success) {
          const newProject = res.data.project
          onAutoRun(newProject)
        } else {
          setCreateError(res.data?.error || '创建失败')
        }
      } catch (e) {
        setCreateError(e.response?.data?.error || e.message || '创建失败')
      } finally {
        setCreating(false)
      }
    }
    
    return (
      <div className="mt-2 p-3 bg-white border border-slate-200 rounded-lg space-y-3">
        <div className="text-[10px] font-medium text-slate-500 uppercase tracking-wider">项目创建</div>
        
        <div className="space-y-1.5">
          <label className="text-[10px] font-medium text-slate-600">靶点蛋白</label>
          <TargetSelector
            value={target}
            onChange={(val) => { setTarget(val); setCreateError(null) }}
          />
        </div>
        
        <div className="space-y-1.5">
          <label className="text-[10px] font-medium text-slate-600">项目名称</label>
          <input
            type="text"
            value={projectName}
            onChange={(e) => { setProjectName(e.target.value); setCreateError(null) }}
            placeholder="选择靶点后自动生成"
            className="w-full px-2.5 py-1.5 text-xs border border-slate-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-slate-400 focus:border-slate-400"
          />
          <div className="text-[9px] text-slate-400">设计目标默认为 hit_finding，其他参数使用系统默认</div>
        </div>
        
        {createError && (
          <div className="text-[10px] text-red-500 bg-red-50 px-2 py-1 rounded border border-red-100">
            {createError}
          </div>
        )}
        
        <div className="flex gap-2">
          <button
            onClick={handleCreate}
            disabled={creating || !target?.target_name}
            className="flex-1 px-3 py-2 text-xs font-medium bg-slate-700 text-white rounded-lg hover:bg-slate-800 disabled:opacity-50 disabled:cursor-not-allowed transition flex items-center justify-center gap-1.5"
          >
            {creating ? (
              <>
                <Loader2 className="w-3 h-3 animate-spin" />
                创建中...
              </>
            ) : (
              <>
                <FolderPlus className="w-3 h-3" />
                创建项目
              </>
            )}
          </button>
          <button
            onClick={handleAutoRun}
            disabled={creating || !target?.target_name}
            className="flex-1 px-3 py-2 text-xs font-medium bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition flex items-center justify-center gap-1.5"
          >
            {creating ? (
              <>
                <Loader2 className="w-3 h-3 animate-spin" />
                启动中...
              </>
            ) : (
              <>
                <Zap className="w-3 h-3" />
                一键创建并运行
              </>
            )}
          </button>
        </div>
      </div>
    )
  }
  
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [sessionId, setSessionId] = useState(null)
  const [mode, setMode] = useState('copilot') // 'copilot' | 'chat'
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
  
  /* ── 前端动作展示 ── */
  const [pendingActions, setPendingActions] = useState([])
  const [showActionPanel, setShowActionPanel] = useState(false)

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
        // Copilot 模式：统一走 agentChat，后端 LLM 判断是 goal-oriented 还是 chat
        const res = await api.agentChat({
          message: text.trim(),
          project_id: projectId,
          session_id: sessionId
        })
        
        if (res.data?.success) {
          const data = res.data.data || res.data
          if (data.session_id) setSessionId(data.session_id)
          
          // 执行前端动作（如果有）
          const frontendActions = data.actions || []
          if (frontendActions.length > 0) {
            executeFrontendActions(frontendActions)
          }
          
          // 判断是否为自主执行模式
          const isAutonomous = data.type === 'action' || data.autonomous || 
            (data.execution_report && data.execution_report.steps && data.execution_report.steps.length > 0)
          
          if (isAutonomous) {
            setMessages((prev) => [...prev, {
              role: 'assistant',
              content: data.chat_summary || data.final_answer || '任务执行完成',
              source: 'copilot',
              steps: data.steps || [],
              type: 'autonomous',
              plan_summary: data.plan_summary,
              execution_report: data.execution_report,
            }])
          } else {
            setMessages((prev) => [...prev, {
              role: 'assistant',
              content: data.chat_summary || data.final_answer || '操作已识别',
              source: 'copilot',
              steps: data.steps || [],
              type: data.type,
              form_type: data.form_type || '',
            }])
          }
        } else {
          throw new Error(res.data?.error || '请求失败')
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

  /* ── 前端动作执行器 ── */
  const executeFrontendActions = useCallback((actions) => {
    if (!actions || actions.length === 0) return
    
    const executed = []
    
    // 按优先级排序
    const sortedActions = [...actions].sort((a, b) => (b.priority || 0) - (a.priority || 0))
    
    for (const action of sortedActions) {
      try {
        const { type, payload } = action
        
        switch (type) {
          case 'navigate': {
            const path = payload?.path || '/'
            setTimeout(() => navigate(path), 100)
            executed.push({ type, status: 'done', description: action.description })
            break
          }
          
          case 'set_state': {
            const key = payload?.key
            const value = payload?.value
            if (key && value !== undefined) {
              dispatch({ type: 'APPLY_AGENT_ACTION', payload: { key, value } })
              executed.push({ type, status: 'done', description: action.description })
            }
            break
          }
          
          case 'set_filter': {
            const filters = payload?.filters
            if (filters) {
              dispatch({ type: 'SET_FILTER_PARAMS', payload: filters })
              // 同时存储到 localStorage，页面加载时读取
              localStorage.setItem('agent_filter_params', JSON.stringify(filters))
              executed.push({ type, status: 'done', description: action.description })
            }
            break
          }
          
          case 'highlight': {
            const ids = payload?.molecule_ids || []
            if (ids.length > 0) {
              localStorage.setItem('agent_highlight_molecules', JSON.stringify(ids))
              executed.push({ type, status: 'done', description: action.description })
            }
            break
          }
          
          case 'toast': {
            const msg = payload?.message || ''
            const toastType = payload?.type || 'info'
            const duration = payload?.duration || 4000
            if (msg) {
              dispatch({
                type: 'ADD_NOTIFICATION',
                payload: { id: Date.now(), message: msg, type: toastType, duration }
              })
              executed.push({ type, status: 'done', description: action.description })
            }
            break
          }
          
          case 'refresh': {
            setTimeout(() => window.location.reload(), 500)
            executed.push({ type, status: 'done', description: action.description })
            break
          }
          
          case 'show_data': {
            // 存储数据到 localStorage，页面组件读取展示
            localStorage.setItem('agent_show_data', JSON.stringify(payload))
            executed.push({ type, status: 'done', description: action.description })
            break
          }
          
          case 'show_chart': {
            localStorage.setItem('agent_show_chart', JSON.stringify(payload))
            executed.push({ type, status: 'done', description: action.description })
            break
          }
          
          case 'open_modal': {
            const modalType = payload?.modal_type || 'info'
            localStorage.setItem('agent_open_modal', JSON.stringify({ modal_type: modalType, data: payload }))
            executed.push({ type, status: 'done', description: action.description })
            break
          }
          
          case 'scroll_to': {
            const selector = payload?.selector
            if (selector) {
              setTimeout(() => {
                const el = document.querySelector(selector)
                el?.scrollIntoView({ behavior: 'smooth', block: 'center' })
              }, 300)
              executed.push({ type, status: 'done', description: action.description })
            }
            break
          }
          
          default:
            executed.push({ type, status: 'skipped', description: `未知动作: ${type}` })
        }
      } catch (e) {
        executed.push({ type: action.type, status: 'error', error: e.message })
      }
    }
    
    setPendingActions(executed)
    if (executed.length > 0) setShowActionPanel(true)
    
    return executed
  }, [navigate, dispatch])

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

        // ── 执行前端动作 ──
        const frontendActions = data.actions || []
        if (frontendActions.length > 0) {
          console.log('执行前端动作:', frontendActions)
          const executed = executeFrontendActions(frontendActions)
          
          // 在消息中追加动作执行结果
          const actionSummary = executed
            .filter(a => a.status === 'done')
            .map(a => `• ${a.description}`)
            .join('\n')
          
          if (actionSummary) {
            setMessages((prev) => [...prev, {
              role: 'system',
              content: `已自动执行以下操作：\n${actionSummary}`,
              source: 'action_summary'
            }])
          }
        }

        // 替换 working 消息为最终 assistant 消息
        setMessages((prev) => prev.filter(m => !m.agent_working))
        setMessages((prev) => [...prev, {
          role: 'assistant',
          content: data.chat_summary || data.final_answer || '任务执行完成',
          source: 'copilot',
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
      content: '已取消当前任务',
      source: 'error'
    }])
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
    setPendingActions([])
    setShowActionPanel(false)
    inputRef.current?.focus()
  }

  const isEmpty = messages.length === 0

  /* ── Agent 工作进度组件 ── */
  const AgentWorkingIndicator = () => {
    if (!agentWorking) return null

    const progress = agentProgress || { step: 0, total: 0, tool: '', status: 'planning' }

    return (
      <div className="flex gap-2.5">
        <div className="w-7 h-7 rounded-full flex items-center justify-center shrink-0 bg-slate-700 animate-pulse">
          <Brain className="w-3.5 h-3.5 text-white" />
        </div>
        <div className="flex-1 px-3.5 py-2.5 rounded-2xl bg-slate-50 border border-slate-200 rounded-tl-sm">
          <div className="flex items-center gap-2 mb-2">
            <Loader2 className="w-3.5 h-3.5 text-slate-500 animate-spin" />
            <span className="text-xs font-semibold text-slate-700">
              Agent 正在工作中...
            </span>
            <button
              onClick={handleCancelAgent}
              className="ml-auto flex items-center gap-1 text-[10px] px-2 py-0.5 bg-slate-100 text-slate-600 border border-slate-200 rounded hover:bg-slate-200 transition"
            >
              <StopCircle className="w-3 h-3" />
              取消
            </button>
          </div>

          {/* 进度条 */}
          <div className="w-full bg-slate-200 rounded-full h-1.5 mb-3">
            <div
              className="bg-slate-500 h-1.5 rounded-full transition-all duration-500"
              style={{ width: progress.total > 0 ? `${(progress.step / progress.total) * 100}%` : '10%' }}
            />
          </div>

          {/* 当前状态 */}
          <div className="text-[10px] text-slate-600 mb-2">
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
                    <CheckCircle2 className="w-3 h-3 text-slate-500" />
                  ) : s.status === 'error' ? (
                    <XCircle className="w-3 h-3 text-slate-400" />
                  ) : s.status === 'running' ? (
                    <Loader2 className="w-3 h-3 text-slate-400 animate-spin" />
                  ) : (
                    <CircleDot className="w-3 h-3 text-slate-300" />
                  )}
                  <span className={`${
                    s.status === 'ok' ? 'text-slate-700' :
                    s.status === 'error' ? 'text-slate-500' :
                    s.status === 'running' ? 'text-slate-600' :
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
      <div className="mt-2 p-3 bg-slate-50 border border-slate-200 rounded-lg">
        <div className="flex items-center gap-1.5 mb-1.5">
          <Sparkles className="w-3.5 h-3.5 text-slate-500" />
          <span className="text-[10px] font-semibold text-slate-700">执行报告</span>
          {report.success ? (
            <span className="text-[9px] px-1.5 py-0.5 bg-slate-100 text-slate-600 rounded">成功</span>
          ) : (
            <span className="text-[9px] px-1.5 py-0.5 bg-slate-100 text-slate-600 rounded">部分完成</span>
          )}
        </div>
        <p className="text-[10px] text-slate-800 leading-relaxed whitespace-pre-wrap">
          {report.final_answer}
        </p>
      </div>
    )
  }

  /* ── 前端动作执行面板 ── */
  const ActionSummaryPanel = ({ actions }) => {
    if (!actions || actions.length === 0) return null
    
    const actionIcons = {
      navigate: Navigation,
      set_state: Activity,
      set_filter: Filter,
      highlight: Eye,
      toast: Bell,
      refresh: RefreshCw,
      show_data: BarChart3,
      show_chart: BarChart3,
      open_modal: Maximize2,
      scroll_to: Navigation,
    }
    
    return (
      <div className="mt-2 p-3 bg-slate-50 border border-slate-200 rounded-lg">
        <div className="flex items-center gap-1.5 mb-2">
          <Zap className="w-3.5 h-3.5 text-slate-500" />
          <span className="text-[10px] font-semibold text-slate-700">已自动执行操作</span>
        </div>
        <div className="space-y-1">
          {actions.map((action, i) => {
            const Icon = actionIcons[action.type] || Zap
            const statusColors = {
              done: 'text-slate-700',
              error: 'text-slate-500',
              skipped: 'text-slate-400',
            }
            return (
              <div key={i} className="flex items-center gap-1.5 text-[10px]">
                <Icon className={`w-3 h-3 ${statusColors[action.status] || 'text-slate-500'}`} />
                <span className={statusColors[action.status] || 'text-slate-600'}>
                  {action.description}
                </span>
                {action.status === 'done' && (
                  <CheckCircle2 className="w-3 h-3 text-slate-500 ml-auto" />
                )}
                {action.status === 'error' && (
                  <XCircle className="w-3 h-3 text-slate-400 ml-auto" />
                )}
              </div>
            )
          })}
        </div>
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
      className={`fixed z-50 flex flex-col rounded-xl border border-slate-200 shadow-2xl overflow-hidden bg-white ${
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
            className="w-7 h-7 rounded-md hover:bg-slate-200 flex items-center justify-center text-slate-400 hover:text-slate-600 transition"
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
                  className="flex items-center justify-center gap-1.5 px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-xs text-slate-700 hover:bg-slate-100 transition"
                >
                  <Play className="w-3.5 h-3.5" />
                  运行 Pipeline
                </button>
                <button
                  onClick={() => handleSend('帮我分析失败分子')}
                  className="flex items-center justify-center gap-1.5 px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-xs text-slate-700 hover:bg-slate-100 transition"
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
                  className="flex items-center justify-center gap-1.5 px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-xs text-slate-700 hover:bg-slate-100 transition"
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
                        ? 'bg-slate-50 text-slate-700 border border-slate-100 rounded-tl-sm'
                        : 'bg-slate-50 text-slate-700 border border-slate-100 rounded-tl-sm'
                    }`}>
                      <div className="whitespace-pre-wrap">{msg.content}</div>
                      
                      {/* 内嵌表单 */}
                      {msg.type === 'form' && msg.form_type === 'create_project' && (
                        <ProjectCreationForm
                          onCreated={(newProject) => {
                            // 1. 更新全局状态
                            dispatch({ type: 'SET_PROJECT', payload: newProject })
                            // 2. 导航到项目列表
                            navigate('/projects')
                            // 3. 在聊天中追加成功消息
                            setMessages((prev) => [...prev, {
                              role: 'system',
                              content: `项目 "${newProject.name}" 创建成功。已设置为当前项目，并导航到项目列表。`,
                              source: 'action_summary',
                            }])
                            // 4. 追加建议下一步
                            setMessages((prev) => [...prev, {
                              role: 'assistant',
                              content: '项目已创建。建议下一步：运行 Pipeline 生成分子，或查看项目详情。',
                              source: 'copilot',
                            }])
                          }}
                          onAutoRun={(newProject) => {
                            // 1. 更新全局状态
                            dispatch({ type: 'SET_PROJECT', payload: newProject })
                            // 2. 在聊天中追加系统消息
                            setMessages((prev) => [...prev, {
                              role: 'system',
                              content: `项目 "${newProject.name}" 已创建，正在自动启动 Pipeline...`,
                              source: 'action_summary',
                            }])
                            // 3. 触发 Agent 自动执行：运行 Pipeline 并获取 Top 分子
                            handleSend(`为项目 ${newProject.id} 运行 Pipeline 并获取 Top 分子`)
                          }}
                        />
                      )}
                      
                      {/* 来源标签 */}
                      {msg.role === 'assistant' && msg.source === 'copilot' && (
                        <div className="mt-1.5 pt-1.5 border-t border-slate-200/60 flex items-center gap-1">
                          <span className="text-[9px] px-1.5 py-0.5 bg-slate-100 text-slate-600 rounded border border-slate-200 font-medium">
                            Copilot
                          </span>
                          <span className="text-[9px] text-slate-400">
                            {msg.type === 'autonomous' ? '自主执行' : 'Agent 执行'}
                          </span>
                        </div>
                      )}
                      {msg.role === 'assistant' && msg.source === 'rag' && (
                        <div className="mt-1.5 pt-1.5 border-t border-slate-200/60 flex items-center gap-1">
                          <span className="text-[9px] px-1.5 py-0.5 bg-slate-100 text-slate-600 rounded border border-slate-200 font-medium">
                            知识库
                          </span>
                        </div>
                      )}
                      {msg.role === 'assistant' && msg.source === 'ai' && (
                        <div className="mt-1.5 pt-1.5 border-t border-slate-200/60 flex items-center gap-1">
                          <span className="text-[9px] px-1.5 py-0.5 bg-slate-100 text-slate-600 rounded border border-slate-200 font-medium">
                            AI
                          </span>
                          <span className="text-[9px] text-slate-400">KIMI</span>
                        </div>
                      )}
                      {msg.role === 'system' && msg.source === 'action_summary' && (
                        <div className="mt-1.5 pt-1.5 border-t border-slate-200/60 flex items-center gap-1">
                          <span className="text-[9px] px-1.5 py-0.5 bg-slate-100 text-slate-600 rounded border border-slate-200 font-medium">
                            自动操作
                          </span>
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
                      
                      {/* 前端动作执行结果 */}
                      {msg.source === 'action_summary' && pendingActions.length > 0 && (
                        <ActionSummaryPanel actions={pendingActions} />
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
