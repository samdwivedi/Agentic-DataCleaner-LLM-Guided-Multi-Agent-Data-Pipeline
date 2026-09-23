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

from app.models.schema import (
    ColumnRule,
    ValidationSchema,
    ValidationViolation,
    SchemaReport,
)
from app.agents.schema_validator.agent import SchemaValidator

__all__ = [
    "SchemaValidator",
    "ValidationSchema",
    "ColumnRule",
    "SchemaReport",
    "ValidationViolation",
]
