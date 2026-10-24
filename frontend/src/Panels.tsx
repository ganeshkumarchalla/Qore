import { useState } from 'react';
import { Circuit, MetricCards } from './Circuit';
import { Icon } from './Icons';
import { BlochSphereViewer, QasmViewer, StatevectorAmplitudesViewer, UnitaryMatrixViewer } from './QuantumVisuals';
import { QuantumStateWorld } from './QuantumStateWorld';
import { api, formatDate, readable, type Experiment, type ExperimentSummary, type Health, type Optimization, type Simulation } from './types';

export function Empty({ icon, title, children }: { icon: 'lab' | 'forge' | 'research'; title: string; children: React.ReactNode }) {
  return (
    <div className="empty-state">
      <div className="empty-icon-wrap">
        <Icon name={icon} size={28} />
      </div>
      <h3>{title}</h3>
      <p>{children}</p>
    </div>
  );
}

function download(value: unknown, filename: string) {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], { type: 'application/json' }));
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

export function Warnings({ warnings }: { warnings: string[] }) {
  if (warnings.length === 0) return null;
  return (
    <div className="warnings" role="status">
      {warnings.map((warning, i) => (
        <div key={i} className="warning-item">
          <Icon name="info" size={14} />
          <span>{readable(warning)}</span>
        </div>
      ))}
    </div>
  );
}

function KeyValues({ data }: { data: Record<string, unknown> }) {
  return (
    <dl className="key-values">
      {Object.entries(data).map(([key, value]) => (
        <div key={key} className="kv-row">
          <dt>{key.replaceAll('_', ' ')}</dt>
          <dd>{readable(value)}</dd>
        </div>
      ))}
    </dl>
  );
}

export function Lab({ run, historical }: { run: Simulation | null; historical: boolean }) {
  const [subTab, setSubTab] = useState<'world' | 'distribution' | 'bloch' | 'unitary' | 'amplitudes' | 'qasm'>('world');

  if (!run) {
    return (
      <Empty icon="lab" title="No Simulation Results">
        Click <strong>Run Simulation</strong> in the top toolbar to execute this circuit on the local Aer simulator. Observed measurement counts, Bloch vectors, and probabilities will appear here.
      </Empty>
    );
  }

  const allKeys = new Set([...Object.keys(run.counts), ...Object.keys(run.probabilities), ...Object.keys(run.theoretical_probabilities)]);
  if (run.ir.num_clbits <= 5) {
    for (let i = 0; i < 2 ** run.ir.num_clbits; i++) {
      allKeys.add(i.toString(2).padStart(run.ir.num_clbits, '0'));
    }
  }
  const sorted = [...allKeys].sort();
  const keys = sorted.length > 32
    ? [...sorted].sort((a, b) => (run.probabilities[b] ?? 0) - (run.probabilities[a] ?? 0)).slice(0, 32)
    : sorted;

  return (
    <div className="lab-grid">
      <section className="panel distribution">
        <div className="panel-heading">
          <div>
            <span className="eyebrow">SIMULATION OUTPUT</span>
            <h2>Quantum Measurement & State Diagnostics</h2>
          </div>
          <div className="status-pills">
            {run.noise_applied && (
              <span className="pill violet" title="Qiskit Aer depolarizing noise model active">
                <span className="dot" />
                Noise: p={(run.noise_rate ?? 0).toFixed(3)}
              </span>
            )}
            <span className="pill success">
              <span className="dot" />
              {historical ? 'Historical Snapshot' : 'Simulation Complete'}
            </span>
          </div>
        </div>
        <div className="lab-explain-strip">
          <Icon name="info" size={13} />
          <span>Live evidence surface: orbiting nodes show ideal probability, glow shows measured shots, and the readout identifies the selected basis state.</span>
        </div>

        {/* Lab Sub-Tabs */}
        <div className="lab-subtabs-bar">
          <button
            type="button"
            className={`subtab-btn world-tab ${subTab === 'world' ? 'active' : ''}`}
            onClick={() => setSubTab('world')}
          >
            <Icon name="cube" size={14} />
            <span>State World 3D</span>
          </button>
          <button
            type="button"
            className={`subtab-btn ${subTab === 'distribution' ? 'active' : ''}`}
            onClick={() => setSubTab('distribution')}
          >
            <Icon name="lab" size={14} />
            <span>Distribution</span>
          </button>
          <button
            type="button"
            className={`subtab-btn ${subTab === 'bloch' ? 'active' : ''}`}
            onClick={() => setSubTab('bloch')}
          >
            <Icon name="circuit" size={14} />
            <span>Bloch Spheres ({run.bloch_vectors?.length ?? 0})</span>
          </button>
          <button
            type="button"
            className={`subtab-btn ${subTab === 'unitary' ? 'active' : ''}`}
            onClick={() => setSubTab('unitary')}
          >
            <Icon name="code" size={14} />
            <span>Unitary Matrix (U)</span>
          </button>
          <button
            type="button"
            className={`subtab-btn ${subTab === 'amplitudes' ? 'active' : ''}`}
            onClick={() => setSubTab('amplitudes')}
          >
            <Icon name="spark" size={14} />
            <span>Amplitudes</span>
          </button>
          <button
            type="button"
            className={`subtab-btn ${subTab === 'qasm' ? 'active' : ''}`}
            onClick={() => setSubTab('qasm')}
          >
            <Icon name="copy" size={14} />
            <span>OpenQASM</span>
          </button>
        </div>

        {subTab === 'world' && <QuantumStateWorld run={run} />}

        {subTab === 'distribution' && (
          <>
            <div className="chart-legend">
              <span><i className="cyan-dot" />Measured Frequency</span>
              <span><i className="violet-dot" />Theoretical Probability</span>
              <span className="mono">{run.shots.toLocaleString()} shots</span>
            </div>

            <div className="distribution-chart">
              {keys.map((key) => {
                const measProb = (run.probabilities[key] ?? 0) * 100;
                const theoProb = (run.theoretical_probabilities[key] ?? 0) * 100;
                const isDominant = measProb > 0 && measProb === Math.max(...keys.map((k) => (run.probabilities[k] ?? 0) * 100));

                return (
                  <div className={`distribution-row ${isDominant ? 'dominant-state' : ''}`} key={key}>
                    <div className="basis-label-wrap">
                      <span className="basis mono">|{key}⟩</span>
                      {isDominant && <span className="dominant-pill">DOMINANT</span>}
                    </div>
                    <div className="bar-pair">
                      <div className="bar-track" title={`Measured: ${measProb.toFixed(2)}%`}>
                        <div
                          className="bar measured animated-flux-bar"
                          style={{ width: `${measProb}%` }}
                        />
                      </div>
                      <div className="bar-track theoretical-track" title={`Theoretical: ${theoProb.toFixed(2)}%`}>
                        <div
                          className="bar theoretical animated-flux-bar"
                          style={{ width: `${theoProb}%` }}
                        />
                      </div>
                    </div>
                    <span className="bar-value mono">
                      {measProb.toFixed(2)}%
                      <small>{run.counts[key] ?? 0} shots</small>
                    </span>
                  </div>
                );
              })}
            </div>

            {sorted.length > 32 && (
              <p className="help">Showing top 32 frequent outcomes. All {sorted.length} states are in the table below.</p>
            )}

            <div className="chart-scale">
              <span>0%</span>
              <span>25%</span>
              <span>50%</span>
              <span>75%</span>
              <span>100%</span>
            </div>

            <p className="info-line">
              <Icon name="info" size={14} />
              Finite-shot results reflect statistical sampling. Ideal probabilities are computed from statevector simulation.
            </p>

            <details className="details-table">
              <summary>
                <span>Exact Counts & Probabilities</span>
                <span className="count-pill">{sorted.length} states</span>
              </summary>
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>State</th>
                      <th>Counts</th>
                      <th>Measured</th>
                      <th>Ideal</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sorted.map((key) => (
                      <tr key={key}>
                        <td className="mono font-semibold">|{key}⟩</td>
                        <td className="mono">{run.counts[key] ?? 0}</td>
                        <td className="mono">{((run.probabilities[key] ?? 0) * 100).toFixed(3)}%</td>
                        <td className="mono">{((run.theoretical_probabilities[key] ?? 0) * 100).toFixed(3)}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
          </>
        )}

        {subTab === 'bloch' && <BlochSphereViewer vectors={run.bloch_vectors} />}
        {subTab === 'unitary' && <UnitaryMatrixViewer matrix={run.unitary_matrix} />}
        {subTab === 'amplitudes' && <StatevectorAmplitudesViewer amplitudes={run.statevector_amplitudes} />}
        {subTab === 'qasm' && <QasmViewer qasm={run.qasm} />}
      </section>

      <aside className="lab-side">
        <section className="panel">
          <div className="section-head">
            <Icon name="lab" size={16} />
            <h3>Execution Metadata</h3>
          </div>
          <KeyValues
            data={{
              backend: run.backend,
              shots: run.shots,
              seed: run.seed,
              noise_model: run.noise_applied ? `Aer Depolarizing (p=${run.noise_rate})` : 'Ideal (Noiseless)',
              execution_time: `${run.execution_ms.toFixed(2)} ms`,
              timestamp: formatDate(run.created_at),
            }}
          />
          <div className="tvd">
            <span>TOTAL VARIATION DISTANCE (TVD)</span>
            <strong>{run.tvd === null ? 'N/A' : run.tvd.toFixed(6)}</strong>
            <p>Statistical divergence between sampled distribution and ideal reference. 0 indicates perfect match.</p>
          </div>
        </section>

        <section className="panel">
          <div className="section-head">
            <Icon name="circuit" size={16} />
            <h3>Bitstring Convention</h3>
          </div>
          <p className="help preserve-lines">{readable(run.bit_ordering)}</p>
          <p className="help">Classical registers are ordered little-endian: highest bit on left, c[0] on right.</p>
        </section>

        <Warnings warnings={run.warnings ?? []} />
      </aside>

      <section className="panel wide">
        <div className="section-head spread">
          <h3>Reproducibility & Provenance</h3>
          <button className="button secondary small" onClick={() => download(run, `qore-simulation-${run.id}.json`)}>
            <Icon name="save" size={14} /> Export JSON
          </button>
        </div>
        <div className="provenance-inline">
          <span>Run ID: <code>{run.id}</code></span>
          <span>Source SHA-256: <code>{run.source_hash.slice(0, 16)}...</code></span>
        </div>
        <details>
          <summary>Framework Versions & Definition</summary>
          <KeyValues data={run.versions} />
          <MetricCards metrics={run.metrics} />
          <p className="help">{readable(run.metrics.definition)}</p>
        </details>
      </section>
    </div>
  );
}

export function Forge({
  run,
  historical,
  onApprove,
  busy,
}: {
  run: Optimization | null;
  historical: boolean;
  onApprove: () => void;
  busy: boolean;
}) {
  if (!run) {
    return (
      <Empty icon="forge" title="No Optimization Candidate">
        Click <strong>Optimize</strong> in the toolbar to transpile the circuit through Qiskit compiler passes and compare candidate improvements against the original.
      </Empty>
    );
  }

  const improved = Object.values(run.differences).some((value) => value.absolute < 0);
  const statusText = {
    validated: 'Semantically Validated',
    failed: 'Validation Failed',
    unavailable: 'Validation Unavailable',
    inconclusive: 'Validation Inconclusive',
  }[run.validation.status];

  return (
    <div className="forge-layout">
      <div className="comparison-title">
        <div>
          <span className="eyebrow">COMPILER PASSES</span>
          <h2>Circuit Optimization & Equivalence</h2>
          <p className="help">
            {historical ? 'Inspecting preserved candidate.' : 'Original source remains unchanged.'}{' '}
            {improved ? 'Resource reductions detected below.' : 'No gate count reduction achieved with current optimization settings.'}
          </p>
        </div>
        <button className="button primary" disabled={busy || run.validation.status === 'failed'} onClick={onApprove}>
          <Icon name="check" size={15} /> Apply Candidate to Editor
        </button>
      </div>

      <div className="comparison-grid">
        {(['original', 'candidate'] as const).map((key) => (
          <section className={`panel comparison-circuit ${key}`} key={key}>
            <div className="section-head spread">
              <h3>
                <span className={`little-square ${key}`} />
                {key === 'original' ? 'Original Circuit' : 'Candidate Circuit'}
              </h3>
              <span className="mini-tag">{key === 'original' ? 'BASELINE' : 'OPTIMIZED'}</span>
            </div>
            <Circuit ir={run[key].ir} compact />
            <MetricCards metrics={run[key].metrics} />
            <details>
              <summary>Gate Type Distribution</summary>
              <KeyValues data={run[key].metrics.gate_types} />
            </details>
          </section>
        ))}
      </div>

      <div className="forge-evidence">
        <section className="panel">
          <div className="section-head">
            <Icon name="circuit" size={16} />
            <h3>Resource Metrics Comparison</h3>
          </div>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Metric</th>
                  <th>Original</th>
                  <th>Candidate</th>
                  <th>Delta</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(run.differences).map(([key, value]) => (
                  <tr key={key}>
                    <td className="capitalize">{key.replaceAll('_', ' ')}</td>
                    <td className="mono">{value.original}</td>
                    <td className="mono">{value.candidate}</td>
                    <td className={`mono font-semibold ${value.absolute < 0 ? 'positive-text' : value.absolute > 0 ? 'warning-text' : 'muted'}`}>
                      {value.absolute > 0 ? '+' : ''}
                      {value.absolute}
                      <span className="delta-percent">
                        {value.relative_percent === null ? '' : ` (${value.relative_percent > 0 ? '+' : ''}${value.relative_percent.toFixed(1)}%)`}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="help metric-definition">{readable(run.original.metrics.definition)}</p>
        </section>

        <section className="panel verification">
          <div className="section-head">
            <Icon name="check" size={16} />
            <h3>Equivalence Verification</h3>
          </div>
          <span className={`validation ${run.validation.status}`}>
            <Icon name={run.validation.status === 'validated' ? 'check' : 'info'} size={15} />
            {statusText}
          </span>
          <p className="verification-method">{run.validation.method}</p>
          <p className="help">{readable(run.validation.details)}</p>
          <details>
            <summary>Quantitative Details</summary>
            <pre className="json-block">{JSON.stringify(run.validation, null, 2)}</pre>
          </details>
        </section>
      </div>

      <section className="panel">
        <div className="section-head spread">
          <h3>Transpiler Configuration & Candidate Source</h3>
          <button className="button secondary small" onClick={() => download(run, `qore-optimization-${run.id}.json`)}>
            <Icon name="save" size={14} /> Export Optimization JSON
          </button>
        </div>
        <p className="help preserve-lines">{Array.isArray(run.explanation) ? run.explanation.join('\n') : run.explanation}</p>
        <details>
          <summary>Pass Settings & Versions</summary>
          <KeyValues data={{ ...run.settings, run_id: run.id, source_hash: run.source_hash, ...run.versions }} />
        </details>
        <details>
          <summary>Inspect Candidate Python Code</summary>
          <pre className="source-preview">{run.candidate.source}</pre>
        </details>
        <Warnings warnings={run.warnings ?? []} />
      </section>
    </div>
  );
}

export function Research({
  experiments,
  selected,
  onOpen,
  onSelect,
  onRestore,
  busy,
}: {
  experiments: ExperimentSummary[];
  selected: Experiment | null;
  onOpen: (id: string) => void;
  onSelect?: (id: string) => void;
  onRestore?: (id: string) => void;
  busy: boolean;
}) {
  return (
    <div className="research-layout">
      <section className="panel">
        <div className="panel-heading">
          <div>
            <span className="eyebrow">REPRODUCIBILITY LEDGER</span>
            <h2>Saved Experiments</h2>
          </div>
          <span className="count-badge">{experiments.length}</span>
        </div>
        {experiments.length === 0 ? (
          <Empty icon="research" title="No Saved Experiments">
            Run a simulation or optimization, then click <strong>Save Experiment</strong> in the toolbar to record an immutable snapshot in SQLite.
          </Empty>
        ) : (
          <div className="experiment-list">
            {experiments.map((item) => (
              <div
                key={item.id}
                className={`experiment-item ${selected?.id === item.id ? 'selected' : ''}`}
                onClick={() => (onSelect ? onSelect(item.id) : onOpen(item.id))}
                role="button"
                tabIndex={0}
              >
                <span className="experiment-icon">
                  <Icon name="research" size={16} />
                </span>
                <span className="experiment-info">
                  <strong>{item.name}</strong>
                  <small>{formatDate(item.created_at)} · {item.source_hash.slice(0, 10)}</small>
                </span>
                <button
                  type="button"
                  className="reopen-badge"
                  disabled={busy}
                  onClick={(e) => {
                    e.stopPropagation();
                    onOpen(item.id);
                  }}
                  title="Open snapshot in Studio editor"
                >
                  Open in Studio <Icon name="arrow" size={12} />
                </button>
              </div>
            ))}
          </div>
        )}
      </section>

      {selected ? (
        <section className="panel provenance-panel">
          <div className="section-head spread">
            <h3>Snapshot Provenance</h3>
            <span className="pill violet">Historical Snapshot</span>
          </div>
          <h2>{selected.name}</h2>
          <KeyValues
            data={{
              experiment_id: selected.id,
              saved_at: formatDate(selected.created_at),
              project_id: selected.project_id ?? 'Unlinked draft',
              source_sha256: selected.source_hash,
              ir_version: selected.ir_version,
              simulation_run: selected.simulation?.id ?? 'None',
              optimization_run: selected.optimization?.id ?? 'None',
              ...selected.versions,
            }}
          />
          <p className="help">
            This snapshot preserves the exact source code, circuit representation, and execution metrics as recorded at runtime.
          </p>

          <div className="provenance-actions">
            <button
              type="button"
              className="button primary small"
              disabled={busy}
              onClick={() => onOpen(selected.id)}
            >
              <Icon name="code" size={14} />
              <span>Open in Studio Editor</span>
            </button>
            {onRestore && (
              <button
                type="button"
                className="button secondary small"
                disabled={busy}
                onClick={() => onRestore(selected.id)}
              >
                <Icon name="circuit" size={14} />
                <span>Copy to Editable Draft</span>
              </button>
            )}
            <button
              type="button"
              className="button secondary small"
              onClick={() => download(selected, `qore-experiment-${selected.id}.json`)}
            >
              <Icon name="save" size={14} />
              <span>Export Snapshot JSON</span>
            </button>
          </div>
        </section>
      ) : (
        <section className="panel provenance-panel">
          <span className="eyebrow">REPRODUCIBILITY GUARANTEE</span>
          <h2>Deterministic Record Tracking</h2>
          <div className="research-principles">
            <p><Icon name="code" size={16} /> Exact Python source code & SHA-256 hash</p>
            <p><Icon name="lab" size={16} /> Simulator backend, shots, and seed configuration</p>
            <p><Icon name="forge" size={16} /> Original and candidate compiler passes</p>
            <p><Icon name="check" size={16} /> Semantic equivalence verification evidence</p>
          </div>
          <p className="help">Select any saved snapshot on the left to inspect its historical data.</p>
        </section>
      )}
    </div>
  );
}

export function Intelligence({
  source,
  simulation,
  optimization,
  health,
}: {
  source: string;
  simulation: Simulation | null;
  optimization: Optimization | null;
  health: Health | null;
}) {
  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState('');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const [model, setModel] = useState('');
  const [available, setAvailable] = useState<boolean | null>(null);

  async function ask(text = question) {
    if (!text.trim() || pending) return;
    setQuestion(text);
    setPending(true);
    setError('');
    setAnswer('');
    try {
      const data = await api<{ available: boolean; answer: string; model?: string }>('/assistant', {
        question: text,
        source,
        simulation_id: simulation?.id,
        optimization_id: optimization?.id,
      });
      setAnswer(data.answer);
      setModel(data.model ?? '');
      setAvailable(data.available);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="intelligence-layout">
      <section className="panel assistant">
        <div className="panel-heading">
          <div>
            <span className="eyebrow">QUANTUM COPILOT</span>
            <h2>Grounded AI Assistant</h2>
          </div>
          <span className={`pill ${health?.ai_available ? 'success' : ''}`}>
            <span className="dot" />
            {health?.ai_available ? 'AI Provider Configured' : 'AI Offline (Optional)'}
          </span>
        </div>

        <p className="help">
          The assistant analyzes your active circuit, simulation measurements, and compiler transformations. It operates with strictly read-only context.
        </p>

        <div className="context-chips">
          <span><Icon name="code" size={13} /> Active Source ({source.split('\n').length} lines)</span>
          <span><Icon name="lab" size={13} /> {simulation ? `Simulation (${simulation.shots} shots)` : 'No simulation'}</span>
          <span><Icon name="forge" size={13} /> {optimization ? 'Optimization candidate' : 'No optimization'}</span>
        </div>

        <div className="prompt-options">
          {['Explain this quantum circuit', 'Interpret measurement probabilities', 'Explain compiler optimization differences'].map((text) => (
            <button key={text} disabled={pending} onClick={() => ask(text)}>
              {text} <Icon name="arrow" size={12} />
            </button>
          ))}
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            void ask();
          }}
        >
          <label htmlFor="assistant-question">Ask a question</label>
          <textarea
            id="assistant-question"
            value={question}
            maxLength={4000}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="e.g. Why does this circuit produce entanglement between qubits 0 and 1?"
            rows={3}
          />
          <div className="assistant-action">
            <span className="tiny muted">Responses are advisory and require human review.</span>
            <button className="button primary small" type="submit" disabled={pending || !question.trim()}>
              {pending ? <span className="spinner" /> : <Icon name="spark" size={14} />}
              {pending ? 'Thinking…' : 'Ask Copilot'}
            </button>
          </div>
        </form>

        {error && <div className="error-box" role="alert">{error}</div>}

        {answer && (
          <div className="assistant-answer">
            <div className="section-head">
              <Icon name="spark" size={15} />
              <h3>{available ? 'Copilot Response' : 'Service Notice'}</h3>
              {model && <span className="mini-tag">{model}</span>}
            </div>
            <p className="preserve-lines">{answer}</p>
          </div>
        )}
      </section>

      <section className="panel assistant-note">
        <Icon name="spark" size={24} />
        <h3>Optional Capability</h3>
        <p className="help">
          All core quantum workflows (Monaco editing, QORE-IR visualization, Aer local simulation, compiler optimization, and SQLite provenance) run entirely locally without requiring an API key.
        </p>
        <p className="help">
          To enable Gemini assistance, set <code>GEMINI_API_KEY</code> on your local server.
        </p>
      </section>
    </div>
  );
}
