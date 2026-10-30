import ast
import json
import math
import sys
import pytest
import numpy as np
import qiskit
import qiskit_aer

from qore.quantum import (
    QuantumError,
    parse_source,
    simulate,
    optimize,
    MAX_SOURCE_BYTES,
    MAX_QUBITS,
    MAX_CLBITS,
    MAX_OPERATIONS,
    MAX_SHOTS,
    MAX_EQUIVALENCE_QUBITS,
)

# =====================================================================
# 1. HARDENED AST SANDBOX VALIDATOR (DROP-IN PATCH FOR quantum_engine.py)
# =====================================================================

FORBIDDEN_MODULES = {
    "os", "sys", "subprocess", "shutil", "socket", "urllib", "requests",
    "http", "pathlib", "pickle", "ctypes", "multiprocessing", "importlib",
    "inspect", "builtins", "io", "tempfile", "glob", "signal", "resource"
}

FORBIDDEN_BUILTINS = {
    "eval", "exec", "open", "compile", "__import__", "input", "memoryview",
    "globals", "locals", "vars", "dir", "getattr", "setattr", "delattr",
    "breakpoint", "help", "type", "object", "super", "classmethod", "staticmethod"
}

FORBIDDEN_ATTRIBUTES = {
    "format", "format_map", "gi_frame", "gi_code", "gi_yieldfrom",
    "cr_frame", "cr_code", "ag_frame", "f_back", "f_globals", "f_locals",
    "f_builtins", "f_code", "tb_frame", "tb_next", "func_globals", "func_code"
}


class SandboxSecurityError(Exception):
    pass


def hardened_validate_code(code: str) -> None:
    if len(code.encode("utf-8")) > MAX_SOURCE_BYTES:
        raise SandboxSecurityError(f"Source exceeds {MAX_SOURCE_BYTES} bytes (32 KiB) limit.")

    tree = ast.parse(code)
    for node in ast.walk(tree):
        # Block while loops, function definitions, lambdas, comprehensions, and generators
        if isinstance(node, (ast.While, ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda,
                             ast.ClassDef, ast.GeneratorExp, ast.ListComp, ast.DictComp,
                             ast.SetComp, ast.Try, ast.With, ast.AsyncWith, ast.Yield)):
            raise SandboxSecurityError(f"Construct '{type(node).__name__}' is disallowed in bounded AST mode.")

        # Block restricted imports
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in FORBIDDEN_MODULES:
                    raise SandboxSecurityError(f"Forbidden import: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] in FORBIDDEN_MODULES:
                raise SandboxSecurityError(f"Forbidden import from: {node.module}")

        # Block restricted builtins
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_BUILTINS:
                raise SandboxSecurityError(f"Forbidden builtin call: {node.func.id}()")

        # Block dunder attributes and frame/format escapes
        elif isinstance(node, ast.Attribute):
            if (
                node.attr.startswith("_")
                or node.attr in FORBIDDEN_ATTRIBUTES
            ):
                raise SandboxSecurityError(f"Forbidden attribute access: .{node.attr}")

        # Block exponentiation / bitshift CPU & memory bombs
        elif isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Pow, ast.LShift)):
            if isinstance(node.right, ast.Constant) and isinstance(node.right.value, (int, float)):
                if abs(node.right.value) > 64:
                    raise SandboxSecurityError("Exponent or bitshift exceeds safe constant bound (64).")


# =====================================================================
# 2. RED-TEAM SECURITY & DEPENDENCY VERIFICATION TESTS
# =====================================================================

@pytest.mark.parametrize("malicious_payload", [
    "import os\nos.system('whoami')",
    "from subprocess import Popen",
    "open('/etc/passwd').read()",
    "'{0.__class__.__mro__[1].__subclasses__()}'.format(1)",
    "(x for x in ()).gi_frame.f_back.f_globals",
    "while True:\n    pass",
    "x = 999999 ** 999999",
    "qc._data = []",
    "getattr(qc, '__class__')",
])
def test_red_team_sandbox_blocks_all_escape_vectors(malicious_payload: str):
    with pytest.raises(SandboxSecurityError):
        hardened_validate_code(malicious_payload)


def test_source_size_limit_32kib():
    oversized_code = "# " + ("A" * (MAX_SOURCE_BYTES + 100))
    with pytest.raises(SandboxSecurityError, match="32 KiB"):
        hardened_validate_code(oversized_code)


def test_numpy_2_json_serialization_compatibility():
    """Verifies that NumPy 2.x scalar types are cleanly converted before JSON serialization."""
    sample_metrics = {
        "prob": float(np.float64(0.5)),
        "count": int(np.int64(521)),
        "verified": bool(np.bool_(True)),
    }
    serialized = json.dumps(sample_metrics)
    parsed = json.loads(serialized)
    assert parsed["prob"] == 0.5
    assert parsed["count"] == 521
    assert parsed["verified"] is True


def test_runtime_dependency_health():
    """Audits that core quantum dependencies import cleanly and operator equivalence works."""
    from qiskit import QuantumCircuit, transpile
    from qiskit.quantum_info import Operator

    qc = QuantumCircuit(2)
    qc.h(0)
    qc.x(1)
    qc.x(1)
    qc.cx(0, 1)

    opt_qc = transpile(qc, basis_gates=["u", "cx"], optimization_level=2, seed_transpiler=42)
    assert Operator(qc).equiv(Operator(opt_qc), atol=1e-9) is True


# =====================================================================
# 3. END-TO-END QORE RUNTIME BOUNDARY & SAFETY INTEGRATION TESTS
# =====================================================================

def test_qore_quantum_engine_rejects_malicious_ast_payloads():
    """Ensures QORE's native parse_source rejects the adversarial red-team payloads."""
    payloads = [
        "import os\nos.system('whoami')",
        "from subprocess import Popen",
        "open('/etc/passwd').read()",
        "'{0.__class__.__mro__[1].__subclasses__()}'.format(1)",
        "while True:\n    pass",
        "x = 999999 ** 999999",
        "from qiskit import QuantumCircuit\nqc = QuantumCircuit(2)\nqc._data = []",
        "from qiskit import QuantumCircuit\nqc = QuantumCircuit(2)\ngetattr(qc, '__class__')",
    ]
    for payload in payloads:
        with pytest.raises(QuantumError):
            parse_source(payload)


def test_qore_openqasm_lfi_protection():
    """Audits OpenQASM 2 parser to verify LFI inclusion vectors are blocked."""
    lfi_payload = 'OPENQASM 2.0;\ninclude "../../etc/passwd";\nqreg q[2];\nh q[0];'
    with pytest.raises(QuantumError, match="OpenQASM may include only"):
        parse_source(lfi_payload)


def test_qore_nan_and_inf_angle_rejection():
    """Verifies that NaN, Inf, and out-of-bounds parameters are rejected before synthesis."""
    source_nan = "from qiskit import QuantumCircuit\nqc = QuantumCircuit(1)\nqc.rx(float('nan'), 0)"
    source_inf = "from qiskit import QuantumCircuit\nqc = QuantumCircuit(1)\nqc.rx(float('inf'), 0)"
    with pytest.raises(QuantumError):
        parse_source(source_nan)
    with pytest.raises(QuantumError):
        parse_source(source_inf)


def test_qore_state_and_unitary_cutoffs():
    """Verifies state diagnostics cutoff at 6 qubits and unitary cutoff at 4 qubits."""
    # 7-qubit circuit (exceeds state diagnostics cap of 6)
    source_7q = "from qiskit import QuantumCircuit\nqc = QuantumCircuit(7)\nqc.h(0)\nqc.cx(0, 1)"
    res_7q = parse_source(source_7q)
    assert len(res_7q["bloch_vectors"]) == 0
    assert len(res_7q["statevector_amplitudes"]) == 0
    assert res_7q["unitary_matrix"] == []

    # 5-qubit circuit (within state diagnostics cap of 6, but exceeds unitary cap of 4)
    source_5q = "from qiskit import QuantumCircuit\nqc = QuantumCircuit(5)\nqc.h(0)"
    res_5q = parse_source(source_5q)
    assert len(res_5q["bloch_vectors"]) == 5
    assert len(res_5q["statevector_amplitudes"]) == 32
    assert res_5q["unitary_matrix"] == []

    # 4-qubit circuit (within both 6-qubit state diagnostics and 4-qubit unitary limits)
    source_4q = "from qiskit import QuantumCircuit\nqc = QuantumCircuit(4)\nqc.h(0)"
    res_4q = parse_source(source_4q)
    assert len(res_4q["bloch_vectors"]) == 4
    assert len(res_4q["statevector_amplitudes"]) == 16
    assert len(res_4q["unitary_matrix"]) == 16
