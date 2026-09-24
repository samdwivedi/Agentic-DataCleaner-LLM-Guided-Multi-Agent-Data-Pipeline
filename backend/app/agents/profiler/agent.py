"""
Profiler Engine
───────────────
Deterministic, LLM-free DataFrame profiling engine.

Key guarantees
--------------
* The input DataFrame is NEVER modified.  A deep copy is used internally.
* No LLM calls are made — all computations are pure NumPy / Pandas.
* Returns a fully validated, frozen ``ProfilerReport``.

Usage
-----
    from app.agents.profiler import ProfilerAgent, ProfilerReport

    agent  = ProfilerAgent(top_n=10, least_n=5)
    report = agent.profile(df)
    print(report.summary_text())
"""

from __future__ import annotations

import logging
import math
from collections import Counter
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from app.models.profiler import (
    CategoricalStats,
    CategoryFrequency,
    ColumnProfile,
    DatasetMeta,
    DuplicateInfo,
    NumericalStats,
    ProblematicColumn,
    ProfilerReport,
)

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

_PROFILER_VERSION = "3.0.0"

# Thresholds for flagging
_HIGH_MISSING_THRESHOLD      = 50.0   # % missing → flag
_LOW_VARIANCE_THRESHOLD      = 1e-10  # std → near-constant flag
_HIGH_CARDINALITY_THRESHOLD  = 0.95   # unique/non-null ratio → flag
_CONSTANT_THRESHOLD          = 1      # unique count → constant flag
_SKEWNESS_THRESHOLD          = 2.0    # |skew| > this → flag
_ZERO_HEAVY_THRESHOLD        = 80.0   # % zeros → flag
_ID_CARDINALITY_THRESHOLD    = 0.98   # unique/non-null ≥ this → id candidate


# ── Main Engine ───────────────────────────────────────────────────────────────

class ProfilerAgent:
    """
    Deterministic DataFrame profiler.

    Parameters
    ----------
    top_n : int
        Number of most-frequent values shown in CategoricalStats.
    least_n : int
        Number of least-frequent values shown in CategoricalStats.
    """

    def __init__(self, top_n: int = 10, least_n: int = 5) -> None:
        if top_n < 1:
            raise ValueError("top_n must be ≥ 1")
        if least_n < 1:
            raise ValueError("least_n must be ≥ 1")
        self._top_n   = top_n
        self._least_n = least_n

    # ── Public API ────────────────────────────────────────────────────────────

    def profile(self, df: pd.DataFrame) -> ProfilerReport:
        """
        Profile *df* and return an immutable ``ProfilerReport``.

        The original DataFrame is never modified; a protective copy is
        taken at the very start of this method.

        Parameters
        ----------
        df : pd.DataFrame
            The DataFrame to profile.  May be empty.

        Returns
        -------
        ProfilerReport
            Fully validated, frozen profiling report.

        Raises
        ------
        TypeError
            If *df* is not a ``pd.DataFrame``.
        """
        if not isinstance(df, pd.DataFrame):
            raise TypeError(f"Expected pd.DataFrame, got {type(df).__name__}")

        logger.info(
            "ProfilerAgent.profile() → shape=%s", df.shape
        )

        # ── Protect the caller's DataFrame ───────────────────────────────────
        work: pd.DataFrame = df.copy(deep=True)

        # ── Dataset-level artefacts ───────────────────────────────────────────
        meta       = self._build_meta(work)
        duplicates = self._build_duplicate_info(work)

        # ── Per-column profiles ───────────────────────────────────────────────
        col_profiles: list[ColumnProfile] = [
            self._profile_column(work[col], meta.row_count)
            for col in work.columns
        ]

        # ── Problematic column detection ──────────────────────────────────────
        problematic = self._detect_problematic(col_profiles)

        # ── Assemble report ───────────────────────────────────────────────────
        report = ProfilerReport(
            meta=meta,
            columns=col_profiles,
            duplicates=duplicates,
            problematic=problematic,
            profiler_version=_PROFILER_VERSION,
            profiled_at=datetime.now(timezone.utc).isoformat(),
        )

        logger.info(
            "Profiling complete: %d columns, %d problematic",
            len(col_profiles), len(problematic),
        )
        return report

    # ── Dataset metadata ──────────────────────────────────────────────────────

    def _build_meta(self, df: pd.DataFrame) -> DatasetMeta:
        row_count    = len(df)
        column_count = len(df.columns)
        total_cells  = row_count * column_count
        total_missing = int(df.isna().sum().sum())
        total_missing_pct = (
            (total_missing / total_cells * 100) if total_cells > 0 else 0.0
        )
        memory_bytes = int(df.memory_usage(deep=True).sum())

        # Count by broad dtype category
        numeric_cols    = df.select_dtypes(include=[np.number]).columns
        datetime_cols   = df.select_dtypes(include=["datetime", "datetimetz"]).columns
        boolean_cols    = df.select_dtypes(include=["bool"]).columns
        categorical_cols = df.select_dtypes(
            include=["object", "category", "string"]
        ).columns
        other_count = column_count - (
            len(numeric_cols) + len(datetime_cols)
            + len(boolean_cols) + len(categorical_cols)
        )

        # dtypes_summary: dtype string → count
        dtype_counts: Counter = Counter(str(df[c].dtype) for c in df.columns)

        return DatasetMeta(
            row_count=row_count,
            column_count=column_count,
            total_cells=total_cells,
            total_missing=total_missing,
            total_missing_pct=round(total_missing_pct, 4),
            memory_usage_bytes=memory_bytes,
            numeric_column_count=len(numeric_cols),
            categorical_column_count=len(categorical_cols),
            datetime_column_count=len(datetime_cols),
            boolean_column_count=len(boolean_cols),
            other_column_count=max(other_count, 0),
            dtypes_summary=dict(dtype_counts),
        )

    # ── Duplicate info ────────────────────────────────────────────────────────

    def _build_duplicate_info(self, df: pd.DataFrame) -> DuplicateInfo:
        dup_mask  = df.duplicated(keep="first")
        dup_count = int(dup_mask.sum())
        dup_pct   = (dup_count / len(df) * 100) if len(df) > 0 else 0.0
        return DuplicateInfo(
            duplicate_row_count=dup_count,
            duplicate_row_pct=round(dup_pct, 4),
            has_duplicates=dup_count > 0,
        )

    # ── Per-column profiling ──────────────────────────────────────────────────

    def _profile_column(
        self, series: pd.Series, row_count: int
    ) -> ColumnProfile:
        """Dispatch to numeric or categorical profiler based on dtype."""

        name         = str(series.name)
        dtype_str    = str(series.dtype)
        dtype_kind   = series.dtype.kind if hasattr(series.dtype, "kind") else "O"

        non_null     = series.dropna()
        non_null_cnt = int(non_null.count())
        missing_cnt  = int(series.isna().sum())
        missing_pct  = (missing_cnt / row_count * 100) if row_count > 0 else 0.0
        unique_cnt   = int(non_null.nunique())
        unique_pct   = (
            (unique_cnt / non_null_cnt * 100) if non_null_cnt > 0 else 0.0
        )

        # Determine inferred type
        inferred = self._infer_type(series, unique_cnt, non_null_cnt, dtype_kind)

        # Numeric stats
        numerical_stats:   NumericalStats | None   = None
        categorical_stats: CategoricalStats | None = None
        value_min: str | None = None
        value_max: str | None = None

        # Treat booleans as categorical (not numeric)
        is_bool = series.dtype == bool or dtype_str in ("bool", "boolean")

        if pd.api.types.is_numeric_dtype(series) and not is_bool:
            numerical_stats, value_min, value_max = self._build_numerical_stats(
                non_null, row_count
            )
        else:
            categorical_stats = self._build_categorical_stats(non_null, non_null_cnt)
            if len(non_null) > 0:
                try:
                    sorted_vals = sorted(non_null.dropna().unique().tolist(), key=str)
                    value_min   = str(sorted_vals[0])
                    value_max   = str(sorted_vals[-1])
                except Exception:
                    pass

        return ColumnProfile(
            name=name,
            dtype=dtype_str,
            dtype_kind=str(dtype_kind),
            row_count=row_count,
            non_null_count=non_null_cnt,
            missing_count=missing_cnt,
            missing_pct=round(missing_pct, 4),
            unique_count=unique_cnt,
            unique_pct=round(unique_pct, 4),
            numerical_stats=numerical_stats,
            categorical_stats=categorical_stats,
            value_min=value_min,
            value_max=value_max,
            inferred_type=inferred,
        )

    # ── Numerical statistics ──────────────────────────────────────────────────

    def _build_numerical_stats(
        self,
        non_null: pd.Series,
        row_count: int,
    ) -> tuple[NumericalStats, str | None, str | None]:
        """
        Compute comprehensive numerical statistics.
        Returns (NumericalStats, value_min_str, value_max_str).
        """
        n = len(non_null)

        if n == 0:
            # All-null column → return zero stats
            stats = NumericalStats(
                mean=0.0, median=0.0, std=0.0, min=0.0, max=0.0,
                q1=0.0, q3=0.0, iqr=0.0,
                skewness=0.0, kurtosis=0.0,
                zero_count=0, zero_pct=0.0,
                negative_count=0, negative_pct=0.0,
                positive_count=0, positive_pct=0.0,
                sum=0.0, variance=0.0,
            )
            return stats, None, None

        # Cast to float for uniform arithmetic
        vals = non_null.astype(float)

        mean_val   = float(vals.mean())
        median_val = float(vals.median())
        std_val    = float(vals.std(ddof=1)) if n > 1 else 0.0
        var_val    = float(vals.var(ddof=1)) if n > 1 else 0.0
        min_val    = float(vals.min())
        max_val    = float(vals.max())
        sum_val    = float(vals.sum())

        q1  = float(vals.quantile(0.25))
        q3  = float(vals.quantile(0.75))
        iqr = round(q3 - q1, 10)

        # Skewness / kurtosis (pandas uses Fisher definitions)
        skewness = float(vals.skew())   if n >= 3 else 0.0
        kurtosis = float(vals.kurtosis()) if n >= 4 else 0.0

        # Handle NaN from uniform distributions
        skewness = 0.0 if math.isnan(skewness) else skewness
        kurtosis = 0.0 if math.isnan(kurtosis) else kurtosis

        # Zero / negative / positive counts
        zero_count     = int((vals == 0).sum())
        negative_count = int((vals < 0).sum())
        positive_count = int((vals > 0).sum())

        zero_pct     = round(zero_count     / row_count * 100, 4)
        negative_pct = round(negative_count / row_count * 100, 4)
        positive_pct = round(positive_count / row_count * 100, 4)

        stats = NumericalStats(
            mean=round(mean_val, 10),
            median=round(median_val, 10),
            std=round(std_val, 10),
            min=min_val,
            max=max_val,
            q1=round(q1, 10),
            q3=round(q3, 10),
            iqr=round(iqr, 10),
            skewness=round(skewness, 10),
            kurtosis=round(kurtosis, 10),
            zero_count=zero_count,
            zero_pct=zero_pct,
            negative_count=negative_count,
            negative_pct=negative_pct,
            positive_count=positive_count,
            positive_pct=positive_pct,
            sum=round(sum_val, 10),
            variance=round(var_val, 10),
        )

        value_min = str(min_val)
        value_max = str(max_val)
        return stats, value_min, value_max

    # ── Categorical statistics ────────────────────────────────────────────────

    def _build_categorical_stats(
        self,
        non_null: pd.Series,
        non_null_count: int,
    ) -> CategoricalStats:
        """
        Compute frequency-based categorical statistics.
        Works for object, category, boolean, and datetime columns.
        """
        if non_null_count == 0:
            return CategoricalStats(
                top_values=[],
                least_values=[],
                mode=None,
                mode_count=0,
                mode_frequency=0.0,
                avg_str_length=None,
                max_str_length=None,
                min_str_length=None,
            )

        # Value counts
        vc = non_null.value_counts(dropna=True)

        top_values: list[CategoryFrequency] = [
            CategoryFrequency(
                value=val,
                count=int(cnt),
                frequency=round(cnt / non_null_count, 6),
            )
            for val, cnt in vc.head(self._top_n).items()
        ]

        least_values: list[CategoryFrequency] = [
            CategoryFrequency(
                value=val,
                count=int(cnt),
                frequency=round(cnt / non_null_count, 6),
            )
            for val, cnt in vc.tail(self._least_n).items()
        ]

        mode_val   = vc.index[0] if len(vc) > 0 else None
        mode_count = int(vc.iloc[0])  if len(vc) > 0 else 0
        mode_freq  = round(mode_count / non_null_count, 6) if non_null_count > 0 else 0.0

        # String-length stats (only for actual string columns)
        avg_len = max_len = min_len = None
        if non_null.dtype == object or str(non_null.dtype) in ("string", "StringDtype", "string[python]", "string[pyarrow]"):
            try:
                lengths = [len(str(x)) for x in non_null]
                if lengths:
                    avg_len = round(sum(lengths) / len(lengths), 4)
                    max_len = max(lengths)
                    min_len = min(lengths)
            except Exception as e:
                logger.warning("Failed to compute string length stats: %s", e)

        return CategoricalStats(
            top_values=top_values,
            least_values=least_values,
            mode=mode_val,
            mode_count=mode_count,
            mode_frequency=mode_freq,
            avg_str_length=avg_len,
            max_str_length=max_len,
            min_str_length=min_len,
        )

    # ── Type inference ────────────────────────────────────────────────────────

    def _infer_type(
        self,
        series: pd.Series,
        unique_count: int,
        non_null_count: int,
        dtype_kind: str,
    ) -> str:
        """
        Infer a semantic high-level type for a column.

        Returns one of:
            'numeric_int', 'numeric_float', 'boolean', 'datetime',
            'categorical', 'text', 'id_candidate', 'constant', 'unknown'
        """
        dtype_str = str(series.dtype)

        # Constant
        if unique_count <= _CONSTANT_THRESHOLD and non_null_count > 0:
            return "constant"

        # Boolean
        if series.dtype == bool or dtype_str in ("bool", "boolean"):
            return "boolean"

        # Datetime
        if pd.api.types.is_datetime64_any_dtype(series):
            return "datetime"

        # Numeric
        if pd.api.types.is_numeric_dtype(series):
            # ID candidate: near-100% unique integers
            if (
                pd.api.types.is_integer_dtype(series)
                and non_null_count > 0
                and (unique_count / non_null_count) >= _ID_CARDINALITY_THRESHOLD
            ):
                return "id_candidate"
            if dtype_kind in ("i", "u"):
                return "numeric_int"
            return "numeric_float"

        # Object / string
        if non_null_count > 0:
            cardinality_ratio = unique_count / non_null_count

            # ID candidate for string columns too
            if cardinality_ratio >= _ID_CARDINALITY_THRESHOLD:
                return "id_candidate"

            # High-cardinality text
            if cardinality_ratio >= _HIGH_CARDINALITY_THRESHOLD:
                return "text"

            return "categorical"

        return "unknown"

    # ── Problematic column detection ──────────────────────────────────────────

    def _detect_problematic(
        self, profiles: list[ColumnProfile]
    ) -> list[ProblematicColumn]:
        """
        Scan all column profiles and accumulate data-quality flags.

        Checks performed
        ----------------
        1. High missing rate   (≥ 50 %)
        2. Constant column     (all non-null values identical)
        3. Near-zero variance  (std < 1e-10 for numerics)
        4. High cardinality    (unique/non-null ≥ 95 %, for categoricals)
        5. Heavily skewed      (|skewness| ≥ 2.0)
        6. Zero-heavy          (zeros ≥ 80 % for numerics)
        7. All-null column     (100 % missing)
        8. Potential ID column flagged for review
        """
        results: list[ProblematicColumn] = []

        for col in profiles:
            reasons: list[str] = []

            # All-null
            if col.missing_count == col.row_count:
                reasons.append("All values are null (100% missing).")

            # High missing
            elif col.missing_pct >= _HIGH_MISSING_THRESHOLD:
                reasons.append(
                    f"High missing rate: {col.missing_pct:.1f}% of values are null."
                )

            # Constant column
            if col.inferred_type == "constant":
                reasons.append(
                    "Constant column: only one unique value across all rows."
                )

            # Numeric-specific flags
            if col.numerical_stats is not None:
                ns = col.numerical_stats

                # Near-zero variance
                if ns.std < _LOW_VARIANCE_THRESHOLD and col.non_null_count > 1:
                    reasons.append(
                        f"Near-zero variance (std={ns.std:.2e}); column may be constant."
                    )

                # Heavily skewed
                if abs(ns.skewness) >= _SKEWNESS_THRESHOLD:
                    direction = "right" if ns.skewness > 0 else "left"
                    reasons.append(
                        f"Heavily {direction}-skewed distribution (skewness={ns.skewness:.2f})."
                    )

                # Zero-heavy
                if ns.zero_pct >= _ZERO_HEAVY_THRESHOLD:
                    reasons.append(
                        f"Zero-heavy: {ns.zero_pct:.1f}% of total rows are zero."
                    )

            # Categorical-specific flags
            if col.categorical_stats is not None:
                cs = col.categorical_stats

                # High cardinality (non-ID)
                if (
                    col.inferred_type not in ("id_candidate", "text")
                    and col.non_null_count > 0
                    and (col.unique_count / col.non_null_count)
                    >= _HIGH_CARDINALITY_THRESHOLD
                ):
                    reasons.append(
                        f"High cardinality: {col.unique_count} unique values "
                        f"({col.unique_pct:.1f}% of non-null rows)."
                    )

            # ID candidate — informational flag
            if col.inferred_type == "id_candidate":
                reasons.append(
                    "Appears to be an ID column (near-unique values). "
                    "Verify it is not accidentally included in aggregations."
                )

            if reasons:
                results.append(ProblematicColumn(column=col.name, reasons=reasons))

        return results
