"""The bounded QORE quantum processing layer.

User Python is parsed as syntax and interpreted by a small allowlist. It is never
passed to Python's exec/eval, imported, or given access to Python objects.
"""

from __future__ import annotations

import ast
import hashlib
import importlib.metadata
import math
import platform
import time
from collections import Counter
from typing import Any

import numpy as np
from qiskit import QuantumCircuit, transpile, qasm2
from qiskit.quantum_info import DensityMatrix, Operator, Statevector, partial_trace
from qiskit_aer import AerSimulator
from qiskit_aer.noise import NoiseModel, depolarizing_error
import qiskit.circuit.library as qiskit_gate_lib


IR_VERSION = "1.0"
MAX_QUBITS = 10
MAX_CLBITS = 10
MAX_OPERATIONS = 500
MAX_SOURCE_BYTES = 32 * 1024
MAX_SHOTS = 100_000
MAX_EQUIVALENCE_QUBITS = 6
MAX_AST_NODES = 5_000
MAX_AST_DEPTH = 64
MAX_STATEMENT_STEPS = 2_000
MAX_ABSOLUTE_NUMBER = 1e12
EQUIVALENCE_TOLERANCE = 1e-9
UNITARITY_TOLERANCE = 1e-8
DISPLAY_DIGITS = 8
PAULI_X = np.array([[0, 1], [1, 0]], dtype=complex)
PAULI_Y = np.array([[0, -1j], [1j, 0]], dtype=complex)
PAULI_Z = np.array([[1, 0], [0, -1]], dtype=complex)
NUMERIC_MATH_NAMES = (
    "pi", "tau", "e", "sin", "cos", "tan", "sqrt", "exp", "abs", "asin", "acos", "atan",
    "atan2", "hypot", "radians", "degrees", "log", "log2", "log10", "floor", "ceil", "pow",
)

# Supported standard gate classes from qiskit.circuit.library
SUPPORTED_GATE_CLASSES: dict[str, type] = {
    # 1-qubit unitary gates
    "HGate": qiskit_gate_lib.HGate,
    "XGate": qiskit_gate_lib.XGate,
    "YGate": qiskit_gate_lib.YGate,
    "ZGate": qiskit_gate_lib.ZGate,
    "SGate": qiskit_gate_lib.SGate,
    "SdgGate": qiskit_gate_lib.SdgGate,
    "TGate": qiskit_gate_lib.TGate,
    "TdgGate": qiskit_gate_lib.TdgGate,
    "SXGate": qiskit_gate_lib.SXGate,
    "SXdgGate": qiskit_gate_lib.SXdgGate,
    "RXGate": qiskit_gate_lib.RXGate,
    "RYGate": qiskit_gate_lib.RYGate,
    "RZGate": qiskit_gate_lib.RZGate,
    "PhaseGate": qiskit_gate_lib.PhaseGate,
    "UGate": qiskit_gate_lib.UGate,
    "RGate": qiskit_gate_lib.RGate,
    # 2-qubit unitary gates
    "CXGate": qiskit_gate_lib.CXGate,
    "CYGate": qiskit_gate_lib.CYGate,
    "CZGate": qiskit_gate_lib.CZGate,
    "CHGate": qiskit_gate_lib.CHGate,
    "SwapGate": qiskit_gate_lib.SwapGate,
    "ECRGate": qiskit_gate_lib.ECRGate,
    "iSwapGate": qiskit_gate_lib.iSwapGate,
    "CSXGate": qiskit_gate_lib.CSXGate,
    "CSGate": qiskit_gate_lib.CSGate,
    "CSdgGate": qiskit_gate_lib.CSdgGate,
    "DCXGate": qiskit_gate_lib.DCXGate,
    "CPhaseGate": qiskit_gate_lib.CPhaseGate,
    "CRXGate": qiskit_gate_lib.CRXGate,
    "CRYGate": qiskit_gate_lib.CRYGate,
    "CRZGate": qiskit_gate_lib.CRZGate,
    "RXXGate": qiskit_gate_lib.RXXGate,
    "RYYGate": qiskit_gate_lib.RYYGate,
    "RZZGate": qiskit_gate_lib.RZZGate,
    "RZXGate": qiskit_gate_lib.RZXGate,
    "CUGate": qiskit_gate_lib.CUGate,
    # 3-qubit unitary gates
    "CCXGate": qiskit_gate_lib.CCXGate,
    "CCZGate": qiskit_gate_lib.CCZGate,
    "RCCXGate": qiskit_gate_lib.RCCXGate,
    "CSwapGate": qiskit_gate_lib.CSwapGate,
    # Multi-qubit controlled gates
    "MCXGate": qiskit_gate_lib.MCXGate,
}

# name: (number of numerical parameters, number of qubits).
GATES: dict[str, tuple[int, int]] = {
    **{name: (0, 1) for name in ("id", "x", "y", "z", "h", "s", "sdg", "t", "tdg", "sx", "sxdg")},
    **{name: (1, 1) for name in ("rx", "ry", "rz", "p")},
    "u": (3, 1),
    "r": (2, 1),
    **{name: (0, 2) for name in ("cx", "cy", "cz", "ch", "swap", "ecr", "iswap", "csx", "cs", "csdg", "dcx")},
    **{name: (1, 2) for name in ("cp", "crx", "cry", "crz", "rxx", "ryy", "rzz", "rzx")},
    "cu": (4, 2),
    "ccx": (0, 3),
    "ccz": (0, 3),
    "rccx": (0, 3),
    "cswap": (0, 3),
}
ALIASES = {"cnot": "cx", "toffoli": "ccx", "i": "id", "u3": "u", "u2": "u", "u1": "p", "cu1": "cp", "cu3": "cu"}
ONE_QUBIT_NOISE_GATES = [name for name, (_params, qubits) in GATES.items() if qubits == 1]
TWO_QUBIT_NOISE_GATES = [name for name, (_params, qubits) in GATES.items() if qubits == 2]
THREE_QUBIT_NOISE_GATES = [name for name, (_params, qubits) in GATES.items() if qubits == 3]
METRIC_DEFINITION = (
    "Gate count and gate types count unitary operations only; measurements and "
    "barriers are excluded. Two-qubit gate count counts unitary instructions on "
    "exactly two qubits. Depth is Qiskit circuit depth, including measurements "
    "and excluding barriers. Three-qubit gates are one gate before decomposition."
)


class QuantumError(Exception):
    """An expected error that is safe to report to the client."""

    def __init__(self, code: str, message: str, details: Any = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details


def _error(code: str, message: str, node: ast.AST | None = None) -> QuantumError:
    details = None
    if node is not None and hasattr(node, "lineno"):
        details = {"line": node.lineno, "column": getattr(node, "col_offset", 0) + 1}
    return QuantumError(code, message, details)


def _integer(value: Any, label: str, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise QuantumError("INVALID_INPUT", f"{label} must be an integer between {minimum} and {maximum}.")
    return value


def _number(value: Any, label: str = "Parameter") -> float:
    if type(value) not in (int, float) or abs(value) > MAX_ABSOLUTE_NUMBER or not math.isfinite(value):
        raise QuantumError("INVALID_PARAMETER", f"{label} must be a finite number with absolute value at most {MAX_ABSOLUTE_NUMBER:g}.")
    return float(value)


def _bounded_probability(value: Any, label: str) -> float:
    """Validate noise probabilities at the public quantum boundary."""
    if type(value) not in (int, float) or not math.isfinite(value) or not 0.0 <= value <= 0.5:
        raise QuantumError("INVALID_INPUT", f"{label} must be a finite number between 0 and 0.5.")
    return float(value)


def versions() -> dict[str, str]:
    return {
        "qore_ir": IR_VERSION,
        "qiskit": importlib.metadata.version("qiskit"),
        "qiskit_aer": importlib.metadata.version("qiskit-aer"),
        "python": platform.python_version(),
        "numpy": np.__version__,
    }


def capabilities() -> dict[str, Any]:
    """Describe the executable quantum surface without implying arbitrary Python support."""
    return {
        "languages": [
            {"id": "qiskit-circuit-python", "label": "Qiskit circuit-building Python",
             "execution": "bounded_ast_interpreter", "arbitrary_python": False},
            {"id": "openqasm-2", "label": "OpenQASM 2.0",
             "execution": "qiskit_qasm2_parser", "arbitrary_python": False},
        ],
        "modules": {
            "qiskit": "QuantumCircuit, QuantumRegister, ClassicalRegister",
            "qiskit.circuit.library": "supported standard gate classes through constructors and circuit.append",
            "qiskit_aer": "AerSimulator through QORE simulation settings",
            "math": "bounded numeric constants and functions",
            "numpy": "bounded numeric constants and functions; no array/runtime access",
        },
        "gates": {
            name: {"parameters": parameter_count, "qubits": qubit_count}
            for name, (parameter_count, qubit_count) in sorted(GATES.items())
        },
        "gate_classes": sorted(SUPPORTED_GATE_CLASSES),
        "circuit_methods": ["barrier", "measure", "measure_all", "draw", "depth", "size", "width"],
        "workflows": [
            "parse and validate", "shot simulation", "ideal probabilities", "Bloch vectors and purity",
            "statevector amplitudes", "unitary matrix with U†U residual", "noise simulation",
            "classical fidelity and Hellinger distance", "Forge transpilation and equivalence",
            "OpenQASM 2.0 import and export", "immutable Ledger evidence",
        ],
        "simulation_methods": ["statevector", "matrix_product_state", "stabilizer"],
        "limits": {
            "max_source_bytes": MAX_SOURCE_BYTES, "max_qubits": MAX_QUBITS, "max_clbits": MAX_CLBITS,
            "max_operations": MAX_OPERATIONS, "max_shots": MAX_SHOTS,
            "operator_validation_max_qubits": MAX_EQUIVALENCE_QUBITS,
        },
        "safety_boundary": (
            "Circuit source is parsed and interpreted. It is never passed to exec/eval and cannot access the host "
            "filesystem, network, subprocesses, package installation, provider credentials, or arbitrary imports."
        ),
    }


class _SourceInterpreter:
    """Interpret only bounded circuit-building syntax, never Python code."""

    def __init__(self) -> None:
        self.values: dict[str, Any] = {
            "__name__": "__main__",
            "True": True,
            "False": False,
        }
        self.constructors: set[str] = set()
        self.qreg_constructors: set[str] = set()
        self.creg_constructors: set[str] = set()
        self.gate_constructors: dict[str, type] = {}
        self.quantum_registers: dict[str, int] = {}
        self.classical_registers: dict[str, int] = {}
        self.modules: dict[str, str] = {}
        self.constants: set[str] = set()
        self.circuit: QuantumCircuit | None = None
        self.circuit_name: str | None = None
        self.steps = 0
        self.has_measurement = False

    def run(self, source: str) -> QuantumCircuit:
        try:
            tree = ast.parse(source, mode="exec")
        except SyntaxError as exc:
            raise QuantumError("SYNTAX_ERROR", exc.msg, {"line": exc.lineno, "column": exc.offset}) from exc
        except (ValueError, RecursionError) as exc:
            raise QuantumError("SYNTAX_ERROR", "Source cannot be parsed as a bounded Python program.") from exc
        node_count = 0
        pending = [(tree, 0)]
        while pending:
            current, depth = pending.pop()
            node_count += 1
            if node_count > MAX_AST_NODES or depth > MAX_AST_DEPTH:
                raise _error("RESOURCE_LIMIT", f"Source exceeds {MAX_AST_NODES} syntax nodes or nesting depth {MAX_AST_DEPTH}.", current)
            pending.extend((child, depth + 1) for child in ast.iter_child_nodes(current))
        for statement in tree.body:
            self.statement(statement)
        if self.circuit is None:
            raise QuantumError("MISSING_CIRCUIT", "Declare one circuit with qc = QuantumCircuit(qubits, classical_bits).")
        return self.circuit

    def bindable(self, name: str, node: ast.AST) -> None:
        if name == "range" or name in self.modules or name in self.constructors or name in self.constants or name == self.circuit_name:
            raise _error("UNSUPPORTED_SOURCE", f"Cannot replace reserved name '{name}'.", node)
        if name.startswith("__") and name != "__name__":
            raise _error("UNSUPPORTED_SOURCE", "Double-underscore names are not supported.", node)

    def statement(self, node: ast.stmt) -> None:
        self.steps += 1
        if self.steps > MAX_STATEMENT_STEPS:
            raise _error("RESOURCE_LIMIT", f"Program exceeds {MAX_STATEMENT_STEPS} interpreted statement steps.", node)
        try:
            self._statement(node)
        except QuantumError as exc:
            if exc.details is None:
                exc.details = {"line": node.lineno, "column": node.col_offset + 1}
            raise
        except (TypeError, ValueError, OverflowError, ZeroDivisionError) as exc:
            raise _error("INVALID_INPUT", str(exc), node) from exc

    def _statement(self, node: ast.stmt) -> None:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            self.import_statement(node)
            return
        if isinstance(node, ast.If):
            cond = bool(self.expression(node.test))
            branch = node.body if cond else node.orelse
            for child in branch:
                self.statement(child)
            return
        if isinstance(node, ast.AugAssign):
            if not isinstance(node.target, ast.Name):
                raise _error("UNSUPPORTED_SOURCE", "Augmented assignment targets must be variable names.", node)
            target = node.target.id
            current = self.values.get(target, 0)
            val = self.expression(node.value)
            if isinstance(node.op, ast.Add):
                self.values[target] = current + val
            elif isinstance(node.op, ast.Sub):
                self.values[target] = current - val
            elif isinstance(node.op, ast.Mult):
                self.values[target] = current * val
            elif isinstance(node.op, ast.Div):
                self.values[target] = current / val
            return
        if isinstance(node, ast.Assign):
            if len(node.targets) != 1:
                raise _error("UNSUPPORTED_SOURCE", "Use one simple assignment target.", node)
            target = node.targets[0]
            if isinstance(target, ast.Attribute):
                if not (isinstance(target.value, ast.Name) and target.value.id == self.circuit_name and target.attr == "global_phase"):
                    raise _error("UNSUPPORTED_SOURCE", "Only qc.global_phase may be assigned as an attribute.", node)
                assert self.circuit is not None
                self.circuit.global_phase = _number(self.expression(node.value), "Global phase")
                return
            if not isinstance(target, ast.Name):
                raise _error("UNSUPPORTED_SOURCE", "Assignment targets must be variable names.", node)
            self.bindable(target.id, node)
            if isinstance(node.value, ast.Call):
                if isinstance(node.value.func, ast.Attribute) and node.value.func.attr == "from_qasm_str":
                    if len(node.value.args) == 1:
                        qasm_str = str(self.expression(node.value.args[0]))
                        self.circuit = qasm2.loads(qasm_str)
                        self.circuit_name = target.id
                        self.values.pop(target.id, None)
                        return
                if self.is_qreg_constructor(node.value.func):
                    if len(node.value.args) not in (1, 2) or node.value.keywords:
                        raise _error("UNSUPPORTED_SOURCE", "Use QuantumRegister(size) or QuantumRegister(size, 'name').", node)
                    n = _integer(self.expression(node.value.args[0]), "Quantum register size", 1, MAX_QUBITS)
                    self.quantum_registers[target.id] = n
                    self.values[target.id] = list(range(n))
                    return
                if self.is_creg_constructor(node.value.func):
                    if len(node.value.args) not in (1, 2) or node.value.keywords:
                        raise _error("UNSUPPORTED_SOURCE", "Use ClassicalRegister(size) or ClassicalRegister(size, 'name').", node)
                    m = _integer(self.expression(node.value.args[0]), "Classical register size", 1, MAX_CLBITS)
                    self.classical_registers[target.id] = m
                    self.values[target.id] = list(range(m))
                    return
                if self.is_constructor(node.value.func):
                    if self.circuit is not None:
                        raise _error("UNSUPPORTED_SOURCE", "A program must contain exactly one circuit.", node)
                    if node.value.keywords or len(node.value.args) not in (1, 2):
                        raise _error("UNSUPPORTED_SOURCE", "Use QuantumCircuit(qubits) or QuantumCircuit(qubits, classical_bits).", node)
                    arg0 = node.value.args[0]
                    if isinstance(arg0, ast.Name) and arg0.id in self.quantum_registers:
                        n = self.quantum_registers[arg0.id]
                    else:
                        n = _integer(self.expression(arg0), "Qubit count", 1, MAX_QUBITS)
                    if len(node.value.args) == 2:
                        arg1 = node.value.args[1]
                        if isinstance(arg1, ast.Name) and arg1.id in self.classical_registers:
                            m = self.classical_registers[arg1.id]
                        else:
                            m = _integer(self.expression(arg1), "Classical bit count", 0, MAX_CLBITS)
                    else:
                        m = 0
                    self.circuit = QuantumCircuit(n, m)
                    self.circuit_name = target.id
                    self.values.pop(target.id, None)
                    return
            self.values[target.id] = self.expression(node.value)
            return
        if isinstance(node, ast.Expr):
            if isinstance(node.value, ast.Constant):
                return  # Python-style documentation strings or constants
            if isinstance(node.value, ast.Call):
                func = node.value.func
                # Safely ignore print(...) calls
                if isinstance(func, ast.Name) and func.id == "print":
                    return
                # Safely ignore inspection calls like qc.draw(), qc.depth(), qc.size(), qc.width()
                if isinstance(func, ast.Attribute) and func.attr in ("draw", "depth", "size", "width"):
                    return
                self.circuit_call(node.value)
                return
        if isinstance(node, ast.For):
            if node.orelse or not isinstance(node.target, ast.Name):
                raise _error("UNSUPPORTED_SOURCE", "Only simple for loops without else are supported.", node)
            self.bindable(node.target.id, node)
            iterable = self.expression(node.iter)
            if not isinstance(iterable, (list, tuple, range)):
                raise _error("UNSUPPORTED_SOURCE", "Loop over a finite range or a literal list of indices.", node)
            if len(iterable) > MAX_OPERATIONS:
                raise _error("RESOURCE_LIMIT", f"Loops are limited to {MAX_OPERATIONS} iterations.", node)
            for value in iterable:
                if type(value) is not int:
                    raise _error("UNSUPPORTED_SOURCE", "Loop values must be integer indices.", node)
                self.values[node.target.id] = value
                for child in node.body:
                    self.statement(child)
            return
        raise _error("UNSUPPORTED_SOURCE", f"{type(node).__name__} is outside the supported circuit-building subset.", node)

    def import_statement(self, node: ast.Import | ast.ImportFrom) -> None:
        if isinstance(node, ast.Import):
            for item in node.names:
                if item.name not in ("qiskit", "qiskit.circuit", "qiskit.circuit.library", "math", "numpy"):
                    raise _error("UNSUPPORTED_IMPORT", f"Import '{item.name}' is not supported; no user imports are executed.", node)
                alias = item.asname or item.name
                self.bindable(alias, node)
                self.values.pop(alias, None)
                self.modules[alias] = item.name
            return
        if node.level or node.module not in ("qiskit", "qiskit.circuit", "qiskit.circuit.library", "math", "numpy"):
            raise _error("UNSUPPORTED_IMPORT", "Only QuantumCircuit, QuantumRegister, ClassicalRegister, standard gate classes, and numeric math constants can be imported.", node)
        for item in node.names:
            alias = item.asname or item.name
            self.bindable(alias, node)
            self.values.pop(alias, None)
            if node.module in ("qiskit", "qiskit.circuit"):
                if item.name in ("QuantumCircuit", "*"):
                    self.constructors.add(alias if item.name != "*" else "QuantumCircuit")
                if item.name in ("QuantumRegister", "*"):
                    self.qreg_constructors.add(alias if item.name != "*" else "QuantumRegister")
                if item.name in ("ClassicalRegister", "*"):
                    self.creg_constructors.add(alias if item.name != "*" else "ClassicalRegister")
                if item.name in SUPPORTED_GATE_CLASSES:
                    self.gate_constructors[alias] = SUPPORTED_GATE_CLASSES[item.name]
                if item.name not in ("QuantumCircuit", "QuantumRegister", "ClassicalRegister", "*") and item.name not in SUPPORTED_GATE_CLASSES:
                    raise _error(
                        "UNSUPPORTED_IMPORT",
                        f"Import '{item.name}' from '{node.module}' is outside the supported circuit-building subset.",
                        node,
                    )
            elif node.module == "qiskit.circuit.library":
                if item.name == "*":
                    for gate_name, gate_cls in SUPPORTED_GATE_CLASSES.items():
                        self.gate_constructors[gate_name] = gate_cls
                elif item.name in SUPPORTED_GATE_CLASSES:
                    self.gate_constructors[alias] = SUPPORTED_GATE_CLASSES[item.name]
                else:
                    raise _error(
                        "UNSUPPORTED_IMPORT",
                        f"Gate class '{item.name}' from 'qiskit.circuit.library' is outside the supported gate subset.",
                        node,
                    )
            elif node.module in ("math", "numpy"):
                if item.name == "*":
                    for fn in NUMERIC_MATH_NAMES:
                        if node.module == "numpy" and fn == "tau":
                            continue
                        self.values[fn] = getattr(math, fn if fn != "abs" else "fabs")
                        self.constants.add(fn)
                elif item.name in NUMERIC_MATH_NAMES and not (node.module == "numpy" and item.name == "tau"):
                    fn = getattr(math, item.name if item.name != "abs" else "fabs")
                    self.values[alias] = fn
                    self.constants.add(alias)
                else:
                    raise _error(
                        "UNSUPPORTED_IMPORT",
                        f"Import '{item.name}' from '{node.module}' is outside the supported numeric subset.",
                        node,
                    )
            else:
                raise _error("UNSUPPORTED_IMPORT", f"Import '{item.name}' from '{node.module}' is not supported.", node)

    def _resolve_gate_class(self, node: ast.AST | None) -> type | None:
        if node is None:
            return None
        if isinstance(node, ast.Name) and node.id in self.gate_constructors:
            return self.gate_constructors[node.id]
        if isinstance(node, ast.Attribute) and node.attr in SUPPORTED_GATE_CLASSES:
            val = node.value
            if isinstance(val, ast.Name) and (val.id in ("library", "circuit_library") or self.modules.get(val.id) in ("qiskit.circuit.library", "qiskit.circuit", "qiskit")):
                return SUPPORTED_GATE_CLASSES[node.attr]
            if isinstance(val, ast.Attribute) and val.attr in ("library", "circuit"):
                return SUPPORTED_GATE_CLASSES[node.attr]
        return None

    def is_constructor(self, node: ast.AST) -> bool:
        return (isinstance(node, ast.Name) and node.id in self.constructors) or (
            isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
            and self.modules.get(node.value.id) == "qiskit" and node.attr == "QuantumCircuit"
        )

    def is_qreg_constructor(self, node: ast.AST) -> bool:
        return (isinstance(node, ast.Name) and node.id in self.qreg_constructors) or (
            isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
            and self.modules.get(node.value.id) == "qiskit" and node.attr == "QuantumRegister"
        )

    def is_creg_constructor(self, node: ast.AST) -> bool:
        return (isinstance(node, ast.Name) and node.id in self.creg_constructors) or (
            isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
            and self.modules.get(node.value.id) == "qiskit" and node.attr == "ClassicalRegister"
        )

    def expression(self, node: ast.AST) -> Any:
        if isinstance(node, ast.Constant):
            if type(node.value) in (int, float):
                _number(node.value)
                return node.value
            if isinstance(node.value, (str, bool)):
                return node.value
        if isinstance(node, ast.Name) and node.id in self.values:
            return self.values[node.id]
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            module = self.modules.get(node.value.id)
            if module in ("math", "numpy") and node.attr in ("pi", "tau", "e") and not (module == "numpy" and node.attr == "tau"):
                return getattr(math, node.attr)
        if isinstance(node, (ast.List, ast.Tuple)):
            if len(node.elts) > MAX_OPERATIONS:
                raise _error("RESOURCE_LIMIT", "Literal lists are limited to 500 entries.", node)
            return [self.expression(item) for item in node.elts]
        if isinstance(node, ast.Compare):
            left = self.expression(node.left)
            for op, comp in zip(node.ops, node.comparators):
                right = self.expression(comp)
                if isinstance(op, ast.Eq) and not (left == right): return False
                elif isinstance(op, ast.NotEq) and not (left != right): return False
                elif isinstance(op, ast.Lt) and not (left < right): return False
                elif isinstance(op, ast.LtE) and not (left <= right): return False
                elif isinstance(op, ast.Gt) and not (left > right): return False
                elif isinstance(op, ast.GtE) and not (left >= right): return False
                elif isinstance(op, ast.In) and not (left in right): return False
                elif isinstance(op, ast.NotIn) and not (left not in right): return False
                left = right
            return True
        if isinstance(node, ast.BoolOp):
            if isinstance(node.op, ast.And):
                return all(bool(self.expression(v)) for v in node.values)
            if isinstance(node.op, ast.Or):
                return any(bool(self.expression(v)) for v in node.values)
        if isinstance(node, ast.UnaryOp):
            if isinstance(node.op, ast.Not):
                return not bool(self.expression(node.operand))
            if isinstance(node.op, (ast.UAdd, ast.USub)):
                value = self.expression(node.operand)
                _number(value)
                return value if isinstance(node.op, ast.UAdd) else -value
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
            left, right = self.expression(node.left), self.expression(node.right)
            _number(left)
            _number(right)
            try:
                if isinstance(node.op, ast.Add):
                    result = left + right
                elif isinstance(node.op, ast.Sub):
                    result = left - right
                elif isinstance(node.op, ast.Mult):
                    result = left * right
                else:
                    result = left / right
            except (ZeroDivisionError, OverflowError) as exc:
                raise _error("INVALID_PARAMETER", "Numeric expression divides by zero or overflows.", node) from exc
            _number(result)
            return result
        if isinstance(node, ast.Subscript):
            if isinstance(node.value, ast.Name):
                idx = self.expression(node.slice)
                if node.value.id in self.quantum_registers:
                    return _integer(idx, "Qubit index", 0, self.quantum_registers[node.value.id] - 1)
                if node.value.id in self.classical_registers:
                    return _integer(idx, "Classical bit index", 0, self.classical_registers[node.value.id] - 1)
                if node.value.id in self.values and isinstance(self.values[node.value.id], (list, tuple)):
                    return self.values[node.value.id][idx]
        if isinstance(node, ast.ListComp):
            if len(node.generators) == 1 and not node.generators[0].ifs and isinstance(node.generators[0].target, ast.Name):
                gen = node.generators[0]
                iterable = self.expression(gen.iter)
                if isinstance(iterable, (list, tuple, range)):
                    items = []
                    for val in iterable:
                        self.values[gen.target.id] = val
                        items.append(self.expression(node.elt))
                    return items
        if isinstance(node, ast.Call):
            gate_cls = self._resolve_gate_class(node.func)
            if gate_cls is not None:
                args = [self.expression(a) for a in node.args]
                try:
                    return gate_cls(*args)
                except Exception as exc:
                    raise _error("INVALID_ARGUMENTS", f"Gate initialization failed: {exc}", node) from exc
            if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
                module = self.modules.get(node.func.value.id)
                if module in ("math", "numpy") and node.func.attr in NUMERIC_MATH_NAMES and node.func.attr not in ("pi", "tau", "e"):
                    fn = getattr(math, node.func.attr if node.func.attr != "abs" else "fabs")
                    args = [self.expression(a) for a in node.args]
                    res = float(fn(*args))
                    _number(res)
                    return res
            if isinstance(node.func, ast.Name) and callable(self.values.get(node.func.id)):
                fn = self.values[node.func.id]
                args = [self.expression(a) for a in node.args]
                try:
                    res = float(fn(*args))
                except Exception as exc:
                    raise _error("INVALID_PARAMETER", f"Math function '{node.func.id}' evaluation failed: {exc}", node) from exc
                _number(res)
                return res
            if isinstance(node.func, ast.Name) and node.func.id == "range":
                if node.keywords or not 1 <= len(node.args) <= 3:
                    raise _error("UNSUPPORTED_SOURCE", "range expects one to three integer arguments.", node)
                values = [_integer(self.expression(value), "Range argument", -MAX_OPERATIONS, MAX_OPERATIONS) for value in node.args]
                if len(values) == 3 and values[2] == 0:
                    raise _error("INVALID_INPUT", "Range step cannot be zero.", node)
                result = range(*values)
                if len(result) > MAX_OPERATIONS:
                    raise _error("RESOURCE_LIMIT", "range is limited to 500 entries.", node)
                return result
        raise _error("UNSUPPORTED_SOURCE", f"Unsupported expression: {type(node).__name__}. Use numeric literals, pi, indices, or basic arithmetic.", node)

    def circuit_call(self, node: ast.Call) -> None:
        if not (isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id == self.circuit_name and self.circuit is not None):
            raise _error("UNSUPPORTED_SOURCE", "Only methods on the declared quantum circuit may be called.", node)
        method_name = node.func.attr
        name = ALIASES.get(method_name, method_name)
        if name in ("draw", "depth", "size", "width"):
            return
        if name == "append":
            if self.has_measurement:
                raise _error("NON_TERMINAL_MEASUREMENT", "Measurements must be terminal; no quantum gates may follow the first measurement.", node)
            if not 2 <= len(node.args) <= 3:
                raise _error("INVALID_ARGUMENTS", "append expects a gate and a list of target qubits (and optional clbits).", node)
            gate = self.expression(node.args[0])
            qargs_val = self.expression(node.args[1])
            qargs = [qargs_val] if isinstance(qargs_val, int) else list(qargs_val)
            for q in qargs:
                self.indices(q, self.circuit.num_qubits, "Qubit")
            if len(set(qargs)) != len(qargs):
                raise _error("INVALID_ARGUMENTS", "Duplicate qubits specified for appended gate.", node)
            cargs = None
            if len(node.args) == 3:
                cargs_val = self.expression(node.args[2])
                cargs = [cargs_val] if isinstance(cargs_val, int) else list(cargs_val) if cargs_val else []
                for c in cargs:
                    self.indices(c, self.circuit.num_clbits, "Classical bit")
            try:
                self.circuit.append(gate, qargs, cargs)
            except Exception as exc:
                raise _error("INVALID_ARGUMENTS", f"append failed: {exc}", node) from exc
            if len(self.circuit.data) > MAX_OPERATIONS:
                raise _error("RESOURCE_LIMIT", f"Circuit exceeds {MAX_OPERATIONS} operations, including measurements and barriers.", node)
            return
        if name == "mcx":
            if self.has_measurement:
                raise _error("NON_TERMINAL_MEASUREMENT", "Measurements must be terminal; no quantum gates may follow the first measurement.", node)
            args = [self.expression(a) for a in node.args]
            if len(args) == 2 and isinstance(args[0], (list, tuple, range)):
                ctrls = list(args[0])
                tgt = args[1]
            elif len(args) >= 2 and all(type(x) is int for x in args):
                ctrls = list(args[:-1])
                tgt = args[-1]
            else:
                raise _error("INVALID_ARGUMENTS", "mcx expects control qubits and a target qubit.", node)
            for q in ctrls + [tgt]:
                self.indices(q, self.circuit.num_qubits, "Qubit")
            if len(set(ctrls + [tgt])) != len(ctrls) + 1:
                raise _error("INVALID_ARGUMENTS", "Duplicate qubits in mcx operation.", node)
            try:
                self.circuit.append(SUPPORTED_GATE_CLASSES["MCXGate"](len(ctrls)), ctrls + [tgt])
            except Exception as exc:
                raise _error("INVALID_ARGUMENTS", f"mcx failed: {exc}", node) from exc
            if len(self.circuit.data) > MAX_OPERATIONS:
                raise _error("RESOURCE_LIMIT", f"Circuit exceeds {MAX_OPERATIONS} operations, including measurements and barriers.", node)
            return
        if name not in GATES and name not in ("measure", "measure_all", "barrier"):
            raise _error("UNSUPPORTED_GATE", f"Circuit operation '{name}' is not supported.", node)
        if node.keywords:
            raise _error("UNSUPPORTED_SOURCE", "Circuit method keyword arguments are not supported.", node)
        if self.has_measurement and name not in ("measure", "barrier"):
            raise _error("NON_TERMINAL_MEASUREMENT", "Measurements must be terminal; no quantum gates may follow the first measurement.", node)
        arguments = [self.expression(value) for value in node.args]
        # Preserve common Qiskit legacy spellings without executing deprecated APIs.
        if method_name == "u2" and len(arguments) == 3:
            arguments.insert(0, math.pi / 2)
        elif method_name == "cu3" and len(arguments) == 5:
            arguments.insert(3, 0.0)
        if name in GATES:
            parameter_count, qubit_count = GATES[name]
            # Handle single-qubit broadcasting: e.g. qc.h([0, 1]) or qc.h(range(n))
            if qubit_count == 1 and len(arguments) == parameter_count + 1 and isinstance(arguments[parameter_count], (list, tuple, range)):
                params = arguments[:parameter_count]
                for p_val in params:
                    _number(p_val)
                for q in arguments[parameter_count]:
                    self.indices(q, self.circuit.num_qubits, "Qubit")
                    getattr(self.circuit, name)(*params, q)
                return
            # Handle 2-qubit broadcasting: e.g. qc.cx(0, [1, 2])
            if qubit_count == 2 and len(arguments) == parameter_count + 2 and isinstance(arguments[parameter_count + 1], (list, tuple, range)) and not isinstance(arguments[parameter_count], (list, tuple, range)):
                params = arguments[:parameter_count]
                for p_val in params:
                    _number(p_val)
                ctrl = arguments[parameter_count]
                self.indices(ctrl, self.circuit.num_qubits, "Qubit")
                for tgt in arguments[parameter_count + 1]:
                    self.indices(tgt, self.circuit.num_qubits, "Qubit")
                    getattr(self.circuit, name)(*params, ctrl, tgt)
                return
            if len(arguments) != parameter_count + qubit_count:
                raise _error("INVALID_ARGUMENTS", f"{name} expects {parameter_count} parameter(s) and {qubit_count} qubit argument(s).", node)
            for value in arguments[:parameter_count]:
                _number(value)
            for value in arguments[parameter_count:]:
                self.indices(value, self.circuit.num_qubits, "Qubit")
        elif name == "measure":
            if len(arguments) != 2:
                raise _error("INVALID_ARGUMENTS", "measure expects qubit indices and classical bit indices.", node)
            # Handle measure broadcasting / register mapping: qc.measure(qr, cr) or qc.measure([0, 1], [0, 1])
            if isinstance(arguments[0], (list, tuple, range)) and isinstance(arguments[1], (list, tuple, range)):
                if len(arguments[0]) != len(arguments[1]):
                    raise _error("INVALID_ARGUMENTS", "Qubit list and classical bit list must have the same length in measure.", node)
                for q, c in zip(arguments[0], arguments[1]):
                    self.indices(q, self.circuit.num_qubits, "Qubit")
                    self.indices(c, self.circuit.num_clbits, "Classical bit")
                    self.circuit.measure(q, c)
                self.has_measurement = True
                return
            self.indices(arguments[0], self.circuit.num_qubits, "Qubit")
            self.indices(arguments[1], self.circuit.num_clbits, "Classical bit")
        elif name == "barrier":
            for value in arguments:
                self.indices(value, self.circuit.num_qubits, "Qubit")
        else:
            if arguments:
                raise _error("INVALID_ARGUMENTS", "Use measure_all() without arguments.", node)
            if self.circuit.num_clbits + self.circuit.num_qubits > MAX_CLBITS:
                raise _error("RESOURCE_LIMIT", "Qiskit measure_all() adds one classical bit per qubit and would exceed the 10-bit limit. Use explicit measure instead.", node)
        try:
            getattr(self.circuit, name)(*arguments)
        except Exception as exc:
            raise _error("INVALID_ARGUMENTS", f"{name}: {exc}", node) from exc
        if len(self.circuit.data) > MAX_OPERATIONS:
            raise _error("RESOURCE_LIMIT", f"Circuit exceeds {MAX_OPERATIONS} operations, including measurements and barriers.", node)
        if name in ("measure", "measure_all"):
            self.has_measurement = True

    @staticmethod
    def indices(value: Any, count: int, label: str) -> None:
        values = list(value) if isinstance(value, (list, tuple, range)) else [value]
        if not values:
            raise QuantumError("INVALID_ARGUMENTS", f"{label} lists cannot be empty.")
        for index in values:
            _integer(index, f"{label} index", 0, count - 1)


def _validate_ir(ir: dict[str, Any]) -> dict[str, Any]:
    """Validate and copy every field before constructing a framework circuit."""
    expected = {"version", "num_qubits", "num_clbits", "global_phase", "operations"}
    if not isinstance(ir, dict) or set(ir) != expected:
        raise QuantumError("INVALID_IR", "QORE-IR requires exactly version, num_qubits, num_clbits, global_phase, and operations.")
    if ir["version"] != IR_VERSION:
        raise QuantumError("INVALID_IR", f"Supported QORE-IR version is {IR_VERSION}.")
    n = _integer(ir["num_qubits"], "Qubit count", 1, MAX_QUBITS)
    m = _integer(ir["num_clbits"], "Classical bit count", 0, MAX_CLBITS)
    phase = _number(ir["global_phase"], "Global phase")
    operations = ir["operations"]
    if not isinstance(operations, list) or len(operations) > MAX_OPERATIONS:
        raise QuantumError("RESOURCE_LIMIT", "QORE-IR operations must be a list of at most 500 instructions.")
    normalized = []
    seen_measurement = False
    classical_writes: set[int] = set()
    for index, op in enumerate(operations):
        if not isinstance(op, dict) or set(op) != {"name", "qubits", "clbits", "params"}:
            raise QuantumError("INVALID_IR", f"Operation {index} requires exactly name, qubits, clbits, and params.")
        name = op["name"]
        if not isinstance(name, str) or (name not in GATES and name not in ("measure", "barrier", "mcx")):
            raise QuantumError("INVALID_IR", f"Operation {index} has an unsupported name.")
        if any(not isinstance(op[key], list) for key in ("qubits", "clbits", "params")):
            raise QuantumError("INVALID_IR", f"Operation {index} indices and parameters must be lists.")
        q = [_integer(value, "Qubit index", 0, n - 1) for value in op["qubits"]]
        c = [_integer(value, "Classical bit index", 0, m - 1) for value in op["clbits"]]
        p = [_number(value) for value in op["params"]]
        if len(set(q)) != len(q) or len(set(c)) != len(c):
            raise QuantumError("INVALID_IR", f"Operation {index} repeats an index within one instruction.")
        if name in GATES:
            parameter_count, qubit_count = GATES[name]
            if len(q) != qubit_count or len(p) != parameter_count or c:
                raise QuantumError("INVALID_IR", f"Operation {index} has invalid arity for {name}.")
            if seen_measurement:
                raise QuantumError("NON_TERMINAL_MEASUREMENT", "Measurements must be terminal; quantum gates cannot follow measurement.")
        elif name == "mcx":
            if len(p) != 0 or c or len(q) < 2:
                raise QuantumError("INVALID_IR", f"Operation {index} has invalid arity for mcx.")
            if seen_measurement:
                raise QuantumError("NON_TERMINAL_MEASUREMENT", "Measurements must be terminal; quantum gates cannot follow measurement.")
        elif name == "measure":
            if len(q) != 1 or len(c) != 1 or p:
                raise QuantumError("INVALID_IR", f"Operation {index} has invalid measurement arity.")
            if c[0] in classical_writes:
                raise QuantumError("INVALID_MEASUREMENT_MAPPING", f"Classical bit {c[0]} is written more than once; this subset requires unique classical destinations.")
            classical_writes.add(c[0])
            seen_measurement = True
        elif not q or c or p:
            raise QuantumError("INVALID_IR", f"Operation {index} has invalid barrier arguments.")
        normalized.append({"name": name, "qubits": q, "clbits": c, "params": p})
    return {"version": IR_VERSION, "num_qubits": n, "num_clbits": m, "global_phase": phase, "operations": normalized}


def circuit_to_ir(circuit: QuantumCircuit) -> dict[str, Any]:
    operations = []
    for instruction in circuit.data:
        operations.append({
            "name": instruction.operation.name,
            "qubits": [circuit.find_bit(bit).index for bit in instruction.qubits],
            "clbits": [circuit.find_bit(bit).index for bit in instruction.clbits],
            "params": [float(value) for value in instruction.operation.params],
        })
    return _validate_ir({
        "version": IR_VERSION,
        "num_qubits": circuit.num_qubits,
        "num_clbits": circuit.num_clbits,
        "global_phase": float(circuit.global_phase),
        "operations": operations,
    })


def ir_to_circuit(ir: dict[str, Any], *, unitary_only: bool = False) -> QuantumCircuit:
    normalized = _validate_ir(ir)
    circuit = QuantumCircuit(normalized["num_qubits"], 0 if unitary_only else normalized["num_clbits"])
    circuit.global_phase = normalized["global_phase"]
    for op in normalized["operations"]:
        name, q, c, p = op["name"], op["qubits"], op["clbits"], op["params"]
        if name in ("measure", "barrier") and unitary_only:
            continue
        if name == "measure":
            circuit.measure(q[0], c[0])
        elif name == "barrier":
            circuit.barrier(*q)
        elif name == "mcx":
            circuit.append(SUPPORTED_GATE_CLASSES["MCXGate"](len(q) - 1), q)
        else:
            getattr(circuit, name)(*p, *q)
    return circuit


def _metrics(circuit: QuantumCircuit, ir: dict[str, Any]) -> dict[str, Any]:
    gates = [op for op in ir["operations"] if op["name"] not in ("measure", "barrier")]
    return {
        "qubits": circuit.num_qubits,
        "clbits": circuit.num_clbits,
        "gate_count": len(gates),
        "depth": circuit.depth(),
        "two_qubit_gate_count": sum(len(op["qubits"]) == 2 for op in gates),
        "measurement_count": sum(op["name"] == "measure" for op in ir["operations"]),
        "barrier_count": sum(op["name"] == "barrier" for op in ir["operations"]),
        "gate_types": dict(sorted(Counter(op["name"] for op in gates).items())),
        "definition": METRIC_DEFINITION,
    }


def _round_real(value: float, digits: int = DISPLAY_DIGITS) -> float:
    return round(float(value), digits)


def _complex_cell(value: complex) -> dict[str, float]:
    return {
        "real": _round_real(float(np.real(value))),
        "imag": _round_real(float(np.imag(value))),
        "magnitude": _round_real(float(np.abs(value))),
        "phase": _round_real(float(np.angle(value))),
    }


def _bloch_from_reduced(rho: DensityMatrix, qubit: int) -> dict[str, Any]:
    data = np.asarray(rho.data, dtype=complex)
    x = float(np.real(np.trace(data @ PAULI_X)))
    y = float(np.real(np.trace(data @ PAULI_Y)))
    z = float(np.real(np.trace(data @ PAULI_Z)))
    r = float(np.sqrt(max(0.0, x * x + y * y + z * z)))
    theta = float(np.arccos(np.clip(z / r, -1.0, 1.0))) if r > 1e-12 else 0.0
    phi = float(np.arctan2(y, x))
    purity = float(np.clip(np.real(np.trace(data @ data)), 0.0, 1.0))
    return {
        "qubit": qubit,
        "x": _round_real(x),
        "y": _round_real(y),
        "z": _round_real(z),
        "r": _round_real(r),
        "purity": _round_real(purity),
        "is_pure": bool(abs(purity - 1.0) < 1e-8),
        "theta": _round_real(theta),
        "phi": _round_real(phi),
    }


def _unitarity_report(operator: np.ndarray) -> dict[str, Any]:
    dim = operator.shape[0]
    gram = operator.conj().T @ operator
    residual = float(np.max(np.abs(gram - np.eye(dim, dtype=complex))))
    frobenius = float(np.linalg.norm(gram - np.eye(dim, dtype=complex)))
    determinant_magnitude = float(abs(np.linalg.det(operator)))
    return {
        "is_unitary": bool(residual <= UNITARITY_TOLERANCE),
        "max_deviation": residual,
        "frobenius_deviation": frobenius,
        "determinant_magnitude": determinant_magnitude,
        "tolerance": UNITARITY_TOLERANCE,
        "dimension": dim,
        "definition": "max |U†U − I| over matrix entries. A closed pre-measurement circuit must satisfy U†U = I within numerical tolerance.",
    }


def compute_circuit_bloch_and_unitary(circuit: QuantumCircuit, ir: dict[str, Any]) -> dict[str, Any]:
    n = circuit.num_qubits
    bloch_vectors: list[dict[str, Any]] = []
    unitary_matrix: list[list[dict[str, float]]] = []
    statevector_amplitudes: list[dict[str, Any]] = []
    unitarity: dict[str, Any] | None = None
    analysis_warnings: list[str] = []
    qasm_str = ""
    try:
        qasm_str = qasm2.dumps(circuit)
    except Exception as exc:
        analysis_warnings.append(f"OpenQASM export was unavailable: {exc}")

    try:
        u_circ = ir_to_circuit(ir, unitary_only=True)
        if n <= 6:
            state = Statevector.from_instruction(u_circ)
            state_norm = float(np.linalg.norm(state.data))
            if abs(state_norm - 1.0) > 1e-8:
                analysis_warnings.append(f"Statevector norm is {state_norm:.12f}; expected 1 within 1e-8.")
            for q in range(n):
                other = [i for i in range(n) if i != q]
                rho = partial_trace(state, other) if other else DensityMatrix(state)
                bloch_vectors.append(_bloch_from_reduced(rho, q))
            for idx, amp in enumerate(state.data):
                mag = float(np.abs(amp))
                prob = float(np.real(amp * np.conjugate(amp)))
                statevector_amplitudes.append({
                    "state": format(idx, f"0{n}b"),
                    "real": _round_real(float(np.real(amp))),
                    "imag": _round_real(float(np.imag(amp))),
                    "magnitude": _round_real(mag),
                    "phase": _round_real(float(np.angle(amp))),
                    "probability": _round_real(prob),
                })
            amplitude_sum = sum(item["probability"] for item in statevector_amplitudes)
            if abs(amplitude_sum - 1.0) > 5e-7:
                analysis_warnings.append(
                    f"Displayed amplitude probabilities sum to {amplitude_sum:.12f} after rounding; the underlying statevector is still used for simulation."
                )
        if n <= MAX_EQUIVALENCE_QUBITS:
            u_data = np.asarray(Operator(u_circ).data, dtype=complex)
            unitarity = _unitarity_report(u_data)
            if n <= 4:
                unitary_matrix = [[_complex_cell(c) for c in row] for row in u_data]
            if not unitarity["is_unitary"]:
                analysis_warnings.append(
                    f"Operator failed the unitarity residual check (max |U†U − I| = {unitarity['max_deviation']:.3e})."
                )
    except Exception as exc:
        analysis_warnings.append(f"Ideal state analysis could not be completed: {exc}")

    text_diagram = ""
    try:
        text_diagram = str(circuit.draw("text"))
    except Exception as exc:
        analysis_warnings.append(f"Text circuit diagram was unavailable: {exc}")

    return {
        "qasm": qasm_str,
        "text_diagram": text_diagram,
        "bloch_vectors": bloch_vectors,
        "statevector_amplitudes": statevector_amplitudes,
        "unitary_matrix": unitary_matrix,
        "unitarity": unitarity,
        "analysis_warnings": analysis_warnings,
    }


def parse_source(source: str) -> dict[str, Any]:
    if not isinstance(source, str):
        raise QuantumError("INVALID_SOURCE", "Source must be text.")
    try:
        encoded = source.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise QuantumError("INVALID_SOURCE", "Source must contain valid UTF-8 text.") from exc
    if len(encoded) > MAX_SOURCE_BYTES:
        raise QuantumError("RESOURCE_LIMIT", f"Source exceeds {MAX_SOURCE_BYTES} UTF-8 bytes.")
    stripped = source.strip()
    if stripped.startswith("OPENQASM") or (stripped.startswith("include ") and ("qreg " in stripped or "qubit" in stripped)):
        try:
            circuit = qasm2.loads(source)
        except Exception as exc:
            raise QuantumError("SYNTAX_ERROR", f"OpenQASM parser error: {exc}") from exc
    else:
        circuit = _SourceInterpreter().run(source)
    ir = circuit_to_ir(circuit)
    metrics = _metrics(circuit, ir)
    # Pure unitary circuits are valid inputs. The simulation path adds an
    # identity q[i] -> c[i] measurement map at execution time without changing
    # the saved source or the ideal-state evidence returned by parsing.
    extra = compute_circuit_bloch_and_unitary(circuit, ir)
    extra_warnings = extra.pop("analysis_warnings", [])
    return {
        "ir": ir,
        "metrics": metrics,
        "source_hash": hashlib.sha256(encoded).hexdigest(),
        "warnings": extra_warnings,
        **extra,
    }


def _measurement_mapping(ir: dict[str, Any]) -> list[tuple[int, int]]:
    return sorted((op["qubits"][0], op["clbits"][0]) for op in ir["operations"] if op["name"] == "measure")


def simulate(
    source: str,
    shots: int = 1024,
    seed: int = 42,
    noise_rate: float = 0.0,
    readout_error: float = 0.0,
    method: str = "statevector",
) -> dict[str, Any]:
    started = time.perf_counter()
    shots = _integer(shots, "Shots", 1, MAX_SHOTS)
    seed = _integer(seed, "Seed", 0, 2**32 - 1)
    noise_rate = _bounded_probability(noise_rate, "Noise rate")
    readout_error = _bounded_probability(readout_error, "Readout error")
    if method not in ("statevector", "matrix_product_state", "stabilizer"):
        raise QuantumError(
            "INVALID_INPUT",
            "Simulation method must be statevector, matrix_product_state, or stabilizer.",
        )
    parsed = parse_source(source)
    ir = parsed["ir"]
    mapping = _measurement_mapping(ir)
    auto_measured = False
    if not mapping:
        auto_measured = True
        import json
        auto_ir = json.loads(json.dumps(ir))
        n_q = auto_ir["num_qubits"]
        auto_ir["num_clbits"] = n_q
        for q_idx in range(n_q):
            auto_ir["operations"].append({"name": "measure", "qubits": [q_idx], "clbits": [q_idx], "params": []})
        ir = auto_ir
        mapping = [(q_idx, q_idx) for q_idx in range(n_q)]
    circuit = ir_to_circuit(ir)
    try:
        noise = None
        if noise_rate > 0.0 or readout_error > 0.0:
            noise = NoiseModel()
            if noise_rate > 0.0:
                present = {op["name"] for op in ir["operations"] if op["name"] not in ("measure", "barrier")}
                one = [name for name in ONE_QUBIT_NOISE_GATES if name in present]
                two = [name for name in TWO_QUBIT_NOISE_GATES if name in present]
                three = [name for name in THREE_QUBIT_NOISE_GATES if name in present]
                if one:
                    noise.add_all_qubit_quantum_error(depolarizing_error(min(0.5, noise_rate), 1), one)
                if two:
                    noise.add_all_qubit_quantum_error(depolarizing_error(min(0.5, noise_rate * 2), 2), two)
                if three:
                    noise.add_all_qubit_quantum_error(depolarizing_error(min(0.5, noise_rate * 3), 3), three)
            if readout_error > 0.0:
                from qiskit_aer.noise import ReadoutError
                p = min(0.49, readout_error)
                ro = ReadoutError([[1.0 - p, p], [p, 1.0 - p]])
                noise.add_all_qubit_readout_error(ro)

        chosen_method = method
        if noise is not None:
            simulator = AerSimulator(method=chosen_method, noise_model=noise, max_parallel_threads=1)
            backend_label = f"qiskit_aer.AerSimulator({chosen_method}, noise={noise_rate:.3f}, ro={readout_error:.3f})"
        else:
            simulator = AerSimulator(method=chosen_method, max_parallel_threads=1)
            backend_label = f"qiskit_aer.AerSimulator({chosen_method})"
        executable = transpile(circuit, simulator, optimization_level=0, seed_transpiler=seed)
        result = simulator.run(executable, shots=shots, seed_simulator=seed).result()
        if not result.success:
            raise QuantumError("SIMULATION_FAILED", str(result.status))
        raw_counts = result.get_counts()
        width = ir["num_clbits"]
        counts = {key.replace(" ", "").zfill(width): int(value) for key, value in sorted(raw_counts.items())}
        if sum(counts.values()) != shots:
            raise QuantumError("SIMULATION_FAILED", "Simulator returned an unexpected total shot count.")
        outcomes = [format(value, f"0{width}b") for value in range(2**width)]
        empirical = {key: counts.get(key, 0) / shots for key in outcomes}
        state = Statevector.from_instruction(ir_to_circuit(ir, unitary_only=True))
        theoretical = {key: 0.0 for key in outcomes}
        for basis, probability in enumerate(state.probabilities()):
            output = sum(((basis >> qubit) & 1) << clbit for qubit, clbit in mapping)
            theoretical[format(output, f"0{width}b")] += float(probability)
        total = sum(theoretical.values())
        if total <= 0.0 or not math.isfinite(total):
            raise QuantumError("SIMULATION_FAILED", "Ideal statevector probabilities were not a valid probability distribution.")
        theoretical = {key: value / total for key, value in theoretical.items()}
        tvd = 0.5 * sum(abs(empirical[key] - theoretical[key]) for key in outcomes)
        overlap = sum(math.sqrt(max(0.0, empirical[key]) * max(0.0, theoretical[key])) for key in outcomes)
        overlap = min(1.0, max(0.0, overlap))
        classical_fidelity = overlap ** 2
        hellinger_distance = math.sqrt(max(0.0, 1.0 - overlap))
    except QuantumError:
        raise
    except Exception as exc:
        raise QuantumError("SIMULATION_FAILED", f"Qiskit Aer could not simulate the circuit: {exc}") from exc
    mapping_text = ", ".join(f"q[{q}] → c[{c}]" for q, c in mapping)
    sim_warnings = list(parsed.get("warnings", []))
    if auto_measured:
        sim_warnings.append(
            "Source contained no measurements. QORE appended q[i] → c[i] for sampling only; Bloch vectors, amplitudes, and the unitary remain the pre-measurement ideal state."
        )
    return {
        **parsed,
        "warnings": sim_warnings,
        "counts": counts,
        "probabilities": empirical,
        "theoretical_probabilities": theoretical,
        "tvd": float(tvd),
        "tvd_definition": "Total variation distance between these finite-shot empirical probabilities and the ideal statevector probabilities under the same classical measurement mapping.",
        "classical_fidelity": float(classical_fidelity),
        "classical_fidelity_definition": "Bhattacharyya coefficient squared between the sampled distribution and the ideal mapped probabilities. 1 is a perfect match.",
        "hellinger_distance": float(hellinger_distance),
        "hellinger_definition": "Hellinger distance √(1 − ∑√(p q)) between sampled and ideal mapped probabilities. 0 is a perfect match.",
        "auto_measured": auto_measured,
        "shots": shots,
        "seed": seed,
        "noise_rate": noise_rate,
        "readout_error": readout_error,
        "noise_applied": noise_rate > 0.0 or readout_error > 0.0,
        "simulation_method": chosen_method,
        "backend": backend_label,
        "versions": versions(),
        "execution_ms": round((time.perf_counter() - started) * 1000, 3),
        "bit_ordering": f"Bitstrings read c[{width - 1}]…c[0] from left to right (Qiskit little-endian classical indices). Mapping: {mapping_text}. Unmeasured classical bits are 0.",
    }


def validate_ir(original: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    method = "Full unitary operator comparison up to global phase, with exact terminal measurement mapping"
    try:
        left, right = _validate_ir(original), _validate_ir(candidate)
    except QuantumError as exc:
        return {"status": "unavailable", "method": method, "details": f"Unsupported or invalid QORE-IR: {exc.message}", "error_code": exc.code}
    left_mapping, right_mapping = _measurement_mapping(left), _measurement_mapping(right)
    evidence = {"original_measurement_mapping": left_mapping, "candidate_measurement_mapping": right_mapping}
    if left["num_qubits"] != right["num_qubits"] or left["num_clbits"] != right["num_clbits"]:
        return {"status": "failed", "method": method, "details": "Quantum or classical register sizes differ.", **evidence}
    if left_mapping != right_mapping:
        return {"status": "failed", "method": method, "details": "Terminal qubit-to-classical-bit mappings differ.", **evidence}
    n = left["num_qubits"]
    if n > MAX_EQUIVALENCE_QUBITS:
        return {"status": "unavailable", "method": method, "details": f"Full operator validation is capped at {MAX_EQUIVALENCE_QUBITS} qubits; this circuit has {n}. Successful compilation is not an equivalence proof.", **evidence}
    try:
        u = Operator(ir_to_circuit(left, unitary_only=True)).data
        v = Operator(ir_to_circuit(right, unitary_only=True)).data
        overlap = np.vdot(u, v) / (2**n)
        phase = overlap / abs(overlap) if abs(overlap) > 1e-15 else 1.0 + 0.0j
        max_error = float(np.max(np.abs(v - phase * u)))
        equivalent = max_error <= EQUIVALENCE_TOLERANCE
        return {
            "status": "validated" if equivalent else "failed",
            "method": method,
            "details": ("Every computational basis input has the same unitary action up to one global phase, within numerical tolerance; terminal measurement destinations match." if equivalent else "The full circuit operators differ beyond numerical tolerance after aligning a global phase."),
            "qubits": n,
            "operator_dimension": 2**n,
            "max_absolute_error": max_error,
            "tolerance": EQUIVALENCE_TOLERANCE,
            "process_fidelity": float(min(1.0, abs(overlap) ** 2)),
            "global_phase_difference": float(np.angle(phase)),
            **evidence,
        }
    except Exception as exc:
        return {"status": "inconclusive", "method": method, "details": f"Numerical operator comparison could not complete: {exc}", **evidence}


def ir_to_source(ir: dict[str, Any]) -> str:
    ir = _validate_ir(ir)
    lines = ["from qiskit import QuantumCircuit", "", f"qc = QuantumCircuit({ir['num_qubits']}, {ir['num_clbits']})"]
    if ir["global_phase"]:
        lines.append(f"qc.global_phase = {ir['global_phase']!r}")
    for op in ir["operations"]:
        if op["name"] == "mcx":
            lines.append(f"qc.mcx({op['qubits'][:-1]!r}, {op['qubits'][-1]})")
        else:
            values = [repr(value) for value in op["params"]] + [str(value) for value in op["qubits"]] + [str(value) for value in op["clbits"]]
            lines.append(f"qc.{op['name']}({', '.join(values)})")
    return "\n".join(lines) + "\n"


def optimize(source: str, level: int = 2, seed: int = 42) -> dict[str, Any]:
    level = _integer(level, "Optimization level", 0, 3)
    seed = _integer(seed, "Seed", 0, 2**32 - 1)
    parsed = parse_source(source)
    original_ir = parsed["ir"]
    # Optimize only the unitary prefix. Qiskit's measurement-aware passes may
    # legitimately drop terminal diagonal gates; that preserves the measured
    # distribution but not our stronger full-operator equivalence property.
    boundary = next((index for index, op in enumerate(original_ir["operations"]) if op["name"] == "measure"), len(original_ir["operations"]))
    prefix_ir = {**original_ir, "operations": original_ir["operations"][:boundary]}
    original_circuit = ir_to_circuit(prefix_ir)
    basis = ["u", "cx"]
    try:
        candidate_circuit = transpile(original_circuit, basis_gates=basis, optimization_level=level, seed_transpiler=seed)
        if candidate_circuit.layout and candidate_circuit.layout.final_layout:
            final_indices = candidate_circuit.layout.final_index_layout()
            if final_indices and final_indices != list(range(len(final_indices))):
                from qiskit.circuit.library import PermutationGate
                perm = [final_indices.index(i) for i in range(len(final_indices))]
                perm_circ = QuantumCircuit(len(final_indices))
                perm_circ.append(PermutationGate(perm), range(len(final_indices)))
                for inst in perm_circ.decompose().data:
                    candidate_circuit.append(inst.operation, [candidate_circuit.qubits[perm_circ.find_bit(q).index] for q in inst.qubits])
        for op in original_ir["operations"][boundary:]:
            if op["name"] == "measure":
                candidate_circuit.measure(op["qubits"][0], op["clbits"][0])
            else:
                candidate_circuit.barrier(*op["qubits"])
        candidate_ir = circuit_to_ir(candidate_circuit)
    except QuantumError:
        raise
    except Exception as exc:
        raise QuantumError("OPTIMIZATION_FAILED", f"Qiskit's compiler could not create a supported candidate: {exc}") from exc
    candidate_metrics = _metrics(candidate_circuit, candidate_ir)
    differences = {}
    for metric in ("gate_count", "depth", "two_qubit_gate_count", "qubits", "clbits", "measurement_count", "barrier_count"):
        before, after = parsed["metrics"][metric], candidate_metrics[metric]
        differences[metric] = {"original": before, "candidate": after, "absolute": after - before, "relative_percent": 100 * (after - before) / before if before else None}
    validation = validate_ir(original_ir, candidate_ir)
    before, after = parsed["metrics"]["gate_count"], candidate_metrics["gate_count"]
    change = f"Gate count changed from {before} to {after}; depth changed from {parsed['metrics']['depth']} to {candidate_metrics['depth']}."
    if after >= before:
        change += " This candidate does not reduce gate count."
    explanation = (
        f"Qiskit's standard compiler preset at optimization level {level} produced this separate candidate in the u/cx basis. "
        "Only the unitary prefix is compiled; the terminal measurement/barrier suffix is preserved to support full-operator validation. "
        "The preset may combine one-qubit gates, cancel redundant operations, and synthesize gate blocks. "
        "These are framework-provided transformations. No hardware coupling map or noise model is applied. "
        f"{change} Counts compare instructions in each displayed circuit; basis decomposition can increase counts, and these metrics are not hardware latency or fidelity measurements."
    )
    return {
        "source_hash": parsed["source_hash"],
        "original": {"ir": original_ir, "metrics": parsed["metrics"]},
        "candidate": {"ir": candidate_ir, "metrics": candidate_metrics, "source": ir_to_source(candidate_ir)},
        "settings": {"compiler": "qiskit.transpile", "pass_manager": "Qiskit standard preset pass manager", "optimization_level": level, "seed_transpiler": seed, "basis_gates": basis, "coupling_map": None, "measurement_policy": "Compile the unitary prefix and preserve the terminal measurement/barrier suffix unchanged."},
        "differences": differences,
        "validation": validation,
        "explanation": explanation,
        "versions": versions(),
        "warnings": parsed["warnings"] + (["Equivalence validation is unavailable for circuits above six qubits; inspect the candidate before approval."] if validation["status"] == "unavailable" else []),
    }
