import React, { useState, useEffect } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { Info, FlaskConical, Atom, Activity, GitBranch, Play, BarChart, Home, Menu, X, Target, TrendingUp, AlertTriangle, User, Sun, Moon, Settings, HelpCircle, Hexagon, Cpu } from 'lucide-react'
import { useApp } from '../store/AppContext'
import LoginModal from '../components/LoginModal'
import SettingsModal from '../components/SettingsModal'
import HelpChatModal from '../components/HelpChatModal'

const navItems = [
  { path: '/', icon: Home, label: '首页' },
  { path: '/projects', icon: FlaskConical, label: '项目列表' },
  { path: '/pipeline', icon: Play, label: 'Pipeline运行' },
  { path: '/agent-traces', icon: Cpu, label: 'Agent追踪' },
  { path: '/results', icon: BarChart, label: '结果分析' },
  { path: '/molecules', icon: Atom, label: '分子浏览器' },
  { path: '/builder', icon: Hexagon, label: '分子构建' },
  { path: '/docking', icon: Target, label: '分子对接' },
  { path: '/activity', icon: TrendingUp, label: '活性预测' },
  { path: '/admet', icon: Activity, label: 'ADMET分析' },
  { path: '/synthesis', icon: GitBranch, label: '合成分析' },
  { path: '/failed-molecules', icon: AlertTriangle, label: '失败分子库' },
  { path: '/about', icon: Info, label: '关于我们' },
]

export default function Layout({ children }) {
  const location = useLocation()
  const { state } = useApp()
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [showLogin, setShowLogin] = useState(false)
  const [showSettings, setShowSettings] = useState(false)
  const [showHelp, setShowHelp] = useState(false)
  const [isDark, setIsDark] = useState(() => {
    try {
      return localStorage.getItem('theme') === 'dark' ||
        (!localStorage.getItem('theme') && window.matchMedia('(prefers-color-scheme: dark)').matches)
    } catch { return false }
  })

  useEffect(() => {
    if (isDark) {
      document.documentElement.classList.add('dark')
      localStorage.setItem('theme', 'dark')
    } else {
      document.documentElement.classList.remove('dark')
      localStorage.setItem('theme', 'light')
    }
  }, [isDark])

  const toggleTheme = () => setIsDark(prev => !prev)

  return (
    <div className="min-h-screen bg-gray-50 flex">
      {/* 侧边栏 */}
      <aside
        className={`bg-slate-900 text-white transition-all duration-300 flex flex-col ${
          sidebarOpen ? 'w-64' : 'w-16'
        }`}
      >
        <div className="h-16 flex items-center justify-between px-4 border-b border-slate-700">
          {sidebarOpen && (
            <div className="flex items-center gap-2">
              <FlaskConical className="w-6 h-6 text-slate-400" />
              <span className="font-bold text-sm">DrugDesign</span>
            </div>
          )}
          <button onClick={() => setSidebarOpen(!sidebarOpen)} className="p-1 hover:bg-slate-700 rounded">
            {sidebarOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>
        </div>

        <nav className="flex-1 py-4 px-2 space-y-1">
          {navItems.map((item) => {
            const isActive = location.pathname === item.path ||
              (item.path !== '/' && location.pathname.startsWith(item.path))
            const Icon = item.icon
            return (
              <Link
                key={item.path}
                to={item.path}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors ${
                  isActive
                    ? 'bg-slate-700 text-white'
                    : 'text-slate-300 hover:bg-slate-800 hover:text-white'
                }`}
                title={item.label}
              >
                <Icon className="w-5 h-5 flex-shrink-0" />
                {sidebarOpen && <span className="text-sm font-medium">{item.label}</span>}
              </Link>
            )
          })}
        </nav>

        {sidebarOpen && state.currentProject && (
          <div className="px-4 py-3 border-t border-slate-700">
            <div className="text-xs text-slate-400">当前项目</div>
            <div className="text-sm font-medium text-white truncate">{state.currentProject.name}</div>
            <div className="text-xs text-slate-500">{state.currentProject.target_name}</div>
          </div>
        )}
      </aside>

      {/* 主内容 */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* 顶部栏 */}
        {location.pathname !== '/' && (
        <header className="h-16 bg-white border-b border-gray-200 flex items-center justify-between px-6">
          <h1 className="text-lg font-semibold text-gray-800">小分子药物设计Agent</h1>
          <div className="flex items-center gap-3">
            {/* 帮助按钮 */}
            <button
              onClick={() => setShowHelp(true)}
              className="w-8 h-8 rounded-full bg-slate-100 flex items-center justify-center hover:bg-slate-200 transition text-slate-600"
              title="AI 助手"
            >
              <HelpCircle className="w-4 h-4" />
            </button>
            {/* 设置按钮 */}
            <button
              onClick={() => setShowSettings(true)}
              className="w-8 h-8 rounded-full bg-slate-100 flex items-center justify-center hover:bg-slate-200 transition text-slate-600"
              title="设置"
            >
              <Settings className="w-4 h-4" />
            </button>
            {/* 登录按钮 */}
            <button
              onClick={() => setShowLogin(true)}
              className="w-8 h-8 rounded-full bg-slate-100 flex items-center justify-center hover:bg-slate-200 transition text-xs font-bold text-slate-600"
              title="登录"
            >
              <User className="w-4 h-4" />
            </button>
            {/* 状态标签 */}
            <div className="flex items-center gap-1 bg-slate-100 rounded-lg p-1">
              {[
                { key: 'completed', label: '已完成' },
                { key: 'running', label: '运行中' },
                { key: 'pending', label: '准备中' },
              ].map((tab) => {
                const current = state.pipelineStatus || 'pending'
                const isActive = current === tab.key
                return (
                  <button
                    key={tab.key}
                    className={`px-3 py-1.5 text-xs rounded-md font-medium transition ${
                      isActive
                        ? 'bg-slate-800 text-white'
                        : 'text-slate-500 hover:text-slate-700'
                    }`}
                  >
                    {tab.label}
                  </button>
                )
              })}
            </div>
          </div>
        </header>
        )}

        {/* 登录弹窗 */}
        {showLogin && <LoginModal onClose={() => setShowLogin(false)} />}

        {/* 设置弹窗 */}
        {showSettings && <SettingsModal onClose={() => setShowSettings(false)} isDark={isDark} onToggleTheme={toggleTheme} />}

        {/* AI帮助弹窗 */}
        {showHelp && <HelpChatModal onClose={() => setShowHelp(false)} projectId={state.currentProject?.id} />}

        {/* 内容区 */}
        <main className="flex-1 p-6 overflow-auto flex flex-col">
          {children}
        </main>
      </div>
    </div>
  )
}
