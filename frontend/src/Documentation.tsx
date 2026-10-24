import { useState } from 'react';
import { Icon } from './Icons';

type Topic = 'overview' | 'lab' | 'ledger';

const sections: { id: Topic; label: string; eyebrow: string }[] = [
  { id: 'overview', label: 'About Quantum Studio', eyebrow: 'FOUNDATIONS' },
  { id: 'lab', label: 'Quantum Lab', eyebrow: 'BUILD & SIMULATE' },
  { id: 'ledger', label: 'Quantum Ledger', eyebrow: 'TRACE & LEARN' },
];

export function Documentation({ initialTopic = 'overview' }: { initialTopic?: Topic }) {
  const [topic, setTopic] = useState<Topic>(initialTopic);
  return <div className="documentation-view">
    <header className="documentation-hero">
      <span className="eyebrow">QORE DOCUMENTATION</span>
      <h1>Quantum computing, made tangible.</h1>
      <p>Use QORE to write circuits, simulate quantum behavior, inspect evidence, and build intuition from the first qubit to production-grade experiments.</p>
    </header>
    <nav className="documentation-nav" aria-label="Documentation sections">
      {sections.map((section) => <button key={section.id} className={topic === section.id ? 'active' : ''} onClick={() => setTopic(section.id)} type="button"><span>{section.eyebrow}</span>{section.label}</button>)}
    </nav>
    <main className="documentation-content">
      {topic === 'overview' && <>
        <section className="documentation-section"><span className="eyebrow">ABOUT QUANTUM</span><h2>What is a quantum computer?</h2><p>Quantum computers use qubits, superposition, interference, and entanglement to represent and transform probability amplitudes. They are not faster for every task; they are specialized machines for problems where quantum structure can be exploited.</p><div className="documentation-grid"><article><h3>Qubits</h3><p>A qubit can be measured as 0 or 1, while its state before measurement is described by amplitudes. The Bloch sphere in QORE makes that state visible.</p></article><article><h3>Gates & circuits</h3><p>Gates are reversible transformations. Compose them into circuits, measure the result, and compare sampled outcomes with the ideal statevector.</p></article><article><h3>Entanglement</h3><p>Entangled qubits share correlations that cannot be explained as independent classical bits. QORE exposes these relationships in the State World and Bloch views.</p></article></div></section>
        <section className="documentation-section"><span className="eyebrow">WHY IT MATTERS</span><h2>Quantum in the next era</h2><p>Today, simulation is the safest way to learn algorithms, validate circuit logic, and prepare for hardware constraints. QORE supports that journey with reproducible runs, transparent metrics, and an editable workspace.</p><div className="documentation-callout"><strong>Use QORE when you need to:</strong><span>teach quantum concepts visually</span><span>prototype Qiskit circuits</span><span>compare ideal and measured distributions</span><span>keep experiment history auditable</span></div></section>
      </>}
      {topic === 'lab' && <section className="documentation-section"><span className="eyebrow">QUANTUM LAB</span><h2>From Python to evidence</h2><ol className="documentation-steps"><li><strong>Open or create a project.</strong><span>Use Explorer to edit a Python circuit just like a familiar code workspace.</span></li><li><strong>Define qubits and gates with Qiskit.</strong><span>Build a <code>QuantumCircuit</code>, apply gates such as H, X, CX, and add measurements.</span></li><li><strong>Run the simulator.</strong><span>QORE executes locally with Qiskit Aer, using configurable shots, seed, optimization level, and optional noise.</span></li><li><strong>Read the result.</strong><span>Inspect counts, probabilities, Bloch spheres, State World motion, amplitudes, unitary matrices, and OpenQASM.</span></li><li><strong>Export and reproduce.</strong><span>Execution metadata, TVD, source hash, and framework versions make each run traceable.</span></li></ol><div className="documentation-code"><code>from qiskit import QuantumCircuit<br />qc = QuantumCircuit(2, 2)<br />qc.h(0); qc.cx(0, 1)<br />qc.measure_all()</code></div></section>}
      {topic === 'ledger' && <section className="documentation-section"><span className="eyebrow">QUANTUM LEDGER</span><h2>Understand every run</h2><p>The Ledger is QORE’s evidence trail for experiments. It helps you compare historical snapshots, revisit source code, and understand how a circuit changed over time.</p><div className="documentation-grid"><article><h3>Reproducibility</h3><p>Record backend, shots, seed, noise model, execution time, timestamp, and source fingerprint for every simulation.</p></article><article><h3>Validation</h3><p>Use total variation distance and distribution comparisons to see whether sampled results agree with the ideal reference.</p></article><article><h3>Support</h3><p>When something fails, inspect the terminal output, warnings, file path, and preserved run context before changing the circuit.</p></article></div><p className="documentation-note"><Icon name="info" size={14} /> QORE is a learning and prototyping environment. Hardware availability, runtime, and results can differ on real quantum systems.</p></section>}
    </main>
  </div>;
}
