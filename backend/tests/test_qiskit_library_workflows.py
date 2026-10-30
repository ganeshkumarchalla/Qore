"""Independent Qiskit references for broader, bounded SDK source workflows."""

import numpy as np
import pytest
from qiskit import QuantumCircuit
from qiskit.circuit.library import HGate, RXGate
import qiskit.circuit.library as library
from qiskit.quantum_info import Operator

from qore.quantum import QuantumError, ir_to_circuit, optimize, parse_source, simulate
from qore.qiskit_support import CIRCUIT_FACTORIES


def same_operator(source, reference):
    result = parse_source(source)
    actual = Operator(ir_to_circuit(result["ir"], unitary_only=True)).data
    np.testing.assert_allclose(actual, Operator(reference).data, atol=1e-9)
    return result


def test_parameter_binding_by_identity_and_vector_elements():
    source = ("from qiskit import QuantumCircuit\nfrom qiskit.circuit import Parameter, ParameterVector\n"
              "angle=Parameter('angle')\np=ParameterVector('p',2)\nqc=QuantumCircuit(2)\n"
              "qc.rx(angle/2,0)\nqc.ry(p[0],1)\nqc.rz(p[1],0)\n"
              "qc=qc.assign_parameters({angle:0.5,p[0]:0.25,p[1]:-0.125})")
    reference = QuantumCircuit(2)
    reference.rx(0.25, 0); reference.ry(0.25, 1); reference.rz(-0.125, 0)
    same_operator(source, reference)


def test_parameter_vector_loop_binding_in_place_and_slicing():
    source = ("from qiskit import QuantumCircuit\nfrom qiskit.circuit import ParameterVector\n"
              "p=ParameterVector('p',3)\nqc=QuantumCircuit(3)\n"
              "for i in range(3):\n    qc.ry(p[i],i)\n"
              "values=[0.25,0.5,0.75,1.0]\nqc.assign_parameters(values[:3],inplace=True)")
    reference = QuantumCircuit(3)
    for index, angle in enumerate([0.25, 0.5, 0.75]):
        reference.ry(angle, index)
    same_operator(source, reference)


def test_named_parameter_binding_and_numpy_sequence():
    source = ("import numpy as np\nfrom qiskit import QuantumCircuit\nfrom qiskit.circuit import Parameter\n"
              "p=Parameter('angle')\nqc=QuantumCircuit(1)\nqc.rx(p,0)\n"
              "qc=qc.assign_parameters({'angle':0.5})")
    reference = QuantumCircuit(1); reference.rx(0.5, 0)
    same_operator(source, reference)


@pytest.mark.parametrize("name", sorted(CIRCUIT_FACTORIES))
def test_each_advertised_circuit_factory_binds_and_preserves_its_operator(name):
    from qiskit.quantum_info import SparsePauliOp
    factory = CIRCUIT_FACTORIES[name]
    imports = f"from qiskit.circuit.library import {name}"
    pre_code = ""

    if name == "QFT":
        call_expr = f"{name}(2)"
        reference = factory(2)
    elif name in ("TwoLocal", "n_local"):
        call_expr = f"{name}(2, reps=1, rotation_blocks='ry', entanglement_blocks='cx')"
        reference = factory(2, reps=1, rotation_blocks="ry", entanglement_blocks="cx")
    elif name == "NLocal":
        imports += ", RYGate, CXGate"
        pre_code = "rot = RYGate(0.125)\nent = CXGate()\n"
        call_expr = f"{name}(2, reps=1, rotation_blocks=rot, entanglement_blocks=ent)"
        reference = factory(2, reps=1, rotation_blocks=library.RYGate(0.125), entanglement_blocks=library.CXGate())
    elif name in ("PauliTwoDesign", "pauli_two_design"):
        call_expr = f"{name}(2, reps=1, seed=42)"
        reference = factory(2, reps=1, seed=42)
    elif name in ("QuantumVolume", "quantum_volume"):
        call_expr = f"{name}(2, depth=2, seed=42)"
        reference = factory(2, depth=2, seed=42)
    elif name in ("QAOAAnsatz", "qaoa_ansatz"):
        imports += "\nfrom qiskit.quantum_info import SparsePauliOp"
        pre_code = "cost_op = SparsePauliOp.from_list([('ZZ', 1.0)])\n"
        call_expr = f"{name}(cost_operator=cost_op, reps=1)"
        reference = factory(cost_operator=SparsePauliOp.from_list([('ZZ', 1.0)]), reps=1)
    elif name in ("EvolvedOperatorAnsatz", "evolved_operator_ansatz"):
        imports += "\nfrom qiskit.quantum_info import SparsePauliOp"
        pre_code = "ops = SparsePauliOp.from_list([('ZZ', 1.0)])\n"
        call_expr = f"{name}(operators=ops, reps=1)"
        reference = factory(operators=SparsePauliOp.from_list([('ZZ', 1.0)]), reps=1)
    elif name in ("GroverOperator", "grover_operator"):
        pre_code = "oracle = QuantumCircuit(2)\noracle.z(0)\n"
        call_expr = f"{name}(oracle=oracle)"
        oracle_ref = QuantumCircuit(2); oracle_ref.z(0)
        reference = factory(oracle=oracle_ref)
    elif name in ("IQP", "iqp"):
        pre_code = "interactions = [[0, 1], [1, 0]]\n"
        call_expr = f"{name}(interactions)"
        reference = factory([[0, 1], [1, 0]])
    elif name in ("FourierChecking", "fourier_checking"):
        pre_code = "f = [1, -1, -1, 1]\ng = [1, 1, -1, -1]\n"
        call_expr = f"{name}(f, g)"
        reference = factory([1, -1, -1, 1], [1, 1, -1, -1])
    elif name in ("HiddenLinearFunction", "hidden_linear_function"):
        pre_code = "adj = [[0, 1], [1, 0]]\n"
        call_expr = f"{name}(adj)"
        reference = factory([[0, 1], [1, 0]])
    elif name in ("ExcitationPreserving", "excitation_preserving"):
        call_expr = f"{name}(2, reps=1, mode='iswap')"
        reference = factory(2, reps=1, mode="iswap")
    else:
        call_expr = f"{name}(2, reps=1)"
        reference = factory(2, reps=1)

    reference = reference.assign_parameters([0.125] * reference.num_parameters)
    source = (
        f"from qiskit import QuantumCircuit\n{imports}\n{pre_code}"
        f"ansatz = {call_expr}\n"
        "values = [0.125 for i in range(ansatz.num_parameters)]\n"
        "bound = ansatz.assign_parameters(values)\n"
        "qc = QuantumCircuit(2)\nqc.compose(bound, inplace=True)"
    )
    same_operator(source, reference)
    assert sum(simulate(source, shots=16, seed=7)["counts"].values()) == 16
    assert optimize(source)["validation"]["status"] == "validated"


def test_library_factory_can_be_the_primary_circuit():
    source = ("from qiskit.circuit.library import real_amplitudes\nqc=real_amplitudes(2,reps=1)\n"
              "values=[0.25 for i in range(qc.num_parameters)]\nqc=qc.assign_parameters(values)")
    reference = library.real_amplitudes(2, reps=1)
    same_operator(source, reference.assign_parameters([0.25] * reference.num_parameters))


@pytest.mark.parametrize("blocks,kwargs", [
    ("['ry','rz'], 'cx'", {}),
    ("[], 'cry'", {"entanglement": "linear"}),
    ("'ry', ['rxx','ryy']", {"entanglement": ["full", "linear"]}),
    ("'ry', ['rxx','ryy']", {"entanglement": [[[0, 1]], [[0, 1]]]}),
    ("RYGate(angle), CXGate()", {"overwrite_block_parameters": False}),
])
def test_n_local_supports_named_empty_and_gate_object_blocks(blocks, kwargs):
    angle = library.RYGate(0.3).params[0]
    if blocks == "RYGate(angle), CXGate()":
        rotations, entanglers = library.RYGate(angle), library.CXGate()
    elif blocks == "[], 'cry'":
        rotations, entanglers = [], 'cry'
    elif blocks == "'ry', ['rxx','ryy']":
        rotations, entanglers = 'ry', ['rxx', 'ryy']
    else:
        rotations, entanglers = ['ry', 'rz'], 'cx'
    reference = library.n_local(2, rotations, entanglers, reps=1, **kwargs)
    reference = reference.assign_parameters([0.25] * reference.num_parameters)
    options = ', '.join(f'{key}={value!r}' for key, value in kwargs.items())
    source = ("from qiskit.circuit.library import n_local as build, RYGate, CXGate\nangle=0.3\n"
              f"qc=build(2,{blocks},reps=1{', '+options if options else ''})\n"
              "qc=qc.assign_parameters([0.25 for i in range(qc.num_parameters)])")
    same_operator(source, reference)


def test_n_local_executes_and_compiles_over_the_api(client):
    source = ("import qiskit.circuit.library as library\n"
              "qc=library.n_local(2,['ry','rz'],'cx',reps=1)\n"
              "qc.assign_parameters([0.25 for i in range(qc.num_parameters)],inplace=True)\nqc.measure_all()")
    capabilities = client.get('/api/capabilities').json()
    assert 'n_local' in capabilities['circuit_factories']
    assert 'NLocal' in capabilities['circuit_factories']
    simulated = client.post('/api/simulate', json={'source': source, 'shots': 32, 'seed': 7})
    assert simulated.status_code == 200, simulated.text
    assert sum(simulated.json()['counts'].values()) == 32
    compiled = client.post('/api/optimize', json={'source': source, 'level': 2, 'seed': 7})
    assert compiled.status_code == 200, compiled.text
    assert compiled.json()['validation']['status'] == 'validated'


@pytest.mark.parametrize('options', ["reps=21", "overwrite_block_parameters='yes'", "entanglement='unknown'"])
def test_n_local_rejects_invalid_or_oversized_options(options):
    with pytest.raises(QuantumError) as caught:
        parse_source("from qiskit.circuit.library import n_local\nqc=n_local(2,'ry','cx'," + options + ")")
    assert caught.value.code == 'INVALID_ARGUMENTS'


def test_helper_circuits_do_not_replace_qc_and_composition_mapping_is_respected():
    source = ("from qiskit import QuantumCircuit\nqc=QuantumCircuit(3)\nsub=QuantumCircuit(2)\n"
              "sub.h(0)\nsub.cx(0,1)\nqc.compose(sub,qubits=[2,0],inplace=True)")
    reference = QuantumCircuit(3); reference.h(2); reference.cx(2, 0)
    result = same_operator(source, reference)
    assert result["selected_circuit"] == "qc"


def test_qc_selection_and_copy_semantics_are_explicit():
    source = ("from qiskit import QuantumCircuit\nfragment=QuantumCircuit(1)\nfragment.x(0)\n"
              "qc=QuantumCircuit(1)\ncopy=fragment.copy()\ncopy.h(0)\nqc=qc.compose(copy)")
    reference = QuantumCircuit(1); reference.x(0); reference.h(0)
    same_operator(source, reference)


@pytest.mark.parametrize("transform,gate", [
    ("RXGate(0.25).inverse()", RXGate(0.25).inverse()),
    ("HGate().control(1,ctrl_state=0)", HGate().control(1, ctrl_state=0)),
    ("RXGate(0.5).power(0.5)", RXGate(0.5).power(0.5)),
])
def test_gate_transformations_match_qiskit(transform, gate):
    n = gate.num_qubits
    source = ("from qiskit import QuantumCircuit\nfrom qiskit.circuit.library import HGate,RXGate\n"
              f"qc=QuantumCircuit({n})\nqc.append({transform},{list(range(n))!r})")
    reference = QuantumCircuit(n); reference.append(gate, range(n))
    same_operator(source, reference)


def test_fragment_to_gate_and_primary_inverse_preserve_phase():
    source = ("from qiskit import QuantumCircuit\nsub=QuantumCircuit(1)\nsub.h(0)\nsub.global_phase=0.25\n"
              "qc=QuantumCircuit(1)\nqc.append(sub.to_gate(),[0])\nqc=qc.inverse()")
    reference = QuantumCircuit(1); reference.h(0); reference.global_phase=0.25
    same_operator(source, reference.inverse())


def test_unitary_matrix_complex_literals_and_numpy_dtype():
    source = ("import numpy as np\nfrom qiskit import QuantumCircuit\nfrom qiskit.circuit.library import UnitaryGate\n"
              "matrix=np.array([[0,1j],[1j,0]],dtype=complex)\nqc=QuantumCircuit(1)\n"
              "qc.append(UnitaryGate(matrix),[0])")
    reference = QuantumCircuit(1); reference.append(library.UnitaryGate([[0,1j],[1j,0]]), [0])
    same_operator(source, reference)


def test_state_preparation_with_complex_amplitudes_and_export():
    source = ("from qiskit import QuantumCircuit\nfrom qiskit.circuit.library import StatePreparation\n"
              "from math import sqrt\nqc=QuantumCircuit(1)\n"
              "qc.append(StatePreparation([1/sqrt(2),1j/sqrt(2)]),[0])")
    result = simulate(source, shots=128, seed=5)
    bloch = result["bloch_vectors"][0]
    assert bloch["y"] == pytest.approx(1)
    assert result["theoretical_probabilities"] == pytest.approx({"0":0.5,"1":0.5})


def test_pauli_evolution_uses_actual_qiskit_synthesis():
    from qiskit.quantum_info import SparsePauliOp
    source = ("from qiskit import QuantumCircuit\nfrom qiskit.quantum_info import SparsePauliOp\n"
              "from qiskit.circuit.library import PauliEvolutionGate\n"
              "operator=SparsePauliOp.from_list([('ZZ',0.5),('XX',0.25)])\n"
              "qc=QuantumCircuit(2)\nqc.append(PauliEvolutionGate(operator,time=0.125),[0,1])")
    reference = QuantumCircuit(2)
    reference.append(library.PauliEvolutionGate(SparsePauliOp.from_list([('ZZ',0.5),('XX',0.25)]), time=0.125), [0,1])
    same_operator(source, reference)


@pytest.mark.parametrize("body,imports", [
    ("qc=QuantumCircuit(1)\np=Parameter('p')\nqc.rx(p,0)", "from qiskit.circuit import Parameter"),
    ("qc=QuantumCircuit(1)\ngate=HGate().control(10)", "from qiskit.circuit.library import HGate"),
    ("qc=QuantumCircuit(1)\na=real_amplitudes(1000000000)", "from qiskit.circuit.library import real_amplitudes"),
    ("qc=QuantumCircuit(1)\na=real_amplitudes(2,reps=1000000000)", "from qiskit.circuit.library import real_amplitudes"),
    ("qc=QuantumCircuit(1)\ngate=UnitaryGate([[1,1],[0,1]],check_input=False)", "from qiskit.circuit.library import UnitaryGate"),
    ("qc=QuantumCircuit(1)\nqc.compose(1,inplace=True)", ""),
    ("qc=QuantumCircuit(1)\nqc=qc.__class__()", ""),
    ("qc=QuantumCircuit(1)\nvalue=np.load('private.npy')", "import numpy as np"),
])
def test_unsupported_or_oversized_library_inputs_return_explicit_errors(body, imports):
    with pytest.raises(QuantumError):
        parse_source("from qiskit import QuantumCircuit\n"+imports+"\n"+body)


def test_free_parameters_have_an_actionable_error():
    source = "from qiskit import QuantumCircuit\nfrom qiskit.circuit import Parameter\np=Parameter('theta')\nqc=QuantumCircuit(1)\nqc.rx(p,0)"
    with pytest.raises(QuantumError) as caught:
        parse_source(source)
    assert caught.value.code == "UNBOUND_PARAMETERS"
    assert caught.value.details["parameters"] == ["theta"]


def test_composing_measurement_then_a_gate_stays_outside_the_contract():
    source = ("from qiskit import QuantumCircuit\nqc=QuantumCircuit(1,1)\nsub=QuantumCircuit(1,1)\n"
              "sub.measure(0,0)\nqc.compose(sub,inplace=True)\nqc.x(0)")
    with pytest.raises(QuantumError) as caught:
        parse_source(source)
    assert caught.value.code == "NON_TERMINAL_MEASUREMENT"


def test_symbolic_gate_inverse_and_control_bind_before_execution():
    source = ("from qiskit import QuantumCircuit\nfrom qiskit.circuit import ParameterVector\n"
              "from qiskit.circuit.library import RXGate\np=ParameterVector('theta',length=1)\n"
              "qc=QuantumCircuit(2,global_phase=0.125)\n"
              "qc.append(RXGate(p[0]).inverse().control(1),[0,1])\n"
              "qc.assign_parameters([0.5],inplace=True)")
    reference = QuantumCircuit(2, global_phase=0.125)
    reference.append(RXGate(0.5).inverse().control(1), [0, 1])
    same_operator(source, reference)


def test_compose_without_inplace_or_assignment_leaves_primary_unchanged():
    source = ("from qiskit import QuantumCircuit\nqc=QuantumCircuit(1)\nqc.h(0)\n"
              "sub=QuantumCircuit(1)\nsub.x(0)\nqc.compose(sub)")
    reference = QuantumCircuit(1); reference.h(0)
    same_operator(source, reference)


def test_shared_nested_numeric_data_is_rejected_before_large_materialization():
    source = ("import numpy as np\nfrom qiskit import QuantumCircuit\nqc=QuantumCircuit(1)\n"
              "row=[1 for i in range(500)]\nmatrix=[row for i in range(500)]\n"
              "tensor=[matrix for i in range(500)]\nvalue=np.array(tensor)")
    with pytest.raises(QuantumError) as caught:
        parse_source(source)
    assert caught.value.code == "INVALID_ARGUMENTS"
    assert "bounded vectors and matrices" in caught.value.message


@pytest.mark.parametrize("example_id", ["library-ansatz", "library-fragments", "library-state", "library-evolution"])
def test_new_library_examples_run_compile_and_save_over_the_api(client, example_id):
    example = next(item for item in client.get("/api/examples").json() if item["id"] == example_id)
    simulation = client.post("/api/simulate", json={"source": example["source"], "shots": 32, "seed": 7})
    assert simulation.status_code == 200, simulation.text
    run = simulation.json()
    assert sum(run["counts"].values()) == 32
    assert run["selected_circuit"] == "qc"
    compiled = client.post("/api/optimize", json={"source": example["source"], "level": 2, "seed": 7})
    assert compiled.status_code == 200, compiled.text
    assert compiled.json()["validation"]["status"] == "validated"
    saved = client.post("/api/experiments", json={"name": example["name"], "source": example["source"], "simulation_id": run["id"]})
    assert saved.status_code in (200, 201), saved.text
    record = client.get('/api/experiments/' + saved.json()['id']).json()
    assert record["source"] == example["source"]
    assert record["simulation"]["counts"] == run["counts"]


def test_expanded_gate_classes_append_and_simulate():
    source = """from qiskit import QuantumCircuit
from qiskit.circuit.library import (
    U1Gate, U2Gate, U3Gate, CU1Gate, CU3Gate, RVGate,
    MCXGrayCode, MCXRecursive, MCXVChain, MCMTGate,
    AndGate, OrGate, BitwiseXorGate, FullAdderGate, HalfAdderGate,
    ZGate
)

qc = QuantumCircuit(5)
qc.append(U1Gate(0.5), [0])
qc.append(U2Gate(0.1, 0.2), [0])
qc.append(U3Gate(0.1, 0.2, 0.3), [0])
qc.append(CU1Gate(0.5), [0, 1])
qc.append(CU3Gate(0.1, 0.2, 0.3), [0, 1])
qc.append(RVGate(0.1, 0.2, 0.3), [0])
qc.append(MCXGrayCode(2), [0, 1, 2])
qc.append(MCXRecursive(2), [0, 1, 2])
qc.append(MCXVChain(2), [0, 1, 2])
qc.append(MCMTGate(ZGate(), 2, 2), [0, 1, 2, 3])
qc.append(AndGate(2), [0, 1, 2])
qc.append(OrGate(2), [0, 1, 2])
qc.append(BitwiseXorGate(2, 1), [0, 1])
qc.append(FullAdderGate(1), [0, 1, 2, 3])
qc.append(HalfAdderGate(1), [0, 1, 2])
"""
    result = simulate(source, shots=32, seed=42)
    assert sum(result["counts"].values()) == 32
    compiled = optimize(source)
    assert compiled["validation"]["status"] == "validated"
