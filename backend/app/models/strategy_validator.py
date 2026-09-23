"""
Strategy Validator Models
─────────────────────────
Strongly-typed Pydantic v2 models for the deterministic safety layer
between the LLM Strategist and the Executor.

This module defines:
* ``SafetyThresholds`` — configurable limits that prevent destructive operations.
* ``StrategyViolation`` — a single validation failure with machine-readable codes.
* ``ValidatedCleaningStrategy`` — the *only* type the Executor may accept.

Design invariant
----------------
The Executor **never** receives a raw ``CleaningStrategy``.  It receives a
``ValidatedCleaningStrategy`` whose ``is_valid`` is ``True``, guaranteeing
that every enclosed action has passed all deterministic safety checks.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

# ── Violation Severity ────────────────────────────────────────────────────────

class ViolationSeverity(str, Enum):
    """How critical a validation failure is."""
    ERROR   = "error"      # Action MUST be rejected
    WARNING = "warning"    # Action is allowed but flagged


# ── Violation Codes ───────────────────────────────────────────────────────────

class ViolationCode(str, Enum):
    """Machine-readable codes for every possible validation failure."""

    UNKNOWN_ACTION           = "unknown_action"
    UNKNOWN_COLUMN           = "unknown_column"
    DTYPE_MISMATCH           = "dtype_mismatch"
    INVALID_PARAMETERS       = "invalid_parameters"
    INVALID_CONFIDENCE       = "invalid_confidence"
    MISSING_REQUIRED_FIELD   = "missing_required_field"
    ROW_DROP_LIMIT_EXCEEDED  = "row_drop_limit_exceeded"
    COL_DROP_LIMIT_EXCEEDED  = "col_drop_limit_exceeded"
    TRANSFORM_SCOPE_EXCEEDED = "transform_scope_exceeded"
    DUPLICATE_ACTION         = "duplicate_action"
    CONFLICTING_ACTIONS      = "conflicting_actions"
    UNSAFE_THRESHOLD         = "unsafe_threshold"


# ── Safety Thresholds ─────────────────────────────────────────────────────────

class SafetyThresholds(BaseModel):
    """
    Configurable safety limits.  Any action (or combination of actions)
    that would exceed these limits is rejected deterministically.
    """

    max_row_drop_percentage: float = Field(
        30.0,
        ge=0.0, le=100.0,
        description="Maximum percentage of rows that may be dropped across all drop_rows actions combined (0-100).",
    )
    max_column_drop_count: int = Field(
        3,
        ge=0,
        description="Maximum number of columns that may be dropped in a single strategy.",
    )
    max_transformation_scope: float = Field(
        80.0,
        ge=0.0, le=100.0,
        description="Maximum percentage of columns that a strategy may touch (0-100).",
    )
    min_confidence: float = Field(
        0.0,
        ge=0.0, le=1.0,
        description="Minimum acceptable confidence score for any action.",
    )
    max_confidence: float = Field(
        1.0,
        ge=0.0, le=1.0,
        description="Maximum acceptable confidence score for any action.",
    )


# ── Data Type ↔ Action Compatibility ─────────────────────────────────────────

# Maps each action to the set of inferred_type values it is allowed to target.
# 'drop_column', 'drop_rows', and 'none' are type-agnostic (any column).
ACTION_DTYPE_COMPATIBILITY: dict[str, set | None] = {
    "drop_column":              None,   # any type
    "drop_rows":                None,   # any type
    "none":                     None,   # any type
    "median_imputation":        {"numeric_int", "numeric_float"},
    "mean_imputation":          {"numeric_int", "numeric_float"},
    "mode_imputation":          {"categorical", "boolean", "numeric_int", "numeric_float"},
    "constant_imputation":      None,   # any type (user supplies the value)
    "clamp_outliers":           {"numeric_int", "numeric_float"},
    "cap_outliers":             {"numeric_int", "numeric_float"},
    "drop_outliers":            {"numeric_int", "numeric_float"},
    "remove_duplicates":        None,   # any type (row-level operation)
    "standardize_categories":   {"categorical"},
    "convert_datatype":         None,   # any type (user supplies target dtype)
}


# ── Strategy Violation ────────────────────────────────────────────────────────

class StrategyViolation(BaseModel, frozen=True):
    """A single deterministic validation failure."""

    code: ViolationCode = Field(
        ..., description="Machine-readable violation code.",
    )
    severity: ViolationSeverity = Field(
        ViolationSeverity.ERROR, description="Severity level.",
    )
    column: str | None = Field(
        None, description="The column the violation applies to, if any.",
    )
    action: str | None = Field(
        None, description="The action string that triggered the violation.",
    )
    message: str = Field(
        ..., description="Human-readable description of what went wrong.",
    )


# ── Validated Cleaning Strategy ───────────────────────────────────────────────

class ValidatedCleaningStrategy(BaseModel, frozen=True):
    """
    The output of the StrategyValidator.

    The Executor MUST only accept instances where ``is_valid is True``.
    If ``is_valid`` is ``False``, the ``violations`` list describes every
    reason the strategy was rejected.
    """

    is_valid: bool = Field(
        ..., description="True only if every action passed all safety checks.",
    )
    actions: list[dict[str, Any]] = Field(
        default_factory=list,
        description="The validated action dicts (only meaningful when is_valid=True).",
    )
    violations: list[StrategyViolation] = Field(
        default_factory=list,
        description="All detected validation failures.",
    )
    original_action_count: int = Field(
        0, description="Number of actions in the original CleaningStrategy.",
    )
    validated_action_count: int = Field(
        0, description="Number of actions that survived validation.",
    )
    validator_version: str = Field(
        "1.0.0", description="Semantic version of the strategy validator.",
    )

    def summary_text(self) -> str:
        """Return a concise human-readable summary."""
        status = "✅ PASSED" if self.is_valid else "❌ REJECTED"
        lines = [
            f"Strategy Validation — {status}",
            f"  Original actions : {self.original_action_count}",
            f"  Validated actions: {self.validated_action_count}",
            f"  Violations found : {len(self.violations)}",
        ]
        if self.violations:
            lines.append("\nViolations:")
            for i, v in enumerate(self.violations[:15], 1):
                col_str = f"[{v.column}] " if v.column else ""
                lines.append(
                    f"  {i}. {v.severity.value.upper()} {col_str}"
                    f"({v.code.value}) {v.message}"
                )
            if len(self.violations) > 15:
                lines.append(f"  ... and {len(self.violations) - 15} more.")
        return "\n".join(lines)
