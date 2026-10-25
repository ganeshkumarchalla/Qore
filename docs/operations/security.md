# Security operations

QORE protects secrets by keeping provider credentials in the backend environment and excluding environment files, keys, certificates, databases, and credentials from Git. Frontend `VITE_*` variables are public bundle inputs and must never contain a provider key.

The API applies trusted-host checks, same-origin write checks, request-size limits, strict schemas, constrained circuit parsing, per-workspace rate limits, worker concurrency, and secure response headers. Database lookups always combine an opaque browser scope with the requested identifier.

This release has no verified user identity. An HttpOnly workspace cookie prevents casual cross-browser mixing but does not protect against another person controlling the same browser profile. Do not use the public deployment for confidential multi-tenant data. Add reviewed authentication, authorization, session revocation, and migration before that use case.

Run `scripts/security_checker.py --check` before every release. If a credential was committed, remove it from the current tree, rotate or revoke it at the provider, inspect history and artifacts, and document the incident. Deleting one line does not revoke an already copied secret.
