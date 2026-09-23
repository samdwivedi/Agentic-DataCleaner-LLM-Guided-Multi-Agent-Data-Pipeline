"""
Anomaly Detector Engine
───────────────────────
Deterministic, LLM-free DataFrame anomaly detection engine.

Key guarantees
--------------
* The input DataFrame is NEVER modified.
* Returns a fully validated, frozen ``AnomalyReport``.
* Operates based strictly on ``AnomalyConfig``.
* Safely skips non-numeric and boolean columns.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List

import pandas as pd
import numpy as np

from app.models.anomaly import (
    AnomalyConfig,
    ColumnAnomalyResult,
    AnomalyReport,
)

logger = logging.getLogger(__name__)

_DETECTOR_VERSION = "1.0.0"


class AnomalyDetector:
    """
    Deterministic DataFrame anomaly detector.
    """

    def __init__(self, config: AnomalyConfig = None):
        """Initialize with an optional configuration. If None, uses defaults."""
        self.config = config if config is not None else AnomalyConfig()

    def detect(self, df: pd.DataFrame) -> AnomalyReport:
        """
        Run anomaly detection on numerical columns of *df* and return an 
        immutable ``AnomalyReport``.

        Parameters
        ----------
        df : pd.DataFrame
            The DataFrame to analyze.

        Returns
        -------
        AnomalyReport
            Fully validated, frozen anomaly report.
        """
        if not isinstance(df, pd.DataFrame):
            raise TypeError(f"Expected pd.DataFrame, got {type(df).__name__}")

        logger.info("AnomalyDetector.detect() → shape=%s", df.shape)

        column_reports: List[ColumnAnomalyResult] = []
        total_rows = len(df)
        total_outliers_found = 0
        columns_analyzed = 0

        # Only analyze numeric columns, exclude booleans
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        bool_cols = df.select_dtypes(include=["bool", "boolean"]).columns
        valid_cols = [c for c in numeric_cols if c not in bool_cols]

        for col_name in valid_cols:
            series = df[col_name]
            result = self._analyze_column(str(col_name), series)
            if result is not None:
                column_reports.append(result)
                total_outliers_found += result.outlier_count
                columns_analyzed += 1

        # ── Assemble report ────────────────────────────────────────────────
        report = AnomalyReport(
            total_rows=total_rows,
            columns_analyzed=columns_analyzed,
            total_outliers_found=total_outliers_found,
            column_reports=column_reports,
            analyzed_at=datetime.now(timezone.utc).isoformat(),
            detector_version=_DETECTOR_VERSION,
        )

        logger.info(
            "Anomaly detection complete: %d columns analyzed, %d outliers found total",
            columns_analyzed, total_outliers_found
        )
        return report

    def _analyze_column(self, col_name: str, series: pd.Series) -> ColumnAnomalyResult | None:
        """Analyze a single numerical series for outliers using configured methods."""
        
        # Drop NaNs for statistical calculations
        clean_series = series.dropna()
        n = len(clean_series)
        
        # We need at least some data to compute stats
        if n == 0:
            return None

        # Cast to float to avoid integer division issues during stats calculation
        vals = clean_series.astype(float)
        
        # Outlier masks
        iqr_mask = pd.Series(False, index=vals.index)
        zscore_mask = pd.Series(False, index=vals.index)
        
        iqr_lower = None
        iqr_upper = None
        used_zscore_thresh = None
        is_robust = None
        methods_used = []

        # ── 1. IQR Method ─────────────────────────────────────────────────────
        if self.config.use_iqr and n >= 4:
            q1 = vals.quantile(0.25)
            q3 = vals.quantile(0.75)
            iqr = q3 - q1
            
            # If IQR is exactly 0 (e.g. constant column), IQR method flags everything 
            # outside the single value. This is statistically correct but we must be careful.
            iqr_lower = float(q1 - (self.config.iqr_multiplier * iqr))
            iqr_upper = float(q3 + (self.config.iqr_multiplier * iqr))
            
            iqr_mask = (vals < iqr_lower) | (vals > iqr_upper)
            methods_used.append("IQR")

        # ── 2. Z-Score Method ─────────────────────────────────────────────────
        if self.config.use_zscore and n >= 2:
            used_zscore_thresh = float(self.config.zscore_threshold)
            is_robust = self.config.use_robust_zscore
            
            if is_robust:
                # Robust Z-score: 0.6745 * (x - median) / MAD
                median_val = vals.median()
                mad = (vals - median_val).abs().median()
                if mad > 0:
                    z_scores = 0.6745 * (vals - median_val) / mad
                    zscore_mask = z_scores.abs() > used_zscore_thresh
                    methods_used.append("Robust Z-score")
            else:
                # Standard Z-score: (x - mean) / std
                mean_val = vals.mean()
                std_val = vals.std(ddof=1)
                if std_val > 0:
                    z_scores = (vals - mean_val) / std_val
                    zscore_mask = z_scores.abs() > used_zscore_thresh
                    methods_used.append("Z-score")

        # Combine masks (Logical OR: if flagged by either method, it's an outlier)
        combined_mask = iqr_mask | zscore_mask
        outlier_count = int(combined_mask.sum())
        outlier_pct = (outlier_count / n * 100.0) if n > 0 else 0.0

        if not methods_used:
            return None # e.g. n < 2 or all methods disabled

        return ColumnAnomalyResult(
            column_name=col_name,
            method=" + ".join(methods_used),
            outlier_count=outlier_count,
            outlier_pct=outlier_pct,
            iqr_lower_bound=iqr_lower,
            iqr_upper_bound=iqr_upper,
            zscore_threshold_used=used_zscore_thresh,
            is_robust_zscore=is_robust,
        )
