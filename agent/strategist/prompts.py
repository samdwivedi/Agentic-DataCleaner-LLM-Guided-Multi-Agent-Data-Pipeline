"""
Strategist Prompts
──────────────────
Versioned prompts directing the LLM to output ONLY structured JSON and
restricting actions to the predefined registry.

Prompt versioning
-----------------
Every system prompt embeds a ``PROMPT_VERSION`` string.  When the prompt
wording changes, bump the version so that logged LLM outputs can be
correlated to the exact instruction set that produced them.
"""

from agent.strategist.models import ActionRegistry

# ── Prompt Version ────────────────────────────────────────────────────────────
# Bump this whenever the system prompt text is modified.
PROMPT_VERSION = "1.0.0"

_ALLOWED_ACTIONS_STR = ", ".join([f"'{a.value}'" for a in ActionRegistry])

STRATEGIST_SYSTEM_PROMPT = f"""You are a Data Cleaning Strategist Agent.  (prompt v{PROMPT_VERSION})
Your job is to analyze data profiling, schema validation, and anomaly reports to recommend data cleaning actions.

CRITICAL INSTRUCTIONS:
1. You MUST output ONLY valid JSON.
2. Do NOT output Markdown formatting like ```json or any conversational text.
3. Do NOT generate Python code, SQL, or execute commands.
4. Do NOT modify files, modify Pandas DataFrames, or directly insert values.
5. Do NOT invent column names — use ONLY column names that appear in the reports.
6. You MUST select 'action' ONLY from this allowed registry: [{_ALLOWED_ACTIONS_STR}].
7. Do NOT generate executable SQL or executable code of any kind.
8. The 'confidence' field MUST be a float between 0.0 and 1.0 inclusive.

The output JSON MUST strictly follow this schema:
{{
  "actions": [
    {{
      "column": "column_name",
      "action": "one_of_allowed_actions",
      "parameters": {{}},
      "reason": "Why you chose this action.",
      "confidence": 0.95
    }}
  ]
}}

Reason carefully based on missing values, type mismatches, and anomalies.
If no columns require cleaning, return an empty "actions" list.
"""


def build_strategist_prompt(
    profiler_json: str,
    schema_json: str,
    anomaly_json: str,
    user_config_json: str | None = None,
) -> str:
    """Combines reports (and optional user config) into the user prompt payload."""
    sections = f"""
Analyze the following reports and propose a CleaningStrategy.

=== PROFILER REPORT ===
{profiler_json}

=== SCHEMA VALIDATION REPORT ===
{schema_json}

=== ANOMALY REPORT ===
{anomaly_json}
"""
    if user_config_json:
        sections += f"""
=== USER CONFIGURATION ===
{user_config_json}
"""
    return sections

