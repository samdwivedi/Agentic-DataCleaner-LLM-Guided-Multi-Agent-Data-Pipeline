import { ReactNode } from 'react'
import { motion } from 'framer-motion'

export function MetricCard({ title, value, icon }: { title: string, value: number | string | undefined, icon?: ReactNode }) {
  return (
    <motion.div 
      whileHover={{ scale: 1.05, y: -5 }}
      whileTap={{ scale: 0.95 }}
      className="bg-slate-900/40 border border-slate-800 rounded-3xl p-6 flex items-center gap-4 hover:bg-slate-800/60 hover:border-indigo-500/30 hover:shadow-lg hover:shadow-indigo-500/10 transition-all cursor-default"
    >
      {icon && (
        <div className="w-12 h-12 rounded-2xl bg-indigo-500/10 text-indigo-400 flex items-center justify-center shrink-0">
          {icon}
        </div>
      )}
      <div>
        <p className="text-slate-400 text-sm font-medium mb-1">{title}</p>
        <p className="text-2xl font-bold text-white">{value ?? '-'}</p>
      </div>
    </motion.div>
  )
}
