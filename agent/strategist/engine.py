"""
Strategist Engine
─────────────────
The main orchestration layer for the LLM Strategist Agent.
Injects reports, calls the provider, and robustly parses the output into 
a strict Pydantic CleaningStrategy.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from pydantic import ValidationError

from agent.strategist.models import StrategistConfig, CleaningStrategy
from agent.strategist.prompts import (
    STRATEGIST_SYSTEM_PROMPT,
    PROMPT_VERSION,
    build_strategist_prompt,
)
from agent.strategist.providers import BaseLLMProvider, OllamaProvider

logger = logging.getLogger(__name__)


class StrategistAgent:
    """Orchestrates LLM calls to generate cleaning strategies."""
    
    def __init__(self, config: StrategistConfig = None, provider: BaseLLMProvider = None):
        self.config = config or StrategistConfig()
        # Default to OllamaProvider if not injected
        self.provider = provider or OllamaProvider(self.config)

    def generate_strategy(
        self, 
        profiler_report_dict: Dict[str, Any], 
        schema_report_dict: Dict[str, Any], 
        anomaly_report_dict: Dict[str, Any],
        user_config: Optional[Dict[str, Any]] = None,
    ) -> CleaningStrategy:
        """
        Takes deterministic reports (dicts), sends them to the LLM, and 
        returns a strongly-typed CleaningStrategy.
        
        Parameters
        ----------
        profiler_report_dict : dict
            Serialized ProfilerReport.
        schema_report_dict : dict
            Serialized SchemaReport.
        anomaly_report_dict : dict
            Serialized AnomalyReport.
        user_config : dict, optional
            Optional user-provided preferences (e.g. preferred actions).
        """
        logger.info(
            "StrategistAgent starting (prompt v%s, model=%s, provider=%s)",
            PROMPT_VERSION, self.config.model_name, self.config.provider,
        )

        # 1. Prepare reports — serialize to formatted JSON strings
        prof_json = json.dumps(profiler_report_dict, indent=2)
        schem_json = json.dumps(schema_report_dict, indent=2)
        anom_json = json.dumps(anomaly_report_dict, indent=2)
        user_cfg_json = json.dumps(user_config, indent=2) if user_config else None
        
        user_prompt = build_strategist_prompt(prof_json, schem_json, anom_json, user_cfg_json)
        
        # 2. Retry loop
        for attempt in range(1, self.config.max_retries + 1):
            try:
                logger.info("Strategist calling LLM (attempt %d/%d)...", attempt, self.config.max_retries)
                
                raw_response = self.provider.generate_strategy(
                    system_prompt=STRATEGIST_SYSTEM_PROMPT, 
                    user_prompt=user_prompt
                )
                
                # 3. Parse JSON
                try:
                    # The model might include markdown code blocks despite instructions, 
                    # so we strip them just in case.
                    clean_response = raw_response.strip()
                    if clean_response.startswith("```json"):
                        clean_response = clean_response[7:]
                    if clean_response.startswith("```"):
                        clean_response = clean_response[3:]
                    if clean_response.endswith("```"):
                        clean_response = clean_response[:-3]
                        
                    parsed_json = json.loads(clean_response)
                except json.JSONDecodeError as e:
                    logger.warning("Attempt %d: LLM returned malformed JSON: %s", attempt, str(e))
                    continue # Try again

                # 4. Validate with Pydantic
                strategy = CleaningStrategy.model_validate(parsed_json)
                logger.info("Successfully generated CleaningStrategy with %d actions.", len(strategy.actions))
                return strategy
                
            except ValidationError as e:
                logger.warning("Attempt %d: LLM output failed Pydantic validation: %s", attempt, str(e))
                continue # Try again
                
            except RuntimeError as e:
                # Network errors, timeouts. Don't retry these infinitely in a tight loop.
                # In a real app, maybe backoff, but here we just fallback.
                logger.error("LLM Provider failed: %s", str(e))
                break 

        # 5. Fallback
        logger.error("Strategist failed to generate a valid strategy after %d attempts. Returning fallback.", self.config.max_retries)
        return CleaningStrategy(
            actions=[],
            status="error",
            error_message="Failed to generate valid strategy. Check LLM availability or prompt constraints."
        )

