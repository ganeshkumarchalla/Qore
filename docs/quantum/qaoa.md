# QAOA and graph-cut experiments

QAOA alternates a cost evolution encoding an optimization objective with a mixer that redistributes amplitude. For a graph-cut example, computational-basis strings represent partitions and the cost rewards edges crossing the partition. Parameters determine the interference pattern; measurement samples candidate strings rather than proving an optimum.

Use `openqasm/qaoa_cut.qasm` as a four-qubit inspection case. Verify its gate structure, matrix within display limits, ideal amplitudes, sampled distribution, and classical mapping. Record shots, seed, simulator method, and source hash. A high-frequency bitstring is evidence from that configured run—not a guarantee about every parameter choice or hardware execution.
