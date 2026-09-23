"""
Web Search Tool
───────────────
Uses DuckDuckGo (free, no API key required) with optional SerpAPI fallback.
Returns structured results with title, snippet, URL, and source.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Optional

from langchain.tools import BaseTool
from pydantic import BaseModel, Field

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import MAX_SEARCH_RESULTS, SERPAPI_KEY

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    title: str
    snippet: str
    url: str
    source: str = "web"
    score: float = 1.0


def _ddg_search(query: str, max_results: int) -> List[SearchResult]:
    """DuckDuckGo search – no API key needed."""
    try:
        from duckduckgo_search import DDGS
        results: List[SearchResult] = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append(
                    SearchResult(
                        title=r.get("title", ""),
                        snippet=r.get("body", ""),
                        url=r.get("href", ""),
                        source="DuckDuckGo",
                    )
                )
        return results
    except Exception as exc:
        logger.warning("DuckDuckGo search failed: %s", exc)
        return []


def _serp_search(query: str, max_results: int) -> List[SearchResult]:
    """SerpAPI search – requires API key."""
    if not SERPAPI_KEY:
        return []
    try:
        import requests
        params = {
            "q": query,
            "api_key": SERPAPI_KEY,
            "num": max_results,
            "engine": "google",
        }
        resp = requests.get("https://serpapi.com/search", params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        results: List[SearchResult] = []
        for r in data.get("organic_results", [])[:max_results]:
            results.append(
                SearchResult(
                    title=r.get("title", ""),
                    snippet=r.get("snippet", ""),
                    url=r.get("link", ""),
                    source="SerpAPI/Google",
                )
            )
        return results
    except Exception as exc:
        logger.warning("SerpAPI search failed: %s", exc)
        return []


def web_search(query: str, max_results: int = MAX_SEARCH_RESULTS) -> dict:
    """
    Perform a web search and return structured results.

    Args:
        query: The search query string.
        max_results: Maximum number of results to return.

    Returns:
        dict with 'results' list and 'total' count.
    """
    results = _serp_search(query, max_results) if SERPAPI_KEY else []
    if not results:
        results = _ddg_search(query, max_results)

    if not results:
        return {
            "results": [],
            "total": 0,
            "error": "No results found. Try a different query.",
        }

    serialized = [
        {
            "title": r.title,
            "snippet": r.snippet,
            "url": r.url,
            "source": r.source,
        }
        for r in results
    ]
    return {"results": serialized, "total": len(serialized)}


# ── LangChain Tool Wrapper ─────────────────────────────────────────────────────

class WebSearchInput(BaseModel):
    query: str = Field(description="The search query to look up on the web")
    max_results: int = Field(default=5, description="Maximum number of results to return (1-10)")


class WebSearchTool(BaseTool):
    name: str = "web_search"
    description: str = (
        "Search the web for current information, news, facts, and recent events. "
        "Use this when you need up-to-date information that may not be in your training data. "
        "Input should be a clear search query."
    )
    args_schema: type[BaseModel] = WebSearchInput
    return_direct: bool = False

    def _run(self, query: str, max_results: int = 5) -> str:
        result = web_search(query, min(max_results, 10))
        if "error" in result:
            return f"Search error: {result['error']}"
        
        lines = [f"🔍 Web Search Results for: '{query}'\n"]
        for i, r in enumerate(result["results"], 1):
            lines.append(f"[{i}] **{r['title']}**")
            lines.append(f"   📝 {r['snippet']}")
            lines.append(f"   🔗 {r['url']}")
            lines.append(f"   📌 Source: {r['source']}\n")
        
        return "\n".join(lines)

    async def _arun(self, query: str, max_results: int = 5) -> str:
        return self._run(query, max_results)
