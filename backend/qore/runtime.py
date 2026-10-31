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


_REMOTE_CLIENT = None


def _get_remote_client(timeout=30):
    global _REMOTE_CLIENT
    if _REMOTE_CLIENT is None or _REMOTE_CLIENT.is_closed:
        import httpx
        _REMOTE_CLIENT = httpx.Client(
            timeout=timeout,
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=50, keepalive_expiry=60.0)
        )
    return _REMOTE_CLIENT


def run_worker(operation, args, timeout=30):
    worker_host = os.environ.get("QORE_WORKER_HOST", "").strip().rstrip("/")
    if worker_host:
        import httpx
        try:
            client = _get_remote_client(timeout=timeout)
            resp = client.post(
                f"{worker_host}/api/worker",
                json={"operation": operation, "args": args},
                headers={"Content-Type": "application/json"}
            )
            if resp.status_code >= 400:
                try:
                    err_data = resp.json().get("error", {})
                    raise JobError(
                        err_data.get("code", "remote_worker_error"),
                        err_data.get("message", f"Remote worker error: {resp.status_code}"),
                        details=err_data.get("details"),
                        status=resp.status_code
                    )
                except (ValueError, TypeError):
                    raise JobError("remote_worker_error", f"Remote worker failed with HTTP {resp.status_code}", status=500)
            data = resp.json()
            if "error" in data:
                raise JobError(**data["error"])
            return data["result"]
        except httpx.TimeoutException:
            raise JobError("execution_timeout", f"The remote quantum job exceeded the {timeout}-second limit.", status=408)
        except JobError:
            raise
        except Exception:
            # Fall back to local worker if remote host is unreachable
            pass

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
