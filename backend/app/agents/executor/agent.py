"""
Executor Engine
───────────────
Deterministic cleaning executor.  Receives a ``ValidatedCleaningStrategy``
and applies each action sequentially on a **working copy** of the DataFrame.

Flow
----
    ValidatedCleaningStrategy
            ↓
       ExecutorAgent.execute(df, strategy)
            ↓
    (cleaned_df, ExecutionResult)

Guarantees
----------
* The original DataFrame is **never** modified.
* Every operation is dispatched through a static lookup table — no
  ``eval()``, ``exec()``, or dynamic code execution.
* If any single operation fails, the error is logged and the executor
  continues with the remaining actions on the last-good state.
* A detailed ``ExecutionResult`` with per-action ``ExecutionLogEntry``
  records is always returned.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Tuple

import pandas as pd

from app.models.strategy_validator import ValidatedCleaningStrategy
from app.models.execution import (
    ExecutionLogEntry,
    ExecutionResult,
    ExecutionStatus,
)
from app.operations.operations import OPERATION_DISPATCH

logger = logging.getLogger(__name__)

_EXECUTOR_VERSION = "1.0.0"


class ExecutorAgent:
    """
    Deterministic, auditable DataFrame cleaning executor.

    Usage
    -----
    >>> from app.agents.executor import ExecutorAgent
    >>> executor = ExecutorAgent()
    >>> cleaned_df, result = executor.execute(df, validated_strategy)
    """

    def execute(
        self,
        df: pd.DataFrame,
        strategy: ValidatedCleaningStrategy,
    ) -> Tuple[pd.DataFrame, ExecutionResult]:
        """
        Apply every action in *strategy* to a **copy** of *df*.

        Parameters
        ----------
        df : pd.DataFrame
            The original dataset.  It is NEVER modified.
        strategy : ValidatedCleaningStrategy
            Must have ``is_valid == True``.

        Returns
        -------
        (pd.DataFrame, ExecutionResult)
            The cleaned DataFrame and an immutable audit log.

        Raises
        ------
        ValueError
            If ``strategy.is_valid`` is ``False``.
        TypeError
            If ``df`` is not a pandas DataFrame.
        """
        if not isinstance(df, pd.DataFrame):
            raise TypeError(f"Expected pd.DataFrame, got {type(df).__name__}")
        if not strategy.is_valid:
            raise ValueError(
                "Executor received an invalid strategy. "
                "Only ValidatedCleaningStrategy with is_valid=True is accepted."
            )

        run_id = str(uuid.uuid4())
        rows_before = len(df)
        cols_before = len(df.columns)

        logger.info(
            "ExecutorAgent starting run=%s | %d actions | shape=%s",
            run_id, len(strategy.actions), df.shape,
        )

        # ── Work on a copy ────────────────────────────────────────────────
        working_df = df.copy()
        log_entries: List[ExecutionLogEntry] = []
        success_count = 0
        skip_count = 0
        fail_count = 0

        for idx, action_dict in enumerate(strategy.actions):
            action_name = action_dict.get("action", "unknown")
            column = action_dict.get("column", "unknown")
            parameters = action_dict.get("parameters", {})
            reason = action_dict.get("reason", "")
            confidence = action_dict.get("confidence", 0.0)

            # ── Before-state snapshot ─────────────────────────────────────
            before_state = self._snapshot(working_df, column)

            # ── Dispatch ──────────────────────────────────────────────────
            op_fn = OPERATION_DISPATCH.get(action_name)
            if op_fn is None:
                entry = ExecutionLogEntry(
                    run_id=run_id,
                    action_index=idx,
                    column=column,
                    action=action_name,
                    parameters=parameters,
                    before_state=before_state,
                    after_state=before_state,
                    execution_status=ExecutionStatus.FAILED,
                    error_message=f"No operation registered for action '{action_name}'.",
                    reason=reason,
                    confidence=confidence,
                )
                log_entries.append(entry)
                fail_count += 1
                logger.warning("Action %d [%s.%s]: UNKNOWN ACTION", idx, column, action_name)
                continue

            try:
                new_df, rows_affected, values_changed = op_fn(working_df, column, parameters)
            except Exception as e:
                # ── Fail safely: preserve last-good state ─────────────────
                after_state = self._snapshot(working_df, column)
                entry = ExecutionLogEntry(
                    run_id=run_id,
                    action_index=idx,
                    column=column,
                    action=action_name,
                    parameters=parameters,
                    before_state=before_state,
                    after_state=after_state,
                    execution_status=ExecutionStatus.FAILED,
                    error_message=str(e),
                    reason=reason,
                    confidence=confidence,
                )
                log_entries.append(entry)
                fail_count += 1
                logger.error(
                    "Action %d [%s.%s]: FAILED — %s", idx, column, action_name, e,
                )
                continue

            # ── Check for no-op ───────────────────────────────────────────
            if rows_affected == 0 and values_changed == 0:
                after_state = self._snapshot(new_df, column)
                entry = ExecutionLogEntry(
                    run_id=run_id,
                    action_index=idx,
                    column=column,
                    action=action_name,
                    parameters=parameters,
                    rows_affected=0,
                    values_changed=0,
                    before_state=before_state,
                    after_state=after_state,
                    execution_status=ExecutionStatus.SKIPPED,
                    reason=reason,
                    confidence=confidence,
                )
                log_entries.append(entry)
                skip_count += 1
                logger.info("Action %d [%s.%s]: SKIPPED (no-op)", idx, column, action_name)
                working_df = new_df
                continue

            # ── Success ───────────────────────────────────────────────────
            working_df = new_df
            after_state = self._snapshot(working_df, column)
            entry = ExecutionLogEntry(
                run_id=run_id,
                action_index=idx,
                column=column,
                action=action_name,
                parameters=parameters,
                rows_affected=rows_affected,
                values_changed=values_changed,
                before_state=before_state,
                after_state=after_state,
                execution_status=ExecutionStatus.SUCCESS,
                reason=reason,
                confidence=confidence,
            )
            log_entries.append(entry)
            success_count += 1
            logger.info(
                "Action %d [%s.%s]: SUCCESS — %d rows affected, %d values changed",
                idx, column, action_name, rows_affected, values_changed,
            )

        # ── Build result ──────────────────────────────────────────────────
        result = ExecutionResult(
            run_id=run_id,
            total_actions=len(strategy.actions),
            successful_actions=success_count,
            skipped_actions=skip_count,
            failed_actions=fail_count,
            total_rows_before=rows_before,
            total_rows_after=len(working_df),
            total_columns_before=cols_before,
            total_columns_after=len(working_df.columns),
            log_entries=log_entries,
            executor_version=_EXECUTOR_VERSION,
        )

        logger.info(
            "ExecutorAgent finished run=%s | %d success, %d skipped, %d failed | "
            "rows %d→%d, cols %d→%d",
            run_id, success_count, skip_count, fail_count,
            rows_before, len(working_df), cols_before, len(working_df.columns),
        )

        return working_df, result

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _snapshot(df: pd.DataFrame, column: str) -> Dict[str, Any]:
        """
        Capture a lightweight statistical snapshot of a column for the log.
        If the column doesn't exist (e.g. after a drop), return shape info only.
        """
        snap: Dict[str, Any] = {
            "row_count": len(df),
            "column_count": len(df.columns),
        }

        if column not in df.columns:
            snap["column_exists"] = False
            return snap

        snap["column_exists"] = True
        series = df[column]
        snap["dtype"] = str(series.dtype)
        snap["null_count"] = int(series.isna().sum())
        snap["non_null_count"] = int(series.notna().sum())

        # Basic stats for numeric columns
        if pd.api.types.is_numeric_dtype(series):
            non_null = series.dropna()
            if len(non_null) > 0:
                snap["mean"] = float(non_null.mean())
                snap["median"] = float(non_null.median())
                snap["min"] = float(non_null.min())
                snap["max"] = float(non_null.max())
        else:
            # Unique count for categorical-like columns
            snap["unique_count"] = int(series.nunique())

        return snap
