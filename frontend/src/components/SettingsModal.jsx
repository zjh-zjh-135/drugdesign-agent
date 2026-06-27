import React, { useState } from 'react'
import {
  User, Palette, Bell, Database, Download, Info, ChevronRight, Search, X,
  Settings, FileText, Moon, Sun, Monitor, ExternalLink, Trash2
} from 'lucide-react'

const settingCategories = [
  { key: 'profile', label: '个人资料', icon: User },
  { key: 'appearance', label: '外观', icon: Palette },
  { key: 'models', label: '模型偏好', icon: Database },
  { key: 'notifications', label: '通知', icon: Bell },
  { key: 'download', label: '下载', icon: Download },
  { key: 'about', label: '关于', icon: Info },
]

export default function SettingsModal({ onClose, isDark, onToggleTheme }) {
  const [activeCategory, setActiveCategory] = useState('profile')
  const [searchQuery, setSearchQuery] = useState('')
  const [showProfileEditor, setShowProfileEditor] = useState(false)
  const [email, setEmail] = useState('')

  const renderContent = () => {
    switch (activeCategory) {
      case 'profile':
        return (
          <>
            {/* 个人资料卡片 */}
            <div className="bg-white border border-slate-200 rounded-lg p-5 mb-6">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div className="w-14 h-14 rounded-full bg-slate-100 flex items-center justify-center text-slate-400">
                    <User className="w-6 h-6" />
                  </div>
                  <div>
                    <div className="text-base font-semibold text-slate-800">个人</div>
                    <div className="text-sm text-slate-500 mt-0.5">未登录</div>
                    <div className="text-xs text-emerald-600 mt-1 font-medium">● 已启用同步</div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setShowProfileEditor(true)}
                    className="w-8 h-8 rounded-lg border border-slate-200 flex items-center justify-center hover:bg-slate-50 text-slate-400 hover:text-slate-600 transition"
                  >
                    <ExternalLink className="w-4 h-4" />
                  </button>
                  <button className="w-8 h-8 rounded-lg border border-slate-200 flex items-center justify-center hover:bg-slate-50 text-slate-400 hover:text-slate-600 transition">
                    <Trash2 className="w-4 h-4" />
                  </button>
                  <button className="px-3 h-8 rounded-lg border border-slate-200 text-sm font-medium text-slate-600 hover:bg-slate-50 transition">
                    退出登录
                  </button>
                </div>
              </div>

              {showProfileEditor && (
                <div className="mt-4 pt-4 border-t border-slate-100">
                  <div className="flex items-center gap-3">
                    <input
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="输入邮箱地址"
                      className="flex-1 h-10 px-4 border border-slate-200 rounded-lg text-sm focus:outline-none focus:border-slate-400 transition"
                    />
                    <button className="h-10 px-4 bg-slate-800 text-white rounded-lg text-sm font-medium hover:bg-slate-900 transition">
                      保存
                    </button>
                    <button
                      onClick={() => setShowProfileEditor(false)}
                      className="h-10 px-4 border border-slate-200 rounded-lg text-sm text-slate-600 hover:bg-slate-50 transition"
                    >
                      取消
                    </button>
                  </div>
                </div>
              )}
            </div>

            <div className="text-base font-semibold text-slate-800 mb-3">个人资料设置</div>
            <p className="text-sm text-slate-500 mb-4">这些设置适用于你在 DrugDesign 中的配置文件</p>

            <div className="bg-white border border-slate-200 rounded-lg overflow-hidden divide-y divide-slate-100">
              {[
                { icon: Database, label: '数据同步', desc: '自动同步项目数据到云端' },
                { icon: FileText, label: '实验记录', desc: '管理你的实验记录本' },
                { icon: Download, label: '导出偏好', desc: '默认导出格式和路径' },
                { icon: Bell, label: '消息通知', desc: '邮件和应用内通知设置' },
                { icon: Palette, label: '界面偏好', desc: '字体大小、缩放比例' },
                { icon: Monitor, label: '工作区', desc: '多显示器和窗口布局' },
              ].map((item) => (
                <button key={item.label} className="w-full flex items-center gap-4 px-5 py-4 hover:bg-slate-50 transition text-left">
                  <item.icon className="w-5 h-5 text-slate-500" />
                  <div className="flex-1">
                    <div className="text-sm font-medium text-slate-700">{item.label}</div>
                    <div className="text-xs text-slate-400 mt-0.5">{item.desc}</div>
                  </div>
                  <ChevronRight className="w-4 h-4 text-slate-400" />
                </button>
              ))}
            </div>
          </>
        )

      case 'appearance':
        return (
          <>
            <div className="text-base font-semibold text-slate-800 mb-4">外观</div>
            <div className="bg-white border border-slate-200 rounded-lg p-5 mb-5">
              <div className="text-sm font-medium text-slate-700 mb-3">主题</div>
              <div className="flex gap-3">
                {[
                  { key: 'light', label: '亮色', icon: Sun },
                  { key: 'dark', label: '暗色', icon: Moon },
                  { key: 'auto', label: '自动', icon: Monitor },
                ].map((theme) => (
                  <button
                    key={theme.key}
                    onClick={() => {
                      if (theme.key === 'light' && isDark) onToggleTheme()
                      if (theme.key === 'dark' && !isDark) onToggleTheme()
                    }}
                    className={`flex-1 flex items-center gap-2 px-4 py-2.5 rounded-lg border text-sm font-medium transition ${
                      (theme.key === 'dark' && isDark) || (theme.key === 'light' && !isDark) || (theme.key === 'auto')
                        ? 'border-slate-800 bg-slate-50 text-slate-800'
                        : 'border-slate-200 text-slate-600 hover:bg-slate-50'
                    }`}
                  >
                    <theme.icon className="w-4 h-4" />
                    {theme.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="bg-white border border-slate-200 rounded-lg p-5 mb-5">
              <div className="text-sm font-medium text-slate-700 mb-3">界面密度</div>
              <div className="flex gap-3">
                {['紧凑', '标准', '舒适'].map((d) => (
                  <button
                    key={d}
                    className={`flex-1 px-4 py-2.5 rounded-lg border text-sm font-medium transition ${
                      d === '标准' ? 'border-slate-800 bg-slate-50 text-slate-800' : 'border-slate-200 text-slate-600 hover:bg-slate-50'
                    }`}
                  >
                    {d}
                  </button>
                ))}
              </div>
            </div>
          </>
        )

      case 'models':
        return (
          <>
            <div className="text-base font-semibold text-slate-800 mb-4">模型偏好</div>
            <div className="bg-white border border-slate-200 rounded-lg overflow-hidden divide-y divide-slate-100">
              {[
                { label: 'ADMET 预测模型', value: 'ADMET-AI v2.1', desc: '药代动力学与毒性评估' },
                { label: '活性预测模型', value: 'DeepAffinity', desc: '基于图神经网络的亲和力预测' },
                { label: '分子生成模型', value: 'CReM + RNN', desc: '片段替换 + 递归神经网络' },
                { label: '对接引擎', value: 'AutoDock Vina', desc: '分子对接与评分' },
              ].map((item) => (
                <div key={item.label} className="flex items-center justify-between px-5 py-4">
                  <div>
                    <div className="text-sm font-medium text-slate-700">{item.label}</div>
                    <div className="text-xs text-slate-400 mt-0.5">{item.desc}</div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-slate-600">{item.value}</span>
                    <ChevronRight className="w-4 h-4 text-slate-400" />
                  </div>
                </div>
              ))}
            </div>
          </>
        )

      case 'notifications':
        return (
          <>
            <div className="text-base font-semibold text-slate-800 mb-4">通知设置</div>
            <div className="bg-white border border-slate-200 rounded-lg overflow-hidden divide-y divide-slate-100">
              {[
                { label: 'Pipeline 完成通知', desc: 'Pipeline 运行结束后推送通知' },
                { label: '分子筛选结果', desc: '筛选完成时通知' },
                { label: 'ADMET 分析完成', desc: 'ADMET 分析结束后通知' },
                { label: '系统公告', desc: '平台更新和维护通知' },
              ].map((item) => (
                <div key={item.label} className="flex items-center justify-between px-5 py-4">
                  <div>
                    <div className="text-sm font-medium text-slate-700">{item.label}</div>
                    <div className="text-xs text-slate-400 mt-0.5">{item.desc}</div>
                  </div>
                  <div className="w-10 h-6 bg-slate-800 rounded-full relative cursor-pointer">
                    <div className="absolute right-0.5 top-0.5 w-5 h-5 bg-white rounded-full shadow-sm" />
                  </div>
                </div>
              ))}
            </div>
          </>
        )

      case 'download':
        return (
          <>
            <div className="text-base font-semibold text-slate-800 mb-4">下载设置</div>
            <div className="bg-white border border-slate-200 rounded-lg overflow-hidden divide-y divide-slate-100">
              {[
                { label: '默认导出格式', value: 'CSV + SDF', desc: '项目数据和分子结构' },
                { label: '下载路径', value: 'C:\\Downloads\\DrugDesign', desc: '分子文件保存位置' },
                { label: '自动保存', value: '开启', desc: 'Pipeline 结果自动导出' },
              ].map((item) => (
                <div key={item.label} className="flex items-center justify-between px-5 py-4">
                  <div>
                    <div className="text-sm font-medium text-slate-700">{item.label}</div>
                    <div className="text-xs text-slate-400 mt-0.5">{item.desc}</div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-slate-600">{item.value}</span>
                    <ChevronRight className="w-4 h-4 text-slate-400" />
                  </div>
                </div>
              ))}
            </div>
          </>
        )

      case 'about':
        return (
          <>
            <div className="text-base font-semibold text-slate-800 mb-4">关于 DrugDesign</div>
            <div className="bg-white border border-slate-200 rounded-lg p-6">
              <div className="flex items-center gap-4 mb-4">
                <div className="w-12 h-12 rounded-lg bg-slate-900 flex items-center justify-center">
                  <Settings className="w-6 h-6 text-white" />
                </div>
                <div>
                  <div className="text-lg font-semibold text-slate-800">DrugDesign Agent</div>
                  <div className="text-sm text-slate-400">v1.0.0</div>
                </div>
              </div>
              <div className="text-sm text-slate-600 space-y-2">
                <p>基于人工智能的端到端小分子药物设计平台。</p>
                <p>从分子生成到药物优化，加速新药发现全流程。</p>
              </div>
              <div className="mt-4 pt-4 border-t border-slate-100 flex items-center gap-2 text-xs text-slate-400">
                <span>© 2025 DrugDesign</span>
                <span>·</span>
                <span>隐私政策</span>
                <span>·</span>
                <span>使用条款</span>
              </div>
            </div>
          </>
        )

      default:
        return null
    }
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex z-50" onClick={onClose}>
      <div className="bg-white w-full h-full flex overflow-hidden" onClick={(e) => e.stopPropagation()}>
        {/* 左侧边栏 */}
        <div className="w-64 bg-white border-r border-slate-200 flex flex-col shrink-0">
          <div className="h-16 flex items-center px-6 border-b border-slate-100">
            <h2 className="text-lg font-bold text-slate-800">设置</h2>
          </div>

          <div className="flex-1 py-3 px-2 space-y-0.5 overflow-auto">
            {settingCategories.map((cat) => {
              const Icon = cat.icon
              const isActive = activeCategory === cat.key
              return (
                <button
                  key={cat.key}
                  onClick={() => setActiveCategory(cat.key)}
                  className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition text-left ${
                    isActive
                      ? 'bg-slate-100 text-slate-800'
                      : 'text-slate-600 hover:bg-slate-50'
                  }`}
                >
                  <Icon className={`w-4.5 h-4.5 ${isActive ? 'text-slate-800' : 'text-slate-400'}`} />
                  {cat.label}
                </button>
              )
            })}
          </div>
        </div>

        {/* 右侧内容区 */}
        <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
          {/* 顶部搜索栏 */}
          <div className="h-16 flex items-center justify-between px-6 border-b border-slate-100 shrink-0">
            <div className="relative flex-1 max-w-md">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="搜索设置"
                className="w-full h-9 pl-9 pr-4 bg-slate-100 border border-transparent rounded-lg text-sm text-slate-700 placeholder:text-slate-400 focus:outline-none focus:bg-white focus:border-slate-300 transition"
              />
            </div>
            <button
              onClick={onClose}
              className="ml-4 w-8 h-8 flex items-center justify-center rounded-lg hover:bg-slate-100 text-slate-400 hover:text-slate-600 transition"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* 滚动内容 */}
          <div className="flex-1 overflow-auto p-6">
            {searchQuery ? (
              <div className="text-sm text-slate-400">搜索结果将显示在这里...</div>
            ) : (
              renderContent()
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
