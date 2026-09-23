"""
Profiler Data Models
────────────────────
Strongly-typed, immutable Pydantic v2 models that represent the full output
of a DataFrame profiling run.

Design rules
------------
* All models are ``frozen=True`` — the report is immutable once built.
* ``Optional`` is used only for genuinely absent statistics
  (e.g. NumericalStats on a categorical column).
* Every field carries a docstring-style ``description`` so the JSON schema
  is self-documenting.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ── Numerical statistics ──────────────────────────────────────────────────────

class NumericalStats(BaseModel, frozen=True):
    """Descriptive statistics for numeric columns."""

    mean:   float = Field(..., description="Arithmetic mean of non-null values.")
    median: float = Field(..., description="50th percentile (median).")
    std:    float = Field(..., description="Sample standard deviation (ddof=1).")
    min:    float = Field(..., description="Minimum value.")
    max:    float = Field(..., description="Maximum value.")
    q1:     float = Field(..., description="25th percentile (Q1).")
    q3:     float = Field(..., description="75th percentile (Q3).")
    iqr:    float = Field(..., description="Interquartile range (Q3 − Q1).")
    skewness:  float = Field(..., description="Fisher–Pearson skewness coefficient.")
    kurtosis:  float = Field(..., description="Excess kurtosis (Fisher definition).")
    zero_count: int  = Field(..., description="Count of zero values in the column.")
    zero_pct:   float = Field(..., description="Percentage of zero values (0–100).")
    negative_count: int   = Field(..., description="Count of strictly negative values.")
    negative_pct:   float = Field(..., description="Percentage of negative values (0–100).")
    positive_count: int   = Field(..., description="Count of strictly positive values.")
    positive_pct:   float = Field(..., description="Percentage of positive values (0–100).")
    sum:   float = Field(..., description="Sum of all non-null values.")
    variance: float = Field(..., description="Sample variance (std²).")


# ── Categorical statistics ────────────────────────────────────────────────────

class CategoryFrequency(BaseModel, frozen=True):
    """A single category value with its count and relative frequency."""

    value:     Any   = Field(..., description="The category label.")
    count:     int   = Field(..., description="Absolute occurrence count.")
    frequency: float = Field(..., description="Relative frequency as a fraction (0–1).")


class CategoricalStats(BaseModel, frozen=True):
    """Frequency-based statistics for object/categorical columns."""

    top_values:       List[CategoryFrequency] = Field(
        ..., description="Top-N most frequent values (default N=10)."
    )
    least_values:     List[CategoryFrequency] = Field(
        ..., description="Bottom-N least frequent values (default N=5)."
    )
    mode:             Optional[Any]  = Field(None, description="Most frequent single value.")
    mode_count:       int            = Field(0,    description="Occurrences of the mode.")
    mode_frequency:   float          = Field(0.0,  description="Mode frequency as a fraction (0–1).")
    avg_str_length:   Optional[float] = Field(
        None, description="Mean string length (only for str-typed columns)."
    )
    max_str_length:   Optional[int] = Field(
        None, description="Maximum string length encountered."
    )
    min_str_length:   Optional[int] = Field(
        None, description="Minimum string length encountered."
    )


# ── Duplicate information ─────────────────────────────────────────────────────

class DuplicateInfo(BaseModel, frozen=True):
    """Row-level duplicate summary for the full DataFrame."""

    duplicate_row_count: int   = Field(..., description="Number of fully duplicate rows.")
    duplicate_row_pct:   float = Field(..., description="Duplicate rows as % of total rows.")
    has_duplicates:      bool  = Field(..., description="True when any duplicate rows exist.")


# ── Potentially problematic column flags ────────────────────────────────────

class ProblematicColumn(BaseModel, frozen=True):
    """
    Represents a column flagged for potential data quality issues.
    Multiple reasons can be attached to a single column.
    """

    column:  str       = Field(..., description="Column name.")
    reasons: List[str] = Field(..., description="Human-readable list of detected issues.")


# ── Per-column profile ────────────────────────────────────────────────────────

class ColumnProfile(BaseModel, frozen=True):
    """Complete profile for a single DataFrame column."""

    # Identity
    name:       str = Field(..., description="Column name.")
    dtype:      str = Field(..., description="Pandas dtype as a string.")
    dtype_kind: str = Field(
        ..., description="NumPy dtype kind character: 'f'=float, 'i'=int, 'O'=object, …"
    )

    # Counts
    row_count:     int = Field(..., description="Total number of rows (incl. NaN).")
    non_null_count: int = Field(..., description="Number of non-null values.")
    missing_count: int = Field(..., description="Number of null/NaN values.")
    missing_pct:   float = Field(..., description="Null percentage (0–100).")
    unique_count:  int   = Field(..., description="Number of distinct non-null values.")
    unique_pct:    float = Field(..., description="Unique / non-null ratio × 100.")

    # Type-specific stats (mutually exclusive)
    numerical_stats:   Optional[NumericalStats]   = Field(
        None, description="Set for numeric columns; None otherwise."
    )
    categorical_stats: Optional[CategoricalStats] = Field(
        None, description="Set for object/category/bool columns; None otherwise."
    )

    # Min / max expressed as strings so they work for both types
    value_min: Optional[str] = Field(
        None, description="String representation of the minimum value."
    )
    value_max: Optional[str] = Field(
        None, description="String representation of the maximum value."
    )

    # Inferred type hint
    inferred_type: str = Field(
        ...,
        description=(
            "High-level semantic type inferred from data: "
            "'numeric_int', 'numeric_float', 'categorical', 'boolean', "
            "'datetime', 'text', 'id_candidate', 'constant', 'unknown'."
        ),
    )


# ── Dataset-level metadata ────────────────────────────────────────────────────

class DatasetMeta(BaseModel, frozen=True):
    """Dataset-wide summary metadata."""

    row_count:    int   = Field(..., description="Total number of rows.")
    column_count: int   = Field(..., description="Total number of columns.")
    total_cells:  int   = Field(..., description="row_count × column_count.")
    total_missing: int  = Field(..., description="Total null cells across all columns.")
    total_missing_pct: float = Field(
        ..., description="Dataset-wide null percentage (0–100)."
    )
    memory_usage_bytes: int = Field(
        ..., description="Deep memory usage of the DataFrame in bytes."
    )
    numeric_column_count:      int = Field(..., description="Number of numeric columns.")
    categorical_column_count:  int = Field(..., description="Number of categorical/object columns.")
    datetime_column_count:     int = Field(..., description="Number of datetime columns.")
    boolean_column_count:      int = Field(..., description="Number of boolean columns.")
    other_column_count:        int = Field(..., description="Columns not in above categories.")

    dtypes_summary: Dict[str, int] = Field(
        ..., description="Mapping of dtype-string → column count."
    )


# ── Top-level report ──────────────────────────────────────────────────────────

class ProfilerReport(BaseModel, frozen=True):
    """
    Complete, immutable profiling report for a pandas DataFrame.

    Produced exclusively by ``ProfilerAgent.profile(df)``.
    Never modified after construction.
    """

    meta:             DatasetMeta           = Field(..., description="Dataset-level metadata.")
    columns:          List[ColumnProfile]   = Field(..., description="Per-column profiles.")
    duplicates:       DuplicateInfo         = Field(..., description="Duplicate-row analysis.")
    problematic:      List[ProblematicColumn] = Field(
        ..., description="Columns flagged for data quality issues."
    )
    profiler_version: str = Field(
        "3.0.0", description="Semantic version of the profiler engine."
    )
    profiled_at:      str = Field(
        ..., description="ISO-8601 UTC timestamp of when profiling was performed."
    )

    # ── Convenience helpers ───────────────────────────────────────────────────

    def column(self, name: str) -> Optional[ColumnProfile]:
        """Return the ColumnProfile for *name*, or None if not found."""
        for col in self.columns:
            if col.name == name:
                return col
        return None

    def numeric_columns(self) -> List[ColumnProfile]:
        """Return all numeric column profiles."""
        return [c for c in self.columns if c.numerical_stats is not None]

    def categorical_columns(self) -> List[ColumnProfile]:
        """Return all categorical column profiles."""
        return [c for c in self.columns if c.categorical_stats is not None]

    def high_missing(self, threshold: float = 50.0) -> List[ColumnProfile]:
        """Return columns where missing % ≥ *threshold*."""
        return [c for c in self.columns if c.missing_pct >= threshold]

    def to_dict(self) -> dict:
        """Serialize the report to a plain Python dict (JSON-safe)."""
        return self.model_dump()

    def summary_text(self) -> str:
        """Return a concise human-readable summary string."""
        lines = [
            f"ProfilerReport — {self.profiled_at}",
            f"  Rows: {self.meta.row_count:,}  |  Columns: {self.meta.column_count}",
            f"  Missing cells: {self.meta.total_missing:,} "
            f"({self.meta.total_missing_pct:.1f}%)",
            f"  Duplicate rows: {self.duplicates.duplicate_row_count:,} "
            f"({self.duplicates.duplicate_row_pct:.1f}%)",
            f"  Memory: {self.meta.memory_usage_bytes / 1024:.1f} KB",
            f"  Problematic columns: {len(self.problematic)}",
        ]
        return "\n".join(lines)
