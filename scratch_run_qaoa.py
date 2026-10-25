import json
import requests

source = """OPENQASM 2.0;
include "qelib1.inc";

qreg q[4];
creg c[4];

h q[0];
h q[1];
h q[2];
h q[3];

cx q[0], q[1];
rz(0.45) q[1];
cx q[0], q[1];

cx q[1], q[2];
rz(0.45) q[2];
cx q[1], q[2];

rx(0.62) q[0];
rx(0.62) q[1];
rx(0.62) q[2];
rx(0.62) q[3];

measure q -> c;
"""

headers = {'Origin': 'http://127.0.0.1:8000', 'Content-Type': 'application/json'}
payload = {'source': source, 'shots': 1024, 'seed': 42}
r = requests.post('http://127.0.0.1:8000/api/simulate', json=payload, headers=headers)
print('Status:', r.status_code)
data = r.json()
print('Counts:', json.dumps(data.get('counts'), indent=2))
print('Duration ms:', data.get('duration_ms'))
print('Keys in data:', list(data.keys()))
if 'unitary' in data:
    print('Unitary dim:', len(data['unitary']))
