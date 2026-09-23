"""
Strategy Validator Package
──────────────────────────
Deterministic safety layer between the LLM Strategist and the Executor.

Public API
----------
from agent.strategy_validator import (
    StrategyValidator,
    SafetyThresholds,
    ValidatedCleaningStrategy,
    StrategyViolation,
    ViolationCode,
    ViolationSeverity,
)

validator = StrategyValidator(
    known_columns={"age", "name"},
    column_types={"age": "numeric_int", "name": "categorical"},
    total_row_count=1000,
)
result = validator.validate(cleaning_strategy)
"""

from agent.strategy_validator.models import (
    SafetyThresholds,
    StrategyViolation,
    ValidatedCleaningStrategy,
    ViolationCode,
    ViolationSeverity,
    ACTION_DTYPE_COMPATIBILITY,
)
from agent.strategy_validator.engine import StrategyValidator

__all__ = [
    "StrategyValidator",
    "SafetyThresholds",
    "ValidatedCleaningStrategy",
    "StrategyViolation",
    "ViolationCode",
    "ViolationSeverity",
    "ACTION_DTYPE_COMPATIBILITY",
]
