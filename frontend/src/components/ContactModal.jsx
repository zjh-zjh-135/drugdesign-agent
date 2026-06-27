import React, { useState, useEffect } from 'react'
import { X, Phone, Hash, Mail } from 'lucide-react'

const teamMembers = [
  {
    name: '赵俊豪',
    studentId: '202321156110',
    phone: '19822681985',
  },
  {
    name: '向常皓',
    studentId: '202327156104',
    phone: '19705169380',
  },
]

export default function ContactModal({ onClose }) {
  const [showAnimation, setShowAnimation] = useState(true)

  useEffect(() => {
    const timer = setTimeout(() => {
      setShowAnimation(false)
    }, 5200)
    return () => clearTimeout(timer)
  }, [])

  const skipAnimation = (e) => {
    e.stopPropagation()
    setShowAnimation(false)
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={onClose}>
      <div
        className="bg-[#faf8f5] rounded-xl w-full max-w-[500px] overflow-hidden shadow-2xl relative"
        onClick={(e) => e.stopPropagation()}
      >
        <style>{`
          @keyframes ringStroke {
            to { stroke-dashoffset: 0; }
          }
          @keyframes logoGrow {
            0% { opacity: 0; transform: scale(0) rotate(-15deg); filter: blur(8px); }
            55% { opacity: 1; transform: scale(1.1) rotate(3deg); filter: blur(1px); }
            75% { transform: scale(0.96) rotate(-1deg); filter: blur(0); }
            100% { opacity: 1; transform: scale(1) rotate(0deg); filter: blur(0); }
          }
          @keyframes textSlideIn {
            0% { opacity: 0; transform: translateY(18px); letter-spacing: 0.18em; }
            100% { opacity: 1; transform: translateY(0); letter-spacing: 0.06em; }
          }
          @keyframes introFadeOut {
            to { opacity: 0; visibility: hidden; }
          }
          @keyframes contentFadeIn {
            from { opacity: 0; transform: translateY(15px); }
            to { opacity: 1; transform: translateY(0); }
          }
          @keyframes ringSpin {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
          }
        `}</style>

        {/* ═══════ 开场动画层 ═══════ */}
        {showAnimation && (
          <div
            className="absolute inset-0 z-30 bg-[#faf8f5] flex flex-col items-center justify-center"
            style={{ animation: 'introFadeOut 0.6s ease 4.6s forwards' }}
          >
            {/* 跳过按钮 */}
            <button
              onClick={skipAnimation}
              className="absolute top-4 right-4 text-xs text-slate-400 hover:text-slate-600 transition z-40 px-2 py-1 rounded hover:bg-slate-100"
            >
              跳过
            </button>

            {/* SVG 装饰双圆环 — 描边绘制 + 旋转 */}
            <div className="absolute" style={{ width: 220, height: 220 }}>
              <svg
                width="220"
                height="220"
                viewBox="0 0 220 220"
                style={{ animation: 'ringSpin 8s linear infinite' }}
              >
                <circle
                  cx="110"
                  cy="110"
                  r="95"
                  fill="none"
                  stroke="#d4c5b0"
                  strokeWidth="1"
                  strokeDasharray="596"
                  strokeDashoffset="596"
                  opacity="0.6"
                  style={{ animation: 'ringStroke 1.4s ease-out 0.4s forwards' }}
                />
                <circle
                  cx="110"
                  cy="110"
                  r="82"
                  fill="none"
                  stroke="#c4b5a0"
                  strokeWidth="0.8"
                  strokeDasharray="515"
                  strokeDashoffset="515"
                  opacity="0.4"
                  style={{ animation: 'ringStroke 1.2s ease-out 0.7s forwards' }}
                />
              </svg>
            </div>

            {/* 校徽 — 几何生长动画 */}
            <div
              style={{
                animation: 'logoGrow 1.3s cubic-bezier(0.34, 1.56, 0.64, 1) 0.2s forwards',
                opacity: 0,
              }}
            >
              <img
                src="/njtech-logo.png"
                alt="南京工业大学"
                className="w-28 h-28 object-contain"
                style={{ filter: 'drop-shadow(0 6px 12px rgba(0,0,0,0.12))' }}
              />
            </div>

            {/* NJTECH UNIVERSITY 文字 */}
            <div
              className="mt-7 text-center"
              style={{
                animation: 'textSlideIn 0.9s ease-out 2.0s forwards',
                opacity: 0,
              }}
            >
              <div className="text-[15px] font-bold text-slate-600 tracking-wide">
                NJTECH UNIVERSITY
              </div>
              <div
                className="mt-2 text-xs text-slate-400"
                style={{
                  animation: 'textSlideIn 0.7s ease-out 2.4s forwards',
                  opacity: 0,
                }}
              >
                南京工业大学
              </div>
            </div>
          </div>
        )}

        {/* ═══════ 关闭按钮（动画结束后可点） ═══════ */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 w-8 h-8 rounded-full bg-slate-100 flex items-center justify-center hover:bg-slate-200 transition text-slate-500 z-20"
        >
          <X className="w-4 h-4" />
        </button>

        {/* ═══════ 名片内容 ═══════ */}
        <div
          className="p-8 pt-10 space-y-6"
          style={showAnimation ? { opacity: 0 } : { animation: 'contentFadeIn 0.6s ease forwards' }}
        >
          {/* 标题 */}
          <div className="text-center mb-2">
            <h2 className="text-lg font-bold text-slate-800">开发团队</h2>
            <p className="text-xs text-slate-400 mt-1">DrugDesign Agent</p>
          </div>

          {/* 名片卡片 */}
          {teamMembers.map((member) => (
            <div
              key={member.studentId}
              className="border border-slate-200/60 rounded-xl p-6 hover:shadow-md transition relative overflow-hidden"
              style={{ background: 'linear-gradient(135deg, #fcfbf9 0%, #f5f2ec 100%)' }}
            >
              {/* 装饰弧线 — 左上 */}
              <div className="absolute -top-6 -left-8 w-28 h-28 rounded-full border border-[#d4c5b0]/30 pointer-events-none" />
              <div className="absolute -top-4 -left-6 w-20 h-20 rounded-full border border-[#d4c5b0]/20 pointer-events-none" />
              {/* 装饰弧线 — 右下 */}
              <div className="absolute -bottom-10 -right-10 w-36 h-36 rounded-full border border-[#d4c5b0]/25 pointer-events-none" />
              <div className="absolute -bottom-6 -right-6 w-24 h-24 rounded-full border border-[#d4c5b0]/15 pointer-events-none" />

              {/* 右上角校徽 */}
              <div className="absolute top-4 right-4">
                <img
                  src="/njtech-logo.png"
                  alt="南京工业大学"
                  className="w-14 h-14 object-contain opacity-90"
                />
              </div>

              <div className="pr-16 relative z-10">
                {/* 姓名 */}
                <div className="text-2xl font-bold text-emerald-600 mb-1">
                  {member.name}
                </div>
                <div className="text-xs text-slate-400 mb-5">
                  DrugDesign Agent 开发成员
                </div>

                {/* 联系信息 */}
                <div className="space-y-3">
                  <div className="flex items-center gap-3">
                    <div className="w-6 h-6 rounded bg-slate-100/80 flex items-center justify-center shrink-0">
                      <Hash className="w-3 h-3 text-slate-500" />
                    </div>
                    <div className="text-sm text-slate-600">
                      <span className="text-xs text-slate-400 mr-2">学号</span>
                      {member.studentId}
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="w-6 h-6 rounded bg-slate-100/80 flex items-center justify-center shrink-0">
                      <Phone className="w-3 h-3 text-slate-500" />
                    </div>
                    <div className="text-sm text-slate-600">
                      <span className="text-xs text-slate-400 mr-2">电话</span>
                      {member.phone}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          ))}

          {/* 底部项目联系 */}
          <div className="border-t border-slate-200/50 pt-5">
            <div className="flex items-center justify-center gap-2 text-sm text-slate-500">
              <Mail className="w-4 h-4 text-slate-400" />
              <span className="text-slate-400 text-xs mr-1">项目联系</span>
              <span className="text-slate-700 font-medium">taizh52@163.com</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
