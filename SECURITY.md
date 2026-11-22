# Security policy

QORE is a public quantum development workspace. The current hosted release uses a Render frontend gateway and an AWS quantum API. It has no account sign-in: an opaque browser cookie separates backend records, while editable Explorer files also live in browser storage. **Do not use the public service for confidential or regulated work.** A shared browser profile can access the same workspace.

## Supported releases

Security fixes target the current `main` release and its deployed image. Development branches and older images are not maintained as separate security releases.

## Report a vulnerability privately

Use [GitHub private vulnerability reporting](https://github.com/ganeshkumarchalla/Qore/security/advisories/new). Describe the affected route or component, the minimum steps to reproduce, impact, and a safe proof of concept. Do not put credentials, private source files, workspace cookies, or personal data in a public issue.

Security reports are reviewed privately. A fix is tested against the affected boundary and the release checks before deployment. If you suspect a credential was exposed, revoke or rotate it at its provider; removing text from the latest commit does not invalidate historical copies.

## Boundaries

- The browser sends same-origin requests to a gateway that checks hosts and write origins, limits body and response sizes, and forwards API requests over HTTPS using a server-only gateway token.
- Quantum source is interpreted within a documented, bounded language scope and run in a timed worker. The worker is **not** an operating-system sandbox for arbitrary code.
- QORE Intelligence uses a server-side provider credential. Never put a secret in `VITE_*`, a browser file, an issue, or a pull request.
- GitHub secret scanning and push protection supplement the local security audit. They cannot prove that every kind of credential has been found or rotated.

Read [production security](docs/PRODUCTION.md) and [language limits](docs/reference/limits.md) before hosting or extending the runtime.
