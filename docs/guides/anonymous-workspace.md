# Account-free workspace and browser boundaries

QORE currently opens without registration, an identity provider, or a password. This keeps first use immediate and makes local or controlled demonstrations straightforward. It also changes the security model: a browser profile, rather than a verified person, is the workspace boundary.

## What persists

Explorer source is stored in the browser and survives ordinary refreshes. The active file, folders, settings, and recovery state are restored from the same site profile. Backend projects, runs, and Ledger records use SQLite. The server assigns a random opaque cookie and uses it to choose a database namespace without trusting an owner ID from request JSON.

The cookie is HttpOnly, SameSite=Lax, and Secure on production HTTPS. JavaScript cannot read it. It contains no personal profile, API token, or database credential. It is nevertheless a capability: another person using the same unlocked browser profile can reach the same QORE records.

## Shared computers

Use a separate operating-system account or browser profile on a shared machine. Export important source before clearing site data, using private browsing, or moving to another device. There is no password-based recovery or account transfer in this release.

Do not store passwords, API keys, patient data, regulated data, or confidential research in circuit comments. Browser storage is not an encrypted vault. QI questions and attached context can be sent to the configured external model provider when the assistant is used.

## Server persistence

SQLite survives process restarts only when `QORE_DB_PATH` points to durable storage. A Render service without a mounted disk can lose projects, runs, and Ledger records during replacement or redeployment. Browser Explorer files remain on the device, but that does not restore missing backend evidence.

Operators should back up the database, test restoration, monitor disk capacity, and retain the same public origin. Changing domains creates a new cookie and browser-storage origin, which appears as a different workspace.

## Isolation test

Automated tests create two independent browser clients, save records in one, and verify that the other receives empty lists and `404` responses for guessed record IDs. This establishes browser-scope isolation for application routes. It is not equivalent to authentication because control of a browser profile is sufficient to use its cookie.

## When authentication returns

A future identity layer should migrate anonymous records only after explicit user confirmation. It must not silently assign a shared-browser workspace to the next person who signs in. The identity design must keep provider tokens server-side, preserve source-hash checks, and retain owner scoping for projects, runs, experiments, files, Trash, and rate limits.

See [workspace files](workspace-files.md), [production operations](../PRODUCTION.md), and [security](../operations/security.md) for the complete operational boundary.
