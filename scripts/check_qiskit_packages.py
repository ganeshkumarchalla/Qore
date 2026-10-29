"""Offline import smoke checks; installed SDKs are not editor permissions.

No provider is instantiated, no credentials are forwarded, and no jobs are sent.
Run with the project's Python environment. Results go to evidence/.
"""

import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys


MODULES = {
    "qiskit": "qiskit",
    "qiskit-aer": "qiskit_aer",
    "qiskit-ibm-runtime": "qiskit_ibm_runtime",
    "qiskit-addon-utils": "qiskit_addon_utils",
    "qiskit-addon-aqc-tensor": "qiskit_addon_aqc_tensor",
    "qiskit-addon-cutting": "qiskit_addon_cutting",
    "qiskit-addon-mpf": "qiskit_addon_mpf",
    "qiskit-addon-obp": "qiskit_addon_obp",
    "qiskit-addon-sqd": "qiskit_addon_sqd",
    "qiskit-mitigation": "qiskit_mitigation",
    "qiskit-qasm3-import": "qiskit_qasm3_import",
}


def main():
    environment = {key: value for key, value in os.environ.items()
                   if key.upper() in {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP"}}
    environment.update({"OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "QISKIT_PARALLEL": "FALSE"})
    records = []
    program = "import importlib,sys; importlib.import_module(sys.argv[1])"
    for distribution, module in MODULES.items():
        try:
            version = importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError:
            records.append({"distribution": distribution, "status": "not_installed"})
            continue
        try:
            result = subprocess.run(
                [sys.executable, "-I", "-c", program, module],
                env=environment, capture_output=True, timeout=30,
                **({"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}),
            )
            status = "passed" if result.returncode == 0 else "import_failed"
        except subprocess.TimeoutExpired:
            status = "timeout"
        # Raw dependency stderr can include local paths or provider diagnostics.
        records.append({"distribution": distribution, "module": module,
                        "version": version, "status": status,
                        "scope": "offline import only, not full API or editor execution"})
        print(f"{distribution} {version}: {status}", flush=True)
    output = Path(__file__).resolve().parents[1] / "evidence" / "qiskit_package_check.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps({"checks": records, "scope": "No network jobs or provider authentication tested."}, indent=2))
    return int(any(row["status"] in {"import_failed", "timeout"} for row in records))


if __name__ == "__main__":
    raise SystemExit(main())
