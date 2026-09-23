"""
Strategy Validator Package
──────────────────────────
Deterministic safety layer between the LLM Strategist and the Executor.

Public API
----------
from app.agents.strategy_validator import (
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

from app.agents.strategy_validator.agent import StrategyValidator
from app.models.strategy_validator import (
    ACTION_DTYPE_COMPATIBILITY,
    SafetyThresholds,
    StrategyViolation,
    ValidatedCleaningStrategy,
    ViolationCode,
    ViolationSeverity,
)

__all__ = [
    "ACTION_DTYPE_COMPATIBILITY",
    "SafetyThresholds",
    "StrategyValidator",
    "StrategyViolation",
    "ValidatedCleaningStrategy",
    "ViolationCode",
    "ViolationSeverity",
]
