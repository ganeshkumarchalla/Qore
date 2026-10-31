"""Compare accepted source with actual Qiskit semantics, not parser internals."""

import inspect

import numpy as np
import pytest
from qiskit import QuantumCircuit
from qiskit.circuit.library import CXGate, MCXGate, RXGate
from qiskit.quantum_info import Operator

from qore.quantum import (
    GATES, SUPPORTED_GATE_CLASSES, QuantumError, ir_to_circuit, optimize, parse_source, simulate,
)


def assert_operator(source, expected, *, up_to_global_phase=False):
    parsed = parse_source(source)
    actual = Operator(ir_to_circuit(parsed["ir"], unitary_only=True)).data
    if up_to_global_phase:
        assert Operator(actual).equiv(Operator(expected), atol=1e-9)
    else:
        np.testing.assert_allclose(actual, Operator(expected).data, atol=1e-9)


@pytest.mark.parametrize("declaration", [
    "import qiskit\nqc = qiskit.QuantumCircuit(2)",
    "import qiskit.circuit as circuit\nqc = circuit.QuantumCircuit(2)",
    "import qiskit.circuit\nqc = qiskit.circuit.QuantumCircuit(2)",
    "from qiskit import circuit as c\nqc = c.QuantumCircuit(2)",
    "from qiskit.circuit import QuantumCircuit as Circuit\nqc = Circuit(2)",
])
def test_circuit_import_forms_match_qiskit(declaration):
    expected = QuantumCircuit(2)
    expected.h(0)
    expected.cx(0, 1)
    assert_operator(declaration + "\nqc.h(0)\nqc.cx(0, 1)", expected)


@pytest.mark.parametrize("declaration,constructor", [
    ("import qiskit.circuit.library", "qiskit.circuit.library.RXGate"),
    ("import qiskit.circuit.library as gates", "gates.RXGate"),
    ("from qiskit.circuit import library as gates", "gates.RXGate"),
])
def test_gate_namespace_and_keyword_parameters_match_qiskit(declaration, constructor):
    expected = QuantumCircuit(1)
    expected.append(RXGate(theta=0.375), [0])
    source = ("from qiskit import QuantumCircuit\n" + declaration +
              f"\nqc=QuantumCircuit(1)\nqc.append({constructor}(theta=0.375), [0])")
    assert_operator(source, expected)


@pytest.mark.parametrize("name", sorted(SUPPORTED_GATE_CLASSES))
def test_every_advertised_library_class_preserves_its_operator(name):
    cls = SUPPORTED_GATE_CLASSES[name]
    kwargs = {}
    structured = {
        "PauliGate": {"label": "XY"},
        "DiagonalGate": {"diag": [1, -1]},
        "PermutationGate": {"pattern": [1, 0]},
        "UnitaryGate": {"data": [[0, 1j], [1j, 0]]},
        "HamiltonianGate": {"data": [[0, 1], [1, 0]], "time": 0.25},
        "StatePreparation": {"params": [0, 1]},
        "GraphStateGate": {"adjacency_matrix": [[0, 1], [1, 0]]},
        "AndGate": {"num_variable_qubits": 2},
        "OrGate": {"num_variable_qubits": 2},
        "BitwiseXorGate": {"num_qubits": 2, "amount": 1},
        "FullAdderGate": {"num_state_qubits": 1},
        "HalfAdderGate": {"num_state_qubits": 1},
    }
    if name == "PauliEvolutionGate":
        from qiskit.quantum_info import SparsePauliOp
        gate = cls(SparsePauliOp.from_list([("ZZ", 0.5)]), time=0.25)
        expected = QuantumCircuit(2)
        expected.append(gate, [0, 1])
        assert_operator("from qiskit import QuantumCircuit\nfrom qiskit.circuit.library import PauliEvolutionGate\n"
                        "from qiskit.quantum_info import SparsePauliOp\nqc=QuantumCircuit(2)\n"
                        "qc.append(PauliEvolutionGate(SparsePauliOp.from_list([('ZZ',0.5)]),time=0.25),[0,1])", expected)
        return
    if name == "MCMTGate":
        from qiskit.circuit.library import ZGate
        gate = cls(ZGate(), 2, 1)
        expected = QuantumCircuit(3)
        expected.append(gate, [0, 1, 2])
        assert_operator(
            "from qiskit import QuantumCircuit\nfrom qiskit.circuit.library import MCMTGate, ZGate\n"
            "qc=QuantumCircuit(3)\n"
            "qc.append(MCMTGate(ZGate(), 2, 1), [0, 1, 2])",
            expected,
        )
        return
    for parameter in inspect.signature(cls.__init__).parameters.values():
        if parameter.name == "self" or parameter.default is not inspect.Parameter.empty:
            continue
        if parameter.kind in (parameter.VAR_POSITIONAL, parameter.VAR_KEYWORD):
            continue
        kwargs[parameter.name] = 3 if parameter.name in ("num_ctrl_qubits", "num_qubits") else 0.375
    kwargs = structured.get(name, kwargs)
    gate = cls(**kwargs)
    width = max(1, gate.num_qubits)
    expected = QuantumCircuit(width)
    expected.append(gate, range(gate.num_qubits))
    arguments = ", ".join(f"{key}={value!r}" for key, value in kwargs.items())
    source = (f"from qiskit import QuantumCircuit\nfrom qiskit.circuit.library import {name}\n"
              f"qc=QuantumCircuit({width})\n"
              f"qc.append({name}({arguments}), {list(range(gate.num_qubits))!r})")
    assert_operator(source, expected)


@pytest.mark.parametrize("name,arguments,qubits", [
    ("CXGate", "ctrl_state=0", 2),
    ("MCXGate", "2, ctrl_state='01'", 3),
])
def test_open_control_gate_keywords_are_not_silently_ignored(name, arguments, qubits):
    gate = CXGate(ctrl_state=0) if name == "CXGate" else MCXGate(2, ctrl_state="01")
    expected = QuantumCircuit(qubits)
    expected.append(gate, range(qubits))
    source = (f"from qiskit import QuantumCircuit\nfrom qiskit.circuit.library import {name}\n"
              f"qc=QuantumCircuit({qubits})\nqc.append({name}({arguments}), {list(range(qubits))!r})")
    assert_operator(source, expected)


@pytest.mark.parametrize("body", [
    "qc.h([0, 1])\nqc.cx([0, 1], [2, 3])",
    "qc.x(0)\nqc.cx([0, 1], 2)",
    "qc.h([0, 1])\nqc.swap([0, 1], [2, 3])",
])
def test_native_broadcasting_matches_qiskit(body):
    # Expected operations are built independently, without evaluating source.
    expected = QuantumCircuit(4)
    if "swap" in body:
        expected.h([0, 1]); expected.swap([0, 1], [2, 3])
    elif "x(0)" in body:
        expected.x(0); expected.cx([0, 1], 2)
    else:
        expected.h([0, 1]); expected.cx([0, 1], [2, 3])
    assert_operator("from qiskit import QuantumCircuit\nqc=QuantumCircuit(4)\n" + body, expected)


def test_comprehension_preserves_outer_variable_scope():
    source = ("from qiskit import QuantumCircuit\nqc=QuantumCircuit(1)\n"
              "angle=0\nindices=[angle for angle in range(2)]\nqc.rx(angle, 0)")
    assert_operator(source, QuantumCircuit(1))


@pytest.mark.parametrize("body", [
    "angle=0.75\nangle %= 0.5\nqc.rx(angle, 0)",
    "undefined += 1\nqc.rx(undefined, 0)",
    "qc.append(CXGate(ctrl_state=0, unknown=True), [0, 1])",
    "qc.append(CXGate(), [0, 1], ignored=True)",
    "qc.mcx([0], 1, ignored=True)",
    "angle=pow(2, 3, ignored=True)\nqc.rx(angle, 0)",
    "values=[0 for qc in range(2)]\nqc.x(0)",
    "if 0 is 1:\n    qc.x(0)",
    "unknown.draw()\nqc.x(0)",
    "qc.append(unknown.library.CXGate(), [0, 1])",
])
def test_unsupported_syntax_fails_instead_of_changing_meaning(body):
    source = ("from qiskit import QuantumCircuit\nfrom qiskit.circuit.library import CXGate\n"
              "from math import pow\nqc=QuantumCircuit(2)\n" + body)
    with pytest.raises(QuantumError):
        parse_source(source)


def test_second_qasm_constructor_does_not_replace_the_active_circuit():
    qasm = 'OPENQASM 2.0; include "qelib1.inc"; qreg q[1];'
    source = f"from qiskit import QuantumCircuit\nqc=QuantumCircuit(1)\nqc.x(0)\nother=QuantumCircuit.from_qasm_str({qasm!r})"
    expected = QuantumCircuit(1)
    expected.x(0)
    assert_operator(source, expected)


def test_open_control_execution_and_export_keep_the_same_result():
    source = ("from qiskit import QuantumCircuit\nfrom qiskit.circuit.library import CXGate\n"
              "qc=QuantumCircuit(2,2)\nqc.append(CXGate(ctrl_state=0), [0,1])\n"
              "qc.measure([0,1], [0,1])")
    result = simulate(source, shots=16, seed=3)
    assert result["counts"] == {"10": 16}
    assert result["theoretical_probabilities"]["10"] == pytest.approx(1)
    assert simulate(result["qasm"], shots=16, seed=3)["counts"] == {"10": 16}


def test_native_open_control_keywords_and_existing_measurement_registers():
    source = ("from qiskit import QuantumCircuit\nqc=QuantumCircuit(2,2)\n"
              "qc.cx(0,1,ctrl_state=0)\nqc.measure_all(add_bits=False)")
    assert simulate(source, shots=16, seed=3)["counts"] == {"10": 16}


@pytest.mark.parametrize("name,spec", sorted(GATES.items()))
def test_exported_native_gates_reimport_with_the_same_operator(name, spec):
    parameters, qubits = spec
    args = ["0.375"] * parameters + [str(i) for i in range(qubits)]
    source = f"from qiskit import QuantumCircuit\nqc=QuantumCircuit({qubits})\nqc.{name}({', '.join(args)})"
    parsed = parse_source(source)
    expected = ir_to_circuit(parsed["ir"])
    # OpenQASM 2 cannot represent a circuit's global phase.
    assert_operator(parsed["qasm"], expected, up_to_global_phase=True)


@pytest.mark.parametrize("definition,expected_x", [
    ("gate h a { U(pi,0,pi) a; }", True),
    ("gate u(theta,phi,lam) a { U(0,0,0) a; }", False),
])
def test_explicit_qasm_gate_definitions_are_not_replaced_by_standard_names(definition, expected_x):
    instruction = "h q[0];" if expected_x else "u(pi,0,pi) q[0];"
    source = f"OPENQASM 2.0;\n{definition}\nqreg q[1];\n{instruction}"
    expected = QuantumCircuit(1)
    if expected_x:
        expected.x(0)
    assert_operator(source, expected)


def test_qasm_source_cannot_include_a_local_file(tmp_path):
    include = tmp_path / "private.inc"
    include.write_text("gate local a { U(pi,0,pi) a; }")
    source = f'OPENQASM 2.0;\ninclude "{include.as_posix()}";\nqreg q[1];\nlocal q[0];'
    with pytest.raises(QuantumError) as caught:
        parse_source(source)
    assert caught.value.code == "UNSUPPORTED_IMPORT"


def test_noisy_mcx_applies_errors_to_its_decomposition():
    source = ("from qiskit import QuantumCircuit\nqc=QuantumCircuit(4,4)\n"
              "qc.mcx([0,1,2],3)\nqc.measure([0,1,2,3],[0,1,2,3])")
    assert simulate(source, shots=128, seed=42)["counts"] == {"0000": 128}
    noisy = simulate(source, shots=128, seed=42, noise_rate=0.25)
    assert any(state != "0000" for state in noisy["counts"])


@pytest.mark.parametrize("constructor,qubits", [
    ("QFTGate(3)", 3), ("C4XGate()", 5), ("XXPlusYYGate(0.375, beta=0.25)", 2),
    ("GlobalPhaseGate(0.375)", 1),
])
def test_composite_gate_simulation_and_optimization_preserve_behavior(constructor, qubits):
    name = constructor.split("(")[0]
    qargs = [] if name == "GlobalPhaseGate" else list(range(qubits))
    source = (f"from qiskit import QuantumCircuit\nfrom qiskit.circuit.library import {name}\n"
              f"qc=QuantumCircuit({qubits})\nqc.append({constructor}, {qargs!r})")
    result = simulate(source, shots=16, seed=3)
    assert sum(result["counts"].values()) == 16
    optimized = optimize(source)
    assert optimized["validation"]["status"] == "validated"
    original = parse_source(source)
    assert_operator(optimized["candidate"]["source"], ir_to_circuit(original["ir"]))


@pytest.mark.parametrize("constructor", ["MCXGate(1000000000)", "QFTGate(1000000000)"])
def test_large_gate_dimensions_are_rejected_before_construction(constructor):
    name = constructor.split("(")[0]
    source = f"from qiskit import QuantumCircuit\nfrom qiskit.circuit.library import {name}\nqc=QuantumCircuit(1)\ngate={constructor}"
    with pytest.raises(QuantumError):
        parse_source(source)


def test_api_separates_installed_sdks_from_executable_editor_support(client):
    response = client.get("/api/capabilities")
    assert response.status_code == 200
    data = response.json()
    assert {"QFTGate", "MCPhaseGate", "GlobalPhaseGate"} <= set(data["gate_classes"])
    assert {"append", "mcx"} <= set(data["circuit_methods"])
    assert data["installed_packages"]["qiskit"]
    assert data["installed_packages"]["qiskit-aer"]
    assert "does not enable editor execution" in data["package_execution"]["optional_packages"]
