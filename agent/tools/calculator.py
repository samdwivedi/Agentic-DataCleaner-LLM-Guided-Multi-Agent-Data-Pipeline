"""
Calculator Tool
───────────────
Supports arithmetic, scientific functions, statistical operations,
unit conversions, and percentage calculations via SymPy + NumPy.
Provides safe expression evaluation with clear error messages.
"""

from __future__ import annotations

import math
import re
import statistics
from typing import Any

import numpy as np
import sympy as sp
from sympy.parsing.sympy_parser import (
    parse_expr,
    standard_transformations,
    implicit_multiplication_application,
)
from langchain.tools import BaseTool
from pydantic import BaseModel, Field


TRANSFORMATIONS = standard_transformations + (implicit_multiplication_application,)

# Safe globals for eval
SAFE_MATH_GLOBALS = {
    "__builtins__": {},
    "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "asin": math.asin, "acos": math.acos, "atan": math.atan,
    "sinh": math.sinh, "cosh": math.cosh, "tanh": math.tanh,
    "sqrt": math.sqrt, "cbrt": lambda x: x ** (1/3),
    "log": math.log, "log2": math.log2, "log10": math.log10,
    "exp": math.exp,
    "abs": abs, "ceil": math.ceil, "floor": math.floor,
    "round": round, "pow": pow,
    "pi": math.pi, "e": math.e, "tau": math.tau,
    "inf": math.inf,
    # Numpy stats
    "mean": np.mean, "median": np.median,
    "std": np.std, "var": np.var,
    "min": min, "max": max, "sum": sum,
    # Combinatorics
    "factorial": math.factorial,
    "comb": math.comb,
    "perm": math.perm,
}


def _preprocess(expr: str) -> str:
    """Normalize the expression string."""
    expr = expr.strip()
    # Replace ^ with ** for exponentiation
    expr = re.sub(r"\^", "**", expr)
    # Replace × ÷ with * /
    expr = expr.replace("×", "*").replace("÷", "/").replace("−", "-")
    # Handle percentage shorthand: "15% of 200" → "0.15 * 200"
    expr = re.sub(r"(\d+\.?\d*)\s*%\s*of\s*(\d+\.?\d*)", r"(\1/100)*\2", expr, flags=re.I)
    # Handle plain percentage: "15%" → "0.15"
    expr = re.sub(r"(\d+\.?\d*)\s*%", r"(\1/100)", expr)
    return expr


def calculate(expression: str) -> dict:
    """
    Evaluate a mathematical expression.

    Returns:
        dict with 'result', 'expression', 'steps', 'error'
    """
    original = expression
    expression = _preprocess(expression)
    steps = [f"Parsed: `{expression}`"]

    # Try SymPy first for symbolic math
    try:
        local_vars = {
            "pi": sp.pi, "e": sp.E, "sqrt": sp.sqrt,
            "sin": sp.sin, "cos": sp.cos, "tan": sp.tan,
            "log": sp.log, "exp": sp.exp, "abs": sp.Abs,
            "factorial": sp.factorial,
        }
        sym_result = parse_expr(expression, local_dict=local_vars,
                                transformations=TRANSFORMATIONS)
        simplified = sp.simplify(sym_result)
        numeric_val = float(simplified.evalf()) if simplified.is_number else None

        if numeric_val is not None:
            steps.append(f"Simplified: `{simplified}`")
            # Format nicely
            if numeric_val == int(numeric_val) and abs(numeric_val) < 1e15:
                result_str = str(int(numeric_val))
            else:
                result_str = f"{numeric_val:.10g}"
            return {
                "expression": original,
                "result": result_str,
                "numeric": numeric_val,
                "steps": steps,
                "error": None,
            }
        else:
            # Return symbolic result
            return {
                "expression": original,
                "result": str(simplified),
                "numeric": None,
                "steps": steps,
                "error": None,
            }

    except Exception:
        pass

    # Fallback: safe eval
    try:
        result = eval(expression, SAFE_MATH_GLOBALS, {})  # noqa: S307
        if isinstance(result, float):
            if result == int(result) and abs(result) < 1e15:
                result_str = str(int(result))
            else:
                result_str = f"{result:.10g}"
        else:
            result_str = str(result)
        steps.append("Evaluated via safe numeric evaluator")
        return {
            "expression": original,
            "result": result_str,
            "numeric": float(result) if isinstance(result, (int, float)) else None,
            "steps": steps,
            "error": None,
        }
    except ZeroDivisionError:
        return {"expression": original, "result": None, "error": "Division by zero"}
    except Exception as exc:
        return {"expression": original, "result": None, "error": str(exc)}


# ── LangChain Tool Wrapper ─────────────────────────────────────────────────────

class CalculatorInput(BaseModel):
    expression: str = Field(
        description=(
            "Mathematical expression to evaluate. Supports: arithmetic (+,-,*,/,**), "
            "scientific (sin, cos, sqrt, log, exp), percentages (15% of 200), "
            "statistics (mean([1,2,3])), factorial, and more. "
            "Use ** for exponentiation, not ^."
        )
    )


class CalculatorTool(BaseTool):
    name: str = "calculator"
    description: str = (
        "Perform mathematical calculations including arithmetic, algebra, "
        "scientific functions (sin, cos, log, sqrt, exp), percentages, "
        "statistics (mean, median, std), and financial calculations. "
        "Always use this tool for any numerical computation instead of estimating."
    )
    args_schema: type[BaseModel] = CalculatorInput
    return_direct: bool = False

    def _run(self, expression: str) -> str:
        result = calculate(expression)

        if result.get("error"):
            return f"❌ Calculation error: {result['error']}\n💡 Expression: `{expression}`"

        lines = [
            f"🧮 **Expression:** `{result['expression']}`",
            f"✅ **Result:** `{result['result']}`",
        ]
        if result.get("steps") and len(result["steps"]) > 1:
            lines.append("\n**Steps:**")
            for s in result["steps"]:
                lines.append(f"  • {s}")

        return "\n".join(lines)

    async def _arun(self, expression: str) -> str:
        return self._run(expression)
