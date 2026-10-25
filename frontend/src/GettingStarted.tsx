import { Icon } from './Icons';

interface GettingStartedProps {
  busy: boolean;
  onGetStarted: () => void;
  onCreateBlank: () => void;
}

export function GettingStarted({ busy, onGetStarted, onCreateBlank }: GettingStartedProps) {
  return (
    <section className="workspace-start" aria-labelledby="workspace-start-title">
      <div className="workspace-start-inner">
        <span className="workspace-start-kicker">QORE · QUANTUM STUDIO</span>
        <h1 id="workspace-start-title">A clear start.<br />A world to explore.</h1>
        <p className="workspace-start-lead">Your workspace is yours to build. Start with a simple three-qubit circuit, or open a blank file and write your own.</p>
        <div className="workspace-start-actions">
          <button type="button" className="button primary" onClick={onGetStarted} disabled={busy}>
            <Icon name="play" size={16} /> Get Started
          </button>
          <button type="button" className="button secondary" onClick={onCreateBlank} disabled={busy}>
            <Icon name="filePlus" size={16} /> Create blank file
          </button>
        </div>
        <div className="workspace-first-circuit">
          <div className="workspace-first-mark"><Icon name="circuit" size={22} /></div>
          <div><h2>Meet your first three qubits</h2><p>Get Started creates one editable GHZ circuit. Run it in Lab to discover the paired outcomes <code>000</code> and <code>111</code>, then inspect the state and keep your results.</p></div>
          <span className="workspace-three-qubit-badge">3 QUBITS</span>
        </div>
        <ol className="workspace-start-steps">
          <li><span>01</span><div><strong>Write</strong><p>Edit your circuit and see its gates.</p></div></li>
          <li><span>02</span><div><strong>Explore</strong><p>Run a simulation and inspect each outcome.</p></div></li>
          <li><span>03</span><div><strong>Verify</strong><p>Compare transformations and save evidence.</p></div></li>
        </ol>
        <p className="workspace-start-note">No files are added until you choose an action. Existing files remain available in Explorer.</p>
      </div>
    </section>
  );
}
