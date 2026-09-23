"""
Profiler Agent Package
──────────────────────
Deterministic, LLM-free DataFrame profiling engine.

Public API
----------
from app.agents.profiler import ProfilerAgent, ProfilerReport
report = ProfilerAgent().profile(df)
"""

from app.agents.profiler.agent import ProfilerAgent
from app.models.profiler import (
    CategoricalStats,
    ColumnProfile,
    DatasetMeta,
    DuplicateInfo,
    NumericalStats,
    ProblematicColumn,
    ProfilerReport,
)

__all__ = [
    "CategoricalStats",
    "ColumnProfile",
    "DatasetMeta",
    "DuplicateInfo",
    "NumericalStats",
    "ProblematicColumn",
    "ProfilerAgent",
    "ProfilerReport",
]
