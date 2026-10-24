"""Resource-bounded worker orchestration; not an operating-system security sandbox."""

import json
import os
import subprocess
import sys
from pathlib import Path


class JobError(Exception):
    def __init__(self, code, message, details=None, status=422):
        self.code, self.message, self.details, self.status = code, message, details, status
        super().__init__(message)


def run_worker(operation, args, timeout=30):
    # Credentials are deliberately absent from the quantum process environment.
    environment = {k: v for k, v in os.environ.items() if k.upper() in {
        "PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "VIRTUAL_ENV", "LD_LIBRARY_PATH",
    }}
    environment.update({"PYTHONPATH": str(Path(__file__).resolve().parents[1]),
                        "PYTHONIOENCODING": "utf-8", "OMP_NUM_THREADS": "1",
                        "OPENBLAS_NUM_THREADS": "1", "QISKIT_PARALLEL": "FALSE"})
    options = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
    try:
        result = subprocess.run([sys.executable, "-m", "qore.worker"],
                                input=json.dumps({"operation": operation, "args": args}),
                                capture_output=True, text=True, encoding="utf-8", timeout=timeout,
                                env=environment, cwd=str(Path(__file__).resolve().parents[1]), **options)
    except subprocess.TimeoutExpired:
        raise JobError("execution_timeout", f"The quantum job exceeded the {timeout}-second limit.", status=408)
    if result.returncode != 0:
        raise JobError("worker_failed", "The isolated quantum worker exited unexpectedly.", status=500)
    try:
        response = json.loads(result.stdout)
    except (ValueError, TypeError):
        raise JobError("invalid_worker_response", "The quantum worker returned an invalid response.", status=500)
    if "error" in response:
        raise JobError(**response["error"])
    return response["result"]
