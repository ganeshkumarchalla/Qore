import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Icon } from './Icons';
import { api, type Parsed, type Simulation, type Optimization, type Health, type QuantumCapabilities, type UnitaryCell } from './types';
import type { WorkspaceFile } from './Explorer';

export interface WorkspaceProblem {
  id: string;
  severity: 'error' | 'warning' | 'info';
  file: string;
  line: number;
  col: number;
  message: string;
  code: string;
}

export interface TerminalProps {
  isOpen: boolean;
  onClose: () => void;
  onRunSimulation: () => void;
  onRunTranspile: () => void;
  onRunParse: () => void;
  parsed: Parsed | null;
  simulation: Simulation | null;
  optimization: Optimization | null;
  health: Health | null;
  busy: string;
  source?: string;
  fileName?: string;
  error?: string;
  onSelectProblemLine?: (line: number) => void;
  workspaceFiles?: WorkspaceFile[];
}

interface LogEntry {
  id: string;
  type: 'cmd' | 'info' | 'success' | 'warn' | 'error' | 'output';
  text: string;
  time: string;
}

const ALL_COMMANDS = [
  'help', 'qiskit --version', 'qiskit run', 'qiskit transpile', 'qiskit backends',
  'qiskit validate', 'qiskit draw', 'qiskit statevector', 'qiskit unitary', 'qiskit metrics',
  'qiskit qasm', 'qiskit bloch', 'qiskit purity', 'qiskit ideal', 'qiskit bitorder',
  'qiskit noise', 'qiskit result', 'qiskit source-hash', 'qiskit capabilities',
  'qiskit gates', 'qiskit modules', 'qiskit methods', 'qiskit limits', 'qiskit forge',
  'run', 'simulate', 'parse', 'validate', 'transpile', 'metrics', 'statevector', 'unitary', 'probs',
  'ideal', 'counts', 'qasm', 'bloch', 'purity', 'bitorder', 'noise', 'result', 'source-hash',
  'capabilities', 'gates', 'modules', 'methods', 'limits', 'ast', 'status', 'ls', 'tree', 'cat', 'head', 'wc', 'pwd', 'date', 'clear', 'echo',
];

function redact(text: string): string {
  return text
    .replace(/\bBearer\s+[^\s"']+/gi, 'Bearer [REDACTED]')
    .replace(/\b(?:AIza[\w-]{20,}|sk-[\w-]{20,}|sb_secret_[\w-]+)\b/g, '[REDACTED]')
    .replace(/((?:password|api[_-]?key|access[_-]?token|refresh[_-]?token)\s*[=:]\s*)["']?[^\s,"']+/gi, '$1[REDACTED]');
}

function complex(value: Pick<UnitaryCell, 'real' | 'imag'>): string {
  const real = Math.abs(value.real) < 1e-10 ? 0 : value.real;
  const imag = Math.abs(value.imag) < 1e-10 ? 0 : value.imag;
  return real.toFixed(6) + (imag < 0 ? ' - ' : ' + ') + Math.abs(imag).toFixed(6) + 'i';
}

function versionSummary(versions?: Record<string, string>): string {
  return versions && Object.keys(versions).length
    ? Object.entries(versions).map(([name, value]) => '  ' + name + ': ' + value).join('\n')
    : '  Version information has not been reported by the server.';
}

function analyzeWorkspaceProblems(fileName?: string, error?: string, warnings?: string[]): WorkspaceProblem[] {
  const problems: WorkspaceProblem[] = [];
  if (error) {
    const location = error.match(/line\s*(\d+)/i) ?? error.match(/:\s*(\d+):/);
    problems.push({ id: 'execution-error', severity: 'error', file: fileName ?? 'Active buffer',
      line: location ? Math.max(1, Number(location[1])) : 1, col: 1,
      message: redact(error), code: 'BACKEND' });
  }
  warnings?.forEach((warning, index) => problems.push({ id: 'warning-' + index, severity: 'warning',
    file: fileName ?? 'Active buffer', line: 1, col: 1, message: redact(warning), code: 'PARSER' }));
  return problems;
}

export function Terminal({ isOpen, onClose, onRunSimulation, onRunTranspile, onRunParse, parsed, simulation,
  optimization, health, busy, source, fileName, error, onSelectProblemLine, workspaceFiles = [] }: TerminalProps) {
  const [activeTab, setActiveTab] = useState<'terminal' | 'output' | 'problems' | 'debug'>('terminal');
  const [inputVal, setInputVal] = useState('');
  const [isMaximized, setIsMaximized] = useState(false);
  const [cmdHistory, setCmdHistory] = useState<string[]>([]);
  const [historyIndex, setHistoryIndex] = useState(-1);
  const [logs, setLogs] = useState<LogEntry[]>(() => [{ id: 'welcome', type: 'info',
    text: 'QORE command console. Type help for supported commands. Run commands use your active file and current settings.',
    time: new Date().toLocaleTimeString() }]);
  const terminalEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const workspaceProblems = useMemo(() => analyzeWorkspaceProblems(fileName, error, parsed?.warnings),
    [fileName, error, parsed?.warnings]);
  const hasErrors = workspaceProblems.some(problem => problem.severity === 'error');

  const addLog = (type: LogEntry['type'], text: string) => setLogs(previous => [...previous.slice(-499), {
    id: Date.now() + '-' + Math.random().toString(36).slice(2, 8), type, text: redact(text), time: new Date().toLocaleTimeString(),
  }]);

  useEffect(() => {
    terminalEndRef.current?.scrollIntoView({ behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' });
  }, [logs, activeTab]);
  useEffect(() => {
    if (!isOpen || activeTab !== 'terminal') return;
    const timer = window.setTimeout(() => inputRef.current?.focus(), 50);
    return () => window.clearTimeout(timer);
  }, [isOpen, activeTab]);
  useEffect(() => { if (busy) addLog('info', busy + ' in progress…'); }, [busy]);
  useEffect(() => { if (error) addLog('error', (fileName ?? 'Active buffer') + ': ' + error); }, [error]);
  useEffect(() => {
    if (!simulation) return;
    addLog('success', 'Simulation complete: ' + simulation.backend + '; ' + simulation.shots + ' shots; ' + simulation.execution_ms.toFixed(2) + ' ms.');
    const top = Object.entries(simulation.probabilities).sort((a, b) => b[1] - a[1])[0];
    if (top) addLog('output', 'Most frequent measured state |' + top[0] + '⟩: ' + (top[1] * 100).toFixed(2) + '%.');
  }, [simulation]);
  useEffect(() => {
    if (!optimization) return;
    addLog('success', 'Optimization complete: ' + optimization.original.metrics.gate_count + ' → ' + optimization.candidate.metrics.gate_count + ' gates; depth ' + optimization.candidate.metrics.depth + '. Validation: ' + optimization.validation.status + '.');
  }, [optimization]);

  const result = simulation ?? parsed;
  const output = simulation
    ? JSON.stringify({ backend: simulation.backend, shots: simulation.shots, seed: simulation.seed,
      execution_ms: simulation.execution_ms, counts: simulation.counts, tvd: simulation.tvd,
      created_at: simulation.created_at, warnings: simulation.warnings }, null, 2)
    : optimization ? JSON.stringify({ validation: optimization.validation, differences: optimization.differences,
      settings: optimization.settings, warnings: optimization.warnings }, null, 2)
    : error ?? 'No execution result yet. Run a circuit to see its actual output.';
  const debug = JSON.stringify({ active_file: fileName ?? null, source_characters: source?.length ?? 0,
    server_status: health?.status ?? 'unavailable', versions: health?.versions ?? {},
    ai_available: health?.ai_available ?? null, limits: health?.limits ?? {},
    parsed_ir_version: parsed?.ir.version ?? null, source_hash: parsed?.source_hash ?? null,
    simulation_id: simulation?.id ?? null, optimization_id: optimization?.id ?? null,
    bit_ordering: simulation?.bit_ordering ?? null, simulation_method: simulation?.simulation_method ?? null,
  }, null, 2);

  const handleCommandSubmit = async (commandText: string) => {
    const raw = commandText.trim();
    if (!raw) return;
    addLog('cmd', 'qore › ' + raw);
    // History is bounded and redacted just like visible output.
    setCmdHistory(previous => [redact(raw), ...previous].slice(0, 100));
    setHistoryIndex(-1); setInputVal('');
    const parts = raw.split(/\s+/);
    let command = parts[0].toLowerCase();
    const args = parts.slice(1);
    if (command === 'az' || command === 'qsharp') {
      addLog('warn', (command === 'az' ? 'Azure Quantum CLI' : 'Q#') + ' is not connected to this command console. No cloud job or compiler command was executed.');
      return;
    }
    if (command === 'qiskit') { command = (args.shift() ?? '--version').toLowerCase(); }
    const aliases: Record<string, string> = { simulate: 'run', opt: 'transpile', optimize: 'transpile', forge: 'transpile',
      validate: 'parse', circuit: 'draw', ir: 'ast', targets: 'backends', version: '--version', '-v': '--version',
      env: 'capabilities', dir: 'ls', cls: 'clear', '?': 'help' };
    command = aliases[command] ?? command;
    if (args.length && !['cat', 'head', 'wc', 'echo'].includes(command)) {
      addLog('warn', 'This command takes no arguments. Simulation and optimization use the settings selected in the workspace.');
      return;
    }
    switch (command) {
      case 'help':
        addLog('output', [
          'QORE command console',
          '  run, qiskit run       Simulate the active circuit using current settings',
          '  parse, qiskit validate Validate and parse active source without sampling',
          '  transpile            Optimize the active circuit using current settings',
          '  qiskit --version     Show server-reported package versions',
          '  qiskit backends      Show the last run backend and available engine limits',
          '  qiskit draw          List actual parsed circuit operations',
          '  qiskit qasm          Show backend-generated OpenQASM 2.0',
          '  qiskit bloch         Show per-qubit Bloch vectors and purity',
          '  qiskit ideal         Show ideal measurement probabilities',
          '  qiskit bitorder      Explain the recorded classical mapping',
          '  qiskit noise         Show the applied simulator noise configuration',
          '  qiskit result        Summarize source-matched parse/run/Forge evidence',
          '  qiskit capabilities  Query executable languages and workflows',
          '  qiskit gates/modules/methods/limits  Query the server runtime contract',
          '  metrics              Show parsed circuit metrics',
          '  statevector          Show actual complex state amplitudes, when available',
          '  unitary              Show the actual circuit operator, when available',
          '  probs, counts        Show sampled probabilities or shot counts',
          '  ast                  Show the parsed intermediate representation',
          '  status               Show live server health and limits',
          '  ls, tree, pwd        Inspect browser-workspace files and paths',
          '  cat/head/wc [path]   Inspect a browser-workspace file without host access',
          '  date, echo, clear    Console utilities',
          '',
          'Commands with the qiskit prefix are QORE shortcuts. This console executes supported circuit actions through the backend; it does not provide an operating system shell.',
        ].join('\n'));
        break;
      case 'run':
      case 'parse':
      case 'transpile':
        if (busy) { addLog('warn', 'An operation is already in progress. Wait for it to finish.'); break; }
        if (!source?.trim()) { addLog('warn', 'Open or create a circuit file before running it.'); break; }
        addLog('info', (command === 'run' ? 'Simulating ' : command === 'parse' ? 'Validating ' : 'Optimizing ') + (fileName ?? 'the active buffer') + ' with the bounded quantum runtime…');
        if (command === 'run') onRunSimulation(); else if (command === 'parse') onRunParse(); else onRunTranspile();
        break;
      case '--version':
        addLog('output', 'Server-reported versions:\n' + versionSummary(health?.versions ?? simulation?.versions ?? optimization?.versions));
        break;
      case 'backends':
        addLog('output', 'Last execution backend: ' + (simulation?.backend ?? 'No run yet') + '\nServer-reported limits:\n' + (health ? JSON.stringify(health.limits, null, 2) : 'Health information unavailable.') + '\nCloud hardware connection is not exposed by this console.');
        break;
      case 'draw':
        if (!parsed) { addLog('warn', 'Parse or run the active circuit first.'); break; }
        addLog('output', 'Parsed operations (' + parsed.ir.num_qubits + ' qubits):\n' + (parsed.ir.operations.length
          ? parsed.ir.operations.map((operation, index) => (index + 1) + '. ' + operation.name + (operation.params.length ? '(' + operation.params.join(', ') + ')' : '') + ' ' + operation.qubits.map(qubit => 'q[' + qubit + ']').join(', ') + (operation.clbits.length ? ' → ' + operation.clbits.map(bit => 'c[' + bit + ']').join(', ') : '')).join('\n')
          : 'The circuit contains no operations.'));
        break;
      case 'metrics':
        addLog(parsed ? 'output' : 'warn', parsed ? JSON.stringify(parsed.metrics, null, 2) : 'Parse or run the active circuit to see its metrics.');
        break;
      case 'qasm':
        addLog(parsed?.qasm ? 'output' : 'warn', parsed?.qasm ?? 'No OpenQASM export is attached. Parse or run a supported circuit first.');
        break;
      case 'bloch':
      case 'purity': {
        const vectors = result?.bloch_vectors;
        addLog(vectors?.length ? 'output' : 'warn', vectors?.length
          ? vectors.map(vector => `q[${vector.qubit}] ${command === 'purity' ? `purity=${vector.purity.toFixed(8)} ${vector.is_pure ? 'pure' : 'mixed'}` : `x=${vector.x.toFixed(8)} y=${vector.y.toFixed(8)} z=${vector.z.toFixed(8)} theta=${vector.theta.toFixed(8)} phi=${vector.phi.toFixed(8)} purity=${vector.purity.toFixed(8)}`}`).join('\n')
          : 'No Bloch evidence is attached. Parse or run a circuit within the visualization limit.');
        break;
      }
      case 'statevector': {
        const amplitudes = result?.statevector_amplitudes;
        addLog(amplitudes?.length ? 'output' : 'warn', amplitudes?.length
          ? 'Complex state amplitudes:\n' + amplitudes.slice(0, 256).map(amplitude => '|' + amplitude.state + '⟩: ' + complex(amplitude) + '; probability ' + (amplitude.probability * 100).toFixed(4) + '%').join('\n') + (amplitudes.length > 256 ? '\nFirst 256 amplitudes shown. Open the Lab for the full result.' : '')
          : 'No statevector amplitudes were returned. Run a supported statevector simulation or inspect measured probabilities with probs.');
        break;
      }
      case 'unitary': {
        const matrix = result?.unitary_matrix;
        addLog(matrix?.length ? 'output' : 'warn', matrix?.length
          ? 'Circuit unitary (' + matrix.length + ' × ' + (matrix[0]?.length ?? 0) + '):\n' + matrix.slice(0, 32).map(row => '[ ' + row.slice(0, 32).map(complex).join(', ') + (row.length > 32 ? ', …' : '') + ' ]').join('\n') + (matrix.length > 32 ? '\nFirst 32 rows and columns shown. Open the Lab for the full result.' : '')
          : 'No unitary matrix was returned for this circuit. A non-unitary circuit or size limit may prevent matrix output.');
        break;
      }
      case 'probs':
      case 'counts':
        addLog(simulation ? 'output' : 'warn', simulation
          ? (command === 'counts' ? 'Measured shot counts' : 'Sampled measurement probabilities') + ' (' + simulation.shots + ' shots):\n' + JSON.stringify(command === 'counts' ? simulation.counts : simulation.probabilities, null, 2)
          : 'No measured result yet. Run a simulation first.');
        break;
      case 'ideal':
        addLog(simulation ? 'output' : 'warn', simulation
          ? 'Ideal reference probabilities:\n' + JSON.stringify(simulation.theoretical_probabilities, null, 2)
          : 'No source-matched simulation is attached. Run the active circuit first.');
        break;
      case 'bitorder':
        addLog(simulation ? 'output' : 'warn', simulation ? 'Recorded bitstring convention:\n' + (typeof simulation.bit_ordering === 'string' ? simulation.bit_ordering : JSON.stringify(simulation.bit_ordering, null, 2)) : 'No simulation mapping is attached.');
        break;
      case 'noise':
        addLog(simulation ? 'output' : 'warn', simulation ? JSON.stringify({
          backend: simulation.backend, simulation_method: simulation.simulation_method ?? null,
          noise_applied: simulation.noise_applied ?? false, depolarizing_rate: simulation.noise_rate ?? 0,
          readout_error: simulation.readout_error ?? 0,
        }, null, 2) : 'No simulation evidence is attached.');
        break;
      case 'source-hash':
        addLog(parsed?.source_hash ? 'output' : 'warn', parsed?.source_hash ?? 'Parse or run the active source to calculate its hash.');
        break;
      case 'result':
        addLog(parsed ? 'output' : 'warn', parsed ? JSON.stringify({
          source_hash: parsed.source_hash, metrics: parsed.metrics,
          simulation: simulation ? { id: simulation.id, backend: simulation.backend, shots: simulation.shots, seed: simulation.seed, tvd: simulation.tvd } : null,
          forge: optimization ? { id: optimization.id, validation: optimization.validation, differences: optimization.differences } : null,
        }, null, 2) : 'No parsed evidence is attached.');
        break;
      case 'capabilities':
      case 'gates':
      case 'modules':
      case 'methods':
      case 'limits': {
        try {
          const capability = await api<QuantumCapabilities>('/capabilities');
          const value = command === 'gates' ? capability.gates
            : command === 'modules' ? capability.modules
            : command === 'methods' ? capability.simulation_methods
            : command === 'limits' ? capability.limits : capability;
          addLog('output', JSON.stringify(value, null, 2));
        } catch (capabilityError) {
          addLog('error', capabilityError instanceof Error ? capabilityError.message : 'Could not load quantum capabilities.');
        }
        break;
      }
      case 'ast':
        addLog(parsed ? 'output' : 'warn', parsed
          ? 'Parsed circuit IR (this is not the Python AST):\n' + JSON.stringify(parsed.ir, null, 2)
          : 'The backend has not returned a parsed circuit. No validation result is available.');
        break;
      case 'status': {
        const sanitizedHealth = health ? {
          ...health,
          storage: String((health as Record<string, unknown>).storage || '').includes('supabase') ? 'cloud' : (health as Record<string, unknown>).storage
        } : null;
        addLog(sanitizedHealth ? 'output' : 'warn', sanitizedHealth ? JSON.stringify(sanitizedHealth, null, 2) : 'Server health is unavailable. No backend status has been confirmed.');
        break;
      }
      case 'ls':
        addLog('output', workspaceFiles.length ? workspaceFiles.map(file => file.path).sort().join('\n') : 'The browser workspace contains no files.');
        break;
      case 'tree': {
        const paths = workspaceFiles.map(file => file.path).sort();
        addLog('output', paths.length ? paths.map(path => {
          const parts = path.split('/'); return '  '.repeat(Math.max(0, parts.length - 1)) + '└─ ' + parts[parts.length - 1];
        }).join('\n') : 'The browser workspace contains no files.');
        break;
      }
      case 'pwd':
        addLog('output', fileName ? 'browser-workspace:/' + (workspaceFiles.find(file => file.name === fileName || file.id === fileName)?.path ?? fileName) : 'browser-workspace:/');
        break;
      case 'cat':
      case 'head':
      case 'wc': {
        const requestedFile = args.join(' ').replace(/^['"]|['"]$/g, '');
        const selected = requestedFile
          ? workspaceFiles.find(file => file.path === requestedFile || file.name === requestedFile || file.id === requestedFile)
          : workspaceFiles.find(file => file.name === fileName || file.id === fileName);
        const contents = selected?.source ?? (!requestedFile ? source : undefined);
        if (contents === undefined) { addLog('warn', 'Workspace file not found: ' + (requestedFile || fileName || '(none)')); break; }
        if (command === 'wc') {
          addLog('output', `${contents.split(/\r?\n/).length} lines  ${new TextEncoder().encode(contents).length} bytes  ${selected?.path ?? fileName ?? 'active buffer'}`);
        } else {
          const shown = command === 'head' ? contents.split(/\r?\n/).slice(0, 20).join('\n') : contents;
          addLog('output', (selected?.path ?? fileName ?? 'Active buffer') + '\n' + (shown || '(empty file)'));
        }
        break;
      }
      case 'date': addLog('output', new Date().toISOString()); break;
      case 'echo': addLog('output', args.join(' ')); break;
      case 'clear': setLogs([]); break;
      default: addLog('error', 'Unsupported command: ' + parts[0] + '. Type help for supported commands.');
    }
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'l') {
      event.preventDefault(); setLogs([]);
    } else if (event.key === 'Enter') void handleCommandSubmit(inputVal);
    else if (event.key === 'ArrowUp') {
      event.preventDefault();
      if (cmdHistory.length) {
        const next = Math.min(historyIndex + 1, cmdHistory.length - 1);
        setHistoryIndex(next); setInputVal(cmdHistory[next]);
      }
    } else if (event.key === 'ArrowDown') {
      event.preventDefault();
      const next = historyIndex - 1;
      setHistoryIndex(Math.max(-1, next)); setInputVal(next >= 0 ? cmdHistory[next] : '');
    } else if (event.key === 'Tab') {
      const match = ALL_COMMANDS.find(command => command.startsWith(inputVal.trim()));
      if (inputVal.trim() && match) { event.preventDefault(); setInputVal(match); }
    }
  };

  if (!isOpen) return null;
  return <div className={'vscode-terminal-dock ' + (isMaximized ? 'maximized' : '')}>
    <div className="terminal-header">
      <div className="terminal-tabs" role="tablist" aria-label="Console panels">
        {(['terminal', 'output', 'problems', 'debug'] as const).map(tab => <button key={tab} type="button" role="tab"
          aria-selected={activeTab === tab} aria-controls={'qore-console-' + tab} id={'qore-console-tab-' + tab}
          className={'terminal-tab-btn ' + (activeTab === tab ? 'active' : '')} onClick={() => setActiveTab(tab)}>
          <span>{tab === 'debug' ? 'DEBUG CONSOLE' : tab.toUpperCase()}</span>
          {tab === 'terminal' && <span className="tab-pill">QORE</span>}
          {tab === 'problems' && <span className={'tab-pill-count ' + (workspaceProblems.length ? hasErrors ? 'error' : 'warn' : 'zero')}>{workspaceProblems.length}</span>}
        </button>)}
      </div>
      <div className="terminal-controls">
        <button type="button" className="terminal-icon-btn" aria-label="Clear terminal" title="Clear terminal (Ctrl+L)" onClick={() => setLogs([])}><Icon name="trash" size={13} /></button>
        <button type="button" className="terminal-icon-btn" aria-label={isMaximized ? 'Restore terminal size' : 'Maximize terminal'} onClick={() => setIsMaximized(value => !value)}><Icon name={isMaximized ? 'collapse' : 'expand'} size={13} /></button>
        <button type="button" className="terminal-icon-btn close" aria-label="Close terminal" onClick={onClose}><Icon name="close" size={13} /></button>
      </div>
    </div>
    <div className="terminal-body" id={'qore-console-' + activeTab} role="tabpanel" aria-labelledby={'qore-console-tab-' + activeTab}>
      {activeTab === 'terminal' && <div className="terminal-log-scroll">
        <div role="log" aria-label="Command output" aria-live="polite" aria-relevant="additions">
          {logs.map(log => <div key={log.id} className={'terminal-line ' + log.type + ' line-fade-in'}>
            <span className="terminal-time">{log.time}</span><div className="terminal-content">
              {log.type === 'cmd' ? <span className="term-cmd-text">{log.text}</span> : <pre className="term-pre">{log.text}</pre>}
            </div>
          </div>)}
        </div>
        <div className="terminal-prompt-row">
          <span className="prompt-label">qore ›</span>
          <input ref={inputRef} type="text" className="terminal-input" aria-label="QORE console command"
            value={inputVal} maxLength={4096} onChange={event => setInputVal(event.target.value)} onKeyDown={handleKeyDown}
            placeholder="Type help, run, metrics, or unitary…" spellCheck={false} autoComplete="off" />
        </div>
        <div ref={terminalEndRef} />
      </div>}
      {activeTab === 'output' && <div className="terminal-output-pane"><pre className="term-output-pre">{redact(output)}</pre></div>}
      {activeTab === 'problems' && <div className="terminal-problems-pane">
        {!workspaceProblems.length ? <div className="no-problems-msg"><Icon name="check" size={14} />
          <span>{parsed ? 'The latest parse reported no problems.' : 'No backend diagnostics yet. Parse or run the file to check it.'}</span></div>
          : <div className="problems-tree-list"><div className="problems-file-group">
            <div className="problems-file-header"><Icon name="chevron" size={11} /><Icon name="file" size={13} />
              <span className="file-name">{fileName ?? 'Active buffer'}</span><span className="problems-count-badge">{workspaceProblems.length}</span></div>
            <div className="problems-items-column">{workspaceProblems.map(problem => <div key={problem.id}
              className={'problem-item ' + problem.severity} role="button" tabIndex={0}
              onClick={() => onSelectProblemLine?.(problem.line)} onKeyDown={event => {
                if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); onSelectProblemLine?.(problem.line); }
              }} title={'Jump to line ' + problem.line}>
              <div className={'problem-icon-wrap ' + problem.severity}><Icon name={problem.severity === 'error' ? 'close' : 'info'} size={12} /></div>
              <span className="problem-msg">{problem.message}</span><span className="problem-code mono">{problem.code}</span>
              <span className="problem-pos mono">[{problem.line}, {problem.col}]</span>
            </div>)}</div>
          </div></div>}
      </div>}
      {activeTab === 'debug' && <div className="terminal-output-pane"><pre className="term-output-pre">{redact(debug)}</pre></div>}
    </div>
  </div>;
}
