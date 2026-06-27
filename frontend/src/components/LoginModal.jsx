import React, { useState } from 'react'
import LoginCreatures from './LoginCreatures'

export default function LoginModal({ onClose }) {
  const [mode, setMode] = useState('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')
  const [loading, setLoading] = useState(false)
  const [pwdFocus, setPwdFocus] = useState(false)
  const [emailFocus, setEmailFocus] = useState(false)
  const [isSad, setIsSad] = useState(false)

  const handleSubmit = (e) => {
    e.preventDefault()
    setLoading(true)
    setIsSad(false)
    setTimeout(() => {
      setLoading(false)
      // 模拟登录失败 → 小生物悲伤
      setIsSad(true)
      setTimeout(() => {
        alert('登录功能暂未开放，敬请期待')
        setIsSad(false)
        onClose()
      }, 1200)
    }, 800)
  }

  return (
    <div className="fixed inset-0 bg-slate-900/50 flex items-center justify-center z-50 backdrop-blur-sm" onClick={onClose}>
      {/* 主卡片：左右分栏 */}
      <div
        className="bg-white rounded-2xl shadow-2xl w-full max-w-[760px] flex overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* 左侧：小生物区域 */}
        <div className="hidden sm:flex w-[380px] bg-slate-100 relative items-end justify-center overflow-hidden"
          style={{ minHeight: 460 }}
        >
          <LoginCreatures
            isPasswordFocused={pwdFocus}
            isEmailFocused={emailFocus}
            isSad={isSad}
            className="w-[340px] h-[260px] mb-16"
          />
        </div>

        {/* 右侧：表单区域 */}
        <div className="flex-1 p-8">
          <form onSubmit={handleSubmit} className="space-y-4">
            {mode === 'register' && (
              <div>
                <label className="text-xs font-medium text-slate-600 block mb-1.5">用户名</label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="您的用户名"
                  className="w-full border border-slate-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:border-slate-400 focus:ring-1 focus:ring-slate-200 transition"
                  required
                />
              </div>
            )}

            <div>
              <label className="text-xs font-medium text-slate-600 block mb-1.5">邮箱</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                onFocus={() => setEmailFocus(true)}
                onBlur={() => setEmailFocus(false)}
                placeholder="name@example.com"
                className="w-full border border-slate-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:border-slate-400 focus:ring-1 focus:ring-slate-200 transition"
                required
              />
            </div>

            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="text-xs font-medium text-slate-600">密码</label>
                {mode === 'login' && (
                  <button type="button" className="text-xs text-slate-400 hover:text-slate-600 transition">
                    忘记密码？
                  </button>
                )}
              </div>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                onFocus={() => setPwdFocus(true)}
                onBlur={() => setPwdFocus(false)}
                placeholder="••••••••"
                className="w-full border border-slate-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:border-slate-400 focus:ring-1 focus:ring-slate-200 transition"
                required
              />
            </div>

            {mode === 'login' && (
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="remember"
                  className="w-3.5 h-3.5 rounded border-slate-300 text-slate-800 focus:ring-slate-200"
                />
                <label htmlFor="remember" className="text-xs text-slate-500">30天内自动登录</label>
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-slate-900 text-white py-2.5 rounded-lg text-sm font-medium hover:bg-slate-800 disabled:opacity-50 transition"
            >
              {loading ? '请稍候...' : mode === 'login' ? '登录' : '注册'}
            </button>
          </form>

          {/* or 分隔 */}
          <div className="flex items-center gap-3 my-5">
            <div className="flex-1 h-px bg-slate-100" />
            <span className="text-[10px] text-slate-400 uppercase tracking-wider">或</span>
            <div className="flex-1 h-px bg-slate-100" />
          </div>

          {/* 社交登录 */}
          <div className="space-y-2">
            <button className="w-full flex items-center justify-center gap-2 border border-slate-200 rounded-lg py-2 text-sm text-slate-600 hover:bg-slate-50 transition">
              <svg className="w-4 h-4" viewBox="0 0 24 24">
                <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
                <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
                <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
                <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
              </svg>
              Google 登录
            </button>
          </div>

          {/* 切换模式 */}
          <div className="text-center mt-5 text-xs text-slate-400">
            {mode === 'login' ? (
              <span>
                还没有账户？{' '}
                <button onClick={() => { setMode('register'); setIsSad(false) }} className="text-slate-700 font-medium hover:underline">
                  注册
                </button>
              </span>
            ) : (
              <span>
                已有账户？{' '}
                <button onClick={() => { setMode('login'); setIsSad(false) }} className="text-slate-700 font-medium hover:underline">
                  登录
                </button>
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
