# Production operations

QORE serves the React workbench and FastAPI API from one origin. This release intentionally has no account, login, OAuth, or email-confirmation flow. Editable Explorer source is retained in browser storage. Backend projects, runs, workspace records, and Ledger evidence use SQLite and an opaque browser-specific HttpOnly cookie. Simulation remains a bounded Qiskit environment rather than arbitrary Python, a general shell, or a hardware-job service.

## Runtime architecture

The browser loads a static Vite build and calls same-origin `/api` routes. `AnonymousWorkspace` validates or creates a random UUID cookie, then scopes every database operation to `guest:<uuid>`. The cookie is HttpOnly and SameSite=Lax; production adds Secure. It is a capability for one browser profile, not proof of a person's identity. Anyone with control of that browser profile can use its QORE workspace.

FastAPI validates request shape, size, origin, and host. Circuit work is passed to a bounded worker with explicit qubit, operation, shot, and timeout limits. SQLite stores project and evidence records. Gemini calls are optional, rate-limited, and server-side; the key is never accepted in JSON or compiled into the frontend.

## Required host settings

| Variable | Production value |
| --- | --- |
| `QORE_ENV` | `production` |
| `QORE_STORAGE` | `sqlite` |
| `QORE_DB_PATH` | A path on the mounted persistent disk |
| `QORE_PUBLIC_URL` | The public HTTPS origin |
| `GEMINI_API_KEY` | Optional secret entered in the host dashboard |
| `GEMINI_MODEL` | An allowed Gemini model identifier |

Never put a Gemini or database credential in a `VITE_*` variable, Dockerfile, committed environment file, source comment, issue, screenshot, or CI log. The checked-in `.env.example` contains names and safe defaults only.

## Render and Docker

Build from the repository root with `Dockerfile`. The image installs the Python runtime, copies the built frontend, installs QORE, and starts Uvicorn on the platform-provided `PORT`. Attach a persistent disk and point `QORE_DB_PATH` into that mount. Without a disk, browser files still survive refreshes, but backend projects, runs, and Ledger records can disappear whenever Render replaces the container.

After deployment, inspect `/api/health`. It should report `status: ok`, `storage: sqlite`, `auth_configured: false`, and `auth_required: false`. `ai_available` confirms that the server process can see configuration; a real QI request verifies provider connectivity. Never expose the value while debugging.

## Release verification

From the repository root run:

```powershell
& .\.venv\Scripts\python.exe -m pytest backend/tests -q
& .\.venv\Scripts\python.exe scripts/production_acceptance.py
& .\.venv\Scripts\python.exe scripts/security_checker.py --check
& .\.venv\Scripts\python.exe scripts/frontend_auditor.py
Set-Location frontend
pnpm build
pnpm test:ui
```

Tests distinguish mocked browser/provider checks from real numerical simulation. Validate Explorer by creating nested folders, renaming a subtree, editing two files, refreshing, deleting a folder, undoing it, and restoring another item from Trash. Validate QI in every view, including one question without a circuit and one source-matched simulation explanation.

## GitHub Actions and promotion

The quality workflow installs pinned package-manager and language versions, runs the daily quality report, builds the frontend, starts the local production server, and runs Playwright contracts. Do not promote an editing commit while a required job is red. A secret scan failure is a release failure even if the application builds.

The recommended flow is editing branch → local verification → pull request checks → production branch/main. Generated evidence, databases, browser profiles, dependencies, and promotional recordings remain ignored. Only intentional source, documentation, lockfiles, migrations, and reproducible public assets belong in a release commit.

## QI Assistant operations

QI uses `GEMINI_API_KEY` and `GEMINI_MODEL` from the backend process. The API assembles the active view, file name, bounded workspace summary, diagnostics, optional source, and source-matched run evidence. A model answer cannot trigger arbitrary commands. The local QI command map supports a small explicit set of QORE actions, while simulation and optimization still pass through normal validated endpoints.

Rate limits are process-local: ten assistant calls per browser workspace per minute, two simultaneous provider calls, a bounded admission wait, and a provider timeout. Configure provider-side budgets and monitoring separately. Multiple replicas need a shared rate limiter and job queue before horizontal scaling.

## Backups and recovery

Back up the mounted SQLite database using a consistent snapshot method. Test restore into a separate service before treating backups as reliable. Browser source is separate: users should export important files before clearing site data or changing browser profiles. Trash provides a 48-hour application recovery window; it is not a replacement for database backups.

## Security boundary

Origin checks, trusted hosts, request limits, constrained circuit parsing, isolated browser scopes, and secure headers reduce risk. They do not turn an account-free public deployment into authenticated multi-tenant storage. Use this release for local, personal, demonstration, or controlled-access environments. Add a reviewed identity layer before hosting confidential work for unrelated users.

The previously committed privileged database credential must be rotated in its provider dashboard. Removing it from the current Dockerfile prevents new exposure but does not invalidate copies already present in Git history.
