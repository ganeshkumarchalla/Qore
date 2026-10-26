# Architecture and trust boundaries

QORE is a single-origin React and FastAPI application. React owns the interactive workbench; FastAPI validates API contracts and coordinates bounded quantum workers; Qiskit and Aer provide circuit semantics; SQLite stores projects and immutable evidence. Browser storage holds editable Explorer source so typing and refresh recovery do not depend on network latency.

## Request path

Every API request crosses trusted-host, origin, body-size, and schema checks before application logic. A random HttpOnly workspace cookie selects a SQLite namespace. The client never supplies an owner ID. Parse, simulate, and optimize requests enter a process-local budget and a two-slot worker gate. CPU-heavy quantum work runs outside the async event loop and is subject to a 30-second timeout.

## Data classes

Editable workspace files are mutable working material. Projects are named source records. Runs are append-oriented simulation or optimization results. Ledger experiments are immutable snapshots linking exact source hashes to compatible runs. Editing a file clears live UI evidence but never rewrites a saved run or experiment.

## AI boundary

QI Assistant receives a bounded context assembled by the backend. Gemini credentials remain in the server environment. Source and questions are treated as untrusted content, not system instructions. Local QI commands map to a small allowlist of existing UI actions; model text cannot execute arbitrary operations.

## Deployment boundary

The container is replaceable; durable state must live on a mounted disk addressed by `QORE_DB_PATH`. Browser state belongs to one origin and profile. The anonymous cookie isolates browser workspaces but is not verified identity, so this release is appropriate for personal, local, demonstration, or controlled-access use—not confidential public multi-tenancy.

## Failure behavior

Validation failures return structured errors without stack traces. Provider failure does not disable Studio, Lab, Forge, or Ledger. A worker timeout records an unsuccessful run when possible. Missing durable storage can lose backend evidence while leaving browser source intact, which is why UI save state and operations monitoring must distinguish those layers.
