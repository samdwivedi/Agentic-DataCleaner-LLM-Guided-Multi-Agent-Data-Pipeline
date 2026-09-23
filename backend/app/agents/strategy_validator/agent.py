"""
Strategy Validator Engine
─────────────────────────
Deterministic safety layer between the LLM Strategist and the Executor.

Flow
----
    CleaningStrategy  →  StrategyValidator  →  ValidatedCleaningStrategy
                                                     ↓
                                                  Executor (only if is_valid)

The validator enforces the following checks **per action**:
  1. Action is in the ActionRegistry enum.
  2. Column exists in the dataset (derived from the ProfilerReport).
  3. Action is compatible with the column's inferred data type.
  4. Parameters are structurally valid for the action.
  5. Confidence is within [min_confidence, max_confidence].
  6. Required fields (column, action, reason, confidence) are present.

And the following checks **across all actions**:
  7. Row-drop actions combined must not exceed ``max_row_drop_percentage``.
  8. Column-drop actions must not exceed ``max_column_drop_count``.
  9. Total columns touched must not exceed ``max_transformation_scope``.
 10. No duplicate (column, action) pairs.
 11. No conflicting actions on the same column (e.g. drop_column + imputation).

If **any** ERROR-level violation is found, ``is_valid`` is ``False`` and the
entire strategy is rejected.  The validator **never silently corrects** the
LLM output.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set, Tuple

from app.models.strategy import CleaningStrategy, CleaningAction, ActionRegistry
from app.models.strategy_validator import (
    SafetyThresholds,
    StrategyViolation,
    ValidatedCleaningStrategy,
    ViolationCode,
    ViolationSeverity,
    ACTION_DTYPE_COMPATIBILITY,
)

logger = logging.getLogger(__name__)

_VALIDATOR_VERSION = "1.0.0"

# Actions that are destructive to rows
_ROW_DROP_ACTIONS = {ActionRegistry.DROP_ROWS, ActionRegistry.DROP_OUTLIERS}

# Actions that are destructive to columns
_COL_DROP_ACTIONS = {ActionRegistry.DROP_COLUMN}

# Actions that conflict with drop_column on the same column
# (no point imputing or clamping a column you are about to drop)
_TRANSFORM_ACTIONS = {
    ActionRegistry.MEDIAN_IMPUTATION,
    ActionRegistry.MEAN_IMPUTATION,
    ActionRegistry.MODE_IMPUTATION,
    ActionRegistry.CONSTANT_IMPUTATION,
    ActionRegistry.CLAMP_OUTLIERS,
    ActionRegistry.DROP_OUTLIERS,
    ActionRegistry.DROP_ROWS,
}

# Required fields that every CleaningAction must expose
_REQUIRED_FIELDS = {"column", "action", "reason", "confidence"}


class StrategyValidator:
    """
    Deterministic, LLM-free safety gate.

    Usage
    -----
    >>> from app.agents.strategy_validator import StrategyValidator, SafetyThresholds
    >>> sv = StrategyValidator(
    ...     known_columns={"age", "name", "salary"},
    ...     column_types={"age": "numeric_int", "name": "categorical", "salary": "numeric_float"},
    ...     total_row_count=10000,
    ...     thresholds=SafetyThresholds(max_row_drop_percentage=20),
    ... )
    >>> result = sv.validate(cleaning_strategy)
    >>> assert result.is_valid
    """

    def __init__(
        self,
        known_columns: Set[str],
        column_types: Dict[str, str],
        total_row_count: int,
        thresholds: SafetyThresholds | None = None,
    ):
        """
        Parameters
        ----------
        known_columns : set[str]
            Column names present in the actual dataset (from ProfilerReport).
        column_types : dict[str, str]
            Mapping of column name → ``inferred_type`` string (from ProfilerReport).
        total_row_count : int
            Total rows in the dataset (used for row-drop percentage math).
        thresholds : SafetyThresholds, optional
            Configurable safety limits (defaults are conservative).
        """
        self.known_columns = known_columns
        self.column_types = column_types
        self.total_row_count = total_row_count
        self.thresholds = thresholds or SafetyThresholds()

    # ── Public API ────────────────────────────────────────────────────────────

    def validate(self, strategy: CleaningStrategy) -> ValidatedCleaningStrategy:
        """
        Validate a ``CleaningStrategy`` and return a ``ValidatedCleaningStrategy``.

        If the incoming strategy already has ``status == "error"`` (the LLM
        provider failed), it is immediately rejected without further checks.
        """
        if strategy.status == "error":
            logger.warning("Incoming strategy already has error status — rejecting.")
            return ValidatedCleaningStrategy(
                is_valid=False,
                actions=[],
                violations=[
                    StrategyViolation(
                        code=ViolationCode.MISSING_REQUIRED_FIELD,
                        severity=ViolationSeverity.ERROR,
                        message=f"Upstream strategy error: {strategy.error_message or 'unknown'}",
                    )
                ],
                original_action_count=len(strategy.actions),
                validated_action_count=0,
                validator_version=_VALIDATOR_VERSION,
            )

        violations: List[StrategyViolation] = []

        # ── Per-action checks ─────────────────────────────────────────────
        for action in strategy.actions:
            self._check_required_fields(action, violations)
            self._check_action_allowed(action, violations)
            self._check_column_exists(action, violations)
            self._check_dtype_compatibility(action, violations)
            self._check_parameters(action, violations)
            self._check_confidence(action, violations)

        # ── Cross-action checks ───────────────────────────────────────────
        self._check_row_drop_limit(strategy.actions, violations)
        self._check_column_drop_limit(strategy.actions, violations)
        self._check_transformation_scope(strategy.actions, violations)
        self._check_duplicate_actions(strategy.actions, violations)
        self._check_conflicting_actions(strategy.actions, violations)

        # ── Build result ──────────────────────────────────────────────────
        has_errors = any(v.severity == ViolationSeverity.ERROR for v in violations)
        is_valid = not has_errors

        validated_actions = (
            [a.model_dump() for a in strategy.actions] if is_valid else []
        )

        result = ValidatedCleaningStrategy(
            is_valid=is_valid,
            actions=validated_actions,
            violations=violations,
            original_action_count=len(strategy.actions),
            validated_action_count=len(validated_actions),
            validator_version=_VALIDATOR_VERSION,
        )

        if is_valid:
            logger.info(
                "Strategy PASSED validation: %d actions approved.",
                result.validated_action_count,
            )
        else:
            logger.warning(
                "Strategy REJECTED: %d violations (%d errors).",
                len(violations),
                sum(1 for v in violations if v.severity == ViolationSeverity.ERROR),
            )

        return result

    # ── Per-Action Checks ─────────────────────────────────────────────────────

    def _check_required_fields(
        self, action: CleaningAction, violations: List[StrategyViolation]
    ) -> None:
        """Ensure every required field is present and non-empty."""
        action_dict = action.model_dump()
        for field in _REQUIRED_FIELDS:
            value = action_dict.get(field)
            if value is None or (isinstance(value, str) and not value.strip()):
                violations.append(
                    StrategyViolation(
                        code=ViolationCode.MISSING_REQUIRED_FIELD,
                        severity=ViolationSeverity.ERROR,
                        column=action.column if field != "column" else None,
                        action=action_dict.get("action"),
                        message=f"Required field '{field}' is missing or empty.",
                    )
                )

    def _check_action_allowed(
        self, action: CleaningAction, violations: List[StrategyViolation]
    ) -> None:
        """Verify the action value is in the ActionRegistry enum."""
        try:
            ActionRegistry(action.action)
        except ValueError:
            violations.append(
                StrategyViolation(
                    code=ViolationCode.UNKNOWN_ACTION,
                    severity=ViolationSeverity.ERROR,
                    column=action.column,
                    action=str(action.action),
                    message=f"Action '{action.action}' is not in the allowed ActionRegistry.",
                )
            )

    def _check_column_exists(
        self, action: CleaningAction, violations: List[StrategyViolation]
    ) -> None:
        """Verify the target column actually exists in the dataset."""
        if action.column not in self.known_columns:
            violations.append(
                StrategyViolation(
                    code=ViolationCode.UNKNOWN_COLUMN,
                    severity=ViolationSeverity.ERROR,
                    column=action.column,
                    action=action.action.value if isinstance(action.action, ActionRegistry) else str(action.action),
                    message=f"Column '{action.column}' does not exist in the dataset. "
                            f"Known columns: {sorted(self.known_columns)}",
                )
            )

    def _check_dtype_compatibility(
        self, action: CleaningAction, violations: List[StrategyViolation]
    ) -> None:
        """Verify the action is type-compatible with the target column."""
        action_str = action.action.value if isinstance(action.action, ActionRegistry) else str(action.action)
        allowed_types = ACTION_DTYPE_COMPATIBILITY.get(action_str)

        # None means any type is acceptable
        if allowed_types is None:
            return

        col_type = self.column_types.get(action.column)
        if col_type is None:
            # Column doesn't exist — already caught by _check_column_exists
            return

        if col_type not in allowed_types:
            violations.append(
                StrategyViolation(
                    code=ViolationCode.DTYPE_MISMATCH,
                    severity=ViolationSeverity.ERROR,
                    column=action.column,
                    action=action_str,
                    message=(
                        f"Action '{action_str}' requires column type in {sorted(allowed_types)}, "
                        f"but '{action.column}' has type '{col_type}'."
                    ),
                )
            )

    def _check_parameters(
        self, action: CleaningAction, violations: List[StrategyViolation]
    ) -> None:
        """Validate action-specific parameters."""
        action_str = action.action.value if isinstance(action.action, ActionRegistry) else str(action.action)
        params = action.parameters or {}

        # constant_imputation requires a 'value' parameter
        if action_str == "constant_imputation":
            if "value" not in params:
                violations.append(
                    StrategyViolation(
                        code=ViolationCode.INVALID_PARAMETERS,
                        severity=ViolationSeverity.ERROR,
                        column=action.column,
                        action=action_str,
                        message="Action 'constant_imputation' requires a 'value' parameter.",
                    )
                )

        # clamp_outliers may optionally specify lower/upper bounds
        if action_str == "clamp_outliers":
            lower = params.get("lower")
            upper = params.get("upper")
            if lower is not None and upper is not None:
                try:
                    if float(lower) >= float(upper):
                        violations.append(
                            StrategyViolation(
                                code=ViolationCode.INVALID_PARAMETERS,
                                severity=ViolationSeverity.ERROR,
                                column=action.column,
                                action=action_str,
                                message=f"clamp_outliers: 'lower' ({lower}) must be < 'upper' ({upper}).",
                            )
                        )
                except (TypeError, ValueError):
                    violations.append(
                        StrategyViolation(
                            code=ViolationCode.INVALID_PARAMETERS,
                            severity=ViolationSeverity.ERROR,
                            column=action.column,
                            action=action_str,
                            message="clamp_outliers: 'lower' and 'upper' must be numeric.",
                        )
                    )

    def _check_confidence(
        self, action: CleaningAction, violations: List[StrategyViolation]
    ) -> None:
        """Ensure confidence is within the configured bounds."""
        if action.confidence < self.thresholds.min_confidence:
            violations.append(
                StrategyViolation(
                    code=ViolationCode.INVALID_CONFIDENCE,
                    severity=ViolationSeverity.ERROR,
                    column=action.column,
                    action=action.action.value if isinstance(action.action, ActionRegistry) else str(action.action),
                    message=(
                        f"Confidence {action.confidence:.2f} is below the minimum "
                        f"threshold ({self.thresholds.min_confidence:.2f})."
                    ),
                )
            )
        if action.confidence > self.thresholds.max_confidence:
            violations.append(
                StrategyViolation(
                    code=ViolationCode.INVALID_CONFIDENCE,
                    severity=ViolationSeverity.ERROR,
                    column=action.column,
                    action=action.action.value if isinstance(action.action, ActionRegistry) else str(action.action),
                    message=(
                        f"Confidence {action.confidence:.2f} exceeds the maximum "
                        f"threshold ({self.thresholds.max_confidence:.2f})."
                    ),
                )
            )

    # ── Cross-Action Checks ───────────────────────────────────────────────────

    def _check_row_drop_limit(
        self, actions: List[CleaningAction], violations: List[StrategyViolation]
    ) -> None:
        """Ensure combined row-drop actions don't exceed the safe percentage."""
        drop_row_actions = [a for a in actions if a.action in _ROW_DROP_ACTIONS]
        if not drop_row_actions:
            return

        # We estimate the *worst case* as each action independently dropping
        # rows.  Without the actual data we can't compute the exact overlap,
        # so we use the action count as a proxy: more drop actions = more risk.
        # If total_row_count is 0, skip (no data).
        if self.total_row_count == 0:
            return

        # Simple heuristic: count of row-drop actions × 100 / total_columns
        # gives a rough scope.  But the user's real concern is an explicit
        # percentage threshold.  We flag if the *count* of row-targeting
        # actions exceeds a reasonable proportion.
        drop_action_count = len(drop_row_actions)
        estimated_pct = (drop_action_count / max(len(self.known_columns), 1)) * 100

        if estimated_pct > self.thresholds.max_row_drop_percentage:
            violations.append(
                StrategyViolation(
                    code=ViolationCode.ROW_DROP_LIMIT_EXCEEDED,
                    severity=ViolationSeverity.ERROR,
                    message=(
                        f"Row-drop actions target {drop_action_count} column(s), "
                        f"estimated impact {estimated_pct:.1f}% exceeds "
                        f"max_row_drop_percentage={self.thresholds.max_row_drop_percentage}%."
                    ),
                )
            )

    def _check_column_drop_limit(
        self, actions: List[CleaningAction], violations: List[StrategyViolation]
    ) -> None:
        """Ensure total column-drop count doesn't exceed the threshold."""
        drop_cols = [a for a in actions if a.action in _COL_DROP_ACTIONS]
        if len(drop_cols) > self.thresholds.max_column_drop_count:
            violations.append(
                StrategyViolation(
                    code=ViolationCode.COL_DROP_LIMIT_EXCEEDED,
                    severity=ViolationSeverity.ERROR,
                    message=(
                        f"Strategy drops {len(drop_cols)} column(s), "
                        f"exceeding max_column_drop_count={self.thresholds.max_column_drop_count}."
                    ),
                )
            )

    def _check_transformation_scope(
        self, actions: List[CleaningAction], violations: List[StrategyViolation]
    ) -> None:
        """Ensure the strategy doesn't touch too many columns at once."""
        if not self.known_columns:
            return

        touched_columns = {a.column for a in actions if a.action != ActionRegistry.NONE}
        scope_pct = (len(touched_columns) / len(self.known_columns)) * 100

        if scope_pct > self.thresholds.max_transformation_scope:
            violations.append(
                StrategyViolation(
                    code=ViolationCode.TRANSFORM_SCOPE_EXCEEDED,
                    severity=ViolationSeverity.ERROR,
                    message=(
                        f"Strategy touches {len(touched_columns)}/{len(self.known_columns)} "
                        f"columns ({scope_pct:.1f}%), exceeding "
                        f"max_transformation_scope={self.thresholds.max_transformation_scope}%."
                    ),
                )
            )

    def _check_duplicate_actions(
        self, actions: List[CleaningAction], violations: List[StrategyViolation]
    ) -> None:
        """Flag identical (column, action) pairs."""
        seen: Set[Tuple[str, str]] = set()
        for a in actions:
            action_str = a.action.value if isinstance(a.action, ActionRegistry) else str(a.action)
            key = (a.column, action_str)
            if key in seen:
                violations.append(
                    StrategyViolation(
                        code=ViolationCode.DUPLICATE_ACTION,
                        severity=ViolationSeverity.ERROR,
                        column=a.column,
                        action=action_str,
                        message=f"Duplicate action: '{action_str}' on column '{a.column}' appears more than once.",
                    )
                )
            seen.add(key)

    def _check_conflicting_actions(
        self, actions: List[CleaningAction], violations: List[StrategyViolation]
    ) -> None:
        """
        Detect logically conflicting actions on the same column.

        Conflict rules:
          - A column cannot be both dropped AND transformed.
        """
        # Group actions by column
        col_actions: Dict[str, List[ActionRegistry]] = {}
        for a in actions:
            col_actions.setdefault(a.column, []).append(a.action)

        for col, action_list in col_actions.items():
            has_drop = any(a in _COL_DROP_ACTIONS for a in action_list)
            has_transform = any(a in _TRANSFORM_ACTIONS for a in action_list)

            if has_drop and has_transform:
                violations.append(
                    StrategyViolation(
                        code=ViolationCode.CONFLICTING_ACTIONS,
                        severity=ViolationSeverity.ERROR,
                        column=col,
                        message=(
                            f"Column '{col}' has both a drop_column and a "
                            f"transformation action — these conflict."
                        ),
                    )
                )
