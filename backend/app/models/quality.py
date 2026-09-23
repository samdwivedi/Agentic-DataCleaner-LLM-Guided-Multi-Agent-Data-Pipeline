"""
Quality Assessment Models
─────────────────────────
Strongly-typed Pydantic v2 models for the post-cleaning validation system.

This module defines:
* ``QualityConfig``           — configurable weights and thresholds for scoring.
* ``DataQualityMetrics``      — a flat bag of measurable quality dimensions.
* ``QualityIssue``            — a single remaining or new issue.
* ``QualityReport``           — the complete before/after comparison report.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

# ── Issue Severity ────────────────────────────────────────────────────────────

class IssueSeverity(str, Enum):
    CRITICAL = "critical"
    WARNING  = "warning"
    INFO     = "info"


# ── Quality Configuration ─────────────────────────────────────────────────────

class QualityConfig(BaseModel):
    """
    Configurable weights for the composite Data Quality Score and thresholds
    for deciding whether a cleaning run is successful.

    All weights are relative — the engine normalises them to sum to 1.0.
    """

    # ── Dimension weights (relative) ──────────────────────────────────────
    weight_missing:      float = Field(25.0, description="Weight for missing-value dimension.")
    weight_duplicates:   float = Field(15.0, description="Weight for duplicate-row dimension.")
    weight_schema:       float = Field(20.0, description="Weight for schema/datatype conformance.")
    weight_anomalies:    float = Field(15.0, description="Weight for numerical outlier dimension.")
    weight_completeness: float = Field(25.0, description="Weight for row/column completeness.")

    # ── Thresholds ────────────────────────────────────────────────────────
    min_acceptable_score: float = Field(
        60.0, ge=0.0, le=100.0,
        description="Minimum quality score (0–100) to mark the run as successful.",
    )
    max_allowed_missing_pct: float = Field(
        5.0, ge=0.0, le=100.0,
        description="Maximum acceptable overall missing percentage after cleaning.",
    )
    max_allowed_duplicate_pct: float = Field(
        1.0, ge=0.0, le=100.0,
        description="Maximum acceptable duplicate-row percentage after cleaning.",
    )


# ── Data Quality Metrics ──────────────────────────────────────────────────────

class DataQualityMetrics(BaseModel, frozen=True):
    """
    A flat snapshot of measurable quality dimensions for a DataFrame
    at a single point in time (before or after cleaning).
    """

    # Shape
    row_count:    int = Field(..., description="Total rows.")
    column_count: int = Field(..., description="Total columns.")

    # Missing values
    total_missing:     int   = Field(..., description="Total null cells.")
    missing_pct:       float = Field(..., description="Overall missing percentage (0–100).")
    columns_with_nulls: int  = Field(0, description="Number of columns containing ≥1 null.")

    # Duplicates
    duplicate_rows:    int   = Field(0, description="Number of fully duplicate rows.")
    duplicate_pct:     float = Field(0.0, description="Duplicate rows as percentage (0–100).")

    # Schema / dtypes
    dtype_violations:  int   = Field(0, description="Columns whose dtype differs from expected.")
    invalid_category_count: int = Field(
        0, description="Values outside allowed categorical sets.",
    )

    # Anomalies
    outlier_count:     int   = Field(0, description="Total outliers (IQR-based) across all numeric columns.")

    # Composite score
    quality_score:     float = Field(
        0.0, ge=0.0, le=100.0,
        description="Composite Data Quality Score (0–100).",
    )


# ── Quality Issue ─────────────────────────────────────────────────────────────

class QualityIssue(BaseModel, frozen=True):
    """A single remaining or newly introduced quality issue."""

    severity: IssueSeverity = Field(..., description="How critical this issue is.")
    dimension: str = Field(..., description="Quality dimension (e.g., 'missing', 'duplicates').")
    column: str | None = Field(None, description="Affected column, if applicable.")
    message: str = Field(..., description="Human-readable description.")


# ── Quality Report ────────────────────────────────────────────────────────────

class QualityReport(BaseModel, frozen=True):
    """
    Complete post-cleaning validation report comparing BEFORE vs AFTER.

    ``is_successful`` is ``False`` if:
      - The quality score decreased.
      - The after-score is below ``min_acceptable_score``.
      - Any critical failure was detected.
    """

    # Scores
    quality_score_before: float = Field(..., description="Composite score BEFORE cleaning.")
    quality_score_after:  float = Field(..., description="Composite score AFTER cleaning.")
    improvement:          float = Field(..., description="Score change (after − before). Positive = better.")

    # Snapshots
    metrics_before: DataQualityMetrics = Field(..., description="Full metrics snapshot BEFORE.")
    metrics_after:  DataQualityMetrics = Field(..., description="Full metrics snapshot AFTER.")

    # Issues
    remaining_issues:  list[QualityIssue] = Field(
        default_factory=list, description="Issues that still exist after cleaning.",
    )
    critical_failures: list[QualityIssue] = Field(
        default_factory=list, description="Issues severe enough to mark the run as unsuccessful.",
    )

    # Verdict
    is_successful: bool = Field(
        ..., description="True only if cleaning improved or maintained quality above thresholds.",
    )

    # Metadata
    assessor_version: str = Field("1.0.0", description="Semantic version of the quality assessor.")

    # ── Human-readable summary ────────────────────────────────────────────

    def summary_text(self) -> str:
        """Return a multi-line human-readable summary."""
        verdict = "✅ SUCCESSFUL" if self.is_successful else "❌ UNSUCCESSFUL"
        sign = "+" if self.improvement >= 0 else ""
        lines = [
            f"Post-Cleaning Quality Report — {verdict}",
            "",
            f"  Quality Score:  {self.quality_score_before:.1f}  →  {self.quality_score_after:.1f}  "
            f"({sign}{self.improvement:.1f})",
            "",
            "  BEFORE                          AFTER",
            f"  Rows:        {self.metrics_before.row_count:<10,}       Rows:        {self.metrics_after.row_count:,}",
            f"  Columns:     {self.metrics_before.column_count:<10}       Columns:     {self.metrics_after.column_count}",
            f"  Missing:     {self.metrics_before.missing_pct:<8.2f}%       Missing:     {self.metrics_after.missing_pct:.2f}%",
            f"  Duplicates:  {self.metrics_before.duplicate_pct:<8.2f}%       Duplicates:  {self.metrics_after.duplicate_pct:.2f}%",
            f"  Outliers:    {self.metrics_before.outlier_count:<10,}       Outliers:    {self.metrics_after.outlier_count:,}",
        ]

        if self.remaining_issues:
            lines.append(f"\n  Remaining Issues ({len(self.remaining_issues)}):")
            for issue in self.remaining_issues[:10]:
                col = f"[{issue.column}] " if issue.column else ""
                lines.append(f"    {issue.severity.value.upper():8s} {col}{issue.message}")
            if len(self.remaining_issues) > 10:
                lines.append(f"    ... and {len(self.remaining_issues) - 10} more.")

        if self.critical_failures:
            lines.append(f"\n  Critical Failures ({len(self.critical_failures)}):")
            for cf in self.critical_failures:
                col = f"[{cf.column}] " if cf.column else ""
                lines.append(f"    🚨 {col}{cf.message}")

        return "\n".join(lines)
