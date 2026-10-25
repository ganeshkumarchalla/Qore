# Quantum computing foundations

A qubit is described by complex amplitudes whose squared magnitudes sum to one. Relative phase affects later interference even when it is invisible in an immediate computational-basis measurement. Multiple qubits live in a joint state space; entanglement means that state cannot be separated into independent single-qubit states.

Gates are unitary transformations. Measurement converts a quantum state into classical outcomes sampled according to probability, so finite-shot counts fluctuate. A simulator can retain exact statevector evidence before measurement and also sample shots; those are different objects and should not be conflated.

QORE makes this distinction visible through circuit structure, ideal probabilities, sampled distributions, amplitudes, reduced Bloch vectors, and metadata. It does not claim hardware execution or quantum advantage. Use small circuits to form a prediction first, then compare the recorded result and limitation statement.
