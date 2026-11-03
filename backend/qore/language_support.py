"""Bounded static language adapters. No submitted Python is executed here.

Q# is checked against a closed circuit grammar before the Microsoft compiler
sees it. Each compilation gets its own context, without a project or imports.
OpenQASM 3 is checked as a syntax tree before Qiskit allocates circuit objects.
"""

from __future__ import annotations

import ast
import importlib.metadata
import importlib.util
import math
import os
import re

from qiskit import ClassicalRegister, QuantumCircuit, QuantumRegister

# Set the documented opt-out before the optional SDK is imported. No program
# source or diagnostic telemetry should leave the QORE execution environment.
os.environ["QDK_PYTHON_TELEMETRY"] = "none"


class SourceLanguageError(ValueError):
    def __init__(self, code: str, message: str):
        self.code, self.message = code, message
        super().__init__(message)


def available(module: str) -> bool:
    return importlib.util.find_spec(module) is not None


def _reject(message: str, code: str = "UNSUPPORTED_SOURCE"):
    raise SourceLanguageError(code, message)


def strip_comments(source: str) -> str:
    return re.sub(r"/\*.*?\*/|//[^\n]*", " ", source, flags=re.DOTALL).strip()


def _bounded_syntax(source: str):
    depth = 0
    for char in source:
        if char in "([{":
            depth += 1
            if depth > 64:
                _reject("Source nesting exceeds 64 levels.", "RESOURCE_LIMIT")
        elif char in ")]}":
            depth -= 1
    if len(source) > 32768:
        _reject("Source exceeds the language adapter limit.", "RESOURCE_LIMIT")


def _finite(value):
    if type(value) not in (int, float) or not math.isfinite(value) or abs(value) > 1e12:
        _reject("Numeric expressions must remain finite and at most 1e12 in magnitude.", "INVALID_PARAMETER")
    return value


def load_qasm3(source: str, *, max_qubits: int, max_operations: int) -> QuantumCircuit:
    if not available("qiskit_qasm3_import"):
        _reject("OpenQASM 3 requires the optional qiskit-tools installation.", "DEPENDENCY_UNAVAILABLE")
    from openqasm3 import ast as qa, parse
    from qiskit_qasm3_import import convert

    _bounded_syntax(strip_comments(source))
    try:
        program = parse(source)
    except Exception:
        _reject("Invalid OpenQASM 3 syntax.", "SYNTAX_ERROR")
    if program.version not in ("3", "3.0"):
        _reject("Use OPENQASM 3.0 for this importer.")
    if len(program.statements) > max_operations + 32:
        _reject("OpenQASM 3 exceeds the statement limit.", "RESOURCE_LIMIT")

    def number(node, depth=0):
        if depth > 64:
            _reject("Numeric expression is too deeply nested.", "RESOURCE_LIMIT")
        if isinstance(node, (qa.IntegerLiteral, qa.FloatLiteral)):
            return _finite(node.value)
        if isinstance(node, qa.Identifier) and node.name in ("pi", "tau", "euler"):
            return {"pi": math.pi, "tau": math.tau, "euler": math.e}[node.name]
        if isinstance(node, qa.UnaryExpression) and node.op.name == "-":
            return _finite(-number(node.expression, depth + 1))
        if isinstance(node, qa.BinaryExpression) and node.op.name in ("+", "-", "*", "/"):
            left, right = number(node.lhs, depth + 1), number(node.rhs, depth + 1)
            if node.op.name == "/" and right == 0:
                _reject("Division by zero in gate parameter.", "INVALID_PARAMETER")
            return _finite({"+": lambda: left + right, "-": lambda: left - right,
                            "*": lambda: left * right, "/": lambda: left / right}[node.op.name]())
        _reject("OpenQASM 3 parameters support numeric literals, pi/tau/euler, and + - * /.")

    def width(size):
        if size is None:
            return 1
        if not isinstance(size, qa.IntegerLiteral) or type(size.value) is not int or not 1 <= size.value <= max_qubits:
            _reject(f"Register sizes must be literal integers from 1 to {max_qubits}.", "RESOURCE_LIMIT")
        return size.value

    registers = {}
    qtotal = ctotal = cost = 0

    def reference(node, quantum=True):
        if isinstance(node, qa.Identifier):
            name, index = node.name, None
        elif isinstance(node, qa.IndexedIdentifier):
            name = node.name.name
            if len(node.indices) != 1 or not isinstance(node.indices[0], list) or len(node.indices[0]) != 1:
                _reject("Only single literal register indices are supported.")
            item = node.indices[0][0]
            if not isinstance(item, qa.IntegerLiteral):
                _reject("Register indices must be literal integers.")
            index = item.value
        else:
            _reject("Only named registers and literal indices are supported.")
        if name not in registers or registers[name][1] != quantum:
            _reject("Unknown register or incorrect register type.", "INVALID_ARGUMENTS")
        count = registers[name][0]
        if index is not None and not 0 <= index < count:
            _reject("Register index is out of bounds.", "INVALID_ARGUMENTS")
        return count if index is None else 1

    for statement in program.statements:
        if getattr(statement, "annotations", []):
            _reject("OpenQASM annotations are unavailable.")
        if isinstance(statement, qa.Include):
            if statement.filename != "stdgates.inc":
                _reject("OpenQASM 3 may include only the built-in stdgates.inc.", "UNSUPPORTED_IMPORT")
        elif isinstance(statement, (qa.QubitDeclaration, qa.ClassicalDeclaration)):
            is_quantum = isinstance(statement, qa.QubitDeclaration)
            if not is_quantum and not isinstance(statement.type, qa.BitType):
                _reject("Only qubit and bit registers are supported.")
            count = width(statement.size if is_quantum else statement.type.size)
            name = (statement.qubit if is_quantum else statement.identifier).name
            if name in registers:
                _reject("Register names must be unique.", "INVALID_ARGUMENTS")
            registers[name] = (count, is_quantum)
            qtotal += count if is_quantum else 0
            ctotal += 0 if is_quantum else count
            if max(qtotal, ctotal) > max_qubits:
                _reject(f"Circuits support at most {max_qubits} qubits and classical bits.", "RESOURCE_LIMIT")
            if not is_quantum and statement.init_expression is not None:
                if not isinstance(statement.init_expression, qa.QuantumMeasurement):
                    _reject("Classical bits can only be initialized with measurement.")
                if reference(statement.init_expression.qubit) != count:
                    _reject("Measurement register widths must match.", "INVALID_ARGUMENTS")
                cost += count
        elif isinstance(statement, qa.QuantumGate):
            if statement.duration is not None or len(statement.modifiers) > 2:
                _reject("Timed gates and more than two gate modifiers are unavailable.")
            for modifier in statement.modifiers:
                if modifier.modifier.name not in ("inv", "ctrl", "negctrl"):
                    _reject("Only inv, ctrl and negctrl gate modifiers are supported.")
                if modifier.argument is not None:
                    if not isinstance(modifier.argument, qa.IntegerLiteral) or not 1 <= modifier.argument.value < max_qubits:
                        _reject("Control counts must be bounded literal integers.", "RESOURCE_LIMIT")
            for argument in statement.arguments:
                number(argument)
            cost += max((reference(qubit) for qubit in statement.qubits), default=1)
        elif isinstance(statement, qa.QuantumMeasurementStatement):
            count = reference(statement.measure.qubit)
            if statement.target is None or reference(statement.target, False) != count:
                _reject("Measurements require a matching classical bit or register.", "INVALID_ARGUMENTS")
            cost += count
        elif isinstance(statement, qa.QuantumBarrier):
            for qubit in statement.qubits:
                reference(qubit)
            cost += 1
        else:
            _reject(f"OpenQASM 3 statement {type(statement).__name__} is outside the static circuit subset.")
        if cost > max_operations:
            _reject("Circuit exceeds the operation limit.", "RESOURCE_LIMIT")
    try:
        return convert(program)
    except Exception:
        _reject("OpenQASM 3 could not be converted to a supported Qiskit circuit.", "INVALID_ARGUMENTS")


QSHARP_GATES = {
    "H": ("h", 0, 1), "X": ("x", 0, 1), "Y": ("y", 0, 1), "Z": ("z", 0, 1),
    "I": ("id", 0, 1), "S": ("s", 0, 1), "T": ("t", 0, 1),
    "Rx": ("rx", 1, 1), "Ry": ("ry", 1, 1), "Rz": ("rz", 1, 1),
    "R1": ("p", 1, 1), "CNOT": ("cx", 0, 2), "CX": ("cx", 0, 2),
    "CY": ("cy", 0, 2), "CZ": ("cz", 0, 2), "CCNOT": ("ccx", 0, 3),
    "SWAP": ("swap", 0, 2),
}


def _split_arguments(text):
    if not text.strip():
        return []
    result, start, depth = [], 0, 0
    for index, char in enumerate(text):
        if char in "([":
            depth += 1
        elif char in ")]":
            depth -= 1
        elif char == "," and depth == 0:
            result.append(text[start:index].strip())
            start = index + 1
    result.append(text[start:].strip())
    return result


def _qsharp_number(text):
    text = re.sub(r"\bPI\s*\(\s*\)", "pi", text)
    try:
        tree = ast.parse(text, mode="eval")
    except SyntaxError:
        _reject("Invalid Q# numeric expression.", "SYNTAX_ERROR")

    def visit(node):
        if isinstance(node, ast.Constant):
            return _finite(node.value)
        if isinstance(node, ast.Name) and node.id == "pi":
            return math.pi
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            return _finite(visit(node.operand) * (-1 if isinstance(node.op, ast.USub) else 1))
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
            left, right = visit(node.left), visit(node.right)
            if isinstance(node.op, ast.Div) and right == 0:
                _reject("Division by zero in Q# gate parameter.", "INVALID_PARAMETER")
            return _finite({ast.Add: lambda: left + right, ast.Sub: lambda: left - right,
                            ast.Mult: lambda: left * right, ast.Div: lambda: left / right}[type(node.op)]())
        _reject("Q# angles support numeric literals, PI(), and + - * /.")

    if len(list(ast.walk(tree))) > 128:
        _reject("Numeric expression exceeds its complexity limit.", "RESOURCE_LIMIT")
    return float(visit(tree.body))


def load_qsharp(source: str, *, max_qubits: int, max_operations: int):
    """Validate a straight-line Main operation, compile QIR, and build its circuit.

    Reset after terminal measurement affects neither the recorded results nor
    the premeasurement state. It remains in QIR and is omitted in the QORE IR.
    """
    if not available("qdk"):
        _reject("Q# requires the optional Microsoft QDK installation.", "DEPENDENCY_UNAVAILABLE")
    clean = strip_comments(source)
    _bounded_syntax(clean)
    namespace = None
    wrapper = re.fullmatch(r"namespace\s+([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)\s*\{(.*)\}", clean, re.DOTALL)
    if wrapper:
        namespace, clean = wrapper.groups()
        clean = clean.strip()
    # Only standard-library opens; no project manifests, remote packages or files.
    while clean.startswith("open "):
        opened = re.match(r"open\s+(Std\.(?:Intrinsic|Measurement|Math)|Microsoft\.Quantum\.(?:Intrinsic|Measurement|Math))\s*;", clean)
        if not opened:
            _reject("Only standard Intrinsic, Measurement and Math Q# namespaces may be opened.", "UNSUPPORTED_IMPORT")
        clean = clean[opened.end():].strip()
    operation = re.fullmatch(r"(?:@EntryPoint\s*\(\s*\)\s*)?operation\s+Main\s*\(\s*\)\s*:\s*(Unit|Result\s*\[\s*\]|Result)\s*\{([^{}]*)\}", clean, re.DOTALL)
    if not operation:
        _reject("Q# supports one straight-line operation Main() returning Unit, Result, or Result[].")
    return_type, body = operation.groups()
    return_type = re.sub(r"\s", "", return_type)
    statements = [part.strip() for part in body.split(";")]
    # Q# permits its final expression without a trailing semicolon.
    statements = [part for part in statements if part]
    if len(statements) > max_operations + max_qubits + 1:
        _reject("Q# exceeds the statement limit.", "RESOURCE_LIMIT")
    circuit = QuantumCircuit()
    registers = {}
    measurements = []
    returned = False
    reset_used = False

    def reference(text, array=False):
        match = re.fullmatch(r"([A-Za-z_]\w*)(?:\[\s*(\d+)\s*\])?", text.strip())
        if not match or match[1] not in registers:
            _reject("Q# qubits must use a declared register and a literal index.")
        register, is_array = registers[match[1]]
        if array:
            if match[2] is not None or not is_array:
                _reject("MResetEachZ requires a complete qubit array.")
            return list(register)
        if match[2] is None:
            if is_array:
                _reject("Select an array qubit with a literal index.")
            return register[0]
        if not is_array or len(match[2]) > 2 or int(match[2]) >= len(register):
            _reject("Q# qubit index is out of bounds.", "INVALID_ARGUMENTS")
        return register[int(match[2])]

    def measure(expression):
        nonlocal reset_used
        call = re.fullmatch(r"(M|MResetZ|MResetEachZ)\s*\((.*)\)", expression.strip(), re.DOTALL)
        if not call:
            _reject("Return measurements with M, MResetZ, or MResetEachZ.")
        qubits = reference(call[2], array=call[1] == "MResetEachZ")
        qubits = qubits if isinstance(qubits, list) else [qubits]
        if any(qubit in measurements for qubit in qubits):
            _reject("Each qubit may be measured only once.")
        measurements.extend(qubits)
        reset_used |= call[1] != "M"
        return call[1] == "MResetEachZ"

    for statement in statements:
        if returned:
            _reject("Statements after the Q# return expression are unavailable.")
        allocation = re.fullmatch(r"use\s+([A-Za-z_]\w*)\s*=\s*Qubit\s*(\[\s*(\d+)\s*\]|\(\s*\))", statement)
        if allocation:
            if circuit.data or measurements or allocation[1] in registers:
                _reject("Declare uniquely named Q# qubits before applying gates.")
            if allocation[3] is not None and len(allocation[3]) > 2:
                _reject(f"Q# circuits support at most {max_qubits} qubits.", "RESOURCE_LIMIT")
            count = int(allocation[3] or 1)
            if not 1 <= count <= max_qubits or circuit.num_qubits + count > max_qubits:
                _reject(f"Q# circuits support at most {max_qubits} qubits.", "RESOURCE_LIMIT")
            register = QuantumRegister(count, allocation[1])
            circuit.add_register(register)
            registers[allocation[1]] = (register, allocation[3] is not None)
            continue
        expression = re.sub(r"^return\s+", "", statement)
        if expression != statement or re.match(r"(?:M|MResetZ|MResetEachZ)\s*\(", statement):
            if expression == "()" and return_type == "Unit":
                returned = True
                continue
            if expression.startswith("[") and expression.endswith("]"):
                if return_type != "Result[]":
                    _reject("Measurement return type must match the operation signature.")
                for item in _split_arguments(expression[1:-1]):
                    if measure(item):
                        _reject("Return MResetEachZ directly, not inside an array.")
            else:
                is_array = measure(expression)
                if return_type != ("Result[]" if is_array else "Result"):
                    _reject("Measurement return type must match the operation signature.")
            returned = True
            continue
        gate_call = re.fullmatch(r"(Adjoint\s+)?([A-Za-z_]\w*)\s*\((.*)\)", statement, re.DOTALL)
        if not gate_call or gate_call[2] not in QSHARP_GATES or measurements:
            _reject("Only supported static Q# gates followed by terminal measurements are available.")
        method, parameter_count, qubit_count = QSHARP_GATES[gate_call[2]]
        arguments = _split_arguments(gate_call[3])
        if len(arguments) != parameter_count + qubit_count:
            _reject("Incorrect Q# gate argument count.", "INVALID_ARGUMENTS")
        parameters = [_qsharp_number(arg) for arg in arguments[:parameter_count]]
        qubits = [reference(arg) for arg in arguments[parameter_count:]]
        if len(set(qubits)) != len(qubits):
            _reject("Gate qubits must be distinct.", "INVALID_ARGUMENTS")
        gate_circuit = QuantumCircuit(qubit_count)
        getattr(gate_circuit, method)(*parameters, *range(qubit_count))
        gate = gate_circuit.data[0].operation
        circuit.append(gate.inverse() if gate_call[1] else gate, qubits)
        if len(circuit.data) > max_operations:
            _reject("Q# circuit exceeds the operation limit.", "RESOURCE_LIMIT")
    if not circuit.num_qubits or (return_type != "Unit" and not returned):
        _reject("Q# Main must allocate qubits and return the declared measurement result.")
    if len(circuit.data) + len(measurements) > max_operations:
        _reject("Q# circuit exceeds the operation limit.", "RESOURCE_LIMIT")
    if measurements:
        circuit.add_register(ClassicalRegister(len(measurements), "meas"))
        for index, qubit in enumerate(measurements):
            circuit.measure(qubit, index)

    # The source passed here has no loops, recursion, callbacks, arbitrary calls,
    # mutable variables, nested declarations, or imports outside the standard lib.
    # Context.eval is Microsoft's Q# compiler API, NOT Python eval.
    from qdk import Context, TargetProfile
    context = None
    failed = False
    try:
        context = Context(target_profile=TargetProfile.Base)
        context.eval(source)
        qir = str(context.compile(f"{namespace + '.' if namespace else ''}Main()"))
    except Exception:
        failed = True
    finally:
        if context is not None:
            # QDK callables in this public namespace reference their Context.
            # Break that cycle on the creating thread: its native interpreter
            # is thread-affine and must not await collection on another thread.
            vars(context.code).clear()
        context = None
    if failed:
        _reject("Microsoft QDK could not compile this Q# circuit. Check Q# syntax and gate types.", "SYNTAX_ERROR")
    return circuit, {
        "qir": qir,
        "compiler": {"name": "Microsoft QDK", "version": importlib.metadata.version("qdk"), "target_profile": "Base"},
        "language_warnings": (["Terminal Q# resets are retained in QIR; QORE circuit analysis shows the premeasurement state and measurement results."] if reset_used else []),
    }
