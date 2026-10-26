# Measurement and bit ordering

Measurement maps qubits into classical bits. The displayed bitstring places the highest classical index on the left and `c[0]` on the right, following the recorded Qiskit convention. A mapping such as `q[0] → c[1]` means the observed value of qubit zero appears in the second classical position, not necessarily at the right edge.

Counts are integers summing to shots. Sampled probabilities are counts divided by shots. Ideal probabilities come from the noiseless unitary prefix under the same mapping. Total variation distance summarizes the difference between distributions but does not explain its cause; sampling, modeled noise, mapping errors, or changed source must be considered separately.

Always read the bit-ordering metadata attached to the run. Do not relabel strings to match intuition, because that destroys reproducibility.
