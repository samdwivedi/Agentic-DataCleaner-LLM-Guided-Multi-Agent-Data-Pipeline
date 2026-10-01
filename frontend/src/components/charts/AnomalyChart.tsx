'use client'

import { motion } from 'framer-motion'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell
} from 'recharts'

// ── Anomaly Chart: Outliers per column ───────────────────────────────────────

interface AnomalyColumn {
  column_name: string
  outlier_count: number
  outlier_pct: number
  method: string
  iqr_lower_bound?: number | null
  iqr_upper_bound?: number | null
}

interface AnomalyChartProps {
  columnReports: AnomalyColumn[]
  totalRows: number
}

const ANOMALY_COLORS = [
  '#f87171', '#fb923c', '#fbbf24', '#a78bfa', '#f472b6',
  '#34d399', '#38bdf8', '#c084fc', '#fb7185', '#facc15',
]

function CustomTooltip({ active, payload }: any) {
  if (!active || !payload?.[0]) return null
  const d = payload[0].payload
  return (
    <div className="bg-slate-900/95 border border-slate-700 backdrop-blur-xl rounded-xl px-4 py-3 shadow-2xl">
      <p className="font-mono text-indigo-300 text-sm font-semibold mb-1">{d.column_name}</p>
      <p className="text-slate-300 text-xs">
        <span className="text-red-400 font-bold">{d.outlier_count.toLocaleString()}</span> outliers ({d.outlier_pct.toFixed(1)}%)
      </p>
      <p className="text-slate-500 text-xs mt-1">Method: {d.method}</p>
      {d.iqr_lower_bound != null && d.iqr_upper_bound != null && (
        <p className="text-slate-500 text-xs">
          IQR bounds: [{d.iqr_lower_bound.toFixed(2)}, {d.iqr_upper_bound.toFixed(2)}]
        </p>
      )}
    </div>
  )
}

export function AnomalyChart({ columnReports, totalRows }: AnomalyChartProps) {
  if (!columnReports || columnReports.length === 0) {
    return (
      <div className="text-slate-400 py-8 text-center bg-slate-900/50 rounded-2xl border border-slate-800">
        No anomalies detected — data looks clean!
      </div>
    )
  }

  // Only show columns with outliers, sorted descending
  const data = [...columnReports]
    .filter(c => c.outlier_count > 0)
    .sort((a, b) => b.outlier_count - a.outlier_count)

  if (data.length === 0) {
    return (
      <div className="text-emerald-400/70 py-8 text-center bg-emerald-900/10 rounded-2xl border border-emerald-500/20">
        ✓ No outliers detected in any column
      </div>
    )
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
    >
      <ResponsiveContainer width="100%" height={Math.max(200, data.length * 45 + 60)}>
        <BarChart
          data={data}
          layout="vertical"
          margin={{ top: 10, right: 30, left: 10, bottom: 10 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" horizontal={false} />
          <XAxis
            type="number"
            tick={{ fill: '#64748b', fontSize: 11 }}
            axisLine={{ stroke: 'rgba(255,255,255,0.06)' }}
          />
          <YAxis
            dataKey="column_name"
            type="category"
            width={120}
            tick={{ fill: '#a5b4fc', fontSize: 12, fontFamily: 'monospace' }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(255,255,255,0.02)' }} />
          <Bar dataKey="outlier_count" radius={[0, 8, 8, 0]} maxBarSize={28}>
            {data.map((_, index) => (
              <Cell key={index} fill={ANOMALY_COLORS[index % ANOMALY_COLORS.length]} fillOpacity={0.8} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      <div className="flex items-center justify-center gap-6 mt-4 text-xs text-slate-500">
        <span>Total rows: <strong className="text-slate-300">{totalRows.toLocaleString()}</strong></span>
        <span>Columns with outliers: <strong className="text-red-400">{data.length}</strong></span>
      </div>
    </motion.div>
  )
}
