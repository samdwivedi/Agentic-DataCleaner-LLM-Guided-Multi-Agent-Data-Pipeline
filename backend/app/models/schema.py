"""
Schema Validator Models
───────────────────────
Strongly-typed Pydantic v2 models for configuring validation rules
and representing the validation report.

All report models are immutable (frozen=True).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ── Configuration Models ──────────────────────────────────────────────────────

class ColumnRule(BaseModel):
    """Configuration rules for a single DataFrame column."""
    
    expected_dtype: Optional[str] = Field(
        None, description="Expected pandas dtype (e.g., 'int64', 'float64', 'object', 'bool', 'datetime64[ns]')."
    )
    nullable: bool = Field(
        True, description="Whether the column is allowed to contain missing (null/NaN) values."
    )
    unique: bool = Field(
        False, description="Whether all non-null values in the column must be unique."
    )
    min_value: Optional[float] = Field(
        None, description="Minimum allowed numeric value (inclusive)."
    )
    max_value: Optional[float] = Field(
        None, description="Maximum allowed numeric value (inclusive)."
    )
    allowed_values: Optional[List[Any]] = Field(
        None, description="List of strictly allowed categorical values."
    )
    regex_pattern: Optional[str] = Field(
        None, description="Regex pattern that all non-null string values must match."
    )
    min_date: Optional[str] = Field(
        None, description="Minimum allowed date (inclusive), as ISO string (e.g., '2020-01-01')."
    )
    max_date: Optional[str] = Field(
        None, description="Maximum allowed date (inclusive), as ISO string (e.g., '2025-12-31')."
    )


class ValidationSchema(BaseModel):
    """Complete schema definition for a DataFrame."""
    
    required_columns: List[str] = Field(
        default_factory=list, description="List of column names that must exist in the DataFrame."
    )
    columns: Dict[str, ColumnRule] = Field(
        default_factory=dict, description="Mapping of column names to their specific validation rules."
    )


# ── Report Models ─────────────────────────────────────────────────────────────

class ValidationViolation(BaseModel, frozen=True):
    """Represents a single rule violation detected during validation."""
    
    column: Optional[str] = Field(
        None, description="The column where the violation occurred, if applicable."
    )
    rule: str = Field(
        ..., description="The name of the rule that was violated (e.g., 'required_column', 'min_value')."
    )
    message: str = Field(
        ..., description="Human-readable description of the violation."
    )


class SchemaReport(BaseModel, frozen=True):
    """
    Immutable validation report containing the overall result and any violations.
    """
    
    is_valid: bool = Field(
        ..., description="True if no violations were found, False otherwise."
    )
    rows_checked: int = Field(
        ..., description="Total number of rows processed in the DataFrame."
    )
    columns_checked: int = Field(
        ..., description="Total number of columns checked against the schema."
    )
    violations: List[ValidationViolation] = Field(
        default_factory=list, description="List of all detected violations."
    )
    validated_at: str = Field(
        ..., description="ISO-8601 UTC timestamp of when validation was performed."
    )
    validator_version: str = Field(
        "1.0.0", description="Semantic version of the validator engine."
    )

    def summary_text(self) -> str:
        """Return a concise human-readable summary string of the validation results."""
        status = "✅ PASSED" if self.is_valid else "❌ FAILED"
        lines = [
            f"Schema Validation Report — {self.validated_at}",
            f"  Status: {status}",
            f"  Rows checked: {self.rows_checked:,}",
            f"  Columns checked: {self.columns_checked}",
            f"  Violations found: {len(self.violations)}",
        ]
        
        if self.violations:
            lines.append("\nTop Violations:")
            for i, v in enumerate(self.violations[:10], 1):
                col_str = f"[{v.column}] " if v.column else ""
                lines.append(f"  {i}. {col_str}({v.rule}) {v.message}")
            if len(self.violations) > 10:
                lines.append(f"  ... and {len(self.violations) - 10} more.")
                
        return "\n".join(lines)
