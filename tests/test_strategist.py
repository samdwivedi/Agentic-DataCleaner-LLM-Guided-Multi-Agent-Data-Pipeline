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
from agent.strategist.prompts import PROMPT_VERSION


class MockLLMProvider(BaseLLMProvider):
    """Mock provider to inject arbitrary strings for testing parser logic."""
    def __init__(self, responses: list[str], config=None):
        super().__init__(config or StrategistConfig())
        self.responses = responses
        self.call_count = 0
        self.last_system_prompt = None
        self.last_user_prompt = None
        
    def generate_strategy(self, system_prompt: str, user_prompt: str) -> str:
        self.last_system_prompt = system_prompt
        self.last_user_prompt = user_prompt
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


# ═══════════════════════════════════════════════════════════════════════════════
# 1. VALID STRATEGY
# ═══════════════════════════════════════════════════════════════════════════════


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


# ═══════════════════════════════════════════════════════════════════════════════
# 2. MALFORMED RESPONSE
# ═══════════════════════════════════════════════════════════════════════════════


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


def test_all_retries_exhausted_on_malformed(empty_reports):
    """When every retry returns garbage, we get error fallback."""
    mock_provider = MockLLMProvider(["not json"] * 3)
    config = StrategistConfig(max_retries=3)
    agent = StrategistAgent(config=config, provider=mock_provider)

    strategy = agent.generate_strategy(*empty_reports)
    assert strategy.status == "error"
    assert mock_provider.call_count == 3


# ═══════════════════════════════════════════════════════════════════════════════
# 3. UNKNOWN ACTION
# ═══════════════════════════════════════════════════════════════════════════════


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


# ═══════════════════════════════════════════════════════════════════════════════
# 4. UNKNOWN COLUMN (Pydantic accepts any string — caught downstream)
# ═══════════════════════════════════════════════════════════════════════════════


def test_unknown_column_accepted_by_strategist(empty_reports):
    """
    Pydantic treats 'column' as a free-form string, so a hallucinated column
    name passes the Strategist but should be caught by the downstream
    StrategyValidator (Phase 7).
    """
    hallucinated = json.dumps({
        "actions": [
            {
                "column": "nonexistent_hallucinated_col",
                "action": "median_imputation",
                "parameters": {},
                "reason": "made up",
                "confidence": 0.9
            }
        ]
    })

    mock_provider = MockLLMProvider([hallucinated])
    agent = StrategistAgent(provider=mock_provider)
    strategy = agent.generate_strategy(*empty_reports)

    # The strategist itself does NOT reject unknown columns — that is the
    # StrategyValidator's job.  We confirm the action parses successfully.
    assert strategy.status == "success"
    assert strategy.actions[0].column == "nonexistent_hallucinated_col"


# ═══════════════════════════════════════════════════════════════════════════════
# 5. UNAVAILABLE MODEL (connection refused)
# ═══════════════════════════════════════════════════════════════════════════════


def test_provider_network_error_fallback(empty_reports):
    """Test that provider runtime errors trigger immediate fallback (no tight loop)."""
    mock_provider = MockLLMProvider([RuntimeError("Connection Refused")])
    agent = StrategistAgent(provider=mock_provider)
    
    strategy = agent.generate_strategy(*empty_reports)
    assert strategy.status == "error"
    assert "Failed to generate valid strategy" in strategy.error_message
    assert mock_provider.call_count == 1


# ═══════════════════════════════════════════════════════════════════════════════
# 6. TIMEOUT
# ═══════════════════════════════════════════════════════════════════════════════


def test_timeout_triggers_fallback(empty_reports):
    """Explicit timeout error triggers immediate fallback, not a retry loop."""
    mock_provider = MockLLMProvider(
        [RuntimeError("LLM Provider Timeout (30.0s)")]
    )
    agent = StrategistAgent(provider=mock_provider)

    strategy = agent.generate_strategy(*empty_reports)
    assert strategy.status == "error"
    assert mock_provider.call_count == 1  # No tight-loop retry on timeout


# ═══════════════════════════════════════════════════════════════════════════════
# 7. INVALID CONFIDENCE
# ═══════════════════════════════════════════════════════════════════════════════


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


def test_negative_confidence_fails(empty_reports):
    """Test that confidence < 0 also fails Pydantic validation."""
    neg_conf = json.dumps({
        "actions": [
            {
                "column": "age",
                "action": "drop_column",
                "parameters": {},
                "reason": "bad",
                "confidence": -0.5
            }
        ]
    })

    mock_provider = MockLLMProvider([neg_conf])
    config = StrategistConfig(max_retries=1)
    agent = StrategistAgent(config=config, provider=mock_provider)

    strategy = agent.generate_strategy(*empty_reports)
    assert strategy.status == "error"


# ═══════════════════════════════════════════════════════════════════════════════
# 8. INCOMPLETE RESPONSE (missing required fields)
# ═══════════════════════════════════════════════════════════════════════════════


def test_incomplete_response_missing_reason(empty_reports):
    """LLM omits the required 'reason' field — Pydantic rejects it."""
    incomplete = json.dumps({
        "actions": [
            {
                "column": "age",
                "action": "median_imputation",
                "parameters": {},
                # "reason" is missing
                "confidence": 0.9
            }
        ]
    })

    mock_provider = MockLLMProvider([incomplete])
    config = StrategistConfig(max_retries=1)
    agent = StrategistAgent(config=config, provider=mock_provider)

    strategy = agent.generate_strategy(*empty_reports)
    assert strategy.status == "error"


def test_incomplete_response_missing_column(empty_reports):
    """LLM omits the required 'column' field."""
    incomplete = json.dumps({
        "actions": [
            {
                "action": "median_imputation",
                "parameters": {},
                "reason": "some reason",
                "confidence": 0.9
            }
        ]
    })

    mock_provider = MockLLMProvider([incomplete])
    config = StrategistConfig(max_retries=1)
    agent = StrategistAgent(config=config, provider=mock_provider)

    strategy = agent.generate_strategy(*empty_reports)
    assert strategy.status == "error"


# ═══════════════════════════════════════════════════════════════════════════════
# 9. PROMPT VERSIONING & USER CONFIG
# ═══════════════════════════════════════════════════════════════════════════════


def test_prompt_version_exists():
    """Ensure the PROMPT_VERSION constant is a non-empty semver-like string."""
    assert PROMPT_VERSION
    parts = PROMPT_VERSION.split(".")
    assert len(parts) == 3
    assert all(p.isdigit() for p in parts)


def test_user_config_injected_into_prompt(empty_reports):
    """When user_config is provided, it should appear in the user prompt."""
    valid_json = '{"actions": []}'
    mock_provider = MockLLMProvider([valid_json])
    agent = StrategistAgent(provider=mock_provider)

    user_cfg = {"prefer": "mode_imputation", "max_drop": 5}
    agent.generate_strategy(*empty_reports, user_config=user_cfg)

    assert "USER CONFIGURATION" in mock_provider.last_user_prompt
    assert "mode_imputation" in mock_provider.last_user_prompt


def test_no_user_config_omits_section(empty_reports):
    """When user_config is None, the user prompt should not contain the section."""
    valid_json = '{"actions": []}'
    mock_provider = MockLLMProvider([valid_json])
    agent = StrategistAgent(provider=mock_provider)

    agent.generate_strategy(*empty_reports)  # no user_config

    assert "USER CONFIGURATION" not in mock_provider.last_user_prompt

