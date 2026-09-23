from tests.test_e2e_pipeline import client
from unittest.mock import patch
import io
from agent.strategist.models import CleaningStrategy

d = 'id,age,category\n1,25.0,A\n2,,B\n3,30.0,X\n4,400.0,A\n5,35.0,\n6,26.0,B\n6,26.0,B\n8,,A\n9,29.0,Y\n10,31.0,B\n'
file_obj = io.BytesIO(d.encode('utf-8'))
res = client.post('/pipeline/upload', files={'file': ('dirty.csv', file_obj, 'text/csv')})
session_id = res.json()['session_id']
client.post(f'/pipeline/{session_id}/analyze')

def mock_strategy_fn(*args, **kwargs):
    return CleaningStrategy(actions=[{'column': 'age', 'action': 'median_imputation', 'parameters': {}, 'reason': 'x', 'confidence': 0.95}, {'column': 'id', 'action': 'remove_duplicates', 'parameters': {}, 'reason': 'x', 'confidence': 0.99}, {'column': 'age', 'action': 'cap_outliers', 'parameters': {}, 'reason': 'x', 'confidence': 0.90}])

with patch('agent.strategist.engine.StrategistAgent.generate_strategy', side_effect=mock_strategy_fn):
    res = client.post(f'/pipeline/{session_id}/strategy')
    print('Strategy Status:', res.status_code)
    print(res.json())
