"""Central configuration module for the AI Research Agent."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv(override=True)

# ── Project Root ─────────────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).parent
DATA_DIR = ROOT_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_DIR: Path         = ROOT_DIR / "logs"
LOG_FILE: Path        = LOG_DIR / "agent.log"
LOG_LEVEL: str        = os.getenv("LOG_LEVEL", "INFO")   # DEBUG | INFO | WARNING | ERROR
LOG_MAX_BYTES: int    = 5 * 1024 * 1024   # 5 MB per file
LOG_BACKUP_COUNT: int = 3                  # keep 3 rotated backups

# ── LLM Settings ─────────────────────────────────────────────────────────────
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL: str   = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
TEMPERATURE: float  = 0.1
MAX_TOKENS: int     = 4096

# ── Tool Settings ─────────────────────────────────────────────────────────────
MAX_SEARCH_RESULTS: int = int(os.getenv("MAX_SEARCH_RESULTS", "5"))
SERPAPI_KEY: str        = os.getenv("SERPAPI_KEY", "")

# ── Database ──────────────────────────────────────────────────────────────────
DATABASE_PATH: str = os.getenv("DATABASE_PATH", str(DATA_DIR / "research.db"))

# ── Memory ────────────────────────────────────────────────────────────────────
MEMORY_MAX_HISTORY: int = 20        # conversation turns to retain

# ── Default Tool Toggles ──────────────────────────────────────────────────────
DEFAULT_TOOLS = {
    "web_search":    os.getenv("DEFAULT_WEB_SEARCH",    "true").lower() == "true",
    "web_scraper":   os.getenv("DEFAULT_WEB_SCRAPER",   "true").lower() == "true",
    "calculator":    os.getenv("DEFAULT_CALCULATOR",    "true").lower() == "true",
    "database":      os.getenv("DEFAULT_DATABASE",      "true").lower() == "true",
    "code_executor": os.getenv("DEFAULT_CODE_EXEC",     "false").lower() == "true",
}

# ── UI / Display ──────────────────────────────────────────────────────────────
APP_TITLE   = "🔬 AI Research Agent"
APP_ICON    = "🤖"
APP_VERSION = "1.0.0"
