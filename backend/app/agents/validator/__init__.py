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

from app.agents.validator.agent import QualityAssessor
from app.models.quality import (
    DataQualityMetrics,
    IssueSeverity,
    QualityConfig,
    QualityIssue,
    QualityReport,
)

__all__ = [
    "DataQualityMetrics",
    "IssueSeverity",
    "QualityAssessor",
    "QualityConfig",
    "QualityIssue",
    "QualityReport",
]
