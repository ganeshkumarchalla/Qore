# QORE Phase 1 MVP — Final Engineering Report

**Product:** QORE (The Core of Quantum Development)  
**Version:** Phase 1 MVP (v0.1)  
**Date:** 2026-10-23  
**Status:** Verification Passed · Definition of Done Fulfilled  

---

## 1. Repository Assessment and Existing Functionality

When resuming work, the codebase had the structural layout established:
- `backend/qore/`: Core modules for quantum AST parsing, worker execution, FastAPI endpoints, and SQLite storage.
- `backend/tests/`: 72 automated tests spanning API validation, quantum transformations, runtime execution, and security boundaries.
- `frontend/`: React + TypeScript + Monaco setup with SVG circuit visualizer and analysis panels.
- `scripts/`: End-to-end acceptance script (`acceptance.py`) and startup script (`start.ps1`).

**Issues Identified and Resolved During Verification:**
1. **Pytest Setup Error on Windows (`test_security.py`):**
   A parameterized security test using a raw 32,768-byte comment string generated test node IDs exceeding Windows file/cache path constraints. Explicit parameter IDs (`ids=["large_source", "qubits_cap", "clbits_cap", "instructions_cap"]`) were added, resolving the error cleanly.
2. **Missing Frontend Stylesheet (`styles.css`):**
   `main.tsx` imported `./styles.css`, which had not been written. We created the full visual design stylesheet applying QORE's design tokens (`#080B14`, `#0B101C`, `#0F1523`, `#57D9FF`, `#9A83FF`), custom dark scrollbars, responsive breakpoints, metric cards, and charts.
3. **Static File Serving Mount Timing:**
   FastAPI was restarted after `frontend/dist` was built, ensuring `application.mount("/", StaticFiles(directory=dist, html=True))` successfully serves the application on `http://127.0.0.1:8000/`.

---

## 2. Features Implemented

The full Phase 1 specification was implemented across all 6 core functional modules:

1. **QORE Studio (Quantum Development Workspace):**
   - Monaco Editor with dark custom theme (`qore`), Python syntax highlighting, Cascadia Code font, line counter, and unsaved changes tracking.
   - Project lifecycle: Create, Open, Rename, Save, and Discard safety checks.
   - Example library: Bell state, Redundant Bell, GHZ state, Superposition, Quantum Teleportation.
   - Bounded Python AST parsing into QORE-IR with syntax/resource error reporting.

2. **QORE Circuit Viewer:**
   - SVG circuit diagram generated directly from QORE-IR.
   - Explicit rendering for 1-qubit gates, multi-controlled gates (`CX`, `CCX`), swap gates, barriers, and classical register measurement lines.
   - Circuit resource metrics: Unitary gate count, circuit depth, 2-qubit gate count, register sizes, and unitary gate distribution breakdown.

3. **QORE Lab (Real Local Simulation):**
   - Genuine local simulation using `qiskit_aer.AerSimulator`.
   - User-configurable shot count ($1 \le \text{shots} \le 100,000$) and deterministic random seed.
   - Dual-bar probability visualization comparing sampled empirical frequencies with theoretical statevector probabilities.
   - Total Variation Distance (TVD) calculation for empirical vs. theoretical reference distributions.
   - Classical bit ordering documentation (`c[n-1]...c[0]` little-endian notation).

4. **QORE Forge (Optimization & Equivalence Verification):**
   - Transpilation using Qiskit compiler optimization levels (0, 1, 2, 3).
   - Preserves original circuit while producing an independent candidate.
   - Side-by-side SVG circuit rendering and delta metric tables (absolute and percentage differences).
   - Equivalence verification using Hilbert-Schmidt operator process fidelity ($F \ge 1 - 10^{-9}$) and terminal measurement destination matching.
   - Explicit "Approve Candidate" workflow requiring manual confirmation before modifying source code.

5. **QORE Intelligence (Optional Grounded Assistant):**
   - Server-side optional integration with Google Gemini API (`gemini-2.5-flash`).
   - Grounded context injection (current source, simulation results, optimization differences).
   - Graceful fallback when credentials are not configured, leaving all quantum workflows completely operational.

6. **QORE Research (Reproducibility Ledger):**
   - Transactional SQLite ledger storing immutable experiment snapshots.
   - Stores source code, SHA-256 hash, QORE-IR version, simulator/compiler versions, shots, seed, metrics, validation results, and execution timestamps.
   - One-click experiment reopening and JSON export.

---

## 3. Actual Technology Stack

- **Backend:** Python 3.12.14, FastAPI 0.115.0, Pydantic 2.10.0, Starlette 0.45.0, Uvicorn 0.34.0, SQLite3.
- **Quantum Processing:** Qiskit 2.6.1, Qiskit Aer 0.18.0, NumPy 2.5.4.
- **Testing & Verification:** pytest 9.1.1, Playwright (Edge/Chromium).
- **Frontend:** React 18.3.1, TypeScript 5.9.3, Vite 5.4.21, Tailwind CSS 3.4.19, `@monaco-editor/react` 4.7.0, Monaco Editor 0.52.2.
- **Runtime Environment:** Windows 11 local workstation.

---

## 4. Architecture and QORE-IR Design

The architecture enforces strict separation of concerns across 4 distinct layers:
- **Presentation Layer:** SPA served via FastAPI static mount; communicates with backend via `/api/*` JSON contracts.
- **Application Layer:** Request validation, project state, orchestrating worker execution, and SQLite transactions.
- **Quantum Processing Layer:** Constrained AST interpretation, QORE-IR conversion, Aer simulation, Qiskit transpilation, and unitary operator verification.
- **Persistence Layer:** SQLite database (`data/qore.sqlite3`) with schema migrations for projects, execution runs, and immutable experiment snapshots.

**QORE-IR Design (v1.0):**
A strict JSON-serializable intermediate representation describing register widths, global phase, and ordered operations (`name`, `qubits`, `clbits`, `params`). Both frontend visualizers and backend transpilers consume and produce QORE-IR to guarantee identical interpretations.

---

## 5. Supported Source Constructs and Limitations

### Supported Constructs:
- Unitary gates: `id`, `x`, `y`, `z`, `h`, `s`, `sdg`, `t`, `tdg`, `sx`, `sxdg`, `rx`, `ry`, `rz`, `p`, `u`, `cx` (`cnot`), `cy`, `cz`, `ch`, `swap`, `ecr`, `cp`, `crx`, `cry`, `crz`, `rxx`, `ryy`, `rzz`, `rzx`, `ccx` (`toffoli`), `cswap`.
- Instructions: `qc.barrier(...)`, `qc.measure(q, c)`.
- Global phase: `qc.global_phase = float_val`.
- Simple finite `for` loops over `range(...)` or list literals (up to 500 statement steps).

### Intentional Constraints & Limitations:
- Maximum qubits: 10.
- Maximum classical bits: 10.
- Maximum operations: 500.
- Maximum source size: 32 KB.
- Unitary equivalence check limit: circuits with $\le 6$ qubits.
- Arbitrary Python syntax (function definitions, classes, file I/O, network calls, comprehensions, `eval`/`exec`, `import os/sys`) is rejected at parse time.
- Mid-circuit conditional reset and quantum feedback are not supported in Phase 1.

---

## 6. Setup and Execution Instructions

### Prerequisites:
- Python 3.11–3.13 (Python 3.12 tested).
- Node.js 20+ with Corepack enabled.

### Quick Start:
```powershell
# 1. Start backend and serve frontend:
.\scripts\start.ps1

# 2. Open browser:
http://127.0.0.1:8000
```

### Running Test Suite:
```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests
```

### Running End-to-End Acceptance:
```powershell
.\.venv\Scripts\python.exe scripts\acceptance.py --output evidence\acceptance.json
```

---

## 7. Actual Automated Test Results

Running `pytest` against `backend/tests`:
```
============================= test session starts =============================
platform win32 -- Python 3.12.14, pytest-9.1.1, pluggy-1.7.0
rootdir: c:\Users\ganes\OneDrive\QORE
configfile: pyproject.toml
plugins: anyio-4.15.1
collected 72 items

backend\tests\test_api.py ...........................                    [ 37%]
backend\tests\test_quantum.py .............                              [ 55%]
backend\tests\test_runtime.py ...                                        [ 59%]
backend\tests\test_security.py ............................              [100%]

======================= 72 passed, 1 warning in 23.85s ========================
```
All 72 tests passed cleanly.

---

## 8. Actual Bell-State Simulation Output

Executed with 1,024 shots and seed 42 on `qiskit_aer.AerSimulator`:
- **Observed Counts:**
  - `|00⟩`: 526 counts (51.37%)
  - `|11⟩`: 498 counts (48.63%)
  - `|01⟩`: 0 counts (0.00%)
  - `|10⟩`: 0 counts (0.00%)
  - **Total Shots:** 1,024
- **Ideal Reference Probabilities:**
  - `P(|00⟩) = 0.5000`
  - `P(|11⟩) = 0.5000`
- **Total Variation Distance (TVD):**
  $$\operatorname{TVD}(P_{\text{sim}}, P_{\text{ideal}}) = \frac{1}{2} (|0.51367 - 0.5| + |0.48633 - 0.5|) = 0.013671875$$
- **Bitstring Interpretation:** Output displayed in little-endian format `c[1]c[0]`.

---

## 9. Actual Optimization Comparison

### Test 1: Canonical Bell State (No Redundancy)
- **Compiler Pass:** Qiskit transpiler, optimization level 2, seed 42.
- **Gate Count:** Original: 2 $\to$ Candidate: 2 ($\Delta = 0$, 0.0%).
- **Depth:** Original: 3 $\to$ Candidate: 3 ($\Delta = 0$, 0.0%).
- **2-Qubit Gates:** Original: 1 $\to$ Candidate: 1 ($\Delta = 0$, 0.0%).
- **Reporting:** Honest zero-improvement reported in UI.

### Test 2: Redundant Bell State (`H-H-H`, `CX-CX-CX`)
- **Gate Count:** Original: 6 $\to$ Candidate: 2 ($\Delta = -4$, -66.67%).
- **Depth:** Original: 7 $\to$ Candidate: 3 ($\Delta = -4$, -57.14%).
- **2-Qubit Gates:** Original: 3 $\to$ Candidate: 1 ($\Delta = -2$, -66.67%).
- **Reporting:** Real compiler reduction displayed with green negative deltas.

---

## 10. Validation Method and Result

- **Method:** Full unitary operator comparison up to global phase, with exact terminal measurement mapping.
- **Process Fidelity:** $F_{\text{process}} = 1.0000000000$
- **Max Absolute Error:** $1.19166 \times 10^{-16}$
- **Tolerance Threshold:** $1.0 \times 10^{-9}$
- **Global Phase Difference:** $-6.12323 \times 10^{-17}$ rad
- **Terminal Measurement Destinations:**
  - Original: $[[0, 0], [1, 1]]$
  - Candidate: $[[0, 0], [1, 1]]$ (matched identically)
- **Status:** `validated`

---

## 11. Persistence and Experiment-Reopening Results

- Transactional SQLite ledger created at `data/qore.sqlite3`.
- An experiment snapshot was created from the verified Bell-state run (`id = exp-3ee44053e198`).
- The experiment was reopened via GET `/api/experiments/{id}`.
- All fields (source code, SHA-256 hash `d31a55...`, QORE-IR operations, simulation counts `{"00": 526, "11": 498}`, compiler differences, validation metrics, and timestamps) matched identically (`reopened_identical == true`).

---

## 12. Security Measures and Remaining Limitations

### Implemented Measures:
1. **Constrained AST Interpreter:** Source is walked via an AST visitor with a strict allowlist. Python builtins, file I/O, `import`, `eval`, `exec`, and attribute navigation (`__class__`, `__globals__`) are rejected before execution.
2. **Worker Process Isolation:** Simulations and optimizations execute inside short-lived subprocess workers with timeout enforcement (30 seconds) and concurrency caps (max 2 jobs).
3. **Hard Resource Limits:** Maximum 32 KB source, 10 qubits, 10 classical bits, 500 operations, 100,000 shots.
4. **Credential Isolation:** AI API keys remain exclusively server-side in environment variables and are never sent to the browser.

### Remaining Limitations:
- Single-host local deployment only; does not provide OS-level cgroups or Docker containerization for worker processes.
- Unitary equivalence check is limited to $\le 6$ qubits due to $2^n \times 2^n$ matrix dimensionality.

---

## 13. Known Bugs and Unfinished Features

- None in Phase 1 scope. All acceptance tests, end-to-end API workflows, and browser rendering paths pass without errors or regressions.

---

## 14. Screenshots of the Running Application

The following high-resolution screenshots were captured from the live application using Playwright in Edge and saved to the `evidence/` directory:

| Screenshot | Description | File Path |
| --- | --- | --- |
| **01 Studio** | Monaco editor with Bell source, QORE-IR 1.0 SVG circuit, and live metric cards | [`evidence/01_studio.png`](file:///c:/Users/ganes/OneDrive/QORE/evidence/01_studio.png) |
| **02 Lab** | Measured distribution (526 for 00, 498 for 11), ideal probability bars, TVD, and little-endian notes | [`evidence/02_lab_simulation.png`](file:///c:/Users/ganes/OneDrive/QORE/evidence/02_lab_simulation.png) |
| **03 Forge** | Side-by-side original and candidate circuits, measured metric changes, and verification evidence | [`evidence/03_forge_optimization.png`](file:///c:/Users/ganes/OneDrive/QORE/evidence/03_forge_optimization.png) |
| **04 Research** | Immutable experiment ledger, SHA-256 hash, dependency versions, and historical provenance | [`evidence/04_research_ledger.png`](file:///c:/Users/ganes/OneDrive/QORE/evidence/04_research_ledger.png) |
| **05 Intelligence** | Grounded AI assistant interface with context indicators and provider status | [`evidence/05_intelligence.png`](file:///c:/Users/ganes/OneDrive/QORE/evidence/05_intelligence.png) |

---

## 15. Recommended Next Engineering Priorities (Horizon 2)

1. **Hardware Provider Connectors:** Add adapter interface for IBM Quantum / Braket QPU submission.
2. **Clifford / Stabilizer Simulation:** Add support for polynomial-time Clifford circuit simulation (>100 qubits).
3. **Noise Modeling:** Add configurable decoherence ($T_1$, $T_2$) and depolarizing gate noise models in QORE Lab.
4. **OpenQASM 3.0 Export/Import:** Allow bi-directional translation between QORE-IR and OpenQASM 3.0.
5. **Interactive Circuit Canvas:** Enable interactive drag-and-drop gate placement synchronized two-way with Monaco editor code.
