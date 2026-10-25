# Deployment guide

Build the frontend with the pinned pnpm lockfile, then build the root Dockerfile. Configure `QORE_ENV=production`, `QORE_STORAGE=sqlite`, the public HTTPS origin, and a `QORE_DB_PATH` inside a mounted persistent disk. Gemini configuration is optional and must be entered only in the host secret manager.

After release, check health, create and refresh an Explorer file, run a small Bell or GHZ circuit, save a Ledger record, and verify QI both with and without attached source. Confirm that a second clean browser profile cannot list the first profile's records. Monitor memory during simulation and disk growth during repeated runs.

Never use a successful image build as the only acceptance signal. Promotion requires backend tests, production acceptance, frontend build, browser contracts, security audit, and frontend audit. GitHub Actions should run the same reproducible baseline before main is deployed.
