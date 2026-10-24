# Phase 1 acceptance coverage

The automated tests execute the installed Qiskit/Aer engine, FastAPI application, and a temporary SQLite database. Compiler, simulation, and persistence results are not mocked. This document is a coverage guide; the final engineering report records the commands and outcomes that were actually executed.

| Requirement | Automated evidence |
| --- | --- |
| QORE-IR version, gate order, control/target and classical mapping | `backend/tests/test_quantum.py` |
| Metric definitions, counts and actual compiler differences | `backend/tests/test_quantum.py` |
| Bell-state samples, seeded repeatability, exact shot totals, theoretical probabilities and calculated TVD | `backend/tests/test_quantum.py` |
| Little-endian output labels and swapped classical mapping | `backend/tests/test_quantum.py` |
| Original circuit preserved; real simplification; honest zero improvement | `backend/tests/test_quantum.py` |
| Full-operator comparison, global phase, incorrect transformation, mapping mismatch and size limit | `backend/tests/test_quantum.py` |
| Arbitrary imports/calls, attribute traversal, file access, comprehensions, unsupported constructs and malformed source rejected | `backend/tests/test_security.py` |
| Source, register, instruction and shot caps | `backend/tests/test_security.py` and `backend/tests/test_api.py` |
| Project create, rename, save, open and list | `backend/tests/test_api.py` |
| Bell parse → simulate → optimize → validate → save → reopen | `backend/tests/test_api.py` |
| Immutable historical snapshots after project edits and application restart | `backend/tests/test_api.py` |
| Source hash mismatch, unknown references and incorrect run kinds rejected | `backend/tests/test_api.py` |
| Structured HTTP errors, recovery after a failed run and optional AI unavailable | `backend/tests/test_api.py` |

## Browser acceptance procedure

Run the backend and frontend using the repository setup instructions. In the running application:

1. Open the Bell-state example and inspect editable, highlighted source.
2. Parse and verify that the SVG shows H on q0, CX from q0 to q1, and the measurement/classical connections from the returned IR.
3. Run the simulator with 1,024 shots and seed 42. Confirm counts total 1,024, only 00/11 occur, and theoretical values are visibly distinguished from sampled probabilities.
4. Optimize and inspect separate original/candidate diagrams, actual metrics, settings and validation evidence. Confirm that the editor still contains the original source.
5. Save an experiment, edit the source, and reopen the saved experiment. Confirm the historical label, original source, run configuration, counts and compiler evidence are restored.
6. Edit the source again and confirm live results are cleared. Run again and confirm new execution replaces the historical context.
7. Make an unsaved edit and switch projects. Confirm the discard decision is explicit.
8. Use the redundant-gates example to verify an actual simplification. Approve the candidate explicitly and confirm that the optimization snapshot retains the original.
9. Trigger invalid syntax and confirm the error is visible, then correct it and run successfully.
10. Open Intelligence without configured credentials and confirm the unavailable state leaves the core workflow usable.
11. Check a narrow viewport and keyboard navigation. Record screenshots of the working application.

Passing API tests alone does not establish that these browser steps have passed. Browser outcomes and any unverified steps must be reported separately.
