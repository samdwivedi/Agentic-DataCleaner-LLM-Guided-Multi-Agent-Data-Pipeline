'use client'

import { motion } from 'framer-motion'
import {
  Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer, Legend
} from 'recharts'

interface DataHealthRadarProps {
  /** Metrics BEFORE cleaning */
  before: {
    missing_pct: number
    duplicate_pct: number
    outlier_count: number
    quality_score: number
    columns_with_nulls: number
    column_count: number
  }
  /** Metrics AFTER cleaning */
  after: {
    missing_pct: number
    duplicate_pct: number
    outlier_count: number
    quality_score: number
    columns_with_nulls: number
    column_count: number
  }
  totalRows: number
}

/**
 * Converts a raw metric to a 0–100 "health" score.
 * For "lower is better" metrics, we invert so 100 = perfect.
 */
function normalizeMetric(value: number, max: number, lowerIsBetter: boolean): number {
  if (max === 0) return 100
  const raw = Math.min(value / max, 1)
  const score = lowerIsBetter ? (1 - raw) * 100 : raw * 100
  return Math.round(Math.max(0, Math.min(100, score)))
}

export function DataHealthRadar({ before, after, totalRows }: DataHealthRadarProps) {
  // Normalize all metrics to 0–100 health scores
  const dimensions = [
    {
      dimension: 'Completeness',
      before: normalizeMetric(before.missing_pct, 100, true),
      after: normalizeMetric(after.missing_pct, 100, true),
    },
    {
      dimension: 'Uniqueness',
      before: normalizeMetric(before.duplicate_pct, 100, true),
      after: normalizeMetric(after.duplicate_pct, 100, true),
    },
    {
      dimension: 'Anomaly Free',
      before: normalizeMetric(before.outlier_count, totalRows * 0.1, true),
      after: normalizeMetric(after.outlier_count, totalRows * 0.1, true),
    },
    {
      dimension: 'Quality Score',
      before: Math.round(before.quality_score),
      after: Math.round(after.quality_score),
    },
    {
      dimension: 'Column Health',
      before: before.column_count > 0
        ? normalizeMetric(before.columns_with_nulls, before.column_count, true)
        : 100,
      after: after.column_count > 0
        ? normalizeMetric(after.columns_with_nulls, after.column_count, true)
        : 100,
    },
  ]

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.5 }}
      className="flex flex-col items-center"
    >
      <ResponsiveContainer width="100%" height={320}>
        <RadarChart cx="50%" cy="50%" outerRadius="70%" data={dimensions}>
          <PolarGrid
            stroke="rgba(255,255,255,0.06)"
            gridType="polygon"
          />
          <PolarAngleAxis
            dataKey="dimension"
            tick={{ fill: '#94a3b8', fontSize: 11 }}
          />
          <PolarRadiusAxis
            angle={90}
            domain={[0, 100]}
            tick={{ fill: '#475569', fontSize: 9 }}
            axisLine={false}
          />
          <Radar
            name="Before"
            dataKey="before"
            stroke="#f87171"
            fill="#f87171"
            fillOpacity={0.1}
            strokeWidth={2}
            dot={{ r: 3, fill: '#f87171' }}
          />
          <Radar
            name="After"
            dataKey="after"
            stroke="#34d399"
            fill="#34d399"
            fillOpacity={0.15}
            strokeWidth={2}
            dot={{ r: 3, fill: '#34d399' }}
          />
          <Legend
            wrapperStyle={{ fontSize: '12px', paddingTop: '10px' }}
          />
        </RadarChart>
      </ResponsiveContainer>
    </motion.div>
  )
}
