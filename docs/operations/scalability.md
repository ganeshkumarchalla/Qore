# Scalability and capacity

QORE currently limits each API process to two concurrent quantum jobs and two concurrent Gemini calls. Budgets and queues are process-local. Horizontal replicas therefore require a shared rate limiter, durable job queue, centralized evidence store, and consistent browser-workspace routing before they represent one coherent service.

Profile memory by circuit size and simulator method. Statevector cost grows exponentially with qubit count; the ten-qubit product limit is a correctness guard, not a complete capacity plan. Set host memory alerts, request latency metrics, worker timeout counts, provider error rates, and persistent-disk alerts.

Static frontend assets can be cached aggressively because their names are content-hashed. API responses, workspace HTML, and private evidence use no-store/noindex behavior. Scale the static and compute paths independently only after preserving same-origin security and cookie semantics.
