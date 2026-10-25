# Bloch spheres and reduced states

The Bloch sphere represents a single-qubit density matrix with coordinates `x`, `y`, and `z`. Pure states lie on the surface; mixed states lie inside. QORE reports purity and labels whether the reduced state is pure within its numerical policy.

For an entangled register, an individual qubit can have a centered Bloch vector even though the complete multi-qubit state is pure. This is expected for GHZ and Bell states: local information is mixed while correlations live in the joint state. A centered vector is therefore not by itself evidence of failed preparation.

Rotate the 3D view for orientation, but read the numeric vector, purity, source, and run metadata for analysis. Animation is a navigation aid rather than experimental evidence.
