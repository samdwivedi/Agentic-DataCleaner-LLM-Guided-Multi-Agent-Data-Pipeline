"""
Quality Assessment Package
──────────────────────────
Post-cleaning validation system.

Public API
----------
from agent.quality import QualityAssessor, QualityConfig, QualityReport

assessor = QualityAssessor(config=QualityConfig())
report = assessor.assess(df_before, df_after)
"""

from agent.quality.models import (
    DataQualityMetrics,
    IssueSeverity,
    QualityConfig,
    QualityIssue,
    QualityReport,
)
from agent.quality.engine import QualityAssessor

__all__ = [
    "QualityAssessor",
    "QualityConfig",
    "QualityReport",
    "DataQualityMetrics",
    "QualityIssue",
    "IssueSeverity",
]
