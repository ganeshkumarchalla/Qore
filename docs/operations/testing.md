# Verification and testing

Backend tests cover parsing, simulation, optimization, source hashing, immutable evidence, browser-workspace isolation, Trash, concurrency, origin policy, provider failure, and structured errors. Production acceptance executes real Qiskit/Aer cases rather than replacing numerical behavior with mocks.

Frontend checks compile TypeScript, create the production bundle, and use Playwright to exercise onboarding, Explorer, QORE Intelligence, Lab, Forge, terminal, responsive layouts, and keyboard focus. Provider responses are mocked in UI contracts; that proves the interface contract, not live provider availability. A separate bounded provider probe verifies configuration without printing the key.

`frontend/tests/welcome-ui.cjs` starts with a clean browser profile and checks the timed splash, question and animated completion, keyboard skip, reduced motion, delayed questions, blocked visit preferences, Help → Replay Welcome, and starter-file persistence across refresh. Run it against both the Vite development URL (`node tests/welcome-ui.cjs http://127.0.0.1:5173` from `frontend/`) and the built application to catch React StrictMode initialization regressions.

The daily quality report combines security, frontend health, backend, and quantum stages. Keep the distinction between mocked evidence, real local computation, and external-service checks explicit. A red required stage blocks promotion.

`backend/tests/test_qiskit_compatibility.py` compares accepted library classes with actual Qiskit operators, exercises import aliases and broadcasting, checks export/reimport, open controls, composite compilation, noisy MCX and explicit error cases. `scripts/check_qiskit_packages.py` separately checks installed optional SDK imports in credential-free subprocesses and writes `evidence/qiskit_package_check.json`. An import pass does not establish full editor support or external-service availability. See the [compatibility matrix](../reference/qiskit-compatibility.md).

`backend/tests/test_qiskit_library_workflows.py` compares parameter binding, all advertised circuit factories, fragment mapping, inverse/control/power, complex state preparation and Pauli evolution with independent Qiskit references. It also executes the new examples through the HTTP API, compiles and validates candidates, and saves/reopens their numerical evidence. Resource tests reject oversized dimensions, repetitions and deeply shared numeric structures before expensive allocation.
