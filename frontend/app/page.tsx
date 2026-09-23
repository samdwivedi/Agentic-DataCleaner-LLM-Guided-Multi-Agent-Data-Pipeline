'use client'

import { useState, useCallback, useEffect } from 'react'
import { Sidebar } from '@/components/Sidebar'
import { ChatWindow } from '@/components/ChatWindow'
import { Menu, X } from 'lucide-react'
import { AnimatePresence, motion } from 'framer-motion'

export default function Home() {
  const [activeChatId, setActiveChatId] = useState<string | null>(null)
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [isMobile, setIsMobile] = useState(false)

  useEffect(() => {
    const handleResize = () => setIsMobile(window.innerWidth < 768)
    handleResize()
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  const handleNewChat = useCallback(() => {
    setActiveChatId(null)
    if (typeof window !== 'undefined') {
      if (window.innerWidth < 768) setSidebarOpen(false)
      setTimeout(() => document.getElementById('query-input')?.focus(), 50)
    }
  }, [])

  const handleChatCreated = useCallback((id: string) => {
    setActiveChatId(id)
  }, [])

  const handleSelectChat = useCallback((id: string) => {
    setActiveChatId(id)
    if (typeof window !== 'undefined' && window.innerWidth < 768) setSidebarOpen(false)
  }, [])

  return (
    <div className="flex relative h-screen w-full overflow-hidden text-slate-200">
      
      {/* ── Mobile Sidebar Overlay ── */}
      <AnimatePresence>
        {sidebarOpen && isMobile && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 md:hidden"
            onClick={() => setSidebarOpen(false)}
          />
        )}
      </AnimatePresence>

      {/* ── Framer Sidebar ── */}
      <motion.div
        className="fixed md:relative z-50 h-full w-72 shrink-0 md:translate-x-0"
        initial={{ x: '-100%' }}
        animate={{ x: !isMobile ? 0 : (sidebarOpen ? 0 : '-100%') }}
        transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
      >
        <Sidebar
          activeChatId={activeChatId}
          onSelectChat={handleSelectChat}
          onNewChat={handleNewChat}
        />
      </motion.div>

      {/* ── Main Chat Composition ── */}
      <div className="flex flex-col flex-1 min-w-0 h-full relative z-10 transition-all duration-300">
        
        {/* Topbar (Mobile Hamburger & Quick Controls) */}
        <header className="absolute top-0 left-0 right-0 z-30 flex items-center justify-between p-4 bg-gradient-to-b from-black/50 to-transparent pointer-events-none">
          <button
            onClick={() => setSidebarOpen(true)}
            className="p-2.5 rounded-full border border-white/10 bg-black/20 backdrop-blur-md text-white hover:bg-white/10
              transition-all duration-300 pointer-events-auto md:hidden"
          >
            <Menu className="w-5 h-5" />
          </button>
        </header>

        <div className="flex-1 w-full h-full relative">
          <ChatWindow
            chatId={activeChatId}
            onChatCreated={handleChatCreated}
          />
        </div>

      </div>
    </div>
  )
}
