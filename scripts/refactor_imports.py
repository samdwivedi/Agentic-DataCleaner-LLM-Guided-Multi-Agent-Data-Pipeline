import os

replacements = {
    "from agent.profiler.models": "from app.models.profiler",
    "from agent.anomaly.models": "from app.models.anomaly",
    "from agent.validator.models": "from app.models.schema",
    "from agent.strategist.models": "from app.models.strategy",
    "from agent.strategy_validator.models": "from app.models.strategy_validator",
    "from agent.quality.models": "from app.models.quality",
    "from agent.executor.models": "from app.models.execution",
    
    "from agent.profiler": "from app.agents.profiler",
    "from agent.anomaly": "from app.agents.anomaly_detector",
    "from agent.validator": "from app.agents.schema_validator",
    "from agent.strategist": "from app.agents.strategist",
    "from agent.strategy_validator": "from app.agents.strategy_validator",
    "from agent.quality": "from app.agents.validator",
    "from agent.executor": "from app.agents.executor",
    
    "from app.agents.strategist.providers": "from app.llm.providers",
    "from agent.strategist.providers": "from app.llm.providers",
    
    "from app.agents.executor.operations": "from app.operations.operations",
    "from agent.executor.operations": "from app.operations.operations",
    
    "from agent.logger": "from app.config.logging",
}

def replace_in_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    modified = content
    for old, new in replacements.items():
        modified = modified.replace(old, new)
        
    if modified != content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(modified)
        print(f"Updated {filepath}")

for root, dirs, files in os.walk("backend/app"):
    for file in files:
        if file.endswith(".py"):
            replace_in_file(os.path.join(root, file))
            
for root, dirs, files in os.walk("tests"):
    for file in files:
        if file.endswith(".py"):
            replace_in_file(os.path.join(root, file))

