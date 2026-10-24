# QORE Frontend Architecture & Multi-Agent UI Guidelines

This document defines the architectural standards, UI reliability rules, and collaborative protocols established by the **Frontend Autonomous Bug Resolver & UI Healer**.

All subagents, automated sidecars, and developer workflows operating on `frontend/` within `c:\Users\ganes\OneDrive\QORE` **MUST** follow these guidelines.

---

## 1. UI Resilience & Consumer Protection Protocols
* **Zero Breaking Changes**: Any UI bug fix, style refinement, or component refactoring must preserve backwards compatibility for existing user sessions, saved workspaces, and state caches.
* **Error Boundary Isolation**: Wrap all high-complexity components (Monaco Editor, Quantum Visualizers, State Inspectors) in resilient React Error Boundaries with graceful fallbacks so an isolated component crash never breaks the entire studio workbench.
* **Layout Overflow Defense**: 
  - Never apply `overflow: hidden` on parent containers without providing explicit inner scrollable regions (`overflow-y: auto`, `min-height: 0`).
  - Maintain viewport boundary integrity across 1366x768, 1440x900, 1920x1080, and responsive resizing.
* **Terminal & Canvas Teardown**: Always clean up event listeners, resize observers, canvas animation frames (`cancelAnimationFrame`), and Monaco editor models when components unmount to prevent memory leaks in consumer browsers.

---

## 2. Zero-Exposure Frontend Security & Client Isolation
* **No Client-Side Secrets**: Never declare `VITE_*` secrets or store backend API tokens, database paths, or private keys in `frontend/`.
* **API Proxy Routing**: All quantum simulation, AI assistant, and optimization requests must route strictly through the backend API (`/api/...`).
* **Secret Masking**: If error objects or logs are displayed in the UI, sanitize and mask all credential patterns prior to rendering.

---

## 3. Advanced Scalability & Performance Benchmarks
* **Code Splitting & Bundle Optimization**: Isolate language modes and heavy visualization libraries into asynchronous dynamic imports or explicit Rollup chunk boundaries to maintain rapid first-contentful-paint (<1.5s).
* **State Immutability**: Adhere to `CONTRACT.md` immutable run rules:
  - Simulation and optimization runs are immutable historical snapshots.
  - Reopening a saved experiment restores source in read-only historical mode until explicitly cloned or edited.
  - Edits clear stale live results immediately to avoid consumer confusion.
* **Strict Type Safety**: All components must pass `tsc --noEmit -p frontend/tsconfig.json` without `any` regressions or ignored type diagnostics.

---

## 4. Multi-Agent Collaboration & Guideline Linkage
When any subagent (e.g. backend specialist, security auditor, optimization agent, or general developer assistant) touches or interacts with the UI:
1. **Consult This Guideline**: Always check `docs/FRONTEND_AGENT_GUIDELINES.md` before altering frontend code or adding new API endpoints.
2. **Synchronize Contracts**: When introducing backend API endpoints or altering response envelopes in `backend/qore/`, verify alignment with `CONTRACT.md` and run `scripts/frontend_auditor.py` to ensure the frontend client remains in lockstep.
3. **Execute Verification**: Prior to closing any task that touches frontend files, execute the automated frontend audit engine:
   ```powershell
   & "C:\Users\ganes\OneDrive\QORE\.venv\Scripts\python.exe" scripts/frontend_auditor.py
   ```
4. **Autonomous Fix Verification**: If the audit detects any TypeScript failure, broken endpoint route, or secret exposure, resolve the issue autonomously before reporting completion.

---

*Authored by the QORE Frontend Autonomous Quality & UI Healing Agent.*
