'use client'

import { useState } from 'react'
import { Copy, Check, Clock } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Message } from '@/lib/api'
import { ToolBadge } from './ToolBadge'
import { SourcesList } from './SourcesList'
import { ConfidenceBar } from './ConfidenceBar'
import { motion } from 'framer-motion'

interface ChatBubbleProps {
  message: Message
}

function formatTime(iso: string) {
  try { return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) } 
  catch { return '' }
}

export function ChatBubble({ message }: ChatBubbleProps) {
  const isUser = message.role === 'user'
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    await navigator.clipboard.writeText(message.content)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  // ── User bubble ───────────────────────────────────────────────────────────
  if (isUser) {
    return (
      <motion.div 
        initial={{ opacity: 0, y: 15 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: "easeOut" }}
        className="flex justify-end w-full"
      >
        <div className="max-w-[80%] flex flex-col items-end group">
          <div className="px-5 py-3.5 rounded-3xl rounded-tr-sm text-[15px] leading-relaxed
              bg-gradient-to-br from-indigo-500 to-purple-600 text-white shadow-lg shadow-indigo-500/20"
          >
            {message.content}
          </div>
          <div className="opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-end gap-1.5 mt-1.5 pr-2">
            <Clock className="w-3 h-3 text-slate-500" />
            <span suppressHydrationWarning className="text-[11px] text-slate-500 font-medium tracking-wide">{formatTime(message.created_at)}</span>
          </div>
        </div>
      </motion.div>
    )
  }

  // ── Assistant bubble ────────────────────────────────────────────────────
  return (
    <motion.div 
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: "easeOut" }}
      className="flex gap-4 group w-full"
    >
      {/* Avatar */}
      <div className="shrink-0 mt-1">
        <div className="w-8 h-8 rounded-full border border-white/10 bg-white/5 flex items-center justify-center
          text-sm shadow-xl backdrop-blur-md">
          ✨
        </div>
      </div>

      <div className="flex-1 min-w-0 max-w-[90%]">
        {/* Tools used */}
        {message.tools_used && message.tools_used.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-3">
            {message.tools_used.map((t, idx) => (
              <ToolBadge key={`${t}-${idx}`} tool={t} />
            ))}
          </div>
        )}

        {/* Main Content Area (Glassmorphism layout) */}
        <div className="glass-panel p-5 rounded-3xl rounded-tl-sm text-white">
          <div className="prose prose-invert max-w-none text-[15px] leading-relaxed">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {message.content}
            </ReactMarkdown>
          </div>

          <div className="mt-6 flex flex-col gap-4">
            {/* Confidence Progress Bar */}
            {message.confidence !== null && message.confidence !== undefined && message.confidence > 0 && (
              <div className="max-w-sm">
                <ConfidenceBar score={message.confidence} />
              </div>
            )}

            {/* Source references (rendered as chic minimal cards) */}
            <SourcesList sources={message.sources} />
          </div>
        </div>

        {/* Footer actions */}
        <div className="opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-4 mt-3 pl-1">
          <button
            onClick={handleCopy}
            title="Copy response"
            className="flex items-center gap-1.5 text-xs font-medium text-slate-500 hover:text-white transition-colors"
          >
            {copied ? <Check className="w-3.5 h-3.5 text-green-400" /> : <Copy className="w-3.5 h-3.5" />}
            {copied ? <span className="text-green-400">Copied</span> : <span>Copy</span>}
          </button>

          <div className="flex items-center gap-1.5 mt-0.5">
            <Clock className="w-3 h-3 text-slate-500" />
            <span suppressHydrationWarning className="text-[11px] text-slate-500 font-medium tracking-wide">{formatTime(message.created_at)}</span>
          </div>
        </div>
      </div>
    </motion.div>
  )
}

/* ── Animated Agent Typing UI ───────────────────────────────────────────── */
interface TypingBubbleProps {
  toolsActive: string[]
}

export function TypingBubble({ toolsActive }: TypingBubbleProps) {
  let label = 'Thinking'
  if (toolsActive.length > 0) {
    const latestTool = toolsActive[toolsActive.length - 1]
    if (latestTool === 'web_search' || latestTool === 'web_scraper') label = 'Searching the web'
    else if (latestTool === 'calculator' || latestTool === 'code_executor') label = 'Calculating'
    else if (latestTool === 'database_query') label = 'Analyzing context'
    else label = `Using ${latestTool.replace('_', ' ')}`
  }

  return (
    <div className="flex gap-4">
      <div className="shrink-0 mt-1">
        <div className="w-8 h-8 rounded-full border border-indigo-500/30 bg-indigo-500/10 flex items-center justify-center text-sm shadow-xl shadow-indigo-500/20 backdrop-blur-md">
          <motion.div animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 4, ease: "linear" }}>
            ✨
          </motion.div>
        </div>
      </div>
      <div className="flex flex-col gap-3">
        <div className="flex items-center gap-3 h-8">
          <span className="text-[15px] font-medium text-indigo-300 tracking-wide">{label}</span>
          <div className="flex gap-1.5 mt-1.5">
            <motion.span animate={{ opacity: [0.3, 1, 0.3] }} transition={{ repeat: Infinity, duration: 1.4, delay: 0 }} className="w-1.5 h-1.5 bg-indigo-400 rounded-full" />
            <motion.span animate={{ opacity: [0.3, 1, 0.3] }} transition={{ repeat: Infinity, duration: 1.4, delay: 0.2 }} className="w-1.5 h-1.5 bg-indigo-400 rounded-full" />
            <motion.span animate={{ opacity: [0.3, 1, 0.3] }} transition={{ repeat: Infinity, duration: 1.4, delay: 0.4 }} className="w-1.5 h-1.5 bg-indigo-400 rounded-full" />
          </div>
        </div>
        {toolsActive.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {toolsActive.map((t, i) => <ToolBadge key={`${t}-${i}`} tool={t} animated />)}
          </div>
        )}
      </div>
    </div>
  )
}
