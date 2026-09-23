"""
Schema Validator Package
────────────────────────
Deterministic, configuration-driven DataFrame validation engine.

Public API
----------
from agent.validator import SchemaValidator, ValidationSchema, ColumnRule
from agent.validator import SchemaReport, ValidationViolation

validator = SchemaValidator()
report = validator.validate(df, schema)
"""

from agent.validator.models import (
    ColumnRule,
    ValidationSchema,
    ValidationViolation,
    SchemaReport,
)
from agent.validator.engine import SchemaValidator

__all__ = [
    "SchemaValidator",
    "ValidationSchema",
    "ColumnRule",
    "SchemaReport",
    "ValidationViolation",
]
