# 🔬 AI Research Agent — Full-Stack

A production-ready multi-tool AI research agent with a **FastAPI backend** and **Next.js 14 frontend**.

## Architecture

```
ai-research-agent/
  agent/                 # Core agent (untouched)
  │  tools/              # Web search, scraper, calculator, DB, code executor
  │  logger.py           # Centralised rotating-file logger
  │  memory.py           # Short + long-term memory (FAISS)
  │
  backend/               # FastAPI API layer
  │  main.py             # App entry point (uvicorn)
  │  database.py         # SQLite: chats / messages / tool_logs / feedback
  │  routes/
  │  │  query.py         # POST /query
  │  │  history.py       # GET  /history, GET /history/{chat_id}
  │  │  feedback.py      # POST /feedback
  │  services/
  │     agent_service.py # run_agent() wrapper
  │
  frontend/              # Next.js 14 App Router + Tailwind CSS
  │  app/
  │  │  layout.tsx       # Root layout + fonts
  │  │  page.tsx         # Main page (sidebar + chat)
  │  │  globals.css      # Dark theme, prose styles, animations
  │  components/
  │  │  Sidebar.tsx      # Chat history, new chat button
  │  │  ChatWindow.tsx   # Message orchestrator + auto-scroll
  │  │  ChatBubble.tsx   # User / AI bubbles + copy + feedback
  │  │  ChatInput.tsx    # Auto-growing textarea + quick examples
  │  │  ToolBadge.tsx    # Colour-coded pill badges per tool
  │  │  SourcesList.tsx  # Clickable source links
  │  │  ConfidenceBar.tsx# Animated confidence score bar
  │  lib/
  │     api.ts           # Typed API client + tool metadata
  │
  config.py              # Central configuration (adds LOG_* keys)
  requirements.txt       # Python deps (now includes fastapi, uvicorn)
  logs/                  # Auto-created: agent.log (rotating, 5 MB × 3)
  data/                  # Auto-created: research.db + api.db
```

---

## Quick Start

### 1 — Python backend

```bash
# Install / update Python deps
pip install -r requirements.txt

# Copy env and add your OpenAI key
cp .env.example .env
# Edit .env → set OPENAI_API_KEY=sk-...

# Start FastAPI (auto-reload for dev)
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Swagger UI → http://localhost:8000/docs  
Health check → http://localhost:8000/health

---

### 2 — Next.js frontend

```bash
cd frontend
npm install
npm run dev
```

Open → http://localhost:3000

---

## API Endpoints

| Method | Path               | Description                        |
|--------|--------------------|------------------------------------|
| POST   | `/query`           | Run a research query               |
| GET    | `/history`         | List all chat sessions             |
| GET    | `/history/{id}`    | Messages for a specific chat       |
| POST   | `/feedback`        | Submit like / dislike rating       |
| GET    | `/health`          | Health check                       |
| GET    | `/docs`            | Interactive Swagger UI             |

### POST `/query` example

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the current generative AI market size?"}'
```

Response:
```json
{
  "answer": "...",
  "sources": [{"url": "...", "tool": "web_search"}],
  "confidence": 0.87,
  "tools_used": ["web_search", "database_query"],
  "elapsed_ms": 3241.5,
  "message_id": "uuid",
  "chat_id": "uuid"
}
```

---

## Features

### Backend
- ✅ Async FastAPI with CORS for Next.js dev server
- ✅ Request timing (`X-Response-Time-Ms` header)
- ✅ Global exception handler with JSON error responses
- ✅ SQLite persistence: chats, messages, tool_logs, feedback
- ✅ Rotating log file (`logs/agent.log`, 5 MB × 3)
- ✅ Stub mode when `OPENAI_API_KEY` is not set (for UI dev)

### Frontend
- ✅ Dark glassmorphism UI with brand purple palette
- ✅ Chat sidebar with auto-refreshing history
- ✅ Markdown-rendered AI responses (tables, code, bold, links)
- ✅ Animated typing indicator with live tool badges
- ✅ Confidence score bar (green / amber / red)
- ✅ Clickable source links with favicon-style tool icons
- ✅ Copy response button + per-message feedback (👍 / 👎)
- ✅ Quick example query buttons
- ✅ Auto-scroll to latest message
- ✅ Responsive (mobile sidebar overlay)

---

## Logs

Logs are written to `logs/agent.log` (rotated at 5 MB, 3 backups).

```
2026-04-04 09:50:00  INFO      backend.routes.query – POST /query | chat=uuid | query=…
2026-04-04 09:50:03  INFO      backend.services.agent_service – ✅ Query done in 3241 ms
2026-04-04 09:50:03  INFO      backend.routes.query – POST /query done | 3241.5 ms | tools=['web_search']
```

Set `LOG_LEVEL=DEBUG` in `.env` for verbose output including all tool calls.

---

## Environment Variables

| Variable              | Default              | Description                   |
|-----------------------|----------------------|-------------------------------|
| `OPENAI_API_KEY`      | *(required)*         | OpenAI API key                |
| `OPENAI_MODEL`        | `gpt-4o-mini`        | LLM model                     |
| `LOG_LEVEL`           | `INFO`               | `DEBUG\|INFO\|WARNING\|ERROR` |
| `MAX_SEARCH_RESULTS`  | `5`                  | Max web search results        |
| `DATABASE_PATH`       | `./data/research.db` | Agent knowledge DB path       |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Backend URL (frontend)     |
