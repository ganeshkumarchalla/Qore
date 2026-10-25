# Email accounts and private sessions

QORE uses email and password for hosted sign-in. Account identity determines which files, folders, runs, and experiments the server may return. The backend verifies the session with the identity provider and passes the verified identity into private storage. A client-supplied owner identifier never determines access.

## Register and confirm

Enter your name, email address, and password in the account dialog. Signup requires at least eight password characters and enforces bounded field sizes. Use a unique password and a password manager. Follow the confirmation email, return to the configured QORE origin, and sign in with the confirmed address.

If the identity provider is deliberately configured for immediate confirmation, the backend can establish a verified session after signup. QORE does not use an administrative key to bypass provider confirmation. A public operator should keep confirmation enabled and configure reliable outbound delivery before inviting users.

## Recover from missing confirmation mail

Check spam, filtering rules, and the spelling of the address. Use **Resend confirmation** and allow time for delivery. Repeated requests can hit a provider or application rate limit. The resend response intentionally does not disclose whether a particular address has a pending account.

An operator can inspect delivery settings and provider status without collecting passwords or asking a user to paste a confirmation URL. The Site URL should match the public HTTPS QORE origin, and confirmation redirects must be allowed. Mocked tests verify request handling; only an actual delivered message followed by confirmed sign-in proves the complete delivery path.

## Session behavior

QORE's backend sets HTTP-only session cookies. The session JSON contains a limited profile, not access or refresh tokens. Cookies use the HTTPS security flag in production and a SameSite policy for the same-origin application. The backend verifies provider identity and refreshes sessions where appropriate.

Browser JavaScript cannot read an HTTP-only cookie, but account-specific editing caches can still contain source and pending changes. A browser cache is not an encrypted vault. Use a private operating-system account and browser profile on a shared device; sign out before handing the device to another person.

## Private data and account switching

Hosted requests use the verified account's identity. Postgres row-level security and guarded workspace write functions enforce account isolation. Legacy projects, runs, and experiments remain separately owner-scoped. Guessing a UUID must not reveal someone else's entry or permit a write.

Signing out clears the visible editor, results, terminal, and private lists. A second account receives its own workspace and cache. Guest work is not silently assigned to whichever account signs in next. Export pending offline text before changing accounts, particularly if a synchronization error remains unresolved.

## Distinguish common errors

| State | Interpretation and response |
| --- | --- |
| Confirmation required | Follow the email link or resend after checking delivery |
| Invalid details | Verify address/password inside the app; never send them in a report |
| Rate limited | Wait; repeated attempts do not accelerate confirmation |
| Service unavailable | Preserve pending source and retry after provider recovery |
| Session expired | Sign in to the same account and inspect pending saves |
| Required configuration missing | Operator must fix server settings; private APIs remain closed |

The current public auth surface is email-only. Provider configuration and secrets belong in the operator dashboard or ignored server environment, never in the repository, frontend bundle, or circuit files. See [security operations](../operations/security.md) for identity checks, origin controls, least privilege, and safe support practices.
