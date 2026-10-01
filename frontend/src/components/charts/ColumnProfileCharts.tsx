'use client'

import { motion } from 'framer-motion'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell,
  PieChart, Pie
} from 'recharts'

// ── Column Profile Charts ────────────────────────────────────────────────────

interface NumericalStats {
  mean: number
  median: number
  std: number
  min: number
  max: number
  q1: number
  q3: number
  iqr: number
  skewness: number
  kurtosis: number
}

interface CategoryFrequency {
  value: string
  count: number
  frequency: number
}

interface CategoricalStats {
  top_values: CategoryFrequency[]
  mode: string | null
  mode_count: number
}

interface ColumnProfile {
  name: string
  dtype: string
  inferred_type: string
  row_count: number
  missing_count: number
  missing_pct: number
  unique_count: number
  numerical_stats?: NumericalStats | null
  categorical_stats?: CategoricalStats | null
}

interface ColumnProfileChartsProps {
  columns: ColumnProfile[]
}

const NUM_COLORS = ['#818cf8', '#6366f1', '#a78bfa', '#8b5cf6', '#c084fc']
const CAT_COLORS = ['#38bdf8', '#22d3ee', '#2dd4bf', '#34d399', '#4ade80', '#a3e635', '#facc15', '#fb923c', '#f87171', '#f472b6']

function NumBoxPlotTooltip({ active, payload }: any) {
  if (!active || !payload?.[0]) return null
  const d = payload[0].payload
  return (
    <div className="bg-slate-900/95 border border-slate-700 backdrop-blur-xl rounded-xl px-4 py-3 shadow-2xl text-xs">
      <p className="text-slate-300">{d.label}: <span className="text-white font-bold">{d.value?.toFixed(2)}</span></p>
    </div>
  )
}

/** Shows a bar chart of key stats for a numeric column */
function NumericColumnViz({ col }: { col: ColumnProfile }) {
  const stats = col.numerical_stats
  if (!stats) return null

  const data = [
    { label: 'Min', value: stats.min },
    { label: 'Q1', value: stats.q1 },
    { label: 'Median', value: stats.median },
    { label: 'Mean', value: stats.mean },
    { label: 'Q3', value: stats.q3 },
    { label: 'Max', value: stats.max },
  ]

  return (
    <div>
      <ResponsiveContainer width="100%" height={140}>
        <BarChart data={data} margin={{ top: 5, right: 5, left: 5, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
          <XAxis
            dataKey="label"
            tick={{ fill: '#94a3b8', fontSize: 10 }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis hide />
          <Tooltip content={<NumBoxPlotTooltip />} cursor={{ fill: 'rgba(255,255,255,0.02)' }} />
          <Bar dataKey="value" radius={[6, 6, 0, 0]} maxBarSize={30}>
            {data.map((_, i) => (
              <Cell key={i} fill={NUM_COLORS[i % NUM_COLORS.length]} fillOpacity={0.7} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      <div className="grid grid-cols-3 gap-2 mt-2 text-[10px] text-slate-500">
        <div>σ = <span className="text-slate-300 font-mono">{stats.std.toFixed(2)}</span></div>
        <div>IQR = <span className="text-slate-300 font-mono">{stats.iqr.toFixed(2)}</span></div>
        <div>Skew = <span className="text-slate-300 font-mono">{stats.skewness.toFixed(2)}</span></div>
      </div>
    </div>
  )
}

/** Shows a horizontal bar chart of top category values */
function CategoricalColumnViz({ col }: { col: ColumnProfile }) {
  const stats = col.categorical_stats
  if (!stats || !stats.top_values || stats.top_values.length === 0) return null

  const data = stats.top_values.slice(0, 8).map(v => ({
    name: String(v.value).length > 20 ? String(v.value).slice(0, 18) + '…' : String(v.value),
    count: v.count,
    frequency: v.frequency,
  }))

  return (
    <div>
      <ResponsiveContainer width="100%" height={Math.max(100, data.length * 24 + 30)}>
        <BarChart
          data={data}
          layout="vertical"
          margin={{ top: 5, right: 10, left: 5, bottom: 5 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" horizontal={false} />
          <XAxis type="number" tick={{ fill: '#64748b', fontSize: 10 }} axisLine={false} tickLine={false} />
          <YAxis
            dataKey="name"
            type="category"
            width={100}
            tick={{ fill: '#94a3b8', fontSize: 10 }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            content={({ active, payload }: any) => {
              if (!active || !payload?.[0]) return null
              const d = payload[0].payload
              return (
                <div className="bg-slate-900/95 border border-slate-700 backdrop-blur-xl rounded-xl px-3 py-2 shadow-xl text-xs">
                  <p className="text-white font-semibold">{d.name}</p>
                  <p className="text-slate-300">{d.count.toLocaleString()} ({(d.frequency * 100).toFixed(1)}%)</p>
                </div>
              )
            }}
            cursor={{ fill: 'rgba(255,255,255,0.02)' }}
          />
          <Bar dataKey="count" radius={[0, 6, 6, 0]} maxBarSize={18}>
            {data.map((_, i) => (
              <Cell key={i} fill={CAT_COLORS[i % CAT_COLORS.length]} fillOpacity={0.7} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      {stats.mode && (
        <p className="text-[10px] text-slate-500 mt-1">
          Mode: <span className="text-cyan-300 font-mono">{String(stats.mode)}</span> ({stats.mode_count.toLocaleString()})
        </p>
      )}
    </div>
  )
}

/** Type badge color */
function typeBadgeColor(type: string): string {
  const map: Record<string, string> = {
    numeric_int: 'bg-indigo-500/15 text-indigo-300 border-indigo-500/25',
    numeric_float: 'bg-purple-500/15 text-purple-300 border-purple-500/25',
    categorical: 'bg-cyan-500/15 text-cyan-300 border-cyan-500/25',
    boolean: 'bg-amber-500/15 text-amber-300 border-amber-500/25',
    datetime: 'bg-pink-500/15 text-pink-300 border-pink-500/25',
    text: 'bg-slate-500/15 text-slate-300 border-slate-500/25',
    id_candidate: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/25',
    constant: 'bg-red-500/15 text-red-300 border-red-500/25',
  }
  return map[type] || 'bg-slate-500/15 text-slate-300 border-slate-500/25'
}

export function ColumnProfileCharts({ columns }: ColumnProfileChartsProps) {
  if (!columns || columns.length === 0) return null

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {columns.map((col, i) => (
        <motion.div
          key={col.name}
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: i * 0.05, duration: 0.35 }}
          className="bg-slate-900/40 border border-slate-800 rounded-2xl p-5 hover:border-slate-700/80 transition-colors"
        >
          {/* Header */}
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2 min-w-0">
              <h5 className="text-sm font-bold font-mono text-white truncate">{col.name}</h5>
              <span className={`text-[10px] px-2 py-0.5 rounded-full border font-medium shrink-0 ${typeBadgeColor(col.inferred_type)}`}>
                {col.inferred_type}
              </span>
            </div>
            <span className="text-[10px] text-slate-500 shrink-0 ml-2">{col.dtype}</span>
          </div>

          {/* Quick stats */}
          <div className="flex gap-4 mb-3 text-[11px]">
            <div>
              <span className="text-slate-500">Unique: </span>
              <span className="text-white font-semibold">{col.unique_count.toLocaleString()}</span>
            </div>
            <div>
              <span className="text-slate-500">Missing: </span>
              <span className={col.missing_pct > 0 ? 'text-amber-400 font-semibold' : 'text-emerald-400 font-semibold'}>
                {col.missing_pct.toFixed(1)}%
              </span>
            </div>
            <div>
              <span className="text-slate-500">Rows: </span>
              <span className="text-slate-300">{col.row_count.toLocaleString()}</span>
            </div>
          </div>

          {/* Chart */}
          {col.numerical_stats && <NumericColumnViz col={col} />}
          {col.categorical_stats && <CategoricalColumnViz col={col} />}
          {!col.numerical_stats && !col.categorical_stats && (
            <p className="text-xs text-slate-500 py-4 text-center">No distribution data available</p>
          )}
        </motion.div>
      ))}
    </div>
  )
}
