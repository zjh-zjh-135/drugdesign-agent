import React, { useState } from 'react'
import {
  FlaskConical, Atom, Activity, Target, TrendingUp, GitBranch, Mail, FileText, BookOpen, ExternalLink,
  Brain, Zap, Layers, Database, Cpu, Microscope, Play, Filter, Eye, AlertTriangle, MessageCircle, Users, Heart
} from 'lucide-react'
import ContactModal from '../components/ContactModal'
import SponsorModal from '../components/SponsorModal'

export default function AboutPage() {
  const [showContact, setShowContact] = useState(false)
  const [showSponsor, setShowSponsor] = useState(false)

  return (
    <div className="min-h-[calc(100vh-4rem)] bg-white text-gray-700 -m-6 p-6">
      {/* 顶部品牌 */}
      <div className="max-w-5xl mx-auto pt-8 pb-12">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-lg bg-gray-100 flex items-center justify-center">
            <FlaskConical className="w-6 h-6 text-gray-600" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-gray-900">DrugDesign Agent</h1>
            <p className="text-sm text-gray-500">小分子智能药物设计平台</p>
          </div>
        </div>
        <p className="text-sm text-gray-500 leading-relaxed max-w-2xl">
          基于人工智能的端到端小分子药物设计系统，集成分子生成、ADMET成药性预测、
          分子对接、活性预测和合成路径分析等核心模块，加速早期药物研发流程。
        </p>
      </div>

      {/* 多列链接 */}
      <div className="max-w-5xl mx-auto">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-8 md:gap-12">
          {/* 核心技术 */}
          <div>
            <h3 className="text-sm font-bold text-gray-900 mb-4">核心技术</h3>
            <ul className="space-y-3">
              <li>
                <a href="#" className="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-800 transition">
                  <Brain className="w-4 h-4" />
                  ADMET-AI 深度学习
                </a>
              </li>
              <li>
                <a href="#" className="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-800 transition">
                  <Target className="w-4 h-4" />
                  AutoDock Vina 分子对接
                </a>
              </li>
              <li>
                <a href="#" className="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-800 transition">
                  <GitBranch className="w-4 h-4" />
                  RDKit 化学信息学
                </a>
              </li>
              <li>
                <a href="#" className="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-800 transition">
                  <Atom className="w-4 h-4" />
                  CReM 片段分子生成
                </a>
              </li>
              <li>
                <a href="#" className="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-800 transition">
                  <Zap className="w-4 h-4" />
                  FEP 自由能微扰
                </a>
              </li>
              <li>
                <a href="#" className="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-800 transition">
                  <TrendingUp className="w-4 h-4" />
                  DeepAffinity 活性预测
                </a>
              </li>
              <li>
                <a href="#" className="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-800 transition">
                  <Microscope className="w-4 h-4" />
                  OpenMM 分子动力学
                </a>
              </li>
              <li>
                <a href="#" className="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-800 transition">
                  <Layers className="w-4 h-4" />
                  MM-GBSA 结合自由能
                </a>
              </li>
              <li>
                <a href="#" className="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-800 transition">
                  <Database className="w-4 h-4" />
                  QED / PAINS 成药性过滤
                </a>
              </li>
              <li>
                <a href="#" className="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-800 transition">
                  <Cpu className="w-4 h-4" />
                  Flask + React 全栈架构
                </a>
              </li>
              <li>
                <a href="#" className="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-800 transition">
                  <Activity className="w-4 h-4" />
                  3Dmol.js 分子可视化
                </a>
              </li>
            </ul>
          </div>

          {/* 功能模块 */}
          <div>
            <h3 className="text-sm font-bold text-gray-900 mb-4">功能模块</h3>
            <ul className="space-y-3">
              <li>
                <a href="/molecules" className="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-800 transition">
                  <Atom className="w-4 h-4" />
                  分子浏览器
                </a>
              </li>
              <li>
                <a href="/admet" className="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-800 transition">
                  <Activity className="w-4 h-4" />
                  ADMET 成药性分析
                </a>
              </li>
              <li>
                <a href="/docking" className="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-800 transition">
                  <Target className="w-4 h-4" />
                  分子对接
                </a>
              </li>
              <li>
                <a href="/activity" className="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-800 transition">
                  <TrendingUp className="w-4 h-4" />
                  活性预测
                </a>
              </li>
              <li>
                <a href="/synthesis" className="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-800 transition">
                  <GitBranch className="w-4 h-4" />
                  合成分析
                </a>
              </li>
              <li>
                <a href="/pipeline" className="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-800 transition">
                  <Play className="w-4 h-4" />
                  Pipeline 自动化运行
                </a>
              </li>
              <li>
                <a href="/molecules" className="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-800 transition">
                  <Eye className="w-4 h-4" />
                  3D 分子可视化
                </a>
              </li>
              <li>
                <a href="/pipeline" className="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-800 transition">
                  <Filter className="w-4 h-4" />
                  结构筛选与过滤
                </a>
              </li>
              <li>
                <a href="/failed-molecules" className="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-800 transition">
                  <AlertTriangle className="w-4 h-4" />
                  失败分子分析
                </a>
              </li>
              <li>
                <a href="/admet" className="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-800 transition">
                  <Layers className="w-4 h-4" />
                  批量 ADMET 分析
                </a>
              </li>
              <li>
                <a href="/projects" className="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-800 transition">
                  <Users className="w-4 h-4" />
                  项目协作管理
                </a>
              </li>
            </ul>
          </div>

          {/* 相关资源 */}
          <div>
            <h3 className="text-sm font-bold text-gray-900 mb-4">相关资源</h3>
            <ul className="space-y-3">
              <li>
                <a href="#" className="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-800 transition">
                  <BookOpen className="w-4 h-4" />
                  使用文档
                </a>
              </li>
              <li>
                <a href="#" className="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-800 transition">
                  <FileText className="w-4 h-4" />
                  API 参考
                </a>
              </li>
              <li>
                <a href="#" className="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-800 transition">
                  <ExternalLink className="w-4 h-4" />
                  ADMET-AI 论文
                </a>
              </li>
              <li>
                <a href="#" className="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-800 transition">
                  <ExternalLink className="w-4 h-4" />
                  RDKit 文档
                </a>
              </li>
              <li>
                <a href="#" className="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-800 transition">
                  <ExternalLink className="w-4 h-4" />
                  GitHub 仓库
                </a>
              </li>
              <li>
                <a href="#" className="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-800 transition">
                  <FileText className="w-4 h-4" />
                  CReM 分子生成论文
                </a>
              </li>
              <li>
                <a href="#" className="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-800 transition">
                  <ExternalLink className="w-4 h-4" />
                  OpenFE 自由能微扰文档
                </a>
              </li>
              <li>
                <a href="#" className="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-800 transition">
                  <FileText className="w-4 h-4" />
                  DeepAffinity 活性预测论文
                </a>
              </li>
              <li>
                <a href="#" className="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-800 transition">
                  <MessageCircle className="w-4 h-4" />
                  开发者社区
                </a>
              </li>
              <li>
                <a href="#" className="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-800 transition">
                  <FileText className="w-4 h-4" />
                  版本更新日志
                </a>
              </li>
            </ul>
          </div>

          {/* 支持 */}
          <div>
            <h3 className="text-sm font-bold text-gray-900 mb-4">支持</h3>
            <ul className="space-y-3">
              <li>
                <button
                  onClick={() => setShowContact(true)}
                  className="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-800 transition cursor-pointer"
                >
                  <Mail className="w-4 h-4" />
                  联系我们
                </button>
              </li>
              <li>
                <a href="#" className="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-800 transition">
                  <FileText className="w-4 h-4" />
                  报告问题
                </a>
              </li>
              <li>
                <button
                  onClick={() => setShowSponsor(true)}
                  className="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-800 transition cursor-pointer"
                >
                  <Heart className="w-4 h-4" />
                  赞助支持
                </button>
              </li>
              <li>
                <span className="text-sm text-gray-400">版本: v1.0.0</span>
              </li>
            </ul>
          </div>
        </div>
      </div>

      {/* 分隔线 + 底部 */}
      <div className="max-w-5xl mx-auto mt-12 pt-6 border-t border-gray-200">
        <div className="flex items-center justify-between flex-wrap gap-4">
          <p className="text-xs text-gray-400">
            DrugDesign Agent — 基于 MIT 协议开源
          </p>
          <p className="text-xs text-gray-400">
            2026 DrugDesign Agent. All rights reserved.
          </p>
        </div>
      </div>
      {/* 联系我们弹窗 */}
      {showContact && <ContactModal onClose={() => setShowContact(false)} />}
      {/* 赞助弹窗 */}
      {showSponsor && <SponsorModal onClose={() => setShowSponsor(false)} />}
    </div>
  )
}
