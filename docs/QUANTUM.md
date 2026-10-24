# QORE-IR and Supported Quantum Subset

## 1. Supported Quantum Subset

QORE Phase 1 implements a strictly controlled subset of Qiskit Python programs. Arbitrary Python code is parsed via Python's `ast` module and walked through a restricted visitor allowlist. No user code is ever passed to `eval`, `exec`, or dynamic module loaders.

### 1.1 Supported Imports
- `from qiskit import QuantumCircuit`
- `import qiskit`
- `import math` / `from math import pi, tau, e`
- `import numpy` / `from numpy import pi, e`

### 1.2 Circuit Declarations
Programs must declare exactly one `QuantumCircuit` instance:
```python
from qiskit import QuantumCircuit

qc = QuantumCircuit(qubits, classical_bits)
```
- Maximum qubits: 10 (`MAX_QUBITS = 10`)
- Maximum classical bits: 10 (`MAX_CLBITS = 10`)
- Maximum operations: 500 (`MAX_OPERATIONS = 500`)
- Maximum source size: 32 KB (`MAX_SOURCE_BYTES = 32768`)

### 1.3 Supported Gates and Operations
Unitary gates supported in Phase 1:
- **1-qubit parameter-free:** `id` (`i`), `x`, `y`, `z`, `h`, `s`, `sdg`, `t`, `tdg`, `sx`, `sxdg`
- **1-qubit parameterized:** `rx(theta, q)`, `ry(theta, q)`, `rz(theta, q)`, `p(theta, q)`
- **1-qubit 3-parameter unitary:** `u(theta, phi, lam, q)`
- **2-qubit parameter-free:** `cx` (`cnot`), `cy`, `cz`, `ch`, `swap`, `ecr`
- **2-qubit parameterized:** `cp(theta, c, t)`, `crx`, `cry`, `crz`, `rxx`, `ryy`, `rzz`, `rzx`
- **3-qubit gates:** `ccx` (`toffoli`), `cswap`
- **Barriers:** `qc.barrier()` or `qc.barrier(0, 1)`
- **Measurements:** `qc.measure(qubit, clbit)` (strictly terminal; mid-circuit measurements and conditional reset are rejected)
- **Global phase assignment:** `qc.global_phase = float_val`

---

## 2. QORE-IR Specification (Version 1.0)

QORE-IR connects Studio (editor), Circuit Viewer (SVG visualizer), Lab (Aer simulator), Forge (transpiler/optimizer), and Research (provenance ledger) into an unambiguous shared intermediate representation.

### 2.1 Schema Definition
```json
{
  "version": "1.0",
  "num_qubits": 2,
  "num_clbits": 2,
  "global_phase": 0.0,
  "operations": [
    {
      "name": "h",
      "qubits": [0],
      "clbits": [],
      "params": []
    },
    {
      "name": "cx",
      "qubits": [0, 1],
      "clbits": [],
      "params": []
    },
    {
      "name": "measure",
      "qubits": [0],
      "clbits": [0],
      "params": []
    },
    {
      "name": "measure",
      "qubits": [1],
      "clbits": [1],
      "params": []
    }
  ]
}
```

### 2.2 Metrics Schema
Circuit resource metrics are computed directly from the canonical circuit representation:
- **gate_count**: Total unitary operations (measurements and barriers are strictly excluded).
- **depth**: Circuit depth computed via Qiskit's DAG (includes measurements, excludes barriers).
- **two_qubit_gate_count**: Unitary operations acting on exactly two qubits.
- **qubits / clbits**: Register counts.
- **measurement_count / barrier_count**: Tracked separately for full accountability.
- **gate_types**: Breakdown dictionary of unitary gates by type (e.g. `{"h": 1, "cx": 1}`).

---

## 3. Equivalence and Verification Model

QORE Forge optimizes circuits using standard Qiskit transpilation passes (`optimization_level = 0..3`). Verification evaluates semantic equivalence:

1. **Operator Equivalence (Unitary Portion):**
   For circuits with $\le 6$ qubits without mid-circuit measurements, QORE computes the full unitary operators $U_{\text{orig}}$ and $U_{\text{cand}}$ using `qiskit.quantum_info.Operator`.
   The Hilbert-Schmidt inner product normalized process fidelity is computed:
   $$F_{\text{process}} = \frac{|\operatorname{Tr}(U_{\text{orig}}^\dagger U_{\text{cand}})|^2}{d^2}$$
   where $d = 2^n$. The candidate is verified if $1 - F \le 10^{-9}$ and the global phase difference $\Delta\theta$ is bounded.

2. **Measurement Destination Invariance:**
   Every terminal measurement mapping $(q_i \to c_j)$ in the original circuit must match the candidate circuit identically. Reordered or missing measurement assignments cause validation to fail.
