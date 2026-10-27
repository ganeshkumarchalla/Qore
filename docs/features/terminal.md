# Terminal, Output, Problems, and Debug

QORE's lower console provides typed commands for the active circuit and attached results. Its glass surface and command history resemble a development console, but the supported interface is deliberately bounded. Commands call QORE actions or display actual application data. They do not provide a general operating-system shell inside the server container.

## Understand the four surfaces

Terminal accepts a command and records its response. Output summarizes attached simulation or optimization evidence as structured text. Problems lists backend errors and parser warnings with a file and source location where available. Debug exposes current nonsecret application context such as active path, health, limits, versions, source hash, and run identifiers.

These views share a source context. If you edit a file, previous live results clear. A console command requesting counts before a run should explain that no result is attached, not print canned sample counts. A successful-looking prompt does not imply that arbitrary commands were executed.

## Run and compile commands

| Command | Action |
| --- | --- |
| `help` | Show the current supported command help |
| `run`, `simulate`, `qiskit run` | Simulate active source using workspace settings |
| `parse`, `validate`, `qiskit validate` | Execute bounded parsing and validation without sampling |
| `transpile`, `opt`, `optimize`, `qiskit transpile` | Request a Forge candidate using selected settings |
| `qiskit --version` | Show server-reported dependency versions |
| `qiskit backends` | Show last backend and reported engine limits |
| `qiskit capabilities` | Query executable languages, workflows, modules, methods, gates and safety boundary |
| `qiskit gates`, `qiskit modules`, `qiskit methods`, `qiskit limits` | Query the server-owned runtime contract |

Commands use the active source and settings; they do not accept an alternate script path or arbitrary simulator flags. Set shots, seed, noise, and optimization level through the supported workspace controls. Running again while an operation is busy should report that state instead of silently creating unrestricted parallel jobs.

The `qiskit` prefix identifies QORE shortcuts. It does not launch an installed Qiskit command-line executable. The reported versions come from the server's health information, and the backend description comes from actual attached evidence.

## Inspect real circuit evidence

| Command | Data shown |
| --- | --- |
| `qiskit draw` | Parsed circuit operations |
| `metrics`, `qiskit metrics` | Current circuit metrics |
| `statevector`, `qiskit statevector` | Available ideal complex amplitudes |
| `unitary`, `qiskit unitary` | Available circuit operator |
| `qiskit qasm` | Backend-generated OpenQASM 2.0 |
| `qiskit bloch`, `qiskit purity` | Per-qubit Bloch coordinates and reduced-state purity; undefined polar or azimuthal angles are labeled rather than printed as zero |
| `qiskit ideal` | Ideal reference probabilities attached to the current simulation |
| `qiskit bitorder` | Recorded classical mapping and bitstring convention |
| `qiskit noise` | Simulator method and applied noise configuration |
| `qiskit result`, `qiskit source-hash` | Source-matched parse, simulation and Forge provenance |
| `probs` | Sampled probabilities |
| `counts` | Actual shot counts |
| `ast` | Parsed QORE-IR, not a Python AST dump |
| `status` | Current health and engine limits |

Statevector and unitary output obey their display limits. A missing matrix above four qubits is expected. `ast` is retained as a familiar shortcut, but the displayed object is the circuit intermediate representation used by the application. Read [QORE architecture](../reference/architecture.md) for that representation's role.

## Work with the active buffer

`ls`, `tree`, and `pwd` inspect the browser workspace only. `cat`, `head`, and `wc` may read a file already present in that browser workspace. These commands never address the server container, host filesystem, environment files, or another user's workspace.

`date`, `echo`, and `clear` are console utilities. Command history is bounded. Use the help output as the authority for accepted syntax. Extra arguments to actions that take none should produce a clear warning rather than being interpreted as shell flags.

Commands such as package installation, file deletion through a host shell, remote SSH, hardware submission, or an unrelated cloud CLI are not executed. Unsupported commands should say so. This boundary protects both users and the shared service from a misleading terminal that pretends to have capabilities it lacks.

## Error locations and source truth

The parser can report a line and column for supported syntax failures. Problems associates the report with the active file and lets the user navigate to the relevant source region. Some backend failures have no precise source location, in which case a default location is only a navigation aid, not a diagnosis of that exact character.

Console output redacts common credential patterns and keeps bounded logs. Do not deliberately paste secrets into `echo` or source to test redaction: detection patterns cannot guarantee that every possible secret format is recognized. Use synthetic test values in isolated tests.

Output distinguishes simulation metadata from optimization metadata. A failed run is an error, not a zero-probability distribution. A compiler warning does not prove the candidate wrong, and a successful compilation does not prove it equivalent. Read the status and structured evidence together.

## A practical debugging sequence

Run `status` to inspect health and limits. Use `pwd` to confirm the active path and `cat` to verify the intended source. Parse or run the circuit. Read Problems for a structured failure, or `metrics` and `counts` for successful evidence. Inspect `statevector` and `unitary` only when the size and question make them relevant.

When reporting a bug, include sanitized command, error code, package versions, and minimal nonprivate source. Avoid complete raw logs that may contain user code. A screenshot of a prompt is weaker evidence than the actual structured output and source identity. Use [troubleshooting](../guides/troubleshooting.md) to distinguish a console misunderstanding from a runtime or persistence failure.
