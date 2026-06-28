import React, { Suspense, lazy } from 'react'
import { Routes, Route } from 'react-router-dom'
import Layout from './pages/Layout'
import HomePage from './pages/HomePage'
import ProjectList from './pages/ProjectList'
import ProjectDetail from './pages/ProjectDetail'
import MoleculeBrowser from './pages/MoleculeBrowser'
import MoleculeDetail from './pages/MoleculeDetail'
import AdmetAnalysis from './pages/AdmetAnalysis'
import SynthesisView from './pages/SynthesisView'
import PipelineRun from './pages/PipelineRun'
import DockingPage from './pages/DockingPage'
import ActivityPage from './pages/ActivityPage'
import ResultsPage from './pages/ResultsPage'
import FailedMolecules from './pages/FailedMolecules'
import AboutPage from './pages/AboutPage'
import AgentTracePage from './pages/AgentTracePage'

// 动态导入大体积页面（代码分割）
const MoleculeBuilderPage = lazy(() => import('./pages/MoleculeBuilderPage'))

import { AppProvider } from './store/AppContext'

function App() {
  return (
    <AppProvider>
      <Layout>
        <Suspense fallback={<div className="flex-1 flex items-center justify-center text-slate-400 text-sm">加载中...</div>}>
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/projects" element={<ProjectList />} />
            <Route path="/projects/:id" element={<ProjectDetail />} />
            <Route path="/molecules" element={<MoleculeBrowser />} />
            <Route path="/molecules/:id" element={<MoleculeDetail />} />
            <Route path="/builder" element={<MoleculeBuilderPage />} />
            <Route path="/admet" element={<AdmetAnalysis />} />
            <Route path="/synthesis" element={<SynthesisView />} />
            <Route path="/pipeline" element={<PipelineRun />} />
            <Route path="/docking" element={<DockingPage />} />
            <Route path="/activity" element={<ActivityPage />} />
            <Route path="/failed-molecules" element={<FailedMolecules />} />
            <Route path="/agent-traces" element={<AgentTracePage />} />
            <Route path="/results" element={<ResultsPage />} />
            <Route path="/about" element={<AboutPage />} />
          </Routes>
        </Suspense>
      </Layout>
    </AppProvider>
  )
}

export default App
