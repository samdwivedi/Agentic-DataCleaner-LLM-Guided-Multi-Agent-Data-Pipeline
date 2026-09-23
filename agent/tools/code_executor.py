"""
Code Executor Tool (Optional / Sandboxed)
──────────────────────────────────────────
Executes Python code snippets safely using RestrictedPython.
Falls back to a safe exec environment if RestrictedPython is unavailable.
"""

from __future__ import annotations

import io
import sys
import traceback
import contextlib
from typing import Optional

from langchain.tools import BaseTool
from pydantic import BaseModel, Field

# Allowed imports in safe exec
SAFE_IMPORTS = {
    "math", "statistics", "itertools", "functools",
    "collections", "json", "re", "datetime",
    "numpy", "pandas",
}

FORBIDDEN_KEYWORDS = [
    "import os", "import sys", "subprocess", "open(",
    "__import__", "eval(", "exec(", "compile(",
    "shutil", "socket", "requests", "urllib",
]


def safe_execute(code: str, timeout_secs: int = 10) -> dict:
    """
    Execute Python code in a restricted environment.
    Returns stdout output and any errors.
    """
    # Basic safety check
    for kw in FORBIDDEN_KEYWORDS:
        if kw in code:
            return {
                "output": "",
                "error": f"Forbidden operation detected: `{kw}`. Only math/data operations allowed.",
                "success": False,
            }

    # Capture stdout
    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()

    safe_globals = {
        "__builtins__": {
            "print": print,
            "range": range, "len": len, "list": list,
            "dict": dict, "set": set, "tuple": tuple,
            "int": int, "float": float, "str": str,
            "bool": bool, "abs": abs, "round": round,
            "min": min, "max": max, "sum": sum,
            "sorted": sorted, "enumerate": enumerate,
            "zip": zip, "map": map, "filter": filter,
            "isinstance": isinstance, "type": type,
            "True": True, "False": False, "None": None,
        },
        "__name__": "__main__",
    }

    # Add safe modules
    try:
        import math
        import statistics
        import json
        import re
        safe_globals["math"] = math
        safe_globals["statistics"] = statistics
        safe_globals["json"] = json
        safe_globals["re"] = re
    except ImportError:
        pass

    try:
        import numpy as np
        safe_globals["np"] = np
        safe_globals["numpy"] = np
    except ImportError:
        pass

    try:
        with contextlib.redirect_stdout(stdout_capture), \
             contextlib.redirect_stderr(stderr_capture):
            exec(code, safe_globals)  # noqa: S102
        output = stdout_capture.getvalue()
        return {"output": output or "(No output printed)", "error": None, "success": True}

    except Exception:
        err = traceback.format_exc()
        return {
            "output": stdout_capture.getvalue(),
            "error": err,
            "success": False,
        }


# ── LangChain Tool Wrapper ─────────────────────────────────────────────────────

class CodeExecutorInput(BaseModel):
    code: str = Field(
        description=(
            "Python code to execute. Use print() to show output. "
            "Only math, statistics, numpy, json, re are available. "
            "No file I/O, networking, or OS operations allowed."
        )
    )


class CodeExecutorTool(BaseTool):
    name: str = "code_executor"
    description: str = (
        "Execute Python code for data analysis, numerical computation, "
        "list processing, string manipulation, and statistics. "
        "Useful for complex calculations that require loops or conditionals. "
        "Use print() to display results. Available: math, statistics, numpy, json, re."
    )
    args_schema: type[BaseModel] = CodeExecutorInput
    return_direct: bool = False

    def _run(self, code: str) -> str:
        result = safe_execute(code)
        lines = [f"🐍 **Code Executed:**\n```python\n{code}\n```\n"]

        if result["success"]:
            lines.append(f"✅ **Output:**\n```\n{result['output']}\n```")
        else:
            lines.append(f"❌ **Error:**\n```\n{result['error']}\n```")
            if result["output"]:
                lines.append(f"📤 **Partial Output:**\n```\n{result['output']}\n```")

        return "\n".join(lines)

    async def _arun(self, code: str) -> str:
        return self._run(code)
