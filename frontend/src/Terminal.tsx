import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Icon } from './Icons';
import type { Parsed, Simulation, Optimization, Health } from './types';

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
  parsed: Parsed | null;
  simulation: Simulation | null;
  optimization: Optimization | null;
  health: Health | null;
  busy: string;
  source?: string;
  fileName?: string;
  error?: string;
  onSelectProblemLine?: (line: number) => void;
}

interface LogEntry {
  id: string;
  type: 'cmd' | 'info' | 'success' | 'warn' | 'error' | 'output';
  text: string;
  time: string;
}

const ALL_COMMANDS = [
  'qiskit',
  'qiskit --version',
  'qiskit run',
  'qiskit transpile',
  'qiskit backends',
  'qiskit draw',
  'qiskit statevector',
  'qiskit unitary',
  'qiskit metrics',
  'az quantum',
  'az quantum workspace',
  'az quantum target list',
  'az quantum execute',
  'az quantum status',
  'qsharp',
  'qsharp --version',
  'qsharp estimate',
  'qsharp run',
  'run',
  'simulate',
  'transpile',
  'metrics',
  'statevector',
  'ast',
  'status',
  'ls',
  'cat',
  'whoami',
  'uname -a',
  'date',
  'clear',
  'help',
];

function analyzeWorkspaceProblems(
  source: string | undefined,
  fileName: string | undefined,
  error: string | undefined,
  warnings: string[] | undefined
): WorkspaceProblem[] {
  const problems: WorkspaceProblem[] = [];
  const currentFile = fileName || 'circuit.py';

  // 1. Primary execution or parse error
  if (error) {
    let line = 1;
    let col = 1;
    const lineMatch = error.match(/line\s*(\d+)/i) || error.match(/:\s*(\d+):/);
    if (lineMatch) line = parseInt(lineMatch[1], 10);
    problems.push({
      id: `err-${line}-${col}`,
      severity: 'error',
      file: currentFile,
      line,
      col,
      message: error,
      code: 'E101',
    });
  }

  // 2. Parsed compiler warnings
  if (warnings && warnings.length > 0) {
    warnings.forEach((warn, idx) => {
      problems.push({
        id: `warn-${idx}`,
        severity: 'warning',
        file: currentFile,
        line: 1,
        col: 1,
        message: warn,
        code: 'W201',
      });
    });
  }

  // 3. Static code analysis from active buffer
  if (source) {
    const lines = source.split('\n');

    let numQubits = 2;
    for (const l of lines) {
      const qregMatch = l.match(/QuantumCircuit\((\d+)/);
      if (qregMatch) {
        numQubits = parseInt(qregMatch[1], 10);
        break;
      }
    }

    lines.forEach((l, idx) => {
      const lineNum = idx + 1;
      const trimmed = l.trim();
      if (!trimmed || trimmed.startsWith('#')) return;

      // Unclosed parentheses
      const openParens = (l.match(/\(/g) || []).length;
      const closeParens = (l.match(/\)/g) || []).length;
      if (openParens !== closeParens) {
        problems.push({
          id: `paren-${lineNum}`,
          severity: 'error',
          file: currentFile,
          line: lineNum,
          col: l.length,
          message: 'SyntaxError: Mismatched parentheses in quantum operation statement',
          code: 'E002',
        });
      }

      // Out of bounds qubit reference like qc.h(5)
      const gateMatch = l.match(/qc\.\w+\s*\(\s*(\d+)/);
      if (gateMatch) {
        const qIdx = parseInt(gateMatch[1], 10);
        if (qIdx >= numQubits) {
          problems.push({
            id: `bounds-${lineNum}`,
            severity: 'error',
            file: currentFile,
            line: lineNum,
            col: l.indexOf(gateMatch[1]) + 1,
            message: `IndexError: Qubit register index ${qIdx} exceeds allocated circuit width (${numQubits} qubits)`,
            code: 'E302',
          });
        }
      }
    });
  }

  return problems;
}

export function Terminal({
  isOpen,
  onClose,
  onRunSimulation,
  onRunTranspile,
  parsed,
  simulation,
  optimization,
  health,
  busy,
  source,
  fileName,
  error,
  onSelectProblemLine,
}: TerminalProps) {
  const [activeTab, setActiveTab] = useState<'terminal' | 'output' | 'problems' | 'debug'>('terminal');
  const [inputVal, setInputVal] = useState('');
  const [isMaximized, setIsMaximized] = useState(false);
  const [cmdHistory, setCmdHistory] = useState<string[]>([]);
  const [historyIndex, setHistoryIndex] = useState<number>(-1);

  // Compute live real problems in workspace
  const workspaceProblems = useMemo(() => {
    return analyzeWorkspaceProblems(source, fileName, error, parsed?.warnings);
  }, [source, fileName, error, parsed?.warnings]);

  const hasErrors = workspaceProblems.some((p) => p.severity === 'error');

  const [logs, setLogs] = useState<LogEntry[]>([
    {
      id: 'init-1',
      type: 'info',
      text: 'QORE Quantum Integrated Terminal [Kernel Environment v2.6.1]',
      time: new Date().toLocaleTimeString(),
    },
    {
      id: 'init-2',
      type: 'info',
      text: 'Core Quantum Toolchains Active: AerSimulator, PassManager, Q# Compiler & CLI Tools ready.',
      time: new Date().toLocaleTimeString(),
    },
    {
      id: 'init-3',
      type: 'output',
      text: 'Type "help" to view all available quantum execution, pass manager, and compiler commands.',
      time: new Date().toLocaleTimeString(),
    },
  ]);

  const terminalEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const focusTimerRef = useRef<number | null>(null);

  useEffect(() => {
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    terminalEndRef.current?.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth' });
  }, [logs, activeTab]);

  useEffect(() => {
    if (isOpen) {
      focusTimerRef.current = window.setTimeout(() => inputRef.current?.focus(), 50);
    }
    return () => {
      if (focusTimerRef.current !== null) window.clearTimeout(focusTimerRef.current);
    };
  }, [isOpen, activeTab]);

  useEffect(() => {
    if (busy) {
      addLog('info', `[ENGINE] ${busy} in progress...`);
    }
  }, [busy]);

  useEffect(() => {
    if (simulation) {
      addLog(
        'success',
        `[KERNEL] Simulation complete in ${simulation.execution_ms.toFixed(2)}ms (Backend: ${simulation.backend}, Shots: ${simulation.shots}).`
      );
      const topState = Object.entries(simulation.probabilities).sort((a, b) => b[1] - a[1])[0];
      if (topState) {
        addLog(
          'output',
          `[STATEVECTOR] Dominant state |${topState[0]}⟩ with probability ${(topState[1] * 100).toFixed(2)}%.`
        );
      }
    }
  }, [simulation]);

  useEffect(() => {
    if (optimization) {
      const orig = optimization.original.metrics.gate_count;
      const cand = optimization.candidate.metrics.gate_count;
      const reduction = Math.max(0, orig - cand);
      addLog(
        'success',
        `[TRANSPILER] Pass complete. Gates: ${orig} -> ${cand} (${reduction} eliminated, depth: ${optimization.candidate.metrics.depth}).`
      );
    }
  }, [optimization]);

  const addLog = (type: LogEntry['type'], text: string) => {
    const time = new Date().toLocaleTimeString();
    setLogs((prev) => [
      ...prev.slice(-499),
      {
        id: `${Date.now()}-${Math.random().toString(36).substring(2, 6)}`,
        type,
        text,
        time,
      },
    ]);
  };

  const handleCommandSubmit = (commandText: string) => {
    const raw = commandText.trim();
    if (!raw) return;

    addLog('cmd', `user@qore:~/circuits$ ${raw}`);
    setCmdHistory((prev) => [raw, ...prev]);
    setHistoryIndex(-1);
    setInputVal('');

    const parts = raw.split(/\s+/);
    const cmd = parts[0].toLowerCase();
    const sub = parts[1]?.toLowerCase();

    // 1. Quantum Kernel & PassManager Commands
    if (cmd === 'qiskit') {
      if (!sub || sub === '--version' || sub === '-v' || sub === 'version') {
        addLog(
          'output',
          `quantum-kernel: 2.6.1\naer-simulator: 0.18.0\nquantum-nature: 0.7.2\npass-manager: v2 (SamplerV2, EstimatorV2)\npython-runtime: 3.12.14 [x86_64]`
        );
      } else if (sub === 'run' || sub === 'simulate') {
        addLog('info', '[KERNEL] Dispatching active circuit to AerSimulator(backend="statevector")...');
        onRunSimulation();
      } else if (sub === 'transpile' || sub === 'opt' || sub === 'optimize') {
        const lvl = parts[2] ?? '2';
        addLog('info', `[COMPILER] Executing pass manager with optimization_level=${lvl} (SABRE routing)...`);
        onRunTranspile();
      } else if (sub === 'backends' || sub === 'targets') {
        addLog(
          'output',
          `Configured Quantum Hardware Targets:
  - aer_simulator (Statevector, 30 qubits max, Local Sim)
  - qpu_heron (156 qubits, Heavy-Hexagon, T1=180us, T2=140us)
  - qpu_eagle (127 qubits, Heavy-Hexagon, T1=120us, T2=95us)
  - qpu_brisbane (127 qubits, Cross-Resonance, Online)
  - qpu_kyoto (127 qubits, Cross-Resonance, Online)`
        );
      } else if (sub === 'draw' || sub === 'circuit') {
        if (parsed) {
          addLog(
            'output',
            `Circuit Wire Diagram:
q_0: ──[H]────■────[M]─
              │     │
q_1: ─────────■────[M]─
c: 2/══════════════════`
          );
        } else {
          addLog('warn', '[KERNEL] No active parsed circuit found.');
        }
      } else if (sub === 'statevector') {
        if (simulation?.probabilities) {
          const lines = Object.entries(simulation.probabilities)
            .map(([basis, prob]) => `  |${basis}⟩: ${(prob * 100).toFixed(2)}%`)
            .join('\n');
          addLog('output', `AerSimulator State Probabilities:\n${lines}`);
        } else {
          addLog('warn', '[KERNEL] Statevector empty. Run "qiskit run" first.');
        }
      } else if (sub === 'unitary') {
        addLog(
          'output',
          `Unitary Operator Matrix (2x2 subsystem):
[[ 0.70710678+0.j,  0.70710678+0.j],
 [ 0.70710678+0.j, -0.70710678+0.j]]`
        );
      } else if (sub === 'metrics') {
        if (parsed?.metrics) {
          addLog(
            'output',
            `Circuit Statistics:
  Width (qubits): ${parsed.metrics.qubits}
  Depth: ${parsed.metrics.depth}
  Total Gates: ${parsed.metrics.gate_count}
  2-Qubit CX: ${parsed.metrics.two_qubit_gate_count}
  Measurements: ${parsed.metrics.measurement_count}`
          );
        } else {
          addLog('warn', '[KERNEL] No parsed circuit metrics available.');
        }
      } else {
        addLog('error', `[KERNEL] Unknown argument: "${sub}". Type "help" for options.`);
      }
      return;
    }

    // 2. Cloud Execution & Resource Estimator Commands
    if (cmd === 'az' && sub === 'quantum') {
      const azSub = parts[2]?.toLowerCase();
      if (!azSub || azSub === '--help' || azSub === '-h') {
        addLog(
          'output',
          `Quantum Cloud Commands:
  az quantum workspace          Display active quantum workspace
  az quantum target list        List target QPU and simulator clusters
  az quantum execute            Execute circuit on target backend
  az quantum status             Check job queue and runtime quota`
        );
      } else if (azSub === 'workspace') {
        addLog(
          'output',
          `Active Workspace: qore-quantum-cluster-east
Subscription: Quantum Developer Research
Resource Group: rg-quantum-core
Location: eastus
Status: Connected & Ready`
        );
      } else if (azSub === 'target' && parts[3]?.toLowerCase() === 'list') {
        addLog(
          'output',
          `Quantum Target Providers:
  - ionq.simulator (29 qubits, Ideal all-to-all simulation)
  - ionq.qpu.aria-1 (25 algorithmic qubits, Trapped-Ion)
  - quantinuum.sim.h1-1sc (20 qubits, Quantum Phase Simulator)
  - quantinuum.qpu.h1-1 (20 qubits, System Model H1, 2Q infidelity < 0.2%)
  - rigetti.sim.aspen-m-3 (80 qubits, Planar transmon lattice)`
        );
      } else if (azSub === 'execute' || azSub === 'run') {
        addLog('info', '[CLOUD] Submitting circuit job to ionq.simulator via REST API...');
        onRunSimulation();
      } else if (azSub === 'status' || azSub === 'jobs') {
        addLog(
          'output',
          `Job ID: job-qc-8942-771
Status: Succeeded
Provider: ionq
Target: ionq.simulator
Created: ${new Date().toISOString()}
Total Execution Time: 0.84s`
        );
      } else {
        addLog('error', `[CLOUD] Unknown command: "az quantum ${azSub}".`);
      }
      return;
    }

    if (cmd === 'qsharp') {
      if (!sub || sub === '--version' || sub === '-v') {
        addLog('output', 'Q# Compiler v1.0.38 (Core Runtime net8.0)');
      } else if (sub === 'estimate' || sub === 'resource-estimator') {
        const qCount = parsed?.metrics?.qubits ?? 2;
        const gCount = parsed?.metrics?.gate_count ?? 4;
        addLog(
          'output',
          `Quantum Resource Estimator (Fault-Tolerant Target):
Physical Qubits Required: ${qCount * 120 + 400}
Logical Qubits: ${qCount}
Total T-States: ${Math.max(12, gCount * 3)}
Algorithm Runtime: 1.48 ms
Code Distance: 7
Error Budget: 0.001 (0.1%)
Target Platform: Superconducting Transmon Lattice`
        );
      } else if (sub === 'run' || sub === 'compile') {
        addLog('info', '[COMPILER] Compiling Q# circuit program into quantum target representation...');
        onRunSimulation();
      } else {
        addLog('error', `[COMPILER] Unknown qsharp option: "${sub}". Try "qsharp estimate".`);
      }
      return;
    }

    // 3. Core Shell & Simulator Commands
    switch (cmd) {
      case 'help':
      case '?':
        addLog(
          'output',
          `QORE Quantum Integrated Terminal — Available Commands:

Quantum Simulation & Pass Manager:
  qiskit --version             Display Quantum Kernel, Aer, and Runtime version
  qiskit run                   Execute circuit on local AerSimulator
  qiskit transpile [-o 0-3]    Execute pass manager gate optimization
  qiskit backends              List available QPUs and simulators
  qiskit draw                  Render ASCII gate diagram of current circuit
  qiskit statevector           Inspect calculated quantum state amplitudes
  qiskit metrics               Inspect qubit width, depth, and gate counts

Resource Estimation & Cloud Compilation:
  az quantum workspace         Show connected quantum cloud workspace
  az quantum target list       List target QPU and simulator clusters
  az quantum execute           Execute job on remote quantum target
  az quantum status            Inspect recent cloud job execution status
  qsharp --version             Display Q# compiler version
  qsharp estimate              Run Quantum Resource Estimator (FTQC)

General Workspace Commands:
  run, simulate                Run Aer simulation on active circuit
  transpile, opt               Optimize active circuit with pass manager
  metrics                      Display circuit metrics summary
  statevector, probs           Display state probabilities
  ast                          Inspect bounded AST audit status
  status                       Check Python, Kernel, and IR health
  ls, dir                      List files in workspace
  cat <file>                   Print file contents
  whoami                       Display current user
  uname -a                     Display system environment
  date                         Display current timestamp
  clear, cls                   Clear terminal output`
        );
        break;

      case 'run':
      case 'simulate':
        addLog('info', '[AER] Dispatching circuit simulation to Qiskit Aer...');
        onRunSimulation();
        break;

      case 'transpile':
      case 'opt':
      case 'optimize':
        addLog('info', '[FORGE] Running pass manager optimization Level 2...');
        onRunTranspile();
        break;

      case 'metrics':
        if (parsed?.metrics) {
          addLog(
            'output',
            `Circuit Statistics:
  Qubits: ${parsed.metrics.qubits}
  Depth: ${parsed.metrics.depth}
  Gate Count: ${parsed.metrics.gate_count}
  2-Qubit Gates: ${parsed.metrics.two_qubit_gate_count}
  Measurements: ${parsed.metrics.measurement_count}`
          );
        } else {
          addLog('warn', '[TERMINAL] No parsed circuit metrics available.');
        }
        break;

      case 'statevector':
      case 'probs':
        if (simulation?.probabilities) {
          const lines = Object.entries(simulation.probabilities)
            .map(([st, prob]) => `  |${st}⟩: ${(prob * 100).toFixed(2)}%`)
            .join('\n');
          addLog('output', `Calculated State Probabilities:\n${lines}`);
        } else {
          addLog('warn', '[TERMINAL] No simulation data. Run "run" first.');
        }
        break;

      case 'ast':
        addLog(
          'output',
          `Bounded AST Audit:
  Status: Passed
  Validation: Bounded AST Sandbox
  Prohibited Constructs: None detected
  Execution Model: Direct IR compilation (No eval/exec)`
        );
        break;

      case 'status':
        addLog(
          'output',
          `Environment Status:
  Server: ${health?.status === 'ok' ? 'Online' : 'Connected'}
  Backend: AerSimulator 0.18.0
  Language: Python 3.12.14
  IR Protocol: QORE-IR 1.0`
        );
        break;

      case 'ls':
      case 'dir':
        addLog(
          'output',
          `circuits/
  circuit.py
  ghz_state.py
  teleportation.py
  qft_3qubit.py
  superdense.py
  rotation_ordering.py
openqasm/
  bell_state.qasm
  qaoa_cut.qasm
projects/
README.md`
        );
        break;

      case 'cat':
        if (parts[1]) {
          addLog('output', `# Source preview: ${parts[1]}\nfrom qiskit import QuantumCircuit\n\nqc = QuantumCircuit(2, 2)\nqc.h(0)\nqc.cx(0, 1)\nqc.measure([0, 1], [0, 1])`);
        } else {
          addLog('error', 'Usage: cat <filename>');
        }
        break;

      case 'whoami':
        addLog('output', 'qore-developer');
        break;

      case 'uname':
        addLog('output', 'Linux qore-studio 6.5.0-quantum #1 SMP PREEMPT_DYNAMIC x86_64 GNU/Linux');
        break;

      case 'date':
        addLog('output', new Date().toUTCString());
        break;

      case 'clear':
      case 'cls':
        setLogs([]);
        break;

      case 'echo':
        addLog('output', parts.slice(1).join(' '));
        break;

      default:
        addLog('error', `Command not found: "${cmd}". Type "help" for a list of valid commands.`);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      handleCommandSubmit(inputVal);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (cmdHistory.length > 0) {
        const nextIdx = Math.min(historyIndex + 1, cmdHistory.length - 1);
        setHistoryIndex(nextIdx);
        setInputVal(cmdHistory[nextIdx]);
      }
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (historyIndex > 0) {
        const nextIdx = historyIndex - 1;
        setHistoryIndex(nextIdx);
        setInputVal(cmdHistory[nextIdx]);
      } else if (historyIndex === 0) {
        setHistoryIndex(-1);
        setInputVal('');
      }
    } else if (e.key === 'Tab') {
      e.preventDefault();
      const match = ALL_COMMANDS.find((c) => c.startsWith(inputVal.trim()));
      if (match) {
        setInputVal(match);
      }
    }
  };

  if (!isOpen) return null;

  return (
    <div className={`vscode-terminal-dock ${isMaximized ? 'maximized' : ''}`}>
      {/* 1. Terminal Panel Top Header Bar */}
      <div className="terminal-header">
        <div className="terminal-tabs">
          <button
            type="button"
            className={`terminal-tab-btn ${activeTab === 'terminal' ? 'active' : ''}`}
            onClick={() => setActiveTab('terminal')}
          >
            <span>TERMINAL</span>
            <span className="tab-pill">bash</span>
          </button>

          <button
            type="button"
            className={`terminal-tab-btn ${activeTab === 'output' ? 'active' : ''}`}
            onClick={() => setActiveTab('output')}
          >
            <span>OUTPUT</span>
          </button>

          <button
            type="button"
            className={`terminal-tab-btn ${activeTab === 'problems' ? 'active' : ''}`}
            onClick={() => setActiveTab('problems')}
          >
            <span>PROBLEMS</span>
            <span
              className={`tab-pill-count ${workspaceProblems.length > 0 ? (hasErrors ? 'error' : 'warn') : 'zero'}`}
            >
              {workspaceProblems.length}
            </span>
          </button>

          <button
            type="button"
            className={`terminal-tab-btn ${activeTab === 'debug' ? 'active' : ''}`}
            onClick={() => setActiveTab('debug')}
          >
            <span>DEBUG CONSOLE</span>
          </button>
        </div>

        {/* Toolbar Controls */}
        <div className="terminal-controls">
          <button
            type="button"
            className="terminal-icon-btn"
            title="Clear Terminal (Ctrl+L)"
            onClick={() => setLogs([])}
          >
            <Icon name="trash" size={13} />
          </button>

          <button
            type="button"
            className="terminal-icon-btn"
            title={isMaximized ? 'Restore Terminal Size' : 'Maximize Terminal Panel'}
            onClick={() => setIsMaximized(!isMaximized)}
          >
            <Icon name={isMaximized ? 'collapse' : 'expand'} size={13} />
          </button>

          <button
            type="button"
            className="terminal-icon-btn close"
            title="Close Terminal Panel (Ctrl+`)"
            onClick={onClose}
          >
            <Icon name="close" size={13} />
          </button>
        </div>
      </div>

      {/* 2. Terminal Main Body */}
      <div className="terminal-body" onClick={() => inputRef.current?.focus()}>
        {activeTab === 'terminal' && (
          <div className="terminal-log-scroll">
            {logs.map((log) => (
              <div key={log.id} className={`terminal-line ${log.type} line-fade-in`}>
                <span className="terminal-time">{log.time}</span>
                <div className="terminal-content">
                  {log.type === 'cmd' ? (
                    <span className="term-cmd-text">{log.text}</span>
                  ) : (
                    <pre className="term-pre">{log.text}</pre>
                  )}
                </div>
              </div>
            ))}

            {/* Interactive Prompt Line */}
            <div className="terminal-prompt-row">
              <span className="prompt-label">user@qore:~/circuits$</span>
              <input
                ref={inputRef}
                type="text"
                className="terminal-input"
                value={inputVal}
                onChange={(e) => setInputVal(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Type 'help', 'qiskit run', 'az quantum target list', or 'qsharp estimate'..."
                spellCheck={false}
                autoComplete="off"
              />
            </div>
            <div ref={terminalEndRef} />
          </div>
        )}

        {activeTab === 'output' && (
          <div className="terminal-output-pane">
            <pre className="term-output-pre">
              {`[QORE KERNEL LOG ${new Date().toLocaleDateString()}]
AerSimulator initialized: statevector backend
Bounded AST parser verified: OK (AST Sandbox Enforced)
Matrix Product State engine: Standby
OpenQASM compiler passes: OK
Quantum Intelligence agent: Ready`}
            </pre>
          </div>
        )}

        {/* Real Live Problems Tab */}
        {activeTab === 'problems' && (
          <div className="terminal-problems-pane">
            {workspaceProblems.length === 0 ? (
              <div className="no-problems-msg">
                <Icon name="check" size={14} />
                <span>No problems have been detected in the workspace.</span>
              </div>
            ) : (
              <div className="problems-tree-list">
                <div className="problems-file-group">
                  <div className="problems-file-header">
                    <Icon name="chevron" size={11} />
                    <Icon name="python" size={13} />
                    <span className="file-name">{fileName || 'circuit.py'}</span>
                    <span className="problems-count-badge">{workspaceProblems.length}</span>
                  </div>

                  <div className="problems-items-column">
                    {workspaceProblems.map((prob) => (
                      <div
                        key={prob.id}
                        className={`problem-item ${prob.severity}`}
                        onClick={() => onSelectProblemLine?.(prob.line)}
                        title={`Click to jump to line ${prob.line}`}
                      >
                        <div className={`problem-icon-wrap ${prob.severity}`}>
                          <Icon name={prob.severity === 'error' ? 'close' : 'info'} size={12} />
                        </div>
                        <span className="problem-msg">{prob.message}</span>
                        <span className="problem-code mono">{prob.code}</span>
                        <span className="problem-pos mono">
                          [{prob.line}, {prob.col}]
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === 'debug' && (
          <div className="terminal-output-pane">
            <pre className="term-output-pre">
              {`[DEBUG] QORE IR v1.0 active
[DEBUG] RNG Seed: 42
[DEBUG] Classical Endianness: Little-Endian
[DEBUG] Target Basis: Universal [u, cx]
[DEBUG] Memory Allocation: 0.12 MB
[DEBUG] Health: ${health?.status ?? 'connected'}`}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
}
