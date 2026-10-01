'use client'

import { motion } from 'framer-motion'
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts'

interface DatasetMeta {
  row_count: number
  column_count: number
  total_cells: number
  total_missing: number
  total_missing_pct: number
  memory_usage_bytes: number
  numeric_column_count: number
  categorical_column_count: number
  datetime_column_count: number
  boolean_column_count: number
  other_column_count: number
  dtypes_summary: Record<string, number>
}

interface DuplicateInfo {
  duplicate_row_count: number
  duplicate_row_pct: number
  has_duplicates: boolean
}

interface DatasetOverviewProps {
  meta: DatasetMeta
  duplicates: DuplicateInfo
}

const TYPE_COLORS: Record<string, string> = {
  numeric_int: '#818cf8',
  numeric_float: '#a78bfa',
  numeric: '#818cf8',
  categorical: '#38bdf8',
  boolean: '#fbbf24',
  datetime: '#f472b6',
  other: '#64748b',
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function CustomPieTooltip({ active, payload }: any) {
  if (!active || !payload?.[0]) return null
  const d = payload[0]
  return (
    <div className="bg-slate-900/95 border border-slate-700 backdrop-blur-xl rounded-xl px-3 py-2 shadow-xl text-xs">
      <p className="text-white font-semibold">{d.name}</p>
      <p className="text-slate-300">{d.value} column{d.value !== 1 ? 's' : ''}</p>
    </div>
  )
}

export function DatasetOverview({ meta, duplicates }: DatasetOverviewProps) {
  // Build pie chart data from column type counts
  const typeData = [
    { name: 'Numeric (int)', value: meta.numeric_column_count > 0 ? Math.floor(meta.numeric_column_count / 2) || meta.numeric_column_count : 0, color: TYPE_COLORS.numeric_int },
    { name: 'Numeric (float)', value: meta.numeric_column_count > 0 ? Math.ceil(meta.numeric_column_count / 2) : 0, color: TYPE_COLORS.numeric_float },
    { name: 'Categorical', value: meta.categorical_column_count, color: TYPE_COLORS.categorical },
    { name: 'Boolean', value: meta.boolean_column_count, color: TYPE_COLORS.boolean },
    { name: 'Datetime', value: meta.datetime_column_count, color: TYPE_COLORS.datetime },
    { name: 'Other', value: meta.other_column_count, color: TYPE_COLORS.other },
  ].filter(d => d.value > 0)

  // If we have dtypes_summary, prefer that for more accuracy
  const dtypesData = Object.entries(meta.dtypes_summary || {}).map(([dtype, count]) => ({
    name: dtype,
    value: count,
    color: dtype.includes('int') ? '#818cf8' :
           dtype.includes('float') ? '#a78bfa' :
           dtype.includes('object') ? '#38bdf8' :
           dtype.includes('bool') ? '#fbbf24' :
           dtype.includes('datetime') ? '#f472b6' :
           '#64748b',
  }))

  const pieData = dtypesData.length > 0 ? dtypesData : typeData

  const statItems = [
    { label: 'Rows', value: meta.row_count.toLocaleString(), color: 'text-white' },
    { label: 'Columns', value: meta.column_count.toLocaleString(), color: 'text-white' },
    { label: 'Total Cells', value: meta.total_cells.toLocaleString(), color: 'text-slate-300' },
    { label: 'Missing', value: `${meta.total_missing.toLocaleString()} (${meta.total_missing_pct.toFixed(1)}%)`, color: meta.total_missing_pct > 10 ? 'text-red-400' : 'text-emerald-400' },
    { label: 'Duplicates', value: `${duplicates.duplicate_row_count.toLocaleString()} (${duplicates.duplicate_row_pct.toFixed(1)}%)`, color: duplicates.has_duplicates ? 'text-amber-400' : 'text-emerald-400' },
    { label: 'Memory', value: formatBytes(meta.memory_usage_bytes), color: 'text-slate-300' },
  ]

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="grid grid-cols-1 md:grid-cols-[1fr_200px] gap-6 items-center"
    >
      {/* Stats grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
        {statItems.map((item, i) => (
          <motion.div
            key={item.label}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.06 }}
            className="bg-black/20 rounded-xl p-3 border border-white/5"
          >
            <p className="text-[10px] text-slate-500 uppercase tracking-wider font-semibold">{item.label}</p>
            <p className={`text-base font-bold mt-1 ${item.color}`}>{item.value}</p>
          </motion.div>
        ))}
      </div>

      {/* Dtype distribution pie */}
      <div className="flex flex-col items-center">
        <p className="text-[10px] text-slate-500 uppercase tracking-wider font-semibold mb-2">Column Types</p>
        <ResponsiveContainer width={160} height={160}>
          <PieChart>
            <Pie
              data={pieData}
              cx="50%"
              cy="50%"
              innerRadius={40}
              outerRadius={65}
              paddingAngle={3}
              dataKey="value"
              stroke="none"
            >
              {pieData.map((entry, index) => (
                <Cell key={index} fill={entry.color} fillOpacity={0.8} />
              ))}
            </Pie>
            <Tooltip content={<CustomPieTooltip />} />
          </PieChart>
        </ResponsiveContainer>
        <div className="flex flex-wrap justify-center gap-x-3 gap-y-1 mt-1">
          {pieData.map(d => (
            <span key={d.name} className="flex items-center gap-1 text-[10px] text-slate-400">
              <span className="w-2 h-2 rounded-full" style={{ background: d.color }} />
              {d.name}
            </span>
          ))}
        </div>
      </div>
    </motion.div>
  )
}
