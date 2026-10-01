'use client'

import { motion } from 'framer-motion'
import { ArrowDown, ArrowUp, Minus } from 'lucide-react'

interface MetricsSnapshot {
  row_count: number
  column_count: number
  total_missing: number
  missing_pct: number
  columns_with_nulls: number
  duplicate_rows: number
  duplicate_pct: number
  outlier_count: number
  quality_score: number
}

interface BeforeAfterComparisonProps {
  before: MetricsSnapshot
  after: MetricsSnapshot
}

interface DeltaCardProps {
  label: string
  beforeVal: number | string
  afterVal: number | string
  delta: number
  /** Higher is better (e.g. quality_score) vs lower is better (e.g. missing_pct) */
  higherIsBetter?: boolean
  format?: 'number' | 'pct' | 'score'
}

function DeltaCard({ label, beforeVal, afterVal, delta, higherIsBetter = false, format = 'number' }: DeltaCardProps) {
  const isImproved = higherIsBetter ? delta > 0 : delta < 0
  const isNeutral = delta === 0

  const formatVal = (v: number | string) => {
    if (typeof v === 'string') return v
    if (format === 'pct') return `${v.toFixed(1)}%`
    if (format === 'score') return v.toFixed(1)
    return v.toLocaleString()
  }

  const formatDelta = (d: number) => {
    const sign = d > 0 ? '+' : ''
    if (format === 'pct') return `${sign}${d.toFixed(1)}%`
    if (format === 'score') return `${sign}${d.toFixed(1)}`
    return `${sign}${d.toLocaleString()}`
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-slate-900/30 border border-slate-800/60 rounded-2xl p-4 hover:border-slate-700 transition-colors"
    >
      <p className="text-xs text-slate-500 font-medium uppercase tracking-wider mb-3">{label}</p>

      <div className="flex items-end justify-between">
        <div className="flex items-center gap-3">
          <div>
            <p className="text-[10px] text-slate-600">Before</p>
            <p className="text-lg font-bold text-slate-400">{formatVal(beforeVal)}</p>
          </div>
          <span className="text-slate-700 text-lg">→</span>
          <div>
            <p className="text-[10px] text-slate-600">After</p>
            <p className={`text-lg font-bold ${isImproved ? 'text-emerald-400' : isNeutral ? 'text-slate-300' : 'text-red-400'}`}>
              {formatVal(afterVal)}
            </p>
          </div>
        </div>

        <div className={`flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold ${
          isImproved
            ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
            : isNeutral
              ? 'bg-slate-500/10 text-slate-400 border border-slate-500/20'
              : 'bg-red-500/10 text-red-400 border border-red-500/20'
        }`}>
          {isImproved ? <ArrowDown className="w-3 h-3" /> : isNeutral ? <Minus className="w-3 h-3" /> : <ArrowUp className="w-3 h-3" />}
          {formatDelta(delta)}
        </div>
      </div>
    </motion.div>
  )
}

export function BeforeAfterComparison({ before, after }: BeforeAfterComparisonProps) {
  const metrics = [
    {
      label: 'Quality Score',
      before: before.quality_score,
      after: after.quality_score,
      delta: after.quality_score - before.quality_score,
      higherIsBetter: true,
      format: 'score' as const,
    },
    {
      label: 'Missing Values',
      before: before.total_missing,
      after: after.total_missing,
      delta: after.total_missing - before.total_missing,
      higherIsBetter: false,
    },
    {
      label: 'Missing %',
      before: before.missing_pct,
      after: after.missing_pct,
      delta: after.missing_pct - before.missing_pct,
      higherIsBetter: false,
      format: 'pct' as const,
    },
    {
      label: 'Duplicate Rows',
      before: before.duplicate_rows,
      after: after.duplicate_rows,
      delta: after.duplicate_rows - before.duplicate_rows,
      higherIsBetter: false,
    },
    {
      label: 'Duplicate %',
      before: before.duplicate_pct,
      after: after.duplicate_pct,
      delta: after.duplicate_pct - before.duplicate_pct,
      higherIsBetter: false,
      format: 'pct' as const,
    },
    {
      label: 'Outliers',
      before: before.outlier_count,
      after: after.outlier_count,
      delta: after.outlier_count - before.outlier_count,
      higherIsBetter: false,
    },
    {
      label: 'Row Count',
      before: before.row_count,
      after: after.row_count,
      delta: after.row_count - before.row_count,
      higherIsBetter: true,
    },
    {
      label: 'Columns with Nulls',
      before: before.columns_with_nulls,
      after: after.columns_with_nulls,
      delta: after.columns_with_nulls - before.columns_with_nulls,
      higherIsBetter: false,
    },
  ]

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
      {metrics.map((m, i) => (
        <DeltaCard
          key={m.label}
          label={m.label}
          beforeVal={m.before}
          afterVal={m.after}
          delta={m.delta}
          higherIsBetter={m.higherIsBetter}
          format={m.format}
        />
      ))}
    </div>
  )
}
