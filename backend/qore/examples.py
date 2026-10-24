EXAMPLES = [
    {
        "id": "bell",
        "name": "Bell state",
        "description": "Prepare two entangled qubits. Ideal outcomes 00 and 11 each have probability 1/2.",
        "source": "# Bell state · correlated measurements\nfrom qiskit import QuantumCircuit\n\nqc = QuantumCircuit(2, 2)\nqc.h(0)\nqc.cx(0, 1)\nqc.measure(0, 0)\nqc.measure(1, 1)\n",
    },
    {
        "id": "redundant-bell",
        "name": "Bell with redundant gates",
        "description": "A Bell state with cancelling X and CX pairs. Inspect a real compiler's candidate.",
        "source": "# Equivalent Bell state with redundant operations\nfrom qiskit import QuantumCircuit\n\nqc = QuantumCircuit(2, 2)\nqc.x(0)\nqc.x(0)\nqc.h(0)\nqc.cx(0, 1)\nqc.cx(0, 1)\nqc.cx(0, 1)\nqc.measure(0, 0)\nqc.measure(1, 1)\n",
    },
    {
        "id": "ghz",
        "name": "GHZ · three qubits",
        "description": "Extend Bell-state correlation to three qubits using two controlled gates.",
        "source": "from qiskit import QuantumCircuit\n\nqc = QuantumCircuit(3, 3)\nqc.h(0)\nqc.cx(0, 1)\nqc.cx(1, 2)\nqc.measure(0, 0)\nqc.measure(1, 1)\nqc.measure(2, 2)\n",
    },
    {
        "id": "rotation",
        "name": "Rotation & bit ordering",
        "description": "A parameterized rotation with reversed classical output mapping.",
        "source": "from qiskit import QuantumCircuit\nfrom math import pi\n\nqc = QuantumCircuit(2, 2)\nqc.ry(pi / 3, 0)\nqc.x(1)\nqc.measure(0, 1)\nqc.measure(1, 0)\n",
    },
    {
        "id": "superdense",
        "name": "Superdense Coding",
        "description": "Transmits two classical bits between Alice and Bob using only one entangled qubit.",
        "source": "# Superdense Coding Protocol\n# Transmits 2 classical bits using 1 entangled qubit\nfrom qiskit import QuantumCircuit\n\nqc = QuantumCircuit(2, 2)\n\n# 1. Prepare shared Bell pair\nqc.h(0)\nqc.cx(0, 1)\n\n# 2. Alice encodes message '11' onto qubit 0\nqc.z(0)\nqc.x(0)\n\n# 3. Bob decodes by applying inverse Bell measurement\nqc.cx(0, 1)\nqc.h(0)\n\n# 4. Bob measures to recover 11\nqc.measure(0, 0)\nqc.measure(1, 1)\n",
    },
    {
        "id": "qft",
        "name": "Quantum Fourier Transform (3-Qubit)",
        "description": "Computes the discrete Fourier transform of quantum amplitudes using Hadamard and controlled phase gates.",
        "source": "# 3-Qubit Quantum Fourier Transform (QFT)\nfrom qiskit import QuantumCircuit\nfrom math import pi\n\nqc = QuantumCircuit(3, 3)\n\n# Initialize input state |101>\nqc.x(0)\nqc.x(2)\n\n# QFT stage on qubit 0\nqc.h(0)\nqc.cp(pi / 2, 1, 0)\nqc.cp(pi / 4, 2, 0)\n\n# QFT stage on qubit 1\nqc.h(1)\nqc.cp(pi / 2, 2, 1)\n\n# QFT stage on qubit 2\nqc.h(2)\n\n# Swap qubits for canonical frequency ordering\nqc.swap(0, 2)\n\n# Terminal measurements\nqc.measure(0, 0)\nqc.measure(1, 1)\nqc.measure(2, 2)\n",
    },
]
