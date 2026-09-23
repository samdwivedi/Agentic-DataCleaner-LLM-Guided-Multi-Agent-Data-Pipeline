"""
Feedback Route  POST /feedback
───────────────────────────────
Stores user like / dislike feedback for agent responses.
"""

from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from agent.logger import get_logger
import backend.database as db

logger = get_logger(__name__)
router = APIRouter()


class FeedbackRequest(BaseModel):
    message_id: str
    rating: Literal["like", "dislike"]
    comment: Optional[str] = Field(default=None, max_length=500)


@router.post("/feedback", summary="Submit feedback for an agent response")
async def submit_feedback(req: FeedbackRequest):
    """
    Store a thumbs-up or thumbs-down rating for an assistant message.
    Optionally include a text comment.
    """
    # Verify message exists
    logger.info(
        "POST /feedback | message=%s rating=%s", req.message_id, req.rating
    )
    try:
        feedback = db.save_feedback(req.message_id, req.rating, req.comment)
    except Exception as exc:
        logger.error("Feedback save failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))

    return {"status": "ok", "feedback": feedback}
