import { CheckCircle2, XCircle, ArrowRight } from 'lucide-react'

export function ExecutionLog({ logs }: { logs: any[] }) {
  if (!logs || logs.length === 0) {
    return <div className="text-slate-400 py-8 text-center bg-slate-900/50 rounded-2xl border border-slate-800">No execution logs found.</div>
  }

  return (
    <div className="space-y-4">
      {logs.map((log, i) => (
        <div key={i} className="bg-slate-900/50 border border-slate-800 rounded-2xl p-5 hover:border-slate-700 transition-colors">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-3">
              {log.execution_status === 'success' ? (
                <CheckCircle2 className="text-emerald-500 w-5 h-5" />
              ) : (
                <XCircle className="text-rose-500 w-5 h-5" />
              )}
              <h4 className="font-semibold text-white flex items-center gap-2">
                <span className="font-mono text-indigo-300">{log.column}</span>
                <span className="text-slate-500 text-sm px-2">›</span>
                <span className="text-slate-300">{log.action}</span>
              </h4>
            </div>
            <span className={`text-xs font-medium px-2.5 py-1 rounded-full ${
              log.execution_status === 'success' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
            }`}>
              {log.execution_status.toUpperCase()}
            </span>
          </div>
          
          <div className="grid grid-cols-2 gap-4 mt-4 bg-black/20 rounded-xl p-4 border border-white/5">
            <div>
              <p className="text-xs text-slate-500 uppercase tracking-wider mb-2 font-semibold">Impact</p>
              <div className="flex gap-4">
                <div>
                  <p className="text-xl font-bold text-white">{log.rows_affected}</p>
                  <p className="text-xs text-slate-400">Rows</p>
                </div>
                <div>
                  <p className="text-xl font-bold text-indigo-300">{log.values_changed}</p>
                  <p className="text-xs text-slate-400">Values</p>
                </div>
              </div>
            </div>
            
            {(log.before_state && log.after_state) && (
              <div>
                <p className="text-xs text-slate-500 uppercase tracking-wider mb-2 font-semibold">Distribution Shift</p>
                <div className="flex items-center gap-3">
                  <div className="text-sm">
                    <span className="text-slate-400 inline-block w-8">Null:</span>
                    <span className="text-rose-300 font-mono">{log.before_state.null_count ?? '-'}</span>
                    <ArrowRight className="inline w-3 h-3 text-slate-600 mx-1" />
                    <span className="text-emerald-300 font-mono">{log.after_state.null_count ?? '-'}</span>
                  </div>
                </div>
                {log.before_state.mean !== undefined && log.after_state.mean !== undefined && (
                  <div className="flex items-center gap-3 mt-1">
                    <div className="text-sm">
                      <span className="text-slate-400 inline-block w-8">Mean:</span>
                      <span className="text-slate-300 font-mono">{log.before_state.mean?.toFixed(2) ?? '-'}</span>
                      <ArrowRight className="inline w-3 h-3 text-slate-600 mx-1" />
                      <span className="text-slate-300 font-mono">{log.after_state.mean?.toFixed(2) ?? '-'}</span>
                    </div>
                  </div>
                )}
              </div>
            )}
            
            {log.error_message && (
              <div className="col-span-2 mt-2 text-sm text-rose-400 bg-rose-500/10 p-3 rounded-lg border border-rose-500/20">
                {log.error_message}
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}
