"""Production-grade test suite covering real-world quantum algorithms and optimizations.

Tests:
1. 4-qubit GHZ state entanglement
2. 3-qubit Grover's Search Algorithm (marking |101>)
3. 3-qubit Quantum Fourier Transform (QFT) with Level-2 compiler equivalence
4. Parameterized VQE ansatz with multi-axis rotations
5. Realistic hardware noise model with Matrix Product State (MPS) simulator
"""

import pytest
import numpy as np


def test_ghz_4qubit_simulation(client):
    source = """from qiskit import QuantumCircuit
qc = QuantumCircuit(4, 4)
qc.h(0)
qc.cx(0, 1)
qc.cx(1, 2)
qc.cx(2, 3)
qc.measure([0, 1, 2, 3], [0, 1, 2, 3])
"""
    res = client.post("/api/simulate", json={"source": source, "shots": 2048, "seed": 100})
    assert res.status_code == 200, res.text
    data = res.json()
    counts = data["counts"]
    assert set(counts.keys()).issubset({"0000", "1111"})
    assert counts.get("0000", 0) > 800
    assert counts.get("1111", 0) > 800


def test_grover_3qubit_search(client):
    source = """from qiskit import QuantumCircuit
qc = QuantumCircuit(3, 3)
# Superposition
qc.h(0)
qc.h(1)
qc.h(2)

# Oracle for |101>
qc.x(1)
qc.h(2)
qc.ccx(0, 1, 2)
qc.h(2)
qc.x(1)

# Diffuser
qc.h(0)
qc.h(1)
qc.h(2)
qc.x(0)
qc.x(1)
qc.x(2)
qc.h(2)
qc.ccx(0, 1, 2)
qc.h(2)
qc.x(0)
qc.x(1)
qc.x(2)
qc.h(0)
qc.h(1)
qc.h(2)

qc.measure([0, 1, 2], [0, 1, 2])
"""
    res = client.post("/api/simulate", json={"source": source, "shots": 2048, "seed": 42})
    assert res.status_code == 200, res.text
    counts = res.json()["counts"]
    top_state = max(counts, key=counts.get)
    assert top_state == "101"
    assert counts["101"] > 1400


def test_qft_3qubit_and_optimization_equivalence(client):
    source = """from qiskit import QuantumCircuit
import numpy as np

qc = QuantumCircuit(3, 3)
qc.x(0)
qc.h(2)
qc.cp(np.pi / 2, 1, 2)
qc.cp(np.pi / 4, 0, 2)
qc.h(1)
qc.cp(np.pi / 2, 0, 1)
qc.h(0)
qc.swap(0, 2)
qc.measure([0, 1, 2], [0, 1, 2])
"""
    res = client.post("/api/simulate", json={"source": source, "shots": 1024, "seed": 42})
    assert res.status_code == 200, res.text

    opt_res = client.post("/api/optimize", json={"source": source, "level": 2, "seed": 42})
    assert opt_res.status_code == 200, opt_res.text
    opt_data = opt_res.json()
    assert opt_data["validation"]["status"] == "validated"


def test_vqe_ansatz_simulation(client):
    source = """from qiskit import QuantumCircuit
import numpy as np

qc = QuantumCircuit(2, 2)
theta1 = np.pi / 4
theta2 = np.pi / 3
phi = np.pi / 6

qc.ry(theta1, 0)
qc.rz(phi, 0)
qc.ry(theta2, 1)
qc.cx(0, 1)
qc.rx(phi, 1)
qc.measure([0, 1], [0, 1])
"""
    res = client.post("/api/simulate", json={"source": source, "shots": 1000, "seed": 42})
    assert res.status_code == 200, res.text
    data = res.json()
    assert sum(data["counts"].values()) == 1000
    assert data["tvd"] is not None


def test_noisy_mps_channel_simulation(client):
    source = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
cx q[0], q[1];
measure q[0] -> c[0];
measure q[1] -> c[1];
"""
    res = client.post("/api/simulate", json={
        "source": source,
        "shots": 2000,
        "seed": 42,
        "noise_rate": 0.05,
        "readout_error": 0.03,
        "method": "matrix_product_state"
    })
    assert res.status_code == 200, res.text
    counts = res.json()["counts"]
    noise_count = counts.get("01", 0) + counts.get("10", 0)
    assert noise_count > 0
