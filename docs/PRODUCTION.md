# Running QORE for real users

QORE serves the React workbench and its FastAPI API from one origin. Hosted accounts use Supabase Auth and private Postgres tables; local development can use SQLite. Simulation remains a bounded Qiskit circuit environment, with a maximum of 10 qubits, 500 operations, and 100,000 shots. It does not execute arbitrary Python, provide a general operating-system shell, or submit jobs to quantum hardware.

## First visit

The animated welcome closes automatically. Explorer has no preloaded projects. **Get Started** creates one editable three-qubit GHZ circuit only when selected; **Create blank file** starts empty. Run Kernel opens the Lab, Forge proposes a transformation with equivalence evidence, and the Ledger preserves immutable snapshots. Editing source clears live results. Existing browser files are preserved.

Production runs and cloud records require sign-in. Signed-in Explorer files and folders automatically synchronize to the account's database workspace, including the active file. Refreshing restores saved content; active files have no automatic expiry. The status indicator distinguishes saved changes, pending local drafts, and conflicts. Use **Save As** for a named project snapshot; the editable workspace and immutable Ledger evidence are separate records. Browser recovery storage preserves unsynced drafts and is not an encrypted vault. Use a private browser profile on shared computers. Signing out clears visible private state; another account receives its own workspace.

The primary toolbar includes **Undo delete** and **Trash**. Deleting a folder moves its subtree to Trash atomically. Restore is available for 48 hours from deletion, subject to path conflicts; restoring never silently replaces an existing file. After the deadline, reads and restoration reject the deleted content immediately. A database cleanup job physically removes expired content every five minutes. Active files and folders are not touched by this job. Opaque tombstones prevent an old offline draft from recreating a deleted identifier. Each account currently has a limit of 1,000 entries and 16 MiB of source, with 32 KiB per file; this is bounded application storage rather than a general file drive.

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

Do not use a secret/service-role key. QORE sends each verified user's short-lived token to PostgREST, so row-level security remains enforced. Authentication is email and password only; the application has no Google sign-in route or button. Optional AI configuration uses server-side `GEMINI_API_KEY` and `GEMINI_MODEL`.

Apply the SQL files in `supabase/migrations/` in order for a fresh project. They create the project/run/experiment records and the editable workspace, enforce owner-scoped RLS, and insert no example records. Runs and experiments have SELECT/INSERT privileges only. Composite foreign keys prevent cross-account linking. Workspace mutation goes through a validated RPC: the caller cannot choose an owner or retention timestamp. Per-owner transaction locks and expected-version checks serialize updates without silently overwriting a newer version. The connected database has these migrations applied; verify the scheduled cleanup job after restoring or creating another database.

## Email sign-in and confirmation

Enable the Email provider and email confirmation in Supabase Auth. Set the Site URL to the actual production HTTPS origin. Add the exact production redirect `https://qore-bmh1.onrender.com/?email_confirmation=opened` to its redirect allowlist; for a separate local test, also allow `http://127.0.0.1:8000/?email_confirmation=opened`. Set `QORE_PUBLIC_URL` to the corresponding origin, with no callback path. Avoid wildcard production origins.

Create an account in QORE, choose a password of at least 12 characters, and confirm through the provider's email. Return to QORE and sign in with that password. **Resend verification email** handles pending confirmations without revealing whether a stranger's address is registered. QORE never uses an administrator key to bypass confirmation. Browser JavaScript receives only a public profile; session credentials stay in HttpOnly cookies. Production cookies are Secure and SameSite=Lax, and provider token fragments are removed from the URL before the app loads.

The sign-in form checks live email-provider availability, cached for at most 30 seconds. Configure production SMTP with a sender domain and delivery monitoring; a successful API response is not proof that a particular mailbox received the message. Hosted-provider sandbox email limits and rate limits may prevent delivery until an operator configures email. Complete a real confirmation/sign-in test after each provider or redirect change, and keep passwords and verification codes out of issue reports and chat.

## Container deployment on Render

Use the repository root as the Docker build context and `Dockerfile` as the deployment definition. The image builds the frontend from its lockfile, installs the quantum runtime, and runs as an unprivileged user. Uvicorn binds to the host-provided `PORT`. Access logging is disabled to avoid recording sensitive request URLs.

Set the environment values above before promoting the editing branch to the production branch watched by Render. Check `/api/health`, `/api/auth/config`, and `/api/auth/session`. Process health, email-provider availability, actual email delivery, and database permissions are separate checks. Unauthenticated `/api/projects` and `/api/workspace` should return 401. A production deployment missing authentication configuration fails closed with 503 for private APIs.

Then complete a real email sign-in, create a file, edit it, wait for **Saved**, refresh, and check the exact source. Delete and undo it, test Trash restoration and path conflicts, run the three-qubit circuit, save a Ledger snapshot, and restore that evidence. Sign out and verify another account cannot read the first account's file or project. Build artifacts, browser profiles, local databases, credentials, and generated promotional media are excluded from the container context.

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

Optional AI requests have a separate limit of ten requests per account per minute and two concurrent provider calls per process, with bounded waiting and a provider timeout. These budgets protect the shared provider integration; they are not a replacement for provider-side spending limits.

Operator equivalence is checked up to six qubits, within the documented tolerance and terminal measurement mapping. Larger cases report the actual validation scope. Noise models are simulator models; Bloch vectors and ideal amplitudes are mathematical evidence, not device tomography. Optional cloud SDK packages do not constitute hardware access or a promise that every external SDK program can run in the bounded editor.

## Public pages and search

`/about.html` provides public, static product information with a canonical URL, descriptive metadata, and structured application data. `robots.txt` and `sitemap.xml` identify the public page. The workspace HTML uses `noindex`; API responses send `X-Robots-Tag: noindex, nofollow, noarchive` and private APIs still require authentication. Search directives are not access controls.

If the production domain changes, update the canonical/Open Graph/structured-data URLs in `frontend/public/about.html` and the URLs in `robots.txt` and `sitemap.xml`, then rebuild. Search Console ownership verification and sitemap submission require the site owner's Google account; metadata alone does not prove indexing or rankings. See [Google's indexing controls](https://developers.google.com/search/docs/crawling-indexing/block-indexing) and [sitemap guidance](https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap).

Never embed credentials in the Dockerfile, committed build files, or CI configuration. Enter the publishable key directly in the host environment. If a privileged key has been exposed, rotate/revoke it in the provider dashboard; deleting it from the current file alone does not revoke it. Review history before sharing changes and avoid rewriting shared Git history without coordinating with collaborators.
