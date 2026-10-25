# A learning path through quantum experiments

Use QORE to test a prediction, inspect evidence, and preserve a record. Start with circuits whose expected behavior you can calculate. Complex visualizations become easier to read when you already know what a one-qubit amplitude, a classical measurement bit, and a mixed local state mean.

## One qubit and sampling

Begin with one qubit, one classical bit, and a terminal measurement. The empty unitary prefix yields zero. X yields one. H yields equal ideal probabilities. Vary shots and observe that sampled frequencies approach the prediction without becoming a mathematical guarantee for every run.

Two H gates return the initial state. This is a first example of interference: coherent amplitudes combine before measurement. Compare `H; Z; H` with X. Relative phase can change a later histogram even when it leaves an earlier basis probability unchanged.

## Rotations and visual state

Try `ry(theta, 0)` for several angles. Compare the Bloch vector and ideal probabilities. Create superposition before applying `rz`, then add H to make the phase observable through a final basis measurement. Explain which view describes a state and which describes a transformation.

Read [Bloch spheres](../quantum/bloch-spheres.md) and [unitary matrices](../quantum/unitary-matrices.md). Avoid inferring an unknown state from a single histogram. QORE's ideal state is calculated from known source, whereas experimentally reconstructing a physical state would require additional measurements.

## Two and three qubits

Prepare a Bell state with H and CX, then follow the three-qubit GHZ lesson. Inspect local purity and explain why a zero local vector can coexist with a pure global state. Swap classical measurement destinations and predict the displayed bitstrings before running.

Compare a correlated distribution with an entangled pure state that has the same computational-basis counts. Those counts alone do not distinguish every quantum property. This is an opportunity to practice making claims supported by the available evidence rather than the visual effect.

## Algorithms and objective functions

Use [Grover search](../quantum/grover.md) to identify the oracle and diffusion step. Calculate the target outcome first. Then study [QAOA](../quantum/qaoa.md), where the result is an expected classical objective, not simply the most attractive bitstring.

For a graph cut, calculate a cut score for sampled strings and compare against uniform sampling. Keep graph, angles, shots, seed, and source together. A small simulator exercise demonstrates an algorithm workflow; it does not establish a speedup over a classical solver.

## Verification and reproducibility

Use Forge on a circuit containing deliberate redundant gates. Compare metrics under one convention and inspect the operator validation. Save the original and candidate as separate experiments. Increasing shots reduces sampling uncertainty but cannot fix the wrong measurement mapping, source version, or noise interpretation.

Finish by reading [runtime limits](../reference/limits.md), [security](../operations/security.md), and [reproducibility](../quantum/reproducibility.md). Knowing where the model stops is part of learning a quantum tool. When a program exceeds the supported runtime, simplify its circuit-building portion for QORE and keep broader classical workflows in an appropriately configured external development environment.
