# Automated quality reviews

QORE has an active Codex daily review coordinator scheduled for **09:00 in Asia/Kolkata**. Scheduling is managed by the Codex heartbeat attached to the project conversation; this repository does not install an operating-system task or a server cron job.

| Dedicated review agent | Responsibility |
| --- | --- |
| Studio and Explorer | Editing, database autosave, refresh/offline recovery, folder operations, 48-hour Trash and Undo, layout and accessibility |
| Quantum Lab and Qiskit | Analytic reference circuits, probabilities, noise, Bloch purity, matrices, supported syntax and bounds |
| Forge | Compiler candidates, operator equivalence, source hashes, measurement mapping and approval |
| Identity and Ledger | Email confirmation and availability, verified sessions, account separation, RLS and immutable restoration |
| AI Assistant | Secondary sidebar, grounded circuit/results context, stale-response prevention and safe failures |
| Security and Secrets | Source/configuration scanning, credentials, Docker boundaries, dependency advisories and IDE safety |
| Organization and Scalability | Module boundaries, types, containers, persistence, worker budgets, concurrency and performance |
| SEO and Google Discoverability | Public metadata, crawlability, sitemap, canonical URLs, accessibility and indexing boundaries |

The coordinator dispatches these scopes in batches within the available agent limit, then consolidates actionable findings into a daily report. If delegation is unavailable, it completes the scopes sequentially. It prepares safe fixes in an isolated branch/worktree and does not automatically push, merge, deploy, rotate credentials, or modify live user data.

The coordinator uses the repeatable local baseline below, reviews its evidence, and directs focused investigation where a check fails or a meaningful improvement is identified. The specialist review complements the executable checks; a successful build alone does not establish security, accessibility, scalability, or quantum correctness.

## Run the same baseline manually

From the repository root, with project dependencies installed:

```powershell
& ".\.venv\Scripts\python.exe" scripts/daily_quality_report.py
```

The script performs four sequential stages:

| Stage | Checks | Timeout |
| --- | --- | ---: |
| Security and secret exposure | Source/configuration credentials, Dockerfiles, environment variants, Git exposure, ignore rules, IDE settings, configuration heuristics | 120 seconds |
| Frontend health | TypeScript, production build, frontend secret isolation, structural checks and API contract heuristics | 180 seconds |
| Backend regression suite | All tests in `backend/tests`, including anonymous browser isolation and workspace boundaries | 600 seconds |
| Quantum and ledger acceptance | Real API/worker/Aer execution, reference comparisons, noise, matrices, Forge equivalence and immutable evidence restoration | 180 seconds |

Every stage runs even if an earlier stage fails, so the resulting report identifies independent problems. The script exits with a nonzero status if a stage fails, times out, or does not produce a fresh valid report. Timed-out process trees are terminated.

## Evidence

Reports are written to the ignored local `evidence/` directory:

- `daily_quality_report.json` and `.md`: stage outcomes, timings, numeric summaries and individual report locations.
- `security_report.json` and `.md`: findings with fully masked credentials.
- `frontend_health_report.json` and `.md`: frontend checks and diagnostics.
- `production_acceptance.json` and `.md`: quantitative quantum and ledger results.

The daily aggregator captures child output in memory and retains only numeric summaries. It does not copy arbitrary compiler, provider, or test output into its logs. Provider credential variables are removed from child environments. Acceptance uses temporary SQLite storage and explicitly prevents loading the user's `.env`; it never operates on live user projects or accounts.

The baseline does not push commits, deploy releases, install dependencies, or change external services. The schedule and specialist responsibilities can be updated through the project conversation.

## Repository quality gate

`.github/workflows/quality.yml` runs the same baseline on pushes to `editing`, `main`, and `production`, and on pull requests targeting release branches. It also has a daily 09:00 India schedule and a manual trigger. The daily GitHub schedule becomes active when the workflow is present on the repository's default branch. This complements the Codex specialist review and can run without the desktop app being open.

The workflow has read-only repository permissions, pinned action revisions, a frontend lockfile, an isolated Python environment, bounded execution, and a numeric job summary. It receives no provider credentials and does not deploy, merge, or publish user data. Use its checks when reviewing the editing branch before release promotion.

## Secret-scanning boundaries

The scanner checks source files, extensionless Dockerfiles/Containerfiles, `.env.example`, and `.env.*` variants. It recognizes modern secret key formats and legacy JWTs whose decoded payload explicitly grants the `service_role` role. Tokens are never printed, including partial prefixes or suffixes. A public `anon` JWT is not treated as a privileged credential merely because it is a JWT.

An ignored server `.env` is left unread. Frontend environment files remain in scope, and Git's index is checked by filename to identify tracked sensitive paths even when ignore rules exist. Generated dependency, build, browser-profile, capture, and media directories are pruned. An unreadable source/configuration file produces a finding rather than a successful secret-scan result.

These are detection heuristics, not a guarantee that every possible credential format or vulnerability will be found. Windows file ACLs require a separate host permission inspection; the scanner does not claim to verify them.

## Quantum verification scope

Acceptance covers three-qubit GHZ preparation, a two-qubit marked-state Grover example, coherent deferred-measurement teleportation, the original four-qubit `openqasm/qaoa_cut.qasm` regression sequence, noisy outcomes versus an ideal reference, displayed unitary orthonormality, Forge operator equivalence, invalid input rejection, and immutable ledger restoration after restart.

All quantum execution is local simulation. The configured source, qubit, operation, shot, timeout, and operator-validation limits apply. These checks do not assert support for arbitrary Python, every Qiskit API, hardware execution, or a proven optimization advantage. The historical QAOA sequence is a test fixture, not an automatically created user file.
