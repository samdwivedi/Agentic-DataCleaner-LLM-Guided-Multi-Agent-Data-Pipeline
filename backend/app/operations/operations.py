"""
Executor Operations
───────────────────
Pure, deterministic, side-effect-free functions that each perform exactly
one cleaning transformation on a pandas DataFrame **copy**.

Rules
-----
1. Every function receives a DataFrame and returns a DataFrame.
2. The input DataFrame is NEVER mutated — all functions operate on copies
   internally or use non-mutating pandas APIs.
3. No function executes arbitrary code, LLM output, SQL, or eval().
4. Each function is independently testable.
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


# ── Type alias for operation return values ────────────────────────────────────
# (modified_df, rows_affected, values_changed)
OpResult = tuple[pd.DataFrame, int, int]


# ═══════════════════════════════════════════════════════════════════════════════
# IMPUTATION OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════════


def median_imputation(df: pd.DataFrame, column: str, params: dict[str, Any]) -> OpResult:
    """Fill missing values with the column's median."""
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found.")

    null_mask = df[column].isna()
    null_count = int(null_mask.sum())

    if null_count == 0:
        return df, 0, 0  # no-op

    median_val = df[column].median()
    result = df.copy()
    result[column] = result[column].fillna(median_val)
    return result, null_count, null_count


def mean_imputation(df: pd.DataFrame, column: str, params: dict[str, Any]) -> OpResult:
    """Fill missing values with the column's mean."""
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found.")

    null_mask = df[column].isna()
    null_count = int(null_mask.sum())

    if null_count == 0:
        return df, 0, 0

    mean_val = df[column].mean()
    result = df.copy()
    result[column] = result[column].fillna(mean_val)
    return result, null_count, null_count


def mode_imputation(df: pd.DataFrame, column: str, params: dict[str, Any]) -> OpResult:
    """Fill missing values with the column's mode (most frequent value)."""
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found.")

    null_mask = df[column].isna()
    null_count = int(null_mask.sum())

    if null_count == 0:
        return df, 0, 0

    modes = df[column].mode()
    if modes.empty:
        # All values are null — nothing to impute from
        return df, 0, 0

    mode_val = modes.iloc[0]
    result = df.copy()
    result[column] = result[column].fillna(mode_val)
    return result, null_count, null_count


def constant_imputation(df: pd.DataFrame, column: str, params: dict[str, Any]) -> OpResult:
    """Fill missing values with a user-specified constant."""
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found.")

    value = params.get("value")
    if value is None:
        raise ValueError("constant_imputation requires a 'value' parameter.")

    null_mask = df[column].isna()
    null_count = int(null_mask.sum())

    if null_count == 0:
        return df, 0, 0

    result = df.copy()
    result[column] = result[column].fillna(value)
    return result, null_count, null_count


# ═══════════════════════════════════════════════════════════════════════════════
# DROP OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════════


def drop_column(df: pd.DataFrame, column: str, params: dict[str, Any]) -> OpResult:
    """Remove an entire column from the DataFrame."""
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found.")

    rows_before = len(df)
    result = df.drop(columns=[column])
    return result, 0, rows_before  # every row lost one cell


def drop_rows(df: pd.DataFrame, column: str, params: dict[str, Any]) -> OpResult:
    """Drop rows where the specified column has missing values."""
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found.")

    null_mask = df[column].isna()
    null_count = int(null_mask.sum())

    if null_count == 0:
        return df, 0, 0

    result = df[~null_mask].reset_index(drop=True)
    return result, null_count, 0


def drop_outliers(df: pd.DataFrame, column: str, params: dict[str, Any]) -> OpResult:
    """Drop rows where the column value is an IQR-based outlier."""
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found.")

    q1 = df[column].quantile(0.25)
    q3 = df[column].quantile(0.75)
    iqr = q3 - q1
    multiplier = params.get("iqr_multiplier", 1.5)
    lower = q1 - multiplier * iqr
    upper = q3 + multiplier * iqr

    outlier_mask = (df[column] < lower) | (df[column] > upper)
    outlier_count = int(outlier_mask.sum())

    if outlier_count == 0:
        return df, 0, 0

    result = df[~outlier_mask].reset_index(drop=True)
    return result, outlier_count, 0


def remove_duplicates(df: pd.DataFrame, column: str, params: dict[str, Any]) -> OpResult:
    """Remove duplicate rows (considering all columns or a subset)."""
    subset = params.get("subset")  # optional list of columns
    rows_before = len(df)
    result = df.drop_duplicates(subset=subset).reset_index(drop=True)
    rows_removed = rows_before - len(result)
    return result, rows_removed, 0


# ═══════════════════════════════════════════════════════════════════════════════
# OUTLIER CAPPING
# ═══════════════════════════════════════════════════════════════════════════════


def clamp_outliers(df: pd.DataFrame, column: str, params: dict[str, Any]) -> OpResult:
    """Clamp (winsorise) outlier values to IQR-derived bounds."""
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found.")

    q1 = df[column].quantile(0.25)
    q3 = df[column].quantile(0.75)
    iqr = q3 - q1
    multiplier = params.get("iqr_multiplier", 1.5)

    lower = params.get("lower", q1 - multiplier * iqr)
    upper = params.get("upper", q3 + multiplier * iqr)

    below_mask = df[column] < lower
    above_mask = df[column] > upper
    values_changed = int(below_mask.sum() + above_mask.sum())

    if values_changed == 0:
        return df, 0, 0

    result = df.copy()
    result[column] = result[column].clip(lower=lower, upper=upper)
    return result, values_changed, values_changed


def cap_outliers(df: pd.DataFrame, column: str, params: dict[str, Any]) -> OpResult:
    """Alias for clamp_outliers — caps values at IQR-derived bounds."""
    return clamp_outliers(df, column, params)


# ═══════════════════════════════════════════════════════════════════════════════
# CATEGORY & TYPE OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════════


def standardize_categories(df: pd.DataFrame, column: str, params: dict[str, Any]) -> OpResult:
    """
    Standardise categorical values: strip whitespace, lowercase, and
    optionally apply a mapping dict.
    """
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found.")

    result = df.copy()
    non_null_mask = result[column].notna()
    original = result.loc[non_null_mask, column].copy()

    # Step 1: strip + lowercase
    standardised = original.astype(str).str.strip().str.lower()

    # Step 2: optional explicit mapping
    mapping = params.get("mapping")
    if mapping:
        standardised = standardised.map(lambda v: mapping.get(v, v))

    changed_mask = original.astype(str) != standardised
    values_changed = int(changed_mask.sum())

    result.loc[non_null_mask, column] = standardised
    return result, values_changed, values_changed


def convert_datatype(df: pd.DataFrame, column: str, params: dict[str, Any]) -> OpResult:
    """
    Convert a column to a target pandas dtype.

    Requires a 'target_dtype' parameter (e.g. 'int64', 'float64', 'str', 'datetime64[ns]').
    Uses errors='coerce' for numeric/datetime conversions to avoid crashes.
    """
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found.")

    target_dtype = params.get("target_dtype")
    if not target_dtype:
        raise ValueError("convert_datatype requires a 'target_dtype' parameter.")

    result = df.copy()
    old_dtype = str(result[column].dtype)

    try:
        if target_dtype in ("datetime64[ns]", "datetime"):
            result[column] = pd.to_datetime(result[column], errors="coerce")
        elif target_dtype in ("int64", "int32", "int", "float64", "float32", "float"):
            result[column] = pd.to_numeric(result[column], errors="coerce")
            if "int" in target_dtype:
                # Use nullable int to handle NaN
                result[column] = result[column].astype("Int64")
            else:
                result[column] = result[column].astype(target_dtype)
        elif target_dtype in ("str", "string", "object"):
            result[column] = result[column].astype(str)
        elif target_dtype == "bool":
            result[column] = result[column].astype(bool)
        elif target_dtype == "category":
            result[column] = result[column].astype("category")
        else:
            result[column] = result[column].astype(target_dtype)
    except (ValueError, TypeError) as e:
        raise ValueError(f"Cannot convert column '{column}' to '{target_dtype}': {e}")

    new_dtype = str(result[column].dtype)
    values_changed = len(result) if old_dtype != new_dtype else 0
    return result, 0, values_changed


def noop(df: pd.DataFrame, column: str, params: dict[str, Any]) -> OpResult:
    """No-op: returns the DataFrame unchanged."""
    return df, 0, 0


# ═══════════════════════════════════════════════════════════════════════════════
# OPERATION DISPATCH TABLE
# ═══════════════════════════════════════════════════════════════════════════════

OPERATION_DISPATCH = {
    "median_imputation":      median_imputation,
    "mean_imputation":        mean_imputation,
    "mode_imputation":        mode_imputation,
    "constant_imputation":    constant_imputation,
    "drop_column":            drop_column,
    "drop_rows":              drop_rows,
    "drop_outliers":          drop_outliers,
    "remove_duplicates":      remove_duplicates,
    "clamp_outliers":         clamp_outliers,
    "cap_outliers":           cap_outliers,
    "standardize_categories": standardize_categories,
    "convert_datatype":       convert_datatype,
    "none":                   noop,
}
