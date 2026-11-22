# Contributing to QORE

QORE welcomes reproducible bug reports, documentation improvements, accessibility fixes, and bounded quantum workflow contributions. Start with the [product overview](README.md), [manual](docs/README.md), and [security policy](SECURITY.md).

## Propose a change

1. Open an issue that describes the user problem and a way to verify a fix. For a security vulnerability, use private reporting instead.
2. Work on a feature branch from the current `main`. Keep pull requests focused and preserve existing workspaces and experiment evidence.
3. State which behavior is real simulation, mocked UI behavior, or a provider integration. Document unsupported cases explicitly.
4. Include a test when it proves a meaningful numerical, persistence, or security property. Update the relevant manual page when user-facing behavior changes.

## Run the release checks

Use the setup in [Run locally](README.md#run-locally), then run:

```powershell
& .\.venv\Scripts\python.exe -m pytest backend/tests gateway/test_gateway.py -q
& .\.venv\Scripts\python.exe scripts/production_acceptance.py
& .\.venv\Scripts\python.exe scripts/security_checker.py --check
& .\.venv\Scripts\python.exe scripts/frontend_auditor.py
Set-Location frontend
pnpm build
pnpm test:ui
```

The browser suite needs the local QORE server running at `http://127.0.0.1:8000`. Review [testing guidance](docs/operations/testing.md) for the complete setup.

Never commit `.env` files, tokens, keys, databases, browser profiles, generated reports, or private user data. Do not widen the circuit language to arbitrary Python, shell execution, or hardware submissions without a separate security review.
