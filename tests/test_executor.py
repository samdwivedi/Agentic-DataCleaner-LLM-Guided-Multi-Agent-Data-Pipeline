"""
Extensive unit tests for Phase 8 — Deterministic Executor.

Tests every operation, edge case, fail-safe behaviour, log entry
structure, and the guarantee that the original DataFrame is never mutated.

Run with:
    pytest tests/test_executor.py -v
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.agents.executor.agent import ExecutorAgent
from app.models.execution import ExecutionResult, ExecutionLogEntry, ExecutionStatus
from app.operations.operations import (
    median_imputation,
    mean_imputation,
    mode_imputation,
    constant_imputation,
    drop_column,
    drop_rows,
    drop_outliers,
    remove_duplicates,
    clamp_outliers,
    cap_outliers,
    standardize_categories,
    convert_datatype,
    noop,
)
from app.models.strategy_validator import ValidatedCleaningStrategy


# ── Helpers ───────────────────────────────────────────────────────────────────

def _validated_strategy(*action_dicts) -> ValidatedCleaningStrategy:
    """Build a minimal ValidatedCleaningStrategy from action dicts."""
    actions = list(action_dicts)
    return ValidatedCleaningStrategy(
        is_valid=True,
        actions=actions,
        violations=[],
        original_action_count=len(actions),
        validated_action_count=len(actions),
    )


def _action(
    column: str,
    action: str,
    parameters: dict | None = None,
    reason: str = "test",
    confidence: float = 0.9,
) -> dict:
    return {
        "column": column,
        "action": action,
        "parameters": parameters or {},
        "reason": reason,
        "confidence": confidence,
    }


def _sample_df() -> pd.DataFrame:
    """Typical test DataFrame with nulls, duplicates, and outliers."""
    return pd.DataFrame({
        "age":    [25, np.nan, 35, 40, np.nan, 28, 200, 30, 31, 29],
        "name":   ["Alice", "Bob", None, "Dave", "Eve", " alice ", "BOB", "Charlie", "Dave", "Eve"],
        "salary": [50000.0, 60000.0, np.nan, 75000.0, 80000.0, 55000.0, 60000.0, 65000.0, 70000.0, 85000.0],
        "city":   ["NYC", "LA", "NYC", "SF", "LA", "NYC", "SF", "LA", "NYC", "SF"],
    })


@pytest.fixture
def executor():
    return ExecutorAgent()


@pytest.fixture
def sample_df():
    return _sample_df()


# ═══════════════════════════════════════════════════════════════════════════════
# 1. ORIGINAL DATAFRAME IS NEVER MODIFIED
# ═══════════════════════════════════════════════════════════════════════════════


class TestImmutability:

    def test_original_df_unchanged_after_execution(self, executor, sample_df):
        original_copy = sample_df.copy()
        strategy = _validated_strategy(
            _action("age", "median_imputation"),
            _action("name", "drop_column"),
        )
        cleaned, result = executor.execute(sample_df, strategy)

        # Original must be byte-identical
        pd.testing.assert_frame_equal(sample_df, original_copy)
        # Cleaned must be different
        assert "name" not in cleaned.columns
        assert "name" in sample_df.columns

    def test_original_df_unchanged_on_failure(self, executor, sample_df):
        original_copy = sample_df.copy()
        strategy = _validated_strategy(
            _action("nonexistent", "median_imputation"),
        )
        cleaned, result = executor.execute(sample_df, strategy)
        pd.testing.assert_frame_equal(sample_df, original_copy)


# ═══════════════════════════════════════════════════════════════════════════════
# 2. IMPUTATION OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════════


class TestMedianImputation:

    def test_fills_nulls_with_median(self, sample_df):
        result_df, rows, vals = median_imputation(sample_df, "age", {})
        assert result_df["age"].isna().sum() == 0
        assert rows == 2  # two nulls in age
        assert vals == 2

    def test_no_nulls_is_noop(self):
        df = pd.DataFrame({"x": [1, 2, 3]})
        result_df, rows, vals = median_imputation(df, "x", {})
        assert rows == 0 and vals == 0

    def test_missing_column_raises(self, sample_df):
        with pytest.raises(ValueError, match="not found"):
            median_imputation(sample_df, "ghost", {})


class TestMeanImputation:

    def test_fills_nulls_with_mean(self, sample_df):
        result_df, rows, vals = mean_imputation(sample_df, "salary", {})
        assert result_df["salary"].isna().sum() == 0
        assert rows == 1

    def test_no_nulls_is_noop(self):
        df = pd.DataFrame({"x": [1.0, 2.0]})
        result_df, rows, vals = mean_imputation(df, "x", {})
        assert rows == 0


class TestModeImputation:

    def test_fills_nulls_with_mode(self):
        df = pd.DataFrame({"color": ["red", "red", "blue", None, None]})
        result_df, rows, vals = mode_imputation(df, "color", {})
        assert result_df["color"].isna().sum() == 0
        # mode is "red"
        assert result_df["color"].iloc[3] == "red"
        assert rows == 2

    def test_all_nulls_is_noop(self):
        df = pd.DataFrame({"x": [np.nan, np.nan]})
        result_df, rows, vals = mode_imputation(df, "x", {})
        assert rows == 0  # can't compute mode from all-null


class TestConstantImputation:

    def test_fills_nulls_with_constant(self, sample_df):
        result_df, rows, vals = constant_imputation(sample_df, "age", {"value": 0})
        assert result_df["age"].isna().sum() == 0
        filled_vals = result_df.loc[sample_df["age"].isna(), "age"]
        assert (filled_vals == 0).all()

    def test_missing_value_param_raises(self, sample_df):
        with pytest.raises(ValueError, match="'value' parameter"):
            constant_imputation(sample_df, "age", {})


# ═══════════════════════════════════════════════════════════════════════════════
# 3. DROP OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════════


class TestDropColumn:

    def test_removes_column(self, sample_df):
        result_df, rows, vals = drop_column(sample_df, "city", {})
        assert "city" not in result_df.columns
        assert len(result_df.columns) == len(sample_df.columns) - 1

    def test_missing_column_raises(self, sample_df):
        with pytest.raises(ValueError, match="not found"):
            drop_column(sample_df, "ghost", {})


class TestDropRows:

    def test_drops_rows_with_nulls(self, sample_df):
        result_df, rows, vals = drop_rows(sample_df, "age", {})
        assert result_df["age"].isna().sum() == 0
        assert rows == 2  # two null rows removed
        assert len(result_df) == len(sample_df) - 2

    def test_no_nulls_is_noop(self):
        df = pd.DataFrame({"x": [1, 2, 3]})
        result_df, rows, vals = drop_rows(df, "x", {})
        assert rows == 0


class TestDropOutliers:

    def test_drops_iqr_outliers(self):
        # Age 200 is clearly an outlier in [25, 28, 29, 30, 31, 35, 40]
        df = pd.DataFrame({"val": [25, 28, 29, 30, 31, 35, 40, 200]})
        result_df, rows, vals = drop_outliers(df, "val", {})
        assert rows > 0
        assert 200 not in result_df["val"].values

    def test_no_outliers_is_noop(self):
        df = pd.DataFrame({"val": [10, 11, 12, 13, 14]})
        result_df, rows, vals = drop_outliers(df, "val", {})
        assert rows == 0


class TestRemoveDuplicates:

    def test_removes_exact_duplicates(self):
        df = pd.DataFrame({
            "a": [1, 2, 1, 2],
            "b": ["x", "y", "x", "y"],
        })
        result_df, rows, vals = remove_duplicates(df, "a", {})
        assert len(result_df) == 2
        assert rows == 2

    def test_no_duplicates_is_noop(self):
        df = pd.DataFrame({"a": [1, 2, 3]})
        result_df, rows, vals = remove_duplicates(df, "a", {})
        assert rows == 0


# ═══════════════════════════════════════════════════════════════════════════════
# 4. OUTLIER CAPPING
# ═══════════════════════════════════════════════════════════════════════════════


class TestClampOutliers:

    def test_clamps_extreme_values(self):
        df = pd.DataFrame({"val": [1, 2, 3, 4, 5, 100]})
        result_df, rows, vals = clamp_outliers(df, "val", {})
        assert result_df["val"].max() < 100
        assert rows > 0

    def test_no_outliers_is_noop(self):
        df = pd.DataFrame({"val": [10, 11, 12, 13, 14]})
        result_df, rows, vals = clamp_outliers(df, "val", {})
        assert rows == 0

    def test_cap_outliers_is_alias(self):
        df = pd.DataFrame({"val": [1, 2, 3, 4, 5, 100]})
        r1, rows1, vals1 = clamp_outliers(df, "val", {})
        r2, rows2, vals2 = cap_outliers(df, "val", {})
        pd.testing.assert_frame_equal(r1, r2)


# ═══════════════════════════════════════════════════════════════════════════════
# 5. CATEGORY & TYPE OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════════


class TestStandardizeCategories:

    def test_strips_and_lowercases(self):
        df = pd.DataFrame({"color": [" Red ", "BLUE", "green", None]})
        result_df, rows, vals = standardize_categories(df, "color", {})
        assert list(result_df["color"].dropna()) == ["red", "blue", "green"]

    def test_with_mapping(self):
        df = pd.DataFrame({"status": ["Active", "INACTIVE", "active"]})
        result_df, rows, vals = standardize_categories(df, "status", {
            "mapping": {"inactive": "disabled"}
        })
        assert "disabled" in result_df["status"].values
        assert "active" in result_df["status"].values

    def test_already_clean_is_low_change(self):
        df = pd.DataFrame({"x": ["a", "b", "c"]})
        result_df, rows, vals = standardize_categories(df, "x", {})
        assert vals == 0  # already lowercase and stripped


class TestConvertDatatype:

    def test_string_to_numeric(self):
        df = pd.DataFrame({"val": ["1", "2", "3"]})
        result_df, rows, vals = convert_datatype(df, "val", {"target_dtype": "float64"})
        assert result_df["val"].dtype == np.float64

    def test_string_to_datetime(self):
        df = pd.DataFrame({"date": ["2024-01-01", "2024-06-15"]})
        result_df, rows, vals = convert_datatype(df, "date", {"target_dtype": "datetime64[ns]"})
        assert pd.api.types.is_datetime64_any_dtype(result_df["date"])

    def test_missing_target_dtype_raises(self, sample_df):
        with pytest.raises(ValueError, match="target_dtype"):
            convert_datatype(sample_df, "age", {})

    def test_coercion_on_invalid_values(self):
        """Non-convertible values become NaN instead of crashing."""
        df = pd.DataFrame({"val": ["1", "abc", "3"]})
        result_df, rows, vals = convert_datatype(df, "val", {"target_dtype": "float64"})
        assert result_df["val"].isna().sum() == 1  # "abc" → NaN


class TestNoop:

    def test_returns_unchanged(self, sample_df):
        result_df, rows, vals = noop(sample_df, "age", {})
        pd.testing.assert_frame_equal(result_df, sample_df)
        assert rows == 0 and vals == 0


# ═══════════════════════════════════════════════════════════════════════════════
# 6. EXECUTOR ENGINE — INTEGRATION
# ═══════════════════════════════════════════════════════════════════════════════


class TestExecutorEngine:

    def test_single_action_success(self, executor, sample_df):
        strategy = _validated_strategy(
            _action("age", "median_imputation"),
        )
        cleaned, result = executor.execute(sample_df, strategy)
        assert result.successful_actions == 1
        assert result.total_actions == 1
        assert cleaned["age"].isna().sum() == 0

    def test_multiple_actions(self, executor, sample_df):
        strategy = _validated_strategy(
            _action("age", "median_imputation"),
            _action("salary", "mean_imputation"),
            _action("city", "drop_column"),
        )
        cleaned, result = executor.execute(sample_df, strategy)
        assert result.successful_actions == 3
        assert cleaned["age"].isna().sum() == 0
        assert cleaned["salary"].isna().sum() == 0
        assert "city" not in cleaned.columns

    def test_noop_is_skipped(self, executor):
        df = pd.DataFrame({"x": [1, 2, 3]})
        strategy = _validated_strategy(
            _action("x", "median_imputation"),  # no nulls → skip
        )
        cleaned, result = executor.execute(df, strategy)
        assert result.skipped_actions == 1
        assert result.successful_actions == 0

    def test_failed_action_continues(self, executor, sample_df):
        """A failing action should not abort subsequent actions."""
        strategy = _validated_strategy(
            _action("ghost_col", "median_imputation"),  # will fail
            _action("age", "median_imputation"),         # should succeed
        )
        cleaned, result = executor.execute(sample_df, strategy)
        assert result.failed_actions == 1
        assert result.successful_actions == 1
        assert cleaned["age"].isna().sum() == 0

    def test_unknown_action_fails_safely(self, executor, sample_df):
        strategy = _validated_strategy(
            _action("age", "invent_column_magic"),
        )
        cleaned, result = executor.execute(sample_df, strategy)
        assert result.failed_actions == 1
        assert result.successful_actions == 0

    def test_rejects_invalid_strategy(self, executor, sample_df):
        invalid_strat = ValidatedCleaningStrategy(
            is_valid=False, actions=[], violations=[],
        )
        with pytest.raises(ValueError, match="invalid strategy"):
            executor.execute(sample_df, invalid_strat)

    def test_rejects_non_dataframe(self, executor):
        strategy = _validated_strategy()
        with pytest.raises(TypeError, match="pd.DataFrame"):
            executor.execute([1, 2, 3], strategy)

    def test_empty_strategy(self, executor, sample_df):
        strategy = _validated_strategy()  # no actions
        cleaned, result = executor.execute(sample_df, strategy)
        pd.testing.assert_frame_equal(cleaned, sample_df)
        assert result.total_actions == 0


# ═══════════════════════════════════════════════════════════════════════════════
# 7. LOG ENTRY STRUCTURE
# ═══════════════════════════════════════════════════════════════════════════════


class TestLogEntries:

    def test_log_entry_has_run_id(self, executor, sample_df):
        strategy = _validated_strategy(_action("age", "median_imputation"))
        _, result = executor.execute(sample_df, strategy)
        assert len(result.log_entries) == 1
        assert result.log_entries[0].run_id == result.run_id

    def test_log_entry_before_after_states(self, executor, sample_df):
        strategy = _validated_strategy(_action("age", "median_imputation"))
        _, result = executor.execute(sample_df, strategy)
        entry = result.log_entries[0]
        assert "null_count" in entry.before_state
        assert "null_count" in entry.after_state
        assert entry.before_state["null_count"] > 0
        assert entry.after_state["null_count"] == 0

    def test_log_entry_preserves_reason_and_confidence(self, executor, sample_df):
        strategy = _validated_strategy(
            _action("age", "median_imputation", reason="high missing", confidence=0.95),
        )
        _, result = executor.execute(sample_df, strategy)
        entry = result.log_entries[0]
        assert entry.reason == "high missing"
        assert entry.confidence == 0.95

    def test_failed_entry_has_error_message(self, executor, sample_df):
        strategy = _validated_strategy(_action("ghost", "median_imputation"))
        _, result = executor.execute(sample_df, strategy)
        entry = result.log_entries[0]
        assert entry.execution_status == ExecutionStatus.FAILED
        assert entry.error_message is not None
        assert "not found" in entry.error_message

    def test_rows_before_after_tracked(self, executor, sample_df):
        strategy = _validated_strategy(_action("age", "drop_rows"))
        _, result = executor.execute(sample_df, strategy)
        assert result.total_rows_before == 10
        assert result.total_rows_after == 8  # 2 null ages dropped

    def test_columns_before_after_tracked(self, executor, sample_df):
        strategy = _validated_strategy(_action("city", "drop_column"))
        _, result = executor.execute(sample_df, strategy)
        assert result.total_columns_before == 4
        assert result.total_columns_after == 3


# ═══════════════════════════════════════════════════════════════════════════════
# 8. EXECUTION RESULT SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════


class TestExecutionResultSummary:

    def test_summary_text_success(self, executor, sample_df):
        strategy = _validated_strategy(_action("age", "median_imputation"))
        _, result = executor.execute(sample_df, strategy)
        summary = result.summary_text()
        assert "1 success" in summary
        assert result.run_id in summary

    def test_summary_text_failure(self, executor, sample_df):
        strategy = _validated_strategy(_action("ghost", "median_imputation"))
        _, result = executor.execute(sample_df, strategy)
        summary = result.summary_text()
        assert "1 failed" in summary
        assert "Failed Actions" in summary


# ═══════════════════════════════════════════════════════════════════════════════
# 9. SEQUENTIAL ACTION CHAINING
# ═══════════════════════════════════════════════════════════════════════════════


class TestSequentialChaining:

    def test_drop_rows_then_impute(self, executor):
        """Actions execute sequentially on the evolving working copy."""
        df = pd.DataFrame({
            "a": [1, np.nan, 3, np.nan],
            "b": [10.0, 2, np.nan, 4],
        })
        strategy = _validated_strategy(
            _action("a", "drop_rows"),      # drops rows 1,3 → shape (2, 2)
            _action("b", "mean_imputation"), # row with a=3 has b=NaN → fill with 10.0
        )
        cleaned, result = executor.execute(df, strategy)
        assert len(cleaned) == 2
        assert cleaned["b"].isna().sum() == 0

    def test_drop_column_then_use_remaining(self, executor, sample_df):
        strategy = _validated_strategy(
            _action("city", "drop_column"),
            _action("age", "median_imputation"),
        )
        cleaned, result = executor.execute(sample_df, strategy)
        assert "city" not in cleaned.columns
        assert cleaned["age"].isna().sum() == 0
        assert result.successful_actions == 2
