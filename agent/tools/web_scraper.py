"""
Web Scraper Tool
────────────────
Fetches and parses a URL using requests + BeautifulSoup.
Extracts clean text, metadata, and key sections.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

import requests
from bs4 import BeautifulSoup
from langchain.tools import BaseTool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Tags that are noise (navigation, ads, etc.)
NOISE_TAGS = [
    "script", "style", "nav", "header", "footer",
    "aside", "form", "button", "noscript", "iframe",
    "advertisement", "cookie", "popup",
]


def scrape_url(url: str, max_chars: int = 5000) -> dict:
    """
    Scrape and clean text content from a URL.

    Returns:
        dict with keys: title, url, text, meta_description, word_count, error
    """
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        # Remove noise
        for tag in NOISE_TAGS:
            for el in soup.find_all(tag):
                el.decompose()

        # Extract metadata
        title = soup.title.string.strip() if soup.title else "Unknown Title"
        meta_desc = ""
        meta_tag = soup.find("meta", attrs={"name": "description"})
        if meta_tag:
            meta_desc = meta_tag.get("content", "")

        # Extract article / main content preferentially
        content_area = (
            soup.find("article")
            or soup.find("main")
            or soup.find("div", {"id": re.compile(r"content|article|main", re.I)})
            or soup.find("div", {"class": re.compile(r"content|article|main|body", re.I)})
            or soup.body
        )

        if content_area:
            raw_text = content_area.get_text(separator=" ", strip=True)
        else:
            raw_text = soup.get_text(separator=" ", strip=True)

        # Collapse whitespace
        clean_text = re.sub(r"\s+", " ", raw_text).strip()
        truncated = clean_text[:max_chars]
        if len(clean_text) > max_chars:
            truncated += "… [content truncated]"

        return {
            "title": title,
            "url": url,
            "meta_description": meta_desc,
            "text": truncated,
            "word_count": len(clean_text.split()),
            "error": None,
        }

    except requests.exceptions.Timeout:
        return {"url": url, "error": "Request timed out", "text": ""}
    except requests.exceptions.HTTPError as e:
        return {"url": url, "error": f"HTTP {e.response.status_code}", "text": ""}
    except Exception as exc:
        logger.exception("Scraping failed for %s", url)
        return {"url": url, "error": str(exc), "text": ""}


# ── LangChain Tool Wrapper ─────────────────────────────────────────────────────

class WebScraperInput(BaseModel):
    url: str = Field(description="The full URL to scrape content from (must start with http:// or https://)")
    max_chars: int = Field(default=4000, description="Maximum characters of content to extract (500-8000)")


class WebScraperTool(BaseTool):
    name: str = "web_scraper"
    description: str = (
        "Fetch and read the full text content of a specific webpage URL. "
        "Use this after web_search to read the actual content of relevant pages. "
        "Provide the complete URL starting with http:// or https://."
    )
    args_schema: type[BaseModel] = WebScraperInput
    return_direct: bool = False

    def _run(self, url: str, max_chars: int = 4000) -> str:
        data = scrape_url(url, min(max_chars, 8000))

        if data.get("error"):
            return f"❌ Scraping failed for {url}: {data['error']}"

        lines = [
            f"🌐 **Page:** {data['title']}",
            f"🔗 **URL:** {data['url']}",
        ]
        if data.get("meta_description"):
            lines.append(f"📋 **Description:** {data['meta_description']}")
        lines.append(f"📊 **Word Count:** ~{data['word_count']} words\n")
        lines.append("─" * 60)
        lines.append(data["text"])

        return "\n".join(lines)

    async def _arun(self, url: str, max_chars: int = 4000) -> str:
        return self._run(url, max_chars)
