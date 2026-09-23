"""
Strategist Providers
────────────────────
LLM Provider abstractions. Allows plugging in different models/APIs
(Ollama, OpenAI, Anthropic, etc.) without altering the strategist logic.
"""

from __future__ import annotations

import json
import logging
import httpx
from abc import ABC, abstractmethod
from typing import Dict, Any

from app.models.strategy import StrategistConfig

logger = logging.getLogger(__name__)


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    def __init__(self, config: StrategistConfig):
        self.config = config

    @abstractmethod
    def generate_strategy(self, system_prompt: str, user_prompt: str) -> str:
        """
        Sends the prompts to the LLM and returns the raw string response.
        Should handle its own network timeouts and raise exceptions on hard failures.
        """
        pass


class OllamaProvider(BaseLLMProvider):
    """Concrete implementation for local Ollama."""
    
    def generate_strategy(self, system_prompt: str, user_prompt: str) -> str:
        """Call Ollama /api/generate endpoint."""
        
        payload = {
            "model": self.config.model_name,
            "system": system_prompt,
            "prompt": user_prompt,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": self.config.temperature
            }
        }
        
        try:
            with httpx.Client(timeout=self.config.timeout_seconds) as client:
                response = client.post(self.config.endpoint_url, json=payload)
                response.raise_for_status()
                data = response.json()
                return data.get("response", "")
        except httpx.TimeoutException:
            logger.error("Ollama API timed out after %s seconds.", self.config.timeout_seconds)
            raise RuntimeError(f"LLM Provider Timeout ({self.config.timeout_seconds}s)")
        except httpx.RequestError as e:
            logger.error("Ollama API request failed: %s", e)
            raise RuntimeError(f"LLM Provider Request Failed: {str(e)}")
        except json.JSONDecodeError:
            logger.error("Failed to decode JSON response from Ollama API.")
            raise RuntimeError("LLM Provider returned invalid JSON in API envelope.")
