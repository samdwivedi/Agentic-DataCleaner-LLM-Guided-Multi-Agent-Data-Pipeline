"""
Comprehensive unit tests for the Phase 5 Anomaly Detector Agent.

Run with:
    pytest tests/test_anomaly.py -v
"""

from __future__ import annotations

import pandas as pd
import numpy as np
import pytest

from app.agents.anomaly_detector import (
    AnomalyDetector,
    AnomalyConfig,
    ColumnAnomalyResult,
    AnomalyReport,
)

@pytest.fixture(scope="session")
def detector() -> AnomalyDetector:
    return AnomalyDetector()


def test_normal_data(detector):
    """Normal data without outliers should return 0 outliers."""
    # Data from N(0, 1), unlikely to exceed Z=3 or IQR=1.5 bounds in a small sample
    rng = np.random.default_rng(42)
    df = pd.DataFrame({"normal": rng.normal(0, 1, size=100)})
    
    report = detector.detect(df)
    assert report.total_outliers_found == 0
    assert report.columns_analyzed == 1
    col_rep = report.column_reports[0]
    assert col_rep.outlier_count == 0


def test_extreme_outliers(detector):
    """Clear outliers should be flagged by both IQR and Z-score."""
    # 98 normal points, 2 extreme points
    data = list(np.random.default_rng(42).normal(0, 1, size=98))
    data.extend([1000.0, -1000.0])
    df = pd.DataFrame({"with_outliers": data})
    
    report = detector.detect(df)
    assert report.total_outliers_found == 2
    col_rep = report.column_reports[0]
    assert col_rep.outlier_count == 2
    assert abs(col_rep.outlier_pct - 2.0) < 0.01


def test_skewed_data():
    """Skewed data (e.g. lognormal) should flag the right tail."""
    detector = AnomalyDetector()
    rng = np.random.default_rng(42)
    df = pd.DataFrame({"skewed": rng.lognormal(mean=0, sigma=1.5, size=500)})
    
    report = detector.detect(df)
    assert report.total_outliers_found > 0
    # The upper bound should be crossed by the heavy tail
    col_rep = report.column_reports[0]
    assert col_rep.outlier_count > 0


def test_constant_column(detector):
    """Constant column has IQR=0 and std=0. Should handle safely."""
    df = pd.DataFrame({"constant": [5.0] * 100})
    report = detector.detect(df)
    
    # Standard deviation is 0, so Z-score shouldn't crash.
    # IQR is 0, so anything != 5.0 is an outlier. But here, all are 5.0, so 0 outliers.
    assert report.total_outliers_found == 0


def test_constant_column_with_one_outlier(detector):
    """Constant column with a single anomaly."""
    df = pd.DataFrame({"constant_w_outlier": [5.0] * 50 + [100.0]})
    report = detector.detect(df)
    
    assert report.total_outliers_found == 1


def test_small_dataset(detector):
    """Should safely ignore columns with too few rows to compute IQR/Z-score."""
    df = pd.DataFrame({"tiny": [1.0]})
    report = detector.detect(df)
    
    # n=1 is not enough for IQR (needs 4 for reliable quartiles, though pandas won't crash)
    # n=1 std is NaN, so Z-score is skipped.
    assert report.total_outliers_found == 0
    assert len(report.column_reports) == 0  # Should be None/skipped


def test_missing_values(detector):
    """Missing values should be dropped for statistical calculations without crashing."""
    df = pd.DataFrame({
        "with_nans": [1, 2, 3, 4, 5, 1000, np.nan, np.nan, np.nan]
    })
    report = detector.detect(df)
    assert report.total_outliers_found == 1
    
    col_rep = report.column_reports[0]
    assert col_rep.outlier_count == 1
    # 6 valid values, 1 outlier -> 16.66%
    assert abs(col_rep.outlier_pct - (1 / 6 * 100)) < 0.01


def test_categorical_and_boolean_columns_are_skipped(detector):
    """Detector should only process numerical columns."""
    df = pd.DataFrame({
        "cat": ["A", "B", "C", "D", "E"],
        "bools": [True, False, True, False, True],
        "nums": [1, 2, 3, 4, 100]
    })
    report = detector.detect(df)
    
    assert report.columns_analyzed == 1
    assert len(report.column_reports) == 1
    assert report.column_reports[0].column_name == "nums"


def test_configurable_thresholds():
    """Tuning thresholds should alter outlier detection sensitivity."""
    df = pd.DataFrame({"data": [1, 2, 3, 4, 5, 15]})
    
    # Strict thresholds: will catch 15
    strict_detector = AnomalyDetector(config=AnomalyConfig(iqr_multiplier=1.0, zscore_threshold=1.5))
    strict_rep = strict_detector.detect(df)
    assert strict_rep.total_outliers_found > 0
    
    # Loose thresholds: will NOT catch 15
    loose_detector = AnomalyDetector(config=AnomalyConfig(iqr_multiplier=10.0, zscore_threshold=10.0))
    loose_rep = loose_detector.detect(df)
    assert loose_rep.total_outliers_found == 0


def test_robust_zscore():
    """Robust Z-score using MAD should work properly."""
    df = pd.DataFrame({"data": [1, 2, 3, 4, 5, 1000]})
    # Standard Z-score gets distorted by 1000, but robust z-score handles it.
    
    detector = AnomalyDetector(
        config=AnomalyConfig(use_iqr=False, use_zscore=True, use_robust_zscore=True, zscore_threshold=3.0)
    )
    report = detector.detect(df)
    assert report.total_outliers_found == 1
    assert report.column_reports[0].is_robust_zscore is True
    assert "Robust Z-score" in report.column_reports[0].method


def test_disabling_methods():
    """Can disable IQR or Z-score via config."""
    df = pd.DataFrame({"data": [1, 2, 3, 4, 5, 1000]})
    
    det1 = AnomalyDetector(config=AnomalyConfig(use_iqr=False, use_zscore=False))
    rep1 = det1.detect(df)
    # Both disabled, returns None for column
    assert rep1.total_outliers_found == 0
    assert rep1.columns_analyzed == 0
    
    det2 = AnomalyDetector(config=AnomalyConfig(use_iqr=True, use_zscore=False))
    rep2 = det2.detect(df)
    assert "IQR" in rep2.column_reports[0].method
    assert "Z-score" not in rep2.column_reports[0].method


def test_summary_text_generation(detector):
    """Ensure summary_text returns a formatted string."""
    df = pd.DataFrame({"x": [1, 2, 3, 4, 100]})
    report = detector.detect(df)
    summary = report.summary_text()
    
    assert "Anomaly Detection Report" in summary
    assert "100" not in summary # just string formatting
    assert "Rows analyzed: 5" in summary
    assert "Columns analyzed: 1" in summary
    assert "x: 1 outliers" in summary
