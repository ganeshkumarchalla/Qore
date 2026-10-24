# Local execution guarantees and limitations

QORE is designed for a single user on loopback. Start with `--host 127.0.0.1`. It has no multi-user authentication, tenancy, or internet-facing deployment security.

## Source handling

User source is parsed using Python's AST and interpreted through a closed circuit-building grammar. It is never passed to `exec`, `eval`, a shell, dynamic import, or a Python runtime namespace. Supported imports are declarations recognized by the interpreter, not general Python imports. Filesystem/network calls, attributes outside the defined grammar, arbitrary functions/classes, comprehensions, while loops, exceptions and unsupported constructs are rejected. The engine documents exact permitted constructs in `QUANTUM.md`.

The AST interpreter and framework mapping enforce source bytes, AST/numeric/iteration limits, qubit/classical-bit/operation caps, finite numeric values, supported gate arity, bit indices, and terminal-only measurements. Exact full-operator verification is capped separately at six qubits. No assertion of equivalence is made when that method is unavailable.

## Runtime controls

Each parse/simulate/optimize job uses a fresh subprocess through a fixed `qore.worker` entry point and structured JSON stdin. The parent imposes a 30-second wall-clock timeout and kills/waits for the worker on timeout. There are at most two active quantum jobs, with a two-second queue wait followed by HTTP 429. Numerical libraries and Aer use limited CPU parallelism. API inputs cap 10 qubits, 10 classical bits, 500 operations, 100000 shots and 32 KiB UTF-8 source. JSON bodies are capped at 96 KiB regardless of their advertised content length.

The worker receives a small environment allowlist; AI keys are excluded. User source has no operation that can read files, access the network or spawn processes. This is **not an operating-system sandbox**: trusted Python/Qiskit/native dependencies retain their normal OS privileges, and no hard OS memory quota or network namespace is configured on Windows. Resource bounds reduce expected resource use; they do not protect against an exploitable defect in a dependency. Untrusted multi-tenant hosting would need containers/VMs, OS quotas, network restrictions, authentication and rate limits.

## API, secrets and persistence

Pydantic rejects unexpected fields, malformed types, out-of-range values and oversized inputs. Requests use a consistent error envelope; internal exception details and provider errors are not returned to clients. Trusted host checks and explicit loopback Origin checks reject cross-origin writes. Cross-site browser requests are rejected. Same-origin production serving and Vite proxying avoid broad CORS permissions. These controls are not authentication against malicious local processes.

SQL uses parameter binding. Runs and experiments are append-only through the API, and experiment creation retrieves trusted run records by ID and checks exact source hashes and run types. The client cannot submit invented counts as evidence. Local users with filesystem access can modify SQLite; there is no cryptographic execution attestation or tamper-proof audit trail. Failed runs are retained with source, configuration, timestamp and error.

Gemini credentials exist only in server environment variables and never frontend bundles. The assistant only sends context after the user asks a question. Source and results are treated as untrusted text in the AI system prompt. AI output is advisory text, never executable code or automatic source changes. No logs intentionally include API keys.

## Deployment boundary

Do not expose this Phase 1 server to a public network. Security verification results in `ENGINEERING_REPORT.md` describe tests actually executed, not a formal security audit. Dependencies and future expanded source constructs require renewed review.
