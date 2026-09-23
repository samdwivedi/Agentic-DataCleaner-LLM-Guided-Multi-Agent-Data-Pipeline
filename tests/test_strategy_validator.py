"""
Adversarial unit tests for Phase 7 — Strategy Validator.

These tests exercise every validation path, including edge cases an LLM
might produce: hallucinated columns, wrong dtypes, conflicting actions,
exceeding safety thresholds, duplicate actions, and more.

Run with:
    pytest tests/test_strategy_validator.py -v
"""

from __future__ import annotations

import pytest

from app.models.strategy import CleaningStrategy, CleaningAction, ActionRegistry
from app.agents.strategy_validator import (
    StrategyValidator,
    SafetyThresholds,
    ValidatedCleaningStrategy,
    ViolationCode,
    ViolationSeverity,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

KNOWN_COLUMNS = {"age", "name", "salary", "city", "signup_date"}
COLUMN_TYPES = {
    "age":         "numeric_int",
    "name":        "categorical",
    "salary":      "numeric_float",
    "city":        "categorical",
    "signup_date": "datetime",
}
TOTAL_ROWS = 10_000


def _make_validator(thresholds: SafetyThresholds | None = None) -> StrategyValidator:
    return StrategyValidator(
        known_columns=KNOWN_COLUMNS,
        column_types=COLUMN_TYPES,
        total_row_count=TOTAL_ROWS,
        thresholds=thresholds,
    )


def _action(
    column: str = "age",
    action: str = "median_imputation",
    reason: str = "test reason",
    confidence: float = 0.9,
    parameters: dict | None = None,
) -> CleaningAction:
    return CleaningAction(
        column=column,
        action=ActionRegistry(action),
        parameters=parameters or {},
        reason=reason,
        confidence=confidence,
    )


def _strategy(*actions: CleaningAction, status: str = "success") -> CleaningStrategy:
    return CleaningStrategy(actions=list(actions), status=status)


# ═══════════════════════════════════════════════════════════════════════════════
# 1. VALID STRATEGIES
# ═══════════════════════════════════════════════════════════════════════════════


class TestValidStrategies:
    """Strategies that should pass without violations."""

    def test_empty_strategy_passes(self):
        sv = _make_validator()
        result = sv.validate(_strategy())
        assert result.is_valid is True
        assert len(result.violations) == 0
        assert result.original_action_count == 0

    def test_single_valid_action(self):
        sv = _make_validator()
        result = sv.validate(_strategy(
            _action("age", "median_imputation", confidence=0.95),
        ))
        assert result.is_valid is True
        assert result.validated_action_count == 1
        assert len(result.actions) == 1
        assert result.actions[0]["column"] == "age"

    def test_multiple_valid_actions(self):
        sv = _make_validator()
        result = sv.validate(_strategy(
            _action("age", "median_imputation"),
            _action("salary", "clamp_outliers"),
            _action("name", "mode_imputation"),
        ))
        assert result.is_valid is True
        assert result.validated_action_count == 3

    def test_none_action_passes(self):
        sv = _make_validator()
        result = sv.validate(_strategy(
            _action("age", "none"),
        ))
        assert result.is_valid is True

    def test_drop_column_within_limit(self):
        sv = _make_validator(SafetyThresholds(max_column_drop_count=2))
        result = sv.validate(_strategy(
            _action("age", "drop_column"),
            _action("city", "drop_column"),
        ))
        assert result.is_valid is True

    def test_constant_imputation_with_value_param(self):
        sv = _make_validator()
        result = sv.validate(_strategy(
            _action("name", "constant_imputation", parameters={"value": "Unknown"}),
        ))
        assert result.is_valid is True

    def test_summary_text_on_valid(self):
        sv = _make_validator()
        result = sv.validate(_strategy(_action("age", "median_imputation")))
        summary = result.summary_text()
        assert "PASSED" in summary


# ═══════════════════════════════════════════════════════════════════════════════
# 2. UNKNOWN COLUMN (LLM hallucinated a column)
# ═══════════════════════════════════════════════════════════════════════════════


class TestUnknownColumn:

    def test_hallucinated_column_rejected(self):
        sv = _make_validator()
        result = sv.validate(_strategy(
            _action("nonexistent_col", "median_imputation"),
        ))
        assert result.is_valid is False
        codes = {v.code for v in result.violations}
        assert ViolationCode.UNKNOWN_COLUMN in codes

    def test_multiple_hallucinated_columns(self):
        sv = _make_validator()
        result = sv.validate(_strategy(
            _action("ghost_a", "drop_column"),
            _action("ghost_b", "mean_imputation"),
        ))
        assert result.is_valid is False
        unknown_violations = [v for v in result.violations if v.code == ViolationCode.UNKNOWN_COLUMN]
        assert len(unknown_violations) == 2


# ═══════════════════════════════════════════════════════════════════════════════
# 3. DTYPE MISMATCH (action incompatible with column type)
# ═══════════════════════════════════════════════════════════════════════════════


class TestDtypeMismatch:

    def test_median_on_categorical_rejected(self):
        """median_imputation requires numeric, 'name' is categorical."""
        sv = _make_validator()
        result = sv.validate(_strategy(
            _action("name", "median_imputation"),
        ))
        assert result.is_valid is False
        codes = {v.code for v in result.violations}
        assert ViolationCode.DTYPE_MISMATCH in codes

    def test_mean_on_datetime_rejected(self):
        sv = _make_validator()
        result = sv.validate(_strategy(
            _action("signup_date", "mean_imputation"),
        ))
        assert result.is_valid is False
        codes = {v.code for v in result.violations}
        assert ViolationCode.DTYPE_MISMATCH in codes

    def test_clamp_on_categorical_rejected(self):
        sv = _make_validator()
        result = sv.validate(_strategy(
            _action("city", "clamp_outliers"),
        ))
        assert result.is_valid is False
        codes = {v.code for v in result.violations}
        assert ViolationCode.DTYPE_MISMATCH in codes

    def test_drop_column_on_any_type_passes(self):
        """drop_column is type-agnostic."""
        sv = _make_validator()
        result = sv.validate(_strategy(
            _action("name", "drop_column"),
        ))
        assert result.is_valid is True

    def test_mode_on_numeric_passes(self):
        """mode_imputation is allowed on numeric types too."""
        sv = _make_validator()
        result = sv.validate(_strategy(
            _action("age", "mode_imputation"),
        ))
        assert result.is_valid is True


# ═══════════════════════════════════════════════════════════════════════════════
# 4. INVALID PARAMETERS
# ═══════════════════════════════════════════════════════════════════════════════


class TestInvalidParameters:

    def test_constant_imputation_missing_value(self):
        sv = _make_validator()
        result = sv.validate(_strategy(
            _action("age", "constant_imputation", parameters={}),
        ))
        assert result.is_valid is False
        codes = {v.code for v in result.violations}
        assert ViolationCode.INVALID_PARAMETERS in codes

    def test_clamp_lower_gte_upper(self):
        sv = _make_validator()
        result = sv.validate(_strategy(
            _action("salary", "clamp_outliers", parameters={"lower": 100, "upper": 50}),
        ))
        assert result.is_valid is False
        codes = {v.code for v in result.violations}
        assert ViolationCode.INVALID_PARAMETERS in codes

    def test_clamp_non_numeric_bounds(self):
        sv = _make_validator()
        result = sv.validate(_strategy(
            _action("salary", "clamp_outliers", parameters={"lower": "abc", "upper": "xyz"}),
        ))
        assert result.is_valid is False
        codes = {v.code for v in result.violations}
        assert ViolationCode.INVALID_PARAMETERS in codes


# ═══════════════════════════════════════════════════════════════════════════════
# 5. CONFIDENCE VIOLATIONS
# ═══════════════════════════════════════════════════════════════════════════════


class TestConfidence:

    def test_confidence_below_minimum(self):
        sv = _make_validator(SafetyThresholds(min_confidence=0.5))
        result = sv.validate(_strategy(
            _action("age", "median_imputation", confidence=0.3),
        ))
        assert result.is_valid is False
        codes = {v.code for v in result.violations}
        assert ViolationCode.INVALID_CONFIDENCE in codes

    def test_confidence_at_boundary_passes(self):
        sv = _make_validator(SafetyThresholds(min_confidence=0.5))
        result = sv.validate(_strategy(
            _action("age", "median_imputation", confidence=0.5),
        ))
        assert result.is_valid is True

    def test_confidence_zero_passes_with_default_thresholds(self):
        sv = _make_validator()
        result = sv.validate(_strategy(
            _action("age", "median_imputation", confidence=0.0),
        ))
        assert result.is_valid is True


# ═══════════════════════════════════════════════════════════════════════════════
# 6. ROW DROP LIMIT
# ═══════════════════════════════════════════════════════════════════════════════


class TestRowDropLimit:

    def test_excessive_row_drops_rejected(self):
        """When row-drop actions touch too many columns relative to total."""
        sv = _make_validator(SafetyThresholds(max_row_drop_percentage=10.0))
        result = sv.validate(_strategy(
            _action("age", "drop_rows"),
            _action("salary", "drop_rows"),
            _action("name", "drop_rows"),
            _action("city", "drop_rows"),
        ))
        assert result.is_valid is False
        codes = {v.code for v in result.violations}
        assert ViolationCode.ROW_DROP_LIMIT_EXCEEDED in codes

    def test_single_row_drop_passes(self):
        sv = _make_validator(SafetyThresholds(max_row_drop_percentage=30.0))
        result = sv.validate(_strategy(
            _action("age", "drop_rows"),
        ))
        assert result.is_valid is True


# ═══════════════════════════════════════════════════════════════════════════════
# 7. COLUMN DROP LIMIT
# ═══════════════════════════════════════════════════════════════════════════════


class TestColumnDropLimit:

    def test_exceeding_column_drop_limit(self):
        sv = _make_validator(SafetyThresholds(max_column_drop_count=1))
        result = sv.validate(_strategy(
            _action("age", "drop_column"),
            _action("salary", "drop_column"),
        ))
        assert result.is_valid is False
        codes = {v.code for v in result.violations}
        assert ViolationCode.COL_DROP_LIMIT_EXCEEDED in codes

    def test_at_limit_passes(self):
        sv = _make_validator(SafetyThresholds(max_column_drop_count=2))
        result = sv.validate(_strategy(
            _action("age", "drop_column"),
            _action("salary", "drop_column"),
        ))
        assert result.is_valid is True


# ═══════════════════════════════════════════════════════════════════════════════
# 8. TRANSFORMATION SCOPE
# ═══════════════════════════════════════════════════════════════════════════════


class TestTransformationScope:

    def test_touching_all_columns_rejected(self):
        """With 5 known columns, touching all 5 = 100% scope."""
        sv = _make_validator(SafetyThresholds(max_transformation_scope=50.0))
        result = sv.validate(_strategy(
            _action("age", "median_imputation"),
            _action("name", "mode_imputation"),
            _action("salary", "mean_imputation"),
            _action("city", "mode_imputation"),
            _action("signup_date", "drop_column"),
        ))
        assert result.is_valid is False
        codes = {v.code for v in result.violations}
        assert ViolationCode.TRANSFORM_SCOPE_EXCEEDED in codes

    def test_touching_few_columns_passes(self):
        sv = _make_validator(SafetyThresholds(max_transformation_scope=50.0))
        result = sv.validate(_strategy(
            _action("age", "median_imputation"),
            _action("salary", "mean_imputation"),
        ))
        assert result.is_valid is True  # 2/5 = 40%


# ═══════════════════════════════════════════════════════════════════════════════
# 9. DUPLICATE ACTIONS
# ═══════════════════════════════════════════════════════════════════════════════


class TestDuplicateActions:

    def test_exact_duplicate_action_rejected(self):
        sv = _make_validator()
        result = sv.validate(_strategy(
            _action("age", "median_imputation"),
            _action("age", "median_imputation"),
        ))
        assert result.is_valid is False
        codes = {v.code for v in result.violations}
        assert ViolationCode.DUPLICATE_ACTION in codes

    def test_different_actions_same_column_passes(self):
        """Two *different* actions on the same column is not a duplicate."""
        sv = _make_validator()
        result = sv.validate(_strategy(
            _action("salary", "mean_imputation"),
            _action("salary", "clamp_outliers"),
        ))
        assert result.is_valid is True


# ═══════════════════════════════════════════════════════════════════════════════
# 10. CONFLICTING ACTIONS
# ═══════════════════════════════════════════════════════════════════════════════


class TestConflictingActions:

    def test_drop_and_impute_same_column(self):
        """Dropping a column AND imputing it is contradictory."""
        sv = _make_validator()
        result = sv.validate(_strategy(
            _action("age", "drop_column"),
            _action("age", "median_imputation"),
        ))
        assert result.is_valid is False
        codes = {v.code for v in result.violations}
        assert ViolationCode.CONFLICTING_ACTIONS in codes

    def test_drop_and_clamp_same_column(self):
        sv = _make_validator()
        result = sv.validate(_strategy(
            _action("salary", "drop_column"),
            _action("salary", "clamp_outliers"),
        ))
        assert result.is_valid is False
        codes = {v.code for v in result.violations}
        assert ViolationCode.CONFLICTING_ACTIONS in codes

    def test_no_conflict_on_different_columns(self):
        sv = _make_validator()
        result = sv.validate(_strategy(
            _action("age", "drop_column"),
            _action("salary", "clamp_outliers"),
        ))
        assert result.is_valid is True


# ═══════════════════════════════════════════════════════════════════════════════
# 11. ERROR STATUS FROM UPSTREAM
# ═══════════════════════════════════════════════════════════════════════════════


class TestUpstreamError:

    def test_error_strategy_immediately_rejected(self):
        strategy = CleaningStrategy(
            actions=[],
            status="error",
            error_message="LLM provider timed out.",
        )
        sv = _make_validator()
        result = sv.validate(strategy)
        assert result.is_valid is False
        assert result.validated_action_count == 0
        assert any("Upstream" in v.message for v in result.violations)


# ═══════════════════════════════════════════════════════════════════════════════
# 12. REQUIRED FIELDS
# ═══════════════════════════════════════════════════════════════════════════════


class TestRequiredFields:

    def test_empty_reason_rejected(self):
        action = CleaningAction(
            column="age",
            action=ActionRegistry.MEDIAN_IMPUTATION,
            parameters={},
            reason="",  # empty
            confidence=0.9,
        )
        sv = _make_validator()
        result = sv.validate(_strategy(action))
        assert result.is_valid is False
        codes = {v.code for v in result.violations}
        assert ViolationCode.MISSING_REQUIRED_FIELD in codes


# ═══════════════════════════════════════════════════════════════════════════════
# 13. COMBINED / ADVERSARIAL SCENARIOS
# ═══════════════════════════════════════════════════════════════════════════════


class TestAdversarialCombinations:

    def test_multiple_violations_accumulated(self):
        """A single strategy can trigger many violations at once."""
        sv = _make_validator(SafetyThresholds(max_column_drop_count=0))
        result = sv.validate(_strategy(
            _action("ghost_col", "median_imputation"),   # unknown column
            _action("name", "median_imputation"),        # dtype mismatch
            _action("age", "drop_column"),               # col drop > limit(0)
            _action("age", "median_imputation"),         # conflict with drop
        ))
        assert result.is_valid is False
        codes = {v.code for v in result.violations}
        assert ViolationCode.UNKNOWN_COLUMN in codes
        assert ViolationCode.DTYPE_MISMATCH in codes
        assert ViolationCode.COL_DROP_LIMIT_EXCEEDED in codes
        assert ViolationCode.CONFLICTING_ACTIONS in codes

    def test_validator_version_present(self):
        sv = _make_validator()
        result = sv.validate(_strategy())
        assert result.validator_version == "1.0.0"

    def test_summary_text_on_rejected(self):
        sv = _make_validator()
        result = sv.validate(_strategy(
            _action("ghost", "median_imputation"),
        ))
        summary = result.summary_text()
        assert "REJECTED" in summary
        assert "unknown_column" in summary
