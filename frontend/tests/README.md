# QORE browser checks

These checks open a fresh browser context and exercise the served application. Start QORE with a current frontend build before running them. The default URL is `http://127.0.0.1:8000`.

From the repository root:

```powershell
pnpm --dir frontend install --frozen-lockfile
pnpm --dir frontend build
# Start the QORE backend using the project's documented local run command.
pnpm --dir frontend test:ui
```

Windows uses installed Microsoft Edge. Linux and macOS use Playwright Chromium; install it once with `pnpm exec playwright install chromium` from `frontend/`. CI can use `pnpm exec playwright install --with-deps chromium`.

For another running server, set `QORE_TEST_URL` before running the suite:

```powershell
$env:QORE_TEST_URL = 'http://127.0.0.1:5174'
pnpm --dir frontend test:ui
```

Individual checks also accept a URL argument, which takes precedence over the environment variable:

```powershell
node frontend/tests/assistant-ui.cjs http://127.0.0.1:8000
node frontend/tests/settings-ui.cjs http://127.0.0.1:8000
node frontend/tests/workspace-ui.cjs http://127.0.0.1:8000
node frontend/tests/auth-ui.cjs http://127.0.0.1:8000
node frontend/tests/public-page-ui.cjs http://127.0.0.1:8000
```

- `assistant-ui.cjs` checks deferred editor loading, active circuit context, independent assistant navigation, five viewport sizes, focus behavior, account clearing, and terminal output accuracy. API responses are explicitly mocked.
- `settings-ui.cjs` checks all six settings sections, unsupported controls, persisted supported settings, and keyboard focus. API responses are explicitly mocked.
- `workspace-ui.cjs` checks editable files/folders, autosave, refresh and offline recovery, conflict handling, 48-hour Trash, Undo, restoration, expiry and account isolation with an explicit API fixture.
- `auth-ui.cjs` checks email-only signup/sign-in, confirmation/resend feedback, verified-profile reopening, sign-out and absence of password persistence. API responses are explicitly mocked.
- `public-page-ui.cjs` checks the real About page, desktop/mobile overflow, title, canonical URL, and sitemap. It does not mock responses.

These are UI contract checks. They do not prove real email delivery, live hosted account permissions, or numerical backend correctness. Backend/SQL verification covers API and ownership boundaries; a real confirmation and sign-in must be completed separately by an account owner. They never reuse personal browser profiles or create live accounts.

Screenshots and reports are written to the repository's ignored `evidence/` directory regardless of the working directory. A failing assertion exits nonzero. The original replay copies in `evidence/` remain available locally; these tracked scripts are the portable versions for future checkouts.
