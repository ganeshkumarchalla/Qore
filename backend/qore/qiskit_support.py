"""Explicit, resource-bounded adapters for trusted Qiskit library objects.

This module never imports names supplied by source or evaluates Python code.
Only the constructors and object methods below can cross the interpreter boundary.
"""

import inspect
import math

import numpy as np
from qiskit import QuantumCircuit
from qiskit.circuit import Gate, Parameter, ParameterExpression, ParameterVector
import qiskit.circuit.library as library
from qiskit.quantum_info import Pauli, SparsePauliOp


DATA_GATES = {name: getattr(library, name) for name in (
    "PauliGate", "DiagonalGate", "PermutationGate", "UnitaryGate", "HamiltonianGate",
    "StatePreparation", "PauliEvolutionGate", "GraphStateGate",
)}
CIRCUIT_FACTORIES = {name: getattr(library, name) for name in (
    "RealAmplitudes", "EfficientSU2", "TwoLocal", "NLocal", "QFT", "ZZFeatureMap",
    "real_amplitudes", "efficient_su2", "n_local", "zz_feature_map", "pauli_feature_map",
)}
PARAMETER_TYPES = {"Parameter": Parameter, "ParameterVector": ParameterVector}
OPERATOR_TYPES = {"Pauli": Pauli, "SparsePauliOp": SparsePauliOp}
OBJECT_METHODS = {"assign_parameters", "compose", "inverse", "control", "power", "to_gate", "copy", "decompose"}


class BoundedQiskit:
    def __init__(self, qubits, operations, maximum_number, gates):
        self.qubits, self.operations, self.maximum_number = qubits, operations, maximum_number
        self.gates = gates

    def integer(self, value, minimum=0, maximum=None):
        maximum = self.operations if maximum is None else maximum
        if type(value) is not int or not minimum <= value <= maximum:
            raise ValueError(f"Expected an integer between {minimum} and {maximum}.")
        return value

    def number(self, value, symbolic=False):
        if symbolic and isinstance(value, ParameterExpression):
            if len(value.parameters) > self.operations:
                raise ValueError("Too many symbolic parameters.")
            if value.parameters:
                return value
            value = complex(value)
        if isinstance(value, np.generic):
            value = value.item()
        if type(value) not in (int, float, complex) or not math.isfinite(abs(value)) or abs(value) > self.maximum_number:
            raise ValueError("Expected a bounded finite numeric value.")
        return value

    def angle(self, value):
        value = self.number(value, symbolic=True)
        if isinstance(value, complex):
            if abs(value.imag) > 1e-12:
                raise ValueError("Gate angles must be real.")
            return float(value.real)
        return value

    def text(self, value, maximum=128):
        if not isinstance(value, str) or not 1 <= len(value) <= maximum:
            raise ValueError(f"Expected text of 1 to {maximum} characters.")
        return value

    def array(self, value, dimensions=None):
        if not isinstance(value, (list, tuple, np.ndarray)):
            raise ValueError("Use a literal numeric vector or matrix.")
        # Check the Python structure before NumPy can materialize broadcasted
        # or repeatedly referenced lists into an oversized allocation.
        pending, entries = [(value, 0)], 0
        while pending:
            item, depth = pending.pop()
            if isinstance(item, np.ndarray):
                if item.ndim + depth > 2:
                    raise ValueError("Numeric data supports one or two dimensions.")
                entries += item.size
            elif isinstance(item, (list, tuple)):
                if depth >= 2 or len(item) > self.operations:
                    raise ValueError("Numeric data supports bounded vectors and matrices.")
                pending.extend((element, depth + 1) for element in item)
            else:
                self.number(int(item) if type(item) is bool else item)
                entries += 1
            if entries > self.operations:
                raise ValueError(f"Numeric data must contain at most {self.operations} elements.")
        data = np.asarray(value, dtype=complex)
        if data.ndim not in (1, 2) or not 1 <= data.size <= self.operations:
            raise ValueError(f"Numeric data must contain at most {self.operations} elements in one or two dimensions.")
        if dimensions is not None and data.ndim != dimensions:
            raise ValueError(f"Expected {dimensions}-dimensional numeric data.")
        if not np.all(np.isfinite(data)) or np.max(np.abs(data)) > self.maximum_number:
            raise ValueError("Numeric data must be finite and bounded.")
        return data

    def circuit(self, value):
        if not isinstance(value, QuantumCircuit):
            raise ValueError("Expected a quantum circuit.")
        self.integer(value.num_qubits, 1, self.qubits)
        self.integer(value.num_clbits, 0, self.qubits)
        if len(value.data) > self.operations or value.num_parameters > self.operations:
            raise ValueError("Circuit exceeds the instruction or symbolic-parameter limit.")
        return value

    def parameter(self, name, args, kwargs):
        if name == "Parameter" and len(args) == 1 and not kwargs:
            return Parameter(self.text(args[0], 64))
        if name == "ParameterVector" and len(args) in (1, 2) and set(kwargs) <= {"length"}:
            if len(args) == 2 and kwargs:
                raise ValueError("Specify the vector length once.")
            length = args[1] if len(args) == 2 else kwargs.get("length")
            return ParameterVector(self.text(args[0], 64), self.integer(length, 1))
        raise ValueError("Use Parameter(name) or ParameterVector(name, length).")

    def operator(self, name, args, kwargs, method=None):
        if kwargs:
            raise ValueError("Operator constructors accept positional arguments only.")
        if name == "Pauli" and method is None and len(args) == 1:
            label = self.text(args[0], self.qubits)
            if any(c not in "IXYZ" for c in label):
                raise ValueError("Pauli labels use I, X, Y and Z.")
            return Pauli(label)
        if name == "SparsePauliOp" and method == "from_list" and len(args) == 1:
            terms = args[0]
            if not isinstance(terms, (list, tuple)) or not 1 <= len(terms) <= self.operations:
                raise ValueError("Use a bounded list of Pauli label and coefficient pairs.")
            validated = []
            for term in terms:
                if not isinstance(term, (list, tuple)) or len(term) != 2:
                    raise ValueError("Each Pauli term needs a label and coefficient.")
                pauli = self.operator("Pauli", [term[0]], {})
                coefficient = self.number(term[1])
                if validated and len(term[0]) != len(validated[0][0]):
                    raise ValueError("All Pauli terms must have the same width.")
                validated.append((pauli.to_label(), coefficient))
            return SparsePauliOp.from_list(validated)
        raise ValueError("Use Pauli(label) or SparsePauliOp.from_list(terms).")

    def data_gate(self, cls, args, kwargs):
        bound = inspect.signature(cls.__init__).bind(None, *args, **kwargs)
        values = dict(bound.arguments); values.pop("self", None)
        name = cls.__name__
        for key, value in values.items():
            if key in ("data", "diag"):
                data = self.array(value, 2 if key == "data" else 1)
                if key == "data" and (data.shape[0] != data.shape[1] or data.shape[0] & (data.shape[0] - 1)):
                    raise ValueError("Matrices must be square with a power-of-two dimension.")
            elif key == "adjacency_matrix":
                data = self.array(value, 2)
                if data.shape[0] != data.shape[1] or not 1 <= data.shape[0] <= self.qubits:
                    raise ValueError("Adjacency matrices need one row and column per qubit.")
                if np.any(data.imag) or not np.all(np.isin(data.real, [0, 1])):
                    raise ValueError("Adjacency matrices contain zero and one entries.")
            elif key == "pattern":
                if not isinstance(value, (list, tuple)) or not 1 <= len(value) <= self.qubits:
                    raise ValueError("Permutation patterns must fit the qubit limit.")
                if any(type(i) is not int for i in value) or sorted(value) != list(range(len(value))):
                    raise ValueError("A permutation must contain every qubit index exactly once.")
            elif key == "operator":
                if not isinstance(value, (Pauli, SparsePauliOp)) or value.num_qubits > self.qubits:
                    raise ValueError("Evolution requires a bounded Pauli or SparsePauliOp.")
                if isinstance(value, SparsePauliOp) and np.any(np.abs(value.coeffs.imag) > 1e-12):
                    raise ValueError("Pauli evolution requires real coefficients for a Hermitian operator.")
            elif key == "params":
                if isinstance(value, str):
                    self.text(value, self.qubits)
                elif type(value) is int:
                    self.integer(value, 0, 2**self.qubits - 1)
                else:
                    self.array(value, 1)
            elif key == "num_qubits":
                if value is not None:
                    self.integer(value, 1, self.qubits)
            elif key in ("inverse", "normalize", "check_input"):
                if type(value) is not bool or (key == "check_input" and not value):
                    raise ValueError("Boolean options must be explicit; unitary validation cannot be disabled.")
            elif key == "label":
                if value is not None:
                    self.text(value, self.qubits if name == "PauliGate" else 128)
            elif key == "synthesis":
                if value is not None:
                    raise ValueError("Custom evolution synthesis callbacks are unavailable.")
            else:
                self.angle(value)
        result = cls(*args, **kwargs)
        self.integer(result.num_qubits, 1, self.qubits)
        return result

    def factory(self, factory, args, kwargs):
        bound = inspect.signature(factory).bind(*args, **kwargs)
        for key, value in bound.arguments.items():
            if key in ("num_qubits", "feature_dimension"):
                self.integer(value, 1, self.qubits)
            elif key in ("reps", "approximation_degree"):
                self.integer(value, 0, 20 if key == "reps" else self.qubits)
            elif key in ("skip_unentangled_qubits", "skip_final_rotation_layer", "insert_barriers", "overwrite_block_parameters", "do_swaps", "inverse", "flatten"):
                if value is not None and type(value) is not bool:
                    raise ValueError(f"{key} must be a boolean.")
            elif key in ("name", "parameter_prefix"):
                if value is not None:
                    self.text(value, 64)
            elif key == "entanglement":
                entries = 0

                def validate_layout(layout, depth=0):
                    nonlocal entries
                    entries += 1
                    if entries > self.operations or depth > 3:
                        raise ValueError("Use a bounded explicit entanglement layout.")
                    if isinstance(layout, str):
                        if layout not in ("full", "linear", "reverse_linear", "circular", "sca", "pairwise"):
                            raise ValueError("Unsupported entanglement layout.")
                    elif isinstance(layout, (list, tuple)):
                        if len(layout) > self.operations:
                            raise ValueError("Use a bounded explicit entanglement layout.")
                        for item in layout:
                            if type(item) is int:
                                entries += 1
                                if entries > self.operations:
                                    raise ValueError("Use a bounded explicit entanglement layout.")
                                self.integer(item, 0, self.qubits - 1)
                            else:
                                validate_layout(item, depth + 1)
                    else:
                        raise ValueError("Use a named or bounded explicit entanglement layout.")

                validate_layout(value)
            elif key in ("su2_gates", "rotation_blocks", "entanglement_blocks", "paulis"):
                blocks = [value] if isinstance(value, (str, Gate, QuantumCircuit)) else value
                if blocks is not None:
                    minimum = 0 if key in ("rotation_blocks", "entanglement_blocks") else 1
                    if not isinstance(blocks, (list, tuple)) or not minimum <= len(blocks) <= 8:
                        raise ValueError("Use up to eight supported circuit blocks.")
                    for block in blocks:
                        if key in ("rotation_blocks", "entanglement_blocks"):
                            if isinstance(block, QuantumCircuit):
                                self.circuit(block)
                                continue
                            if isinstance(block, Gate):
                                self.integer(block.num_qubits, 1, self.qubits)
                                if len(block.params) > self.operations:
                                    raise ValueError("Too many circuit-block parameters.")
                                continue
                        self.text(block, self.qubits if key == "paulis" else 32)
                        if key == "paulis":
                            if any(c not in "IXYZ" for c in block):
                                raise ValueError("Pauli blocks use I, X, Y and Z.")
                        elif block not in self.gates:
                            raise ValueError("Circuit blocks must be supported native gate names.")
            elif key == "initial_state":
                if value is not None:
                    self.circuit(value)
            elif key == "data_map_func":
                if value is not None:
                    raise ValueError("Custom feature-map callbacks are unavailable.")
            elif key == "alpha":
                self.angle(value)
            else:
                raise ValueError(f"Unsupported circuit-library option '{key}'.")
        return self.circuit(factory(*args, **kwargs))

    def method(self, owner, name, args, kwargs):
        if name not in OBJECT_METHODS or not isinstance(owner, (Gate, QuantumCircuit)):
            raise ValueError("Unsupported quantum object method.")
        if name == "assign_parameters":
            if not isinstance(owner, QuantumCircuit) or len(args) != 1 or set(kwargs) - {"inplace"}:
                raise ValueError("Use circuit.assign_parameters(values, inplace=False).")
            if "inplace" in kwargs and type(kwargs["inplace"]) is not bool:
                raise ValueError("inplace must be a boolean.")
            parameters = args[0]
            if isinstance(parameters, dict):
                if len(parameters) > self.operations:
                    raise ValueError("Too many parameter bindings.")
                for key, value in parameters.items():
                    if not isinstance(key, (str, Parameter)):
                        raise ValueError("Parameter binding keys must be parameter objects or names.")
                    self.angle(value)
            else:
                if not isinstance(parameters, (list, tuple, np.ndarray)) or len(parameters) > self.operations:
                    raise ValueError("Use a bounded binding dictionary or sequence.")
                for value in parameters:
                    self.angle(value)
        elif name == "compose":
            if not isinstance(owner, QuantumCircuit) or not 1 <= len(args) <= 2 or set(kwargs) - {"qubits", "inplace", "front"}:
                raise ValueError("Use circuit.compose(other, qubits=None, inplace=False, front=False).")
            if not isinstance(args[0], (Gate, QuantumCircuit)):
                raise ValueError("Compose a supported gate or circuit.")
            if isinstance(args[0], QuantumCircuit):
                self.circuit(args[0])
            if len(args) == 2 and "qubits" in kwargs:
                raise ValueError("Specify the qubit mapping once.")
            mapping = args[1] if len(args) == 2 else kwargs.get("qubits")
            if mapping is not None:
                if not isinstance(mapping, (list, tuple, range)) or len(mapping) > self.qubits:
                    raise ValueError("Use a bounded qubit mapping.")
                for index in mapping:
                    self.integer(index, 0, owner.num_qubits - 1)
            for option in ("inplace", "front"):
                if option in kwargs and type(kwargs[option]) is not bool:
                    raise ValueError(f"{option} must be a boolean.")
        elif name == "control":
            if len(args) > 1 or set(kwargs) - {"num_ctrl_qubits", "ctrl_state", "label"}:
                raise ValueError("Use control(num_ctrl_qubits=1, ctrl_state=None, label=None).")
            controls = args[0] if args else kwargs.get("num_ctrl_qubits", 1)
            self.integer(controls, 1, self.qubits - owner.num_qubits)
            if "ctrl_state" in kwargs:
                state = kwargs["ctrl_state"]
                if isinstance(state, str):
                    if len(state) != controls or any(c not in "01" for c in state):
                        raise ValueError("Control state width must match the number of controls.")
                elif state is not None:
                    self.integer(state, 0, 2**controls - 1)
            if kwargs.get("label") is not None:
                self.text(kwargs["label"])
        elif name == "power":
            if len(args) != 1 or kwargs:
                raise ValueError("power expects one bounded real exponent.")
            exponent = self.angle(args[0])
            if isinstance(exponent, ParameterExpression) or abs(exponent) > 16:
                raise ValueError("Power exponents must be real and at most 16 in magnitude.")
            if owner.num_qubits > 4:
                raise ValueError("Gate and circuit powers are limited to four qubits for bounded matrix synthesis.")
        elif name in ("inverse", "copy", "to_gate", "decompose"):
            if name == "decompose":
                if not isinstance(owner, QuantumCircuit):
                    raise ValueError("decompose applies to circuits.")
                if len(args) > 1 or set(kwargs) - {"gates_to_decompose", "reps"}:
                    raise ValueError("decompose accepts optional gates_to_decompose or reps.")
            else:
                if args or kwargs:
                    raise ValueError(f"Use {name}() without options.")
                if name == "to_gate" and not isinstance(owner, QuantumCircuit):
                    raise ValueError("to_gate applies to circuits.")
        result = getattr(owner, name)(*args, **kwargs)
        if isinstance(result, QuantumCircuit):
            self.circuit(result)
        elif isinstance(result, Gate):
            self.integer(result.num_qubits, 0, self.qubits)
        elif result is not None:
            raise ValueError("This operation did not return a supported quantum object.")
        if isinstance(owner, QuantumCircuit):
            self.circuit(owner)
        return result
