"""Real framework acceptance tests; no simulator or compiler mocks."""

from copy import deepcopy
from hashlib import sha256
import math

import pytest

from qore.quantum import QuantumError, optimize, parse_source, simulate, validate_ir, versions


def program(body, qubits=2, clbits=2):
    return f"from qiskit import QuantumCircuit\nqc = QuantumCircuit({qubits}, {clbits})\n{body}\n"


def test_bell_ir_is_versioned_ordered_and_preserves_control_target(bell_source):
    result = parse_source(bell_source)
    ir = result["ir"]
    assert ir["version"] == "1.0"
    assert (ir["num_qubits"], ir["num_clbits"]) == (2, 2)
    assert ir["global_phase"] == pytest.approx(0)
    assert [(op["name"], op["qubits"], op["clbits"]) for op in ir["operations"]] == [
        ("h", [0], []), ("cx", [0, 1], []), ("measure", [0], [0]), ("measure", [1], [1])
    ]
    assert all(isinstance(op["params"], list) for op in ir["operations"])
    assert result["source_hash"] == sha256(bell_source.encode("utf-8")).hexdigest()


def test_metrics_define_actual_gate_counts_separately_from_measurements_and_barriers():
    parsed = parse_source(program("qc.h(0)\nqc.barrier()\nqc.cx(0, 1)\nqc.measure(0, 0)\nqc.measure(1, 1)"))
    metrics = parsed["metrics"]
    assert metrics["qubits"] == 2
    assert metrics["clbits"] == 2
    assert metrics["gate_count"] == 2
    assert metrics["two_qubit_gate_count"] == 1
    assert metrics["measurement_count"] == 2
    assert metrics["barrier_count"] == 1
    assert metrics["gate_types"]["h"] == 1
    assert metrics["gate_types"]["cx"] == 1
    assert metrics["depth"] >= 2
    assert metrics["definition"]


def test_math_parameters_and_reversed_control_mapping_are_not_reinterpreted():
    source = "from qiskit import QuantumCircuit\nfrom math import pi\nqc = QuantumCircuit(2, 2)\nqc.rx(pi / 2, 1)\nqc.cx(1, 0)\n"
    operations = parse_source(source)["ir"]["operations"]
    assert operations[0]["params"] == pytest.approx([math.pi / 2])
    assert operations[0]["qubits"] == [1]
    assert operations[1]["qubits"] == [1, 0]


def test_real_bell_simulation_preserves_shots_seed_and_probability_evidence(bell_source):
    first = simulate(bell_source, shots=4096, seed=17)
    second = simulate(bell_source, shots=4096, seed=17)
    assert first["counts"] == second["counts"]
    assert sum(first["counts"].values()) == 4096
    assert set(k for k, v in first["counts"].items() if v) <= {"00", "11"}
    assert first["shots"] == 4096 and first["seed"] == 17
    assert first["probabilities"]["00"] == first["counts"]["00"] / 4096
    assert first["probabilities"]["11"] == first["counts"]["11"] / 4096
    assert sum(first["probabilities"].values()) == pytest.approx(1)
    assert first["theoretical_probabilities"]["00"] == pytest.approx(0.5)
    assert first["theoretical_probabilities"]["11"] == pytest.approx(0.5)
    assert abs(first["probabilities"]["00"] - 0.5) < 0.05
    support = set(first["probabilities"]) | set(first["theoretical_probabilities"])
    expected_tvd = 0.5 * sum(abs(first["probabilities"].get(k, 0) - first["theoretical_probabilities"].get(k, 0)) for k in support)
    assert first["tvd"] == pytest.approx(expected_tvd)
    assert first["backend"] and first["versions"] and first["bit_ordering"]
    assert first["execution_ms"] >= 0


@pytest.mark.parametrize("measurement,outcome", [
    ("qc.measure(0, 0)\nqc.measure(1, 1)", "01"),
    ("qc.measure(0, 1)\nqc.measure(1, 0)", "10"),
])
def test_simulator_obeys_classical_mapping_and_little_endian_display(measurement, outcome):
    result = simulate(program(f"qc.x(0)\n{measurement}"), shots=128, seed=3)
    assert result["counts"] == {outcome: 128}
    assert result["theoretical_probabilities"].get(outcome) == pytest.approx(1)
    assert result["tvd"] == pytest.approx(0)


def test_optimization_uses_compiler_and_keeps_original_evidence():
    source = program("qc.x(0)\nqc.x(0)\nqc.h(1)\nqc.h(1)\nqc.measure(0, 0)\nqc.measure(1, 1)")
    before = parse_source(source)
    result = optimize(source, level=2, seed=7)
    assert result["original"]["ir"] == before["ir"]
    assert result["original"]["metrics"] == before["metrics"]
    assert result["source_hash"] == before["source_hash"]
    assert result["candidate"]["metrics"]["gate_count"] < before["metrics"]["gate_count"]
    assert result["validation"]["status"] == "validated"
    assert result["settings"] and result["versions"] and result["explanation"]
    reparsed = parse_source(result["candidate"]["source"])
    assert reparsed["metrics"] == result["candidate"]["metrics"]
    assert validate_ir(before["ir"], reparsed["ir"])["status"] == "validated"
    for metric, difference in result["differences"].items():
        original = result["original"]["metrics"][metric]
        candidate = result["candidate"]["metrics"][metric]
        assert difference["absolute"] == candidate - original
        assert difference["original"] == original
        assert difference["candidate"] == candidate
        if original:
            assert difference["relative_percent"] == pytest.approx((candidate - original) / original * 100)
        else:
            assert difference["relative_percent"] is None


def test_empty_circuit_optimization_does_not_invent_an_improvement():
    result = optimize(program("qc.measure(0, 0)\nqc.measure(1, 1)"), level=2, seed=9)
    assert result["original"]["metrics"]["gate_count"] == 0
    assert result["candidate"]["metrics"]["gate_count"] == 0
    assert result["differences"]["gate_count"]["absolute"] == 0
    assert result["differences"]["gate_count"]["relative_percent"] is None


def test_validation_checks_full_operator_not_only_zero_input_state():
    identity = parse_source(program(""))["ir"]
    z_gate = parse_source(program("qc.z(0)"))["ir"]
    # I|00> and Z|00> coincide, but these are different operators.
    assert validate_ir(identity, z_gate)["status"] == "failed"


def test_validation_accepts_global_phase_without_mutating_ir():
    original = parse_source(program("qc.h(0)\nqc.cx(0, 1)"))["ir"]
    candidate = deepcopy(original)
    candidate["global_phase"] = math.pi / 3
    snapshot = deepcopy(candidate)
    result = validate_ir(original, candidate)
    assert result["status"] == "validated"
    assert result["method"] and result["details"]
    assert candidate == snapshot


def test_validation_rejects_classical_mapping_change_even_for_same_unitary():
    first = parse_source(program("qc.x(0)\nqc.measure(0, 0)\nqc.measure(1, 1)"))["ir"]
    swapped = parse_source(program("qc.x(0)\nqc.measure(0, 1)\nqc.measure(1, 0)"))["ir"]
    assert validate_ir(first, swapped)["status"] == "failed"


def test_validation_is_honestly_unavailable_above_full_operator_limit():
    ir = parse_source(program("qc.h(0)", qubits=7, clbits=7))["ir"]
    result = validate_ir(ir, deepcopy(ir))
    assert result["status"] == "unavailable"
    assert result["details"]


def test_runtime_versions_report_framework_and_simulator():
    reported = versions()
    assert reported
    assert any("qiskit" in key.lower() for key in reported)
    assert any("aer" in key.lower() for key in reported)


@pytest.mark.parametrize("instruction", [
    "qc.cs(0, 1)",
    "qc.csdg(0, 1)",
    "qc.cu(0.1, 0.2, 0.3, 0.4, 0, 1)",
    "qc.ccz(0, 1, 2)",
    "qc.rccx(0, 1, 2)",
    "qc.u2(0.2, 0.3, 0)",
    "qc.cu3(0.1, 0.2, 0.3, 0, 1)",
])
def test_additional_native_qiskit_gates_parse_simulate_and_export(instruction):
    source = program(f"{instruction}\nqc.measure(0, 0)\nqc.measure(1, 1)\nqc.measure(2, 2)", qubits=3, clbits=3)
    parsed = parse_source(source)
    assert parsed["ir"]["operations"][0]["name"] in {"cs", "csdg", "u", "cu", "ccz", "rccx"}
    assert parsed["qasm"].startswith("OPENQASM 2.0")
    result = simulate(source, shots=64, seed=5)
    assert sum(result["counts"].values()) == 64


def test_qiskit_circuit_module_import_is_supported():
    source = "from qiskit.circuit import QuantumCircuit\nqc = QuantumCircuit(1, 1)\nqc.h(0)\nqc.measure(0, 0)\n"
    assert parse_source(source)["metrics"]["gate_types"] == {"h": 1}


def test_qiskit_circuit_library_gates_and_append_are_supported():
    source = (
        "from qiskit import QuantumCircuit\n"
        "from qiskit.circuit.library import HGate, MCXGate\n"
        "mcx_gate = MCXGate(3)\n"
        "hadamard_gate = HGate()\n"
        "qc = QuantumCircuit(4, 4)\n"
        "qc.append(hadamard_gate, [0])\n"
        "qc.append(mcx_gate, [0, 1, 2, 3])\n"
        "qc.draw('mpl')\n"
        "qc.measure([0, 1, 2, 3], [0, 1, 2, 3])\n"
    )
    parsed = parse_source(source)
    assert parsed["metrics"]["gate_types"] == {"h": 1, "mcx": 1}
    assert parsed["metrics"]["qubits"] == 4
    sim = simulate(source, shots=100, seed=42)
    assert sum(sim["counts"].values()) == 100
    assert "0000" in sim["counts"] or "0001" in sim["counts"]

