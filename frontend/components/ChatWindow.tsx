'use client'

import { useEffect, useRef, useState, useCallback } from 'react'
import { v4 as uuidv4 } from 'uuid'
import { Message, runQuery, getChatDetail } from '@/lib/api'
import { ChatBubble, TypingBubble } from './ChatBubble'
import { ChatInput } from './ChatInput'
import { motion, AnimatePresence } from 'framer-motion'
import { Loader2 } from 'lucide-react'

interface ChatWindowProps {
  chatId: string | null
  onChatCreated: (id: string) => void
}

function WelcomeScreen() {
  return (
    <motion.div 
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, ease: "easeOut" }}
      className="flex-1 flex flex-col items-center justify-center px-6 text-center h-full pt-10"
    >
      <div className="w-16 h-16 rounded-3xl bg-white/5 border border-white/10 flex items-center justify-center
        text-3xl mb-8 shadow-2xl">
        ✨
      </div>
      <h1 className="text-4xl font-semibold text-white mb-4 tracking-tight">
        How can I help you?
      </h1>
      <p className="text-slate-400 max-w-sm leading-relaxed text-lg">
        Ask any research question. I will search the web, analyze data, and synthesize a verified answer.
      </p>
    </motion.div>
  )
}

export function ChatWindow({ chatId, onChatCreated }: ChatWindowProps) {
  const [messages, setMessages] = useState<Message[]>([])
  const [loading, setLoading] = useState(false)
  const [initialLoading, setInitialLoading] = useState(false)
  const [toolsActive, setToolsActive] = useState<string[]>([])
  const [error, setError] = useState<string | null>(null)
  
  const scrollRef = useRef<HTMLDivElement>(null)
  const activeChatRef = useRef<string | null>(null)

  // Auto-scroll function
  const scrollToBottom = () => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }

  // Load chat
  useEffect(() => {
    activeChatRef.current = chatId
    if (!chatId) {
      setMessages([])
      setError(null)
      setToolsActive([])
      setLoading(false)
      setInitialLoading(false)
      return
    }
    
    setInitialLoading(true)
    getChatDetail(chatId).then((data) => {
      if (activeChatRef.current === chatId) {
        setMessages(data.messages)
        setTimeout(scrollToBottom, 100)
      }
    }).catch(() => {
      if (activeChatRef.current === chatId) setMessages([])
    }).finally(() => {
      if (activeChatRef.current === chatId) setInitialLoading(false)
    })
  }, [chatId])

  // Scroll newly added messages
  useEffect(() => {
    scrollToBottom()
  }, [messages, loading])

  const handleSend = useCallback(async (query: string) => {
    if (loading) return
    setError(null)

    const now = new Date().toISOString()
    const tempUserId = uuidv4()
    const userMsg: Message = {
      id: tempUserId,
      chat_id: chatId ?? '',
      role: 'user',
      content: query,
      sources: [],
      confidence: null,
      tools_used: [],
      created_at: now,
    }
    
    setMessages((prev) => [...prev, userMsg])
    setLoading(true)
    setToolsActive([])

    const toolTimers = [
      setTimeout(() => setToolsActive(['web_search']), 1000),
      setTimeout(() => setToolsActive(['web_search', 'database_query']), 2500),
    ]

    try {
      const result = await runQuery({ query, chat_id: chatId ?? undefined })
      toolTimers.forEach(clearTimeout)

      const resolvedChatId = result.chat_id
      if (!chatId) onChatCreated(resolvedChatId)

      const aiMsg: Message = {
        id: result.message_id,
        chat_id: resolvedChatId,
        role: 'assistant',
        content: result.answer,
        sources: result.sources,
        confidence: result.confidence,
        tools_used: result.tools_used,
        created_at: new Date().toISOString(),
      }
      setMessages((prev) => [...prev, aiMsg])
    } catch (err: any) {
      toolTimers.forEach(clearTimeout)
      setError(err?.message ?? 'Something went wrong. Is the backend running?')
    } finally {
      setLoading(false)
      setToolsActive([])
    }
  }, [chatId, loading, onChatCreated])

  return (
    <div className="relative flex flex-col h-full w-full">
      {/* Scrollable messages area */}
      <div 
        ref={scrollRef}
        className="flex-1 overflow-y-auto scroll-smooth px-4 pt-16 pb-4 w-full"
      >
        <div className="max-w-4xl mx-auto flex flex-col gap-6 min-h-full">
          {initialLoading ? (
            <div className="flex-1 flex items-center justify-center h-full">
              <Loader2 className="w-8 h-8 text-indigo-500 animate-spin" />
            </div>
          ) : messages.length === 0 && !loading ? (
            <WelcomeScreen />
          ) : (
            <>
              {messages.map((msg) => (
                <ChatBubble key={msg.id} message={msg} />
              ))}

              <AnimatePresence>
                {loading && (
                  <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, scale: 0.95 }}
                  >
                    <TypingBubble toolsActive={toolsActive} />
                  </motion.div>
                )}
              </AnimatePresence>

              {error && (
                <motion.div 
                  initial={{ opacity: 0, y: 10 }} 
                  animate={{ opacity: 1, y: 0 }}
                  className="flex items-start gap-4"
                >
                  <div className="w-8 h-8 rounded-full bg-red-500/10 flex items-center justify-center text-sm shrink-0 border border-red-500/20">
                    ⚠️
                  </div>
                  <div className="glass-panel rounded-2xl rounded-tl-sm px-6 py-5 border-red-500/20 bg-red-950/20">
                    <p className="text-sm text-red-400 font-semibold mb-1">Error Processing Request</p>
                    <p className="text-sm text-slate-300">{error}</p>
                  </div>
                </motion.div>
              )}
            </>
          )}
        </div>
      </div>

      {/* Floating Input area */}
      <ChatInput onSend={handleSend} loading={loading} />
    </div>
  )
}
