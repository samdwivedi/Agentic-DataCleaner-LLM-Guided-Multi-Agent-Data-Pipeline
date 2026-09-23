'use client'

import { useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Upload, Activity, Zap, CheckCircle, Download, Shield, Play } from 'lucide-react'
import { StrategyTable } from '@/components/StrategyTable'
import { ExecutionLog } from '@/components/ExecutionLog'
import { MetricCard } from '@/components/MetricCard'

type Step = 'upload' | 'analyzing' | 'strategy' | 'executing' | 'results'

export default function PipelineDashboard() {
  const [step, setStep] = useState<Step>('upload')
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [file, setFile] = useState<File | null>(null)
  
  const [analysisData, setAnalysisData] = useState<any>(null)
  const [strategyData, setStrategyData] = useState<any>(null)
  const [executionData, setExecutionData] = useState<any>(null)
  const [qualityData, setQualityData] = useState<any>(null)
  
  const [loadingMsg, setLoadingMsg] = useState('')

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || e.target.files.length === 0) return
    const uploadedFile = e.target.files[0]
    setFile(uploadedFile)
    
    // 1. Upload
    setStep('analyzing')
    setLoadingMsg('Uploading dataset...')
    
    const formData = new FormData()
    formData.append('file', uploadedFile)
    
    try {
      const uploadRes = await fetch('http://localhost:8000/pipeline/upload', {
        method: 'POST',
        body: formData
      })
      const uploadJson = await uploadRes.json()
      const sid = uploadJson.session_id
      setSessionId(sid)
      
      // 2. Analyze
      setLoadingMsg('Profiling dataset & detecting anomalies...')
      const analyzeRes = await fetch(`http://localhost:8000/pipeline/${sid}/analyze`, { method: 'POST' })
      const analyzeJson = await analyzeRes.json()
      setAnalysisData(analyzeJson)
      
      // 3. Strategy
      setLoadingMsg('LLM Strategist is formulating a plan...')
      const stratRes = await fetch(`http://localhost:8000/pipeline/${sid}/strategy`, { method: 'POST' })
      const stratJson = await stratRes.json()
      setStrategyData(stratJson)
      
      setStep('strategy')
      
    } catch (err) {
      console.error(err)
      alert('Pipeline failed during analysis phase.')
      setStep('upload')
    }
  }

  const handleExecute = async () => {
    if (!sessionId || !strategyData) return
    
    setStep('executing')
    try {
      // 4. Validate Strategy
      setLoadingMsg('Validating strategy against safety thresholds...')
      const valRes = await fetch(`http://localhost:8000/pipeline/${sessionId}/validate-strategy`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ actions: strategyData.actions })
      })
      if (!valRes.ok) {
        const valErr = await valRes.json()
        alert('Validation failed: ' + JSON.stringify(valErr))
        setStep('strategy')
        return
      }
      
      // 5. Execute
      setLoadingMsg('Executing deterministic cleaning actions...')
      const execRes = await fetch(`http://localhost:8000/pipeline/${sessionId}/execute`, { method: 'POST' })
      const execJson = await execRes.json()
      setExecutionData(execJson)
      
      // 6. Quality Validation
      setLoadingMsg('Assessing post-cleaning quality...')
      const qualRes = await fetch(`http://localhost:8000/pipeline/${sessionId}/validate-quality`, { method: 'POST' })
      const qualJson = await qualRes.json()
      setQualityData(qualJson)
      
      setStep('results')
    } catch (err) {
      console.error(err)
      alert('Execution failed.')
      setStep('strategy')
    }
  }

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
                  <input type="file" accept=".csv" className="hidden" onChange={handleFileUpload} />
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
                className="space-y-8"
              >
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                  <MetricCard title="Rows" value={analysisData.profiler_report?.summary?.row_count} icon={<Activity />} />
                  <MetricCard title="Columns" value={analysisData.profiler_report?.summary?.column_count} icon={<Activity />} />
                  <MetricCard title="Anomalies" value={analysisData.anomaly_report?.summary?.total_outliers_found} icon={<Activity />} />
                </div>
                
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
                className="space-y-8"
              >
                <div className="bg-gradient-to-br from-emerald-900/20 to-teal-900/20 border border-emerald-500/20 backdrop-blur-xl rounded-3xl p-8 text-center shadow-2xl shadow-emerald-900/10">
                  <div className="w-20 h-20 bg-emerald-500/20 rounded-full flex items-center justify-center mx-auto mb-6">
                    <CheckCircle className="w-10 h-10 text-emerald-400" />
                  </div>
                  <h2 className="text-4xl font-bold text-white mb-4">Cleaning Complete</h2>
                  <p className="text-emerald-100/70 text-lg mb-8 max-w-2xl mx-auto">
                    The deterministic executor safely applied the strategy. Quality score improved from <strong className="text-white">{qualityData.score_before.toFixed(1)}</strong> to <strong className="text-emerald-400">{qualityData.score_after.toFixed(1)}</strong>.
                  </p>
                  
                  <a 
                    href={`http://localhost:8000/pipeline/${sessionId}/download`}
                    target="_blank"
                    className="inline-flex px-8 py-4 bg-emerald-600 hover:bg-emerald-500 text-white rounded-2xl font-bold items-center gap-3 shadow-lg shadow-emerald-900/20 transition-all hover:scale-105"
                  >
                    <Download className="w-5 h-5" />
                    Download Cleaned Dataset
                  </a>
                </div>

                <div className="bg-slate-900/60 backdrop-blur-xl border border-slate-800 rounded-3xl p-8 shadow-2xl">
                  <h3 className="text-2xl font-bold text-white flex items-center gap-3 mb-6">
                    <Shield className="text-indigo-400 w-6 h-6" />
                    Execution Audit Log
                  </h3>
                  <ExecutionLog logs={executionData.log_entries} />
                </div>
              </motion.div>
            )}

          </AnimatePresence>
        </div>
      </main>
    </div>
  )
}
