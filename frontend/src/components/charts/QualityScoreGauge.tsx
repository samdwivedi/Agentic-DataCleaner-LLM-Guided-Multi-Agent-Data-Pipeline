'use client'

import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'

interface QualityScoreGaugeProps {
  scoreBefore: number
  scoreAfter: number
  label?: string
}

function scoreColor(score: number): string {
  if (score >= 80) return '#34d399' // emerald-400
  if (score >= 60) return '#fbbf24' // amber-400
  if (score >= 40) return '#f97316' // orange-400
  return '#f87171' // red-400
}

function scoreGradientId(prefix: string): string {
  return `gauge-gradient-${prefix}`
}

export function QualityScoreGauge({ scoreBefore, scoreAfter, label = 'Quality Score' }: QualityScoreGaugeProps) {
  const [animatedScore, setAnimatedScore] = useState(0)
  const improvement = scoreAfter - scoreBefore

  useEffect(() => {
    // Animate the score counter
    const duration = 1200
    const startTime = Date.now()
    const startVal = 0
    const endVal = scoreAfter

    const animate = () => {
      const elapsed = Date.now() - startTime
      const progress = Math.min(elapsed / duration, 1)
      // Ease out cubic
      const eased = 1 - Math.pow(1 - progress, 3)
      setAnimatedScore(startVal + (endVal - startVal) * eased)
      if (progress < 1) requestAnimationFrame(animate)
    }
    requestAnimationFrame(animate)
  }, [scoreAfter])

  const radius = 80
  const strokeWidth = 12
  const circumference = Math.PI * radius // Half circle
  const normalizedScore = Math.min(Math.max(animatedScore, 0), 100)
  const strokeDashoffset = circumference - (normalizedScore / 100) * circumference
  const cx = 100
  const cy = 95

  const afterColor = scoreColor(scoreAfter)
  const beforeColor = scoreColor(scoreBefore)

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.5 }}
      className="flex flex-col items-center"
    >
      <svg width="200" height="120" viewBox="0 0 200 120">
        <defs>
          <linearGradient id={scoreGradientId('after')} x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor={afterColor} stopOpacity="0.6" />
            <stop offset="100%" stopColor={afterColor} />
          </linearGradient>
          <filter id="gauge-glow">
            <feGaussianBlur stdDeviation="3" result="glow" />
            <feMerge>
              <feMergeNode in="glow" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* Track */}
        <path
          d={`M ${cx - radius} ${cy} A ${radius} ${radius} 0 0 1 ${cx + radius} ${cy}`}
          fill="none"
          stroke="rgba(255,255,255,0.06)"
          strokeWidth={strokeWidth}
          strokeLinecap="round"
        />

        {/* Before score (dim reference arc) */}
        <path
          d={`M ${cx - radius} ${cy} A ${radius} ${radius} 0 0 1 ${cx + radius} ${cy}`}
          fill="none"
          stroke={beforeColor}
          strokeOpacity="0.15"
          strokeWidth={strokeWidth - 4}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={circumference - (scoreBefore / 100) * circumference}
        />

        {/* After score (main arc) */}
        <path
          d={`M ${cx - radius} ${cy} A ${radius} ${radius} 0 0 1 ${cx + radius} ${cy}`}
          fill="none"
          stroke={`url(#${scoreGradientId('after')})`}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={strokeDashoffset}
          filter="url(#gauge-glow)"
          style={{ transition: 'stroke-dashoffset 1.2s cubic-bezier(0.4, 0, 0.2, 1)' }}
        />

        {/* Score text */}
        <text x={cx} y={cy - 15} textAnchor="middle" className="fill-white text-3xl font-extrabold" style={{ fontSize: '32px', fontWeight: 800 }}>
          {Math.round(animatedScore)}
        </text>
        <text x={cx} y={cy + 5} textAnchor="middle" className="fill-slate-400" style={{ fontSize: '11px' }}>
          / 100
        </text>
      </svg>

      <p className="text-sm font-medium text-slate-400 mt-1">{label}</p>

      <div className="flex items-center gap-4 mt-3">
        <div className="text-center">
          <p className="text-xs text-slate-500 uppercase tracking-wider">Before</p>
          <p className="text-lg font-bold" style={{ color: beforeColor }}>{scoreBefore.toFixed(1)}</p>
        </div>
        <div className="text-slate-600">→</div>
        <div className="text-center">
          <p className="text-xs text-slate-500 uppercase tracking-wider">After</p>
          <p className="text-lg font-bold" style={{ color: afterColor }}>{scoreAfter.toFixed(1)}</p>
        </div>
        <div className={`px-2.5 py-1 rounded-full text-xs font-bold ${
          improvement >= 0 ? 'bg-emerald-500/10 text-emerald-400' : 'bg-red-500/10 text-red-400'
        }`}>
          {improvement >= 0 ? '+' : ''}{improvement.toFixed(1)}
        </div>
      </div>
    </motion.div>
  )
}
