"""
Quality Assessor Engine
───────────────────────
Deterministic post-cleaning validation system.

Computes a configurable composite Data Quality Score for a DataFrame,
compares BEFORE vs AFTER metrics, and produces a machine-readable
``QualityReport`` with a human-readable summary.

Flow
----
    QualityAssessor.assess(df_before, df_after)
            ↓
        QualityReport
            ├─ quality_score_before
            ├─ quality_score_after
            ├─ improvement
            ├─ remaining_issues
            ├─ critical_failures
            └─ is_successful

Scoring
-------
The composite score is the weighted sum of 5 per-dimension sub-scores,
each ranging from 0 to 100:

1. **Missing**      — penalises based on overall missing percentage.
2. **Duplicates**   — penalises based on duplicate-row percentage.
3. **Schema**       — penalises for dtype mismatches & invalid categories.
4. **Anomalies**    — penalises for IQR-based outlier prevalence.
5. **Completeness** — rewards for row and column retention.

A higher score is always better.  The engine **never** claims a dataset is
clean if the post-cleaning score is worse than the pre-cleaning score or
falls below the configured minimum.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from app.models.quality import (
    DataQualityMetrics,
    IssueSeverity,
    QualityConfig,
    QualityIssue,
    QualityReport,
)

logger = logging.getLogger(__name__)

_ASSESSOR_VERSION = "1.0.0"


class QualityAssessor:
    """
    Deterministic, LLM-free quality assessment engine.

    Usage
    -----
    >>> from app.agents.validator import QualityAssessor
    >>> assessor = QualityAssessor()
    >>> report = assessor.assess(df_before, df_after)
    >>> print(report.summary_text())
    """

    def __init__(self, config: QualityConfig | None = None) -> None:
        self.config = config or QualityConfig()

    # ══════════════════════════════════════════════════════════════════════
    # PUBLIC API
    # ══════════════════════════════════════════════════════════════════════

    def assess(
        self,
        df_before: pd.DataFrame,
        df_after: pd.DataFrame,
        expected_dtypes: dict[str, str] | None = None,
        allowed_categories: dict[str, list] | None = None,
    ) -> QualityReport:
        """
        Compare two DataFrames (before and after cleaning) and produce a
        ``QualityReport``.

        Parameters
        ----------
        df_before : pd.DataFrame
            The original, uncleaned DataFrame.
        df_after : pd.DataFrame
            The DataFrame after the Executor has applied cleaning actions.
        expected_dtypes : dict, optional
            Mapping of column name → expected dtype string for schema checks.
        allowed_categories : dict, optional
            Mapping of column name → list of allowed categorical values.

        Returns
        -------
        QualityReport
        """
        if not isinstance(df_before, pd.DataFrame):
            raise TypeError(f"df_before: expected pd.DataFrame, got {type(df_before).__name__}")
        if not isinstance(df_after, pd.DataFrame):
            raise TypeError(f"df_after: expected pd.DataFrame, got {type(df_after).__name__}")

        logger.info(
            "QualityAssessor.assess() — before shape=%s, after shape=%s",
            df_before.shape, df_after.shape,
        )

        # ── Compute metrics ───────────────────────────────────────────────
        metrics_before = self._compute_metrics(
            df_before, expected_dtypes, allowed_categories,
        )
        metrics_after = self._compute_metrics(
            df_after, expected_dtypes, allowed_categories,
        )

        # ── Score ─────────────────────────────────────────────────────────
        score_before = self._compute_score(metrics_before)
        score_after  = self._compute_score(metrics_after)
        improvement  = round(score_after - score_before, 2)

        metrics_before = DataQualityMetrics(
            **{**metrics_before.model_dump(), "quality_score": score_before}
        )
        metrics_after = DataQualityMetrics(
            **{**metrics_after.model_dump(), "quality_score": score_after}
        )

        # ── Remaining issues ──────────────────────────────────────────────
        remaining = self._detect_remaining_issues(df_after, metrics_after, allowed_categories)

        # ── Critical failures ─────────────────────────────────────────────
        criticals = self._detect_critical_failures(
            metrics_before, metrics_after, score_before, score_after,
        )

        # ── Verdict ───────────────────────────────────────────────────────
        is_successful = (
            len(criticals) == 0
            and score_after >= self.config.min_acceptable_score
            and score_after >= score_before
        )

        report = QualityReport(
            quality_score_before=score_before,
            quality_score_after=score_after,
            improvement=improvement,
            metrics_before=metrics_before,
            metrics_after=metrics_after,
            remaining_issues=remaining,
            critical_failures=criticals,
            is_successful=is_successful,
            assessor_version=_ASSESSOR_VERSION,
        )

        logger.info(
            "Quality assessment complete: %.1f → %.1f (%s%.1f) — %s",
            score_before, score_after,
            "+" if improvement >= 0 else "", improvement,
            "SUCCESS" if is_successful else "UNSUCCESSFUL",
        )

        return report

    def score_dataframe(
        self,
        df: pd.DataFrame,
        expected_dtypes: dict[str, str] | None = None,
        allowed_categories: dict[str, list] | None = None,
    ) -> DataQualityMetrics:
        """Score a single DataFrame (convenience method)."""
        metrics = self._compute_metrics(df, expected_dtypes, allowed_categories)
        score = self._compute_score(metrics)
        return DataQualityMetrics(**{**metrics.model_dump(), "quality_score": score})

    # ══════════════════════════════════════════════════════════════════════
    # METRICS COMPUTATION
    # ══════════════════════════════════════════════════════════════════════

    def _compute_metrics(
        self,
        df: pd.DataFrame,
        expected_dtypes: dict[str, str] | None = None,
        allowed_categories: dict[str, list] | None = None,
    ) -> DataQualityMetrics:
        """Compute raw quality metrics for a single DataFrame."""

        row_count = len(df)
        col_count = len(df.columns)
        total_cells = row_count * col_count

        # ── Missing values ────────────────────────────────────────────────
        total_missing = int(df.isna().sum().sum())
        missing_pct = (total_missing / total_cells * 100) if total_cells > 0 else 0.0
        columns_with_nulls = int((df.isna().sum() > 0).sum())

        # ── Duplicates ────────────────────────────────────────────────────
        dup_count = int(df.duplicated().sum())
        dup_pct = (dup_count / row_count * 100) if row_count > 0 else 0.0

        # ── Dtype violations ──────────────────────────────────────────────
        dtype_violations = 0
        if expected_dtypes:
            for col_name, expected in expected_dtypes.items():
                if col_name in df.columns:
                    actual = str(df[col_name].dtype)
                    if actual != expected:
                        dtype_violations += 1

        # ── Invalid categories ────────────────────────────────────────────
        invalid_cat_count = 0
        if allowed_categories:
            for col_name, allowed in allowed_categories.items():
                if col_name in df.columns:
                    non_null = df[col_name].dropna()
                    if len(non_null) > 0:
                        invalid_cat_count += int((~non_null.isin(allowed)).sum())

        # ── Numerical outliers (IQR) ──────────────────────────────────────
        outlier_count = 0
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        for col_name in numeric_cols:
            series = df[col_name].dropna()
            if len(series) < 4:
                continue
            q1 = series.quantile(0.25)
            q3 = series.quantile(0.75)
            iqr = q3 - q1
            if iqr == 0:
                continue
            lower = q1 - 1.5 * iqr
            upper = q3 + 1.5 * iqr
            outlier_count += int(((series < lower) | (series > upper)).sum())

        return DataQualityMetrics(
            row_count=row_count,
            column_count=col_count,
            total_missing=total_missing,
            missing_pct=round(missing_pct, 4),
            columns_with_nulls=columns_with_nulls,
            duplicate_rows=dup_count,
            duplicate_pct=round(dup_pct, 4),
            dtype_violations=dtype_violations,
            invalid_category_count=invalid_cat_count,
            outlier_count=outlier_count,
        )

    # ══════════════════════════════════════════════════════════════════════
    # COMPOSITE SCORING
    # ══════════════════════════════════════════════════════════════════════

    def _compute_score(self, m: DataQualityMetrics) -> float:
        """
        Compute a composite quality score (0–100) from raw metrics.

        Each dimension produces a sub-score in [0, 100] where 100 = perfect.
        The composite is a weighted average using ``QualityConfig`` weights.
        """
        cfg = self.config

        # ── Normalise weights ─────────────────────────────────────────────
        raw_weights = [
            cfg.weight_missing,
            cfg.weight_duplicates,
            cfg.weight_schema,
            cfg.weight_anomalies,
            cfg.weight_completeness,
        ]
        total_weight = sum(raw_weights)
        if total_weight == 0:
            return 0.0
        norm = [w / total_weight for w in raw_weights]

        # ── 1. Missing sub-score ──────────────────────────────────────────
        # 0% missing → 100;  100% missing → 0
        s_missing = max(0.0, 100.0 - m.missing_pct)

        # ── 2. Duplicate sub-score ────────────────────────────────────────
        # 0% dups → 100;  100% dups → 0
        s_duplicates = max(0.0, 100.0 - m.duplicate_pct)

        # ── 3. Schema sub-score ───────────────────────────────────────────
        # Penalise per violation; each violation costs 10 points, capped at 0
        schema_penalty = (m.dtype_violations + m.invalid_category_count) * 10
        s_schema = max(0.0, 100.0 - schema_penalty)

        # ── 4. Anomaly sub-score ──────────────────────────────────────────
        # Penalise per outlier relative to total values
        total_cells = m.row_count * m.column_count
        if total_cells > 0:
            outlier_pct = (m.outlier_count / total_cells) * 100
            s_anomalies = max(0.0, 100.0 - outlier_pct * 5)  # 20% outlier cells → 0
        else:
            s_anomalies = 100.0

        # ── 5. Completeness sub-score ─────────────────────────────────────
        # Based on non-null cell ratio
        if total_cells > 0:
            non_null_ratio = (total_cells - m.total_missing) / total_cells
            s_completeness = non_null_ratio * 100
        else:
            s_completeness = 100.0

        # ── Weighted composite ────────────────────────────────────────────
        sub_scores = [s_missing, s_duplicates, s_schema, s_anomalies, s_completeness]
        composite = sum(w * s for w, s in zip(norm, sub_scores))

        return round(min(100.0, max(0.0, composite)), 2)

    # ══════════════════════════════════════════════════════════════════════
    # REMAINING ISSUES DETECTION
    # ══════════════════════════════════════════════════════════════════════

    def _detect_remaining_issues(
        self,
        df_after: pd.DataFrame,
        metrics_after: DataQualityMetrics,
        allowed_categories: dict[str, list] | None = None,
    ) -> list[QualityIssue]:
        """Scan the post-cleaning DataFrame for remaining quality issues."""

        issues: list[QualityIssue] = []

        # ── Missing values ────────────────────────────────────────────────
        for col in df_after.columns:
            null_count = int(df_after[col].isna().sum())
            if null_count > 0:
                pct = null_count / len(df_after) * 100 if len(df_after) > 0 else 0
                severity = IssueSeverity.CRITICAL if pct > 50 else (
                    IssueSeverity.WARNING if pct > 10 else IssueSeverity.INFO
                )
                issues.append(QualityIssue(
                    severity=severity,
                    dimension="missing",
                    column=col,
                    message=f"{null_count:,} null values ({pct:.1f}%) remaining.",
                ))

        # ── Duplicates ────────────────────────────────────────────────────
        if metrics_after.duplicate_rows > 0:
            severity = (
                IssueSeverity.WARNING if metrics_after.duplicate_pct > 5
                else IssueSeverity.INFO
            )
            issues.append(QualityIssue(
                severity=severity,
                dimension="duplicates",
                message=f"{metrics_after.duplicate_rows:,} duplicate rows "
                        f"({metrics_after.duplicate_pct:.1f}%) remaining.",
            ))

        # ── Invalid categories ────────────────────────────────────────────
        if allowed_categories:
            for col, allowed in allowed_categories.items():
                if col in df_after.columns:
                    non_null = df_after[col].dropna()
                    invalid = non_null[~non_null.isin(allowed)]
                    if len(invalid) > 0:
                        issues.append(QualityIssue(
                            severity=IssueSeverity.WARNING,
                            dimension="categories",
                            column=col,
                            message=f"{len(invalid)} values outside allowed set.",
                        ))

        # ── Outliers ──────────────────────────────────────────────────────
        if metrics_after.outlier_count > 0:
            issues.append(QualityIssue(
                severity=IssueSeverity.INFO,
                dimension="anomalies",
                message=f"{metrics_after.outlier_count:,} outliers still present.",
            ))

        return issues

    # ══════════════════════════════════════════════════════════════════════
    # CRITICAL FAILURE DETECTION
    # ══════════════════════════════════════════════════════════════════════

    def _detect_critical_failures(
        self,
        m_before: DataQualityMetrics,
        m_after: DataQualityMetrics,
        score_before: float,
        score_after: float,
    ) -> list[QualityIssue]:
        """
        Detect conditions that **must** mark the run as unsuccessful.

        Critical failures:
        1. Quality score decreased.
        2. Missing percentage increased.
        3. Duplicate percentage increased.
        4. All rows were deleted.
        5. All columns were deleted.
        6. Post-cleaning score is below minimum acceptable.
        """
        criticals: list[QualityIssue] = []

        # 1. Score decreased
        if score_after < score_before:
            criticals.append(QualityIssue(
                severity=IssueSeverity.CRITICAL,
                dimension="score",
                message=f"Quality score decreased: {score_before:.1f} → {score_after:.1f}.",
            ))

        # 2. Missing increased
        if m_after.missing_pct > m_before.missing_pct:
            criticals.append(QualityIssue(
                severity=IssueSeverity.CRITICAL,
                dimension="missing",
                message=f"Missing percentage increased: "
                        f"{m_before.missing_pct:.2f}% → {m_after.missing_pct:.2f}%.",
            ))

        # 3. Duplicates increased
        if m_after.duplicate_pct > m_before.duplicate_pct:
            criticals.append(QualityIssue(
                severity=IssueSeverity.CRITICAL,
                dimension="duplicates",
                message=f"Duplicate percentage increased: "
                        f"{m_before.duplicate_pct:.2f}% → {m_after.duplicate_pct:.2f}%.",
            ))

        # 4. All rows deleted
        if m_after.row_count == 0 and m_before.row_count > 0:
            criticals.append(QualityIssue(
                severity=IssueSeverity.CRITICAL,
                dimension="completeness",
                message="All rows were deleted during cleaning.",
            ))

        # 5. All columns deleted
        if m_after.column_count == 0 and m_before.column_count > 0:
            criticals.append(QualityIssue(
                severity=IssueSeverity.CRITICAL,
                dimension="completeness",
                message="All columns were deleted during cleaning.",
            ))

        # 6. Below minimum
        if score_after < self.config.min_acceptable_score:
            criticals.append(QualityIssue(
                severity=IssueSeverity.CRITICAL,
                dimension="score",
                message=f"Post-cleaning score {score_after:.1f} is below minimum "
                        f"acceptable threshold ({self.config.min_acceptable_score:.1f}).",
            ))

        return criticals
