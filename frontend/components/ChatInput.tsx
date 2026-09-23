'use client'

import { useState, useRef, KeyboardEvent } from 'react'
import { Send, Loader2, Sparkles } from 'lucide-react'
import { motion } from 'framer-motion'

interface ChatInputProps {
  onSend: (query: string) => void
  loading: boolean
}

export function ChatInput({ onSend, loading }: ChatInputProps) {
  const [value, setValue] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const canSend = value.trim().length > 0 && !loading

  const handleSend = () => {
    if (!canSend) return
    onSend(value.trim())
    setValue('')
    if (textareaRef.current) textareaRef.current.style.height = 'auto'
  }

  const handleKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleInput = () => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 180)}px`
  }

  return (
    <div className="shrink-0 w-full bg-gradient-to-t from-black via-black/80 to-transparent pt-12 pb-6 px-4 z-50">
      <div className="max-w-4xl mx-auto">
        <motion.div 
          className="relative flex items-end gap-3 rounded-3xl p-2 pl-4
            bg-white/[0.04] backdrop-blur-xl border border-white/10
            shadow-[0_8px_32px_0_rgba(0,0,0,0.4)]
            focus-within:bg-white/[0.08] focus-within:border-indigo-500/50 focus-within:shadow-[0_0_30px_rgba(99,102,241,0.2)]
            transition-all duration-300 ease-out"
          initial={{ y: 20, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ duration: 0.5, ease: "easeOut" }}
        >
          <div className="shrink-0 mb-3 ml-1 text-slate-400 p-1">
            <Sparkles className="w-5 h-5" />
          </div>
          
          <textarea
            id="query-input"
            ref={textareaRef}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onInput={handleInput}
            onKeyDown={handleKey}
            disabled={loading}
            rows={1}
            placeholder="Ask anything..."
            className="flex-1 max-h-[180px] bg-transparent text-[15px] text-white placeholder-slate-500
              resize-none outline-none overflow-y-auto mb-3.5 mt-3.5 leading-relaxed
              disabled:opacity-50"
            style={{ minHeight: '26px' }}
          />

          <motion.button
            whileHover={canSend ? { scale: 1.05 } : {}}
            whileTap={canSend ? { scale: 0.95 } : {}}
            onClick={handleSend}
            disabled={!canSend}
            className={`shrink-0 w-11 h-11 rounded-2xl flex items-center justify-center transition-all duration-300 mb-1 mr-1
              ${canSend ? 'bg-white text-black shadow-lg shadow-white/20' : 'bg-white/5 text-slate-600 cursor-not-allowed'}`}
          >
            {loading ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <Send className="w-5 h-5" />
            )}
          </motion.button>
        </motion.div>

        <p className="text-center text-[11px] text-slate-500 mt-4 tracking-wide font-medium font-sans">
          AI agents can make mistakes. Always verify the provided sources.
        </p>
      </div>
    </div>
  )
}
