import os

def replace_in_file(filepath, replacements):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    modified = content
    for old, new in replacements.items():
        modified = modified.replace(old, new)
        
    if modified != content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(modified)
        print(f"Updated {filepath}")

replace_in_file("tests/test_executor.py", {
    "from app.agents.executor import ExecutorAgent, ExecutionResult, ExecutionLogEntry, ExecutionStatus": "from app.agents.executor.agent import ExecutorAgent\nfrom app.models.execution import ExecutionResult, ExecutionLogEntry, ExecutionStatus"
})

replace_in_file("tests/test_strategist.py", {
    "from app.agents.strategist import (": "from app.agents.strategist.agent import StrategistAgent\nfrom app.models.strategy import (\n    StrategistConfig,",
    "    StrategistAgent,\n    StrategistConfig,": " "
})
