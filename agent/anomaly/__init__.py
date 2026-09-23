"""
Anomaly Detector Package
────────────────────────
Deterministic, configuration-driven DataFrame anomaly detection engine.

Public API
----------
from agent.anomaly import AnomalyDetector, AnomalyConfig, ColumnAnomalyResult, AnomalyReport

detector = AnomalyDetector(config=AnomalyConfig(iqr_multiplier=1.5, zscore_threshold=3.0))
report = detector.detect(df)
"""

from agent.anomaly.models import (
    AnomalyConfig,
    ColumnAnomalyResult,
    AnomalyReport,
)
from agent.anomaly.engine import AnomalyDetector

__all__ = [
    "AnomalyDetector",
    "AnomalyConfig",
    "ColumnAnomalyResult",
    "AnomalyReport",
]
