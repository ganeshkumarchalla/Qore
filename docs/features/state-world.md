# State World and visual state inspection

State World is QORE's spatial view of simulation evidence. It complements distributions, amplitudes, Bloch vectors, and matrices with interactive 3D inspection. The shared graphite gradient and glass controls keep it part of the same workbench. Motion helps navigation and emphasis; the numerical readout remains the authority for probability, phase, and state identity.

## Different visualizations, different objects

A quantum register state, a one-qubit reduced state, a unitary transformation, and a histogram are not interchangeable. State World presents basis-state information. A Bloch sphere presents one qubit's reduced state. An amplitude table exposes complex coefficients. A unitary matrix describes a transformation on every possible input. A histogram shows sampled classical outcomes.

These views can agree with one another without looking similar. An entangled GHZ state has two nonzero basis probabilities, yet every local Bloch vector is at the sphere center. A phase change can leave a histogram unchanged and still alter interference later. Understanding the object behind each view avoids reading decorative movement as an additional measurement.

## Basis states in State World

Basis labels identify bitstrings under the view's stated convention. Interactive selection lets you inspect a state without relying on the size or glow of a moving element. Read the associated probability and sampled count where available. A missing sampled count does not imply an exactly zero ideal probability at finite shots.

Use the backend result as the reference when comparing visual emphasis. The visual scene may compress dynamic ranges for legibility. Camera angle, orbit, glow, or a selected-node highlight does not create a new physical observable. Any conclusion about distribution quality belongs to the returned probabilities, counts, and TVD.

The Lab's metadata remains attached below the primary result. Check source hash and configuration before comparing two scenes. Source edits clear stale live results; immutable historical runs can still be reopened through the Ledger.

## Focused Bloch mode

Focused mode enlarges the selected qubit inside the shared gradient surface. Drag to inspect its 3D geometry and axes, then read numerical information below the sphere. The vector coordinates are expectation values of the Pauli X, Y, and Z operators for that qubit's reduced density matrix.

The vector radius is `sqrt(x*x + y*y + z*z)`. A pure one-qubit state lies on the sphere surface. A mixed state lies inside it. The maximally mixed state is at the center. The readout's purity is `Tr(rho*rho)`, equal to `(1 + r*r)/2`; radius itself is not purity.

For an unentangled `|0>` qubit, expect z approximately one. H maps it to the positive x direction. A Y-axis rotation changes x and z according to the angle. In a Bell or GHZ state, the local vector can vanish. These are ideal model states computed before measurement, not reconstructed device tomography.

## All-qubit mode

All-qubit mode displays several spheres on one shared background instead of enclosing each in a separate card. Sphere sizes adapt to the selected qubit count and available width. Axes and interaction remain consistent with focused mode. A laptop viewport may require a smaller arrangement or scrolling when labels and readouts need space.

Use the common numerical convention when comparing qubits. The spheres describe separate reduced states, so they do not directly draw the full entanglement structure between them. Equal local vectors do not mean the full register states are equal. A set of local marginals cannot generally reconstruct all multi-qubit correlations.

## Amplitudes and phase

An amplitude is a complex number `a + i*b`. Its probability is `a*a + b*b`; its phase is the complex argument. QORE displays real and imaginary parts, magnitude, phase, and probability within the supported size. Values are rounded to make tables readable, and tiny components can be omitted under the documented display threshold.

Two states can have identical basis probabilities with different relative phases. Prepare H, apply Z, then apply H again to see phase become a different output probability. A single amplitude table row does not carry the normalization or relative-phase context of the whole state, so inspect the complete relevant state before making an inference.

## Matrix inspection

Unitary display is available for up to four qubits. A two-qubit operator is four by four, a three-qubit operator eight by eight, and a four-qubit operator sixteen by sixteen. Each column is the output amplitude vector for one basis input. Rows identify output basis states.

A cell's magnitude is not a shot frequency. It describes an amplitude of the transformation. Squaring magnitudes gives basis transition probabilities for that particular basis input, but interference for a superposed input depends on complex sums across columns. Rounded display values should not be used as a substitute for full-precision verification.

## Accessibility and motion

Use numerical readouts and tables when 3D motion makes comparison difficult. Focused and all-qubit modes should remain usable without depending on a subtle animated highlight. Respect reduced-motion preferences for decorative transitions where supported. The README offers static posters because a GIF itself does not inherit the browser's reduced-motion media query.

Close Explorer or the assistant for more space when comparing a dense matrix or multiple spheres. The goal is a clear scientific reading, not maximum animation density. Report clipped labels with the viewport dimensions and view mode so the layout can be reproduced.

## Troubleshooting visual conclusions

If a sphere appears centered, check purity and the known global state before assuming a rendering error. If a matrix is empty above four qubits, that is the display cap. If sampled and ideal views disagree, read noise settings and shot count. If an outcome label seems reversed, inspect classical measurement mapping. For exact comparisons, use the result data and the [measurement](../quantum/measurement.md), [Bloch](../quantum/bloch-spheres.md), and [matrix](../quantum/unitary-matrices.md) lessons.
