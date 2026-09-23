"""
Database Tool
─────────────
SQLite-backed knowledge store for structured data.
Pre-seeded with AI/Tech market data, research facts, and economic indicators.
Supports natural language → SQL query translation via the LLM,
plus direct SQL execution for precise queries.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from typing import Any, List, Optional

from langchain.tools import BaseTool
from pydantic import BaseModel, Field

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from config import DATABASE_PATH

logger = logging.getLogger(__name__)


# ── Schema & Seed Data ────────────────────────────────────────────────────────

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS ai_market_data (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    year        INTEGER NOT NULL,
    segment     TEXT    NOT NULL,       -- e.g. 'Generative AI', 'ML Platforms'
    market_size_usd_bn  REAL,           -- billion USD
    growth_rate_pct     REAL,           -- YoY growth %
    top_players         TEXT,           -- comma-separated
    region      TEXT    DEFAULT 'Global',
    source      TEXT
);

CREATE TABLE IF NOT EXISTS tech_companies (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    ticker      TEXT,
    sector      TEXT,
    market_cap_usd_bn REAL,
    revenue_usd_bn    REAL,
    employees         INTEGER,
    founded           INTEGER,
    hq_country        TEXT,
    ai_focus          TEXT
);

CREATE TABLE IF NOT EXISTS research_facts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    category    TEXT,
    fact        TEXT NOT NULL,
    value       TEXT,
    unit        TEXT,
    year        INTEGER,
    source      TEXT
);
"""

SEED_DATA: dict[str, list[dict]] = {
    "ai_market_data": [
        {"year": 2022, "segment": "Generative AI",    "market_size_usd_bn": 10.6,  "growth_rate_pct": 42.0, "top_players": "OpenAI,Anthropic,Google", "source": "Grand View Research"},
        {"year": 2023, "segment": "Generative AI",    "market_size_usd_bn": 22.5,  "growth_rate_pct": 112.3,"top_players": "OpenAI,Google,Microsoft",  "source": "Bloomberg Intelligence"},
        {"year": 2024, "segment": "Generative AI",    "market_size_usd_bn": 45.8,  "growth_rate_pct": 103.6,"top_players": "OpenAI,Google,Anthropic,Meta","source": "McKinsey & Co."},
        {"year": 2025, "segment": "Generative AI",    "market_size_usd_bn": 98.1,  "growth_rate_pct": 114.2,"top_players": "OpenAI,Google,Anthropic,xAI","source": "IDC Forecast"},
        {"year": 2026, "segment": "Generative AI",    "market_size_usd_bn": 191.0, "growth_rate_pct": 94.7, "top_players": "OpenAI,Google,Anthropic,Meta","source": "IDC Forecast (projected)"},
        {"year": 2023, "segment": "AI Overall",       "market_size_usd_bn": 207.9, "growth_rate_pct": 36.8, "top_players": "Microsoft,Google,Amazon,IBM","source": "Statista"},
        {"year": 2024, "segment": "AI Overall",       "market_size_usd_bn": 298.2, "growth_rate_pct": 43.4, "top_players": "Microsoft,Google,Amazon",    "source": "Grand View Research"},
        {"year": 2025, "segment": "AI Overall",       "market_size_usd_bn": 407.0, "growth_rate_pct": 36.5, "top_players": "Microsoft,Google,Amazon,Meta","source": "IDC"},
        {"year": 2026, "segment": "AI Overall",       "market_size_usd_bn": 562.0, "growth_rate_pct": 38.1, "top_players": "Microsoft,Google,Amazon",    "source": "IDC Forecast (projected)"},
        {"year": 2024, "segment": "ML Platforms",     "market_size_usd_bn": 31.4,  "growth_rate_pct": 39.1, "top_players": "AWS,Azure,GCP",              "source": "Gartner"},
        {"year": 2024, "segment": "NLP/LLM",          "market_size_usd_bn": 18.7,  "growth_rate_pct": 67.3, "top_players": "OpenAI,Anthropic,Cohere",    "source": "MarketsandMarkets"},
        {"year": 2024, "segment": "Computer Vision",  "market_size_usd_bn": 22.3,  "growth_rate_pct": 27.6, "top_players": "NVIDIA,Google,Amazon",       "source": "Allied Market Research"},
        {"year": 2024, "segment": "AI Agents",        "market_size_usd_bn": 5.1,   "growth_rate_pct": 145.0,"top_players": "Salesforce,ServiceNow,OpenAI","source": "IDC"},
        {"year": 2025, "segment": "AI Agents",        "market_size_usd_bn": 12.5,  "growth_rate_pct": 145.1,"top_players": "Salesforce,Workday,OpenAI",  "source": "IDC Forecast"},
    ],
    "tech_companies": [
        {"name": "Microsoft",   "ticker": "MSFT",  "sector": "Cloud/AI",    "market_cap_usd_bn": 3100.0, "revenue_usd_bn": 245.1, "employees": 228000, "founded": 1975, "hq_country": "USA",    "ai_focus": "Copilot, Azure AI, OpenAI partnership"},
        {"name": "NVIDIA",      "ticker": "NVDA",  "sector": "Semiconductors","market_cap_usd_bn": 2850.0,"revenue_usd_bn": 130.5, "employees": 32000,  "founded": 1993, "hq_country": "USA",  "ai_focus": "AI GPUs, CUDA, NIM microservices"},
        {"name": "Alphabet",    "ticker": "GOOGL", "sector": "Search/AI",   "market_cap_usd_bn": 2190.0, "revenue_usd_bn": 350.0, "employees": 182000, "founded": 1998, "hq_country": "USA",    "ai_focus": "Gemini, DeepMind, TPUs"},
        {"name": "Amazon",      "ticker": "AMZN",  "sector": "Cloud/E-commerce","market_cap_usd_bn": 2100.0,"revenue_usd_bn": 620.0,"employees": 1540000,"founded": 1994,"hq_country": "USA",   "ai_focus": "Bedrock, Alexa+, AWS AI services"},
        {"name": "Meta",        "ticker": "META",  "sector": "Social/AI",   "market_cap_usd_bn": 1460.0, "revenue_usd_bn": 164.5, "employees": 74000,  "founded": 2004, "hq_country": "USA",    "ai_focus": "Llama 3, FAIR research, Reality AI"},
        {"name": "OpenAI",      "ticker": None,    "sector": "AI Research", "market_cap_usd_bn": 300.0,  "revenue_usd_bn": 3.7,   "employees": 1800,   "founded": 2015, "hq_country": "USA",    "ai_focus": "GPT-4o, DALL-E, Sora, ChatGPT"},
        {"name": "Anthropic",   "ticker": None,    "sector": "AI Safety",   "market_cap_usd_bn": 61.5,   "revenue_usd_bn": 0.8,   "employees": 900,    "founded": 2021, "hq_country": "USA",    "ai_focus": "Claude 3, Constitutional AI"},
        {"name": "xAI",         "ticker": None,    "sector": "AI Research", "market_cap_usd_bn": 50.0,   "revenue_usd_bn": 0.1,   "employees": 800,    "founded": 2023, "hq_country": "USA",    "ai_focus": "Grok, multimodal reasoning"},
        {"name": "Mistral AI",  "ticker": None,    "sector": "AI Research", "market_cap_usd_bn": 6.0,    "revenue_usd_bn": 0.05,  "employees": 200,    "founded": 2023, "hq_country": "France", "ai_focus": "Open-source LLMs, Mixtral"},
        {"name": "Cohere",      "ticker": None,    "sector": "Enterprise AI","market_cap_usd_bn": 5.5,   "revenue_usd_bn": 0.04,  "employees": 450,    "founded": 2019, "hq_country": "Canada", "ai_focus": "Enterprise RAG, Command models"},
    ],
    "research_facts": [
        {"category": "AI Investment",   "fact": "Global AI investment in 2024",          "value": "200",    "unit": "billion USD",     "year": 2024, "source": "Stanford HAI"},
        {"category": "AI Investment",   "fact": "US AI startup funding Q1 2025",         "value": "21.7",   "unit": "billion USD",     "year": 2025, "source": "PitchBook"},
        {"category": "AI Jobs",         "fact": "AI-related job postings growth 2024",   "value": "62",     "unit": "percent YoY",     "year": 2024, "source": "LinkedIn Economic Graph"},
        {"category": "AI Jobs",         "fact": "AI researchers worldwide (estimate)",   "value": "300000", "unit": "professionals",   "year": 2024, "source": "OECD"},
        {"category": "LLM Performance", "fact": "GPT-4 MMLU benchmark score",            "value": "86.4",   "unit": "percent",         "year": 2024, "source": "OpenAI"},
        {"category": "LLM Performance", "fact": "Gemini Ultra MMLU benchmark score",     "value": "90.0",   "unit": "percent",         "year": 2024, "source": "Google DeepMind"},
        {"category": "LLM Performance", "fact": "Claude 3 Opus MMLU benchmark score",   "value": "86.8",   "unit": "percent",         "year": 2024, "source": "Anthropic"},
        {"category": "Compute",         "fact": "AI compute doubling time",              "value": "6",      "unit": "months",          "year": 2024, "source": "OpenAI scaling paper"},
        {"category": "Compute",         "fact": "Cost of training GPT-4 (estimated)",   "value": "100",    "unit": "million USD",     "year": 2023, "source": "SemiAnalysis"},
        {"category": "AI Safety",       "fact": "Researchers who believe AGI possible by 2030","value": "36","unit": "percent",       "year": 2024, "source": "AI Impacts Survey"},
        {"category": "AI Adoption",     "fact": "Fortune 500 companies with AI initiatives","value": "72",  "unit": "percent",        "year": 2024, "source": "McKinsey"},
        {"category": "AI Adoption",     "fact": "Employees using AI tools at work",      "value": "75",    "unit": "percent",         "year": 2025, "source": "Microsoft Work Trend Index"},
        {"category": "Revenue Impact",  "fact": "Average productivity gain from AI tools","value": "40",   "unit": "percent",         "year": 2024, "source": "Accenture Research"},
    ]
}


# ── Database Manager ──────────────────────────────────────────────────────────

class DatabaseManager:
    _instance: Optional["DatabaseManager"] = None

    def __init__(self, db_path: str = DATABASE_PATH):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(SCHEMA_SQL)
            for table, rows in SEED_DATA.items():
                existing = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                if existing == 0:
                    for row in rows:
                        cols = ", ".join(row.keys())
                        placeholders = ", ".join(["?"] * len(row))
                        conn.execute(
                            f"INSERT INTO {table} ({cols}) VALUES ({placeholders})",
                            list(row.values()),
                        )
            conn.commit()
        logger.info("Database initialized at %s", self.db_path)

    def execute_query(self, sql: str) -> dict:
        """Execute a SELECT query and return results."""
        try:
            # Safety: allow only SELECT statements
            stripped = sql.strip().upper()
            if not stripped.startswith("SELECT"):
                return {"error": "Only SELECT queries are allowed.", "rows": []}

            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cur = conn.execute(sql)
                rows = [dict(r) for r in cur.fetchall()]
                cols = [d[0] for d in cur.description] if cur.description else []
                return {"rows": rows, "columns": cols, "count": len(rows), "error": None}

        except sqlite3.Error as exc:
            return {"error": str(exc), "rows": []}

    def get_schema_info(self) -> str:
        """Return a string describing all tables and their columns."""
        with sqlite3.connect(self.db_path) as conn:
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            info_lines = []
            for (table,) in tables:
                cols = conn.execute(f"PRAGMA table_info({table})").fetchall()
                col_desc = ", ".join(f"{c[1]} ({c[2]})" for c in cols)
                count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                info_lines.append(f"📋 **{table}** ({count} rows)\n   Columns: {col_desc}")
            return "\n".join(info_lines)


_db_manager: Optional[DatabaseManager] = None


def get_db() -> DatabaseManager:
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager


# ── LangChain Tool Wrapper ─────────────────────────────────────────────────────

class DatabaseQueryInput(BaseModel):
    query: str = Field(
        description=(
            "A valid SQLite SELECT query to run against the research database. "
            "Available tables: ai_market_data, tech_companies, research_facts. "
            "Always use SELECT only. Example: "
            "SELECT year, market_size_usd_bn FROM ai_market_data WHERE segment='Generative AI' ORDER BY year"
        )
    )


class DatabaseTool(BaseTool):
    name: str = "database_query"
    description: str = (
        "Query the local research database containing structured data about: "
        "AI market sizes by year and segment, tech company financials, "
        "and research statistics/facts. "
        "Use this for precise numerical data, historical market figures, "
        "company comparisons, and quantitative research queries. "
        "Write standard SQLite SELECT queries."
    )
    args_schema: type[BaseModel] = DatabaseQueryInput
    return_direct: bool = False

    def _run(self, query: str) -> str:
        db = get_db()
        result = db.execute_query(query)

        if result.get("error"):
            # Give agent helpful context
            schema = db.get_schema_info()
            return (
                f"❌ **Query Error:** {result['error']}\n\n"
                f"💡 **Database Schema:**\n{schema}"
            )

        if result["count"] == 0:
            return f"📂 Query returned 0 rows.\n```sql\n{query}\n```"

        # Format as markdown table
        cols = result["columns"]
        rows = result["rows"]
        lines = [
            f"✅ **Query returned {result['count']} row(s):**\n",
            "```sql\n" + query + "\n```\n",
        ]

        # Header
        header = "| " + " | ".join(cols) + " |"
        divider = "|" + "|".join([":---:"] * len(cols)) + "|"
        lines.append(header)
        lines.append(divider)

        for row in rows[:50]:  # cap at 50 rows
            row_str = "| " + " | ".join(str(row.get(c, "")) for c in cols) + " |"
            lines.append(row_str)

        return "\n".join(lines)

    async def _arun(self, query: str) -> str:
        return self._run(query)


class DatabaseSchemaTool(BaseTool):
    name: str = "database_schema"
    description: str = (
        "Get the schema and structure of the local research database. "
        "Use this BEFORE writing a database query to understand available tables and columns."
    )
    return_direct: bool = False

    def _run(self, tool_input: str = "") -> str:
        db = get_db()
        schema = db.get_schema_info()
        return f"📂 **Research Database Schema:**\n\n{schema}"

    async def _arun(self, tool_input: str = "") -> str:
        return self._run(tool_input)
