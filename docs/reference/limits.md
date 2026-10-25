# Runtime limits and compatibility

| Limit | Value |
| --- | ---: |
| Source | 32 KiB UTF-8 |
| Request body | 96 KiB |
| Qubits / classical bits | 10 / 10 |
| Operations | 500 |
| Shots | 1–100,000 |
| Worker timeout | 30 seconds |
| Concurrent quantum jobs | 2 per process |
| Operator equivalence | Up to 6 qubits |
| Matrix display | Up to 4 qubits |
| Ideal amplitudes and Bloch data | Up to 6 qubits |

Limits protect responsiveness; they do not predict performance exactly. Simulation cost depends on method, circuit structure, entanglement, noise, and native-library behavior. A circuit below every numeric cap can still time out. Multiple replicas need shared admission control to enforce global budgets.

QORE supports bounded Aer simulation and transpiler analysis. It does not promise arbitrary Qiskit compatibility, external service authentication, cloud hardware submission, pulse scheduling, unrestricted Python, or a real shell. Unsupported capability must return an explicit error rather than silently changing semantics.
