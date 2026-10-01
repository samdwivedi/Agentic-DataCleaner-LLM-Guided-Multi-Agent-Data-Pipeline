'use client'

import { useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Upload, Activity, Zap, CheckCircle, Download, Shield, Play, AlertTriangle, RotateCcw, X, BarChart3, Grid3X3, Columns3, Radar, TrendingUp, Eye } from 'lucide-react'
import { StrategyTable } from '@/components/StrategyTable'
import { ExecutionLog } from '@/components/ExecutionLog'
import { MetricCard } from '@/components/MetricCard'
import {
  QualityScoreGauge,
  MissingnessHeatmap,
  AnomalyChart,
  ColumnProfileCharts,
  BeforeAfterComparison,
  DataHealthRadar,
  DatasetOverview,
} from '@/components/charts'

type Step = 'upload' | 'analyzing' | 'strategy' | 'executing' | 'results'

// ── API base URL: uses Next.js rewrites in next.config.ts ────────────────────
const API_BASE = process.env.NEXT_PUBLIC_API_URL || ''

// ── Inline error toast component ─────────────────────────────────────────────
function ErrorToast({ message, onDismiss, onRetry }: { message: string; onDismiss: () => void; onRetry?: () => void }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 30, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: 20, scale: 0.95 }}
      className="fixed bottom-8 left-1/2 -translate-x-1/2 z-50 max-w-lg w-full mx-4"
    >
      <div className="bg-red-950/90 backdrop-blur-xl border border-red-500/30 rounded-2xl p-5 shadow-2xl shadow-red-900/20 flex items-start gap-4">
        <div className="w-10 h-10 rounded-xl bg-red-500/20 flex items-center justify-center shrink-0 mt-0.5">
          <AlertTriangle className="w-5 h-5 text-red-400" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-red-300 mb-1">Pipeline Error</p>
          <p className="text-sm text-red-200/80 leading-relaxed break-words">{message}</p>
          <div className="flex gap-3 mt-3">
            {onRetry && (
              <button
                onClick={onRetry}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-red-500/20 hover:bg-red-500/30 text-red-300 rounded-lg text-xs font-medium transition-colors"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                Retry
              </button>
            )}
            <button
              onClick={onDismiss}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-white/5 hover:bg-white/10 text-slate-400 rounded-lg text-xs font-medium transition-colors"
            >
              Dismiss
            </button>
          </div>
        </div>
        <button onClick={onDismiss} className="text-red-400/50 hover:text-red-300 transition-colors shrink-0">
          <X className="w-4 h-4" />
        </button>
      </div>
    </motion.div>
  )
}

export default function PipelineDashboard() {
  const [step, setStep] = useState<Step>('upload')
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [file, setFile] = useState<File | null>(null)
  
  const [analysisData, setAnalysisData] = useState<any>(null)
  const [strategyData, setStrategyData] = useState<any>(null)
  const [executionData, setExecutionData] = useState<any>(null)
  const [qualityData, setQualityData] = useState<any>(null)
  const [exportFormat, setExportFormat] = useState('csv')
  const [activeAnalysisTab, setActiveAnalysisTab] = useState<'overview' | 'heatmap' | 'columns' | 'anomalies'>('overview')
  const [activeResultsTab, setActiveResultsTab] = useState<'comparison' | 'radar' | 'audit'>('comparison')
  
  const [loadingMsg, setLoadingMsg] = useState('')
  const [error, setError] = useState<string | null>(null)

  const dismissError = useCallback(() => setError(null), [])

  const pollTask = async (taskId: string): Promise<any> => {
    while (true) {
      const res = await fetch(`${API_BASE}/pipeline/task/${taskId}`)
      if (!res.ok) throw new Error(`Task polling failed (${res.status})`)
      const data = await res.json()
      if (data.status === 'SUCCESS') return data.result
      if (data.status === 'FAILURE') throw new Error(data.error || 'Task failed')
      await new Promise(r => setTimeout(r, 1000))
    }
  }

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || e.target.files.length === 0) return
    const uploadedFile = e.target.files[0]
    setFile(uploadedFile)
    setError(null)
    
    // 1. Upload
    setStep('analyzing')
    setLoadingMsg('Uploading dataset...')
    
    const formData = new FormData()
    formData.append('file', uploadedFile)
    
    try {
      const uploadRes = await fetch(`${API_BASE}/pipeline/upload`, {
        method: 'POST',
        body: formData
      })
      if (!uploadRes.ok) {
        const err = await uploadRes.json().catch(() => ({ detail: 'Upload failed' }))
        throw new Error(err.detail || `Upload failed (${uploadRes.status})`)
      }
      const uploadJson = await uploadRes.json()
      const sid = uploadJson.session_id
      setSessionId(sid)
      
      // 2. Analyze
      setLoadingMsg('Profiling dataset & detecting anomalies...')
      const analyzeRes = await fetch(`${API_BASE}/pipeline/${sid}/analyze`, { method: 'POST' })
      if (!analyzeRes.ok) throw new Error('Analysis failed')
      const { task_id: analyzeTaskId } = await analyzeRes.json()
      const analyzeJson = await pollTask(analyzeTaskId)
      setAnalysisData(analyzeJson)
      
      // 3. Strategy
      setLoadingMsg('LLM Strategist is formulating a plan...')
      const stratRes = await fetch(`${API_BASE}/pipeline/${sid}/strategy`, { method: 'POST' })
      if (!stratRes.ok) throw new Error('Strategy generation failed')
      const { task_id: stratTaskId } = await stratRes.json()
      const stratJson = await pollTask(stratTaskId)
      setStrategyData(stratJson)
      
      setStep('strategy')
      
    } catch (err: any) {
      console.error(err)
      setError(err?.message || 'Pipeline failed during analysis phase. Is the backend running?')
      setStep('upload')
    }
  }

  const handleExecute = async () => {
    if (!sessionId || !strategyData) return
    setError(null)
    
    setStep('executing')
    try {
      // 4. Validate Strategy
      setLoadingMsg('Validating strategy against safety thresholds...')
      const valRes = await fetch(`${API_BASE}/pipeline/${sessionId}/validate-strategy`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ actions: strategyData.actions })
      })
      if (!valRes.ok) throw new Error('Validation failed')
      const { task_id: valTaskId } = await valRes.json()
      await pollTask(valTaskId)
      
      // 5. Execute
      setLoadingMsg('Executing deterministic cleaning actions...')
      const execRes = await fetch(`${API_BASE}/pipeline/${sessionId}/execute`, { method: 'POST' })
      if (!execRes.ok) throw new Error('Execution failed')
      const { task_id: execTaskId } = await execRes.json()
      const execJson = await pollTask(execTaskId)
      setExecutionData(execJson)
      
      // 6. Quality Validation
      setLoadingMsg('Assessing post-cleaning quality...')
      const qualRes = await fetch(`${API_BASE}/pipeline/${sessionId}/validate-quality`, { method: 'POST' })
      if (!qualRes.ok) throw new Error('Quality validation failed')
      const { task_id: qualTaskId } = await qualRes.json()
      const qualJson = await pollTask(qualTaskId)
      setQualityData(qualJson)
      
      setStep('results')
    } catch (err: any) {
      console.error(err)
      setError(err?.message || 'Execution failed. Please try again.')
      setStep('strategy')
    }
  }

  const handleReset = useCallback(() => {
    setStep('upload')
    setSessionId(null)
    setFile(null)
    setAnalysisData(null)
    setStrategyData(null)
    setExecutionData(null)
    setQualityData(null)
    setError(null)
    setLoadingMsg('')
  }, [])

  return (
    <div className="min-h-screen bg-slate-950 text-slate-200 font-sans selection:bg-indigo-500/30">
      
      {/* Dynamic Background */}
      <div className="fixed inset-0 z-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-[20%] -left-[10%] w-[50%] h-[50%] rounded-full bg-indigo-900/20 blur-[120px]" />
        <div className="absolute top-[60%] -right-[10%] w-[40%] h-[60%] rounded-full bg-purple-900/20 blur-[120px]" />
      </div>

      <main className="relative z-10 max-w-6xl mx-auto p-6 md:p-12 min-h-screen flex flex-col">
        
        {/* Header */}
        <header className="mb-12 text-center">
          <h1 className="text-4xl md:text-5xl font-extrabold tracking-tight mb-4 bg-gradient-to-r from-indigo-400 via-purple-400 to-pink-400 text-transparent bg-clip-text">
            Agentic Data Cleaner
          </h1>
          <p className="text-slate-400 text-lg max-w-2xl mx-auto">
            LLM-Guided Multi-Agent Data Pipeline. Upload dirty data, let AI formulate a deterministic strategy, and execute safely.
          </p>
        </header>

        {/* Stepper Content */}
        <div className="flex-1 w-full max-w-5xl mx-auto">
          <AnimatePresence mode="wait">
            
            {step === 'upload' && (
              <motion.div
                key="upload"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.95 }}
                className="flex flex-col items-center justify-center h-[50vh]"
              >
                <label className="group relative cursor-pointer flex flex-col items-center justify-center w-full max-w-xl p-12 border-2 border-dashed border-indigo-500/30 rounded-3xl bg-slate-900/50 backdrop-blur-xl hover:bg-slate-800/50 hover:border-indigo-400/50 transition-all duration-300">
                  <div className="absolute inset-0 bg-gradient-to-b from-indigo-500/5 to-purple-500/5 rounded-3xl opacity-0 group-hover:opacity-100 transition-opacity" />
                  <Upload className="w-16 h-16 text-indigo-400 mb-6 group-hover:scale-110 transition-transform duration-300" />
                  <h3 className="text-2xl font-bold mb-2 text-white">Upload Dataset</h3>
                  <p className="text-slate-400 text-center">Drag and drop your messy CSV file here, or click to browse.</p>
                  <input id="csv-file-input" type="file" accept=".csv" className="hidden" onChange={handleFileUpload} />
                </label>
              </motion.div>
            )}

            {(step === 'analyzing' || step === 'executing') && (
              <motion.div
                key="loading"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="flex flex-col items-center justify-center h-[50vh]"
              >
                <div className="relative">
                  <div className="w-24 h-24 border-4 border-indigo-500/20 border-t-indigo-500 rounded-full animate-spin" />
                  <div className="absolute inset-0 flex items-center justify-center">
                    <Activity className="w-8 h-8 text-indigo-400 animate-pulse" />
                  </div>
                </div>
                <h3 className="text-2xl font-semibold mt-8 text-white">{loadingMsg}</h3>
                <p className="text-slate-400 mt-2">Please wait while the agents process your data.</p>
              </motion.div>
            )}

            {step === 'strategy' && strategyData && analysisData && (
              <motion.div
                key="strategy"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                className="space-y-6"
              >
                {/* ── Top metric cards ─────────────────────────── */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                  <MetricCard title="Rows" value={analysisData.profiler?.meta?.row_count ?? analysisData.profiler_report?.summary?.row_count} icon={<Activity />} />
                  <MetricCard title="Columns" value={analysisData.profiler?.meta?.column_count ?? analysisData.profiler_report?.summary?.column_count} icon={<Columns3 />} />
                  <MetricCard title="Anomalies" value={analysisData.anomaly?.total_outliers_found ?? analysisData.anomaly_report?.summary?.total_outliers_found} icon={<AlertTriangle />} />
                </div>

                {/* ── Interactive Data Visualizations (Tabbed) ── */}
                <div className="bg-slate-900/60 backdrop-blur-xl border border-slate-800 rounded-3xl p-6 shadow-2xl">
                  <div className="flex items-center justify-between mb-6">
                    <h2 className="text-xl font-bold text-white flex items-center gap-2">
                      <Eye className="text-indigo-400 w-5 h-5" />
                      Dataset Analysis
                    </h2>
                    <div className="flex bg-slate-800/60 rounded-xl p-1 gap-1">
                      {[
                        { key: 'overview' as const, label: 'Overview', icon: <BarChart3 className="w-3.5 h-3.5" /> },
                        { key: 'heatmap' as const, label: 'Missing Data', icon: <Grid3X3 className="w-3.5 h-3.5" /> },
                        { key: 'columns' as const, label: 'Distributions', icon: <Columns3 className="w-3.5 h-3.5" /> },
                        { key: 'anomalies' as const, label: 'Anomalies', icon: <AlertTriangle className="w-3.5 h-3.5" /> },
                      ].map(tab => (
                        <button
                          key={tab.key}
                          onClick={() => setActiveAnalysisTab(tab.key)}
                          className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium transition-all ${
                            activeAnalysisTab === tab.key
                              ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-900/30'
                              : 'text-slate-400 hover:text-white hover:bg-slate-700/50'
                          }`}
                        >
                          {tab.icon}
                          {tab.label}
                        </button>
                      ))}
                    </div>
                  </div>

                  <AnimatePresence mode="wait">
                    {activeAnalysisTab === 'overview' && (analysisData.profiler?.meta || analysisData.profiler_report?.summary) && (
                      <motion.div key="tab-overview" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
                        <DatasetOverview
                          meta={analysisData.profiler?.meta ?? analysisData.profiler_report?.summary}
                          duplicates={analysisData.profiler?.duplicates ?? analysisData.profiler_report?.duplicates ?? { duplicate_row_count: 0, duplicate_row_pct: 0, has_duplicates: false }}
                        />
                      </motion.div>
                    )}

                    {activeAnalysisTab === 'heatmap' && (analysisData.profiler?.columns || analysisData.profiler_report?.columns) && (
                      <motion.div key="tab-heatmap" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
                        <MissingnessHeatmap
                          columns={(analysisData.profiler?.columns ?? analysisData.profiler_report?.columns ?? []).map((c: any) => ({
                            name: c.name,
                            missing_pct: c.missing_pct,
                            missing_count: c.missing_count,
                            row_count: c.row_count,
                          }))}
                        />
                      </motion.div>
                    )}

                    {activeAnalysisTab === 'columns' && (analysisData.profiler?.columns || analysisData.profiler_report?.columns) && (
                      <motion.div key="tab-columns" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
                        <ColumnProfileCharts
                          columns={analysisData.profiler?.columns ?? analysisData.profiler_report?.columns ?? []}
                        />
                      </motion.div>
                    )}

                    {activeAnalysisTab === 'anomalies' && (
                      <motion.div key="tab-anomalies" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
                        <AnomalyChart
                          columnReports={analysisData.anomaly?.column_reports ?? analysisData.anomaly_report?.column_reports ?? []}
                          totalRows={analysisData.profiler?.meta?.row_count ?? analysisData.profiler_report?.summary?.row_count ?? 0}
                        />
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>

                {/* ── Proposed Strategy ─────────────────────────── */}
                <div className="bg-slate-900/60 backdrop-blur-xl border border-slate-800 rounded-3xl p-8 shadow-2xl">
                  <div className="flex items-center justify-between mb-8">
                    <div>
                      <h2 className="text-3xl font-bold text-white flex items-center gap-3">
                        <Zap className="text-amber-400 w-8 h-8" />
                        Proposed Cleaning Strategy
                      </h2>
                      <p className="text-slate-400 mt-2">The LLM Strategist recommends the following deterministic actions.</p>
                    </div>
                    <button 
                      id="execute-strategy-btn"
                      onClick={handleExecute}
                      className="px-8 py-4 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white rounded-2xl font-bold flex items-center gap-3 shadow-lg shadow-indigo-900/20 hover:shadow-indigo-500/30 transition-all hover:scale-105"
                    >
                      <Play className="w-5 h-5 fill-current" />
                      Approve & Execute
                    </button>
                  </div>
                  
                  <StrategyTable actions={strategyData.actions} />
                </div>
              </motion.div>
            )}

            {step === 'results' && executionData && qualityData && (
              <motion.div
                key="results"
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                className="space-y-6"
              >
                {/* ── Hero banner with gauge ─────────────────── */}
                <div className="bg-gradient-to-br from-emerald-900/20 to-teal-900/20 border border-emerald-500/20 backdrop-blur-xl rounded-3xl p-8 shadow-2xl shadow-emerald-900/10">
                  <div className="grid grid-cols-1 md:grid-cols-[1fr_auto_1fr] gap-8 items-center">
                    {/* Left: Text */}
                    <div className="text-center md:text-left">
                      <div className="flex items-center gap-3 justify-center md:justify-start mb-4">
                        <div className="w-12 h-12 bg-emerald-500/20 rounded-full flex items-center justify-center">
                          <CheckCircle className="w-6 h-6 text-emerald-400" />
                        </div>
                        <h2 className="text-3xl font-bold text-white">Cleaning Complete</h2>
                      </div>
                      <p className="text-emerald-100/70 text-base mb-6 max-w-md">
                        The deterministic executor safely applied the strategy. Your dataset has been cleaned and validated.
                      </p>
                      <div className="flex items-center gap-3 flex-wrap justify-center md:justify-start">
                        <select 
                          value={exportFormat}
                          onChange={(e) => setExportFormat(e.target.value)}
                          className="px-4 py-3 bg-slate-800 text-white rounded-xl border border-slate-700 outline-none focus:border-emerald-500 transition-colors cursor-pointer shadow-lg font-medium text-sm"
                        >
                          <option value="csv">CSV</option>
                          <option value="parquet">Parquet</option>
                          <option value="xlsx">Excel (XLSX)</option>
                          <option value="json">JSON</option>
                        </select>
                        <a 
                          href={`${API_BASE}/pipeline/${sessionId}/download?format=${exportFormat}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          id="download-cleaned-btn"
                          className="inline-flex px-6 py-3 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl font-bold items-center gap-2 shadow-lg shadow-emerald-900/20 transition-all hover:scale-105 text-sm"
                        >
                          <Download className="w-4 h-4" />
                          Download
                        </a>
                        <button
                          onClick={handleReset}
                          className="inline-flex px-5 py-3 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl font-bold items-center gap-2 transition-all hover:scale-105 text-sm"
                        >
                          <RotateCcw className="w-4 h-4" />
                          New
                        </button>
                      </div>
                    </div>

                    {/* Center: Quality Gauge */}
                    <div className="hidden md:block">
                      <QualityScoreGauge
                        scoreBefore={qualityData.quality_score_before ?? qualityData.score_before ?? 0}
                        scoreAfter={qualityData.quality_score_after ?? qualityData.score_after ?? 0}
                      />
                    </div>

                    {/* Right: Quick stats */}
                    <div className="grid grid-cols-2 gap-3">
                      {[
                        { label: 'Rows Cleaned', value: (qualityData.metrics_after?.row_count ?? qualityData.metrics_before?.row_count ?? '-').toLocaleString(), color: 'text-white' },
                        { label: 'Missing After', value: `${(qualityData.metrics_after?.missing_pct ?? 0).toFixed(1)}%`, color: (qualityData.metrics_after?.missing_pct ?? 0) < 5 ? 'text-emerald-400' : 'text-amber-400' },
                        { label: 'Duplicates After', value: `${(qualityData.metrics_after?.duplicate_pct ?? 0).toFixed(1)}%`, color: (qualityData.metrics_after?.duplicate_pct ?? 0) < 1 ? 'text-emerald-400' : 'text-amber-400' },
                        { label: 'Improvement', value: `${qualityData.improvement >= 0 ? '+' : ''}${(qualityData.improvement ?? 0).toFixed(1)}`, color: (qualityData.improvement ?? 0) >= 0 ? 'text-emerald-400' : 'text-red-400' },
                      ].map(s => (
                        <div key={s.label} className="bg-black/20 rounded-xl p-3 border border-white/5">
                          <p className="text-[10px] text-slate-500 uppercase tracking-wider">{s.label}</p>
                          <p className={`text-lg font-bold mt-0.5 ${s.color}`}>{s.value}</p>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Mobile gauge */}
                  <div className="md:hidden mt-6 flex justify-center">
                    <QualityScoreGauge
                      scoreBefore={qualityData.quality_score_before ?? qualityData.score_before ?? 0}
                      scoreAfter={qualityData.quality_score_after ?? qualityData.score_after ?? 0}
                    />
                  </div>
                </div>

                {/* ── Detailed Results (Tabbed) ──────────────── */}
                <div className="bg-slate-900/60 backdrop-blur-xl border border-slate-800 rounded-3xl p-6 shadow-2xl">
                  <div className="flex items-center justify-between mb-6">
                    <h3 className="text-xl font-bold text-white flex items-center gap-2">
                      <TrendingUp className="text-indigo-400 w-5 h-5" />
                      Detailed Results
                    </h3>
                    <div className="flex bg-slate-800/60 rounded-xl p-1 gap-1">
                      {[
                        { key: 'comparison' as const, label: 'Before / After', icon: <BarChart3 className="w-3.5 h-3.5" /> },
                        { key: 'radar' as const, label: 'Health Radar', icon: <Radar className="w-3.5 h-3.5" /> },
                        { key: 'audit' as const, label: 'Audit Log', icon: <Shield className="w-3.5 h-3.5" /> },
                      ].map(tab => (
                        <button
                          key={tab.key}
                          onClick={() => setActiveResultsTab(tab.key)}
                          className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium transition-all ${
                            activeResultsTab === tab.key
                              ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-900/30'
                              : 'text-slate-400 hover:text-white hover:bg-slate-700/50'
                          }`}
                        >
                          {tab.icon}
                          {tab.label}
                        </button>
                      ))}
                    </div>
                  </div>

                  <AnimatePresence mode="wait">
                    {activeResultsTab === 'comparison' && qualityData.metrics_before && qualityData.metrics_after && (
                      <motion.div key="tab-comparison" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
                        <BeforeAfterComparison
                          before={qualityData.metrics_before}
                          after={qualityData.metrics_after}
                        />
                      </motion.div>
                    )}

                    {activeResultsTab === 'radar' && qualityData.metrics_before && qualityData.metrics_after && (
                      <motion.div key="tab-radar" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
                        <DataHealthRadar
                          before={qualityData.metrics_before}
                          after={qualityData.metrics_after}
                          totalRows={qualityData.metrics_before.row_count ?? 1}
                        />
                      </motion.div>
                    )}

                    {activeResultsTab === 'audit' && (
                      <motion.div key="tab-audit" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
                        <ExecutionLog logs={executionData.log_entries} />
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              </motion.div>
            )}

          </AnimatePresence>
        </div>
      </main>

      {/* Error Toast (replaces alert()) */}
      <AnimatePresence>
        {error && (
          <ErrorToast 
            message={error} 
            onDismiss={dismissError}
            onRetry={step === 'upload' ? undefined : () => {
              dismissError()
              if (step === 'strategy') handleExecute()
            }}
          />
        )}
      </AnimatePresence>
    </div>
  )
}
