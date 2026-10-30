# Qiskit compatibility

QORE reports its executable editor surface at `GET /api/capabilities`. The `installed_packages` field separately lists installed Qiskit distributions and versions. Installing a package does not enable its Python API in the editor.

The checked environment uses Qiskit 2.6.1 and Aer 0.18.0. The compatibility suite compares every advertised library gate class with Qiskit's actual operator, and reimports exports for every native gate. Passing these checks establishes the tested cases, not every API in every Qiskit version.

## Supported editor features

| Area | Current scope |
| --- | --- |
| Circuit construction | `QuantumCircuit`, `QuantumRegister`, `ClassicalRegister` through the bounded interpreter; reusable circuit fragments |
| Import forms | Direct imports, aliases, and qualified `qiskit.circuit` and `qiskit.circuit.library` namespaces |
| Native gates | 41 methods reported in `capabilities.gates`, with Qiskit's index broadcasting |
| Library gates | 60 classes reported in `capabilities.gate_classes`, including validated positional and keyword constructor arguments |
| Added composite classes | Identity, C3X, C3SX, C4X, RC3X, MCPhase, MCU1, GlobalPhase, QFT, XXMinusYY and XXPlusYY |
| Data-based gates | Pauli, diagonal, permutation, unitary matrices, Hamiltonian, state preparation, Pauli evolution and graph states |
| Circuit templates | Eleven classes/functions for RealAmplitudes, EfficientSU2, TwoLocal, NLocal / n_local, QFT and Pauli/ZZ feature maps |
| Parameters | `Parameter`, `ParameterVector`, arithmetic expressions and sequence/dictionary `assign_parameters` |
| Circuit and gate methods | Bounded composition, copy, inverse, control, power and circuit-to-gate conversion |
| Operator construction | `Pauli(label)` and `SparsePauliOp.from_list` for bounded evolution operators |
| Numeric data | Literal finite complex vectors/matrices and bounded `numpy.array`; at most 500 entries |
| Open controls | Supported through gate constructors, `mcx`, and native methods whose Qiskit signature accepts `ctrl_state` |
| Measurement | Terminal measurement and `measure_all(add_bits=False)` using sufficient existing classical bits |
| Simulation | Statevector, matrix product state and compatible stabilizer circuits through QORE settings |
| Compiler review | Qiskit preset compilation, numerical operator comparison up to six qubits and exact measurement mapping |
| OpenQASM | OpenQASM 2, Qiskit exporter gate spellings and bounded unitary gate definitions |

Composite gates and open controls lower to the supported `u`/`cx` representation before metrics, state analysis and execution. Lowering retains circuit global phase in QORE-IR. The expanded circuit must remain within 500 operations and the existing register limits. Gate count and depth therefore describe the lowered representation. Multi-controlled X gates also lower to noise-supported instructions before depolarizing errors are attached.

## Parameterized programs and fragments

The primary circuit is the variable `qc` when declared; otherwise it is the first constructed circuit. Additional named circuits are reusable fragments and do not silently replace it. The parse and simulation response identifies the choice in `selected_circuit`. An explicit assignment such as `qc = qc.inverse()` replaces that primary circuit with the returned circuit. Operations returning copies follow Qiskit's semantics: `qc.compose(fragment)` alone discards its result, while `qc = qc.compose(fragment)` or `qc.compose(fragment, inplace=True)` applies it.

Every parameter in the primary circuit must be bound before numerical parsing, simulation or compilation. Unbound parameters return `UNBOUND_PARAMETERS` with their names, rather than an invented result. Bind by parameter identity/name or Qiskit's parameter order with a sequence. An unused helper fragment may remain parameterized.

```python
from qiskit import QuantumCircuit
from qiskit.circuit.library import real_amplitudes

ansatz = real_amplitudes(2, reps=1)
bound = ansatz.assign_parameters([0.1, 0.2, 0.3, 0.4])
qc = QuantumCircuit(2, 2)
qc.compose(bound, inplace=True)
qc.measure_all(add_bits=False)
```

Factory dimensions, repetitions and options are validated before construction. Repetitions are capped at 20, numeric data at 500 entries and matrix-based powers at four qubits. Calls cannot provide custom synthesis or feature-map callbacks, disable unitary input validation or access arbitrary object methods. Functional factories such as `real_amplitudes`, `efficient_su2`, `n_local` and `zz_feature_map` are preferred; the corresponding older Qiskit 2 classes remain supported but emit upstream deprecation warnings.

`n_local` accepts named gates or supported gate objects, empty rotation/entanglement layers, and bounded named or explicit entanglement layouts. Its `overwrite_block_parameters` option follows Qiskit's semantics. The legacy `NLocal` constructor uses gate/circuit objects rather than named strings. Bind the returned circuit's parameters before running it:

```python
from qiskit.circuit.library import n_local

qc = n_local(2, ["ry", "rz"], "cx", reps=1)
qc.assign_parameters([0.25 for i in range(qc.num_parameters)], inplace=True)
qc.measure_all()
```

The adapter is checked against the installed SDK and the [official Qiskit n_local API](https://quantum.cloud.ibm.com/docs/en/api/qiskit/qiskit.circuit.library.n_local). Callbacks remain outside QORE's submitted-source contract.

`StatePreparation` is a unitary preparation gate, rather than reset-based `initialize`. Hamiltonian and Pauli evolution use Qiskit's circuit synthesis; this is not a claim that a default product formula exactly implements every noncommuting Hamiltonian. Check the actual synthesized circuit and its intended approximation before interpreting a research result.

OpenQASM 2 cannot represent circuit global phase. Reimported exports must preserve the unitary action up to global phase. Use QORE-IR or generated circuit Python when exact circuit phase metadata is required. Explicit user gate definitions retain their meaning even when named like standard gates. Includes are restricted to the built-in `qelib1.inc`; local files are unavailable.

## Example

```python
from qiskit.circuit import QuantumCircuit
from qiskit.circuit.library import QFTGate, CXGate, RXGate

qc = QuantumCircuit(3, 3)
qc.append(RXGate(theta=0.25), [0])
qc.append(CXGate(ctrl_state=0), [0, 1])
qc.append(QFTGate(3), [0, 1, 2])
qc.measure_all(add_bits=False)
```

## Installed SDKs and optional packages

The current offline import check passes for Qiskit, Aer, IBM Runtime, add-on utils, AQC tensor, cutting, MPF, OBP, SQD, mitigation and the QASM 3 importer. This checks importing their top-level modules only. It does not test every function, optional accelerator, external service or hardware job.

Provider clients, Runtime primitives, QASM 3 source, algorithm frameworks, unrestricted array manipulation, pulse programs, dynamic circuits and arbitrary Python remain outside the editor contract. A package can be available to separately maintained trusted Python programs while remaining unavailable to submitted editor source. QORE never falls back to `exec`, `eval`, package installation or host-shell execution to make unsupported source appear successful.

## Repeat the checks

```powershell
& .\.venv\Scripts\python.exe -m pytest backend/tests/test_qiskit_compatibility.py -q
& .\.venv\Scripts\python.exe scripts/check_qiskit_packages.py
```

The package checker runs imports in short-lived processes without forwarding provider credentials. It submits no model request or hardware job. Its report is `evidence/qiskit_package_check.json`. Run the full backend suite after changes to the interpreter or circuit normalization.

For upstream behavior, see [IBM's OpenQASM 2 interoperability guide](https://quantum.cloud.ibm.com/docs/en/guides/interoperate-qiskit-qasm2) and [Aer simulation methods](https://qiskit.github.io/qiskit-aer/stubs/qiskit_aer.AerSimulator.html).
