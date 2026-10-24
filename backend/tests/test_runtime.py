"""Exercise the actual short-lived worker, including forced termination."""

import time

import pytest

from qore.runtime import JobError, run_worker


def test_real_worker_returns_actual_ir(bell_source):
    result = run_worker("parse", {"source": bell_source})
    assert [op["name"] for op in result["ir"]["operations"]] == ["h", "cx", "measure", "measure"]


def test_real_worker_timeout_terminates_process_and_next_job_recovers(bell_source):
    started = time.monotonic()
    with pytest.raises(JobError) as caught:
        # An intentionally tiny budget expires during Python/framework startup.
        run_worker("parse", {"source": bell_source}, timeout=0.001)
    assert caught.value.code == "execution_timeout"
    assert time.monotonic() - started < 10
    recovered = run_worker("parse", {"source": bell_source})
    assert recovered["metrics"]["gate_count"] == 2


def test_unknown_worker_operation_returns_sanitized_error():
    with pytest.raises(JobError) as caught:
        run_worker("not_an_operation", {})
    assert caught.value.code == "quantum_failure"
    assert "Traceback" not in caught.value.message
    assert "C:\\" not in caught.value.message
