"""
Schema Validator Engine
───────────────────────
Deterministic, LLM-free DataFrame schema validation engine.

Key guarantees
--------------
* The input DataFrame is NEVER modified.
* Returns a fully validated, frozen ``SchemaReport``.
* Operates based strictly on a ``ValidationSchema`` configuration.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List

import pandas as pd
import numpy as np

from app.models.schema import (
    ColumnRule,
    ValidationSchema,
    ValidationViolation,
    SchemaReport,
)

logger = logging.getLogger(__name__)

_VALIDATOR_VERSION = "1.0.0"


class SchemaValidator:
    """
    Deterministic DataFrame schema validator.
    """

    def validate(self, df: pd.DataFrame, schema: ValidationSchema) -> SchemaReport:
        """
        Validate *df* against *schema* and return an immutable ``SchemaReport``.

        Parameters
        ----------
        df : pd.DataFrame
            The DataFrame to validate.
        schema : ValidationSchema
            The schema rules to enforce.

        Returns
        -------
        SchemaReport
            Fully validated, frozen validation report.
        """
        if not isinstance(df, pd.DataFrame):
            raise TypeError(f"Expected pd.DataFrame, got {type(df).__name__}")
        
        if not isinstance(schema, ValidationSchema):
            raise TypeError(f"Expected ValidationSchema, got {type(schema).__name__}")

        logger.info("SchemaValidator.validate() → shape=%s", df.shape)

        violations: List[ValidationViolation] = []
        rows_checked = len(df)
        columns_checked = 0

        # ── 1. Check required columns ─────────────────────────────────────────
        existing_columns = set(df.columns)
        for req_col in schema.required_columns:
            if req_col not in existing_columns:
                violations.append(
                    ValidationViolation(
                        column=req_col,
                        rule="required_column",
                        message=f"Required column '{req_col}' is missing from the dataset."
                    )
                )

        # ── 2. Check column rules ─────────────────────────────────────────────
        for col_name, rule in schema.columns.items():
            if col_name not in existing_columns:
                # If a column has rules but is missing, we don't evaluate the rules,
                # but it should have been caught by required_columns if it was mandatory.
                continue
            
            columns_checked += 1
            series = df[col_name]
            
            self._validate_column(col_name, series, rule, violations)

        # ── 3. Assemble report ────────────────────────────────────────────────
        is_valid = len(violations) == 0
        report = SchemaReport(
            is_valid=is_valid,
            rows_checked=rows_checked,
            columns_checked=columns_checked,
            violations=violations,
            validated_at=datetime.now(timezone.utc).isoformat(),
            validator_version=_VALIDATOR_VERSION,
        )

        logger.info(
            "Validation complete: is_valid=%s, violations=%d",
            is_valid, len(violations)
        )
        return report

    def _validate_column(
        self, 
        col_name: str, 
        series: pd.Series, 
        rule: ColumnRule, 
        violations: List[ValidationViolation]
    ) -> None:
        """Apply a ColumnRule to a specific pandas Series, accumulating violations."""
        
        # 1. Nullability
        null_mask = series.isna()
        null_count = null_mask.sum()
        
        if not rule.nullable and null_count > 0:
            violations.append(
                ValidationViolation(
                    column=col_name,
                    rule="nullable",
                    message=f"Column contains {null_count} missing value(s) but is marked as non-nullable."
                )
            )
            
        non_null_series = series[~null_mask]
        if non_null_series.empty:
            # If everything is null (or empty), skip further value checks
            return

        # 2. Datatype
        if rule.expected_dtype is not None:
            actual_dtype = str(series.dtype)
            
            # Allow some flexibility, e.g., if expected is 'int64', accept 'Int64' (nullable int) or 'int32' 
            # based on substring matching, or exact match. For strictness, we'll do an exact match or 
            # kind match (e.g. expected='int' matches 'int64', 'int32').
            if not self._is_dtype_compatible(actual_dtype, rule.expected_dtype):
                violations.append(
                    ValidationViolation(
                        column=col_name,
                        rule="expected_dtype",
                        message=f"Expected dtype '{rule.expected_dtype}', found '{actual_dtype}'."
                    )
                )

        # 3. Numeric Ranges
        if rule.min_value is not None:
            try:
                out_of_bounds = (non_null_series < rule.min_value).sum()
                if out_of_bounds > 0:
                    violations.append(
                        ValidationViolation(
                            column=col_name,
                            rule="min_value",
                            message=f"Found {out_of_bounds} value(s) below the minimum allowed ({rule.min_value})."
                        )
                    )
            except TypeError:
                pass # e.g. comparing strings to min_value float
                
        if rule.max_value is not None:
            try:
                out_of_bounds = (non_null_series > rule.max_value).sum()
                if out_of_bounds > 0:
                    violations.append(
                        ValidationViolation(
                            column=col_name,
                            rule="max_value",
                            message=f"Found {out_of_bounds} value(s) above the maximum allowed ({rule.max_value})."
                        )
                    )
            except TypeError:
                pass

        # 4. Categorical Allowed Values
        if rule.allowed_values is not None:
            invalid_vals = non_null_series[~non_null_series.isin(rule.allowed_values)]
            invalid_count = len(invalid_vals)
            if invalid_count > 0:
                unique_invalid = invalid_vals.unique().tolist()
                violations.append(
                    ValidationViolation(
                        column=col_name,
                        rule="allowed_values",
                        message=f"Found {invalid_count} value(s) not in allowed list. Example invalid values: {unique_invalid[:3]}"
                    )
                )

        # 5. Uniqueness
        if rule.unique:
            dup_count = non_null_series.duplicated().sum()
            if dup_count > 0:
                violations.append(
                    ValidationViolation(
                        column=col_name,
                        rule="unique",
                        message=f"Column requires unique values, but found {dup_count} duplicate(s)."
                    )
                )

        # Date Validity (min_date, max_date)
        if rule.min_date is not None or rule.max_date is not None:
            try:
                datetime_series = pd.to_datetime(non_null_series, errors='coerce')
                valid_dates = datetime_series.dropna()
                
                # Report invalid dates if there were conversion errors
                invalid_dates_count = len(non_null_series) - len(valid_dates)
                if invalid_dates_count > 0:
                    violations.append(
                        ValidationViolation(
                            column=col_name,
                            rule="date_format",
                            message=f"Found {invalid_dates_count} value(s) that could not be parsed as dates."
                        )
                    )

                if rule.min_date is not None:
                    min_dt = pd.to_datetime(rule.min_date)
                    out_of_bounds = (valid_dates < min_dt).sum()
                    if out_of_bounds > 0:
                        violations.append(
                            ValidationViolation(
                                column=col_name,
                                rule="min_date",
                                message=f"Found {out_of_bounds} date(s) before the minimum allowed ({rule.min_date})."
                            )
                        )
                        
                if rule.max_date is not None:
                    max_dt = pd.to_datetime(rule.max_date)
                    out_of_bounds = (valid_dates > max_dt).sum()
                    if out_of_bounds > 0:
                        violations.append(
                            ValidationViolation(
                                column=col_name,
                                rule="max_date",
                                message=f"Found {out_of_bounds} date(s) after the maximum allowed ({rule.max_date})."
                            )
                        )
            except Exception as e:
                violations.append(
                    ValidationViolation(
                        column=col_name,
                        rule="date_validity",
                        message=f"Error evaluating date constraints: {str(e)}"
                    )
                )

        # 6. Regex Pattern
        if rule.regex_pattern is not None:
            # Cast to string safely and check match
            try:
                str_series = non_null_series.astype(str)
                # str.match checks from beginning of string
                matches = str_series.str.match(rule.regex_pattern)
                mismatch_count = (~matches).sum()
                if mismatch_count > 0:
                    violations.append(
                        ValidationViolation(
                            column=col_name,
                            rule="regex_pattern",
                            message=f"Found {mismatch_count} value(s) not matching regex pattern '{rule.regex_pattern}'."
                        )
                    )
            except Exception as e:
                violations.append(
                    ValidationViolation(
                        column=col_name,
                        rule="regex_pattern",
                        message=f"Error applying regex pattern: {str(e)}"
                    )
                )
                
    def _is_dtype_compatible(self, actual: str, expected: str) -> bool:
        """Check if pandas actual dtype is compatible with the expected string."""
        actual_lower = actual.lower()
        expected_lower = expected.lower()
        
        if actual_lower == expected_lower:
            return True
            
        # Broad categories
        if expected_lower in ('int', 'integer'):
            return 'int' in actual_lower
        if expected_lower in ('float', 'numeric'):
            return 'float' in actual_lower or 'int' in actual_lower
        if expected_lower in ('str', 'string', 'text'):
            return actual_lower in ('object', 'string')
        if expected_lower == 'bool':
            return 'bool' in actual_lower
        if expected_lower == 'datetime':
            return 'datetime' in actual_lower
            
        return False
