# Local development

Local development uses the same React workbench and FastAPI routes as the hosted product. The API can serve a built frontend from one origin, or Vite can provide hot reload while proxying `/api` to Python. SQLite stores backend records; browser storage retains editable Explorer source.

## Install and build

Use Python 3.11–3.13 and a Node.js release compatible with the pinned pnpm version in `frontend/package.json`. The backend constrains Qiskit 2 and a compatible Aer version. Keep the committed frontend lockfile authoritative.

```powershell
py -3.12 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -e ".[test,docs]"
Set-Location frontend
pnpm install --frozen-lockfile
pnpm build
Set-Location ..
& .\scripts\start.ps1
```

Open `http://127.0.0.1:8000`. The startup script checks the environment and frontend build, sets a workspace temporary directory, and binds to loopback. Stop it with Ctrl+C. A missing build should be fixed by building, not by assuming that an unrelated preview server represents the current code.

## Hot reload

Start `scripts/start.ps1 -Dev` in one terminal. Run `pnpm dev` inside `frontend` in another. Open Vite's reported local URL. The frontend continues to call relative API routes, and its development proxy sends them to the Python server.

Hot reload does not rebuild the release bundle. Run `pnpm build` before checking the single-origin production behavior. If an older interface appears, verify the address and server process first. Do not delete browser site data or databases as a routine troubleshooting shortcut; they may contain user work.

## Configuration boundaries

Keep configuration in the ignored server environment. Read [configuration](../reference/configuration.md) for identity, storage, public origin, host validation, and optional AI variables. Never prefix a backend secret with `VITE_`; Vite embeds those values in public static files. The frontend does not need a service-role database key or model-provider credential.

The account-free SQLite runtime is intended for local, personal, demonstration, or controlled-access use. A confidential public multi-user service requires a reviewed identity and authorization layer. Optional SDK extras support separate operator experiments; they do not expand the public source interpreter's allowlist.

## Module orientation

`main.py` wires routes, anonymous browser workspaces, and orchestration. `quantum.py` implements source parsing, IR, simulation, metrics, and equivalence. `runtime.py` and `worker.py` bound execution. `workspace.py` and `store.py` handle entries, concurrency, evidence, and recovery. Feature components and application state live under `frontend/src`.

Read the frontend agent guidelines before UI edits. Keep source hashes, live-result invalidation, immutable snapshots, and request types consistent. Renaming a path must preserve its stable record ID. A stale write must fail rather than silently overwrite newer server text. Use temporary browser contexts and databases when checking these behaviors.

## Verify and build documentation

Run backend regression tests, production acceptance, security checking, and frontend auditing from the root. Run browser tests with `pnpm test:ui` inside `frontend`. Fresh reports matter: a stale passing artifact says nothing about the current change.

The `docs` extra installs the Markdown renderer. `scripts/build_docs.py` turns the Markdown pages into a separate static documentation site with navigation, search, table of contents, and copied local images. Check its `--help` interface before invoking it for another destination. Edit Markdown sources rather than generated HTML that the next build will replace.
