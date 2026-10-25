import { useEffect, useRef, useState } from 'react';
import { ErrorBoundary } from './ErrorBoundary';
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

interface AssistantContext {
  source: string;
  simulation: Simulation | null;
  optimization: Optimization | null;
  health: Health | null;
  fileName?: string;
  historical?: boolean;
}

export function Intelligence({ source, simulation, optimization, health, fileName, historical }: AssistantContext) {
  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState('');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const [model, setModel] = useState('');
  const [available, setAvailable] = useState<boolean | null>(null);
  const generation = useRef(0);
  const ready = Boolean(health?.ai_available && source.trim());

  useEffect(() => {
    generation.current += 1;
    setAnswer(''); setError(''); setModel(''); setAvailable(null); setPending(false);
    return () => { generation.current += 1; };
  }, [source, simulation?.id, optimization?.id]);

  async function ask(text = question) {
    if (!text.trim() || pending || !ready) return;
    const requestGeneration = generation.current;
    setQuestion(text);
    setPending(true); setError(''); setAnswer('');
    try {
      const data = await api<{ available: boolean; answer: string; model?: string }>('/assistant', {
        question: text.trim(),
        source,
        simulation_id: simulation?.id,
        optimization_id: optimization?.id,
      });
      if (generation.current !== requestGeneration) return;
      setAnswer(data.answer);
      setModel(data.model ?? '');
      setAvailable(data.available);
    } catch (reason) {
      if (generation.current === requestGeneration) setError(reason instanceof Error ? reason.message : 'The assistant could not respond. Please try again.');
    } finally {
      if (generation.current === requestGeneration) setPending(false);
    }
  }

  const prompts = [
    { text: 'Explain this circuit', question: 'Explain this quantum circuit', enabled: true },
    { text: 'Interpret the results', question: 'Interpret measurement probabilities', enabled: Boolean(simulation) },
    { text: 'Review the optimization', question: 'Explain compiler optimization differences', enabled: Boolean(optimization) },
  ];

  return <div className="intelligence-layout">
    <section className="panel assistant">
      <div className="qore-assistant-availability">
        <span className={'pill ' + (health?.ai_available ? 'success' : '')}>
          <span className="dot" />{health ? health.ai_available ? 'Assistant available' : 'Assistant unavailable' : 'Checking availability'}
        </span>
        <span className="qore-assistant-readonly"><Icon name="code" size={12} />Read-only</span>
      </div>
      <p className="help">Explore your circuit and understand its results while keeping your workspace in view. The assistant can explain context; it cannot edit or run your code.</p>
      <div className="qore-assistant-context">
        <div><Icon name={historical ? 'clock' : 'file'} size={14} /><strong>{fileName || 'No circuit open'}</strong></div>
        <span>{historical ? 'Historical snapshot · read-only source' : source.trim() ? 'Active editor · ' + source.split('\n').length + ' lines' : 'Open or create a circuit to begin.'}</span>
      </div>
      <div className="context-chips">
        <span><Icon name="lab" size={13} />{simulation ? simulation.shots.toLocaleString() + ' shots' : 'No simulation'}</span>
        <span><Icon name="forge" size={13} />{optimization ? 'Optimization attached' : 'No optimization'}</span>
      </div>
      {health && !health.ai_available && <p className="qore-assistant-service-note" role="status">AI assistance is currently unavailable. Your circuit editor, Lab, and Forge remain available.</p>}
      <div className="prompt-options" aria-label="Suggested questions">
        {prompts.map(prompt => <button key={prompt.text} type="button"
          disabled={pending || !ready || !prompt.enabled} onClick={() => void ask(prompt.question)}>
          {prompt.text}<Icon name="arrow" size={12} />
        </button>)}
      </div>
      <form onSubmit={event => { event.preventDefault(); void ask(); }}>
        <label htmlFor="assistant-question">Ask about your circuit</label>
        <textarea id="assistant-question" value={question} maxLength={4000}
          onChange={event => setQuestion(event.target.value)} rows={4} disabled={pending || !ready}
          placeholder={source.trim() ? 'What does each operation do, and how should I interpret the output?' : 'Open a circuit to ask a question…'}
          aria-describedby="qore-assistant-review" />
        <div className="assistant-action">
          <span id="qore-assistant-review" className="tiny muted">Review explanations against your measured results.</span>
          <button className="button primary small" type="submit" disabled={pending || !ready || !question.trim()}>
            {pending ? <span className="spinner" /> : <Icon name="spark" size={14} />}
            {pending ? 'Thinking…' : 'Ask assistant'}
          </button>
        </div>
      </form>
      {pending && <p className="help" role="status">Reading the attached circuit context…</p>}
      {error && <div className="error-box" role="alert">{error}</div>}
      {answer && <div className="assistant-answer" role="status">
        <div className="section-head"><Icon name="spark" size={15} /><h3>{available ? 'Assistant response' : 'Service notice'}</h3></div>
        {model && <span className="mini-tag">{model}</span>}
        <p className="preserve-lines">{answer}</p>
      </div>}
    </section>
    <p className="qore-assistant-footnote"><Icon name="info" size={13} />Only the active circuit and attached run context accompany your question.</p>
  </div>;
}

export function AssistantSidebar({ isOpen, onClose, contextId, ...context }: AssistantContext & {
  isOpen: boolean;
  onClose: () => void;
  contextId: string;
}) {
  const [overlay, setOverlay] = useState(() => window.matchMedia('(max-width: 1100px)').matches);
  const panel = useRef<HTMLElement>(null);
  const closeCallback = useRef(onClose);
  closeCallback.current = onClose;

  useEffect(() => {
    const media = window.matchMedia('(max-width: 1100px)');
    const update = () => setOverlay(media.matches);
    media.addEventListener('change', update);
    return () => media.removeEventListener('change', update);
  }, []);

  useEffect(() => {
    if (!isOpen) return;
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const frame = requestAnimationFrame(() => panel.current?.querySelector<HTMLButtonElement>('.qore-assistant-close')?.focus());
    const onKey = (event: KeyboardEvent) => {
      const root = panel.current;
      if (!root) return;
      // Other dialogs keep their own Escape handling when opened above this panel.
      const focusInside = root.contains(document.activeElement);
      if (event.key === 'Escape' && focusInside) {
        event.preventDefault(); event.stopPropagation(); closeCallback.current();
      }
      if (!overlay || event.key !== 'Tab') return;
      if (document.querySelector('.modal-overlay')) return;
      const controls = Array.from(root.querySelectorAll<HTMLElement>('button:not([disabled]), textarea:not([disabled]), a[href], [tabindex="0"]'))
        .filter(element => element.offsetParent !== null);
      const first = controls[0], last = controls[controls.length - 1];
      if (!first) { event.preventDefault(); root.focus(); return; }
      if (event.shiftKey && (document.activeElement === first || !focusInside)) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && (document.activeElement === last || !focusInside)) { event.preventDefault(); first.focus(); }
    };
    document.addEventListener('keydown', onKey, true);
    return () => {
      cancelAnimationFrame(frame);
      document.removeEventListener('keydown', onKey, true);
      if (panel.current?.contains(document.activeElement) || document.activeElement === document.body) {
        if (previous?.isConnected) previous.focus();
        else document.getElementById('qore-assistant-toggle')?.focus();
      }
    };
  }, [isOpen, overlay]);

  if (!isOpen) return null;
  return <>
    {overlay && <button type="button" className="qore-assistant-backdrop" tabIndex={-1} aria-label="Close assistant sidebar" onClick={onClose} />}
    <aside ref={panel} id="qore-assistant-sidebar" className="qore-assistant-sidebar" tabIndex={-1}
      role={overlay ? 'dialog' : 'complementary'} aria-modal={overlay || undefined} aria-labelledby="qore-assistant-title">
      <header className="qore-assistant-header">
        <div className="qore-assistant-heading"><span className="qore-assistant-symbol"><Icon name="spark" size={18} /></span>
          <div><span>QORE INTELLIGENCE</span><h2 id="qore-assistant-title">Assistant</h2></div>
        </div>
        <button type="button" className="qore-assistant-close topbar-util-btn" aria-label="Close assistant sidebar" title="Close assistant (Escape)" onClick={onClose}><Icon name="close" size={14} /></button>
      </header>
      <div className="qore-assistant-scroll">
        <ErrorBoundary label="QORE assistant" key={contextId}>
          <Intelligence key={contextId} {...context} />
        </ErrorBoundary>
      </div>
    </aside>
  </>;
}
