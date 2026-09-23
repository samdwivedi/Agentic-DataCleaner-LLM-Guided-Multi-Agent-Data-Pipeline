"""
Backend Database Layer
──────────────────────
SQLite tables for the API layer:
  • chats      – conversation sessions
  • messages   – individual turns per chat
  • tool_logs  – tool invocation records per message
  • feedback   – thumbs up/down on messages

This is SEPARATE from the agent's research database (data/research.db).
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from agent.logger import get_logger

from config import ROOT_DIR

logger = get_logger(__name__)

API_DB_PATH: Path = ROOT_DIR / "data" / "api.db"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS chats (
    id          TEXT PRIMARY KEY,
    title       TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id          TEXT PRIMARY KEY,
    chat_id     TEXT NOT NULL REFERENCES chats(id),
    role        TEXT NOT NULL CHECK(role IN ('user','assistant')),
    content     TEXT NOT NULL,
    sources     TEXT,          -- JSON array
    confidence  REAL,
    tools_used  TEXT,          -- JSON array
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tool_logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id  TEXT NOT NULL REFERENCES messages(id),
    tool_name   TEXT NOT NULL,
    success     INTEGER NOT NULL DEFAULT 1,
    duration_ms REAL,
    logged_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS feedback (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id  TEXT NOT NULL REFERENCES messages(id),
    rating      TEXT NOT NULL CHECK(rating IN ('like','dislike')),
    comment     TEXT,
    created_at  TEXT NOT NULL
);
"""


def _connect() -> sqlite3.Connection:
    API_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(API_DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    """Create tables if they don't exist."""
    with _connect() as conn:
        conn.executescript(SCHEMA_SQL)
    logger.info("API database initialised at %s", API_DB_PATH)


# ── Chat helpers ──────────────────────────────────────────────────────────────

def create_chat(chat_id: str, title: str = "New Chat") -> dict:
    now = datetime.utcnow().isoformat()
    with _connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO chats (id, title, created_at, updated_at) VALUES (?,?,?,?)",
            (chat_id, title, now, now),
        )
    return {"id": chat_id, "title": title, "created_at": now, "updated_at": now}


def list_chats() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM chats ORDER BY updated_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def get_chat(chat_id: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM chats WHERE id=?", (chat_id,)).fetchone()
    return dict(row) if row else None


def touch_chat(chat_id: str, title: str | None = None) -> None:
    now = datetime.utcnow().isoformat()
    with _connect() as conn:
        if title:
            conn.execute(
                "UPDATE chats SET updated_at=?, title=? WHERE id=?", (now, title, chat_id)
            )
        else:
            conn.execute("UPDATE chats SET updated_at=? WHERE id=?", (now, chat_id))


# ── Message helpers ───────────────────────────────────────────────────────────

def save_message(
    message_id: str,
    chat_id: str,
    role: str,
    content: str,
    sources: list | None = None,
    confidence: float | None = None,
    tools_used: list | None = None,
) -> dict:
    now = datetime.utcnow().isoformat()
    with _connect() as conn:
        conn.execute(
            """INSERT INTO messages
               (id, chat_id, role, content, sources, confidence, tools_used, created_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                message_id,
                chat_id,
                role,
                content,
                json.dumps(sources or []),
                confidence,
                json.dumps(tools_used or []),
                now,
            ),
        )
    return {
        "id": message_id,
        "chat_id": chat_id,
        "role": role,
        "content": content,
        "sources": sources or [],
        "confidence": confidence,
        "tools_used": tools_used or [],
        "created_at": now,
    }


def get_messages(chat_id: str) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM messages WHERE chat_id=? ORDER BY created_at ASC",
            (chat_id,),
        ).fetchall()
    results = []
    for r in rows:
        d = dict(r)
        d["sources"] = json.loads(d["sources"] or "[]")
        d["tools_used"] = json.loads(d["tools_used"] or "[]")
        results.append(d)
    return results


# ── Tool log helpers ──────────────────────────────────────────────────────────

def log_tool(message_id: str, tool_name: str, success: bool, duration_ms: float) -> None:
    now = datetime.utcnow().isoformat()
    with _connect() as conn:
        conn.execute(
            "INSERT INTO tool_logs (message_id, tool_name, success, duration_ms, logged_at) VALUES (?,?,?,?,?)",
            (message_id, tool_name, int(success), duration_ms, now),
        )


# ── Feedback helpers ──────────────────────────────────────────────────────────

def save_feedback(message_id: str, rating: str, comment: str | None = None) -> dict:
    now = datetime.utcnow().isoformat()
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO feedback (message_id, rating, comment, created_at) VALUES (?,?,?,?)",
            (message_id, rating, comment, now),
        )
        feedback_id = cur.lastrowid
    return {"id": feedback_id, "message_id": message_id, "rating": rating, "created_at": now}
