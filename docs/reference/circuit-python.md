# Supported circuit language

QORE accepts OpenQASM 2 and a deliberately constrained Qiskit-style Python subset. It parses structure instead of executing arbitrary Python. Supported programs construct `QuantumCircuit`, apply documented gates, add barriers, and perform terminal measurement. Circuit aliases, register sizes, indices, numeric parameters, and bounded loops must be statically understandable.

Imports outside the allowlist, file access, networking, subprocesses, reflection, dynamic evaluation, arbitrary function calls, and operating-system APIs are rejected. Installing an SDK does not expand the public editor language. This boundary keeps the circuit surface reviewable and makes resource limits enforceable.

QORE supports up to 10 qubits, 10 classical bits, 500 operations, and 32 KiB of UTF-8 source. Measurement must be terminal for the current ideal-state and equivalence workflows. Dynamic classical control and mid-circuit measurement are outside the Phase 1 contract.

The executable gate catalog is available from `GET /api/capabilities` and from the integrated terminal with `qiskit gates`. The current native set includes identity, Pauli, Hadamard, phase, square-root, arbitrary single-qubit rotations, controlled rotations/phases, interaction rotations, SWAP-family gates, controlled-S/controlled-S-dagger, controlled-U, Toffoli, controlled-Z on three qubits, relative-phase Toffoli, and Fredkin. Use `qiskit modules`, `qiskit methods`, and `qiskit limits` for the exact runtime contract installed on the server.

“Qiskit support” means compatible circuit construction inside this declared subset. QORE does not claim that every Qiskit package, algorithm class, provider client, pulse program, primitive, dynamic circuit, arbitrary Python program, or future SDK API can run unchanged. Unsupported code returns an explicit compatibility error rather than being pretended successful.

Qualified imports and aliases for `qiskit.circuit` and `qiskit.circuit.library` are supported. Gate constructors validate keyword arguments, including numeric parameters, labels and `ctrl_state`. Native gate methods use Qiskit's broadcasting semantics after index validation. `measure_all(add_bits=False)` reuses sufficient existing classical bits. Unknown keywords and unsupported operators are errors rather than ignored instructions.

Composite library gates such as `QFTGate`, multi-controlled phase gates and open-controlled gates lower to bounded `u`/`cx` instructions before metrics and numerical analysis. Global phase is retained in QORE-IR, and expanded operations count toward the 500-operation limit. See the [Qiskit compatibility matrix](qiskit-compatibility.md) for tested classes, package inventory, examples and verification commands.

Programs may create reusable circuit fragments and supported variational or feature-map templates. The primary output is `qc` when declared, otherwise the first constructed circuit; parse results expose `selected_circuit`. Parameters and parameter vectors support basic arithmetic and explicit binding with `assign_parameters`. The primary circuit must be fully bound before numerical execution. `compose`, `copy`, `inverse`, `control`, `power` and `to_gate` have bounded adapters with Qiskit's copy-versus-in-place semantics. Literal numeric vectors/matrices and bounded `numpy.array` are available for data-based unitary gates. Provider calls, arbitrary object methods, custom callbacks and unrestricted NumPy remain unavailable.

OpenQASM bitstrings follow the recorded classical mapping. Never infer qubit order from visual position alone; read the result's bit-ordering field. For portable experiments, specify shots, seed, method, noise parameters, and source exactly, then preserve the run in Ledger.
