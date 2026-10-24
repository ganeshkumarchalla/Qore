"""Adversarial input tests for the constrained circuit builder."""

import math

import pytest

from qore.quantum import QuantumError, parse_source, simulate


PREFIX = "from qiskit import QuantumCircuit\nqc = QuantumCircuit(2, 2)\n"


@pytest.mark.parametrize("source", [
    "import os\nos.system('echo not_allowed')",
    "from qiskit import Aer\nfrom qiskit import QuantumCircuit\nqc = QuantumCircuit(2, 2)",
    "from numpy import random\nfrom qiskit import QuantumCircuit\nqc = QuantumCircuit(2, 2)",
    PREFIX + "exec('qc.x(0)')",
    PREFIX + "eval('1 + 1')",
    PREFIX + "__import__('os').getcwd()",
    PREFIX + "open('forbidden.txt', 'w').write('no')",
    PREFIX + "qc.__class__.__mro__",
    PREFIX + "qc.h.__globals__",
    PREFIX + "getattr(qc, 'h')(0)",
    PREFIX + "[qc.x(0) for x in range(10000000)]",
    PREFIX + "while True:\n    qc.x(0)",
    PREFIX + "def attack():\n    return 42",
    PREFIX + "qc.reset(0)",
    PREFIX + "qc.h(999999)",
    PREFIX + "qc.cx(0, 0)",
    PREFIX + "qc.rx(float('nan'), 0)",
    PREFIX + "qc.rx(1e999, 0)",
    PREFIX + "qc.rx(10 ** 1000000000, 0)",
    PREFIX + "qc.rx(1 / 0, 0)",
    PREFIX + "qc.measure(0, 0)\nqc.x(1)",
    PREFIX + "qc.measure(0, 9)",
    PREFIX + "qc.h(",
])
def test_unsupported_or_malformed_source_is_rejected_without_python_execution(source):
    with pytest.raises(QuantumError) as caught:
        parse_source(source)
    assert caught.value.code and caught.value.message


@pytest.mark.parametrize("source", [
    "#" + "a" * 32768,
    "from qiskit import QuantumCircuit\nqc = QuantumCircuit(11, 2)",
    "from qiskit import QuantumCircuit\nqc = QuantumCircuit(2, 11)",
    PREFIX + "qc.x(0)\n" * 501,
], ids=["large_source", "qubits_cap", "clbits_cap", "instructions_cap"])
def test_source_qubit_clbit_and_instruction_caps_are_enforced(source):
    with pytest.raises(QuantumError):
        parse_source(source)


@pytest.mark.parametrize("shots", [0, -1, 100001])
def test_shot_limits_enforced_by_quantum_boundary(bell_source, shots):
    with pytest.raises(QuantumError):
        simulate(bell_source, shots=shots, seed=42)


@pytest.mark.parametrize("field,value", [
    ("noise_rate", -0.1),
    ("noise_rate", 0.5001),
    ("noise_rate", math.nan),
    ("readout_error", math.inf),
    ("readout_error", True),
    ("method", "automatic"),
])
def test_noise_and_simulation_method_limits_are_enforced_at_quantum_boundary(
    bell_source, field, value
):
    arguments = {"source": bell_source, field: value}
    with pytest.raises(QuantumError):
        simulate(**arguments)


def test_file_write_payload_does_not_create_target(tmp_path):
    destination = tmp_path / "must_not_exist.txt"
    source = PREFIX + f"open({str(destination)!r}, 'w').write('unsafe')"
    with pytest.raises(QuantumError):
        parse_source(source)
    assert not destination.exists()
