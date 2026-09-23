// Central API client for the AI Research Agent backend

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export interface QueryRequest {
  query: string
  chat_id?: string
}

export interface Source {
  url: string
  tool: string
}

export interface QueryResponse {
  answer: string
  sources: Source[]
  confidence: number
  tools_used: string[]
  elapsed_ms: number
  message_id: string
  chat_id: string
}

export interface Message {
  id: string
  chat_id: string
  role: 'user' | 'assistant'
  content: string
  sources: Source[]
  confidence: number | null
  tools_used: string[]
  created_at: string
}

export interface Chat {
  id: string
  title: string
  created_at: string
  updated_at: string
}

export interface HistoryResponse {
  chats: Chat[]
  total: number
}

export interface ChatDetailResponse {
  chat: Chat
  messages: Message[]
  total: number
}

export interface FeedbackRequest {
  message_id: string
  rating: 'like' | 'dislike'
  comment?: string
}

// ── Raw fetch helpers ──────────────────────────────────────────────────────

async function apiFetch<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE}${path}`
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  })
  if (!res.ok) {
    const errorText = await res.text()
    throw new Error(`API ${res.status}: ${errorText}`)
  }
  return res.json() as Promise<T>
}

// ── API calls ──────────────────────────────────────────────────────────────

export async function runQuery(req: QueryRequest): Promise<QueryResponse> {
  return apiFetch<QueryResponse>('/query', {
    method: 'POST',
    body: JSON.stringify(req),
  })
}

export async function getHistory(): Promise<HistoryResponse> {
  return apiFetch<HistoryResponse>('/history')
}

export async function getChatDetail(chatId: string): Promise<ChatDetailResponse> {
  return apiFetch<ChatDetailResponse>(`/history/${chatId}`)
}

export async function submitFeedback(req: FeedbackRequest): Promise<void> {
  await apiFetch('/feedback', {
    method: 'POST',
    body: JSON.stringify(req),
  })
}

// ── Tool metadata ──────────────────────────────────────────────────────────

export const TOOL_META: Record<string, { label: string; emoji: string; color: string }> = {
  web_search:      { label: 'Web Search',    emoji: '🔍', color: '#4f8ef7' },
  web_scraper:     { label: 'Web Scraper',   emoji: '🌐', color: '#43c59e' },
  calculator:      { label: 'Calculator',    emoji: '🧮', color: '#f7a844' },
  database_query:  { label: 'DB Query',      emoji: '🗄️', color: '#b06ef7' },
  database_schema: { label: 'DB Schema',     emoji: '📂', color: '#7b6ef7' },
  code_executor:   { label: 'Code Executor', emoji: '🐍', color: '#f7647a' },
  info:            { label: 'Info',          emoji: 'ℹ️', color: '#94a3b8' },
}

export function getToolMeta(name: string) {
  return TOOL_META[name] ?? { label: name, emoji: '⚙️', color: '#6366f1' }
}

export function formatConfidence(score: number): string {
  return `${Math.round(score * 100)}%`
}

export function confidenceLabel(score: number): string {
  if (score >= 0.85) return 'High'
  if (score >= 0.6)  return 'Medium'
  return 'Low'
}

export function confidenceColor(score: number): string {
  if (score >= 0.85) return '#22c55e'
  if (score >= 0.6)  return '#f59e0b'
  return '#ef4444'
}
