"""
Profiler Agent Package
──────────────────────
Deterministic, LLM-free DataFrame profiling engine.

Public API
----------
from app.agents.profiler import ProfilerAgent, ProfilerReport
report = ProfilerAgent().profile(df)
"""

from app.models.profiler import (
    ProfilerReport,
    ColumnProfile,
    NumericalStats,
    CategoricalStats,
    DatasetMeta,
    ProblematicColumn,
    DuplicateInfo,
)
from app.agents.profiler.agent import ProfilerAgent

__all__ = [
    "ProfilerAgent",
    "ProfilerReport",
    "ColumnProfile",
    "NumericalStats",
    "CategoricalStats",
    "DatasetMeta",
    "ProblematicColumn",
    "DuplicateInfo",
]
