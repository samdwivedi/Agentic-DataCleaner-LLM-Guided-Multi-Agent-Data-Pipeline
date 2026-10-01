'use client'

import { motion } from 'framer-motion'

interface ColumnMissing {
  name: string
  missing_pct: number
  missing_count: number
  row_count: number
}

interface MissingnessHeatmapProps {
  columns: ColumnMissing[]
}

function heatColor(pct: number): string {
  if (pct === 0) return 'rgba(52, 211, 153, 0.15)'  // emerald
  if (pct < 5) return 'rgba(250, 204, 21, 0.2)'     // yellow
  if (pct < 20) return 'rgba(251, 146, 60, 0.3)'    // orange
  if (pct < 50) return 'rgba(248, 113, 113, 0.4)'   // red
  return 'rgba(239, 68, 68, 0.6)'                    // deep red
}

function heatBorderColor(pct: number): string {
  if (pct === 0) return 'rgba(52, 211, 153, 0.3)'
  if (pct < 5) return 'rgba(250, 204, 21, 0.35)'
  if (pct < 20) return 'rgba(251, 146, 60, 0.4)'
  if (pct < 50) return 'rgba(248, 113, 113, 0.5)'
  return 'rgba(239, 68, 68, 0.7)'
}

function heatTextColor(pct: number): string {
  if (pct === 0) return '#6ee7b7'
  if (pct < 5) return '#fde047'
  if (pct < 20) return '#fdba74'
  if (pct < 50) return '#fca5a5'
  return '#fca5a5'
}

export function MissingnessHeatmap({ columns }: MissingnessHeatmapProps) {
  if (!columns || columns.length === 0) return null

  // Sort by missing_pct descending
  const sorted = [...columns].sort((a, b) => b.missing_pct - a.missing_pct)

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between mb-2">
        <h4 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">Missing Data by Column</h4>
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <span className="flex items-center gap-1">
            <span className="w-3 h-3 rounded" style={{ background: 'rgba(52, 211, 153, 0.15)', border: '1px solid rgba(52, 211, 153, 0.3)' }} />
            0%
          </span>
          <span className="flex items-center gap-1">
            <span className="w-3 h-3 rounded" style={{ background: 'rgba(251, 146, 60, 0.3)', border: '1px solid rgba(251, 146, 60, 0.4)' }} />
            20%
          </span>
          <span className="flex items-center gap-1">
            <span className="w-3 h-3 rounded" style={{ background: 'rgba(239, 68, 68, 0.6)', border: '1px solid rgba(239, 68, 68, 0.7)' }} />
            50%+
          </span>
        </div>
      </div>

      <div className="grid gap-2" style={{ gridTemplateColumns: `repeat(auto-fill, minmax(${columns.length > 8 ? '120px' : '160px'}, 1fr))` }}>
        {sorted.map((col, i) => (
          <motion.div
            key={col.name}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.04, duration: 0.3 }}
            className="rounded-xl p-3 cursor-default group relative"
            style={{
              background: heatColor(col.missing_pct),
              border: `1px solid ${heatBorderColor(col.missing_pct)}`,
            }}
          >
            <p className="text-xs font-mono text-slate-300 truncate mb-1.5" title={col.name}>
              {col.name}
            </p>
            <p className="text-lg font-bold" style={{ color: heatTextColor(col.missing_pct) }}>
              {col.missing_pct.toFixed(1)}%
            </p>
            <p className="text-[10px] text-slate-500 mt-0.5">
              {col.missing_count.toLocaleString()} / {col.row_count.toLocaleString()}
            </p>

            {/* Tooltip on hover */}
            <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-xs text-slate-200 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-20 shadow-xl">
              <strong>{col.name}</strong>: {col.missing_count.toLocaleString()} missing ({col.missing_pct.toFixed(2)}%)
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  )
}
