"""
Logging Configuration Module
─────────────────────────────
Sets up a centralized, structured logger for the AI Research Agent.

Features:
  - Rotating file handler  → logs/agent.log  (max 5 MB × 3 backups)
  - Console (stderr) handler with colour-coded level names
  - One call  (setup_logging / get_logger)  used by every module

Usage:
    from app.config.logging import get_logger
    logger = get_logger(__name__)
    logger.info("Agent started")
"""

from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import LOG_DIR, LOG_LEVEL, LOG_FILE, LOG_MAX_BYTES, LOG_BACKUP_COUNT

# ── ANSI colour codes for console output ─────────────────────────────────────
_COLOURS = {
    "DEBUG":    "\033[36m",   # cyan
    "INFO":     "\033[32m",   # green
    "WARNING":  "\033[33m",   # yellow
    "ERROR":    "\033[31m",   # red
    "CRITICAL": "\033[35m",   # magenta
}
_RESET = "\033[0m"


class _ColourFormatter(logging.Formatter):
    """Applies ANSI colour to the level name in console output."""

    _FMT = "%(asctime)s  %(levelname)-8s  %(name)s – %(message)s"
    _DATE = "%H:%M:%S"

    def format(self, record: logging.LogRecord) -> str:
        colour = _COLOURS.get(record.levelname, "")
        record.levelname = f"{colour}{record.levelname}{_RESET}"
        return super().format(record)

    def __init__(self) -> None:
        super().__init__(fmt=self._FMT, datefmt=self._DATE)


class _PlainFormatter(logging.Formatter):
    """Plain formatter for the log file (no ANSI codes)."""

    _FMT  = "%(asctime)s  %(levelname)-8s  %(name)s – %(message)s"
    _DATE = "%Y-%m-%d %H:%M:%S"

    def __init__(self) -> None:
        super().__init__(fmt=self._FMT, datefmt=self._DATE)


_configured: bool = False   # guard against double-setup


def setup_logging() -> None:
    """
    Configure the root logger once.
    Safe to call multiple times – subsequent calls are no-ops.
    """
    global _configured
    if _configured:
        return
    _configured = True

    # Ensure the logs directory exists
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))

    # ── Rotating file handler ────────────────────────────────────────────────
    file_handler = logging.handlers.RotatingFileHandler(
        filename=LOG_FILE,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(_PlainFormatter())
    file_handler.setLevel(logging.DEBUG)   # capture everything to file

    # ── Console handler ──────────────────────────────────────────────────────
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(_ColourFormatter())
    console_handler.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))

    root.addHandler(file_handler)
    root.addHandler(console_handler)

    root.info(
        "Logging initialised → file: %s  |  level: %s",
        LOG_FILE,
        LOG_LEVEL.upper(),
    )


def get_logger(name: str) -> logging.Logger:
    """
    Return a named logger, ensuring the root logger is set up first.

    Args:
        name: typically ``__name__`` of the calling module.

    Returns:
        A ``logging.Logger`` instance.
    """
    setup_logging()
    return logging.getLogger(name)
