"""
Anomaly Detector Models
───────────────────────
Strongly-typed Pydantic v2 models for configuring anomaly detection rules
and representing the final anomaly report.

All report models are immutable (frozen=True).
"""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


# ── Configuration Models ──────────────────────────────────────────────────────

class AnomalyConfig(BaseModel):
    """Global configuration for anomaly detection thresholds."""
    
    use_iqr: bool = Field(
        True, description="Whether to use the Interquartile Range (IQR) method for outlier detection."
    )
    iqr_multiplier: float = Field(
        1.5, description="Multiplier for the IQR to determine boundaries (typically 1.5)."
    )
    
    use_zscore: bool = Field(
        True, description="Whether to use the Z-score method for outlier detection."
    )
    zscore_threshold: float = Field(
        3.0, description="The Z-score threshold beyond which a value is considered an outlier."
    )
    
    use_robust_zscore: bool = Field(
        False, description="Use Median and MAD instead of Mean and STD for Z-score calculation (more robust to extreme outliers)."
    )


# ── Report Models ─────────────────────────────────────────────────────────────

class ColumnAnomalyResult(BaseModel, frozen=True):
    """Anomaly detection results for a single numerical column."""
    
    column_name: str = Field(
        ..., description="The name of the column analyzed."
    )
    method: str = Field(
        ..., description="The method(s) used to flag outliers (e.g., 'IQR', 'Z-score', 'IQR + Z-score')."
    )
    outlier_count: int = Field(
        ..., description="Total number of unique rows flagged as outliers in this column."
    )
    outlier_pct: float = Field(
        ..., description="Percentage of non-null values flagged as outliers (0-100)."
    )
    
    # Boundary thresholds (optional, depending on methods used)
    iqr_lower_bound: Optional[float] = Field(
        None, description="The calculated lower boundary for IQR-based detection."
    )
    iqr_upper_bound: Optional[float] = Field(
        None, description="The calculated upper boundary for IQR-based detection."
    )
    zscore_threshold_used: Optional[float] = Field(
        None, description="The Z-score threshold applied to this column."
    )
    
    # For robust z-score vs standard z-score
    is_robust_zscore: Optional[bool] = Field(
        None, description="True if robust Z-score (MAD) was used, False if standard (STD)."
    )


class AnomalyReport(BaseModel, frozen=True):
    """
    Immutable anomaly detection report containing dataset-level summaries and 
    per-column anomaly results.
    """
    
    total_rows: int = Field(
        ..., description="Total number of rows in the DataFrame."
    )
    columns_analyzed: int = Field(
        ..., description="Total number of numerical columns analyzed."
    )
    total_outliers_found: int = Field(
        ..., description="Sum of outlier counts across all analyzed columns."
    )
    column_reports: List[ColumnAnomalyResult] = Field(
        default_factory=list, description="Per-column anomaly detection results."
    )
    analyzed_at: str = Field(
        ..., description="ISO-8601 UTC timestamp of when anomaly detection was performed."
    )
    detector_version: str = Field(
        "1.0.0", description="Semantic version of the anomaly detector engine."
    )

    def summary_text(self) -> str:
        """Return a concise human-readable summary string of the anomaly results."""
        lines = [
            f"Anomaly Detection Report — {self.analyzed_at}",
            f"  Rows analyzed: {self.total_rows:,}",
            f"  Columns analyzed: {self.columns_analyzed}",
            f"  Total outliers found (sum across columns): {self.total_outliers_found:,}",
        ]
        
        if self.column_reports:
            lines.append("\nPer-Column Anomalies:")
            for report in self.column_reports:
                if report.outlier_count > 0:
                    lines.append(
                        f"  - {report.column_name}: {report.outlier_count:,} outliers "
                        f"({report.outlier_pct:.2f}%) via {report.method}"
                    )
            if all(r.outlier_count == 0 for r in self.column_reports):
                lines.append("  No outliers detected in any analyzed columns.")
                
        return "\n".join(lines)
