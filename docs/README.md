# QORE documentation

QORE connects circuit authoring, numerical execution, visual inspection, compiler comparison, and historical evidence. This manual describes the product and its bounded runtime for learners, researchers, maintainers, and service operators. Each topic has a separate page so you can follow a task, study a concept, or find an exact interface without searching a single oversized document.

Begin with an empty Explorer—no account is required. Create a blank file, or explicitly choose Get Started to create one editable three-qubit starter. Browser storage retains editable source across refreshes; browser-scoped SQLite records preserve projects, runs, and Research Ledger evidence when the server has durable storage.

![QORE workflow](assets/animations/workflow.gif)

## Guides

| Page | Purpose |
| --- | --- |
| [Getting started](guides/getting-started.md) | Navigate and complete a first session |
| [Workspace files](guides/workspace-files.md) | Create, organize, edit, delete, undo, and restore source |
| [Local development](guides/local-development.md) | Install, build, and run the application |
| [Files and recovery](guides/workspace-files.md) | Edit, organize, synchronize, delete, and restore |
| [First experiment](guides/first-experiment.md) | Predict and inspect a GHZ circuit |
| [Learning path](guides/learning-path.md) | Progress from one qubit to algorithms |
| [Troubleshooting](guides/troubleshooting.md) | Diagnose identity, save, runtime, and display issues |

## Feature manuals

- [Studio](features/studio.md): Explorer, paths, editing, state, and responsive panels.
- [Quantum Lab](features/quantum-lab.md): simulation settings, distributions, noise, and metadata.
- [State World](features/state-world.md): orbital state views, spheres, amplitudes, and matrices.
- [Forge](features/forge.md): compilation, resource comparisons, validation, and approval.
- [Research Ledger](features/research-ledger.md): runs, experiments, immutable evidence, and restoration.
- [Assistant](features/assistant.md): secondary sidebar, source-matched context, and privacy.
- [Terminal](features/terminal.md): supported commands, output, and error locations.

## Quantum concepts

- [Foundations](quantum/foundations.md), [gates and circuits](quantum/gates-circuits.md), [measurement](quantum/measurement.md).
- [Entanglement](quantum/entanglement.md), [Bloch spheres](quantum/bloch-spheres.md), [unitary matrices](quantum/unitary-matrices.md).
- [Noise and sampling](quantum/noise-sampling.md), [equivalence](quantum/equivalence.md), [reproducibility](quantum/reproducibility.md).
- [Grover search](quantum/grover.md), [QAOA](quantum/qaoa.md), [applications](quantum/applications.md).

## Developer reference

- [Architecture](reference/architecture.md), [data model](reference/data-model.md), [configuration](reference/configuration.md).
- [Core API](reference/api.md), [workspace API](reference/workspace-api.md).
- [Circuit Python](reference/circuit-python.md), [OpenQASM](reference/openqasm.md), [gate catalog](reference/gate-catalog.md), [limits](reference/limits.md).

## Operations

- [Deployment](operations/deployment.md), [security](operations/security.md), [testing](operations/testing.md).
- [Scaling](operations/scaling.md), [backup and recovery](operations/backup-recovery.md), [releases](operations/releases.md).
- [Production checklist](PRODUCTION.md), [daily reviews](AUTOMATED_REVIEWS.md).

## Use evidence within its scope

Ideal amplitudes describe a noiseless state before measurement. Shot counts are finite samples from the selected simulator and noise settings. A Bloch sphere describes one reduced qubit, which can be mixed while the complete register is pure. An operator validation applies to its recorded method, size limit, and tolerance. These are related forms of evidence, but they answer different questions.

Examples in this manual are optional learning material, never records inserted into an account by the documentation build. [Asset provenance](assets/BRAND_ASSETS.md) records the origins of brand marks and the illustrative nature of animation values. The actual API response is the authority for a particular execution.
