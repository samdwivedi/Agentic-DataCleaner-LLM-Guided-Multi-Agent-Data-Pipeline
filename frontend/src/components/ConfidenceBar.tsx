'use client'

import { formatConfidence, confidenceLabel, confidenceColor } from '@/lib/api'

interface ConfidenceBarProps {
  score: number
}

export function ConfidenceBar({ score }: ConfidenceBarProps) {
  const pct = Math.round(score * 100)
  const label = confidenceLabel(score)
  const color = confidenceColor(score)

  return (
    <div className="mt-3">
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-xs text-slate-500 font-medium">Confidence</span>
        <span className="text-xs font-semibold" style={{ color }}>
          {label} · {pct}%
        </span>
      </div>
      <div className="h-1.5 rounded-full bg-surface-border overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-700 ease-out"
          style={{
            width: `${pct}%`,
            background: `linear-gradient(90deg, ${color}99, ${color})`,
          }}
        />
      </div>
    </div>
  )
}
