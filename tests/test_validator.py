"""
Comprehensive unit tests for the Phase 4 Schema Validator Agent.

Run with:
    pytest tests/test_validator.py -v
"""

from __future__ import annotations

import pandas as pd
import numpy as np
import pytest

from agent.validator import (
    SchemaValidator,
    ValidationSchema,
    ColumnRule,
    SchemaReport,
    ValidationViolation,
)


@pytest.fixture(scope="session")
def validator() -> SchemaValidator:
    return SchemaValidator()


def test_valid_schema(validator):
    df = pd.DataFrame({
        "id": [1, 2, 3],
        "name": ["Alice", "Bob", "Charlie"],
        "age": [25, 30, 35]
    })
    
    schema = ValidationSchema(
        required_columns=["id", "name"],
        columns={
            "id": ColumnRule(expected_dtype="int", unique=True, min_value=1),
            "name": ColumnRule(expected_dtype="str", nullable=False, regex_pattern="^[A-Z][a-z]+$"),
            "age": ColumnRule(expected_dtype="int", min_value=0, max_value=120)
        }
    )
    
    report = validator.validate(df, schema)
    assert report.is_valid is True
    assert len(report.violations) == 0
    assert report.rows_checked == 3
    assert report.columns_checked == 3


def test_missing_required_column(validator):
    df = pd.DataFrame({"id": [1, 2]})
    schema = ValidationSchema(required_columns=["id", "name"])
    
    report = validator.validate(df, schema)
    assert report.is_valid is False
    assert len(report.violations) == 1
    v = report.violations[0]
    assert v.column == "name"
    assert v.rule == "required_column"


def test_dtype_mismatch(validator):
    df = pd.DataFrame({"age": ["twenty", "thirty"]})
    schema = ValidationSchema(columns={"age": ColumnRule(expected_dtype="int")})
    
    report = validator.validate(df, schema)
    assert report.is_valid is False
    assert len(report.violations) == 1
    assert report.violations[0].rule == "expected_dtype"


def test_nullability_violation(validator):
    df = pd.DataFrame({"name": ["Alice", None, "Charlie"]})
    schema = ValidationSchema(columns={"name": ColumnRule(nullable=False)})
    
    report = validator.validate(df, schema)
    assert report.is_valid is False
    assert len(report.violations) == 1
    assert report.violations[0].rule == "nullable"


def test_min_max_value_violation(validator):
    df = pd.DataFrame({"score": [-5, 50, 150]})
    schema = ValidationSchema(columns={"score": ColumnRule(min_value=0, max_value=100)})
    
    report = validator.validate(df, schema)
    assert report.is_valid is False
    # Should flag both -5 and 150
    assert len(report.violations) == 2
    rules = [v.rule for v in report.violations]
    assert "min_value" in rules
    assert "max_value" in rules


def test_allowed_values_violation(validator):
    df = pd.DataFrame({"color": ["red", "green", "purple"]})
    schema = ValidationSchema(
        columns={"color": ColumnRule(allowed_values=["red", "green", "blue"])}
    )
    
    report = validator.validate(df, schema)
    assert report.is_valid is False
    assert len(report.violations) == 1
    assert report.violations[0].rule == "allowed_values"
    assert "purple" in report.violations[0].message


def test_uniqueness_violation(validator):
    df = pd.DataFrame({"id": [1, 2, 2, 3]})
    schema = ValidationSchema(columns={"id": ColumnRule(unique=True)})
    
    report = validator.validate(df, schema)
    assert report.is_valid is False
    assert len(report.violations) == 1
    assert report.violations[0].rule == "unique"


def test_regex_pattern_violation(validator):
    df = pd.DataFrame({"code": ["A123", "B456", "123C"]})
    schema = ValidationSchema(
        columns={"code": ColumnRule(regex_pattern="^[A-Z][0-9]{3}$")}
    )
    
    report = validator.validate(df, schema)
    assert report.is_valid is False
    assert len(report.violations) == 1
    assert report.violations[0].rule == "regex_pattern"


def test_ignore_missing_non_required_column(validator):
    df = pd.DataFrame({"id": [1, 2]})
    schema = ValidationSchema(
        required_columns=["id"],
        columns={"age": ColumnRule(min_value=0)}  # age has rules but is not required
    )
    
    report = validator.validate(df, schema)
    assert report.is_valid is True
    assert report.columns_checked == 0  # didn't check age since it wasn't there (id has no rules)


def test_all_nulls_in_nullable_column_passes(validator):
    df = pd.DataFrame({"age": [np.nan, np.nan]})
    # It is nullable by default. And if it is all null, numeric rules should be skipped.
    schema = ValidationSchema(columns={"age": ColumnRule(min_value=0, max_value=100)})
    
    report = validator.validate(df, schema)
    assert report.is_valid is True


def test_summary_text_generation(validator):
    df = pd.DataFrame({"age": [-10]})
    schema = ValidationSchema(columns={"age": ColumnRule(min_value=0)})
    report = validator.validate(df, schema)
    
    summary = report.summary_text()
    assert "FAILED" in summary
    assert "min_value" in summary


def test_date_validity(validator):
    df = pd.DataFrame({
        "dob": ["1990-01-01", "2025-12-31", "invalid_date", "1980-05-15"]
    })
    schema = ValidationSchema(
        columns={
            "dob": ColumnRule(min_date="1985-01-01", max_date="2020-01-01")
        }
    )
    
    report = validator.validate(df, schema)
    assert report.is_valid is False
    # "2025-12-31" is > max_date
    # "invalid_date" fails parsing
    # "1980-05-15" is < min_date
    assert len(report.violations) == 3
    rules = [v.rule for v in report.violations]
    assert "date_format" in rules
    assert "min_date" in rules
    assert "max_date" in rules


def test_raises_type_error_on_invalid_inputs(validator):
    with pytest.raises(TypeError):
        validator.validate([1, 2, 3], ValidationSchema())
        
    with pytest.raises(TypeError):
        validator.validate(pd.DataFrame(), {"required_columns": []})
