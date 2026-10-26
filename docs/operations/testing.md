# Verification and testing

Backend tests cover parsing, simulation, optimization, source hashing, immutable evidence, browser-workspace isolation, Trash, concurrency, origin policy, provider failure, and structured errors. Production acceptance executes real Qiskit/Aer cases rather than replacing numerical behavior with mocks.

Frontend checks compile TypeScript, create the production bundle, and use Playwright to exercise onboarding, Explorer, QORE Intelligence, Lab, Forge, terminal, responsive layouts, and keyboard focus. Provider responses are mocked in UI contracts; that proves the interface contract, not live provider availability. A separate bounded provider probe verifies configuration without printing the key.

The daily quality report combines security, frontend health, backend, and quantum stages. Keep the distinction between mocked evidence, real local computation, and external-service checks explicit. A red required stage blocks promotion.
