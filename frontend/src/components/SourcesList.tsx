'use client'

import { Source, getToolMeta } from '@/lib/api'
import { ExternalLink } from 'lucide-react'

interface SourcesListProps {
  sources: Source[]
}

export function SourcesList({ sources }: SourcesListProps) {
  if (!sources || sources.length === 0) return null

  return (
    <div className="mt-4">
      <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
        Sources
      </p>
      <div className="flex flex-col gap-1.5">
        {sources.map((s, i) => {
          const meta = getToolMeta(s.tool)
          let hostname = ''
          try { hostname = new URL(s.url).hostname.replace('www.', '') } catch {}
          return (
            <a
              key={i}
              href={s.url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 px-3 py-2 rounded-lg border border-surface-border
                bg-surface-card hover:bg-surface-hover hover:border-brand-500/40
                transition-all duration-200 group text-sm"
            >
              <span className="text-base shrink-0">{meta.emoji}</span>
              <span className="text-slate-300 group-hover:text-white truncate flex-1 font-mono text-xs">
                {hostname || s.url}
              </span>
              <ExternalLink className="w-3.5 h-3.5 text-slate-600 group-hover:text-brand-400 shrink-0 transition-colors" />
            </a>
          )
        })}
      </div>
    </div>
  )
}
