# Supported circuit language

QORE accepts OpenQASM 2 and a deliberately constrained Qiskit-style Python subset. It parses structure instead of executing arbitrary Python. Supported programs construct `QuantumCircuit`, apply documented gates, add barriers, and perform terminal measurement. Circuit aliases, register sizes, indices, numeric parameters, and bounded loops must be statically understandable.

Imports outside the allowlist, file access, networking, subprocesses, reflection, dynamic evaluation, arbitrary function calls, and operating-system APIs are rejected. Installing an SDK does not expand the public editor language. This boundary keeps the circuit surface reviewable and makes resource limits enforceable.

QORE supports up to 10 qubits, 10 classical bits, 500 operations, and 32 KiB of UTF-8 source. Measurement must be terminal for the current ideal-state and equivalence workflows. Dynamic classical control and mid-circuit measurement are outside the Phase 1 contract.

OpenQASM bitstrings follow the recorded classical mapping. Never infer qubit order from visual position alone; read the result's bit-ordering field. For portable experiments, specify shots, seed, method, noise parameters, and source exactly, then preserve the run in Ledger.
