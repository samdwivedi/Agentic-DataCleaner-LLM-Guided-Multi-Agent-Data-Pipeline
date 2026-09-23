"""
FastAPI Application Entry Point
─────────────────────────────────
Start with:
    uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
Or via the helper script:
    python -m backend.main
"""

from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import time

from agent.logger import get_logger, setup_logging
import backend.database as db
from backend.routes import query as query_router
from backend.routes import history as history_router
from backend.routes import feedback as feedback_router

# ── Bootstrap logging before anything else ────────────────────────────────────
setup_logging()
logger = get_logger(__name__)

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="AI Research Agent API",
    description=(
        "Production API for the multi-tool AI research agent. "
        "Supports natural language queries, chat history, and feedback."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS (allow Next.js dev server) ──────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Request timing middleware ─────────────────────────────────────────────────
@app.middleware("http")
async def add_timing_header(request: Request, call_next):
    t0 = time.perf_counter()
    response = await call_next(request)
    elapsed = round((time.perf_counter() - t0) * 1000, 1)
    response.headers["X-Response-Time-Ms"] = str(elapsed)
    return response

# ── Global exception handler ──────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception on %s: %s", request.url, exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error": str(exc)},
    )

# ── Lifecycle ─────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def on_startup():
    logger.info("🚀 AI Research Agent API starting up…")
    db.init_db()
    logger.info("✅ Database ready")

@app.on_event("shutdown")
async def on_shutdown():
    logger.info("🛑 API shutting down")

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(query_router.router,    tags=["Query"])
app.include_router(history_router.router,  tags=["History"])
app.include_router(feedback_router.router, tags=["Feedback"])

# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["System"])
async def health():
    return {"status": "ok", "service": "AI Research Agent API", "version": "1.0.0"}

@app.get("/", tags=["System"])
async def root():
    return {
        "message": "AI Research Agent API",
        "docs": "/docs",
        "health": "/health",
    }


# ── Dev runner ────────────────────────────────────────────────────────────────
# Triggering a hot-reload so Uvicorn picks up the installed pip modules
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
