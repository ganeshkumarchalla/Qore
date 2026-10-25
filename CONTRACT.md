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
Differences: keyed by metric, `{original:number,candidate:number,absolute:number,relative_percent:number|null}`; absolute is candidate minus original.
Controlled gates use qubits in framework order (controls then targets); no independently interpreted UI source.
Support constrained AST parsing, never exec/eval. Terminal measurements only, up to 10 qubits, 10 classical bits, 500 operations, 32 KiB source, 100000 shots. Equivalence full operator up to global phase <=6 qubits; larger cases honestly unavailable. Preserve global phase in IR/source or equivalence up to global phase. Enforce mapping comparison.

## API
- Authenticated deployments require a verified server session for private `/api` routes.
- GET `/auth/config` -> `{configured,required,google_enabled,email_enabled,message?}` (public availability only).
- GET `/auth/session` -> `{user:null|{id,email,name,avatarInitials,role,tier},configured,required}`.
- GET `/auth/google` -> provider redirect using one-use state and PKCE cookies; GET `/auth/callback` exchanges the code server-side.
- POST `/auth/signin` `{email,password}` and `/auth/signup` `{name,email,password}` -> public profile or email-confirmation message.
- POST `/auth/signout` -> clears the current session. Tokens are HTTP-only cookies and never JSON profile fields.
- The verified owner scopes every project, run, and experiment. Hosted storage uses user-token Supabase RLS; local SQLite retains legacy work under a separate `local` identity.
- GET `/health` -> `{status,versions,ai_available,limits}`
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
- POST `/assistant` body `{question,source,simulation_id?:string,optimization_id?:string}` -> `{available:boolean,answer:string,model?:string}`. Optional provider unavailable is an honest response.

UI must clear live results on code edit; reopen restores source and immutable historical snapshots visibly labeled historical; source actions leave read-only historical mode on new parse/run. Save experiment references backend run IDs and must match source hashes. Approve candidate is explicit source replacement; original remains in immutable optimization record. Do not silently save edits on project switch; in-app discard confirmation.

Welcome animates and dismisses automatically. A new workspace contains no seeded files. Get Started explicitly creates one editable three-qubit GHZ circuit. Browser files are cached under the verified account's namespace, with the original guest cache retained separately. Identity changes cancel outstanding browser requests, clear editor/results/private lists, and reset terminal state.
