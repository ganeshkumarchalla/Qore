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
    assert len(result["unitary_matrix"]) == 2
    assert sum(amplitude["probability"] for amplitude in result["statevector_amplitudes"]) == pytest.approx(1, abs=.0002)


def test_entangled_reduced_state_has_purity_one_half_and_zero_bloch_radius():
    result = parse_source("from qiskit import QuantumCircuit\nqc=QuantumCircuit(3)\nqc.h(0)\nqc.cx(0,1)\nqc.cx(1,2)")
    assert len(result["bloch_vectors"]) == 3
    for vector in result["bloch_vectors"]:
        assert (vector["x"], vector["y"], vector["z"]) == pytest.approx((0, 0, 0))
        assert vector["purity"] == pytest.approx(.5)
        assert vector["is_pure"] is False
