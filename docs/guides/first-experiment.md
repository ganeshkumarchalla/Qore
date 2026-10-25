# Your first three-qubit experiment

This lesson prepares and measures a three-qubit GHZ state. A short circuit gives a clear ideal prediction, correlated outcomes, and a useful distinction between the complete quantum state and each reduced qubit. Enter the code yourself, or use the explicit Get Started action; the documentation does not preload account files.

## Create and predict

Create `ghz.py` and enter:

```python
from qiskit import QuantumCircuit

qc = QuantumCircuit(3, 3)
qc.h(0)
qc.cx(0, 1)
qc.cx(1, 2)
qc.measure(0, 0)
qc.measure(1, 1)
qc.measure(2, 2)
```

H prepares qubit zero in equal superposition. Controlled-X operations correlate the remaining qubits. The ideal premeasurement state is `( |000> + |111> ) / sqrt(2)`. Each terminal measurement writes to the matching classical index.

Only `000` and `111` have nonzero ideal probability, each one half. At 1,024 shots, counts should be around 512 each, not necessarily exactly 512. The seed supports repeating a configuration under the same software but does not change the statistical meaning.

## Execute and read the result

Choose 1,024 shots, seed 42, and ideal statevector simulation. Run the kernel. Verify the reported backend and total shot count. Compare the sampled histogram with the analytic reference rather than judging it by visual symmetry alone. TVD is one summary of the observed distribution difference.

Inspect the nonzero ideal amplitudes. Each has magnitude about `0.7071`, with squared magnitude one half. Display values are rounded; the internal comparison uses greater precision. Source and settings stay attached to this result, and a later source edit clears the live view.

## Interpret the spheres and matrix

The complete register is pure, but tracing out two qubits leaves each individual qubit maximally mixed. Its local Bloch vector has radius zero and purity `0.5`. A vector at the center is the expected result. One sphere cannot show all correlations of an entangled register.

Because this circuit has three qubits, QORE can also display its eight-by-eight unitary matrix. That matrix describes the unitary prefix on every basis input. It does not include measurement and is not a table of sampled probabilities. The statevector is only the matrix's action on the initialized input, so it contains less information than the complete operator.

## Use Forge and preserve evidence

Request a compiler candidate in Forge. This circuit is already small, so fewer gates are not guaranteed. Read the resource conventions, operator comparison, and exact measurement mapping. An unavailable result is not validated. If you apply the candidate, run the changed source again before comparing histograms.

Save the editable file and wait for confirmation. Save a named experiment with the current run, then reopen it through the Ledger. That snapshot remains unchanged when you later edit the workspace file. A clone or an explicit edit starts a new variation.

## Extend one variable at a time

Replace the first H with `qc.ry(0.6, 0)`. Predict that the two allowed outcomes now have unequal probabilities determined by the rotation. Run with the same shots and seed. Next add a modest readout-error setting and explain why sampled outcomes can appear outside the two ideal strings while the ideal state remains unchanged.

Record source, shots, seed, method, and noise for each variation. This habit makes the lesson a reproducible experiment instead of a collection of unrelated screenshots. Continue with [measurement ordering](../quantum/measurement.md), [entanglement](../quantum/entanglement.md), and [QAOA](../quantum/qaoa.md).
