# Running QORE for real users

QORE serves the React workbench and its FastAPI API from one origin. Hosted accounts use Supabase Auth and private Postgres tables; local development can use SQLite. Simulation remains a bounded Qiskit circuit environment, with a maximum of 10 qubits, 500 operations, and 100,000 shots. It does not execute arbitrary Python, provide a general operating-system shell, or submit jobs to quantum hardware.

## First visit

The animated welcome closes automatically. Explorer has no preloaded projects. **Get Started** creates one editable three-qubit GHZ circuit only when selected; **Create blank file** starts empty. Run Kernel opens the Lab, Forge proposes a transformation with equivalence evidence, and the Ledger preserves immutable snapshots. Editing source clears live results. Existing browser files are preserved.

Production runs and cloud records require sign-in. Browser-only files are explicitly saved in account-specific caches. Use **Save As** to create a cloud project; ordinary local-file Save remains a browser save. Cache storage is not an encrypted vault: use a private browser profile on a shared computer, and export important local files before clearing browser data. Signing out clears the visible editor, results, terminal, and private lists; another account receives its own cache and cloud records.

## Required hosting configuration

Set these values in the hosting service's environment settings, never in frontend files or Git:

| Variable | Value |
| --- | --- |
| `QORE_ENV` | `production` |
| `QORE_REQUIRE_AUTH` | `true` |
| `QORE_STORAGE` | `supabase` |
| `QORE_PUBLIC_URL` | `https://qore-bmh1.onrender.com` (or your actual HTTPS origin) |
| `SUPABASE_URL` | Your Supabase project URL |
| `SUPABASE_PUBLISHABLE_KEY` | The project's publishable key, entered directly in the host dashboard |

Do not use a secret/service-role key. QORE sends each verified user's short-lived token to PostgREST, so row-level security remains enforced. Google OAuth client secrets belong in the identity provider dashboard; QORE does not need them. Optional AI configuration uses server-side `GEMINI_API_KEY` and `GEMINI_MODEL`.

Apply the SQL files in `supabase/migrations/` in order for a fresh project. For the connected QORE project, the production workspace and reduced-privilege migrations were already applied. They create three empty tables, enable RLS, remove anonymous access, and allow each account to access its own rows. Runs and experiments have SELECT/INSERT privileges only. Composite foreign keys prevent linking a different account's project or result. No example records are inserted.

## Google sign-in

In Google Cloud, configure an OAuth web client. Its authorized redirect URI is:

```text
https://yxelmlwtggjgbvjpkmrx.supabase.co/auth/v1/callback
```

In the Supabase Google provider settings, enable Google and enter the client ID and client secret directly. Configure the consent screen and test users if the OAuth app is in testing. Add QORE's production callback to the Supabase redirect allowlist:

```text
https://qore-bmh1.onrender.com/api/auth/callback**
```

For local testing only, also allow `http://127.0.0.1:8000/api/auth/callback**` and set the local `QORE_PUBLIC_URL` accordingly. The suffix permits the one-use state query parameter. Keep production redirects restricted to origins you control. Email confirmation uses the Supabase Site URL; set it to QORE's production origin and configure outbound email appropriately.

The Google button reads the provider's live availability. It stays disabled with an explanation until the provider is enabled. **Check sign-in availability** refreshes that status (the backend caches provider settings for up to 30 seconds). Do not treat a mocked OAuth test as proof of a completed real Google login.

## Container deployment on Render

Use the repository root as the Docker build context and `Dockerfile` as the deployment definition. The image builds the frontend from its lockfile, installs the quantum runtime, and runs as an unprivileged user. Uvicorn binds to the host-provided `PORT`. Access logging is disabled so OAuth query parameters are not recorded.

Set the environment values above before promoting the editing branch to the production branch watched by Render. Check `/api/health`, `/api/auth/config`, and `/api/auth/session`. A healthy process and an enabled Google provider are separate checks. Unauthenticated `/api/projects` should return 401. A production deployment missing authentication configuration fails closed with 503 for private APIs.

Then complete a real sign-in, create a project, run the three-qubit circuit, save a snapshot, reload it, sign out, and verify a second account cannot open the first account's project URL. Build artifacts, browser profiles, local databases, credentials, and generated promotional media are excluded from the container context.

## Verification

From the project root:

```powershell
& .\.venv\Scripts\python.exe -m pytest backend/tests -q
& .\.venv\Scripts\python.exe scripts/production_acceptance.py
& .\.venv\Scripts\python.exe scripts/security_checker.py --check
& .\.venv\Scripts\python.exe scripts/frontend_auditor.py
```

Build the frontend with `pnpm install --frozen-lockfile` and `pnpm build` inside `frontend`. Acceptance evidence is written under the ignored `evidence/` directory. The acceptance script uses a temporary database and independent numerical checks; it does not populate a user's workspace.

## Operational boundaries

Use a paid host with enough memory for Qiskit workloads and configure platform monitoring, database backups, and recovery before opening the service broadly. QORE limits each process to two concurrent quantum jobs, imposes per-account job budgets and per-IP authentication budgets, caps request/source sizes, and times out workers. Budgets are currently process-local; multiple replicas require a shared rate limiter and global worker queue. Benchmark the intended concurrency and memory budget before scaling.

Operator equivalence is checked up to six qubits, within the documented tolerance and terminal measurement mapping. Larger cases report the actual validation scope. Noise models are simulator models; Bloch vectors and ideal amplitudes are mathematical evidence, not device tomography. Optional cloud SDK packages do not constitute hardware access or a promise that every external SDK program can run in the bounded editor.
