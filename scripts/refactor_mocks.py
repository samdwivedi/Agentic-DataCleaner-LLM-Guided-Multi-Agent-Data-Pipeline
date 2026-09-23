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

replace_in_file("tests/test_e2e_pipeline.py", {
    'patch("agent.strategist.agent.': 'patch("app.agents.strategist.agent.',
    'patch("agent.strategy_validator.agent.': 'patch("app.agents.strategy_validator.agent.',
})
