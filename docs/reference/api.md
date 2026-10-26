# HTTP API reference

All application routes are under `/api` and return JSON. Errors use `{"error":{"code":"…","message":"…","details":…}}`. Unknown fields are rejected. Source is limited to 32 KiB and request bodies to 96 KiB.

## Service and source

`GET /health` reports runtime versions, AI availability, storage mode, limits, and the disabled-auth state. `POST /parse` accepts `{source}` and returns QORE-IR, metrics, warnings, source hash, and bounded visual evidence. `POST /simulate` adds shots, seed, optional noise and method. `POST /optimize` adds compilation level and seed.

## Projects and evidence

`GET /projects`, `POST /projects`, `GET /projects/{id}`, and `PUT /projects/{id}` manage named source records within the current browser workspace. `GET /runs` and `GET /runs/{id}` expose recorded executions. `POST /experiments` creates an immutable Ledger snapshot from exact source and optional source-matched run IDs. `GET /experiments` lists summaries; `GET /experiments/{id}` returns complete evidence.

## QI Assistant

`POST /assistant` accepts `question`, optional `source`, `view`, `file_name`, `workspace_summary`, `diagnostics`, and optional simulation or optimization IDs. Referenced runs must belong to the same browser scope, have the expected kind, be successful, and match the submitted source hash. A response is `{available,answer,model?}`. Unavailability is reported honestly and never replaced with fabricated numerical output.

## Workspace

`GET /workspace` returns active files, folders, Trash, active ID, server time, and retention. PUT file/folder routes require UUID identifiers and expected versions. DELETE soft-deletes; POST restore and undo recover eligible entries; PATCH state selects an active file. Paths are normalized relative names, never host filesystem paths.

## Security semantics

There are no auth routes. The `qore_workspace` cookie is assigned by the server and must be sent same-origin. Cross-origin writes are rejected. UUIDs are identifiers, not authorization; every lookup also applies the browser workspace scope.
