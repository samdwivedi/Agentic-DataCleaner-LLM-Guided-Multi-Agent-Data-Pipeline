'use client'

import { useEffect, useState } from 'react'
import { Plus, MessageSquare, Clock, ChevronRight, Loader2 } from 'lucide-react'
import { Chat, getHistory } from '@/lib/api'
import clsx from 'clsx'
import { motion } from 'framer-motion'

interface SidebarProps {
  activeChatId: string | null
  onSelectChat: (id: string) => void
  onNewChat: () => void
}

function timeAgo(iso: string): string {
  try {
    const diff = Date.now() - new Date(iso).getTime()
    const mins = Math.floor(diff / 60000)
    if (mins < 1)  return 'just now'
    if (mins < 60) return `${mins}m ago`
    const hrs = Math.floor(mins / 60)
    if (hrs < 24)  return `${hrs}h ago`
    return `${Math.floor(hrs / 24)}d ago`
  } catch { return '' }
}

export function Sidebar({ activeChatId, onSelectChat, onNewChat }: SidebarProps) {
  const [chats, setChats] = useState<Chat[]>([])
  const [loading, setLoading] = useState(true)

  const reload = async () => {
    try {
      const data = await getHistory()
      setChats(data.chats)
    } catch { } 
    finally { setLoading(false) }
  }

  useEffect(() => {
    reload()
    const id = setInterval(reload, 10000)
    return () => clearInterval(id)
  }, [activeChatId])

  return (
    <aside className="h-full w-full flex flex-col glass-panel border-r border-white/5 bg-black/40">
      
      {/* Header Profile */}
      <div className="flex items-center gap-3 px-5 py-6">
        <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-indigo-500 to-purple-500 flex items-center justify-center shadow-lg shadow-purple-500/20 text-white">
          ✨
        </div>
        <div>
          <h1 className="font-semibold text-sm tracking-wide text-white">AI Research</h1>
          <p className="text-[11px] text-slate-400 font-medium">Enterprise Agent</p>
        </div>
      </div>

      {/* New Chat Area */}
      <div className="px-4 pb-4">
        <motion.button
          whileHover={{ scale: 1.03 }}
          whileTap={{ scale: 0.97 }}
          onClick={onNewChat}
          className="w-full flex items-center justify-center gap-2 px-4 py-2.5 btn-glow rounded-xl text-sm font-medium text-white shadow-xl shadow-indigo-500/20"
        >
          <Plus className="w-4 h-4" />
          <span>New Chat</span>
        </motion.button>
      </div>

      {/* Chat History List */}
      <div className="flex-1 overflow-y-auto px-3 pb-6 flex flex-col gap-1">
        {loading ? (
          <div className="flex items-center justify-center py-6 gap-2 text-slate-400">
            <Loader2 className="w-4 h-4 animate-spin text-indigo-400" />
            <span className="text-sm">Loading...</span>
          </div>
        ) : chats.length === 0 ? (
          <div className="text-center py-10 text-slate-500">
            <MessageSquare className="w-6 h-6 mx-auto mb-2 opacity-50" />
            <p className="text-sm font-medium">No history</p>
          </div>
        ) : (
          <>
            <p className="text-[10px] font-bold text-slate-500 uppercase tracking-widest px-3 py-2">
              Recent Chats
            </p>
            {chats.map((chat) => {
              const active = activeChatId === chat.id
              return (
                <button
                  key={chat.id}
                  onClick={() => onSelectChat(chat.id)}
                  className={clsx(
                    'group relative w-full text-left px-3 py-3 rounded-xl transition-all duration-300 flex items-start gap-3',
                    active 
                      ? 'bg-white/10 text-white border border-white/10 shadow-lg' 
                      : 'hover:bg-white/5 text-slate-400 hover:text-slate-200 border border-transparent'
                  )}
                >
                  <MessageSquare className={clsx(
                    'w-4 h-4 mt-0.5 shrink-0 transition-colors',
                    active ? 'text-indigo-400' : 'text-slate-500 group-hover:text-slate-300'
                  )} />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm truncate font-medium leading-tight">
                      {chat.title}
                    </p>
                    <div className="flex items-center gap-1.5 mt-1.5">
                      <Clock className="w-3 h-3 text-slate-500" />
                      <span suppressHydrationWarning className="text-[10px] font-medium text-slate-500 uppercase tracking-wider">{timeAgo(chat.updated_at)}</span>
                    </div>
                  </div>
                  {active && (
                    <motion.div layoutId="sidebar-active" className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-8 bg-indigo-500 rounded-r-lg" />
                  )}
                </button>
              )
            })}
          </>
        )}
      </div>

    </aside>
  )
}
