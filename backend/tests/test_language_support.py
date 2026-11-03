"""SDK-backed language parity and pre-compiler safety-boundary regressions."""

from concurrent.futures import ThreadPoolExecutor
import math

import numpy as np
import pytest
from qiskit import QuantumCircuit
from qiskit.quantum_info import Operator

from qore.quantum import QuantumError, capabilities, ir_to_circuit, optimize, parse_source, simulate


QASM3_BELL = '''OPENQASM 3.0;
include "stdgates.inc";
qubit[2] q;
bit[2] c;
h q[0];
cx q[0], q[1];
c = measure q;
'''
QSHARP_BELL = '''namespace Bell {
    open Std.Intrinsic;
    open Std.Measurement;
    @EntryPoint()
    operation Main() : Result[] {
        use qs = Qubit[2];
        H(qs[0]);
        CX(qs[0], qs[1]);
        return MResetEachZ(qs);
    }
}
'''


@pytest.fixture
def qasm3():
    pytest.importorskip("qiskit_qasm3_import")


@pytest.fixture
def qdk():
    return pytest.importorskip("qdk")


def test_qasm3_bell_analysis_simulation_and_optimization(qasm3):
    parsed = parse_source("/* static circuit */\n" + QASM3_BELL)
    assert parsed["language"] == "openqasm-3"
    assert parsed["metrics"]["gate_count"] == 2
    result = simulate(QASM3_BELL, shots=256)
    assert set(result["counts"]) == {"00", "11"}
    assert sum(result["counts"].values()) == 256
    assert optimize(QASM3_BELL)["validation"]["status"] == "validated"


def test_qasm3_exact_angles_broadcast_and_modifiers(qasm3):
    source = '''OPENQASM 3.0; include "stdgates.inc";
    qubit[2] q; h q; rz(-pi / 7) q[0]; inv @ s q[1];
    negctrl @ x q[0], q[1];'''
    expected = QuantumCircuit(2)
    expected.h([0, 1]); expected.rz(-math.pi / 7, 0); expected.sdg(1)
    expected.x(0); expected.cx(0, 1); expected.x(0)
    actual = ir_to_circuit(parse_source(source)["ir"], unitary_only=True)
    np.testing.assert_allclose(Operator(actual).data, Operator(expected).data, atol=1e-9)


@pytest.mark.parametrize("source", [
    'OPENQASM 3; include "../../private.inc"; qubit q;',
    'OPENQASM 3; include /* comment */ "private.inc"; qubit q;',
    'OPENQASM 3; qubit[1000000000] q;',
    'OPENQASM 3; qubit[6] q; qubit[5] p;',
    'OPENQASM 3; qubit q; bit[1000000000] c;',
    'OPENQASM 3; qubit q; while (true) { x q; }',
    'OPENQASM 3; qubit q; for int i in [0:1000000000] { x q; }',
    'OPENQASM 3; gate h a { x a; } qubit q; h q;',
    'OPENQASM 3; qubit q; pow(1000000000) @ x q;',
    'OPENQASM 3; qubit q; rx(1e11 * 1e11) q;',
    'OPENQASM 3; qubit q; rx(1 / 0) q;',
    'OPENQASM 3; qubit q; reset q;',
    'OPENQASM 3; qubit q; delay[100ns] q;',
    'OPENQASM 3; input float theta; qubit q; rx(theta) q;',
    'OPENQASM 3; qubit q; bit c; if (c == 1) x q;',
])
def test_qasm3_unsupported_features_rejected_before_conversion(qasm3, monkeypatch, source):
    import qiskit_qasm3_import
    def forbidden(*args, **kwargs):
        pytest.fail("Unvalidated source reached SDK conversion")
    monkeypatch.setattr(qiskit_qasm3_import, "convert", forbidden)
    with pytest.raises(QuantumError):
        parse_source(source)


def test_qasm3_measurement_mapping_and_terminal_requirement(qasm3):
    result = simulate('OPENQASM 3; include "stdgates.inc"; qubit[2] q; bit[2] c; x q[0]; c[1] = measure q[0]; c[0] = measure q[1];', shots=32)
    assert result["counts"] == {"10": 32}
    with pytest.raises(QuantumError) as error:
        parse_source('OPENQASM 3; include "stdgates.inc"; qubit q; bit c = measure q; x q;')
    assert error.value.code == "NON_TERMINAL_MEASUREMENT"


def test_qsharp_bell_compiles_qir_and_runs_end_to_end(qdk, client):
    parsed = client.post("/api/parse", json={"source": QSHARP_BELL})
    assert parsed.status_code == 200
    data = parsed.json()
    assert data["language"] == "qsharp"
    assert data["compiler"]["name"] == "Microsoft QDK"
    assert data["compiler"]["target_profile"] == "Base"
    assert "define" in data["qir"] and "__quantum__qis__h" in data["qir"]
    assert data["warnings"] and "resets" in data["warnings"][0]
    response = client.post("/api/simulate", json={"source": QSHARP_BELL, "shots": 256})
    assert response.status_code == 200
    result = response.json()
    assert result["source"] == QSHARP_BELL
    assert result["qir"] == data["qir"]
    assert set(result["counts"]) == {"00", "11"}
    assert optimize(QSHARP_BELL)["validation"]["status"] == "validated"


def test_qsharp_exact_angles_and_adjoint(qdk):
    source = '''open Std.Math;
    operation Main() : Result[] {
        use q = Qubit[2];
        Rx(PI() / 7.0, q[0]);
        Adjoint Ry(0.123456789123, q[1]);
        R1(-0.876543219, q[0]);
        Adjoint S(q[1]);
        CZ(q[0], q[1]);
        return MResetEachZ(q);
    }'''
    expected = QuantumCircuit(2)
    expected.rx(math.pi / 7, 0); expected.ry(-0.123456789123, 1)
    expected.p(-0.876543219, 0); expected.sdg(1); expected.cz(0, 1)
    actual = ir_to_circuit(parse_source(source)["ir"], unitary_only=True)
    np.testing.assert_allclose(Operator(actual).data, Operator(expected).data, atol=1e-9)


def test_qsharp_return_order_matches_microsoft_sdk_results(qdk):
    source = '''operation Main() : Result[] {
        use q = Qubit[2]; X(q[0]); return [MResetZ(q[1]), MResetZ(q[0])];
    }'''
    context = qdk.Context()
    context.eval(source)
    sdk_results = context.run("Main()", 4)
    assert all(result == [qdk.Result.Zero, qdk.Result.One] for result in sdk_results)
    assert simulate(source, shots=32)["counts"] == {"10": 32}


@pytest.mark.parametrize("body", [
    'use q = Qubit[1000000000]; return MResetEachZ(q)',
    'use q = Qubit[6]; use p = Qubit[5]; return MResetEachZ(q)',
    'use q = Qubit[1]; while true { X(q[0]); } return MResetEachZ(q)',
    'use q = Qubit[1]; Main(); return MResetEachZ(q)',
    'use q = Qubit[1]; Message("private"); return MResetEachZ(q)',
    'use q = Qubit[1]; DumpMachine(); return MResetEachZ(q)',
    'use q = Qubit[1]; X(q[1]); return MResetEachZ(q)',
    'use q = Qubit[2]; CX(q[0], q[0]); return MResetEachZ(q)',
    'use q = Qubit[1]; Rx(1e11 * 1e11, q[0]); return MResetEachZ(q)',
    'use q = Qubit[1]; let result = M(q[0]); X(q[0]); return [result]',
    'use q = Qubit[1]; return [M(q[0]), M(q[0])]',
    'use q = Qubit[1]; return MResetEachZ(q); X(q[0])',
])
def test_qsharp_rejection_precedes_compiler_context(qdk, monkeypatch, body):
    def forbidden(*args, **kwargs):
        pytest.fail("Unvalidated Q# reached Microsoft compiler")
    monkeypatch.setattr(qdk, "Context", forbidden)
    with pytest.raises(QuantumError):
        parse_source(f"operation Main() : Result[] {{ {body}; }}")


def test_qsharp_operation_bound_checked_before_sdk(qdk, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Oversized Q# reached Microsoft compiler")
    monkeypatch.setattr(qdk, "Context", forbidden)
    with pytest.raises(QuantumError) as error:
        parse_source('operation Main() : Result { use q = Qubit();' + 'H(q);' * 500 + 'return MResetZ(q); }')
    assert error.value.code == "RESOURCE_LIMIT"


def test_qsharp_contexts_do_not_share_definitions(qdk):
    sources = ['operation Main() : Result { use q = Qubit(); ' + gate + ' return MResetZ(q); }'
               for gate in ('X(q);', '', 'X(q);', '')]
    with ThreadPoolExecutor(max_workers=4) as pool:
        outputs = list(pool.map(parse_source, sources))
    assert [item["metrics"]["gate_count"] for item in outputs] == [1, 0, 1, 0]
    assert all(item["compiler"]["name"] == "Microsoft QDK" for item in outputs)


def test_optional_dependency_unavailable_is_explicit(monkeypatch):
    import qore.language_support as languages
    monkeypatch.setattr(languages, "available", lambda name: False)
    for source in (QASM3_BELL, QSHARP_BELL):
        with pytest.raises(QuantumError) as error:
            parse_source(source)
        assert error.value.code == "DEPENDENCY_UNAVAILABLE"


@pytest.mark.parametrize("imports,call", [
    ('from qiskit import QuantumCircuit, transpile', 'transpile'),
    ('from qiskit import QuantumCircuit\nfrom qiskit import transpile as compile_circuit', 'compile_circuit'),
    ('from qiskit import QuantumCircuit\nimport qiskit', 'qiskit.transpile'),
])
def test_bounded_source_transpile_uses_qiskit(imports, call):
    source = f'{imports}\nqc=QuantumCircuit(2)\nqc.h(0)\nqc.h(0)\nqc.cx(0,1)\nqc={call}(qc, optimization_level=3, basis_gates=["u","cx"], seed_transpiler=7)'
    parsed = parse_source(source)
    assert parsed["metrics"]["gate_count"] == 1
    expected = QuantumCircuit(2); expected.cx(0, 1)
    assert Operator(ir_to_circuit(parsed["ir"])).equiv(Operator(expected))


@pytest.mark.parametrize("extra", [
    'backend="remote"', 'callback="code"', 'optimization_level=4', 'basis_gates=["reset"]',
    'seed_transpiler=-1', 'coupling_map=[[0,1]]',
])
def test_source_transpile_rejects_unbounded_options(extra):
    with pytest.raises(QuantumError):
        parse_source(f'from qiskit import QuantumCircuit, transpile\nqc=QuantumCircuit(2)\nqc=transpile(qc, {extra})')


def test_source_transpile_call_limit():
    source = 'from qiskit import QuantumCircuit, transpile\nqc=QuantumCircuit(1)\nfor i in range(17):\n    qc=transpile(qc)'
    with pytest.raises(QuantumError) as error:
        parse_source(source)
    assert error.value.code == "RESOURCE_LIMIT"


@pytest.mark.parametrize("imports,call", [
    ('from qiskit import qasm3', 'qasm3.loads'),
    ('from qiskit.qasm3 import loads as load_circuit', 'load_circuit'),
    ('import qiskit.qasm3', 'qiskit.qasm3.loads'),
])
def test_qasm3_in_memory_python_loader(qasm3, imports, call):
    source = f'{imports}\nqc={call}({QASM3_BELL!r})'
    assert simulate(source, shots=128)["theoretical_probabilities"] == {"00": 0.5, "01": 0.0, "10": 0.0, "11": 0.5}


def test_qasm2_in_memory_python_loader():
    source = 'from qiskit.qasm2 import loads\nqc=loads(\'OPENQASM 2.0; include "qelib1.inc"; qreg q[1]; x q[0];\')'
    assert simulate(source, shots=16)["counts"] == {"1": 16}
    with pytest.raises(QuantumError):
        parse_source('from qiskit.qasm2 import load\nqc=load("private.qasm")')


def test_capabilities_separate_installation_from_execution():
    data = capabilities()
    assert {item["id"] for item in data["languages"]} == {"qsharp", "openqasm-3", "openqasm-2", "qiskit-circuit-python"}
    assert all(item["arbitrary_python"] is False for item in data["languages"])
    assert data["limits"]["max_source_sdk_calls"] == 16
    assert "No loops" in data["language_subsets"]["openqasm-3"]
    assert "helper operations" in data["language_subsets"]["qsharp"]
