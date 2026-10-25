# Troubleshooting QORE

Separate browser state, identity, storage confirmation, source compatibility, worker execution, and interpretation when diagnosing a problem. Preserve unsaved source before reloading or signing out. A failure at one boundary does not prove that every layer is broken.

## Identity and email

If confirmation is required, follow the delivered email and sign in again. Check spelling and spam before resending. Delivery can be delayed or rate limited. Operators should verify provider email enablement, Site URL, confirmation redirects, and SMTP configuration. Health responding successfully does not establish inbox delivery.

Authentication unavailable means pending source should be preserved while the service is repaired. Production private APIs fail closed. Do not disable required auth to hide a configuration problem. Never send passwords, cookies, or confirmation URLs in a support message.

## Saving and missing files

Confirm that the same account is signed in. Pending or failed save status means the latest text is not confirmed in the database. Another tab may have advanced the entry version. Export your current text before reconciling local and server copies.

Check Trash after a deletion. Restore is available for 48 hours and fails atomically if a path is occupied. Resolve that path conflict before retrying. Expired content cannot be recovered by replaying an old write. Active entries have no automatic expiry.

## Source rejection

Read the structured error and source location. Unsupported imports or expressions indicate a program outside the circuit allowlist. Reduce it to one circuit, supported gates, finite numeric parameters, and terminal measurements. Arbitrary functions, filesystem access, remote provider clients, reset, and measurement-controlled execution are not supported.

Check all limits, including the 500-operation total that counts measurements and barriers. Shot-based simulation needs at least one explicit terminal measurement. A stabilizer simulator can reject a non-Clifford circuit even when it parses; choose a compatible method.

## Busy jobs and timeouts

Each API process permits two simultaneous quantum jobs, a bounded admission wait, and a 30-second worker timeout. Retry after a short delay for busy responses. Reduce circuit complexity when work exceeds its execution budget. Repeated duplicate submissions consume account budgets and can make a temporary issue worse.

Operators should compare memory and duration against the hosting limits. Process-local budgets do not coordinate multiple replicas. Scaling requires shared admission control and monitoring, not simply increasing every limit.

## Unexpected charts or spheres

Read source hash and execution metadata. Edited source intentionally invalidates old live output. Ideal amplitudes and Bloch vectors describe the noiseless premeasurement prefix, while noisy counts describe a separately configured sampled model. A zero local Bloch radius in a GHZ state is correct.

Matrix display is limited to four qubits, and local-state displays to six. For reversed labels, inspect the mapping: highest classical bit appears on the left; `c[0]` is on the right. Unmeasured classical bits are zero. More shots cannot repair a wrong mapping interpretation.

## Useful reports

Report the view, sanitized error code, approximate time, browser/viewport, server-reported package versions, and a minimal nonprivate circuit. State expected versus observed behavior and whether a new blank file reproduces it. Do not attach environment files, provider credentials, private source, or complete raw provider logs. The [testing guide](../operations/testing.md) explains how to reproduce numerical issues against isolated data.
