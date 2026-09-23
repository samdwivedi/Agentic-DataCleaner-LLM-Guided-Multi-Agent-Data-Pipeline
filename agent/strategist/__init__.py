"""
LLM Strategist Package
──────────────────────
Reasons about deterministic reports (Profiler, Schema, Anomaly) and outputs 
a strongly-typed CleaningStrategy without modifying the data directly.

Public API
----------
from agent.strategist import StrategistAgent, StrategistConfig
from agent.strategist import CleaningStrategy, CleaningAction, ActionRegistry
"""

from agent.strategist.models import (
    StrategistConfig,
    CleaningStrategy,
    CleaningAction,
    ActionRegistry,
)
from agent.strategist.engine import StrategistAgent

__all__ = [
    "StrategistAgent",
    "StrategistConfig",
    "CleaningStrategy",
    "CleaningAction",
    "ActionRegistry",
]
