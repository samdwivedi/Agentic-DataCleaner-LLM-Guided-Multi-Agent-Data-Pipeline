"""
Comprehensive unit tests for the Phase 3 Profiler Agent.

Test datasets
─────────────
1.  Numeric-only DataFrame       — int and float columns
2.  Categorical-only DataFrame   — object/string columns
3.  Mixed-type DataFrame         — numeric + text + bool + datetime
4.  Edge: empty DataFrame        — 0 rows, 0 columns
5.  Edge: single-row DataFrame   — statistical degeneracy
6.  Edge: single-column DataFrame
7.  Edge: all-null column
8.  Edge: constant-value column
9.  Dataset with duplicate rows
10. Dataset with negative numbers
11. Dataset with zeros-heavy column
12. High-cardinality string column (ID-like)
13. Boolean column
14. Datetime column
15. Highly skewed distribution

Each test validates structure (correct Pydantic types), values (correct
arithmetic), and behaviour (immutability of original DataFrame).

Run with:
    pytest tests/test_profiler.py -v
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest

# ── Import the public API ─────────────────────────────────────────────────────
from app.agents.profiler import (
    ProfilerAgent,
    ProfilerReport,
    ColumnProfile,
    NumericalStats,
    CategoricalStats,
    DatasetMeta,
    DuplicateInfo,
    ProblematicColumn,
)
from app.models.profiler import CategoryFrequency


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def agent() -> ProfilerAgent:
    return ProfilerAgent(top_n=10, least_n=5)


@pytest.fixture
def numeric_df() -> pd.DataFrame:
    """Pure numeric DataFrame with int and float columns."""
    rng = np.random.default_rng(42)
    return pd.DataFrame(
        {
            "age":    rng.integers(18, 80, size=100).astype(int),
            "salary": rng.normal(60_000, 15_000, size=100).astype(float),
            "score":  rng.uniform(0, 1, size=100).astype(float),
        }
    )


@pytest.fixture
def categorical_df() -> pd.DataFrame:
    """Pure categorical / string DataFrame."""
    rng = np.random.default_rng(7)
    colors     = rng.choice(["red", "green", "blue", "yellow"], size=80)
    categories = rng.choice(["A", "B", "C"], size=80)
    names      = [f"person_{i}" for i in range(80)]
    return pd.DataFrame({"color": colors, "category": categories, "name": names})


@pytest.fixture
def mixed_df() -> pd.DataFrame:
    """Mixed-type DataFrame: numeric + text + bool + datetime."""
    n = 50
    rng = np.random.default_rng(1)
    df = pd.DataFrame(
        {
            "id":        range(n),
            "value":     rng.normal(0, 1, size=n),
            "label":     rng.choice(["X", "Y", "Z"], size=n),
            "flag":      rng.choice([True, False], size=n),
            "timestamp": pd.date_range("2024-01-01", periods=n, freq="D"),
        }
    )
    # Introduce some missing values
    df.loc[0:4, "value"] = np.nan
    df.loc[10:14, "label"] = np.nan
    return df


@pytest.fixture
def duplicate_df() -> pd.DataFrame:
    """DataFrame with exact duplicate rows."""
    base = pd.DataFrame({"x": [1, 2, 3, 4, 5], "y": ["a", "b", "c", "d", "e"]})
    # Stack it twice → 5 duplicates
    return pd.concat([base, base], ignore_index=True)


@pytest.fixture
def negative_df() -> pd.DataFrame:
    """DataFrame containing negative values."""
    rng = np.random.default_rng(99)
    return pd.DataFrame(
        {
            "temp":   rng.uniform(-50, 50, size=200).astype(float),
            "profit": rng.uniform(-10_000, 10_000, size=200).astype(float),
        }
    )


@pytest.fixture
def zero_heavy_df() -> pd.DataFrame:
    """DataFrame where one column is mostly zeros."""
    vals = np.zeros(100, dtype=float)
    vals[:10] = np.arange(1, 11, dtype=float)   # 10 non-zero, 90 zero
    return pd.DataFrame({"sparse": vals, "normal": np.ones(100)})


@pytest.fixture
def high_cardinality_df() -> pd.DataFrame:
    """DataFrame with a near-unique string ID column."""
    return pd.DataFrame(
        {
            "uid":   [f"user_{i:05d}" for i in range(500)],
            "group": ["A"] * 250 + ["B"] * 250,
        }
    )


@pytest.fixture
def all_null_df() -> pd.DataFrame:
    """DataFrame with one entirely null column."""
    return pd.DataFrame(
        {
            "present": [1, 2, 3, 4, 5],
            "absent":  [None, None, None, None, None],
        }
    )


@pytest.fixture
def constant_df() -> pd.DataFrame:
    """DataFrame with a constant column."""
    return pd.DataFrame(
        {
            "varying": range(20),
            "const":   ["same"] * 20,
            "num_const": [42.0] * 20,
        }
    )


@pytest.fixture
def boolean_df() -> pd.DataFrame:
    """DataFrame with a boolean column."""
    rng = np.random.default_rng(0)
    flags = rng.choice([True, False], size=60)
    return pd.DataFrame({"flag": flags, "value": range(60)})


@pytest.fixture
def datetime_df() -> pd.DataFrame:
    """DataFrame with a datetime column."""
    dates = pd.date_range("2023-01-01", periods=30, freq="ME")
    return pd.DataFrame({"date": dates, "sales": range(30)})


@pytest.fixture
def skewed_df() -> pd.DataFrame:
    """DataFrame with a heavily right-skewed distribution (log-normal)."""
    rng = np.random.default_rng(55)
    vals = rng.lognormal(mean=0, sigma=3, size=500)
    return pd.DataFrame({"income": vals})


@pytest.fixture
def single_row_df() -> pd.DataFrame:
    return pd.DataFrame({"a": [42.0], "b": ["hello"]})


@pytest.fixture
def single_col_df() -> pd.DataFrame:
    return pd.DataFrame({"only": [1, 2, 3, 4, 5]})


@pytest.fixture
def empty_df() -> pd.DataFrame:
    return pd.DataFrame()


# ─────────────────────────────────────────────────────────────────────────────
# 1. Input validation & immutability
# ─────────────────────────────────────────────────────────────────────────────

class TestInputValidation:
    def test_raises_on_non_dataframe(self, agent):
        with pytest.raises(TypeError, match="Expected pd.DataFrame"):
            agent.profile([1, 2, 3])

    def test_raises_on_dict_input(self, agent):
        with pytest.raises(TypeError):
            agent.profile({"a": [1, 2]})

    def test_raises_on_none(self, agent):
        with pytest.raises(TypeError):
            agent.profile(None)  # type: ignore

    def test_original_df_not_modified(self, agent, mixed_df):
        original_shape  = mixed_df.shape
        original_dtypes = mixed_df.dtypes.copy()
        original_values = mixed_df.copy(deep=True)

        agent.profile(mixed_df)

        assert mixed_df.shape == original_shape
        assert mixed_df.dtypes.equals(original_dtypes)
        pd.testing.assert_frame_equal(mixed_df, original_values)

    def test_original_numeric_df_not_modified(self, agent, numeric_df):
        snapshot = numeric_df.copy(deep=True)
        agent.profile(numeric_df)
        pd.testing.assert_frame_equal(numeric_df, snapshot)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Return type & frozen model
# ─────────────────────────────────────────────────────────────────────────────

class TestReturnType:
    def test_returns_profiler_report(self, agent, numeric_df):
        report = agent.profile(numeric_df)
        assert isinstance(report, ProfilerReport)

    def test_report_is_frozen(self, agent, numeric_df):
        report = agent.profile(numeric_df)
        with pytest.raises(Exception):  # ValidationError or AttributeError
            report.profiler_version = "99.0"  # type: ignore

    def test_meta_is_frozen(self, agent, numeric_df):
        report = agent.profile(numeric_df)
        with pytest.raises(Exception):
            report.meta.row_count = 999  # type: ignore

    def test_column_profile_is_frozen(self, agent, numeric_df):
        report = agent.profile(numeric_df)
        col = report.columns[0]
        with pytest.raises(Exception):
            col.dtype = "float32"  # type: ignore

    def test_profiler_version(self, agent, numeric_df):
        report = agent.profile(numeric_df)
        assert report.profiler_version == "3.0.0"

    def test_profiled_at_is_iso8601(self, agent, numeric_df):
        report = agent.profile(numeric_df)
        # Must parse without exception
        dt = datetime.fromisoformat(report.profiled_at)
        assert dt.tzinfo is not None


# ─────────────────────────────────────────────────────────────────────────────
# 3. Dataset metadata
# ─────────────────────────────────────────────────────────────────────────────

class TestDatasetMeta:
    def test_row_and_column_counts(self, agent, numeric_df):
        report = agent.profile(numeric_df)
        assert report.meta.row_count    == 100
        assert report.meta.column_count == 3

    def test_total_cells(self, agent, numeric_df):
        report = agent.profile(numeric_df)
        assert report.meta.total_cells == 100 * 3

    def test_total_missing_no_nulls(self, agent, numeric_df):
        report = agent.profile(numeric_df)
        assert report.meta.total_missing == 0
        assert report.meta.total_missing_pct == 0.0

    def test_total_missing_with_nulls(self, agent, mixed_df):
        report = agent.profile(mixed_df)
        # value col: 5 missing; label col: 5 missing → 10 total
        assert report.meta.total_missing == 10

    def test_memory_usage_positive(self, agent, numeric_df):
        report = agent.profile(numeric_df)
        assert report.meta.memory_usage_bytes > 0

    def test_numeric_column_count(self, agent, numeric_df):
        report = agent.profile(numeric_df)
        assert report.meta.numeric_column_count == 3

    def test_categorical_column_count(self, agent, categorical_df):
        report = agent.profile(categorical_df)
        assert report.meta.categorical_column_count == 3

    def test_boolean_column_count(self, agent, boolean_df):
        report = agent.profile(boolean_df)
        assert report.meta.boolean_column_count == 1

    def test_datetime_column_count(self, agent, datetime_df):
        report = agent.profile(datetime_df)
        assert report.meta.datetime_column_count == 1

    def test_dtypes_summary_keys_are_strings(self, agent, mixed_df):
        report = agent.profile(mixed_df)
        for k in report.meta.dtypes_summary:
            assert isinstance(k, str)

    def test_empty_df_meta(self, agent, empty_df):
        report = agent.profile(empty_df)
        assert report.meta.row_count    == 0
        assert report.meta.column_count == 0
        assert report.meta.total_cells  == 0


# ─────────────────────────────────────────────────────────────────────────────
# 4. Column profiles — counts
# ─────────────────────────────────────────────────────────────────────────────

class TestColumnCounts:
    def test_column_count_matches_dataframe(self, agent, mixed_df):
        report = agent.profile(mixed_df)
        assert len(report.columns) == len(mixed_df.columns)

    def test_column_names_match(self, agent, mixed_df):
        report = agent.profile(mixed_df)
        assert [c.name for c in report.columns] == list(mixed_df.columns)

    def test_row_count_per_column(self, agent, numeric_df):
        report = agent.profile(numeric_df)
        for col in report.columns:
            assert col.row_count == 100

    def test_missing_count_zero_when_no_nulls(self, agent, numeric_df):
        report = agent.profile(numeric_df)
        for col in report.columns:
            assert col.missing_count == 0
            assert col.missing_pct   == 0.0

    def test_missing_count_correct(self, agent, mixed_df):
        report = agent.profile(mixed_df)
        value_col = report.column("value")
        assert value_col is not None
        assert value_col.missing_count == 5
        assert abs(value_col.missing_pct - (5 / 50 * 100)) < 0.01

    def test_unique_count_correct(self, agent, categorical_df):
        report = agent.profile(categorical_df)
        color_col = report.column("color")
        assert color_col is not None
        assert color_col.unique_count == 4  # red, green, blue, yellow

    def test_non_null_count_correct(self, agent, mixed_df):
        report = agent.profile(mixed_df)
        value_col = report.column("value")
        assert value_col is not None
        assert value_col.non_null_count == 45  # 50 - 5 missing

    def test_all_null_column(self, agent, all_null_df):
        report  = agent.profile(all_null_df)
        absent  = report.column("absent")
        assert absent is not None
        assert absent.missing_count == 5
        assert absent.non_null_count == 0
        assert absent.missing_pct   == 100.0


# ─────────────────────────────────────────────────────────────────────────────
# 5. Numerical statistics
# ─────────────────────────────────────────────────────────────────────────────

class TestNumericalStats:
    def test_numeric_columns_have_numerical_stats(self, agent, numeric_df):
        report = agent.profile(numeric_df)
        for col in report.columns:
            assert col.numerical_stats is not None
            assert col.categorical_stats is None

    def test_mean_correct(self, agent):
        df = pd.DataFrame({"x": [1.0, 2.0, 3.0, 4.0, 5.0]})
        report = agent.profile(df)
        ns = report.column("x").numerical_stats
        assert abs(ns.mean - 3.0) < 1e-9

    def test_median_correct(self, agent):
        df = pd.DataFrame({"x": [1.0, 2.0, 3.0, 4.0, 5.0]})
        report = agent.profile(df)
        ns = report.column("x").numerical_stats
        assert abs(ns.median - 3.0) < 1e-9

    def test_std_correct(self, agent):
        df = pd.DataFrame({"x": [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]})
        report = agent.profile(df)
        ns = report.column("x").numerical_stats
        expected_std = np.std([2, 4, 4, 4, 5, 5, 7, 9], ddof=1)
        assert abs(ns.std - expected_std) < 1e-6

    def test_min_max_correct(self, agent):
        df = pd.DataFrame({"x": [-10.0, 0.0, 5.0, 100.0]})
        report = agent.profile(df)
        ns = report.column("x").numerical_stats
        assert ns.min == -10.0
        assert ns.max == 100.0

    def test_quartiles_correct(self, agent):
        df = pd.DataFrame({"x": list(range(1, 101))})  # 1..100
        report = agent.profile(df)
        ns = report.column("x").numerical_stats
        expected_q1  = pd.Series(range(1, 101)).quantile(0.25)
        expected_q3  = pd.Series(range(1, 101)).quantile(0.75)
        expected_iqr = expected_q3 - expected_q1
        assert abs(ns.q1  - expected_q1)  < 1e-6
        assert abs(ns.q3  - expected_q3)  < 1e-6
        assert abs(ns.iqr - expected_iqr) < 1e-6

    def test_sum_correct(self, agent):
        df = pd.DataFrame({"x": [10.0, 20.0, 30.0]})
        report = agent.profile(df)
        ns = report.column("x").numerical_stats
        assert abs(ns.sum - 60.0) < 1e-9

    def test_variance_is_std_squared(self, agent, numeric_df):
        report = agent.profile(numeric_df)
        for col in report.numeric_columns():
            ns = col.numerical_stats
            assert abs(ns.variance - ns.std ** 2) < 1e-6

    def test_zero_count_correct(self, agent, zero_heavy_df):
        report = agent.profile(zero_heavy_df)
        sparse_col = report.column("sparse")
        ns = sparse_col.numerical_stats
        assert ns.zero_count == 90
        assert abs(ns.zero_pct - 90.0) < 0.01

    def test_negative_count_correct(self, agent, negative_df):
        report = agent.profile(negative_df)
        temp_col = report.column("temp")
        ns = temp_col.numerical_stats
        # We expect many negatives in [-50, 50] uniform
        assert ns.negative_count > 0
        assert ns.negative_count + ns.zero_count + ns.positive_count == len(negative_df)

    def test_positive_count_correct(self, agent):
        df = pd.DataFrame({"x": [-3.0, -1.0, 0.0, 1.0, 2.0, 3.0]})
        report = agent.profile(df)
        ns = report.column("x").numerical_stats
        assert ns.negative_count == 2
        assert ns.zero_count     == 1
        assert ns.positive_count == 3

    def test_skewness_right_skewed(self, agent, skewed_df):
        report = agent.profile(skewed_df)
        ns = report.column("income").numerical_stats
        assert ns.skewness > 0  # log-normal is right-skewed

    def test_skewness_symmetric(self, agent):
        """A symmetric distribution should have ~0 skewness."""
        df = pd.DataFrame({"x": list(range(1, 101))})
        report = agent.profile(df)
        ns = report.column("x").numerical_stats
        assert abs(ns.skewness) < 0.5   # near-symmetric

    def test_nan_handling_in_stats(self, agent, mixed_df):
        report = agent.profile(mixed_df)
        value_col = report.column("value")
        ns = value_col.numerical_stats
        # Stats computed on 45 non-null values
        expected_mean = mixed_df["value"].mean()
        assert abs(ns.mean - expected_mean) < 1e-6

    def test_value_min_max_strings(self, agent):
        df = pd.DataFrame({"x": [1.0, 5.0, 3.0]})
        report = agent.profile(df)
        col = report.column("x")
        assert col.value_min == "1.0"
        assert col.value_max == "5.0"

    def test_integer_column_stats(self, agent):
        df = pd.DataFrame({"n": [1, 2, 3, 4, 5]})
        report = agent.profile(df)
        col = report.column("n")
        assert col.numerical_stats is not None
        assert col.inferred_type in ("numeric_int", "id_candidate")

    def test_all_null_numeric_column(self, agent):
        df = pd.DataFrame({"x": [None, None, None]})
        df["x"] = df["x"].astype(float)
        report = agent.profile(df)
        col = report.column("x")
        assert col.numerical_stats is not None
        ns = col.numerical_stats
        assert ns.zero_count == 0
        assert ns.sum == 0.0


# ─────────────────────────────────────────────────────────────────────────────
# 6. Categorical statistics
# ─────────────────────────────────────────────────────────────────────────────

class TestCategoricalStats:
    def test_categorical_columns_have_categorical_stats(self, agent, categorical_df):
        report = agent.profile(categorical_df)
        for col in report.columns:
            assert col.categorical_stats is not None
            assert col.numerical_stats   is None

    def test_mode_correct(self, agent):
        df = pd.DataFrame({"c": ["a", "b", "a", "a", "c"]})
        report = agent.profile(df)
        cs = report.column("c").categorical_stats
        assert cs.mode == "a"
        assert cs.mode_count == 3

    def test_top_values_count(self, agent, categorical_df):
        """top_values should have at most top_n entries."""
        local_agent = ProfilerAgent(top_n=3, least_n=2)
        report = local_agent.profile(categorical_df)
        for col in report.categorical_columns():
            assert len(col.categorical_stats.top_values) <= 3

    def test_top_values_are_sorted_by_frequency_desc(self, agent):
        df = pd.DataFrame({"c": ["a"] * 10 + ["b"] * 5 + ["c"] * 2})
        report = agent.profile(df)
        top = report.column("c").categorical_stats.top_values
        counts = [t.count for t in top]
        assert counts == sorted(counts, reverse=True)

    def test_frequency_sums_to_lte_one(self, agent, categorical_df):
        report = agent.profile(categorical_df)
        for col in report.categorical_columns():
            cs = col.categorical_stats
            for tv in cs.top_values:
                assert 0.0 <= tv.frequency <= 1.0

    def test_string_length_stats_populated(self, agent, categorical_df):
        report = agent.profile(categorical_df)
        name_col = report.column("name")
        cs = name_col.categorical_stats
        assert cs.avg_str_length is not None
        assert cs.max_str_length is not None
        assert cs.min_str_length is not None
        assert cs.min_str_length >= 0
        assert cs.max_str_length >= cs.min_str_length

    def test_boolean_column_is_categorical(self, agent, boolean_df):
        report = agent.profile(boolean_df)
        flag_col = report.column("flag")
        assert flag_col.categorical_stats is not None
        assert flag_col.numerical_stats   is None

    def test_category_frequency_values(self, agent):
        df = pd.DataFrame({"x": ["A", "A", "A", "B", "B"]})
        report = agent.profile(df)
        cs = report.column("x").categorical_stats
        top = {tv.value: tv for tv in cs.top_values}
        assert top["A"].count == 3
        assert top["B"].count == 2
        assert abs(top["A"].frequency - 3 / 5) < 1e-6

    def test_empty_categorical_column(self, agent):
        df = pd.DataFrame({"c": pd.Series([], dtype=object)})
        report = agent.profile(df)
        cs = report.column("c").categorical_stats
        assert cs.top_values   == []
        assert cs.mode         is None
        assert cs.mode_count   == 0

    def test_datetime_column_is_categorical(self, agent, datetime_df):
        report = agent.profile(datetime_df)
        date_col = report.column("date")
        # Datetime is treated as categorical (not numeric)
        assert date_col.categorical_stats is not None


# ─────────────────────────────────────────────────────────────────────────────
# 7. Duplicate detection
# ─────────────────────────────────────────────────────────────────────────────

class TestDuplicates:
    def test_no_duplicates_in_numeric_df(self, agent, numeric_df):
        report = agent.profile(numeric_df)
        assert report.duplicates.has_duplicates is False
        assert report.duplicates.duplicate_row_count == 0

    def test_duplicates_detected(self, agent, duplicate_df):
        report = agent.profile(duplicate_df)
        assert report.duplicates.has_duplicates is True
        assert report.duplicates.duplicate_row_count == 5

    def test_duplicate_pct_correct(self, agent, duplicate_df):
        report = agent.profile(duplicate_df)
        expected_pct = 5 / 10 * 100
        assert abs(report.duplicates.duplicate_row_pct - expected_pct) < 0.01

    def test_no_duplicate_rows_single_row(self, agent, single_row_df):
        report = agent.profile(single_row_df)
        assert report.duplicates.duplicate_row_count == 0

    def test_all_rows_duplicate(self, agent):
        df = pd.DataFrame({"x": [1, 1, 1, 1], "y": ["a", "a", "a", "a"]})
        report = agent.profile(df)
        # First occurrence is kept → 3 duplicates
        assert report.duplicates.duplicate_row_count == 3


# ─────────────────────────────────────────────────────────────────────────────
# 8. Inferred types
# ─────────────────────────────────────────────────────────────────────────────

class TestInferredTypes:
    def test_integer_inferred_type(self, agent):
        df = pd.DataFrame({"n": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]})
        report = agent.profile(df)
        assert report.column("n").inferred_type in ("numeric_int", "id_candidate")

    def test_float_inferred_type(self, agent):
        df = pd.DataFrame({"f": [1.1, 2.2, 3.3]})
        report = agent.profile(df)
        assert report.column("f").inferred_type == "numeric_float"

    def test_boolean_inferred_type(self, agent, boolean_df):
        report = agent.profile(boolean_df)
        assert report.column("flag").inferred_type == "boolean"

    def test_datetime_inferred_type(self, agent, datetime_df):
        report = agent.profile(datetime_df)
        assert report.column("date").inferred_type == "datetime"

    def test_categorical_inferred_type(self, agent, categorical_df):
        report = agent.profile(categorical_df)
        assert report.column("color").inferred_type == "categorical"

    def test_id_candidate_inferred_type(self, agent, high_cardinality_df):
        report = agent.profile(high_cardinality_df)
        uid_col = report.column("uid")
        assert uid_col.inferred_type == "id_candidate"

    def test_constant_inferred_type(self, agent, constant_df):
        report = agent.profile(constant_df)
        const_col = report.column("const")
        assert const_col.inferred_type == "constant"

    def test_all_null_column_inferred_type(self, agent, all_null_df):
        report    = agent.profile(all_null_df)
        absent    = report.column("absent")
        # With 0 non-null values, unique_count=0 → constant or unknown
        assert absent.inferred_type in ("constant", "unknown", "categorical")


# ─────────────────────────────────────────────────────────────────────────────
# 9. Problematic column detection
# ─────────────────────────────────────────────────────────────────────────────

class TestProblematicColumns:
    def test_problematic_is_list(self, agent, numeric_df):
        report = agent.profile(numeric_df)
        assert isinstance(report.problematic, list)

    def test_all_null_column_flagged(self, agent, all_null_df):
        report = agent.profile(all_null_df)
        flagged = {p.column for p in report.problematic}
        assert "absent" in flagged

    def test_all_null_reason(self, agent, all_null_df):
        report = agent.profile(all_null_df)
        prob   = next(p for p in report.problematic if p.column == "absent")
        assert any("null" in r.lower() or "missing" in r.lower() for r in prob.reasons)

    def test_constant_column_flagged(self, agent, constant_df):
        report   = agent.profile(constant_df)
        flagged  = {p.column for p in report.problematic}
        assert "const" in flagged

    def test_zero_heavy_column_flagged(self, agent, zero_heavy_df):
        report   = agent.profile(zero_heavy_df)
        flagged  = {p.column for p in report.problematic}
        assert "sparse" in flagged

    def test_skewed_column_flagged(self, agent, skewed_df):
        report  = agent.profile(skewed_df)
        flagged = {p.column for p in report.problematic}
        assert "income" in flagged

    def test_id_candidate_flagged(self, agent, high_cardinality_df):
        report  = agent.profile(high_cardinality_df)
        flagged = {p.column for p in report.problematic}
        assert "uid" in flagged

    def test_clean_column_not_flagged(self, agent):
        df = pd.DataFrame({"clean": ["A", "B", "C", "D", "E", "A", "B", "C"]})
        report = agent.profile(df)
        flagged = {p.column for p in report.problematic}
        assert "clean" not in flagged

    def test_problematic_has_reasons_list(self, agent, all_null_df):
        report = agent.profile(all_null_df)
        for prob in report.problematic:
            assert isinstance(prob.reasons, list)
            assert len(prob.reasons) > 0
            for r in prob.reasons:
                assert isinstance(r, str)


# ─────────────────────────────────────────────────────────────────────────────
# 10. Edge cases
# ─────────────────────────────────────────────────────────────────────────────

class TestEdgeCases:
    def test_empty_dataframe(self, agent, empty_df):
        report = agent.profile(empty_df)
        assert report.meta.row_count    == 0
        assert report.meta.column_count == 0
        assert report.columns           == []
        assert report.duplicates.duplicate_row_count == 0

    def test_single_row_dataframe(self, agent, single_row_df):
        report = agent.profile(single_row_df)
        assert report.meta.row_count == 1
        num_col = report.column("a")
        assert num_col is not None
        # std is 0 or undefined for single row
        ns = num_col.numerical_stats
        assert ns is not None
        assert ns.std == 0.0

    def test_single_column_dataframe(self, agent, single_col_df):
        report = agent.profile(single_col_df)
        assert report.meta.column_count == 1
        assert len(report.columns) == 1

    def test_dataframe_with_only_nans(self, agent):
        df = pd.DataFrame({"a": [np.nan, np.nan], "b": [np.nan, np.nan]})
        report = agent.profile(df)
        assert report.meta.total_missing == 4

    def test_large_dataset_performance(self, agent):
        """Profiling 100k rows × 10 columns should complete in < 30 seconds."""
        import time
        rng = np.random.default_rng(42)
        df = pd.DataFrame(rng.normal(0, 1, (100_000, 10)), columns=[f"c{i}" for i in range(10)])
        t0 = time.perf_counter()
        report = agent.profile(df)
        elapsed = time.perf_counter() - t0
        assert elapsed < 30.0
        assert report.meta.row_count == 100_000

    def test_mixed_null_types(self, agent):
        """Columns with pd.NA, np.nan, and None should all be counted as missing."""
        df = pd.DataFrame(
            {
                "a": [1.0, np.nan, 3.0],
                "b": ["x", None, "z"],
            }
        )
        report = agent.profile(df)
        assert report.column("a").missing_count == 1
        assert report.column("b").missing_count == 1

    def test_negative_values_counted(self, agent, negative_df):
        report = agent.profile(negative_df)
        temp   = report.column("temp")
        ns     = temp.numerical_stats
        direct_neg = int((negative_df["temp"] < 0).sum())
        assert ns.negative_count == direct_neg

    def test_custom_top_n(self):
        agent_5 = ProfilerAgent(top_n=5)
        df = pd.DataFrame({"c": list("abcdefghij") * 3})
        report = agent_5.profile(df)
        cs = report.column("c").categorical_stats
        assert len(cs.top_values) <= 5

    def test_zero_top_n_raises(self):
        with pytest.raises(ValueError, match="top_n must be"):
            ProfilerAgent(top_n=0)

    def test_zero_least_n_raises(self):
        with pytest.raises(ValueError, match="least_n must be"):
            ProfilerAgent(least_n=0)

    def test_column_helper_returns_none_for_missing(self, agent, numeric_df):
        report = agent.profile(numeric_df)
        assert report.column("nonexistent_column") is None

    def test_numeric_columns_helper(self, agent, mixed_df):
        report = agent.profile(mixed_df)
        for col in report.numeric_columns():
            assert col.numerical_stats is not None

    def test_categorical_columns_helper(self, agent, mixed_df):
        report = agent.profile(mixed_df)
        for col in report.categorical_columns():
            assert col.categorical_stats is not None

    def test_high_missing_helper(self, agent, all_null_df):
        report = agent.profile(all_null_df)
        high   = report.high_missing(threshold=50.0)
        assert any(c.name == "absent" for c in high)

    def test_to_dict_returns_dict(self, agent, numeric_df):
        report = agent.profile(numeric_df)
        d = report.to_dict()
        assert isinstance(d, dict)
        assert "meta" in d
        assert "columns" in d

    def test_summary_text_contains_key_info(self, agent, numeric_df):
        report = agent.profile(numeric_df)
        text   = report.summary_text()
        assert "100" in text      # row count
        assert "3"   in text      # column count


# ─────────────────────────────────────────────────────────────────────────────
# 11. Integration — profile real-world-like dataset
# ─────────────────────────────────────────────────────────────────────────────

class TestIntegration:
    """End-to-end profile of a realistic heterogeneous DataFrame."""

    @pytest.fixture
    def realistic_df(self) -> pd.DataFrame:
        rng = np.random.default_rng(2024)
        n   = 300
        df  = pd.DataFrame(
            {
                "customer_id":  [f"CUST_{i:06d}" for i in range(n)],
                "age":          rng.integers(18, 90, size=n).astype(float),
                "income":       rng.lognormal(10.5, 0.5, size=n),
                "region":       rng.choice(["North", "South", "East", "West"], size=n),
                "is_premium":   rng.choice([True, False], size=n),
                "signup_date":  pd.date_range("2020-01-01", periods=n, freq="D"),
                "notes":        rng.choice(["good customer", "bad", None, "vip"], size=n),
                "score":        rng.uniform(0, 100, size=n),
                "refunds":      np.where(rng.random(n) < 0.7, 0, rng.integers(1, 5, size=n)).astype(float),
            }
        )
        # Inject missing
        df.loc[rng.choice(n, 15, replace=False), "age"]    = np.nan
        df.loc[rng.choice(n, 30, replace=False), "income"] = np.nan
        return df

    def test_full_profile_structure(self, agent, realistic_df):
        report = agent.profile(realistic_df)
        assert isinstance(report, ProfilerReport)
        assert isinstance(report.meta, DatasetMeta)
        assert isinstance(report.duplicates, DuplicateInfo)
        assert all(isinstance(c, ColumnProfile) for c in report.columns)
        assert all(isinstance(p, ProblematicColumn) for p in report.problematic)

    def test_correct_column_count(self, agent, realistic_df):
        report = agent.profile(realistic_df)
        assert report.meta.column_count == 9

    def test_customer_id_flagged_as_id(self, agent, realistic_df):
        report = agent.profile(realistic_df)
        cid    = report.column("customer_id")
        assert cid.inferred_type == "id_candidate"

    def test_age_has_numerical_stats(self, agent, realistic_df):
        report = agent.profile(realistic_df)
        age    = report.column("age")
        assert age.numerical_stats is not None
        assert age.missing_count   == 15

    def test_income_missing_count(self, agent, realistic_df):
        report = agent.profile(realistic_df)
        income = report.column("income")
        assert income.missing_count == 30

    def test_region_is_categorical(self, agent, realistic_df):
        report  = agent.profile(realistic_df)
        region  = report.column("region")
        assert region.categorical_stats is not None
        assert region.unique_count == 4

    def test_is_premium_is_boolean(self, agent, realistic_df):
        report     = agent.profile(realistic_df)
        is_premium = report.column("is_premium")
        assert is_premium.inferred_type == "boolean"

    def test_refunds_zero_heavy(self, agent, realistic_df):
        report  = agent.profile(realistic_df)
        refunds = report.column("refunds")
        ns      = refunds.numerical_stats
        # 70 % zeros → should be flagged
        assert ns.zero_pct >= 50.0

    def test_signup_date_is_datetime(self, agent, realistic_df):
        report = agent.profile(realistic_df)
        signup = report.column("signup_date")
        assert signup.inferred_type == "datetime"

    def test_serialisation_roundtrip(self, agent, realistic_df):
        """Report dict must be JSON-serialisable."""
        import json
        report = agent.profile(realistic_df)
        raw = report.to_dict()
        # Should not raise
        json.dumps(raw, default=str)

    def test_original_df_unchanged_after_full_profile(self, agent, realistic_df):
        snapshot = realistic_df.copy(deep=True)
        agent.profile(realistic_df)
        pd.testing.assert_frame_equal(realistic_df, snapshot)
