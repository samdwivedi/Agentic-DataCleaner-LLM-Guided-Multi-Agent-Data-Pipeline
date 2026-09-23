"""
Schema Validator Package
────────────────────────
Deterministic, configuration-driven DataFrame validation engine.

Public API
----------
from app.agents.schema_validator import SchemaValidator, ValidationSchema, ColumnRule
from app.agents.schema_validator import SchemaReport, ValidationViolation

validator = SchemaValidator()
report = validator.validate(df, schema)
"""

from app.agents.schema_validator.agent import SchemaValidator
from app.models.schema import (
    ColumnRule,
    SchemaReport,
    ValidationSchema,
    ValidationViolation,
)

__all__ = [
    "ColumnRule",
    "SchemaReport",
    "SchemaValidator",
    "ValidationSchema",
    "ValidationViolation",
]
