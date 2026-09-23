import os

replacements = {
    ".engine": ".agent",
    "import engine": "import agent",
    "from engine import": "from .agent import",
    "from app.agents.profiler.engine": "from app.agents.profiler.agent",
    "from app.agents.anomaly_detector.engine": "from app.agents.anomaly_detector.agent",
    "from app.agents.schema_validator.engine": "from app.agents.schema_validator.agent",
    "from app.agents.strategist.engine": "from app.agents.strategist.agent",
    "from app.agents.strategy_validator.engine": "from app.agents.strategy_validator.agent",
    "from app.agents.executor.engine": "from app.agents.executor.agent",
    "from app.agents.validator.engine": "from app.agents.validator.agent",
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
