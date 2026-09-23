"""
Profiler Agent Package
──────────────────────
Deterministic, LLM-free DataFrame profiling engine.

Public API
----------
from agent.profiler import ProfilerAgent, ProfilerReport
report = ProfilerAgent().profile(df)
"""

from agent.profiler.models import (
    ProfilerReport,
    ColumnProfile,
    NumericalStats,
    CategoricalStats,
    DatasetMeta,
    ProblematicColumn,
    DuplicateInfo,
)
from agent.profiler.engine import ProfilerAgent

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
