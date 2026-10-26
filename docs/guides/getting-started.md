# Getting started with QORE

QORE gives a quantum experiment a clear path from source to evidence. Studio is where you write and organize code. Quantum Lab runs a supported circuit and exposes its sampled output and ideal state. Forge creates a compiler candidate for comparison. Research Ledger preserves the source and results as immutable evidence. The optional assistant sits beside these views in its own secondary sidebar.

## Begin with your own workspace

On a first visit, the animated welcome closes automatically. The fixed graphite interface stays consistent across views. Explorer initially contains no example files or projects. Create a blank file to start from scratch, or select **Get Started** to create one editable three-qubit learning circuit. That is an explicit action and is never repeatedly inserted on refresh.

No account or sign-in is required. Editable files persist in the browser profile, and the backend assigns an opaque HttpOnly workspace cookie for browser-scoped projects, runs, and Ledger records. The cookie is not a verified identity, so use a separate browser profile on a shared computer and export important source before clearing site data.

## Navigate the workbench

Explorer holds editable files and folders. Select a supported circuit file to open Monaco with its source and visible path. Lab and Forge appear beside Explorer and expand when it closes. The assistant opens in a secondary bar beside the current view. The console below the workspace accepts supported commands; Problems presents reported errors and warnings.

On a laptop, close Explorer or the assistant when inspecting a dense matrix. Results regions scroll within their panels. Source editing and result inspection are separate activities: changing the active code clears live results that belong to the previous source. It does not rewrite earlier runs stored in the Ledger.

## Run a circuit

A shot-based simulation requires terminal measurements. Confirm that the source uses [the supported language](../reference/circuit-python.md), choose shots and seed, then run the kernel. The API parses the circuit into QORE-IR, validates limits, and runs Qiskit Aer in a bounded worker. Unsupported imports are compatibility errors. Installing a package does not make arbitrary source executable through the editor.

Read the backend label and execution metadata before interpreting the chart. Counts should sum to the requested shots. Sampled probabilities divide those counts by shots. The ideal reference is computed separately from the noiseless unitary prefix under the same classical mapping. A finite difference between those distributions is expected even in ideal mode.

Open State World for a spatial interpretation, then inspect Bloch vectors and matrices when the circuit size permits. Matrix display ends above four qubits; ideal local-state and amplitude displays end above six. Those display bounds differ from the ten-qubit simulation limit.

## Keep source and evidence

Saving a file preserves editable source in browser storage. Saving an experiment preserves a separate SQLite historical snapshot with its source and attached execution evidence. A later file edit cannot alter the old snapshot. Name experiments according to the question you tested, such as `GHZ baseline, 1024 shots`, rather than treating every execution as interchangeable.

Forge adds a deliberate review step. Compare the original and candidate, resource metrics, validation status, and measurement mapping. Apply a candidate only after reviewing its scope, then run the changed source for fresh sampled evidence. The compiler may change the gate basis without reducing gate count.

## Finish the session

Wait for saved status before closing a tab. Export important source before clearing browser storage. On a shared computer, use a separate operating-system or browser profile because QORE intentionally has no account boundary in this release.

Use Undo immediately after an accidental deletion, or open Trash to restore another eligible entry within 48 hours. Folder restore checks occupied paths. Active files have no automatic expiry. The [first experiment](first-experiment.md) gives a complete prediction-to-Ledger walkthrough; [troubleshooting](troubleshooting.md) separates storage, execution, provider, and interpretation problems.
