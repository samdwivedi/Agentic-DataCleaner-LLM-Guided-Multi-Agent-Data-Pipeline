"""
Agent Service Layer
────────────────────
Wraps the existing agent tools + LangChain into the run_agent() function
that the FastAPI routes call. Keeps all core agent logic untouched.
"""

from __future__ import annotations

import sys, os, time, uuid
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from typing import Any
from agent.logger import get_logger
from config import (
    OPENAI_API_KEY, OPENAI_MODEL, TEMPERATURE, MAX_TOKENS, DEFAULT_TOOLS
)

logger = get_logger(__name__)


def run_agent(query: str, chat_id: str | None = None) -> dict:
    """
    Execute a research query through the LangChain agent.

    Returns:
        {
          "answer":     str,
          "sources":    list[dict],
          "confidence": float,
          "tools_used": list[str],
        }
    """
    t0 = time.perf_counter()
    logger.info("▶ Query received [chat=%s]: %s", chat_id or "new", query[:120])

    # ── Build tool list ────────────────────────────────────────────────────────
    try:
        from agent.tools import build_tool_list
        tools = build_tool_list(DEFAULT_TOOLS)
        logger.debug("Tools loaded: %s", [t.name for t in tools])
    except Exception as exc:
        logger.error("Failed to load tools: %s", exc)
        return _error_response(query, str(exc))

    # ── Build LLM ─────────────────────────────────────────────────────────────
    if not OPENAI_API_KEY:
        logger.warning("OPENAI_API_KEY not set – returning stub response")
        return _stub_response(query, tools)

    try:
        from langchain_openai import ChatOpenAI
        llm = ChatOpenAI(
            model=OPENAI_MODEL,
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
            openai_api_key=OPENAI_API_KEY,
        )
    except Exception as exc:
        logger.error("LLM init failed: %s", exc)
        return _error_response(query, str(exc))

    # ── Build agent using LangGraph ───────────────────────────────────────────
    try:
        from langgraph.prebuilt import create_react_agent
        from langchain_core.messages import HumanMessage

        system_prompt = (
            "You are an advanced AI Research Agent with access to web search, "
            "web scraping, a calculator, a structured research database, and a "
            "Python code executor. For every query:\n"
            "1. Think step-by-step about which tools are needed.\n"
            "2. Use tools in parallel when possible.\n"
            "3. Cite all URLs / database sources in your final answer.\n"
            "4. Be concise but comprehensive.\n"
            "5. End each answer with a confidence score comment like: "
            "[Confidence: 0.85]"
        )

        executor = create_react_agent(llm, tools=tools, state_modifier=system_prompt)
    except Exception as exc:
        logger.error("Agent build failed: %s", exc)
        return _error_response(query, str(exc))

    # ── Run ───────────────────────────────────────────────────────────────────
    try:
        result = executor.invoke({"messages": [HumanMessage(content=query)]})
    except Exception as exc:
        logger.error("Agent execution failed: %s", exc)
        return _error_response(query, str(exc))

    elapsed = round((time.perf_counter() - t0) * 1000, 1)

    # ── Parse intermediate steps ──────────────────────────────────────────────
    tools_used: list[str] = []
    sources: list[dict] = []

    for msg in result.get("messages", []):
        if getattr(msg, "type", "") == "tool":
            tool_name = getattr(msg, "name", "unknown")
            if tool_name not in tools_used:
                tools_used.append(tool_name)
            logger.info("  Tool used: %s (%.0f ms total)", tool_name, elapsed)

            # Extract URLs from web search / scraper output
            if isinstance(msg.content, str):
                for line in msg.content.splitlines():
                    if line.strip().startswith("🔗"):
                        url = line.strip().replace("🔗", "").strip()
                        if url and url not in [s.get("url") for s in sources]:
                            sources.append({"url": url, "tool": tool_name})
                            
    # Extract the final answer text 
    answer: str = result["messages"][-1].content if result.get("messages") else "No response generated."

    # ── Parse confidence from answer ─────────────────────────────────────────
    confidence = _extract_confidence(answer)

    logger.info(
        "✅ Query done in %.0f ms | tools=%s | confidence=%.2f",
        elapsed, tools_used, confidence,
    )

    return {
        "answer": answer,
        "sources": sources,
        "confidence": confidence,
        "tools_used": tools_used,
        "elapsed_ms": elapsed,
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _extract_confidence(text: str) -> float:
    """Parse [Confidence: 0.xx] from agent output."""
    import re
    m = re.search(r"\[Confidence:\s*([\d.]+)\]", text, re.IGNORECASE)
    if m:
        try:
            return min(1.0, max(0.0, float(m.group(1))))
        except ValueError:
            pass
    return 0.75   # sensible default


def _error_response(query: str, error: str) -> dict:
    return {
        "answer": (
            f"I encountered an error while processing your query: {error}\n\n"
            "Please check the API key and tool configuration, then try again."
        ),
        "sources": [],
        "confidence": 0.0,
        "tools_used": [],
        "error": error,
    }


def _stub_response(query: str, tools: list) -> dict:
    """
    Offline stub – returned when no OPENAI_API_KEY is set.
    Useful for frontend / UI testing without burning API credits.
    """
    import random, time
    time.sleep(0.5)   # simulate latency
    tool_names = [t.name for t in tools]
    used = random.sample(tool_names, k=min(2, len(tool_names)))
    return {
        "answer": (
            f"**[STUB MODE – No API key set]**\n\n"
            f"Your query was: *{query}*\n\n"
            "To get real answers, add your `OPENAI_API_KEY` to the `.env` file. "
            "The agent would have used tools like web search and the research "
            "database to answer this question comprehensively.\n\n"
            "[Confidence: 0.00]"
        ),
        "sources": [
            {"url": "https://platform.openai.com/api-keys", "tool": "info"},
        ],
        "confidence": 0.0,
        "tools_used": used,
        "elapsed_ms": 500,
    }
