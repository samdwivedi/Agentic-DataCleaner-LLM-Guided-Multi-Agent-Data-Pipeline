'use client'

import { getToolMeta } from '@/lib/api'

interface ToolBadgeProps {
  tool: string
  animated?: boolean
}

export function ToolBadge({ tool, animated = false }: ToolBadgeProps) {
  const meta = getToolMeta(tool)
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border
        transition-all duration-200 ${animated ? 'animate-pulse-soft' : ''}`}
      style={{
        backgroundColor: `${meta.color}18`,
        borderColor: `${meta.color}40`,
        color: meta.color,
      }}
    >
      <span>{meta.emoji}</span>
      <span>{meta.label}</span>
    </span>
  )
}

interface ToolActivityProps {
  tools: string[]
  isThinking?: boolean
}

const THINKING_STEPS = [
  { label: 'Thinking…',         emoji: '🧠' },
  { label: 'Selecting tools…',  emoji: '⚙️' },
  { label: 'Gathering data…',   emoji: '📡' },
  { label: 'Synthesising…',     emoji: '✨' },
]

export function ToolActivity({ tools, isThinking }: ToolActivityProps) {
  if (!isThinking && tools.length === 0) return null

  return (
    <div className="flex flex-wrap items-center gap-2 mt-2">
      {isThinking && tools.length === 0 && (
        <div className="flex items-center gap-2 text-sm text-slate-400">
          <span className="animate-spin-slow">🧠</span>
          <span>Thinking…</span>
        </div>
      )}
      {tools.map((t) => (
        <ToolBadge key={t} tool={t} animated={isThinking} />
      ))}
    </div>
  )
}
