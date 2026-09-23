"""Tool registry – exports all available tools."""

from agent.tools.web_search import WebSearchTool
from agent.tools.web_scraper import WebScraperTool
from agent.tools.calculator import CalculatorTool
from agent.tools.database import DatabaseTool, DatabaseSchemaTool
from agent.tools.code_executor import CodeExecutorTool

__all__ = [
    "WebSearchTool",
    "WebScraperTool",
    "CalculatorTool",
    "DatabaseTool",
    "DatabaseSchemaTool",
    "CodeExecutorTool",
]

TOOL_REGISTRY = {
    "web_search":      WebSearchTool,
    "web_scraper":     WebScraperTool,
    "calculator":      CalculatorTool,
    "database_query":  DatabaseTool,
    "database_schema": DatabaseSchemaTool,
    "code_executor":   CodeExecutorTool,
}

TOOL_META = {
    "web_search":      {"label": "🔍 Web Search",      "emoji": "🔍", "color": "#4f8ef7"},
    "web_scraper":     {"label": "🌐 Web Scraper",     "emoji": "🌐", "color": "#43c59e"},
    "calculator":      {"label": "🧮 Calculator",      "emoji": "🧮", "color": "#f7a844"},
    "database_query":  {"label": "🗄️ Database Query",  "emoji": "🗄️", "color": "#b06ef7"},
    "database_schema": {"label": "📂 DB Schema",       "emoji": "📂", "color": "#7b6ef7"},
    "code_executor":   {"label": "🐍 Code Executor",   "emoji": "🐍", "color": "#f7647a"},
}


def build_tool_list(enabled: dict[str, bool]) -> list:
    """Build a list of instantiated tool objects based on enabled flags."""
    tools = []
    # Always include schema tool when database is enabled
    for name, cls in TOOL_REGISTRY.items():
        base = name.replace("_schema", "").replace("_query", "")
        if enabled.get("database", True) and "database" in base:
            tools.append(cls())
        elif enabled.get(name, True) and "database" not in base:
            tools.append(cls())
    return tools
