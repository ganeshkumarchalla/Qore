import httpx

# 1. Test direct OpenQASM
qasm_code = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
cx q[0], q[1];
measure q[0] -> c[0];
measure q[1] -> c[1];
"""
r1 = httpx.post("http://127.0.0.1:8000/api/simulate", json={"source": qasm_code, "shots": 500, "seed": 42})
print("Test 1 (Direct OpenQASM): Status =", r1.status_code, "Counts =", r1.json().get("counts"))

# 2. Test main guard, wildcard import, print, register measurement, broadcasting
code2 = """from qiskit import *
import numpy as np

if __name__ == '__main__':
    qr = QuantumRegister(2)
    cr = ClassicalRegister(2)
    qc = QuantumCircuit(qr, cr)
    qc.h([0, 1])
    qc.cx(0, 1)
    print("Testing print statements and circuit inspection:")
    qc.draw()
    qc.measure(qr, cr)
"""
r2 = httpx.post("http://127.0.0.1:8000/api/simulate", json={"source": code2, "shots": 500, "seed": 42})
print("Test 2 (Wildcard + main guard + registers + print): Status =", r2.status_code, "Counts =", r2.json().get("counts"))

# 3. Test noise and readout error and MPS method
r3 = httpx.post("http://127.0.0.1:8000/api/simulate", json={
    "source": qasm_code,
    "shots": 1000,
    "seed": 42,
    "noise_rate": 0.03,
    "readout_error": 0.02,
    "method": "matrix_product_state"
})
print("Test 3 (Hardware noise + MPS): Status =", r3.status_code, "Counts =", r3.json().get("counts"))
