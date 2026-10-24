# QORE — PHASE 1 MVP
## Complete Product, Engineering, Architecture & Design Specification

**Product:** QORE  
**Full identity:** The Core of Quantum Development  
**Category:** Intelligent Development Environment for Quantum Software  
**Core principle:** AI proposes. Verification checks. Experiments provide the evidence.

---

# 1. Executive Summary

QORE is an intelligent quantum software development environment designed to unify quantum programming, circuit visualization, simulation, optimization, verification, and reproducible experimentation.

The goal is to make quantum software development more inspectable, measurable, and repeatable by connecting the entire development lifecycle within one coherent workspace.

Instead of treating code editing, circuit visualization, simulation, optimization, and experiment tracking as isolated activities, QORE connects them through a shared quantum intermediate representation called **QORE-IR**.

The platform follows an evidence-driven engineering philosophy: AI may propose changes, established quantum computing frameworks perform the actual computations, verification checks supported correctness properties, and experiment records preserve the evidence.

Phase 1 establishes the foundation of this platform through a functional web-based IDE, a real local quantum simulator, a circuit analysis and optimization system, appropriate validation, and persistent experiment history.

The objective is not to simulate the appearance of a complete quantum platform. It is to build a genuine, working foundation that can be extended into a broader quantum software infrastructure.

# 2. Product Vision and Problem Statement

Quantum software development involves multiple connected tasks:

- Writing quantum programs.
- Translating source code into executable circuit representations.
- Understanding gates, qubits, control relationships, and measurements.
- Simulating quantum circuits.
- Evaluating circuit complexity and resource requirements.
- Optimizing circuit implementations.
- Checking whether transformations preserve intended behavior.
- Comparing theoretical expectations with measured outcomes.
- Preserving the exact configurations and results of experiments.

When these activities are disconnected, understanding the relationship between source code, circuit transformations, simulation results, and experimental evidence becomes more difficult.

QORE aims to provide a unified engineering environment in which these relationships remain visible.

**The central problem QORE addresses:** How can quantum developers move from quantum source code to an inspectable, tested, measurable, and reproducible experiment without losing the context connecting each stage?

QORE complements existing quantum frameworks rather than assuming that established tools lack these capabilities. Its differentiation must be demonstrated through integration, transparency, reproducibility, and measurable engineering contributions.

# 3. Core Product Principles

### 3.1 AI proposes

AI assistance can explain code, suggest circuit transformations, identify possible issues, and recommend experiments. Suggestions must be distinguishable from verified outcomes.

### 3.2 Verification checks

Supported circuits and transformations should be checked using appropriate validation methods. Syntax validity alone must never be represented as proof of semantic equivalence.

### 3.3 Experiments provide the evidence

Simulation results, circuit metrics, optimization comparisons, configurations, and validation outcomes must come from real operations. Every saved experiment should retain enough information to understand how its results were produced.

### 3.4 Human approval controls changes

AI-generated or automatically generated candidate transformations must not silently overwrite the original program. Users should inspect and approve changes.

### 3.5 Scientific honesty is mandatory

QORE must distinguish theoretical values, simulated measurements, estimates, and actual hardware measurements. It must not claim quantum advantage, superior performance, or guaranteed optimization without supporting evidence.

# 4. Phase 1 MVP Scope

Build a responsive, desktop-oriented web application with six connected functional areas:

1. **QORE Studio** — quantum code editing and project management.
2. **QORE Circuit Viewer** — circuit visualization and resource analysis.
3. **QORE Lab** — real local simulation and measurement feedback.
4. **QORE Forge** — optimization, candidate comparison, and validation.
5. **QORE Intelligence** — optional context-aware AI assistance.
6. **QORE Research** — experiment history, reproducibility, and provenance.

All six areas must use consistent project and circuit data. If AI integration cannot be completed reliably, the other five areas must continue working.

## 4.1 QORE Studio

Create the primary quantum development workspace.

Required features:

- Editable source-code editor.
- Syntax highlighting for the supported programming format.
- New, open, rename, and save project operations.
- Working example projects.
- Parse, validate, and run actions.
- Clear error messages for invalid or unsupported code.
- Execution status and loading indicators.
- Unsaved-change awareness.
- Project navigation and experiment history.

Use Monaco Editor if compatible with the existing stack.

For Phase 1, implement a documented and tested subset of Qiskit-based quantum programs. Do not claim arbitrary Python or full Qiskit compatibility unless actually implemented and tested.

## 4.2 QORE-IR — Quantum Intermediate Representation

QORE-IR is the shared representation connecting the development workflow.

It must provide a consistent source of truth for:

- Qubit declarations.
- Supported quantum operations.
- Gate parameters.
- Control and target relationships.
- Measurements.
- Classical output mappings.
- Circuit ordering.
- Circuit serialization.
- Resource metrics.
- Simulation preparation.
- Optimization transformations.
- Validation.
- Experiment persistence.

Define a versioned schema and document supported operations.

The parser must convert supported source programs into a real framework circuit object or a validated normalized representation. Do not use fragile text matching as a substitute for parsing executable language constructs.

The frontend visualizer, analysis engine, simulator, and optimizer must not independently invent different interpretations of the same circuit.

Where framework-native circuit objects are used, define how they map into QORE-IR and back.

## 4.3 QORE Circuit Viewer

Render the actual circuit derived from QORE-IR.

Display:

- Qubit wires and labels.
- Quantum gates and their parameters.
- Controlled gates and connections.
- Measurement operations.
- Classical output connections.
- Circuit depth.
- Gate count.
- Two-qubit gate count.
- Applicable gate-type statistics.

Circuit visualization must update when a new supported program is parsed.

Provide clear feedback for unsupported gates and structures.

Use SVG rendering or an appropriate circuit visualization library. Avoid static diagrams presented as live circuit visualizations.

## 4.4 QORE Lab

Integrate a real local quantum simulator using Qiskit and Qiskit Aer, or a compatible documented alternative.

Required features:

- Execute supported circuits.
- Configure shot count.
- Display actual measurement counts.
- Calculate and display measurement probabilities.
- Display circuit and simulator metadata.
- Show execution errors and warnings.
- Distinguish theoretical probabilities from finite-shot measurements.
- Preserve the configuration used for an experiment.

### Required demonstration: Bell-state circuit

Implement a working Bell-state example:

1. Apply a Hadamard gate to the first qubit.
2. Apply a CNOT gate using the first qubit as control and the second as target.
3. Measure both qubits.

Under ideal conditions, the expected outcomes are `00` and `11`, each with probability approximately 50%. The other two outcomes should have probability approximately zero.

Actual finite-shot measurements may vary.

Account for Qiskit's classical bit-string ordering and explain the displayed mapping clearly.

Use this experiment to demonstrate circuit construction, visualization, execution, measurement distributions, and interpretation.

Do not present Bell-state correlation as evidence of quantum computational advantage.

## 4.5 QORE Forge — Optimization and Verification

QORE Forge is the principal technical component of Phase 1.

Implement a working pipeline that creates an optimized candidate from an original circuit using a supported quantum compiler optimization pass.

Required functionality:

- Preserve the original circuit.
- Generate a separate candidate.
- Record the optimization pass and settings.
- Render both circuit versions.
- Calculate comparable metrics.
- Display absolute and relative differences where meaningful.
- Explain the transformation at a useful level.
- Validate supported semantic properties.
- Allow the user to inspect and approve the candidate.

Metrics should include applicable measures such as:

- Gate count.
- Circuit depth.
- Two-qubit gate count.
- Qubit count.
- Gate-type distribution.

Document whether measurements, barriers, and other instructions contribute to each metric.

Use established compiler optimizations as the baseline. Clearly identify framework-provided transformations versus any original QORE-specific method.

Do not hardcode performance improvements. If optimization does not improve a metric, display the actual result.

### Validation requirements

Use a suitable method for the supported circuit and transformation, such as statevector comparison up to global phase for applicable small unitary circuits, or output-distribution comparison under controlled equivalent simulation settings.

Handle measurements, classical operations, and unsupported constructs according to the selected validation method.

Report one of the following as appropriate:

- Validated under the stated method.
- Validation failed.
- Validation unavailable.
- Validation inconclusive.

Do not equate successful parsing or compilation with proof of equivalence.

## 4.6 QORE Intelligence

Provide an optional AI assistant grounded in the current project and available execution data.

It should be able to:

- Explain supported quantum source code.
- Describe gates and circuit structure.
- Interpret simulator outputs.
- Explain resource metrics.
- Summarize optimization differences.
- Suggest possible improvements.
- Help diagnose errors.
- Recommend experiments.

AI responses must be grounded in actual code, circuit metadata, and results when relevant. The assistant must never claim that it executed a program or verified a transformation when that operation did not occur.

Use a server-side API integration, such as Gemini, only when credentials and access are available.

Keep credentials server-side, use environment variables or an appropriate secret manager, and provide graceful handling when the AI service is unavailable.

AI must remain an optional assistance layer rather than a dependency for core quantum functionality.

## 4.7 QORE Research — Reproducibility Ledger

Create persistent project and experiment records.

Store applicable information such as:

- Project and experiment identifiers.
- Source code.
- Source-code SHA-256 hash.
- QORE-IR version.
- Framework and simulator versions.
- Backend identifier.
- Shot count.
- Random seed, where supported and configured.
- Circuit metrics.
- Optimization settings.
- Original and optimized representations.
- Simulation results.
- Validation method and outcome.
- Execution metadata.
- Timestamps.
- Errors and warnings.

Use SQLite for the initial persistence layer.

Provide the ability to list, save, reopen, and inspect previous experiments.

Historical results must remain distinguishable from newly executed results.

A source hash supports identification of code content, but must not be presented as proof of execution correctness. Preserve the associated configuration and relevant dependency metadata as well.

If exact reproducibility cannot be guaranteed, clearly state why.

# 5. Complete End-to-End Workflow

The flagship demonstration must work through one connected interface:

**Open Project → Edit Code → Parse → Visualize → Analyze → Simulate → Optimize → Validate → Compare → Save → Reopen**

1. Open the Bell-state example.
2. Parse the supported program into QORE-IR.
3. Render the actual circuit.
4. Display circuit resource metrics.
5. Execute a genuine local simulation.
6. Show measurement counts and probabilities.
7. Create an optimized candidate using a real compiler pass.
8. Compare original and candidate circuits.
9. Run an appropriate validation check.
10. Save the source, configuration, results, and provenance.
11. Reopen the experiment and confirm that its historical record is preserved.

Every stage must operate on actual application data. A visually complete screen without working backend functionality does not satisfy this requirement.

# 6. Architecture and Technology Stack

Follow the architecture specified in the submitted QORE presentation.

### Frontend

- React.
- TypeScript.
- Tailwind CSS.
- Monaco Editor.
- SVG-based circuit rendering or a suitable visualization library.
- Charts for measurement distributions and metric comparisons.

### Backend

- Python.
- FastAPI.
- Pydantic.
- Qiskit.
- Qiskit Aer or a compatible local simulator.
- SQLite.
- pytest.

### Architecture layers

**Presentation layer:** IDE, editor, circuit viewer, simulation panels, optimization comparisons, experiment history.

**Application layer:** project workflows, execution orchestration, validation, optimization, experiment management.

**Quantum processing layer:** parsing, QORE-IR conversion, circuit construction, simulation, resource analysis, optimization and validation.

**Persistence layer:** projects, experiment records, configurations, results, provenance and version metadata.

Use structured API contracts and consistent error responses.

The application must start locally with documented setup instructions. Adapt to the existing repository rather than replacing a working architecture without justification.

# 7. Safe Execution Architecture

The submitted presentation specifies static AST pre-validation, a controlled namespace, an isolated runtime, and deterministic resource caps.

Implement a security-conscious approach that reflects these goals.

Required safeguards:

- Restrict the supported input constructs.
- Validate source before execution.
- Avoid unrestricted execution of arbitrary user-provided Python.
- Use a controlled namespace.
- Apply execution timeouts and resource limits.
- Isolate execution where feasible.
- Limit filesystem and network access.
- Validate API inputs.
- Keep API credentials out of the frontend.
- Handle oversized and malformed requests.
- Prevent a failed run from crashing the entire application.

Static AST validation alone is not a complete sandbox. If execution isolation cannot be implemented reliably, construct supported circuits through a constrained interpreter or controlled circuit-building layer instead of executing arbitrary Python.

Document the actual security guarantees and limitations.

# 8. Extension API and Future Ecosystem

Design QORE's internal architecture to support future extension points.

Potential extension categories include:

**Hardware connectors:** provider-specific quantum processing unit adapters.

**Compiler passes:** additional circuit transformations.

**AI and analytics plugins:** diagnostic tools and experiment analysis.

A future extension contract may expose interfaces conceptually similar to:

- `provider.execute(job)`
- `pass.run(circuit)`
- `plugin.analyze(run)`

These are interface concepts, not a claim that a stable public plugin API already exists.

For Phase 1, implement only the extension points that are necessary and testable. Document future interfaces instead of creating empty integrations.

# 9. Reproducibility and Experiment Telemetry

Every experiment should have a traceable record connecting its source, configuration, execution, and output.

The submitted presentation identifies source hashing, side-by-side comparisons, total variation distance (TVD), and persistent audit trails as important elements.

Implement these carefully:

- Calculate source hashes from actual source content.
- Preserve the backend and simulator configuration.
- Record shot count and seed when applicable.
- Save original and optimized circuit metrics.
- Preserve the results used in a comparison.
- Store the validation method and outcome.
- Calculate TVD only when valid probability distributions are available.

For discrete probability distributions \(P\) and \(Q\), total variation distance is:

\[
\operatorname{TVD}(P,Q)=\frac{1}{2}\sum_x |P(x)-Q(x)|
\]

Explain what two distributions are being compared. For example, a simulated measurement distribution may be compared with an ideal reference distribution.

Do not copy illustrative telemetry values from a mockup and present them as measured application results.

# 10. Interface and Visual Design System

The implementation must follow the submitted QORE presentation's visual identity.

### Color palette

- **Primary background:** `#080B14`
- **Panel background:** `#0F1523` or a visually compatible deep navy.
- **Primary text:** `#F4F7FF`
- **Secondary text:** accessible muted gray.
- **Cyan accent:** `#57D9FF`
- **Violet accent:** `#9A83FF`
- **Borders:** subtle blue-gray with restrained cyan or violet emphasis.

Use the values above as design tokens, allowing adjustments only when necessary for contrast and consistency with the presentation.

### Visual language

- Dark scientific developer-tool aesthetic.
- Bold white headings.
- Cyan monospace section labels and technical metadata.
- Violet accents for secondary technical emphasis.
- Thin borders.
- Subtle radial ambient glows.
- Carefully layered navy surfaces.
- Restrained transitions and hover states.
- Clear visual hierarchy.
- Consistent spacing and alignment.

Avoid generic dashboard styling, excessive gradients, decorative glass effects, unnecessary animation, and inconsistent colors.

### Application layout

**Left sidebar:** projects, source files, examples, experiments.

**Main workspace:** source editor and circuit visualization.

**Results panel:** simulation output, measurements, resource metrics, optimization and validation status.

**Optional assistant panel:** context-aware AI assistance.

**Top navigation:** project controls and the main workflow actions.

Make the layout responsive. Desktop is the primary target, while smaller screens should retain access to essential functions through appropriate panels or tabs.

### Interface states

Implement real states for:

- Empty workspace.
- Project loaded.
- Parsing.
- Parse success or failure.
- Simulation in progress.
- Simulation results.
- Simulator error.
- Optimization in progress.
- Optimization results.
- No measurable improvement.
- Validation success, failure or unavailable.
- Experiment saved.
- Experiment reopened.
- AI unavailable.

Every primary button must perform its advertised action.

# 11. Competitive Positioning

QORE should be positioned as an integrated, evidence-driven quantum development environment that can complement existing quantum software ecosystems.

Relevant ecosystems include Qiskit, Cirq, Microsoft Quantum Development Kit, and OpenQASM-compatible tools.

Do not claim that QORE replaces these tools or provides superior quantum computation simply because it combines their general workflow stages.

The defensible value proposition is the connection between:

- Source code and circuit representation.
- Circuit visualization and resource metrics.
- Simulation and measurement analysis.
- Optimization and candidate validation.
- Experiment outputs and reproducible provenance.

Any claim of novelty or performance improvement must be supported by actual implementation evidence or reproducible measurements.

# 12. Testing and Acceptance Criteria

### Parsing tests

Test valid supported programs, invalid syntax, unsupported operations, malformed inputs, and measurement mapping.

### Circuit tests

Verify gate order, control-target relationships, visualization consistency, and metric calculations.

### Simulation tests

Test Bell-state behavior, shot count, probability calculations, bit ordering, and execution failures.

### Optimization tests

Confirm that the original circuit is preserved, the candidate comes from a real optimization pass, metrics are calculated consistently, and non-improving results are reported honestly.

### Validation tests

Verify the selected equivalence or behavioral comparison method and confirm that unsupported cases are not incorrectly marked as validated.

### Persistence tests

Test project saving, experiment creation, retrieval, reopening, and preservation of historical results.

### Security tests

Test request validation, supported-source restrictions, secret handling, resource limits, and error recovery.

### Final acceptance test

A user must be able to complete the entire Bell-state workflow in the actual running application. The application must execute real operations, display their actual outputs, and reopen the saved experiment.

Report only tests that were actually executed.

# 13. Implementation Roadmap

### Phase 1A — Foundation

Inspect the existing codebase, preserve working functionality, establish the supported source subset, define QORE-IR, and implement backend/frontend communication.

### Phase 1B — Core Quantum Workflow

Implement Studio, parsing, circuit visualization, circuit metrics, local simulation, and the Bell-state demonstration.

### Phase 1C — QORE Forge

Implement optimization, original-versus-candidate comparison, appropriate validation, and transparent reporting.

### Phase 1D — QORE Research

Implement SQLite persistence, experiment provenance, saved project retrieval, and experiment reopening.

### Phase 1E — Product Quality

Apply the final visual system, improve accessibility and responsive layouts, add loading and failure states, and execute the automated tests.

### Phase 1F — Optional Intelligence

Integrate grounded AI assistance only after the core workflow is reliable.

Do not start future platform modules while critical Phase 1 acceptance criteria remain unmet.

# 14. Long-Term Roadmap

The presentation identifies three horizons.

**Horizon 1 — Foundation**

- Local quantum IDE.
- QORE-IR.
- Circuit visualization.
- Aer simulation.
- Forge optimization.
- Debugging and experiment persistence.

**Horizon 2 — Connected Development**

- Cloud synchronization.
- Multi-user collaboration.
- Hardware and provider adapters.
- Hybrid quantum-classical workflows.
- Expanded optimization and debugging.

**Horizon 3 — Broader Quantum Infrastructure**

- Expanded framework integrations.
- Advanced AI-assisted engineering.
- Research and benchmarking infrastructure.
- Support for larger and more sophisticated quantum workloads.
- Enterprise-oriented and industrial workflows where technically justified.

These horizons represent the product direction, not completed Phase 1 features.

# 15. Definition of Done

Phase 1 is complete when:

- The application starts using documented instructions.
- Users can edit and save supported quantum programs.
- QORE-IR consistently represents the supported circuits.
- The circuit viewer reflects actual parsed data.
- The local simulator returns genuine results.
- Resource metrics are computed from real circuit objects.
- QORE Forge creates and compares real optimization candidates.
- Appropriate validation is performed and accurately reported.
- Experiments can be saved and reopened.
- The provenance record captures relevant source and execution metadata.
- The visual design matches QORE's submitted identity.
- Critical automated tests have been executed.
- Unsupported operations and incomplete capabilities are documented.
- No fake metrics, hardcoded execution results, or simulated success states are presented as real.

# 16. Required Final Engineering Report

At the end of implementation, provide:

1. Repository assessment and existing functionality.
2. Features implemented.
3. Actual technology stack.
4. Architecture and QORE-IR design.
5. Supported source constructs and limitations.
6. Setup and execution instructions.
7. Actual automated test results.
8. Actual Bell-state simulation output.
9. Actual optimization comparison.
10. Validation method and result.
11. Persistence and experiment-reopening results.
12. Security measures and remaining limitations.
13. Known bugs and unfinished features.
14. Screenshots of the running application.
15. Recommended next engineering priorities.

Clearly distinguish implemented features, verified outcomes, planned features, and untested claims.

Do not fabricate successful tests, performance gains, circuit equivalence, or execution statistics.

# Final Implementation Directive

Inspect the existing repository first. Preserve working code and existing functionality wherever possible.

Implement QORE as a cohesive quantum software development environment following the submitted presentation's visual identity, modular architecture, and evidence-driven philosophy.

Prioritize the complete workflow:

**Write Code → Visualize → Simulate → Analyze → Optimize → Validate → Compare → Save → Reopen**

Use genuine quantum framework operations, real simulation results, transparent optimization comparisons, appropriate verification, and persistent experiment provenance.

Build the smallest complete and reliable implementation that satisfies the acceptance criteria. Run the available tests, fix failures, document limitations, and report the actual results.

The goal is not to make QORE look finished. The goal is to make its core engineering workflow genuinely work.