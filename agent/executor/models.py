"""
Executor Models
───────────────
Strongly-typed Pydantic v2 models for recording every mutation the
Executor performs on the working DataFrame copy.

Design invariant
----------------
Every single operation produces an ``ExecutionLogEntry``.
The overall run produces an ``ExecutionResult`` containing all entries
plus before/after metadata.  The original DataFrame is NEVER modified.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ── Execution Status ──────────────────────────────────────────────────────────

class ExecutionStatus(str, Enum):
    """Outcome of a single operation."""
    SUCCESS  = "success"
    SKIPPED  = "skipped"   # e.g. no-op because no nulls to fill
    FAILED   = "failed"    # operation raised but was caught safely


# ── Per-Operation Log Entry ───────────────────────────────────────────────────

class ExecutionLogEntry(BaseModel, frozen=True):
    """
    Immutable record of a single cleaning operation.

    Every field maps directly to the requirements:
      run_id, column, action, rows_affected, values_changed,
      before_state, after_state, execution_status, error_information.
    """

    run_id: str = Field(
        ..., description="UUID for this execution run (shared across all entries in a run).",
    )
    action_index: int = Field(
        ..., description="0-based index of this action within the strategy.",
    )
    column: str = Field(
        ..., description="Column this operation targets.",
    )
    action: str = Field(
        ..., description="The action that was executed (e.g. 'median_imputation').",
    )
    parameters: Dict[str, Any] = Field(
        default_factory=dict, description="Parameters passed to the operation.",
    )
    rows_affected: int = Field(
        0, description="Number of rows modified or removed by this operation.",
    )
    values_changed: int = Field(
        0, description="Number of individual cell values that were changed.",
    )
    before_state: Dict[str, Any] = Field(
        default_factory=dict,
        description="Snapshot of relevant column statistics BEFORE the operation.",
    )
    after_state: Dict[str, Any] = Field(
        default_factory=dict,
        description="Snapshot of relevant column statistics AFTER the operation.",
    )
    execution_status: ExecutionStatus = Field(
        ExecutionStatus.SUCCESS, description="Outcome of this operation.",
    )
    error_message: Optional[str] = Field(
        None, description="Error details if execution_status is FAILED.",
    )
    reason: str = Field(
        "", description="The LLM's stated reason for proposing this action.",
    )
    confidence: float = Field(
        0.0, description="The LLM's confidence score for this action.",
    )


# ── Overall Execution Result ──────────────────────────────────────────────────

class ExecutionResult(BaseModel, frozen=True):
    """
    Complete, immutable record of a full execution run.

    The cleaned DataFrame is NOT serialised inside this model — it is
    returned separately by the engine.  This model is purely for auditing.
    """

    run_id: str = Field(
        ..., description="UUID for this execution run.",
    )
    total_actions: int = Field(
        0, description="Total number of actions attempted.",
    )
    successful_actions: int = Field(
        0, description="Number of actions that completed successfully.",
    )
    skipped_actions: int = Field(
        0, description="Number of actions that were no-ops.",
    )
    failed_actions: int = Field(
        0, description="Number of actions that failed safely.",
    )
    total_rows_before: int = Field(
        0, description="Row count of the DataFrame before execution.",
    )
    total_rows_after: int = Field(
        0, description="Row count of the DataFrame after execution.",
    )
    total_columns_before: int = Field(
        0, description="Column count before execution.",
    )
    total_columns_after: int = Field(
        0, description="Column count after execution.",
    )
    log_entries: List[ExecutionLogEntry] = Field(
        default_factory=list, description="Per-action execution log entries.",
    )
    executor_version: str = Field(
        "1.0.0", description="Semantic version of the executor engine.",
    )

    def summary_text(self) -> str:
        """Return a concise human-readable summary."""
        lines = [
            f"Execution Result — run_id={self.run_id}",
            f"  Actions: {self.total_actions} total, "
            f"{self.successful_actions} success, "
            f"{self.skipped_actions} skipped, "
            f"{self.failed_actions} failed",
            f"  Rows:    {self.total_rows_before:,} → {self.total_rows_after:,}",
            f"  Columns: {self.total_columns_before} → {self.total_columns_after}",
        ]
        if self.failed_actions > 0:
            lines.append("\nFailed Actions:")
            for entry in self.log_entries:
                if entry.execution_status == ExecutionStatus.FAILED:
                    lines.append(
                        f"  - [{entry.column}] {entry.action}: {entry.error_message}"
                    )
        return "\n".join(lines)
