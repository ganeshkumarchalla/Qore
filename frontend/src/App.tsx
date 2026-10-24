import { useCallback, useEffect, useRef, useState } from 'react';
import Editor from '@monaco-editor/react';
import { Circuit, MetricCards } from './Circuit';
import { Icon, Logo, type IconName } from './Icons';
import { CommandPalette, type CommandItem } from './CommandPalette';
import { SettingsModal, loadStoredSettings, saveStoredSettings } from './SettingsModal';
import { BlochSphereViewer, GatePalette, QasmViewer, UnitaryMatrixViewer } from './QuantumVisuals';
import { Forge, Intelligence, Lab, Research, Warnings } from './Panels';
import { Explorer, type WorkspaceFile } from './Explorer';
import { Terminal } from './Terminal';
import { ErrorBoundary } from './ErrorBoundary';
import { WelcomeModal } from './WelcomeModal';
import { AuthModal, type AuthUser, loadStoredUser } from './AuthModal';
import {
  api,
  formatDate,
  readable,
  type Example,
  type Experiment,
  type ExperimentSummary,
  type Health,
  type Optimization,
  type Parsed,
  type Project,
  type Settings,
  type Simulation,
} from './types';

type Tab = 'Studio' | 'Lab' | 'Forge' | 'Research' | 'Intelligence';
type Modal = { kind: 'new' | 'rename' | 'save' | 'experiment' | 'discard' | 'approve'; action?: () => void };

const tabs: { name: Tab; icon: IconName; label: string; shortLabel: string }[] = [
  { name: 'Studio', icon: 'code', label: 'Circuit Editor', shortLabel: 'Editor' },
  { name: 'Lab', icon: 'lab', label: 'Simulation', shortLabel: 'Lab' },
  { name: 'Forge', icon: 'forge', label: 'Optimization', shortLabel: 'Forge' },
  { name: 'Research', icon: 'research', label: 'History', shortLabel: 'Ledger' },
  { name: 'Intelligence', icon: 'spark', label: 'Assistant', shortLabel: 'Copilot' },
];

const blankSource = `# Quantum Circuit Program
from qiskit import QuantumCircuit

qc = QuantumCircuit(2, 2)

# Apply quantum gates
qc.h(0)
qc.cx(0, 1)

# Terminal measurements
qc.measure(0, 0)
qc.measure(1, 1)
`;

const THEME_NAMES: Record<string, string> = {
  'obsidian-void': 'Obsidian Void',
  'hyperion-cyan': 'Hyperion Luminescence',
  'cobalt-singularity': 'Cobalt Singularity',
  'boreal-cryo': 'Zero-Kelvin Cryo',
  'plasma-nebula': 'Plasma Nebula',
  'dark-modern': 'Obsidian Void',
  'antigravity': 'Hyperion Luminescence',
  'azure-quantum': 'Cobalt Singularity',
  'nordic-frost': 'Zero-Kelvin Cryo',
};

export default function App() {
  const [tab, setTab] = useState<Tab>('Studio');
  const [sidebar, setSidebar] = useState(true);
  const [source, setSource] = useState('');
  const sourceRef = useRef(source);
  sourceRef.current = source;
  const editorRef = useRef<any>(null);

  const [name, setName] = useState('Untitled project');
  const [baseline, setBaseline] = useState('');
  const [baselineName, setBaselineName] = useState('Untitled project');
  const [projectId, setProjectId] = useState<string | null>(null);
  const [activeFileId, setActiveFileId] = useState<string>('circuits/circuit.py');

  const [projects, setProjects] = useState<Project[]>([]);
  const [examples, setExamples] = useState<Example[]>([]);
  const [experiments, setExperiments] = useState<ExperimentSummary[]>([]);
  const [health, setHealth] = useState<Health | null>(null);

  const [parsed, setParsed] = useState<Parsed | null>(null);
  const [simulation, setSimulation] = useState<Simulation | null>(null);
  const [optimization, setOptimization] = useState<Optimization | null>(null);
  const [historical, setHistorical] = useState<Experiment | null>(null);
  const [selectedExperiment, setSelectedExperiment] = useState<Experiment | null>(null);

  const [settings, setSettings] = useState<Settings>(loadStoredSettings);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isPaletteOpen, setIsPaletteOpen] = useState(false);
  const [isHudOpen, setIsHudOpen] = useState(false);
  const [isTerminalOpen, setIsTerminalOpen] = useState(false);
  // The entry screen is a page-load experience, not a permanent preference:
  // every refresh starts with the QORE welcome surface again.
  const [isWelcomeOpen, setIsWelcomeOpen] = useState(true);
  const [isAuthOpen, setIsAuthOpen] = useState(false);
  const [currentUser, setCurrentUser] = useState<AuthUser | null>(loadStoredUser);
  const [inspectorTab, setInspectorTab] = useState<'circuit' | 'bloch' | 'unitary' | 'qasm'>('circuit');
  const [activeDropdown, setActiveDropdown] = useState<'File' | 'Edit' | 'Quantum' | 'View' | 'Terminal' | 'Help' | null>(null);
  const [isRunMenuOpen, setIsRunMenuOpen] = useState(false);

  const [shots, setShots] = useState('1024');
  const [seed, setSeed] = useState('42');
  const [level, setLevel] = useState('2');

  const [busy, setBusy] = useState('Connecting');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const [modal, setModal] = useState<Modal | null>(null);
  const [modalName, setModalName] = useState('');
  const [modalError, setModalError] = useState('');
  const [saving, setSaving] = useState(false);

  const dirty = source !== baseline || name !== baselineName;

  const clearResults = useCallback(() => {
    setParsed(null);
    setSimulation(null);
    setOptimization(null);
  }, []);

  useEffect(() => {
    const handler = (event: BeforeUnloadEvent) => {
      if (dirty) {
        event.preventDefault();
        event.returnValue = '';
      }
    };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, [dirty]);

  // Global listener to close menubar & run dropdowns when clicking outside or pressing Escape
  useEffect(() => {
    const handleOutside = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (!target.closest('.menu-dropdown-container') && !target.closest('.unified-run-group')) {
        setActiveDropdown(null);
        setIsRunMenuOpen(false);
      }
    };
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setActiveDropdown(null);
        setIsRunMenuOpen(false);
      }
    };
    window.addEventListener('mousedown', handleOutside);
    window.addEventListener('keydown', handleKey);
    return () => {
      window.removeEventListener('mousedown', handleOutside);
      window.removeEventListener('keydown', handleKey);
    };
  }, []);

  const initialize = useCallback(async () => {
    setBusy('Connecting');
    setError('');
    try {
      const [nextHealth, nextExamples, nextProjects, nextExperiments] = await Promise.all([
        api<Health>('/health'),
        api<Example[]>('/examples'),
        api<Project[]>('/projects'),
        api<ExperimentSummary[]>('/experiments'),
      ]);
      setHealth(nextHealth);
      setExamples(nextExamples);
      setProjects(nextProjects);
      setExperiments(nextExperiments);
      // Start with a genuinely empty workspace. Examples remain available from the
      // explicit File > Load example menu, never as hidden seeded editor content.
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy('');
    }
  }, []);

  useEffect(() => {
    void initialize();
  }, [initialize]);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', 'obsidian-void');
    document.documentElement.style.setProperty('--vscode-accent', '#6ea8d8');
    if (settings.glassmorphism) {
      document.documentElement.setAttribute('data-glass', 'true');
    } else {
      document.documentElement.removeAttribute('data-glass');
    }
  }, [settings.theme, settings.accentColor, settings.glassmorphism]);

  useEffect(() => {
    if (!notice) return;
    const timeout = setTimeout(() => setNotice(''), 5000);
    return () => clearTimeout(timeout);
  }, [notice]);

  useEffect(() => {
    if (error) setIsTerminalOpen(true);
  }, [error]);

  function showModal(kind: Modal['kind'], nextName = name, action?: () => void) {
    setModal({ kind, action });
    setModalName(nextName);
    setModalError('');
  }

  function safeSwitch(action: () => void) {
    if (busy || saving) return;
    if (dirty) showModal('discard', name, action);
    else action();
  }

  function handleOpenFile(file: WorkspaceFile) {
    safeSwitch(() => {
      setActiveFileId(file.id);
      void loadSource(file.source, file.name, file.projectId || null, file.id);
    });
  }

  async function loadSource(nextSource: string, nextName: string, id: string | null, customFileId?: string) {
    const fileId = customFileId || (id ? id : nextName.includes('.') ? `circuits/${nextName}` : `circuits/${nextName.toLowerCase().replace(/[^a-z0-9]/g, '_')}.py`);
    setActiveFileId(fileId);
    setSource(nextSource);
    sourceRef.current = nextSource;
    setName(nextName);
    setBaseline(nextSource);
    setBaselineName(nextName);
    setProjectId(id);
    setHistorical(null);
    setSelectedExperiment(null);
    clearResults();
    setTab('Studio');
    setError('');

    // Only invoke quantum compiler parser on Python quantum circuit code
    if (!fileId.endsWith('.md') && !fileId.endsWith('.json') && !fileId.endsWith('.txt')) {
      setBusy('Parsing');
      try {
        setParsed(await api<Parsed>('/parse', { source: nextSource }));
      } catch (err) {
        setError((err as Error).message);
      } finally {
        setBusy('');
      }
    } else {
      // Non-Python workspace files are still fully editable; they simply do
      // not need a quantum parse pass before the editor becomes interactive.
      setBusy('');
    }
  }

  async function openProject(id: string) {
    setBusy('Opening project');
    setError('');
    try {
      const project = await api<Project>(`/projects/${id}`);
      await loadSource(project.source, project.name, project.id);
      setBusy('');
    } catch (err) {
      setError((err as Error).message);
      setBusy('');
    }
  }

  async function loadExperimentData(id: string) {
    const item = await api<Experiment>(`/experiments/${id}`);
    setSource(item.source);
    sourceRef.current = item.source;
    setName(item.name);
    setBaseline(item.source);
    setBaselineName(item.name);
    setProjectId(null);
    setHistorical(item);
    setSelectedExperiment(item);
    setSimulation(item.simulation);
    setOptimization(item.optimization);
    setParsed(
      item.ir && item.metrics
        ? { ir: item.ir, metrics: item.metrics, source_hash: item.source_hash, warnings: [] }
        : item.simulation ?? (item.optimization ? { ...item.optimization.original, source_hash: item.source_hash, warnings: [] } : null)
    );
    if (item.simulation) {
      setShots(String(item.simulation.shots));
      setSeed(String(item.simulation.seed));
    }
    return item;
  }

  async function openExperimentInStudio(id: string) {
    setBusy('Opening snapshot in editor');
    setError('');
    try {
      const item = await loadExperimentData(id);
      setTab('Studio');
      setNotice(`Loaded snapshot "${item.name}" into Studio. Circuit, Bloch spheres, and Unitary are preserved.`);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy('');
    }
  }

  async function selectExperimentInResearch(id: string) {
    setBusy('Loading provenance');
    setError('');
    try {
      const item = await loadExperimentData(id);
      setTab('Research');
      setNotice(`Viewing provenance for "${item.name}". Click "Open in Studio" to inspect circuit.`);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy('');
    }
  }

  async function restoreExperimentAsDraft(id: string) {
    setBusy('Creating editable draft');
    setError('');
    try {
      const item = await api<Experiment>(`/experiments/${id}`);
      setHistorical(null);
      setProjectId(null);
      setName(`${item.name} copy`);
      setSource(item.source);
      sourceRef.current = item.source;
      setBaseline('');
      setBaselineName(`${item.name} copy`);
      setSelectedExperiment(null);
      setSimulation(null);
      setOptimization(null);
      setTab('Studio');
      const parsedRes = await api<Parsed>('/parse', { source: item.source }).catch(() => null);
      if (parsedRes) setParsed(parsedRes);
      setNotice(`Copied snapshot "${item.name}" as editable draft in Studio.`);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy('');
    }
  }

  function editSource(next: string) {
    // Normal Explorer files and projects remain editable while background
    // parsing runs. Only immutable historical snapshots are read-only.
    if (next === source || historical) return;
    setSource(next);
    sourceRef.current = next;
    clearResults();
    setSelectedExperiment(null);
    setError('');
  }

  function insertSnippet(code: string) {
    if (busy || historical) return;
    const next = source.endsWith('\n') ? `${source}${code}` : `${source}\n${code}`;
    editSource(next);
    setNotice(`Appended gate instruction: ${code.trim()}`);
  }

  function formatCode() {
    if (!source.trim() || busy || historical) return;
    const lines = source.split('\n');
    const cleaned = lines.map((l) => l.trimEnd()).join('\n');
    editSource(cleaned);
    setNotice('Circuit code formatted');
  }

  function leaveHistorical() {
    if (historical) {
      setHistorical(null);
      setProjectId(null);
      setBaseline('');
      setName(`${historical.name} draft`.slice(0, 100));
      clearResults();
    }
  }

  function numericConfig() {
    const shotValue = Number(shots);
    const seedValue = Number(seed);
    if (!Number.isInteger(shotValue) || shotValue < 1 || shotValue > 100000) {
      throw new Error('Shots must be a whole number between 1 and 100,000.');
    }
    if (!Number.isInteger(seedValue) || seedValue < 0 || seedValue > 2147483647) {
      throw new Error('Seed must be an integer between 0 and 2,147,483,647.');
    }
    return { shots: shotValue, seed: seedValue };
  }

  async function execute(action: 'parse' | 'simulate' | 'optimize') {
    if (busy || !source.trim()) return;
    setError('');
    const submittedSource = source;
    try {
      const config = numericConfig();
      const linkedProject = historical ? undefined : projectId ?? undefined;
      leaveHistorical();
      setBusy(action === 'parse' ? 'Parsing' : action === 'simulate' ? 'Simulating' : 'Optimizing');

      if (action === 'parse') {
        const result = await api<Parsed>('/parse', { source: submittedSource });
        setParsed(result);
        setTab('Studio');
        setNotice('Parsed circuit successfully into QORE-IR.');
      }
      if (action === 'simulate') {
        const simPayload: Record<string, unknown> = {
          source: submittedSource,
          ...config,
          project_id: linkedProject,
          method: settings.simulationBackend,
        };
        if (settings.noiseSimulation && settings.depolarizingRate > 0) {
          simPayload.noise_rate = settings.depolarizingRate;
        }
        if (settings.noiseSimulation && settings.readoutErrorRate > 0) {
          simPayload.readout_error = settings.readoutErrorRate;
        }
        const result = await api<Simulation>('/simulate', simPayload);
        setSimulation(result);
        setParsed(result);
        setTab('Lab');
        setNotice(
          `Simulation complete (${settings.simulationBackend}): ${result.shots.toLocaleString()} shots measured${
            result.noise_applied ? ' (Hardware noise model active)' : ''
          }.`
        );
      }
      if (action === 'optimize') {
        const result = await api<Optimization>('/optimize', {
          source: submittedSource,
          level: Number(level),
          seed: config.seed,
          project_id: linkedProject,
        });
        setOptimization(result);
        setParsed({ ...result.original, source_hash: result.source_hash, warnings: result.warnings });
        setTab('Forge');
        setNotice('Optimization candidate ready for review.');
      }
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy('');
    }
  }

  async function saveCurrent() {
    if (!projectId) {
      showModal('save');
      return;
    }
    setBusy('Saving project');
    setError('');
    try {
      const project = await api<Project>(`/projects/${projectId}`, { name, source }, 'PUT');
      setProjects((items) => [project, ...items.filter((item) => item.id !== project.id)]);
      setBaseline(source);
      setBaselineName(name);
      setNotice('Project saved.');
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy('');
    }
  }

  async function submitModal(event: React.FormEvent) {
    event.preventDefault();
    if (!modal || saving) return;
    setModalError('');

    if (modal.kind === 'discard') {
      const action = modal.action;
      setModal(null);
      action?.();
      return;
    }

    if (modal.kind === 'approve') {
      if (!optimization) return;
      const candidate = optimization.candidate.source;
      const approvedName = historical ? `${historical.name} candidate`.slice(0, 100) : name;
      if (historical) {
        setProjectId(null);
        setBaseline('');
      }
      setHistorical(null);
      setName(approvedName);
      setSource(candidate);
      sourceRef.current = candidate;
      clearResults();
      setSelectedExperiment(null);
      setModal(null);
      setTab('Studio');
      setNotice('Candidate applied as unsaved edit. Run simulation to verify.');
      return;
    }

    if (!modalName.trim()) {
      setModalError('Please enter a name.');
      return;
    }
    setSaving(true);
    try {
      if (modal.kind === 'experiment') {
        const item = await api<Experiment>('/experiments', {
          name: modalName.trim(),
          project_id: projectId ?? undefined,
          source,
          simulation_id: simulation?.id,
          optimization_id: optimization?.id,
        });
        setExperiments((items) => [item, ...items]);
        setSelectedExperiment(item);
        setNotice('Experiment saved to SQLite ledger.');
      } else if (modal.kind === 'new') {
        const project = await api<Project>('/projects', { name: modalName.trim(), source: blankSource });
        setProjects((items) => [project, ...items]);
        await loadSource(project.source, project.name, project.id);
        setNotice('Project created.');
      } else {
        const target = modal.kind === 'rename' ? projectId : null;
        const project = await api<Project>(target ? `/projects/${target}` : '/projects', { name: modalName.trim(), source }, target ? 'PUT' : 'POST');
        setProjects((items) => [project, ...items.filter((item) => item.id !== project.id)]);
        setProjectId(project.id);
        setName(project.name);
        setBaseline(source);
        setBaselineName(project.name);
        setHistorical(null);
        setNotice(modal.kind === 'rename' ? 'Project renamed.' : 'Project saved.');
      }
      setModal(null);
    } catch (err) {
      setModalError((err as Error).message);
    } finally {
      setSaving(false);
    }
  }

  // Keyboard Shortcuts: Ctrl+K (Command Palette), Ctrl+, (Settings), Ctrl+Enter / F5 (Run)
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (
        (e.ctrlKey || e.metaKey) &&
        (e.key === 'k' || e.key === 'K' || (e.shiftKey && (e.key === 'p' || e.key === 'P')))
      ) {
        e.preventDefault();
        setIsPaletteOpen((prev) => !prev);
      } else if ((e.ctrlKey || e.metaKey) && e.key === ',') {
        e.preventDefault();
        setIsSettingsOpen(true);
      } else if ((e.ctrlKey || e.metaKey) && (e.key === '`' || e.key === '~')) {
        e.preventDefault();
        setIsTerminalOpen((prev) => !prev);
      } else if ((e.ctrlKey && e.key === 'Enter') || e.key === 'F5') {
        e.preventDefault();
        void execute('simulate');
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [source, shots, seed, level, historical, projectId, settings]);

  const modalTitles = {
    new: 'New Project',
    rename: 'Rename Project',
    save: 'Save Project',
    experiment: 'Save Experiment Snapshot',
    discard: 'Discard Unsaved Changes?',
    approve: 'Apply Candidate to Editor?',
  };

  // Build Command Palette list
  const commands: CommandItem[] = [
    {
      id: 'sim',
      title: 'Run Quantum Simulation (Aer)',
      category: 'Quantum Engine',
      icon: 'play',
      shortcut: 'Ctrl+Enter / F5',
      action: () => void execute('simulate'),
    },
    {
      id: 'opt',
      title: 'Optimize Circuit (Transpiler Passes)',
      category: 'Transpiler',
      icon: 'forge',
      action: () => void execute('optimize'),
    },
    {
      id: 'parse',
      title: 'Parse Circuit & Inspect QORE-IR',
      category: 'AST Parser',
      icon: 'code',
      action: () => void execute('parse'),
    },
    {
      id: 'settings',
      title: 'Preferences: Open QORE Settings',
      category: 'Preferences',
      icon: 'gear',
      shortcut: 'Ctrl+,',
      action: () => setIsSettingsOpen(true),
    },
    {
      id: 'view-editor',
      title: 'View: Open Circuit Editor (circuit.py)',
      category: 'Navigation',
      icon: 'code',
      action: () => setTab('Studio'),
    },
    {
      id: 'view-lab',
      title: 'View: Open Simulation Diagnostics (Lab)',
      category: 'Navigation',
      icon: 'lab',
      action: () => setTab('Lab'),
    },
    {
      id: 'view-forge',
      title: 'View: Open Circuit Optimizer (Forge)',
      category: 'Navigation',
      icon: 'forge',
      action: () => setTab('Forge'),
    },
    {
      id: 'view-history',
      title: 'View: Open Experiment Ledger (Research)',
      category: 'Navigation',
      icon: 'research',
      action: () => setTab('Research'),
    },
    {
      id: 'view-copilot',
      title: 'View: Open Quantum Copilot (Intelligence)',
      category: 'Navigation',
      icon: 'spark',
      action: () => setTab('Intelligence'),
    },
    {
      id: 'view-bloch',
      title: 'Inspect: View Multi-Qubit Bloch Spheres',
      category: 'Quantum Diagnostics',
      icon: 'circuit',
      action: () => {
        setTab('Studio');
        setInspectorTab('bloch');
      },
    },
    {
      id: 'view-unitary',
      title: 'Inspect: View Unitary Matrix Heatmap (U)',
      category: 'Quantum Diagnostics',
      icon: 'code',
      action: () => {
        setTab('Studio');
        setInspectorTab('unitary');
      },
    },
    {
      id: 'view-terminal',
      title: 'View: Toggle Quantum Terminal Dock (Ctrl+`)',
      category: 'View',
      icon: 'code',
      shortcut: 'Ctrl+`',
      action: () => setIsTerminalOpen((v) => !v),
    },
    {
      id: 'view-qasm',
      title: 'Inspect: Export OpenQASM 2.0',
      category: 'Quantum Diagnostics',
      icon: 'copy',
      action: () => {
        setTab('Studio');
        setInspectorTab('qasm');
      },
    },
    {
      id: 'save-proj',
      title: 'File: Save Project',
      category: 'File',
      icon: 'save',
      shortcut: 'Ctrl+S',
      action: () => void saveCurrent(),
    },
    {
      id: 'save-exp',
      title: 'Ledger: Save Experiment Snapshot',
      category: 'Reproducibility',
      icon: 'research',
      action: () => showModal('experiment', `${name} · ${new Date().toLocaleDateString()}`.slice(0, 100)),
    },
    {
      id: 'gate-h',
      title: 'Insert Gate: Hadamard (H)',
      category: 'Insert Gate',
      icon: 'plus',
      action: () => insertSnippet('qc.h(0)\n'),
    },
    {
      id: 'gate-cx',
      title: 'Insert Gate: Controlled-NOT (CX / CNOT)',
      category: 'Insert Gate',
      icon: 'plus',
      action: () => insertSnippet('qc.cx(0, 1)\n'),
    },
    {
      id: 'gate-x',
      title: 'Insert Gate: Pauli-X (NOT)',
      category: 'Insert Gate',
      icon: 'plus',
      action: () => insertSnippet('qc.x(0)\n'),
    },
    {
      id: 'gate-z',
      title: 'Insert Gate: Pauli-Z',
      category: 'Insert Gate',
      icon: 'plus',
      action: () => insertSnippet('qc.z(0)\n'),
    },
    {
      id: 'gate-meas',
      title: 'Insert Gate: Terminal Measurement',
      category: 'Insert Gate',
      icon: 'plus',
      action: () => insertSnippet('qc.measure(0, 0)\n'),
    },
    ...examples.map((ex) => ({
      id: `ex-${ex.id}`,
      title: `Starter Circuit: ${ex.name}`,
      category: 'Examples',
      icon: 'circuit' as const,
      action: () => safeSwitch(() => void loadSource(ex.source, ex.name, null)),
    })),
  ];

  return (
    <div className="vscode-root">
      {/* Top Primary Bar */}
      <header className="workbench-topbar">
        <div className="topbar-left-cluster">
          <div className="topbar-brand" onClick={() => setTab('Studio')} title="QORE Quantum Studio">
            <Logo />
            <span className="brand-title">QORE</span>
          </div>

          {/* Classic Menubar: File, Edit, Quantum, View, Terminal, Help */}
          <div className="topbar-menubar" role="menubar">
            {/* File Menu */}
            <div className="menu-dropdown-container">
              <button
                type="button"
                className={`menu-text-btn ${activeDropdown === 'File' ? 'active-menu' : ''}`}
                onClick={(e) => {
                  e.stopPropagation();
                  setActiveDropdown((cur) => cur === 'File' ? null : 'File');
                }}
                onMouseEnter={() => {
                  if (activeDropdown !== null) setActiveDropdown('File');
                }}
              >
                File
              </button>
              {activeDropdown === 'File' && (
                <div className="classic-dropdown-menu" onClick={(e) => e.stopPropagation()}>
                  <button
                    type="button"
                    className="dropdown-item"
                    onClick={() => {
                      setActiveDropdown(null);
                      safeSwitch(() => showModal('new', 'Untitled project'));
                    }}
                  >
                    <span>New Circuit Project</span>
                    <span className="dropdown-shortcut">Ctrl+N</span>
                  </button>
                  <button
                    type="button"
                    className="dropdown-item"
                    onClick={() => {
                      setActiveDropdown(null);
                      setIsPaletteOpen(true);
                    }}
                  >
                    <span>Open Project...</span>
                    <span className="dropdown-shortcut">Ctrl+O</span>
                  </button>
                  <button
                    type="button"
                    className="dropdown-item"
                    disabled={!source.trim()}
                    onClick={() => {
                      setActiveDropdown(null);
                      void saveCurrent();
                    }}
                  >
                    <span>Save Project</span>
                    <span className="dropdown-shortcut">Ctrl+S</span>
                  </button>
                  <button
                    type="button"
                    className="dropdown-item"
                    disabled={!parsed}
                    onClick={() => {
                      setActiveDropdown(null);
                      showModal('experiment', `${name} · ${new Date().toLocaleDateString()}`.slice(0, 100));
                    }}
                  >
                    <span>Save Experiment Snapshot...</span>
                    <span className="dropdown-shortcut">Ctrl+Shift+S</span>
                  </button>
                  <div className="dropdown-divider" />
                  <button
                    type="button"
                    className="dropdown-item"
                    onClick={() => {
                      setActiveDropdown(null);
                      void navigator.clipboard.writeText(source);
                      setNotice('Python circuit code copied to clipboard');
                    }}
                  >
                    <span>Copy Qiskit Python Code</span>
                  </button>
                  <button
                    type="button"
                    className="dropdown-item"
                    disabled={!parsed?.qasm}
                    onClick={() => {
                      setActiveDropdown(null);
                      if (parsed?.qasm) {
                        void navigator.clipboard.writeText(parsed.qasm);
                        setNotice('OpenQASM 2.0 copied to clipboard');
                      }
                    }}
                  >
                    <span>Copy OpenQASM 2.0</span>
                  </button>
                  <div className="dropdown-divider" />
                  <button
                    type="button"
                    className="dropdown-item"
                    onClick={() => {
                      setActiveDropdown(null);
                      setIsSettingsOpen(true);
                    }}
                  >
                    <span>Preferences & Settings</span>
                    <span className="dropdown-shortcut">Ctrl+,</span>
                  </button>
                </div>
              )}
            </div>

            {/* Edit Menu */}
            <div className="menu-dropdown-container">
              <button
                type="button"
                className={`menu-text-btn ${activeDropdown === 'Edit' ? 'active-menu' : ''}`}
                onClick={(e) => {
                  e.stopPropagation();
                  setActiveDropdown((cur) => cur === 'Edit' ? null : 'Edit');
                }}
                onMouseEnter={() => {
                  if (activeDropdown !== null) setActiveDropdown('Edit');
                }}
              >
                Edit
              </button>
              {activeDropdown === 'Edit' && (
                <div className="classic-dropdown-menu" onClick={(e) => e.stopPropagation()}>
                  <button
                    type="button"
                    className="dropdown-item"
                    onClick={() => {
                      setActiveDropdown(null);
                      formatCode();
                    }}
                  >
                    <span>Format Circuit Code</span>
                    <span className="dropdown-shortcut">Shift+Alt+F</span>
                  </button>
                  <button
                    type="button"
                    className="dropdown-item"
                    onClick={() => {
                      setActiveDropdown(null);
                      safeSwitch(() => {
                        setSource('');
                        setBaseline('');
                        clearResults();
                      });
                    }}
                  >
                    <span>Clear Editor Buffer</span>
                  </button>
                  <div className="dropdown-divider" />
                  {examples.slice(0, 4).map((ex) => (
                    <button
                      key={ex.id}
                      type="button"
                      className="dropdown-item"
                      onClick={() => {
                        setActiveDropdown(null);
                        safeSwitch(() => void loadSource(ex.source, ex.name, null));
                      }}
                    >
                      <span>Load: {ex.name}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Quantum Menu (All quantum simulation, transpilation & analysis consolidated) */}
            <div className="menu-dropdown-container">
              <button
                type="button"
                className={`menu-text-btn ${activeDropdown === 'Quantum' ? 'active-menu' : ''}`}
                onClick={(e) => {
                  e.stopPropagation();
                  setActiveDropdown((cur) => cur === 'Quantum' ? null : 'Quantum');
                }}
                onMouseEnter={() => {
                  if (activeDropdown !== null) setActiveDropdown('Quantum');
                }}
              >
                Quantum
              </button>
              {activeDropdown === 'Quantum' && (
                <div className="classic-dropdown-menu" onClick={(e) => e.stopPropagation()}>
                  <button
                    type="button"
                    className="dropdown-item"
                    disabled={!!busy || !source.trim()}
                    onClick={() => {
                      setActiveDropdown(null);
                      void execute('simulate');
                    }}
                  >
                    <span>▶ Run AerSimulator Kernel</span>
                    <span className="dropdown-shortcut">F5</span>
                  </button>
                  <button
                    type="button"
                    className="dropdown-item"
                    disabled={!!busy || !source.trim()}
                    onClick={() => {
                      setActiveDropdown(null);
                      void execute('optimize');
                    }}
                  >
                    <span>⚡ Transpile & Optimize Circuit</span>
                    <span className="dropdown-shortcut">Ctrl+Shift+B</span>
                  </button>
                  <button
                    type="button"
                    className="dropdown-item"
                    onClick={() => {
                      setActiveDropdown(null);
                      setIsHudOpen((v) => !v);
                    }}
                  >
                    <span>{isHudOpen ? 'Hide' : 'Show'} Circuit Live HUD</span>
                  </button>
                  <div className="dropdown-divider" />
                  <button
                    type="button"
                    className="dropdown-item"
                    onClick={() => {
                      setActiveDropdown(null);
                      setInspectorTab('bloch');
                    }}
                  >
                    <span>Inspect 3D Bloch Spheres</span>
                  </button>
                  <button
                    type="button"
                    className="dropdown-item"
                    onClick={() => {
                      setActiveDropdown(null);
                      setInspectorTab('unitary');
                    }}
                  >
                    <span>Inspect Unitary Operator Matrix (U)</span>
                  </button>
                  <button
                    type="button"
                    className="dropdown-item"
                    onClick={() => {
                      setActiveDropdown(null);
                      setInspectorTab('circuit');
                    }}
                  >
                    <span>Inspect Circuit Wire Diagram</span>
                  </button>
                  <div className="dropdown-divider" />
                  <button
                    type="button"
                    className="dropdown-item"
                    onClick={() => {
                      setActiveDropdown(null);
                      setLevel('1');
                      void execute('optimize');
                    }}
                  >
                    <span>Transpiler: Level 1 (Light)</span>
                  </button>
                  <button
                    type="button"
                    className="dropdown-item"
                    onClick={() => {
                      setActiveDropdown(null);
                      setLevel('2');
                      void execute('optimize');
                    }}
                  >
                    <span>Transpiler: Level 2 (Balanced Default)</span>
                  </button>
                  <button
                    type="button"
                    className="dropdown-item"
                    onClick={() => {
                      setActiveDropdown(null);
                      setLevel('3');
                      void execute('optimize');
                    }}
                  >
                    <span>Transpiler: Level 3 (Aggressive Synthesis)</span>
                  </button>
                </div>
              )}
            </div>

            {/* View Menu */}
            <div className="menu-dropdown-container">
              <button
                type="button"
                className={`menu-text-btn ${activeDropdown === 'View' ? 'active-menu' : ''}`}
                onClick={(e) => {
                  e.stopPropagation();
                  setActiveDropdown((cur) => cur === 'View' ? null : 'View');
                }}
                onMouseEnter={() => {
                  if (activeDropdown !== null) setActiveDropdown('View');
                }}
              >
                View
              </button>
              {activeDropdown === 'View' && (
                <div className="classic-dropdown-menu" onClick={(e) => e.stopPropagation()}>
                  <button
                    type="button"
                    className="dropdown-item"
                    onClick={() => {
                      setActiveDropdown(null);
                      setSidebar(!sidebar);
                    }}
                  >
                    <span>Toggle Workspace Explorer</span>
                    <span className="dropdown-shortcut">Ctrl+B</span>
                  </button>
                  <button
                    type="button"
                    className="dropdown-item"
                    onClick={() => {
                      setActiveDropdown(null);
                      setIsTerminalOpen((v) => !v);
                    }}
                  >
                    <span>Toggle Integrated Terminal</span>
                    <span className="dropdown-shortcut">Ctrl+`</span>
                  </button>
                  <button
                    type="button"
                    className="dropdown-item"
                    onClick={() => {
                      setActiveDropdown(null);
                      setIsHudOpen((v) => !v);
                    }}
                  >
                    <span>Toggle Wire Map Live HUD</span>
                  </button>
                  <div className="dropdown-divider" />
                  <button
                    type="button"
                    className="dropdown-item"
                    onClick={() => {
                      setActiveDropdown(null);
                      setTab('Studio');
                    }}
                  >
                    <span>Studio (Editor & Circuit)</span>
                  </button>
                  <button
                    type="button"
                    className="dropdown-item"
                    onClick={() => {
                      setActiveDropdown(null);
                      setTab('Lab');
                    }}
                  >
                    <span>Lab (Aer Simulation & Sampling)</span>
                  </button>
                  <button
                    type="button"
                    className="dropdown-item"
                    onClick={() => {
                      setActiveDropdown(null);
                      setTab('Forge');
                    }}
                  >
                    <span>Forge (Transpilation Depth & Gates)</span>
                  </button>
                  <button
                    type="button"
                    className="dropdown-item"
                    onClick={() => {
                      setActiveDropdown(null);
                      setTab('Research');
                    }}
                  >
                    <span>Research (Experiment Snapshots)</span>
                  </button>
                  <div className="dropdown-divider" />
                  <button
                    type="button"
                    className="dropdown-item"
                    onClick={() => {
                      setActiveDropdown(null);
                      setIsPaletteOpen(true);
                    }}
                  >
                    <span>Command Palette...</span>
                    <span className="dropdown-shortcut">Ctrl+K</span>
                  </button>
                </div>
              )}
            </div>

            {/* Terminal Menu */}
            <div className="menu-dropdown-container">
              <button
                type="button"
                className={`menu-text-btn ${activeDropdown === 'Terminal' ? 'active-menu' : ''}`}
                onClick={(e) => {
                  e.stopPropagation();
                  setActiveDropdown((cur) => cur === 'Terminal' ? null : 'Terminal');
                }}
                onMouseEnter={() => {
                  if (activeDropdown !== null) setActiveDropdown('Terminal');
                }}
              >
                Terminal
              </button>
              {activeDropdown === 'Terminal' && (
                <div className="classic-dropdown-menu" onClick={(e) => e.stopPropagation()}>
                  <button
                    type="button"
                    className="dropdown-item"
                    onClick={() => {
                      setActiveDropdown(null);
                      setIsTerminalOpen(true);
                    }}
                  >
                    <span>Open Quantum Terminal</span>
                    <span className="dropdown-shortcut">Ctrl+`</span>
                  </button>
                  <button
                    type="button"
                    className="dropdown-item"
                    onClick={() => {
                      setActiveDropdown(null);
                      setIsTerminalOpen(true);
                      void execute('simulate');
                    }}
                  >
                    <span>Run Kernel in Terminal</span>
                  </button>
                  <button
                    type="button"
                    className="dropdown-item"
                    onClick={() => {
                      setActiveDropdown(null);
                      setIsTerminalOpen(true);
                      void execute('optimize');
                    }}
                  >
                    <span>Run Transpile in Terminal</span>
                  </button>
                </div>
              )}
            </div>

            {/* Help Menu */}
            <div className="menu-dropdown-container">
              <button
                type="button"
                className={`menu-text-btn ${activeDropdown === 'Help' ? 'active-menu' : ''}`}
                onClick={(e) => {
                  e.stopPropagation();
                  setActiveDropdown((cur) => cur === 'Help' ? null : 'Help');
                }}
                onMouseEnter={() => {
                  if (activeDropdown !== null) setActiveDropdown('Help');
                }}
              >
                Help
              </button>
              {activeDropdown === 'Help' && (
                <div className="classic-dropdown-menu" onClick={(e) => e.stopPropagation()}>
                  <button
                    type="button"
                    className="dropdown-item"
                    onClick={() => {
                      setActiveDropdown(null);
                      setIsPaletteOpen(true);
                    }}
                  >
                    <span>Command Palette & Shortcuts</span>
                    <span className="dropdown-shortcut">Ctrl+K</span>
                  </button>
                  <button
                    type="button"
                    className="dropdown-item"
                    onClick={() => {
                      setActiveDropdown(null);
                      setNotice('Qiskit Aer 0.18.0 & Python 3.12 operational on local kernel');
                    }}
                  >
                    <span>Qiskit Aer Diagnostics</span>
                  </button>
                  <button
                    type="button"
                    className="dropdown-item"
                    onClick={() => {
                      setActiveDropdown(null);
                      setIsSettingsOpen(true);
                    }}
                  >
                    <span>Settings & Preferences</span>
                    <span className="dropdown-shortcut">Ctrl+,</span>
                  </button>
                  <button type="button" className="dropdown-item" onClick={() => { setActiveDropdown(null); window.open('https://github.com/ganeshkumarchalla/Qore_Documentation', '_blank', 'noopener,noreferrer'); }}>
                    <span>Quantum Lab Documentation ↗</span>
                  </button>
                  <button type="button" className="dropdown-item" onClick={() => { setActiveDropdown(null); window.open('https://github.com/ganeshkumarchalla/Qore_Documentation', '_blank', 'noopener,noreferrer'); }}>
                    <span>Quantum Ledger Documentation ↗</span>
                  </button>
                  <div className="dropdown-divider" />
                  <button
                    type="button"
                    className="dropdown-item"
                    onClick={() => {
                      setActiveDropdown(null);
                      setNotice('QORE Studio v2.0 — Enterprise Quantum Computing IDE');
                    }}
                  >
                    <span>About QORE Quantum Studio</span>
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Centered QORE Studio Command Center */}
        <div
          className="topbar-command-center"
          onClick={() => setIsPaletteOpen(true)}
          title="Open Command Palette (Ctrl+K or Ctrl+Shift+P)"
        >
          <Icon name="search" size={13} />
          <span className="command-center-title">{name.includes('.') ? name : `${name}.py`}</span>
          <kbd className="command-kbd">Ctrl+K</kbd>
        </div>

        {/* Right Workbench Actions: Consolidated Quantum Execution Hub & Telemetry */}
        <div className="workbench-actions">
          {/* Clean Telemetry Readout */}
          <div className="topbar-telemetry">
            <span className="telemetry-item highlight" title="Active Quantum Register Width">
              {parsed?.metrics?.qubits ?? (source.includes('qreg') ? 2 : 2)} Qubits
            </span>
            <span className="telemetry-dot">·</span>
            <span className="telemetry-item" title="Circuit Depth">
              Depth: {parsed?.metrics?.depth ?? 0}
            </span>
            <span className="telemetry-dot">·</span>
            <span className="telemetry-item" title="Total Gate Count">
              {parsed?.metrics?.gate_count ?? 0} Gates
            </span>
            <span className="telemetry-dot">·</span>
            <span
              className={`telemetry-item ${(parsed?.metrics?.two_qubit_gate_count ?? 0) > 0 ? 'entangled-text' : ''}`}
              title={(parsed?.metrics?.two_qubit_gate_count ?? 0) > 0 ? 'Entangled Multi-Qubit State (Bell/EPR)' : 'Separable Product State'}
            >
              {(parsed?.metrics?.two_qubit_gate_count ?? 0) > 0 ? 'Entangled' : 'Separable'}
            </span>
          </div>

          <div className="toolbar-divider" />

          {/* Unified Primary Quantum Run Action Hub */}
          <div className="unified-run-group">
            <button
              type="button"
              className={`primary-run-button ${busy ? 'busy-pulsing' : ''}`}
              disabled={!!busy || !source.trim()}
              onClick={() => void execute('simulate')}
              title="Run Quantum Simulation on AerSimulator (Ctrl+Enter / F5)"
            >
              {busy ? (
                <>
                  <span className="quantum-spinner" />
                  <span>{busy}...</span>
                </>
              ) : (
                <>
                  <Icon name="play" size={13} />
                  <span>Run Kernel</span>
                </>
              )}
            </button>
            <button
              type="button"
              className={`run-chevron-btn ${isRunMenuOpen ? 'active' : ''}`}
              disabled={!!busy}
              onClick={() => setIsRunMenuOpen(!isRunMenuOpen)}
              title="Quantum execution options"
            >
              <Icon name="chevron" size={12} />
            </button>

            {isRunMenuOpen && (
              <div className="classic-dropdown-menu run-dropdown-menu">
                <button
                  type="button"
                  className="dropdown-item"
                  onClick={() => {
                    setIsRunMenuOpen(false);
                    void execute('simulate');
                  }}
                >
                  <span>Run AerSimulator (Default)</span>
                  <span className="dropdown-shortcut">F5</span>
                </button>
                <button
                  type="button"
                  className="dropdown-item"
                  onClick={() => {
                    setIsRunMenuOpen(false);
                    void execute('optimize');
                  }}
                >
                  <span>Transpile & Optimize</span>
                  <span className="dropdown-shortcut">Ctrl+Shift+B</span>
                </button>
                <button
                  type="button"
                  className="dropdown-item"
                  onClick={() => {
                    setIsRunMenuOpen(false);
                    setIsHudOpen((v) => !v);
                  }}
                >
                  <span>Toggle Live Circuit HUD</span>
                </button>
                <div className="dropdown-divider" />
                <button
                  type="button"
                  className="dropdown-item"
                  onClick={() => {
                    setIsRunMenuOpen(false);
                    showModal('experiment', `${name} · ${new Date().toLocaleDateString()}`.slice(0, 100));
                  }}
                >
                  <span>Save Experiment Snapshot</span>
                  <span className="dropdown-shortcut">Ctrl+Shift+S</span>
                </button>
              </div>
            )}
          </div>

          {/* Sleek Utility Actions */}
          <div className="topbar-util-actions">
            <button
              type="button"
              className={`topbar-util-btn ${isTerminalOpen ? 'active' : ''}`}
              onClick={() => setIsTerminalOpen(!isTerminalOpen)}
              title="Toggle Integrated Quantum Terminal (Ctrl+`)"
            >
              <Icon name="terminal" size={14} />
            </button>
          </div>
        </div>
      </header>

      {/* Dynamic Quantum Gradient Flow Line (Active while loading / running) */}
      {busy && <div className="quantum-ambient-gradient-bar" />}

      {/* Workspace Row (Activity Bar + Explorer placed down below the upper bar) */}
      <div className="workbench-workspace-row">
        {/* 1. Activity Bar */}
        <aside className="activity-bar" aria-label="Activity Bar">
          <div className="activity-top">
            <button
              className={`activity-item ${sidebar ? 'active-sidebar' : ''}`}
              title="Explorer (Toggle Sidebar)"
              onClick={() => setSidebar(!sidebar)}
              aria-label="Toggle Explorer"
            >
              <Icon name="explorer" size={20} />
            </button>

            <div className="activity-divider" />

            {tabs.map((item) => (
              <button
                key={item.name}
                className={`activity-item ${tab === item.name ? 'active' : ''}`}
                title={`${item.shortLabel} view`}
                onClick={() => setTab(item.name)}
                aria-label={item.label}
              >
                <Icon name={item.icon} size={20} />
                {item.name === 'Intelligence' && <span className="activity-badge">AI</span>}
              </button>
            ))}
          </div>

          <div className="activity-bottom">
            <button
              className="activity-item"
              title={currentUser ? `Account: ${currentUser.name} (${currentUser.role})` : 'Sign In / Account (VS Code & Antigravity Cloud)'}
              aria-label="Account"
              onClick={() => setIsAuthOpen(true)}
            >
              {currentUser ? (
                <div className="activity-avatar-pill">
                  <span>{currentUser.avatarInitials}</span>
                  <span className="activity-avatar-dot" />
                </div>
              ) : (
                <Icon name="account" size={20} />
              )}
            </button>
            <button
              className="activity-item"
              title="Settings & Preferences (Ctrl+,)"
              aria-label="Open Settings"
              onClick={() => setIsSettingsOpen(true)}
            >
              <Icon name="gear" size={20} />
            </button>
            <span
              className={`activity-status ${health ? 'online' : 'offline'}`}
              title={health ? 'Backend Connected (Aer Simulator)' : 'Backend Disconnected'}
            >
              <i />
            </span>
          </div>
        </aside>

        {/* 2. Advanced VS Code Workspace File Explorer */}
        <Explorer
          sidebarOpen={sidebar}
          activeFileId={activeFileId}
          onOpenFile={handleOpenFile}
          dirty={dirty}
          projects={projects}
          experiments={experiments}
          onOpenProject={(id) => safeSwitch(() => void openProject(id))}
          onOpenExperiment={(id) => safeSwitch(() => void openExperimentInStudio(id))}
          onNewProject={() => safeSwitch(() => showModal('new', 'Untitled project'))}
          onRefresh={() => void initialize()}
          busy={!!busy}
          onRunKernel={() => void execute('simulate')}
          onTranspile={() => void execute('optimize')}
          shots={shots}
          onSetShots={setShots}
          optLevel={level}
          onSetOptLevel={setLevel}
        />

        {/* 3. Main Workspace Area */}
        <main className="vscode-main">
          {/* Notifications & Banners */}
        {historical && (
          <div className="workbench-banner historical">
            <Icon name="clock" size={14} />
            <span>Viewing historical experiment snapshot from {formatDate(historical.created_at)}. Source and outputs are read-only.</span>
            <button
              className="banner-action"
              onClick={() => {
                leaveHistorical();
                setTab('Studio');
              }}
            >
              Copy to editable draft
            </button>
          </div>
        )}

        {error && (
          <div className="workbench-banner error" role="alert">
            <Icon name="info" size={14} />
            <span>{error}</span>
            {!health && (
              <button className="banner-action" onClick={() => void initialize()} disabled={!!busy}>
                Reconnect
              </button>
            )}
            <button className="icon-close" aria-label="Dismiss error" onClick={() => setError('')}>
              <Icon name="close" size={12} />
            </button>
          </div>
        )}

        {notice && (
          <div className="workbench-banner notice" role="status">
            <Icon name="check" size={14} />
            <span>{notice}</span>
            <button className="icon-close" aria-label="Dismiss notification" onClick={() => setNotice('')}>
              <Icon name="close" size={12} />
            </button>
          </div>
        )}

        {/* Active View Container */}
        <div className="workbench-body">
          {tab === 'Studio' && (
            <div className="studio-split-view">
              {/* Left Pane: Code Editor with Gate Palette */}
              <section className="editor-pane">
                <div className="pane-titlebar spread">
                  <div className="pane-title-left">
                    <span className="pane-name">
                      {name.includes('.') ? name : (source.trim().startsWith('OPENQASM') || source.includes('qreg ') ? `${name}.qasm` : `${name}.py`)}
                    </span>
                    <span className="pane-meta">
                      {source.trim().startsWith('OPENQASM') || source.includes('qreg ') ? 'OpenQASM 2.0 / 3.0' : 'Python · Bounded AST'}
                    </span>
                    {(source.trim().startsWith('OPENQASM') || source.includes('qreg ')) && (
                      <span className="mini-tag" style={{ marginLeft: 6 }}>Direct QASM</span>
                    )}
                  </div>
                  <div className="pane-title-actions">
                    <button
                      type="button"
                      className="icon-action-btn"
                      title="Command Palette (Ctrl+K)"
                      onClick={() => setIsPaletteOpen(true)}
                    >
                      <Icon name="search" size={13} />
                    </button>
                    <button
                      type="button"
                      className="icon-action-btn"
                      title="Settings (Ctrl+,)"
                      onClick={() => setIsSettingsOpen(true)}
                    >
                      <Icon name="gear" size={13} />
                    </button>
                  </div>
                </div>

                {/* Gate Quick-Insert Palette */}
                <GatePalette onInsert={insertSnippet} />

                {/* Collapsible Live Quantum Circuit Wire HUD */}
                {isHudOpen && (
                  <div className="quantum-hud-panel">
                    <div className="hud-header">
                      <span className="hud-title">
                        <Icon name="circuit" size={13} />
                        Live Quantum Wire Map
                      </span>
                      <span className="hud-subtitle">
                        Real-time topological wire map synthesized from QORE-IR operations
                      </span>
                    </div>

                    <div className="hud-wire-map">
                      {Array.from({ length: Math.min(parsed?.metrics?.qubits ?? 2, 6) }).map((_, q) => {
                        const opsOnQ = parsed?.ir?.operations?.filter((op) => op.qubits.includes(q)) ?? [];
                        return (
                          <div key={q} className="wire-line">
                            <span className="wire-label">q[{q}]</span>
                            <span className="wire-dash">──</span>
                            <div className="wire-rail">
                              {opsOnQ.length === 0 ? (
                                <span className="wire-dash">────────────────────── (idle wire)</span>
                              ) : (
                                opsOnQ.map((op, idx) => {
                                  const isTwoQubit = op.qubits.length > 1;
                                  const isMeas = op.name === 'measure';
                                  return (
                                    <span key={idx} style={{ display: 'inline-flex', alignItems: 'center' }}>
                                      <span
                                        className={`wire-gate-box ${isTwoQubit ? 'two-qubit' : ''} ${isMeas ? 'wire-measure-box' : ''}`}
                                        title={`${op.name.toUpperCase()} on qubits [${op.qubits.join(', ')}]`}
                                      >
                                        {op.name.toUpperCase()}
                                        {op.qubits.length > 1 ? `[${op.qubits.join(',')}]` : ''}
                                      </span>
                                      <span className="wire-dash">──</span>
                                    </span>
                                  );
                                })
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>

                    <div className="hud-bottom-row">
                      <div className="hud-stats-row">
                        <div className="hud-stat-item">
                          <span>Entangling Ratio:</span>
                          <span className="hud-stat-val">
                            {Math.round(
                              ((parsed?.metrics?.two_qubit_gate_count ?? 0) /
                                Math.max(1, parsed?.metrics?.gate_count ?? 1)) *
                                100
                            )}
                            %
                          </span>
                        </div>
                        <div className="hud-stat-item">
                          <span>Classification:</span>
                          <span className="hud-stat-val">
                            {(parsed?.metrics?.two_qubit_gate_count ?? 0) > 0 &&
                            !parsed?.ir?.operations.some((o) =>
                              ['t', 'tdg', 'rx', 'ry', 'rz', 'u', 'p', 'cp'].includes(o.name)
                            )
                              ? 'Clifford Tableau (Poly-Time)'
                              : 'Universal Quantum'}
                          </span>
                        </div>
                      </div>

                      <div className="archetype-chips">
                        <span style={{ fontSize: 10, color: 'var(--vscode-text-dim)' }}>Archetypes:</span>
                        <button
                          type="button"
                          className="archetype-chip"
                          onClick={() => {
                            void loadSource(
                              'from qiskit import QuantumCircuit\n\nqc = QuantumCircuit(2, 2)\nqc.h(0)\nqc.cx(0, 1)\nqc.measure([0, 1], [0, 1])\n',
                              'Bell State |Φ+⟩',
                              null
                            );
                          }}
                        >
                          + Bell |Φ+⟩
                        </button>
                        <button
                          type="button"
                          className="archetype-chip"
                          onClick={() => {
                            void loadSource(
                              'from qiskit import QuantumCircuit\n\nqc = QuantumCircuit(3, 3)\nqc.h(0)\nqc.cx(0, 1)\nqc.cx(1, 2)\nqc.measure([0, 1, 2], [0, 1, 2])\n',
                              'GHZ Triplet |GHZ⟩',
                              null
                            );
                          }}
                        >
                          + GHZ |000⟩+|111⟩
                        </button>
                        <button
                          type="button"
                          className="archetype-chip"
                          onClick={() => {
                            void loadSource(
                              'import numpy as np\nfrom qiskit import QuantumCircuit\n\nqc = QuantumCircuit(3, 3)\nqc.h(0)\nqc.cp(np.pi / 2, 1, 0)\nqc.cp(np.pi / 4, 2, 0)\nqc.h(1)\nqc.cp(np.pi / 2, 2, 1)\nqc.h(2)\nqc.swap(0, 2)\nqc.measure([0, 1, 2], [0, 1, 2])\n',
                              'QFT 3-Qubit Circuit',
                              null
                            );
                          }}
                        >
                          + QFT 3-Qubit
                        </button>
                      </div>
                    </div>
                  </div>
                )}

                <div className="pane-content editor-wrapper">
                  <ErrorBoundary label="Source editor" className="fill-fallback">
                    <Editor
                    height="100%"
                    language={activeFileId.endsWith('.md') ? 'markdown' : activeFileId.endsWith('.json') ? 'json' : activeFileId.endsWith('.qasm') ? 'c' : 'python'}
                    theme="qore"
                    value={source}
                    onMount={(editor) => { editorRef.current = editor; }}
                    onChange={(val) => editSource(val ?? '')}
                    loading={<div className="editor-loading"><span className="spinner" /> Loading editor…</div>}
                    options={{
                      minimap: { enabled: settings.minimap },
                      fontSize: settings.fontSize,
                      lineHeight: Math.round(settings.fontSize * 1.6),
                      fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
                      autoClosingBrackets: (settings.autoCloseBrackets ?? true) ? 'always' : 'never',
                      autoClosingQuotes: (settings.autoCloseBrackets ?? true) ? 'always' : 'never',
                      formatOnPaste: settings.formatOnSave ?? true,
                      padding: { top: 12, bottom: 12 },
                      scrollBeyondLastLine: false,
                      automaticLayout: true,
                      tabSize: settings.tabSize,
                      wordWrap: settings.wordWrap ? 'on' : 'off',
                      lineNumbers: settings.lineNumbers as any,
                      cursorStyle: settings.cursorStyle as any,
                      cursorBlinking: 'smooth',
                      cursorSmoothCaretAnimation: 'on',
                      smoothScrolling: true,
                      guides: { bracketPairs: true, indentation: true },
                      bracketPairColorization: { enabled: settings.bracketPairColorization },
                      readOnly: !!historical,
                      renderLineHighlight: 'all',
                      overviewRulerBorder: false,
                      folding: true,
                      lineNumbersMinChars: 3,
                    }}
                    />
                  </ErrorBoundary>
                </div>
                <div className="pane-statusbar">
                  <span>UTF-8</span>
                  <span>{source.split('\n').length} lines</span>
                  <span>{source.length} bytes</span>
                  <span
                    className="noise-status-tag"
                    title="Click to configure in Settings"
                    onClick={() => setIsSettingsOpen(true)}
                  >
                    {settings.noiseSimulation
                      ? `Noise (p=${settings.depolarizingRate}, ro=${settings.readoutErrorRate})`
                      : 'Ideal Simulation (Noiseless)'}
                  </span>
                </div>
              </section>

              {/* Right Pane: Circuit Preview & Inspector */}
              <section className="preview-pane">
                <div className="pane-titlebar inspector-tabs-head">
                  <div className="inspector-subtabs">
                    <button
                      type="button"
                      className={`inspector-tab-btn ${inspectorTab === 'circuit' ? 'active' : ''}`}
                      onClick={() => setInspectorTab('circuit')}
                    >
                      <Icon name="circuit" size={13} />
                      <span>Circuit Diagram</span>
                    </button>
                    <button
                      type="button"
                      className={`inspector-tab-btn ${inspectorTab === 'bloch' ? 'active' : ''}`}
                      onClick={() => setInspectorTab('bloch')}
                    >
                      <Icon name="lab" size={13} />
                      <span>Bloch Spheres ({parsed?.bloch_vectors?.length ?? 0})</span>
                    </button>
                    <button
                      type="button"
                      className={`inspector-tab-btn ${inspectorTab === 'unitary' ? 'active' : ''}`}
                      onClick={() => setInspectorTab('unitary')}
                    >
                      <Icon name="code" size={13} />
                      <span>Unitary (U)</span>
                    </button>
                    <button
                      type="button"
                      className={`inspector-tab-btn ${inspectorTab === 'qasm' ? 'active' : ''}`}
                      onClick={() => setInspectorTab('qasm')}
                    >
                      <Icon name="copy" size={13} />
                      <span>OpenQASM</span>
                    </button>
                  </div>
                </div>

                <div className="pane-content preview-scroll">
                  {inspectorTab === 'circuit' && (
                    <ErrorBoundary label="Circuit visualizer">
                      <>
                      <div className="circuit-view-box">
                        <Circuit ir={parsed?.ir ?? null} />
                      </div>

                      <div className="preview-metrics-box">
                        <div className="section-head spread">
                          <h3>Resource Analysis</h3>
                          <span className="mini-tag">Framework Metrics</span>
                        </div>
                        <MetricCards metrics={parsed?.metrics ?? null} />

                        {parsed && (
                          <details className="metric-details">
                            <summary>Gate Type Distribution & Definitions</summary>
                            <div className="gate-stats">
                              {Object.entries(parsed.metrics.gate_types).map(([gate, count]) => (
                                <span key={gate}>
                                  <code>{gate.toUpperCase()}</code> {count}
                                </span>
                              ))}
                            </div>
                            <p className="help">{readable(parsed.metrics.definition)}</p>
                            <p className="help">
                              {parsed.metrics.measurement_count} measurement(s) · {parsed.metrics.barrier_count} barrier(s) · {parsed.metrics.clbits} classical bit(s)
                            </p>
                          </details>
                        )}
                      </div>
                      <Warnings warnings={parsed?.warnings ?? []} />
                      </>
                    </ErrorBoundary>
                  )}

                  {inspectorTab === 'bloch' && (
                    <div className="inspector-content-box">
                      <ErrorBoundary label="Bloch sphere visualizer">
                        <BlochSphereViewer vectors={parsed?.bloch_vectors} />
                      </ErrorBoundary>
                    </div>
                  )}

                  {inspectorTab === 'unitary' && (
                    <div className="inspector-content-box">
                      <ErrorBoundary label="Unitary matrix visualizer">
                        <UnitaryMatrixViewer matrix={parsed?.unitary_matrix} />
                      </ErrorBoundary>
                    </div>
                  )}

                  {inspectorTab === 'qasm' && (
                    <div className="inspector-content-box">
                      <ErrorBoundary label="OpenQASM viewer">
                        <QasmViewer qasm={parsed?.qasm} />
                      </ErrorBoundary>
                    </div>
                  )}
                </div>
              </section>
            </div>
          )}

          {tab === 'Lab' && (
            <ErrorBoundary label="QORE Lab">
              <div className="lab-view-shell">
                <Lab run={simulation} historical={!!historical} />
              </div>
            </ErrorBoundary>
          )}
          {tab === 'Forge' && (
            <Forge run={optimization} historical={!!historical} onApprove={() => showModal('approve')} busy={!!busy} />
          )}
          {tab === 'Research' && (
            <Research
              experiments={experiments}
              selected={selectedExperiment}
              onOpen={(id) => safeSwitch(() => void openExperimentInStudio(id))}
              onSelect={(id) => void selectExperimentInResearch(id)}
              onRestore={(id) => safeSwitch(() => void restoreExperimentAsDraft(id))}
              busy={!!busy}
            />
          )}
          {tab === 'Intelligence' && (
            <Intelligence
              key={`${source.length}-${parsed?.source_hash ?? 'unparsed'}-${simulation?.id ?? ''}-${optimization?.id ?? ''}`}
              source={source}
              simulation={simulation}
              optimization={optimization}
              health={health}
            />
          )}
        </div>

        {/* 4. Integrated Animated Quantum Terminal Dock */}
        <ErrorBoundary label="Quantum terminal">
          <Terminal
          isOpen={isTerminalOpen}
          onClose={() => setIsTerminalOpen(false)}
          onRunSimulation={() => void execute('simulate')}
          onRunTranspile={() => void execute('optimize')}
          parsed={parsed}
          simulation={simulation}
          optimization={optimization}
          health={health}
          busy={busy}
          source={source}
          fileName={name}
          error={error}
          onSelectProblemLine={(line) => {
            setTab('Studio');
            editorRef.current?.revealLineInCenter(line);
            editorRef.current?.setPosition({ lineNumber: line, column: 1 });
            editorRef.current?.focus();
          }}
          />
        </ErrorBoundary>
      </main>
    </div>

    {/* 4. Studio Telemetry Status Bar (Bottom 24px) - Cleaned to show only essential info */}
    <footer className="vscode-statusbar">
      <div className="status-left">
        <span className="status-item brand-item" title="QORE Quantum Kernel">
          <span className={`status-dot ${error ? 'error-dot' : ''}`} />
          <span>{busy ? `${busy}…` : error ? 'Simulation error' : health ? 'Qiskit Aer 0.18 (Ready)' : 'Disconnected'}</span>
        </span>
        <span className="status-item" title="Problems detected in workspace">
          <Icon name="info" size={11} />
          <span>{error ? '1 Problem' : '0 Problems'}</span>
        </span>
        <span
          className={`status-item clickable ${isTerminalOpen ? 'active' : ''}`}
          onClick={() => setIsTerminalOpen((v) => !v)}
          title="Toggle Quantum Terminal Dock (Ctrl+`)"
        >
          <Icon name="code" size={11} />
          <span>Terminal</span>
        </span>
      </div>

      <div className="status-right">
        <span className="status-item" title="Circuit Telemetry">
          {parsed ? `${parsed.metrics.qubits}Q · ${parsed.metrics.gate_count} Ops` : '2Q · 2 Ops'}
        </span>
        <span className="status-item">UTF-8</span>
        <span className="status-item">Python 3.12 · Qiskit 2.6.1</span>
      </div>
    </footer>

      {/* Welcome to QORE Animated Splash Modal */}
      <WelcomeModal
        isOpen={isWelcomeOpen}
        onClose={() => setIsWelcomeOpen(false)}
        onSelectCircuit={(src, n) => {
          safeSwitch(() => void loadSource(src, n, null));
          void execute('simulate');
        }}
      />

      {/* Sign In & Sign Up Auth Modal (VS Code & Antigravity Cloud Accounts) */}
      <AuthModal
        isOpen={isAuthOpen}
        onClose={() => setIsAuthOpen(false)}
        currentUser={currentUser}
        onLoginSuccess={(user) => {
          setCurrentUser(user);
          setNotice(`Authenticated as ${user.name} (${user.role}).`);
        }}
        onLogout={() => {
          setCurrentUser(null);
          setNotice('Signed out of QORE.');
        }}
      />

      {/* Settings Modal Dialog */}
      {isSettingsOpen && (
        <SettingsModal
          settings={settings}
          onSave={(updated) => {
            setSettings(updated);
            saveStoredSettings(updated);
            setNotice('Settings saved.');
          }}
          onClose={() => setIsSettingsOpen(false)}
        />
      )}

      {/* Command Palette (Ctrl+K / Ctrl+Shift+P) */}
      <CommandPalette
        isOpen={isPaletteOpen}
        onClose={() => setIsPaletteOpen(false)}
        commands={commands}
      />

      {/* Modal Dialogs */}
      {modal && (
        <div
          className="modal-overlay"
          onMouseDown={(e) => {
            if (e.target === e.currentTarget && !saving) setModal(null);
          }}
        >
          <form
            className="modal-card"
            role="dialog"
            aria-modal="true"
            aria-labelledby="modal-title"
            onSubmit={(e) => void submitModal(e)}
            onKeyDown={(e) => {
              if (e.key === 'Escape' && !saving) setModal(null);
            }}
          >
            <div className="modal-header">
              <h3 id="modal-title">{modalTitles[modal.kind]}</h3>
              <button type="button" className="icon-close" aria-label="Close dialog" disabled={saving} onClick={() => setModal(null)}>
                <Icon name="close" size={14} />
              </button>
            </div>

            <div className="modal-body">
              {modal.kind === 'discard' ? (
                <p className="help">
                  You have unsaved changes in <strong>{name}</strong>. If you proceed, these changes will be lost.
                </p>
              ) : modal.kind === 'approve' ? (
                <>
                  <p className="help">
                    Replace the current editor code with the candidate circuit generated by the compiler?
                  </p>
                  <div className={`validation ${optimization?.validation.status}`}>
                    <Icon name="check" size={14} />
                    <span>{optimization?.validation.status} · {optimization?.validation.method}</span>
                  </div>
                  <p className="help">The candidate will be loaded into the editor as an unsaved edit.</p>
                </>
              ) : (
                <>
                  <label htmlFor="record-name">{modal.kind === 'experiment' ? 'Experiment Name' : 'Project Name'}</label>
                  <input
                    id="record-name"
                    autoFocus
                    required
                    maxLength={100}
                    value={modalName}
                    onChange={(e) => setModalName(e.target.value)}
                    placeholder="Enter name..."
                  />
                  {modal.kind === 'experiment' && (
                    <div className="snapshot-inclusions">
                      <span><Icon name="check" size={12} /> Source code & QORE-IR representation</span>
                      <span>{simulation ? <Icon name="check" size={12} /> : '—'} {simulation ? 'Simulation results attached' : 'No simulation run'}</span>
                      <span>{optimization ? <Icon name="check" size={12} /> : '—'} {optimization ? 'Optimization candidate attached' : 'No optimization run'}</span>
                    </div>
                  )}
                </>
              )}

              {modalError && <div className="error-box" role="alert">{modalError}</div>}
            </div>

            <div className="modal-footer">
              <button type="button" className="button secondary small" disabled={saving} onClick={() => setModal(null)}>
                Cancel
              </button>
              <button
                type="submit"
                className={`button small ${modal.kind === 'discard' ? 'danger' : 'primary'}`}
                disabled={saving}
              >
                {saving && <span className="spinner" />}
                {saving
                  ? 'Saving…'
                  : modal.kind === 'discard'
                  ? 'Discard Changes'
                  : modal.kind === 'approve'
                  ? 'Apply to Editor'
                  : modal.kind === 'new'
                  ? 'Create'
                  : 'Save'}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
