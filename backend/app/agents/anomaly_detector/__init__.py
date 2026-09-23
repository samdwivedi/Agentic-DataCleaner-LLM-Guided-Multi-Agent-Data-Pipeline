"""
Anomaly Detector Package
────────────────────────
Deterministic, configuration-driven DataFrame anomaly detection engine.

Public API
----------
from app.agents.anomaly_detector import AnomalyDetector, AnomalyConfig, ColumnAnomalyResult, AnomalyReport

detector = AnomalyDetector(config=AnomalyConfig(iqr_multiplier=1.5, zscore_threshold=3.0))
report = detector.detect(df)
"""

from app.models.anomaly import (
    AnomalyConfig,
    ColumnAnomalyResult,
    AnomalyReport,
)
from app.agents.anomaly_detector.agent import AnomalyDetector

__all__ = [
    "AnomalyDetector",
    "AnomalyConfig",
    "ColumnAnomalyResult",
    "AnomalyReport",
]
