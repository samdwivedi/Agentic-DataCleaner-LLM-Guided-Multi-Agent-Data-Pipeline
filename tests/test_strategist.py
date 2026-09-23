"""
Comprehensive unit tests for the Phase 6 LLM Strategist Agent.

Run with:
    pytest tests/test_strategist.py -v
"""

from __future__ import annotations

import json
import pytest
from unittest.mock import MagicMock

from pydantic import ValidationError

from agent.strategist import (
    StrategistAgent,
    StrategistConfig,
    CleaningStrategy,
    CleaningAction,
    ActionRegistry,
)
from agent.strategist.providers import BaseLLMProvider


class MockLLMProvider(BaseLLMProvider):
    """Mock provider to inject arbitrary strings for testing parser logic."""
    def __init__(self, responses: list[str], config=None):
        super().__init__(config or StrategistConfig())
        self.responses = responses
        self.call_count = 0
        
    def generate_strategy(self, system_prompt: str, user_prompt: str) -> str:
        if self.call_count >= len(self.responses):
            raise RuntimeError("Mock provider ran out of configured responses.")
        response = self.responses[self.call_count]
        self.call_count += 1
        
        if isinstance(response, Exception):
            raise response
        return response


@pytest.fixture
def empty_reports():
    return {"dummy": "profiler"}, {"dummy": "schema"}, {"dummy": "anomaly"}


def test_valid_strategy(empty_reports):
    """Test standard JSON parsing and Pydantic validation."""
    valid_json = json.dumps({
        "actions": [
            {
                "column": "age",
                "action": "median_imputation",
                "parameters": {},
                "reason": "missing values",
                "confidence": 0.95
            }
        ]
    })
    
    mock_provider = MockLLMProvider([valid_json])
    agent = StrategistAgent(provider=mock_provider)
    
    strategy = agent.generate_strategy(*empty_reports)
    assert strategy.status == "success"
    assert len(strategy.actions) == 1
    assert strategy.actions[0].column == "age"
    assert strategy.actions[0].action == ActionRegistry.MEDIAN_IMPUTATION


def test_markdown_json_stripping(empty_reports):
    """Test that markdown ```json tags are stripped."""
    markdown_json = "```json\n" + json.dumps({
        "actions": []
    }) + "\n```"
    
    mock_provider = MockLLMProvider([markdown_json])
    agent = StrategistAgent(provider=mock_provider)
    
    strategy = agent.generate_strategy(*empty_reports)
    assert strategy.status == "success"


def test_malformed_json_retries(empty_reports):
    """Test that malformed JSON triggers retries until success."""
    malformed1 = "{ missing quotes }"
    malformed2 = '{"actions": [{"column": "age"' # incomplete
    valid_json = '{"actions": []}'
    
    mock_provider = MockLLMProvider([malformed1, malformed2, valid_json])
    config = StrategistConfig(max_retries=3)
    agent = StrategistAgent(config=config, provider=mock_provider)
    
    strategy = agent.generate_strategy(*empty_reports)
    assert strategy.status == "success"
    assert mock_provider.call_count == 3


def test_invalid_action_retries(empty_reports):
    """Test that an unknown action fails Pydantic validation and retries."""
    invalid_action = json.dumps({
        "actions": [
            {
                "column": "age",
                "action": "invent_column_magic", # Not in ActionRegistry
                "parameters": {},
                "reason": "missing values",
                "confidence": 0.95
            }
        ]
    })
    valid_json = '{"actions": []}'
    
    mock_provider = MockLLMProvider([invalid_action, valid_json])
    config = StrategistConfig(max_retries=2)
    agent = StrategistAgent(config=config, provider=mock_provider)
    
    strategy = agent.generate_strategy(*empty_reports)
    assert strategy.status == "success"
    assert mock_provider.call_count == 2


def test_invalid_confidence_retries(empty_reports):
    """Test that confidence > 1 fails validation."""
    invalid_conf = json.dumps({
        "actions": [
            {
                "column": "age",
                "action": "drop_column",
                "parameters": {},
                "reason": "missing values",
                "confidence": 1.5 # Invalid
            }
        ]
    })
    
    mock_provider = MockLLMProvider([invalid_conf] * 3) # Fails 3 times
    config = StrategistConfig(max_retries=3)
    agent = StrategistAgent(config=config, provider=mock_provider)
    
    strategy = agent.generate_strategy(*empty_reports)
    # Exceeds max retries, should fallback
    assert strategy.status == "error"
    assert mock_provider.call_count == 3


def test_provider_network_error_fallback(empty_reports):
    """Test that provider runtime errors trigger immediate fallback (no tight loop)."""
    mock_provider = MockLLMProvider([RuntimeError("Connection Refused")])
    agent = StrategistAgent(provider=mock_provider)
    
    strategy = agent.generate_strategy(*empty_reports)
    assert strategy.status == "error"
    assert "Failed to generate valid strategy" in strategy.error_message
    assert mock_provider.call_count == 1
