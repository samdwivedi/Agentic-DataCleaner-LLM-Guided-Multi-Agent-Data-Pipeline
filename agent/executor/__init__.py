"""
Executor Agent Package
──────────────────────
Deterministic, auditable DataFrame cleaning executor.

Public API
----------
from agent.executor import ExecutorAgent, ExecutionResult, ExecutionLogEntry

executor = ExecutorAgent()
cleaned_df, result = executor.execute(df, validated_strategy)
"""

from agent.executor.models import (
    ExecutionLogEntry,
    ExecutionResult,
    ExecutionStatus,
)
from agent.executor.engine import ExecutorAgent
from agent.executor.operations import OPERATION_DISPATCH

__all__ = [
    "ExecutorAgent",
    "ExecutionLogEntry",
    "ExecutionResult",
    "ExecutionStatus",
    "OPERATION_DISPATCH",
]
