"""
Strategist Models
─────────────────
Strongly-typed Pydantic v2 models for configuring the LLM Strategist and 
defining the strictly constrained JSON output (CleaningStrategy).
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ── Action Registry (Strict Enums) ────────────────────────────────────────────

class ActionRegistry(str, Enum):
    """Allowed cleaning actions the LLM can select from."""
    
    DROP_COLUMN = "drop_column"
    DROP_ROWS = "drop_rows"
    MEDIAN_IMPUTATION = "median_imputation"
    MEAN_IMPUTATION = "mean_imputation"
    MODE_IMPUTATION = "mode_imputation"
    CONSTANT_IMPUTATION = "constant_imputation"
    CLAMP_OUTLIERS = "clamp_outliers"
    DROP_OUTLIERS = "drop_outliers"
    NONE = "none"


# ── Strategy Models (LLM Output) ──────────────────────────────────────────────

class CleaningAction(BaseModel):
    """A single cleaning instruction proposed by the LLM."""
    
    column: str = Field(
        ..., description="The exact name of the column to clean."
    )
    action: ActionRegistry = Field(
        ..., description="The specific cleaning action to apply."
    )
    parameters: Dict[str, Any] = Field(
        default_factory=dict, description="Optional parameters for the action (e.g., {'value': 0})."
    )
    reason: str = Field(
        ..., description="Explanation of why this action was chosen based on the reports."
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence score for this action (0.0 to 1.0)."
    )


class CleaningStrategy(BaseModel):
    """The complete output strategy containing all proposed actions."""
    
    actions: List[CleaningAction] = Field(
        default_factory=list, description="List of proposed cleaning actions."
    )
    status: str = Field(
        "success", description="Status of the strategy generation ('success' or 'error')."
    )
    error_message: Optional[str] = Field(
        None, description="Error details if the LLM provider failed."
    )


# ── Configuration Models ──────────────────────────────────────────────────────

class StrategistConfig(BaseModel):
    """Configuration for the LLM Strategist Agent."""
    
    provider: str = Field("ollama", description="The LLM provider to use.")
    model_name: str = Field("llama3", description="The exact model name (e.g., 'llama3', 'mistral').")
    endpoint_url: str = Field("http://localhost:11434/api/generate", description="API endpoint for the provider.")
    timeout_seconds: float = Field(30.0, description="Timeout for the LLM API call.")
    max_retries: int = Field(3, description="Maximum number of retries for parsing errors or network failures.")
    temperature: float = Field(0.0, description="LLM temperature (0.0 recommended for deterministic JSON).")
