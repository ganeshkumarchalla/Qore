# Circuit equivalence

Forge compares original and candidate operators up to global phase for circuits within the six-qubit validation bound. It also checks terminal measurement mapping. A small numerical residual within the documented tolerance supports equivalence for that exact method and source; it is not a universal proof for larger or dynamic circuits.

Gate-count or depth improvement does not imply equivalence. Conversely, an equivalent candidate may use more gates after basis decomposition. Review validation status, method, residual, measurement mapping, warnings, and source before applying a candidate. After application, rerun the changed source to produce fresh sampled evidence.
