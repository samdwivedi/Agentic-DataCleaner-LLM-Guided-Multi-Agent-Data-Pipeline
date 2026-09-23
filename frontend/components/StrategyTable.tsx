import { AlertTriangle, CheckCircle, Info } from 'lucide-react'

export function StrategyTable({ actions }: { actions: any[] }) {
  if (!actions || actions.length === 0) {
    return <div className="text-slate-400 py-8 text-center bg-slate-900/50 rounded-2xl">No actions recommended.</div>
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left border-collapse">
        <thead>
          <tr className="border-b border-slate-800 text-slate-400 text-sm">
            <th className="py-4 px-4 font-medium">Column</th>
            <th className="py-4 px-4 font-medium">Action</th>
            <th className="py-4 px-4 font-medium max-w-md">Reasoning</th>
            <th className="py-4 px-4 font-medium text-right">Confidence</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800/50">
          {actions.map((act, i) => (
            <tr key={i} className="hover:bg-slate-800/20 transition-colors group">
              <td className="py-4 px-4 font-mono text-indigo-300">{act.column}</td>
              <td className="py-4 px-4">
                <span className="px-3 py-1 bg-slate-800 text-slate-200 rounded-full text-xs font-medium border border-slate-700">
                  {act.action}
                </span>
              </td>
              <td className="py-4 px-4 text-slate-300 max-w-md text-sm leading-relaxed">
                {act.reason}
              </td>
              <td className="py-4 px-4 text-right">
                <div className="flex items-center justify-end gap-2">
                  <div className="w-16 h-2 bg-slate-800 rounded-full overflow-hidden">
                    <div 
                      className="h-full bg-gradient-to-r from-amber-500 to-emerald-500 rounded-full" 
                      style={{ width: `${Math.round(act.confidence * 100)}%` }}
                    />
                  </div>
                  <span className="text-xs font-bold text-slate-400 w-8">{Math.round(act.confidence * 100)}%</span>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
