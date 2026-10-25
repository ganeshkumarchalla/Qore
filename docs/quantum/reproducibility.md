# Reproducibility and evidence

Reproducibility requires exact source, source hash, shot count, seed, simulator method, noise settings, dependency versions, bit mapping, and validation scope. QORE stores these fields with runs and Ledger snapshots so a later reader can distinguish source identity from execution environment.

A fixed simulator seed makes sampling repeatable within the recorded software environment, but native libraries and framework versions can change details. A source hash proves content identity, not physical correctness. Hardware reproducibility would additionally require backend calibration, queue, layout, compilation, and mitigation records, which this release does not claim.

Name experiments by question and configuration, preserve failed runs as failures, and never replace missing evidence with assistant prose.
