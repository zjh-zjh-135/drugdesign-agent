import React, { useState } from 'react'
import { X, Heart, ArrowLeft } from 'lucide-react'

const AMOUNT_OPTIONS = [
  { label: '5元', value: 5 },
  { label: '10元', value: 10 },
  { label: '20元', value: 20 },
  { label: '50元', value: 50 },
  { label: '100元', value: 100 },
  { label: '200元', value: 200 },
  { label: '500元', value: 500 },
  { label: '自定义', value: null },
]

export default function SponsorModal({ onClose }) {
  const [selectedAmount, setSelectedAmount] = useState(5)
  const [customAmount, setCustomAmount] = useState('')
  const [isCustom, setIsCustom] = useState(false)
  const [paymentMethod, setPaymentMethod] = useState('alipay')
  const [agreed, setAgreed] = useState(false)
  const [showQR, setShowQR] = useState(false)

  const handleAmountClick = (item) => {
    if (item.value === null) {
      setIsCustom(true)
      setSelectedAmount(null)
    } else {
      setIsCustom(false)
      setSelectedAmount(item.value)
    }
  }

  const handleConfirm = () => {
    const finalAmount = isCustom ? parseFloat(customAmount) || 0 : selectedAmount
    if (!finalAmount || finalAmount <= 0) return
    if (!agreed) return
    setShowQR(true)
  }

  const finalAmount = isCustom ? parseFloat(customAmount) || 0 : selectedAmount

  const qrImage = paymentMethod === 'alipay' ? '/alipay-qr.jpg' : '/wechat-qr.png'
  const methodName = paymentMethod === 'alipay' ? '支付宝' : '微信'
  const methodColor = paymentMethod === 'alipay' ? 'text-blue-600' : 'text-emerald-600'

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={onClose}>
      <div
        className="bg-white rounded-xl w-full max-w-[420px] shadow-2xl relative overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* 关闭按钮 */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 w-8 h-8 rounded-full bg-slate-100 flex items-center justify-center hover:bg-slate-200 transition text-slate-500 z-10"
        >
          <X className="w-4 h-4" />
        </button>

        {!showQR ? (
          /* ═══════ 金额选择界面 ═══════ */
          <div className="p-6">
            {/* 标题 */}
            <div className="mb-6">
              <h2 className="text-lg font-bold text-slate-800">赞助支持</h2>
              <p className="text-xs text-slate-400 mt-1">您的支持是我们持续开发的动力</p>
            </div>

            {/* 金额选择 */}
            <div className="mb-5">
              <label className="text-sm text-slate-600 mb-3 block">支付金额：</label>
              <div className="grid grid-cols-4 gap-3">
                {AMOUNT_OPTIONS.map((item) => {
                  const isSelected = !isCustom && selectedAmount === item.value
                  return (
                    <button
                      key={item.label}
                      onClick={() => handleAmountClick(item)}
                      className={`py-2.5 rounded-lg text-sm font-medium border transition ${
                        isSelected
                          ? 'bg-slate-700 text-white border-slate-700'
                          : 'bg-white text-slate-700 border-slate-200 hover:border-slate-400'
                      }`}
                    >
                      {item.label}
                    </button>
                  )
                })}
              </div>

              {/* 自定义金额输入 */}
              {isCustom && (
                <div className="mt-3">
                  <input
                    type="number"
                    value={customAmount}
                    onChange={(e) => setCustomAmount(e.target.value)}
                    placeholder="请输入金额"
                    className="w-full border border-slate-200 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:border-slate-400"
                    min="1"
                    step="1"
                  />
                </div>
              )}
            </div>

            {/* 支付方式 */}
            <div className="mb-5">
              <label className="text-sm text-slate-600 mb-3 block">支付方式：</label>
              <div className="flex gap-3">
                <button
                  onClick={() => setPaymentMethod('alipay')}
                  className={`flex items-center gap-2 px-4 py-2.5 rounded-lg border text-sm transition ${
                    paymentMethod === 'alipay'
                      ? 'bg-slate-50 border-slate-700 text-slate-800'
                      : 'bg-white border-slate-200 text-slate-600 hover:border-slate-400'
                  }`}
                >
                  <img src="/alipay-icon.png" alt="支付宝" className="w-6 h-6 object-contain shrink-0" />
                  支付宝
                </button>
                <button
                  onClick={() => setPaymentMethod('wechat')}
                  className={`flex items-center gap-2 px-4 py-2.5 rounded-lg border text-sm transition ${
                    paymentMethod === 'wechat'
                      ? 'bg-slate-50 border-slate-700 text-slate-800'
                      : 'bg-white border-slate-200 text-slate-600 hover:border-slate-400'
                  }`}
                >
                  <img src="/wechat-icon.png" alt="微信" className="w-6 h-6 object-contain shrink-0" />
                  微信
                </button>
              </div>
            </div>

            {/* 温馨提示 */}
            <div className="bg-amber-50 border border-amber-100 rounded-lg p-3 mb-5">
              <div className="flex items-start gap-2 text-sm text-amber-700">
                <Heart className="w-4 h-4 shrink-0 mt-0.5" />
                <span className="text-xs leading-relaxed">
                  赞助资金将全部用于 DrugDesign Agent 平台的持续开发与维护，感谢您的每一份支持。
                </span>
              </div>
            </div>

            {/* 确认支付 */}
            <button
              onClick={handleConfirm}
              disabled={!agreed || (isCustom && (!customAmount || parseFloat(customAmount) <= 0))}
              className={`w-full py-3 rounded-lg text-sm font-medium transition ${
                agreed && (!isCustom || (customAmount && parseFloat(customAmount) > 0))
                  ? 'bg-slate-700 text-white hover:bg-slate-800'
                  : 'bg-slate-200 text-slate-400 cursor-not-allowed'
              }`}
            >
              确认支付
            </button>

            {/* 协议勾选 */}
            <div className="mt-4 flex items-center gap-2">
              <input
                type="checkbox"
                id="agree-sponsor"
                checked={agreed}
                onChange={(e) => setAgreed(e.target.checked)}
                className="w-4 h-4 rounded border-slate-300 text-slate-700 focus:ring-slate-500"
              />
              <label htmlFor="agree-sponsor" className="text-xs text-slate-500 cursor-pointer">
                已阅读同意
                <span className="text-slate-700 hover:underline ml-1 cursor-pointer">《赞助协议》</span>
              </label>
            </div>
          </div>
        ) : (
          /* ═══════ 二维码展示界面 ═══════ */
          <div className="p-6 text-center">
            {/* 返回按钮 */}
            <button
              onClick={() => setShowQR(false)}
              className="absolute top-4 left-4 w-8 h-8 rounded-full bg-slate-100 flex items-center justify-center hover:bg-slate-200 transition text-slate-500 z-10"
            >
              <ArrowLeft className="w-4 h-4" />
            </button>

            {/* 标题 */}
            <div className="mb-5 mt-1">
              <h2 className="text-lg font-bold text-slate-800">
                <span className={methodColor}>{methodName}</span> 扫码支付
              </h2>
              <p className="text-xs text-slate-400 mt-1">
                赞助金额：<span className="font-bold text-slate-700 text-sm">¥{finalAmount}</span>
              </p>
            </div>

            {/* 二维码图片 */}
            <div className="flex justify-center mb-4">
              <div className="p-3 bg-white border border-slate-200 rounded-xl shadow-sm">
                <img
                  src={qrImage}
                  alt={`${methodName}付款码`}
                  className="w-[220px] h-[220px] object-contain"
                />
              </div>
            </div>

            {/* 提示文字 */}
            <div className="text-sm text-slate-500 space-y-1 mb-4">
              <p>请使用{methodName}扫描上方二维码完成支付</p>
              <p className="text-xs text-slate-400">支付完成后请耐心等待，无需重复操作</p>
            </div>

            {/* 已完成支付按钮 */}
            <button
              onClick={onClose}
              className="w-full py-2.5 rounded-lg text-sm font-medium bg-slate-700 text-white hover:bg-slate-800 transition"
            >
              已完成支付
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
