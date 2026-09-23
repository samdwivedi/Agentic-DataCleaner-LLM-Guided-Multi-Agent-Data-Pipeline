"""
Query Route  POST /query
──────────────────────────
Receives a research query, runs the agent, logs everything,
persists the exchange to the API database, and returns the result.
"""

from __future__ import annotations

import time, uuid
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from agent.logger import get_logger
from backend.services.agent_service import run_agent
import backend.database as db

logger = get_logger(__name__)
router = APIRouter()


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    chat_id: Optional[str] = Field(default=None)

class QueryResponse(BaseModel):
    answer: str
    sources: list
    confidence: float
    tools_used: list[str]
    elapsed_ms: float
    message_id: str
    chat_id: str


@router.post("/query", response_model=QueryResponse, summary="Run a research query")
async def query_endpoint(req: QueryRequest):
    """
    Run the AI research agent on the given query.

    - Creates a new chat session if `chat_id` is not provided.
    - Stores user message and agent response in the database.
    - Logs tool usage timing.
    """
    t0 = time.perf_counter()

    # ── Resolve / create chat ─────────────────────────────────────────────────
    chat_id = req.chat_id or str(uuid.uuid4())
    if not db.get_chat(chat_id):
        title = req.query[:60] + ("…" if len(req.query) > 60 else "")
        db.create_chat(chat_id, title)

    logger.info("POST /query | chat=%s | query=%s", chat_id, req.query[:80])

    # ── Persist user message ──────────────────────────────────────────────────
    user_msg_id = str(uuid.uuid4())
    db.save_message(user_msg_id, chat_id, "user", req.query)

    # ── Run agent ─────────────────────────────────────────────────────────────
    try:
        result = run_agent(req.query, chat_id=chat_id)
    except Exception as exc:
        logger.exception("Unhandled agent error: %s", exc)
        raise HTTPException(status_code=500, detail=f"Agent error: {exc}")

    elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)

    # ── Persist assistant message ─────────────────────────────────────────────
    ai_msg_id = str(uuid.uuid4())
    db.save_message(
        ai_msg_id,
        chat_id,
        "assistant",
        result["answer"],
        sources=result.get("sources", []),
        confidence=result.get("confidence", 0.0),
        tools_used=result.get("tools_used", []),
    )

    # ── Log individual tool calls ─────────────────────────────────────────────
    for tool_name in result.get("tools_used", []):
        db.log_tool(ai_msg_id, tool_name, success=True, duration_ms=elapsed_ms)

    # ── Touch chat updated_at ─────────────────────────────────────────────────
    db.touch_chat(chat_id)

    logger.info("POST /query done | %.0f ms | tools=%s", elapsed_ms, result.get("tools_used"))

    return QueryResponse(
        answer=result["answer"],
        sources=result.get("sources", []),
        confidence=result.get("confidence", 0.0),
        tools_used=result.get("tools_used", []),
        elapsed_ms=elapsed_ms,
        message_id=ai_msg_id,
        chat_id=chat_id,
    )
