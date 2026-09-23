"""
History Route  GET /history  &  GET /history/{chat_id}
────────────────────────────────────────────────────────
Returns past chat sessions and their messages.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from agent.logger import get_logger
import backend.database as db

logger = get_logger(__name__)
router = APIRouter()


@router.get("/history", summary="List all chat sessions")
async def list_history():
    """Return all chat sessions ordered by most recent first."""
    chats = db.list_chats()
    logger.info("GET /history → %d chats", len(chats))
    return {"chats": chats, "total": len(chats)}


@router.get("/history/{chat_id}", summary="Get messages for a chat session")
async def get_chat_history(chat_id: str):
    """Return all messages in a specific chat session."""
    chat = db.get_chat(chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    messages = db.get_messages(chat_id)
    logger.info("GET /history/%s → %d messages", chat_id, len(messages))
    return {"chat": chat, "messages": messages, "total": len(messages)}
