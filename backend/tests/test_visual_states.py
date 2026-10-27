"""Independent analytic states protect the physical meaning of Bloch readouts."""
import math

import pytest

from qore.quantum import parse_source


@pytest.mark.parametrize("gates,expected", [
    ("", (0, 0, 1)),
    ("qc.x(0)", (0, 0, -1)),
    ("qc.h(0)", (1, 0, 0)),
    ("qc.h(0)\nqc.s(0)", (0, 1, 0)),
    ("qc.ry(pi/3, 0)\nqc.rz(pi/5, 0)",
     (math.sin(math.pi/3)*math.cos(math.pi/5), math.sin(math.pi/3)*math.sin(math.pi/5), .5)),
])
def test_single_qubit_readout_is_a_density_matrix_with_physical_purity(gates, expected):
    result = parse_source("from qiskit import QuantumCircuit\nfrom math import pi\nqc=QuantumCircuit(1)\n" + gates)
    assert len(result["bloch_vectors"]) == 1
    vector = result["bloch_vectors"][0]
    assert (vector["x"], vector["y"], vector["z"]) == pytest.approx(expected, abs=6e-5)
    assert vector["purity"] == pytest.approx(1)
    assert vector["is_pure"] is True
    assert vector["direction_defined"] is True
    assert vector["azimuth_defined"] is (math.hypot(expected[0], expected[1]) >= 1e-8)
    if not vector["azimuth_defined"]:
        assert vector["phi"] == 0
    assert len(result["unitary_matrix"]) == 2
    assert sum(amplitude["probability"] for amplitude in result["statevector_amplitudes"]) == pytest.approx(1, abs=.0002)


def test_entangled_reduced_state_has_purity_one_half_and_zero_bloch_radius():
    result = parse_source("from qiskit import QuantumCircuit\nqc=QuantumCircuit(3)\nqc.h(0)\nqc.cx(0,1)\nqc.cx(1,2)")
    assert len(result["bloch_vectors"]) == 3
    for vector in result["bloch_vectors"]:
        assert (vector["x"], vector["y"], vector["z"]) == pytest.approx((0, 0, 0))
        assert vector["purity"] == pytest.approx(.5)
        assert vector["is_pure"] is False
        assert vector["r"] == pytest.approx(0)
        assert vector["direction_defined"] is False
        assert vector["azimuth_defined"] is False
        assert vector["theta"] == 0
        assert vector["phi"] == 0


def test_hadamard_unitary_is_verified_and_amplitudes_sum_to_one():
    result = parse_source("from qiskit import QuantumCircuit\nqc=QuantumCircuit(1)\nqc.h(0)")
    assert result["unitarity"]["is_unitary"] is True
    assert result["unitarity"]["max_deviation"] < 1e-8
    assert result["unitarity"]["dimension"] == 2
    assert abs(sum(amp["probability"] for amp in result["statevector_amplitudes"]) - 1) < 1e-7
    matrix = result["unitary_matrix"]
    assert len(matrix) == 2
    assert matrix[0][0]["real"] == pytest.approx(1 / math.sqrt(2), abs=1e-7)
    assert matrix[0][1]["real"] == pytest.approx(1 / math.sqrt(2), abs=1e-7)


def test_two_qubit_unitary_respects_qiskit_basis_order_and_complex_phase():
    result = parse_source(
        "from qiskit import QuantumCircuit\n"
        "qc=QuantumCircuit(2)\n"
        "qc.cx(0,1)\n"
        "qc.s(1)"
    )
    matrix = result["unitary_matrix"]
    # q[0] is the least significant basis bit: |01> -> i|11>,
    # |11> -> |01>, and |10> -> i|10>.
    expected = {(0, 0): 1, (1, 3): 1, (2, 2): 1j, (3, 1): 1j}
    for row in range(4):
        for column in range(4):
            actual = complex(matrix[row][column]["real"], matrix[row][column]["imag"])
            assert actual == pytest.approx(expected.get((row, column), 0), abs=1e-8)
    assert result["unitarity"]["is_unitary"] is True
    assert result["unitarity"]["max_deviation"] < 1e-8
