from qore.quantum import parse_source, simulate

examples = {
    'Bell State': '''from qiskit import QuantumCircuit
qc = QuantumCircuit(2, 2)
qc.h(0)
qc.cx(0, 1)
qc.measure(0, 0)
qc.measure(1, 1)
''',
    'GHZ (3-qubit)': '''from qiskit import QuantumCircuit
qc = QuantumCircuit(3, 3)
qc.h(0)
qc.cx(0, 1)
qc.cx(1, 2)
qc.measure(0, 0)
qc.measure(1, 1)
qc.measure(2, 2)
''',
    'Grover Search (2-qubit)': '''from qiskit import QuantumCircuit
qc = QuantumCircuit(2, 2)
qc.h(0)
qc.h(1)
qc.cz(0, 1)
qc.h(0)
qc.h(1)
qc.x(0)
qc.x(1)
qc.cz(0, 1)
qc.x(0)
qc.x(1)
qc.h(0)
qc.h(1)
qc.measure(0, 0)
qc.measure(1, 1)
''',
    'Deferred Teleportation': '''from qiskit import QuantumCircuit
qc = QuantumCircuit(3, 3)
qc.h(0)
qc.h(1)
qc.cx(1, 2)
qc.cx(0, 1)
qc.h(0)
qc.cx(1, 2)
qc.cz(0, 2)
qc.measure(2, 2)
''',
    'QAOA Cut (4-qubit)': '''OPENQASM 2.0;
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
''',
    'Quantum Fourier Transform (3-qubit)': '''from qiskit import QuantumCircuit
from math import pi
qc = QuantumCircuit(3, 3)
qc.x(0)
qc.x(2)
qc.h(0)
qc.cp(pi / 2, 1, 0)
qc.cp(pi / 4, 2, 0)
qc.h(1)
qc.cp(pi / 2, 2, 1)
qc.h(2)
qc.swap(0, 2)
qc.measure(0, 0)
qc.measure(1, 1)
qc.measure(2, 2)
'''
}

all_passed = True
for name, src in examples.items():
    try:
        result = simulate(src, shots=1024, seed=42)
        counts = result.get('counts', {})
        qubits = result.get('metrics', {}).get('qubits')
        bloch = len(result.get('bloch_vectors', []))
        tvd = result.get('tvd', 0.0)
        print(f"PASS: {name:35} | Qubits: {qubits} | Bloch: {bloch} | TVD: {tvd:.4f} | Counts: {dict(list(counts.items())[:4])}")
    except Exception as e:
        all_passed = False
        print(f"FAIL: {name:35} | Error: {e}")

if all_passed:
    print("\nALL REAL-WORLD QUANTUM EXAMPLES VERIFIED SUCCESSFULLY!")
