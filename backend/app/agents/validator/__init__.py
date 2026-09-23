"""
Quality Assessment Package
──────────────────────────
Post-cleaning validation system.

Public API
----------
from app.agents.validator import QualityAssessor, QualityConfig, QualityReport

assessor = QualityAssessor(config=QualityConfig())
report = assessor.assess(df_before, df_after)
"""

from app.models.quality import (
    DataQualityMetrics,
    IssueSeverity,
    QualityConfig,
    QualityIssue,
    QualityReport,
)
from app.agents.validator.agent import QualityAssessor

__all__ = [
    "QualityAssessor",
    "QualityConfig",
    "QualityReport",
    "DataQualityMetrics",
    "QualityIssue",
    "IssueSeverity",
]
