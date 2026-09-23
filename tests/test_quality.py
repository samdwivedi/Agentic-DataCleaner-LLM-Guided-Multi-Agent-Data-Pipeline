"""
Extensive unit tests for Phase 9 — Post-Cleaning Validation.

Run with:
    pytest tests/test_quality.py -v
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.agents.validator import QualityAssessor, QualityConfig, IssueSeverity


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def assessor():
    return QualityAssessor()


@pytest.fixture
def dirty_df():
    """A dataset with missing values, duplicates, outliers, and schema issues."""
    return pd.DataFrame({
        "id": [1, 2, 3, 4, 5, 6, 6, 8, 9, 10],  # Duplicate 6
        "age": [25.0, np.nan, 30.0, 400.0, 35.0, 26.0, 26.0, np.nan, 29.0, 31.0],  # 2 nulls, 1 outlier (400)
        "category": ["A", "B", "X", "A", None, "B", "B", "A", "Y", "B"]  # X, Y are invalid if allowed=['A','B']
    })


@pytest.fixture
def clean_df():
    """A perfectly clean version of the dataset."""
    return pd.DataFrame({
        "id": [1, 2, 3, 4, 5, 6, 8, 9, 10],
        "age": [25.0, 30.0, 30.0, 35.0, 35.0, 26.0, 28.0, 29.0, 31.0],
        "category": ["A", "B", "A", "A", "B", "B", "A", "A", "B"]
    })


@pytest.fixture
def empty_df():
    return pd.DataFrame({"id": [], "age": [], "category": []})


# ── 1. Metrics Computation ────────────────────────────────────────────────────

class TestMetricsComputation:
    def test_dirty_metrics(self, assessor, dirty_df):
        metrics = assessor.score_dataframe(
            dirty_df,
            expected_dtypes={"id": "int64", "age": "float64"},
            allowed_categories={"category": ["A", "B"]}
        )
        assert metrics.row_count == 10
        assert metrics.column_count == 3
        assert metrics.total_missing == 3  # 2 age, 1 category
        assert metrics.duplicate_rows == 1  # 6 is duplicated
        assert metrics.outlier_count >= 1   # age 400
        assert metrics.invalid_category_count == 2  # X, Y

    def test_clean_metrics(self, assessor, clean_df):
        metrics = assessor.score_dataframe(
            clean_df,
            expected_dtypes={"id": "int64", "age": "float64"},
            allowed_categories={"category": ["A", "B"]}
        )
        assert metrics.total_missing == 0
        assert metrics.duplicate_rows == 0
        assert metrics.outlier_count == 0
        assert metrics.invalid_category_count == 0
        assert metrics.dtype_violations == 0

    def test_dtype_violation_detection(self, assessor):
        df = pd.DataFrame({"val": ["1", "2"]})
        metrics = assessor.score_dataframe(df, expected_dtypes={"val": "int64"})
        assert metrics.dtype_violations == 1


# ── 2. Assessment and Scoring ─────────────────────────────────────────────────

class TestAssessmentScoring:
    def test_successful_cleaning(self, assessor, dirty_df, clean_df):
        report = assessor.assess(
            dirty_df, clean_df,
            allowed_categories={"category": ["A", "B"]}
        )
        assert report.is_successful is True
        assert report.improvement > 0
        assert report.quality_score_after == 100.0
        assert len(report.remaining_issues) == 0
        assert len(report.critical_failures) == 0

    def test_score_decreased_fails(self, assessor, dirty_df, clean_df):
        """Cleaning made it worse: after is dirty, before is clean."""
        report = assessor.assess(clean_df, dirty_df)
        assert report.is_successful is False
        assert report.improvement < 0
        assert any(cf.dimension == "score" for cf in report.critical_failures)

    def test_below_minimum_score_fails(self, dirty_df):
        assessor = QualityAssessor(config=QualityConfig(min_acceptable_score=99.0))
        # Even if it stays the same, if it's below minimum, it fails
        report = assessor.assess(dirty_df, dirty_df)
        assert report.is_successful is False
        assert any(cf.message.startswith("Post-cleaning score") for cf in report.critical_failures)


# ── 3. Critical Failures ──────────────────────────────────────────────────────

class TestCriticalFailures:
    def test_all_rows_deleted(self, assessor, dirty_df, empty_df):
        report = assessor.assess(dirty_df, empty_df)
        assert report.is_successful is False
        assert any(cf.message == "All rows were deleted during cleaning." for cf in report.critical_failures)

    def test_all_columns_deleted(self, assessor, dirty_df):
        df_after = pd.DataFrame(index=range(10)) # 10 rows, 0 columns
        report = assessor.assess(dirty_df, df_after)
        assert report.is_successful is False
        assert any(cf.message == "All columns were deleted during cleaning." for cf in report.critical_failures)

    def test_missing_percentage_increased(self, assessor, clean_df, dirty_df):
        report = assessor.assess(clean_df, dirty_df)
        assert report.is_successful is False
        assert any(cf.dimension == "missing" for cf in report.critical_failures)

    def test_duplicates_increased(self, assessor, clean_df, dirty_df):
        report = assessor.assess(clean_df, dirty_df)
        assert report.is_successful is False
        assert any(cf.dimension == "duplicates" for cf in report.critical_failures)


# ── 4. Remaining Issues ───────────────────────────────────────────────────────

class TestRemainingIssues:
    def test_detects_remaining_missing(self, assessor, dirty_df):
        report = assessor.assess(dirty_df, dirty_df)
        missing_issues = [i for i in report.remaining_issues if i.dimension == "missing"]
        assert len(missing_issues) > 0

    def test_detects_remaining_duplicates(self, assessor, dirty_df):
        report = assessor.assess(dirty_df, dirty_df)
        dup_issues = [i for i in report.remaining_issues if i.dimension == "duplicates"]
        assert len(dup_issues) == 1

    def test_detects_remaining_invalid_categories(self, assessor, dirty_df):
        report = assessor.assess(dirty_df, dirty_df, allowed_categories={"category": ["A", "B"]})
        cat_issues = [i for i in report.remaining_issues if i.dimension == "categories"]
        assert len(cat_issues) == 1

    def test_detects_remaining_outliers(self, assessor, dirty_df):
        report = assessor.assess(dirty_df, dirty_df)
        outlier_issues = [i for i in report.remaining_issues if i.dimension == "anomalies"]
        assert len(outlier_issues) == 1


# ── 5. Summary Text ───────────────────────────────────────────────────────────

class TestSummaryText:
    def test_success_summary(self, assessor, dirty_df, clean_df):
        report = assessor.assess(dirty_df, clean_df)
        summary = report.summary_text()
        assert "✅ SUCCESSFUL" in summary
        assert "Quality Score:" in summary

    def test_failure_summary(self, assessor, clean_df, dirty_df):
        report = assessor.assess(clean_df, dirty_df)
        summary = report.summary_text()
        assert "❌ UNSUCCESSFUL" in summary
        assert "Critical Failures" in summary
