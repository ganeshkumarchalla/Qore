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
    {
        "id": "grover",
        "name": "Grover's Search Algorithm (2-Qubit)",
        "description": "Quadratic quantum speedup searching an unsorted database. Marks and amplifies state |11> to 100% probability.",
        "source": "# Grover's Search Algorithm (2-Qubit)\n# Amplifies target marked state |11>\nfrom qiskit import QuantumCircuit\n\nqc = QuantumCircuit(2, 2)\n\n# 1. Equal superposition\nqc.h(0)\nqc.h(1)\n\n# 2. Oracle marking state |11>\nqc.cz(0, 1)\n\n# 3. Grover diffusion operator\nqc.h(0)\nqc.h(1)\nqc.x(0)\nqc.x(1)\nqc.cz(0, 1)\nqc.x(0)\nqc.x(1)\nqc.h(0)\nqc.h(1)\n\n# 4. Measure marked state\nqc.measure(0, 0)\nqc.measure(1, 1)\n",
    },
    {
        "id": "teleportation",
        "name": "Quantum Teleportation (3-Qubit)",
        "description": "Transfers quantum information from a source qubit to a target receiver using entanglement and deferred corrections.",
        "source": "# Quantum Teleportation Protocol\n# Transfers unknown state from Alice (q0) to Bob (q2)\nfrom qiskit import QuantumCircuit\n\nqc = QuantumCircuit(3, 3)\n\n# Prepare message state on q0\nqc.h(0)\n\n# Share EPR Bell pair between Alice (q1) and Bob (q2)\nqc.h(1)\nqc.cx(1, 2)\n\n# Alice entangles message with her half of Bell pair\nqc.cx(0, 1)\nqc.h(0)\n\n# Deferred unitary correction to Bob\nqc.cx(1, 2)\nqc.cz(0, 2)\n\n# Bob measures recovered state\nqc.measure(2, 2)\n",
    },
    {
        "id": "qaoa",
        "name": "QAOA Max-Cut (4-Qubit OpenQASM)",
        "description": "Quantum Approximate Optimization Algorithm for combinatorial graph Max-Cut partition.",
        "source": "OPENQASM 2.0;\ninclude \"qelib1.inc\";\n\nqreg q[4];\ncreg c[4];\n\nh q[0];\nh q[1];\nh q[2];\nh q[3];\n\ncx q[0], q[1];\nrz(0.45) q[1];\ncx q[0], q[1];\n\ncx q[1], q[2];\nrz(0.45) q[2];\ncx q[1], q[2];\n\nrx(0.62) q[0];\nrx(0.62) q[1];\nrx(0.62) q[2];\nrx(0.62) q[3];\n\nmeasure q -> c;\n",
    },
]
