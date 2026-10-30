# QORE Phase 1 implementation contract

Python package `backend/qore`, tests `backend/tests`; Vite React/TS frontend `frontend`.
All API URLs use `/api`. JSON timestamps are UTC ISO8601. Error envelope:
`{"error":{"code":"...","message":"...","details":...}}`.

## Quantum engine (backend/qore/quantum.py)

Public functions returning JSON-compatible dictionaries:
- `parse_source(source: str) -> {ir, metrics, source_hash, warnings}`
- `simulate(source: str, shots: int=1024, seed: int=42) -> {ir, metrics, source_hash, warnings, counts, probabilities, theoretical_probabilities, tvd, shots, seed, backend, versions, execution_ms, bit_ordering}`
- `optimize(source: str, level: int=2, seed: int=42) -> {source_hash, original: {ir, metrics}, candidate: {ir, metrics, source}, settings, differences, validation, explanation, versions, warnings}`
- `validate_ir(original: dict, candidate: dict) -> validation`
- `versions() -> dict`
- `QuantumError` exposes `code`, `message`, optional `details`.

IR: `{version:"1.0", num_qubits:int, num_clbits:int, global_phase:number, operations:[{name:string, qubits:number[], clbits:number[], params:number[]}]}`.
Metrics: `{qubits, clbits, gate_count, depth, two_qubit_gate_count, measurement_count, barrier_count, gate_types:{gate:number}, definition:string}`.
Validation: `{status:"validated"|"failed"|"unavailable"|"inconclusive", method:string, details:string, ...actual quantitative evidence}`.
Bloch vectors include `direction_defined:boolean` and `azimuth_defined:boolean`; `theta` is a compatibility placeholder when the direction is undefined, and `phi` is a placeholder when azimuth is undefined (including poles on the Z axis).
Differences: keyed by metric, `{original:number,candidate:number,absolute:number,relative_percent:number|null}`; absolute is candidate minus original.
Controlled gates use qubits in framework order (controls then targets); no independently interpreted UI source.
Support constrained AST parsing, never exec/eval. Terminal measurements only, up to 10 qubits, 10 classical bits, 500 operations, 32 KiB source, 100000 shots. Equivalence full operator up to global phase <=6 qubits; larger cases honestly unavailable. Preserve global phase in IR/source or equivalence up to global phase. Enforce mapping comparison.

The installed executable surface is reported by `GET /api/capabilities`. Qiskit support means the reported bounded circuit-building subset and OpenQASM 2.0, not arbitrary Python, all Qiskit packages, provider clients, pulse programs, primitives, dynamic circuits, hardware jobs, or future SDK APIs. Unsupported source must fail explicitly and must never fall through to `exec`, `eval`, a host shell, filesystem access, networking, or package installation.

Capabilities also report installed Qiskit distribution versions separately from editor execution permissions. Gate constructor keywords must be validated and never silently ignored. Composite unitary library gates and open controls lower to bounded u/cx instructions before metrics and IR generation, preserving global phase; the expanded circuit remains subject to the existing operation limit. OpenQASM includes are restricted to built-in qelib1.inc. QASM 2 export/reimport equivalence is up to global phase.

Supported library constructors may build reusable circuit fragments and bounded variational/feature-map templates. The primary circuit is `qc` when declared, otherwise the first constructed circuit, reported as `selected_circuit` (null for direct QASM). Only the primary circuit must be fully parameter-bound before analysis. Parameter, ParameterVector, explicit parameter binding, circuit composition and whitelisted quantum-object transforms are supported; copy and in-place semantics must match Qiskit. Numeric data is restricted to finite literal vectors/matrices of at most 500 entries, checked before NumPy materialization. Factory repetitions are capped at 20 and matrix-based powers at four qubits. No arbitrary callbacks, object access or provider execution is enabled by these adapters.

## API
- QORE currently exposes no login, signup, OAuth, or account-management routes.
- An opaque `qore_workspace` HttpOnly, SameSite cookie scopes SQLite projects, runs, experiments, and workspace records to one browser profile. It is a workspace boundary, not verified human identity.
- GET `/health` -> `{status,versions,ai_available,auth_configured:false,auth_required:false,storage:"sqlite",limits}`
- GET `/capabilities` -> installed circuit languages, bounded modules, native gates, simulator methods, workflows, limits, and safety boundary
- GET `/examples` -> `[{id,name,description,source}]`
- GET `/projects` -> project summaries (including source acceptable)
- POST `/projects` body `{name,source}` -> project
- PUT `/projects/{id}` body `{name,source}` -> project
- GET `/projects/{id}` -> project
Project `{id,name,source,created_at,updated_at}`.
- POST `/parse` body `{source}` -> parse result
- POST `/simulate` body `{source,shots,seed,project_id?:string}` -> run record
Run `{id,kind:"simulation",created_at,project_id,source,...simulate result}`; persisted immediately as immutable run.
- POST `/optimize` body `{source,level,seed,project_id?:string}` -> optimization run `{id,kind:"optimization",created_at,project_id,source,...optimize result}` persisted immediately.
- POST `/experiments` body `{name,project_id?:string,source,simulation_id?:string,optimization_id?:string}` -> immutable experiment snapshot
- GET `/experiments` -> experiment summaries `[{id,name,project_id,created_at,source_hash}]`
- GET `/experiments/{id}` -> `{id,name,project_id,created_at,source,source_hash,ir_version,versions,simulation:run|null,optimization:run|null}`
- POST `/assistant` body `{question,source?:string,simulation_id?:string,optimization_id?:string,view,file_name?,workspace_summary?,diagnostics?}` -> `{available:boolean,answer:string,model?:string}`. Optional provider unavailable is an honest response. The Gemini key is server-only.

UI must clear live results on code edit; reopen restores source and immutable historical snapshots visibly labeled historical; source actions leave read-only historical mode on new parse/run. Save experiment references backend run IDs and must match source hashes. Approve candidate is explicit source replacement; original remains in immutable optimization record. Do not silently save edits on project switch; in-app discard confirmation.

## Persistent workspace and Trash

Explorer files and folders use a mutable browser workspace with a server workspace API available for browser-scoped records. Existing projects/runs/experiments remain independent historical contracts. Active entries have no automatic expiry. Requests never select an owner supplied in JSON.

- GET `/workspace` -> `WorkspaceSnapshot`.
- GET `/workspace/trash` -> `{trash,retention_hours:48,server_time}`.
- PUT `/workspace/files/{uuid}` body `{path,source,kind,expected_version}` -> entry. `expected_version:0` creates an entry; updates require the current version. Empty source is valid; the UTF-8 source limit is 32768 bytes. `kind` is `python|qasm|json|markdown`.
- PUT `/workspace/folders/{uuid}` body `{path,expected_version}` -> entry. A folder rename/move updates its active subtree atomically.
- DELETE `/workspace/files/{uuid}` or `/workspace/folders/{uuid}` body `{expected_version}` -> snapshot. Deletion is soft, increments versions, removes active entries, and records the last deletion. Folder deletion is an atomic trash batch.
- POST `/workspace/files/{uuid}/restore` or `/workspace/folders/{uuid}/restore` -> snapshot. Restore never overwrites an occupied active path.
- POST `/workspace/undo` -> snapshot restoring the latest recoverable deletion.
- PATCH `/workspace/state` body `{active_file_id:uuid|null}` -> snapshot. Only an active file belonging to the current owner may be selected.

Entry: `{id,path,name,type:"file"|"folder",source,kind:null|fileKind,version,created_at,updated_at,deleted_at:null|ISO,expires_at:null|ISO}`. Snapshot: `{files,folders,trash,active_file_id,last_deleted_id,retention_hours:48,server_time}`. UUID identity survives rename; a path is not an entry identifier. Paths are relative, normalized, bounded, and must not contain empty, dot, parent, backslash, or control-character segments.

The database assigns `expires_at = deleted_at + 48 hours`; the browser cannot extend server retention. Expired trash is unavailable for reads/restoration and is purged by bounded maintenance. Active files are never purged by Trash maintenance. A 409 conflict preserves the browser draft and does not overwrite newer server text. Browser-local source remains authoritative for the account-free editor.

Welcome animates and dismisses automatically. A new workspace contains no seeded files. Get Started explicitly creates one editable three-qubit GHZ circuit. Browser files persist under the local QORE workspace namespace across refreshes.
