"""Acceptance fixtures use the same supported source as the browser workflow."""

import pytest
from fastapi.testclient import TestClient


BELL_SOURCE = """from qiskit import QuantumCircuit
qc = QuantumCircuit(2, 2)
qc.h(0)
qc.cx(0, 1)
qc.measure(0, 0)
qc.measure(1, 1)
"""


@pytest.fixture
def bell_source():
    return BELL_SOURCE


@pytest.fixture
def client(tmp_path, monkeypatch):
    # Tests never send source to an external model or require credentials.
    for variable in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(variable, raising=False)
    from qore.main import create_app

    with TestClient(create_app(tmp_path / "acceptance.sqlite3")) as test_client:
        yield test_client
