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

from app.agents.anomaly_detector.agent import AnomalyDetector
from app.models.anomaly import (
    AnomalyConfig,
    AnomalyReport,
    ColumnAnomalyResult,
)

__all__ = [
    "AnomalyConfig",
    "AnomalyDetector",
    "AnomalyReport",
    "ColumnAnomalyResult",
]
