# Troubleshooting QORE

Separate browser state, storage confirmation, source compatibility, worker execution, provider connectivity, and interpretation when diagnosing a problem. Preserve source before clearing site data. A failure at one boundary does not prove that every layer is broken.

## Browser workspace and obsolete account screens

QORE currently has no account or email-confirmation flow. If an account dialog appears, the browser is serving an obsolete frontend bundle. Rebuild the frontend, restart the API process, and verify the content-hashed assets referenced by `frontend/dist/index.html`. Do not clear site data until important Explorer source is exported.

If the workspace appears new, verify the exact origin and browser profile. Localhost, `127.0.0.1`, a Render hostname, and a custom domain are separate storage origins. Never send cookies, environment values, or provider credentials in a support message.

## Saving and missing files

Confirm that the same browser profile and origin are open. Pending or failed server-save status does not erase the browser draft. Another tab may have advanced a server entry version. Export current text before reconciling copies.

Check Trash after a deletion. Restore is available for 48 hours and fails atomically if a path is occupied. Resolve that path conflict before retrying. Expired content cannot be recovered by replaying an old write. Active entries have no automatic expiry.

## Source rejection

Read the structured error and source location. Unsupported imports or expressions indicate a program outside the circuit allowlist. Reduce it to one circuit, supported gates, finite numeric parameters, and terminal measurements. Arbitrary functions, filesystem access, remote provider clients, reset, and measurement-controlled execution are not supported.

Check all limits, including the 500-operation total that counts measurements and barriers. Shot-based simulation needs at least one explicit terminal measurement. A stabilizer simulator can reject a non-Clifford circuit even when it parses; choose a compatible method.

## Busy jobs and timeouts

Each API process permits two simultaneous quantum jobs, a bounded admission wait, and a 30-second worker timeout. Retry after a short delay for busy responses. Reduce circuit complexity when work exceeds its execution budget. Repeated duplicate submissions consume browser-workspace budgets and can make a temporary issue worse.

Operators should compare memory and duration against the hosting limits. Process-local budgets do not coordinate multiple replicas. Scaling requires shared admission control and monitoring, not simply increasing every limit.

## Unexpected charts or spheres

Read source hash and execution metadata. Edited source intentionally invalidates old live output. Ideal amplitudes and Bloch vectors describe the noiseless premeasurement prefix, while noisy counts describe a separately configured sampled model. A zero local Bloch radius in a GHZ state is correct.

Matrix display is limited to four qubits, and local-state displays to six. For reversed labels, inspect the mapping: highest classical bit appears on the left; `c[0]` is on the right. Unmeasured classical bits are zero. More shots cannot repair a wrong mapping interpretation.

## Useful reports

Report the view, sanitized error code, approximate time, browser/viewport, server-reported package versions, and a minimal nonprivate circuit. State expected versus observed behavior and whether a new blank file reproduces it. Do not attach environment files, provider credentials, private source, or complete raw provider logs. The [testing guide](../operations/testing.md) explains how to reproduce numerical issues against isolated data.
