"""The bounded QORE quantum processing layer.

User Python is parsed as syntax and interpreted by a small allowlist. It is never
passed to Python's exec/eval, imported, or given access to Python objects.
"""

from __future__ import annotations

import ast
import hashlib
import importlib.metadata
import inspect
import math
import platform
import re
import time
from collections import Counter
from functools import lru_cache
from typing import Any

import numpy as np
from qiskit import QuantumCircuit, transpile, qasm2
from qiskit.circuit import Gate, Instruction, Parameter, ParameterExpression, ParameterVector
from qiskit.quantum_info import DensityMatrix, Operator, Statevector, partial_trace
from qiskit_aer import AerSimulator
from qiskit_aer.noise import NoiseModel, depolarizing_error
import qiskit.circuit.library as qiskit_gate_lib
from .qiskit_support import BoundedQiskit, CIRCUIT_FACTORIES, DATA_GATES, OBJECT_METHODS, OPERATOR_TYPES, PARAMETER_TYPES


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
    "U1Gate": qiskit_gate_lib.U1Gate,
    "U2Gate": qiskit_gate_lib.U2Gate,
    "U3Gate": qiskit_gate_lib.U3Gate,
    "RVGate": qiskit_gate_lib.RVGate,
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
    "CU1Gate": qiskit_gate_lib.CU1Gate,
    "CU3Gate": qiskit_gate_lib.CU3Gate,
    # 3-qubit unitary gates
    "CCXGate": qiskit_gate_lib.CCXGate,
    "CCZGate": qiskit_gate_lib.CCZGate,
    "RCCXGate": qiskit_gate_lib.RCCXGate,
    "CSwapGate": qiskit_gate_lib.CSwapGate,
    # Multi-qubit controlled gates
    "MCXGate": qiskit_gate_lib.MCXGate,
    "MCXGrayCode": qiskit_gate_lib.MCXGrayCode,
    "MCXRecursive": qiskit_gate_lib.MCXRecursive,
    "MCXVChain": qiskit_gate_lib.MCXVChain,
    "MCMTGate": qiskit_gate_lib.MCMTGate,
    # Boolean logic & arithmetic gates
    "AndGate": qiskit_gate_lib.AndGate,
    "OrGate": qiskit_gate_lib.OrGate,
    "BitwiseXorGate": qiskit_gate_lib.BitwiseXorGate,
    "FullAdderGate": qiskit_gate_lib.FullAdderGate,
    "HalfAdderGate": qiskit_gate_lib.HalfAdderGate,
    # Composite unitary gates are lowered to the bounded u/cx representation.
    "IGate": qiskit_gate_lib.IGate,
    "C3XGate": qiskit_gate_lib.C3XGate,
    "C3SXGate": qiskit_gate_lib.C3SXGate,
    "C4XGate": qiskit_gate_lib.C4XGate,
    "RC3XGate": qiskit_gate_lib.RC3XGate,
    "MCPhaseGate": qiskit_gate_lib.MCPhaseGate,
    "MCU1Gate": qiskit_gate_lib.MCU1Gate,
    "GlobalPhaseGate": qiskit_gate_lib.GlobalPhaseGate,
    "QFTGate": qiskit_gate_lib.QFTGate,
    "XXMinusYYGate": qiskit_gate_lib.XXMinusYYGate,
    "XXPlusYYGate": qiskit_gate_lib.XXPlusYYGate,
}
SUPPORTED_GATE_CLASSES.update(DATA_GATES)
SOURCE_MODULES = {"qiskit", "qiskit.circuit", "qiskit.circuit.library", "qiskit.quantum_info", "math", "numpy"}

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
    "and excluding barriers. Native three-qubit gates count as one gate. Composite "
    "library gates and open controls are lowered to u/cx before these metrics."
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


@lru_cache(maxsize=1)
def _installed_qiskit_packages() -> tuple[tuple[str, str], ...]:
    return tuple(sorted(
        (package.metadata["Name"], package.version)
        for package in importlib.metadata.distributions()
        if (package.metadata.get("Name") or "").lower().replace("_", "-").startswith("qiskit")
    ))


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
            "qiskit.circuit": "QuantumCircuit, QuantumRegister, ClassicalRegister, Parameter, ParameterVector; library namespace",
            "qiskit.quantum_info": "Pauli(label), SparsePauliOp.from_list for bounded evolution operators",
            "qiskit.circuit.library": "listed unitary gate constructors with validated keywords and circuit.append; composite gates and open controls lower to u/cx",
            "qiskit_aer": "AerSimulator through QORE simulation settings",
            "math": "bounded numeric constants and functions",
            "numpy": "bounded numeric constants/functions and literal arrays of at most 500 entries; no I/O or arbitrary runtime access",
        },
        "gates": {
            name: {"parameters": parameter_count, "qubits": qubit_count}
            for name, (parameter_count, qubit_count) in sorted(GATES.items())
        },
        "gate_classes": sorted(SUPPORTED_GATE_CLASSES),
        "circuit_factories": sorted(CIRCUIT_FACTORIES),
        "parameter_constructors": sorted(PARAMETER_TYPES),
        "object_methods": sorted(OBJECT_METHODS),
        "circuit_selection": "Use qc when declared; otherwise use the first constructed circuit. Other named circuits are reusable fragments.",
        "circuit_methods": ["append", "mcx", "barrier", "measure", "measure_all", "draw", "depth", "size", "width", "compose", "assign_parameters", "inverse", "control", "power", "to_gate", "copy"],
        "installed_packages": dict(_installed_qiskit_packages()),
        "package_execution": {
            "qiskit": "Only the reported circuit-building subset, not arbitrary SDK Python.",
            "qiskit-aer": "Simulation through QORE settings, not direct source imports.",
            "optional_packages": "Installation does not enable editor execution of providers, primitives, algorithms, add-ons, or OpenQASM 3.",
        },
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
            "max_array_elements": MAX_OPERATIONS, "max_factory_reps": 20, "matrix_power_max_qubits": 4,
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
            "complex": "complex",
            "float": "float",
        }
        self.constructors: set[str] = set()
        self.qreg_constructors: set[str] = set()
        self.creg_constructors: set[str] = set()
        self.gate_constructors: dict[str, type] = {}
        self.library_factories: dict[str, Any] = {}
        self.parameter_constructors: dict[str, str] = {}
        self.operator_constructors: dict[str, str] = {}
        self.array_constructors: set[str] = set()
        self.support = BoundedQiskit(MAX_QUBITS, MAX_OPERATIONS, MAX_ABSOLUTE_NUMBER, GATES)
        self.quantum_registers: dict[str, int] = {}
        self.classical_registers: dict[str, int] = {}
        self.modules: dict[str, str] = {}
        self.constants: set[str] = {"complex", "float"}
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
        if self.circuit.parameters:
            # If the initial circuit had parameters but a subsequent assigned/bound circuit was created,
            # select the most recent bound circuit as the primary circuit.
            for name, val in reversed(list(self.values.items())):
                if isinstance(val, QuantumCircuit) and not val.parameters:
                    self.circuit = val
                    self.circuit_name = name
                    break
        if self.circuit.parameters:
            raise QuantumError("UNBOUND_PARAMETERS", "Bind all active-circuit parameters with assign_parameters before parsing, simulation, or compilation.",
                               {"parameters": [str(p) for p in self.circuit.parameters]})
        return self.circuit

    def bindable(self, name: str, node: ast.AST) -> None:
        if (name == "range" or name in self.modules or name in self.constructors
                or name in self.qreg_constructors or name in self.creg_constructors
                or name in self.gate_constructors or name in self.quantum_registers
                or name in self.library_factories or name in self.parameter_constructors
                or name in self.operator_constructors or name in self.array_constructors
                or name in self.classical_registers or name in self.constants
                or name == self.circuit_name):
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
            self.bindable(target, node)
            if target not in self.values:
                raise _error("UNSUPPORTED_SOURCE", "Augmented assignment requires an existing numeric variable.", node)
            self.values[target] = self.expression(ast.BinOp(
                left=ast.Name(id=target, ctx=ast.Load()), op=node.op, right=node.value,
            ))
            return
        if isinstance(node, ast.Assign):
            if len(node.targets) != 1:
                raise _error("UNSUPPORTED_SOURCE", "Use one simple assignment target.", node)
            target = node.targets[0]
            if isinstance(target, ast.Attribute):
                owner = self.named_circuit(target.value)
                if owner is None or target.attr != "global_phase":
                    raise _error("UNSUPPORTED_SOURCE", "Only qc.global_phase may be assigned as an attribute.", node)
                owner.global_phase = self.support.angle(self.expression(node.value))
                return
            if not isinstance(target, ast.Name):
                raise _error("UNSUPPORTED_SOURCE", "Assignment targets must be variable names.", node)
            if target.id != self.circuit_name:
                self.bindable(target.id, node)
            if isinstance(node.value, ast.Call):
                if isinstance(node.value.func, ast.Attribute) and node.value.func.attr == "from_qasm_str":
                    if not self.is_constructor(node.value.func.value):
                        raise _error("UNSUPPORTED_SOURCE", "Use the imported QuantumCircuit.from_qasm_str constructor.", node)
                    if len(node.value.args) != 1 or node.value.keywords:
                        raise _error("INVALID_ARGUMENTS", "from_qasm_str expects one OpenQASM string.", node)
                    qasm_str = self.expression(node.value.args[0])
                    if not isinstance(qasm_str, str):
                        raise _error("INVALID_ARGUMENTS", "from_qasm_str expects an OpenQASM string.", node)
                    self.store_circuit(target.id, _load_qasm(qasm_str))
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
                    self.store_circuit(target.id, self.new_circuit(node.value))
                    return
            value = self.expression(node.value)
            if isinstance(value, QuantumCircuit):
                self.store_circuit(target.id, value)
            elif target.id == self.circuit_name:
                raise _error("UNSUPPORTED_SOURCE", "The active circuit name must remain a quantum circuit.", node)
            else:
                self.values[target.id] = value
            return
        if isinstance(node, ast.Expr):
            if isinstance(node.value, ast.Constant):
                return  # Python-style documentation strings or constants
            if isinstance(node.value, ast.Call):
                func = node.value.func
                # Safely ignore print(...) calls
                if isinstance(func, ast.Name) and func.id == "print":
                    return
                # Safely ignore inspection calls (e.g. qc.draw(), bound_circuit.decompose().draw('mpl'))
                if isinstance(func, ast.Attribute) and func.attr in ("draw", "depth", "size", "width"):
                    target = self.expression(func.value)
                    if not isinstance(target, QuantumCircuit):
                        raise _error("UNSUPPORTED_SOURCE", "Inspection methods are only supported on quantum circuits.", node)
                    return
                if isinstance(func, ast.Attribute) and func.attr in OBJECT_METHODS:
                    self.expression(node.value)
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

    def named_circuit(self, node: ast.AST) -> QuantumCircuit | None:
        if not isinstance(node, ast.Name):
            return None
        value = self.circuit if node.id == self.circuit_name else self.values.get(node.id)
        return value if isinstance(value, QuantumCircuit) else None

    def store_circuit(self, name: str, circuit: QuantumCircuit) -> None:
        self.support.circuit(circuit)
        if self.circuit is None or name == self.circuit_name or name == "qc":
            if self.circuit_name is not None and name != self.circuit_name:
                self.values[self.circuit_name] = self.circuit
            self.circuit, self.circuit_name = circuit, name
            self.values.pop(name, None)
        else:
            self.values[name] = circuit

    def new_circuit(self, node: ast.Call) -> QuantumCircuit:
        kwargs = self.keywords(node)
        if not 1 <= len(node.args) <= 2 or set(kwargs) - {"name", "global_phase"}:
            raise _error("INVALID_ARGUMENTS", "Use QuantumCircuit(qubits) or QuantumCircuit(qubits, classical_bits), with optional name and global_phase.", node)
        arg0 = node.args[0]
        n = self.quantum_registers.get(arg0.id) if isinstance(arg0, ast.Name) else None
        if n is None:
            n = _integer(self.expression(arg0), "Qubit count", 1, MAX_QUBITS)
        m = 0
        if len(node.args) == 2:
            arg1 = node.args[1]
            m = self.classical_registers.get(arg1.id) if isinstance(arg1, ast.Name) else None
            if m is None:
                m = _integer(self.expression(arg1), "Classical bit count", 0, MAX_CLBITS)
        if kwargs.get("name") is not None:
            self.support.text(kwargs["name"], 64)
        if "global_phase" in kwargs:
            kwargs["global_phase"] = self.support.angle(kwargs["global_phase"])
        return QuantumCircuit(n, m, **kwargs)

    def import_statement(self, node: ast.Import | ast.ImportFrom) -> None:
        if isinstance(node, ast.Import):
            for item in node.names:
                if item.name not in SOURCE_MODULES:
                    raise _error("UNSUPPORTED_IMPORT", f"Import '{item.name}' is not supported; no user imports are executed.", node)
                alias = item.asname or item.name.split(".")[0]
                self.bindable(alias, node)
                self.values.pop(alias, None)
                self.modules[alias] = item.name if item.asname else item.name.split(".")[0]
            return
        if node.level or node.module not in SOURCE_MODULES:
            raise _error("UNSUPPORTED_IMPORT", "Only QuantumCircuit, QuantumRegister, ClassicalRegister, standard gate classes, and numeric math constants can be imported.", node)
        for item in node.names:
            alias = item.asname or item.name
            self.bindable(alias, node)
            self.values.pop(alias, None)
            if f"{node.module}.{item.name}" in SOURCE_MODULES:
                self.modules[alias] = f"{node.module}.{item.name}"
                continue
            if node.module == "qiskit.circuit" and item.name in PARAMETER_TYPES:
                self.parameter_constructors[alias] = item.name
                continue
            if node.module == "qiskit.circuit" and item.name == "*":
                self.parameter_constructors.update({name: name for name in PARAMETER_TYPES})
            if node.module == "qiskit.quantum_info":
                if item.name not in OPERATOR_TYPES:
                    raise _error("UNSUPPORTED_IMPORT", "Only Pauli and SparsePauliOp are supported source operator constructors.", node)
                self.operator_constructors[alias] = item.name
                continue
            if node.module in ("qiskit", "qiskit.circuit"):
                if item.name in ("QuantumCircuit", "*"):
                    self.constructors.add(alias if item.name != "*" else "QuantumCircuit")
                if item.name in ("QuantumRegister", "*"):
                    self.qreg_constructors.add(alias if item.name != "*" else "QuantumRegister")
                if item.name in ("ClassicalRegister", "*"):
                    self.creg_constructors.add(alias if item.name != "*" else "ClassicalRegister")
                if item.name not in ("QuantumCircuit", "QuantumRegister", "ClassicalRegister", "*"):
                    raise _error(
                        "UNSUPPORTED_IMPORT",
                        f"Import '{item.name}' from '{node.module}' is outside the supported circuit-building subset.",
                        node,
                    )
            elif node.module == "qiskit.circuit.library":
                if item.name == "*":
                    for gate_name, gate_cls in SUPPORTED_GATE_CLASSES.items():
                        self.gate_constructors[gate_name] = gate_cls
                    self.library_factories.update(CIRCUIT_FACTORIES)
                elif item.name in SUPPORTED_GATE_CLASSES:
                    self.gate_constructors[alias] = SUPPORTED_GATE_CLASSES[item.name]
                elif item.name in CIRCUIT_FACTORIES:
                    self.library_factories[alias] = CIRCUIT_FACTORIES[item.name]
                else:
                    raise _error(
                        "UNSUPPORTED_IMPORT",
                        f"Gate class '{item.name}' from 'qiskit.circuit.library' is outside the supported gate subset.",
                        node,
                    )
            elif node.module in ("math", "numpy"):
                if node.module == "numpy" and item.name == "array":
                    self.array_constructors.add(alias)
                    continue
                if node.module == "numpy" and item.name in ("complex128", "float64"):
                    self.values[alias] = "complex" if item.name == "complex128" else "float"
                    self.constants.add(alias)
                    continue
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

    def module_name(self, node: ast.AST) -> str | None:
        if isinstance(node, ast.Name):
            return self.modules.get(node.id)
        if isinstance(node, ast.Attribute):
            parent = self.module_name(node.value)
            path = f"{parent}.{node.attr}" if parent else None
            return path if path in SOURCE_MODULES else None
        return None

    def _resolve_gate_class(self, node: ast.AST | None) -> type | None:
        if node is None:
            return None
        if isinstance(node, ast.Name) and node.id in self.gate_constructors:
            return self.gate_constructors[node.id]
        if isinstance(node, ast.Attribute) and node.attr in SUPPORTED_GATE_CLASSES:
            if self.module_name(node.value) == "qiskit.circuit.library":
                return SUPPORTED_GATE_CLASSES[node.attr]
        return None

    def registered(self, node: ast.AST, aliases: dict, registry: dict, module: str):
        if isinstance(node, ast.Name):
            return aliases.get(node.id)
        if isinstance(node, ast.Attribute) and self.module_name(node.value) == module:
            return registry.get(node.attr)
        return None

    def sdk_call(self, node: ast.AST, function, *args):
        try:
            return function(*args)
        except QuantumError:
            raise
        except Exception as exc:
            raise _error("INVALID_ARGUMENTS", f"Qiskit library operation failed: {str(exc)[:512]}", node) from exc

    def is_constructor(self, node: ast.AST) -> bool:
        return (isinstance(node, ast.Name) and node.id in self.constructors) or (
            isinstance(node, ast.Attribute) and self.module_name(node.value) in ("qiskit", "qiskit.circuit")
            and node.attr == "QuantumCircuit"
        )

    def is_qreg_constructor(self, node: ast.AST) -> bool:
        return (isinstance(node, ast.Name) and node.id in self.qreg_constructors) or (
            isinstance(node, ast.Attribute) and self.module_name(node.value) in ("qiskit", "qiskit.circuit")
            and node.attr == "QuantumRegister"
        )

    def is_creg_constructor(self, node: ast.AST) -> bool:
        return (isinstance(node, ast.Name) and node.id in self.creg_constructors) or (
            isinstance(node, ast.Attribute) and self.module_name(node.value) in ("qiskit", "qiskit.circuit")
            and node.attr == "ClassicalRegister"
        )

    def keywords(self, node: ast.Call) -> dict[str, Any]:
        values = {}
        for keyword in node.keywords:
            if keyword.arg is None or keyword.arg.startswith("_") or keyword.arg in values:
                raise _error("INVALID_ARGUMENTS", "Keyword unpacking, private options, and duplicate keywords are unsupported.", node)
            values[keyword.arg] = self.expression(keyword.value)
        return values

    def gate(self, cls: type, node: ast.Call) -> Gate:
        args = [self.expression(value) for value in node.args]
        kwargs = self.keywords(node)
        if cls in DATA_GATES.values():
            return self.sdk_call(node, self.support.data_gate, cls, args, kwargs)
        try:
            bound = inspect.signature(cls.__init__).bind(None, *args, **kwargs)
        except TypeError as exc:
            raise _error("INVALID_ARGUMENTS", f"Invalid {cls.__name__} arguments: {exc}", node) from exc
        for name, value in bound.arguments.items():
            if name == "self":
                continue
            if name in ("num_ctrl_qubits", "num_qubits", "num_variable_qubits", "num_state_qubits", "num_target_qubits", "amount"):
                _integer(value, name, 0 if name == "amount" else 1, MAX_QUBITS - (name == "num_ctrl_qubits"))
            elif name == "label":
                if value is not None and (not isinstance(value, str) or len(value) > 128):
                    raise _error("INVALID_ARGUMENTS", "Gate labels must be text of at most 128 characters.", node)
            elif name == "ctrl_state":
                if value is not None:
                    if isinstance(value, str):
                        if not 1 <= len(value) <= MAX_QUBITS or any(c not in "01" for c in value):
                            raise _error("INVALID_ARGUMENTS", "Control state must be a bounded binary string or integer.", node)
                    else:
                        _integer(value, "Control state", 0, 2**MAX_QUBITS - 1)
            elif name in ("dirty_ancillas", "relative_phase", "action_only"):
                if type(value) is not bool:
                    raise _error("INVALID_ARGUMENTS", f"{name} must be a boolean.", node)
            elif name == "basis":
                if not isinstance(value, str) or len(value) > 16:
                    raise _error("INVALID_ARGUMENTS", "basis must be a valid string.", node)
            elif name == "gate":
                if not isinstance(value, Gate):
                    raise _error("INVALID_ARGUMENTS", "gate must be a valid Gate instance.", node)
            elif name == "flags":
                if value is not None and (not isinstance(value, (list, tuple)) or not all(isinstance(x, int) for x in value)):
                    raise _error("INVALID_ARGUMENTS", "flags must be a list of integers.", node)
            elif name == "_base_label":
                if value is not None and not isinstance(value, str):
                    raise _error("INVALID_ARGUMENTS", "_base_label must be a string.", node)
            else:
                self.support.angle(value)
        try:
            gate = cls(*args, **kwargs)
        except Exception as exc:
            raise _error("INVALID_ARGUMENTS", f"Gate initialization failed: {exc}", node) from exc
        _integer(gate.num_qubits, "Gate qubit count", 0, MAX_QUBITS)
        return gate

    def expression(self, node: ast.AST) -> Any:
        if isinstance(node, ast.Constant):
            if type(node.value) in (int, float, complex):
                self.support.number(node.value)
                return node.value
            if node.value is None or isinstance(node.value, (str, bool)):
                return node.value
        if isinstance(node, ast.Name):
            if node.id == self.circuit_name:
                return self.circuit
            if node.id in self.values:
                return self.values[node.id]
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            module = self.modules.get(node.value.id)
            if module in ("math", "numpy") and node.attr in ("pi", "tau", "e") and not (module == "numpy" and node.attr == "tau"):
                return getattr(math, node.attr)
            if module == "numpy" and node.attr in ("complex128", "float64"):
                return "complex" if node.attr == "complex128" else "float"
        if isinstance(node, ast.Attribute) and node.attr in ("num_parameters", "parameters", "num_qubits", "num_clbits", "global_phase"):
            owner = self.expression(node.value)
            if isinstance(owner, QuantumCircuit):
                value = getattr(owner, node.attr)
                return tuple(value) if node.attr == "parameters" else value
        if isinstance(node, (ast.List, ast.Tuple)):
            if len(node.elts) > MAX_OPERATIONS:
                raise _error("RESOURCE_LIMIT", "Literal lists are limited to 500 entries.", node)
            return [self.expression(item) for item in node.elts]
        if isinstance(node, ast.Dict):
            if len(node.keys) > MAX_OPERATIONS or any(key is None for key in node.keys):
                raise _error("RESOURCE_LIMIT", "Parameter dictionaries must be bounded and cannot use unpacking.", node)
            result = {}
            for key, value in zip(node.keys, node.values):
                key = self.expression(key)
                if not isinstance(key, (str, Parameter)):
                    raise _error("INVALID_ARGUMENTS", "Binding keys must be parameter objects or names.", node)
                result[key] = self.support.angle(self.expression(value))
            return result
        if isinstance(node, ast.Compare):
            left = self.expression(node.left)
            for op, comp in zip(node.ops, node.comparators):
                right = self.expression(comp)
                if not isinstance(op, (ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.In, ast.NotIn)):
                    raise _error("UNSUPPORTED_SOURCE", "Only value and membership comparisons are supported.", node)
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
                self.support.number(value, symbolic=True)
                return value if isinstance(node.op, ast.UAdd) else -value
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow)):
            left, right = self.expression(node.left), self.expression(node.right)
            if isinstance(node.op, ast.Mult):
                if isinstance(left, list) and isinstance(right, int):
                    if right < 0 or len(left) * right > MAX_OPERATIONS:
                        raise _error("RESOURCE_LIMIT", f"List repetition exceeds {MAX_OPERATIONS} elements.", node)
                    return left * right
                if isinstance(right, list) and isinstance(left, int):
                    if left < 0 or len(right) * left > MAX_OPERATIONS:
                        raise _error("RESOURCE_LIMIT", f"List repetition exceeds {MAX_OPERATIONS} elements.", node)
                    return right * left
                if isinstance(left, tuple) and isinstance(right, int):
                    if right < 0 or len(left) * right > MAX_OPERATIONS:
                        raise _error("RESOURCE_LIMIT", f"Tuple repetition exceeds {MAX_OPERATIONS} elements.", node)
                    return left * right
                if isinstance(right, tuple) and isinstance(left, int):
                    if left < 0 or len(right) * left > MAX_OPERATIONS:
                        raise _error("RESOURCE_LIMIT", f"Tuple repetition exceeds {MAX_OPERATIONS} elements.", node)
                    return right * left
            self.support.number(left, symbolic=True)
            self.support.number(right, symbolic=True)
            try:
                if isinstance(node.op, ast.Add):
                    result = left + right
                elif isinstance(node.op, ast.Sub):
                    result = left - right
                elif isinstance(node.op, ast.Mult):
                    result = left * right
                elif isinstance(node.op, ast.Div):
                    result = left / right
                else:
                    if isinstance(right, ParameterExpression) or isinstance(right, complex) or abs(right) > 16:
                        raise _error("RESOURCE_LIMIT", "Exponents must be real constants with magnitude at most 16.", node)
                    result = left ** right
            except (ZeroDivisionError, OverflowError) as exc:
                raise _error("INVALID_PARAMETER", "Numeric expression divides by zero or overflows.", node) from exc
            self.support.number(result, symbolic=True)
            return result
        if isinstance(node, ast.Subscript):
            if isinstance(node.value, ast.Name):
                if node.value.id in self.quantum_registers:
                    idx = self.expression(node.slice)
                    return _integer(idx, "Qubit index", 0, self.quantum_registers[node.value.id] - 1)
                if node.value.id in self.classical_registers:
                    idx = self.expression(node.slice)
                    return _integer(idx, "Classical bit index", 0, self.classical_registers[node.value.id] - 1)
            value = self.expression(node.value)
            if isinstance(value, (list, tuple, range, ParameterVector, np.ndarray)):
                if isinstance(node.slice, ast.Slice):
                    bounds = [None if item is None else _integer(self.expression(item), "Slice bound", -MAX_OPERATIONS, MAX_OPERATIONS)
                              for item in (node.slice.lower, node.slice.upper, node.slice.step)]
                    index = slice(*bounds)
                else:
                    index = _integer(self.expression(node.slice), "Sequence index", -MAX_OPERATIONS, MAX_OPERATIONS)
                try:
                    result = value[index]
                    return result.item() if isinstance(result, np.generic) else result
                except (IndexError, ValueError, TypeError) as exc:
                    raise _error("INVALID_ARGUMENTS", "Invalid bounded sequence index or slice.", node) from exc
        if isinstance(node, ast.ListComp):
            if len(node.generators) == 1 and not node.generators[0].ifs and not node.generators[0].is_async and isinstance(node.generators[0].target, ast.Name):
                gen = node.generators[0]
                name = gen.target.id
                self.bindable(name, node)
                iterable = self.expression(gen.iter)
                from collections.abc import Iterable as PyIterable
                if isinstance(iterable, (list, tuple, range, PyIterable)):
                    items = []
                    absent = object()
                    previous = self.values.get(name, absent)
                    try:
                        for count, val in enumerate(iterable):
                            if count >= MAX_OPERATIONS:
                                raise _error("RESOURCE_LIMIT", "Comprehensions are limited to 500 entries.", node)
                            self.values[name] = val
                            items.append(self.expression(node.elt))
                    finally:
                        if previous is absent:
                            self.values.pop(name, None)
                        else:
                            self.values[name] = previous
                    return items
        if isinstance(node, ast.DictComp):
            if len(node.generators) == 1 and not node.generators[0].ifs and not node.generators[0].is_async and isinstance(node.generators[0].target, ast.Name):
                gen = node.generators[0]
                name = gen.target.id
                self.bindable(name, node)
                iterable = self.expression(gen.iter)
                from collections.abc import Iterable as PyIterable
                if isinstance(iterable, (list, tuple, range, PyIterable)):
                    result = {}
                    absent = object()
                    previous = self.values.get(name, absent)
                    try:
                        for count, val in enumerate(iterable):
                            if count >= MAX_OPERATIONS:
                                raise _error("RESOURCE_LIMIT", "Comprehensions are limited to 500 entries.", node)
                            self.values[name] = val
                            key = self.expression(node.key)
                            if not isinstance(key, (str, Parameter)):
                                raise _error("INVALID_ARGUMENTS", "Binding keys must be parameter objects or names.", node)
                            result[key] = self.support.angle(self.expression(node.value))
                    finally:
                        if previous is absent:
                            self.values.pop(name, None)
                        else:
                            self.values[name] = previous
                    return result
        if isinstance(node, ast.Call):
            if self.is_constructor(node.func):
                return self.new_circuit(node)
            gate_cls = self._resolve_gate_class(node.func)
            if gate_cls is not None:
                return self.gate(gate_cls, node)
            factory = self.registered(node.func, self.library_factories, CIRCUIT_FACTORIES, "qiskit.circuit.library")
            if factory is not None:
                return self.sdk_call(node, self.support.factory, factory,
                                     [self.expression(a) for a in node.args], self.keywords(node))
            parameter = self.registered(node.func, self.parameter_constructors,
                                        {name: name for name in PARAMETER_TYPES}, "qiskit.circuit")
            if parameter is not None:
                return self.sdk_call(node, self.support.parameter, parameter,
                                     [self.expression(a) for a in node.args], self.keywords(node))
            operator = self.registered(node.func, self.operator_constructors,
                                       {name: name for name in OPERATOR_TYPES}, "qiskit.quantum_info")
            if operator is not None:
                return self.sdk_call(node, self.support.operator, operator,
                                     [self.expression(a) for a in node.args], self.keywords(node))
            if isinstance(node.func, ast.Attribute) and node.func.attr == "from_list":
                operator = self.registered(node.func.value, self.operator_constructors,
                                           {name: name for name in OPERATOR_TYPES}, "qiskit.quantum_info")
                if operator is not None:
                    return self.sdk_call(node, self.support.operator, operator,
                                         [self.expression(a) for a in node.args], self.keywords(node), "from_list")
            if ((isinstance(node.func, ast.Name) and node.func.id in self.array_constructors) or
                    (isinstance(node.func, ast.Attribute) and self.module_name(node.func.value) == "numpy" and node.func.attr == "array")):
                kwargs = self.keywords(node)
                if len(node.args) != 1 or set(kwargs) - {"dtype"} or kwargs.get("dtype", "complex") not in ("complex", "float"):
                    raise _error("INVALID_ARGUMENTS", "Use numpy.array(literal_data, dtype=complex or float).", node)
                data = self.sdk_call(node, self.support.array, self.expression(node.args[0]))
                if kwargs.get("dtype") == "float":
                    if np.any(data.imag):
                        raise _error("INVALID_ARGUMENTS", "Complex data cannot use a real dtype.", node)
                    return data.real
                return data
            if isinstance(node.func, ast.Attribute) and node.func.attr in OBJECT_METHODS:
                return self.sdk_call(node, self.support.method, self.expression(node.func.value), node.func.attr,
                                     [self.expression(a) for a in node.args], self.keywords(node))
            if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
                module = self.modules.get(node.func.value.id)
                if module in ("math", "numpy") and node.func.attr in NUMERIC_MATH_NAMES and node.func.attr not in ("pi", "tau", "e"):
                    if node.keywords:
                        raise _error("INVALID_ARGUMENTS", "Numeric functions accept positional arguments only.", node)
                    fn = getattr(math, node.func.attr if node.func.attr != "abs" else "fabs")
                    args = [self.expression(a) for a in node.args]
                    res = float(fn(*args))
                    _number(res)
                    return res
            if isinstance(node.func, ast.Name) and callable(self.values.get(node.func.id)):
                if node.keywords:
                    raise _error("INVALID_ARGUMENTS", "Numeric functions accept positional arguments only.", node)
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
        owner = self.named_circuit(node.func.value) if isinstance(node.func, ast.Attribute) else None
        if owner is None:
            raise _error("UNSUPPORTED_SOURCE", "Only methods on declared circuit objects may be called.", node)
        primary, primary_name, measured = self.circuit, self.circuit_name, self.has_measurement
        try:
            self.circuit, self.circuit_name = owner, node.func.value.id
            self.has_measurement = any(item.operation.name == "measure" for item in owner.data)
            self._circuit_call(node)
        finally:
            self.circuit, self.circuit_name, self.has_measurement = primary, primary_name, measured

    def _circuit_call(self, node: ast.Call) -> None:
        if not (isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id == self.circuit_name and self.circuit is not None):
            raise _error("UNSUPPORTED_SOURCE", "Only methods on the declared quantum circuit may be called.", node)
        method_name = node.func.attr
        name = ALIASES.get(method_name, method_name)
        if name in ("draw", "depth", "size", "width"):
            return
        if name == "append":
            if node.keywords:
                raise _error("INVALID_ARGUMENTS", "append expects positional gate, qubits, and optional clbits.", node)
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
            kwargs = self.keywords(node)
            if set(kwargs) - {"ctrl_state", "label"}:
                raise _error("INVALID_ARGUMENTS", "mcx supports only ctrl_state and label keywords.", node)
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
                self.circuit.append(SUPPORTED_GATE_CLASSES["MCXGate"](len(ctrls), **kwargs), ctrls + [tgt])
            except Exception as exc:
                raise _error("INVALID_ARGUMENTS", f"mcx failed: {exc}", node) from exc
            if len(self.circuit.data) > MAX_OPERATIONS:
                raise _error("RESOURCE_LIMIT", f"Circuit exceeds {MAX_OPERATIONS} operations, including measurements and barriers.", node)
            return
        if name not in GATES and name not in ("measure", "measure_all", "barrier"):
            raise _error("UNSUPPORTED_GATE", f"Circuit operation '{name}' is not supported.", node)
        kwargs = self.keywords(node)
        allowed_keywords = ({"label", "ctrl_state"} if name in GATES else
                            {"label"} if name == "barrier" else
                            {"add_bits"} if name == "measure_all" else set())
        if set(kwargs) - allowed_keywords:
            raise _error("INVALID_ARGUMENTS", f"Unsupported keyword arguments for {name}.", node)
        if "label" in kwargs and (not isinstance(kwargs["label"], str) or len(kwargs["label"]) > 128):
            raise _error("INVALID_ARGUMENTS", "Gate labels must be text of at most 128 characters.", node)
        if "add_bits" in kwargs and type(kwargs["add_bits"]) is not bool:
            raise _error("INVALID_ARGUMENTS", "measure_all add_bits must be a boolean.", node)
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
            # Let Qiskit implement broadcasting after bounded index validation.
            if len(arguments) != parameter_count + qubit_count:
                raise _error("INVALID_ARGUMENTS", f"{name} expects {parameter_count} parameter(s) and {qubit_count} qubit argument(s).", node)
            for value in arguments[:parameter_count]:
                self.support.angle(value)
            arguments[:parameter_count] = [self.support.angle(value) for value in arguments[:parameter_count]]
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
            if kwargs.get("add_bits", True) and self.circuit.num_clbits + self.circuit.num_qubits > MAX_CLBITS:
                raise _error("RESOURCE_LIMIT", "Qiskit measure_all() adds one classical bit per qubit and would exceed the 10-bit limit. Use explicit measure instead.", node)
        try:
            getattr(self.circuit, name)(*arguments, **kwargs)
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


def _normalize_library_gates(circuit: QuantumCircuit, *, lower_mcx: bool = False, _depth: int = 0) -> QuantumCircuit:
    """Lower composite unitary instructions without dropping control states or phase."""
    if _depth > MAX_AST_DEPTH:
        raise QuantumError("RESOURCE_LIMIT", "Composite gate definitions exceed the nesting limit.")
    _integer(circuit.num_qubits, "Qubit count", 0 if _depth else 1, MAX_QUBITS)
    _integer(circuit.num_clbits, "Classical bit count", 0, MAX_CLBITS)
    if len(circuit.data) > MAX_OPERATIONS:
        raise QuantumError("RESOURCE_LIMIT", f"Circuit exceeds {MAX_OPERATIONS} operations.")
    normalized = QuantumCircuit(circuit.num_qubits, circuit.num_clbits)
    normalized.global_phase = _number(float(circuit.global_phase), "Global phase")
    for instruction in circuit.data:
        operation = instruction.operation
        qubits = [circuit.find_bit(bit).index for bit in instruction.qubits]
        clbits = [circuit.find_bit(bit).index for bit in instruction.clbits]
        native_gate = (operation.name in GATES or operation.name == "mcx") and getattr(operation, "base_class", None) in SUPPORTED_GATE_CLASSES.values()
        if lower_mcx and operation.name == "mcx":
            native_gate = False
        if native_gate or operation.name in ("measure", "barrier"):
            normalized.append(operation, qubits, clbits)
        elif isinstance(operation, Instruction) and not clbits:
            try:
                # Expand explicit definitions before invoking the compiler. A
                # user-defined QASM gate named "h" or "u" is not the standard
                # gate merely because its name matches a compiler basis entry.
                definition = operation.definition
                if definition is None:
                    if operation.base_class not in SUPPORTED_GATE_CLASSES.values():
                        raise QuantumError("UNSUPPORTED_GATE", f"Gate '{operation.name}' has no supported unitary definition.")
                    # Some trusted library gates, notably PermutationGate, use
                    # high-level synthesis instead of a definition property.
                    component = QuantumCircuit(operation.num_qubits)
                    component.append(operation, range(operation.num_qubits))
                else:
                    component = _normalize_library_gates(definition, lower_mcx=lower_mcx, _depth=_depth + 1)
                lowered = transpile(component, basis_gates=["u", "cx"], optimization_level=0, seed_transpiler=0)
            except QuantumError:
                raise
            except Exception as exc:
                raise QuantumError("UNSUPPORTED_GATE", f"Cannot lower gate '{operation.name}' to the supported unitary basis.") from exc
            if len(normalized.data) + len(lowered.data) > MAX_OPERATIONS:
                raise QuantumError("RESOURCE_LIMIT", f"Expanded circuit exceeds {MAX_OPERATIONS} operations.")
            normalized.compose(lowered, qubits=qubits, inplace=True)
        else:
            raise QuantumError("UNSUPPORTED_GATE", f"Operation '{operation.name}' is outside the supported terminal-measurement circuit subset.")
        if len(normalized.data) > MAX_OPERATIONS:
            raise QuantumError("RESOURCE_LIMIT", f"Expanded circuit exceeds {MAX_OPERATIONS} operations.")
    return normalized


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
    # Below displayed coordinate precision, a direction has no physical meaning.
    direction_defined = r >= 1e-8
    azimuth_defined = direction_defined and np.hypot(x, y) >= 1e-8
    theta = float(np.arccos(np.clip(z / r, -1.0, 1.0))) if direction_defined else 0.0
    phi = float(np.arctan2(y, x)) if azimuth_defined else 0.0
    purity = float(np.clip(np.real(np.trace(data @ data)), 0.0, 1.0))
    return {
        "qubit": qubit,
        "x": _round_real(x),
        "y": _round_real(y),
        "z": _round_real(z),
        "r": _round_real(r),
        "direction_defined": direction_defined,
        "azimuth_defined": bool(azimuth_defined),
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


def _load_qasm(source: str) -> QuantumCircuit:
    # Qiskit's exporter assumes extra qelib1 gates. Enable those spellings, but
    # honor explicit user definitions instead of replacing them with built-ins.
    without_comments = re.sub(r"//[^\n]*", "", source)
    if any(path != "qelib1.inc" for path in re.findall(r'\binclude\s+"([^\"]+)"', without_comments)):
        raise QuantumError("UNSUPPORTED_IMPORT", "OpenQASM may include only the built-in qelib1.inc; local files are unavailable.")
    declared = set(re.findall(r"\b(?:gate|opaque)\s+([A-Za-z_]\w*)", without_comments))
    instructions = [item for item in qasm2.LEGACY_CUSTOM_INSTRUCTIONS if item.name not in declared]
    # qelib1.inc is handled by Qiskit itself; user source cannot search local files.
    return qasm2.loads(source, include_path=(), custom_instructions=instructions)


def parse_source(source: str) -> dict[str, Any]:
    if not isinstance(source, str):
        raise QuantumError("INVALID_SOURCE", "Source must be text.")
    try:
        encoded = source.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise QuantumError("INVALID_SOURCE", "Source must contain valid UTF-8 text.") from exc
    if len(encoded) > MAX_SOURCE_BYTES:
        raise QuantumError("RESOURCE_LIMIT", f"Source exceeds {MAX_SOURCE_BYTES} UTF-8 bytes.")
    qasm_source = source.lstrip("\ufeff \t\r\n")
    selected_circuit = None
    qasm_start = qasm_source
    while qasm_start.startswith("//"):
        newline = qasm_start.find("\n")
        if newline < 0:
            break
        qasm_start = qasm_start[newline + 1:].lstrip(" \t\r\n")
    if qasm_start.startswith("OPENQASM") or (qasm_start.startswith("include ") and ("qreg " in qasm_start or "qubit" in qasm_start)):
        try:
            circuit = _load_qasm(qasm_source)
        except QuantumError:
            raise
        except Exception as exc:
            raise QuantumError("SYNTAX_ERROR", f"OpenQASM parser error: {exc}") from exc
    else:
        interpreter = _SourceInterpreter()
        circuit = interpreter.run(source)
        selected_circuit = interpreter.circuit_name
    circuit = _normalize_library_gates(circuit)
    ir = circuit_to_ir(circuit)
    metrics = _metrics(circuit, ir)
    # Pure unitary circuits are valid inputs. The simulation path adds an
    # identity q[i] -> c[i] measurement map at execution time without changing
    # the saved source or the ideal-state evidence returned by parsing.
    extra = compute_circuit_bloch_and_unitary(circuit, ir)
    extra_warnings = extra.pop("analysis_warnings", [])
    return {
        "ir": ir,
        "selected_circuit": selected_circuit,
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
                # Aer decomposes MCX into smaller operations. Attach errors to
                # those actual instructions rather than silently omitting MCX.
                circuit = _normalize_library_gates(circuit, lower_mcx=True)
                present = set(circuit.count_ops()) - {"measure", "barrier"}
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
                p = readout_error
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
