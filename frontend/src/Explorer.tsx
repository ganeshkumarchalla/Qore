import React, { useEffect, useRef, useState } from 'react';
import { Icon } from './Icons';
import { formatDate, type ExperimentSummary, type Project } from './types';

export interface WorkspaceFile {
  id: string;
  name: string;
  path: string;
  type: 'file';
  kind: 'python' | 'qasm' | 'json' | 'markdown';
  source: string;
  qubits?: number;
  readOnly?: boolean;
  projectId?: string;
  experimentId?: string;
}

interface ExplorerProps {
  sidebarOpen: boolean;
  activeFileId: string;
  onOpenFile: (file: WorkspaceFile) => void;
  dirty: boolean;
  projects: Project[];
  experiments: ExperimentSummary[];
  onOpenProject: (id: string) => void;
  onOpenExperiment: (id: string) => void;
  onNewProject: () => void;
  onRefresh: () => void;
  busy: boolean;
  onRunKernel?: () => void;
  onTranspile?: () => void;
  shots?: string;
  onSetShots?: (shots: string) => void;
  optLevel?: string;
  onSetOptLevel?: (level: string) => void;
}

const DEFAULT_CIRCUITS: WorkspaceFile[] = [
  {
    id: 'circuits/circuit.py',
    name: 'circuit.py',
    path: 'circuits/circuit.py',
    type: 'file',
    kind: 'python',
    qubits: 2,
    source: `# 2-Qubit Bell State (Native Qiskit)
from qiskit import QuantumCircuit

qc = QuantumCircuit(2, 2)
qc.h(0)
qc.cx(0, 1)
qc.measure([0, 1], [0, 1])
`,
  },
  {
    id: 'circuits/ghz_state.py',
    name: 'ghz_state.py',
    path: 'circuits/ghz_state.py',
    type: 'file',
    kind: 'python',
    qubits: 3,
    source: `# 3-Qubit Greenberger-Horne-Zeilinger (GHZ) Entangled State
from qiskit import QuantumCircuit

qc = QuantumCircuit(3, 3)
qc.h(0)
qc.cx(0, 1)
qc.cx(1, 2)
qc.measure([0, 1, 2], [0, 1, 2])
`,
  },
  {
    id: 'circuits/teleportation.py',
    name: 'teleportation.py',
    path: 'circuits/teleportation.py',
    type: 'file',
    kind: 'python',
    qubits: 3,
    source: `# Quantum Teleportation Protocol
from qiskit import QuantumCircuit

qc = QuantumCircuit(3, 3)
# State preparation on qubit 0
qc.ry(1.2, 0)

# Entangled Bell pair between Alice (q1) and Bob (q2)
qc.h(1)
qc.cx(1, 2)

# Alice's Bell-basis measurement preparation
qc.cx(0, 1)
qc.h(0)

# Deferred measurement principle: controlled operations
qc.cx(1, 2)
qc.cz(0, 2)

# Terminal measurements
qc.measure([0, 1, 2], [0, 1, 2])
`,
  },
  {
    id: 'circuits/qft_3qubit.py',
    name: 'qft_3qubit.py',
    path: 'circuits/qft_3qubit.py',
    type: 'file',
    kind: 'python',
    qubits: 3,
    source: `# 3-Qubit Quantum Fourier Transform (QFT)
from qiskit import QuantumCircuit
from math import pi

qc = QuantumCircuit(3, 3)
qc.x(0)
qc.x(2)
qc.h(0)
qc.cp(pi / 2, 1, 0)
qc.cp(pi / 4, 2, 0)
qc.h(1)
qc.cp(pi / 2, 2, 1)
qc.h(2)
qc.swap(0, 2)
qc.measure(0, 0)
qc.measure(1, 1)
qc.measure(2, 2)
`,
  },
  {
    id: 'circuits/superdense.py',
    name: 'superdense.py',
    path: 'circuits/superdense.py',
    type: 'file',
    kind: 'python',
    qubits: 2,
    source: `# Superdense Coding Protocol
from qiskit import QuantumCircuit

qc = QuantumCircuit(2, 2)
qc.h(0)
qc.cx(0, 1)
qc.z(0)
qc.x(0)
qc.cx(0, 1)
qc.h(0)
qc.measure(0, 0)
qc.measure(1, 1)
`,
  },
  {
    id: 'circuits/rotation_ordering.py',
    name: 'rotation_ordering.py',
    path: 'circuits/rotation_ordering.py',
    type: 'file',
    kind: 'python',
    qubits: 2,
    source: `# Parametric Rotation with custom classical mapping
from qiskit import QuantumCircuit
from math import pi

qc = QuantumCircuit(2, 2)
qc.ry(pi / 3, 0)
qc.x(1)
qc.measure(0, 1)
qc.measure(1, 0)
`,
  },
];

const DEFAULT_QASM: WorkspaceFile[] = [
  {
    id: 'openqasm/bell_state.qasm',
    name: 'bell_state.qasm',
    path: 'openqasm/bell_state.qasm',
    type: 'file',
    kind: 'qasm',
    qubits: 2,
    source: `OPENQASM 2.0;
include "qelib1.inc";

qreg q[2];
creg c[2];

h q[0];
cx q[0], q[1];
measure q[0] -> c[0];
measure q[1] -> c[1];
`,
  },
  {
    id: 'openqasm/qaoa_cut.qasm',
    name: 'qaoa_cut.qasm',
    path: 'openqasm/qaoa_cut.qasm',
    type: 'file',
    kind: 'qasm',
    qubits: 4,
    source: `OPENQASM 2.0;
include "qelib1.inc";

qreg q[4];
creg c[4];

h q[0];
h q[1];
h q[2];
h q[3];

cx q[0], q[1];
rz(0.45) q[1];
cx q[0], q[1];

cx q[1], q[2];
rz(0.45) q[2];
cx q[1], q[2];

rx(0.62) q[0];
rx(0.62) q[1];
rx(0.62) q[2];
rx(0.62) q[3];

measure q -> c;
`,
  },
];

const README_FILE: WorkspaceFile = {
  id: 'README.md',
  name: 'README.md',
  path: 'README.md',
  type: 'file',
  kind: 'markdown',
  source: `# QORE Quantum Studio Workspace

Advanced desktop-grade quantum development environment powered by Qiskit Aer, Bounded AST verification, and Gemini Quantum Copilot.

## Project Structure
- \`circuits/\`: Native Qiskit Python circuits running via local AerSimulator.
- \`openqasm/\`: OpenQASM 2.0 & 3.0 circuit programs with real-time wire visualization.
- \`experiments/\`: Immutable SQLite reproducibility ledger snapshots.
- \`projects/\`: Persisted multi-experiment projects.
`,
};

export function Explorer({
  sidebarOpen,
  activeFileId,
  onOpenFile,
  dirty,
  projects,
  experiments,
  onOpenProject,
  onOpenExperiment,
  onNewProject,
  onRefresh,
  busy,
  onRunKernel,
  onTranspile,
  shots = '1024',
  onSetShots,
  optLevel = '2',
  onSetOptLevel,
}: ExplorerProps) {
  // Accordion section states (VS Code native style)
  const [sectionsOpen, setSectionsOpen] = useState({
    workspace: true,
    simulation: false,
    transpile: false,
    snapshots: false,
  });

  // Folder expansion states inside the workspace
  const [expandedFolders, setExpandedFolders] = useState<Record<string, boolean>>({
    circuits: true,
    openqasm: true,
    projects: true,
    experiments: false,
  });

  // Custom user files in localStorage
  const [customFiles, setCustomFiles] = useState<WorkspaceFile[]>(() => {
    try {
      const stored = localStorage.getItem('qore_workspace_files');
      return stored ? JSON.parse(stored) : [];
    } catch {
      return [];
    }
  });

  // Inline creation states
  const [isCreatingFile, setIsCreatingFile] = useState(false);
  const [createName, setCreateName] = useState('');
  const [targetFolder, setTargetFolder] = useState('circuits');

  // Inline rename states
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState('');

  // Right-click context menu
  const [contextMenu, setContextMenu] = useState<{
    x: number;
    y: number;
    file: WorkspaceFile;
  } | null>(null);

  const createInputRef = useRef<HTMLInputElement>(null);
  const renameInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isCreatingFile) {
      setTimeout(() => createInputRef.current?.focus(), 50);
    }
  }, [isCreatingFile]);

  useEffect(() => {
    if (renamingId) {
      setTimeout(() => {
        renameInputRef.current?.focus();
        renameInputRef.current?.select();
      }, 50);
    }
  }, [renamingId]);

  useEffect(() => {
    const handleOutsideClick = () => setContextMenu(null);
    window.addEventListener('click', handleOutsideClick);
    return () => window.removeEventListener('click', handleOutsideClick);
  }, []);

  const saveCustomFiles = (files: WorkspaceFile[]) => {
    setCustomFiles(files);
    try {
      localStorage.setItem('qore_workspace_files', JSON.stringify(files));
    } catch {
      // ignore
    }
  };

  const toggleSection = (section: keyof typeof sectionsOpen) => {
    setSectionsOpen((prev) => ({ ...prev, [section]: !prev[section] }));
  };

  const toggleFolder = (folderKey: string) => {
    setExpandedFolders((prev) => ({ ...prev, [folderKey]: !prev[folderKey] }));
  };

  const collapseAll = () => {
    setExpandedFolders({ circuits: false, openqasm: false, projects: false, experiments: false });
  };

  const expandAll = () => {
    setExpandedFolders({ circuits: true, openqasm: true, projects: true, experiments: true });
  };

  const handleCreateCommit = () => {
    const raw = createName.trim();
    if (!raw) {
      setIsCreatingFile(false);
      return;
    }

    const fileName = raw.includes('.') ? raw : `${raw}.py`;
    const isQasm = fileName.endsWith('.qasm');
    const isJson = fileName.endsWith('.json');
    const isMd = fileName.endsWith('.md');
    const kind: WorkspaceFile['kind'] = isQasm ? 'qasm' : isJson ? 'json' : isMd ? 'markdown' : 'python';
    const path = `${targetFolder}/${fileName}`;
    const defaultCode = isQasm
      ? `OPENQASM 2.0;\ninclude "qelib1.inc";\n\nqreg q[2];\ncreg c[2];\n\nh q[0];\ncx q[0], q[1];\nmeasure q -> c;\n`
      : `# ${fileName}\nfrom qiskit import QuantumCircuit\n\nqc = QuantumCircuit(2, 2)\nqc.h(0)\nqc.cx(0, 1)\nqc.measure(0, 0)\nqc.measure(1, 1)\n`;

    const newFile: WorkspaceFile = {
      id: path,
      name: fileName,
      path,
      type: 'file',
      kind,
      qubits: 2,
      source: defaultCode,
    };

    const nextFiles = [newFile, ...customFiles];
    saveCustomFiles(nextFiles);
    onOpenFile(newFile);

    setIsCreatingFile(false);
    setCreateName('');
  };

  const handleRenameCommit = () => {
    if (!renamingId || !renameValue.trim()) {
      setRenamingId(null);
      return;
    }
    const newName = renameValue.trim();
    const updated = customFiles.map((f) => {
      if (f.id === renamingId) {
        const parts = f.path.split('/');
        parts[parts.length - 1] = newName;
        return { ...f, name: newName, path: parts.join('/') };
      }
      return f;
    });
    saveCustomFiles(updated);
    setRenamingId(null);
  };

  const deleteFile = (id: string) => {
    const updated = customFiles.filter((f) => f.id !== id);
    saveCustomFiles(updated);
    if (activeFileId === id) {
      onOpenFile(DEFAULT_CIRCUITS[0]);
    }
  };

  const duplicateFile = (file: WorkspaceFile) => {
    const baseName = file.name.replace(/(\.[^.]+)$/, '');
    const ext = file.name.includes('.') ? file.name.slice(file.name.lastIndexOf('.')) : '.py';
    const copyName = `${baseName}_copy${ext}`;
    const copyPath = `${file.path.split('/')[0]}/${copyName}`;

    const newFile: WorkspaceFile = {
      ...file,
      id: copyPath,
      name: copyName,
      path: copyPath,
    };

    saveCustomFiles([newFile, ...customFiles]);
    onOpenFile(newFile);
  };

  const copyPath = (path: string) => {
    navigator.clipboard?.writeText(path);
  };

  // Clean, uncluttered file icon renderer
  const renderFileIcon = (file: WorkspaceFile) => {
    if (file.kind === 'python' || file.name.endsWith('.py')) {
      return (
        <span className="clean-file-icon py">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 2a5 5 0 0 0-5 5v3h10V7a5 5 0 0 0-5-5z" fill="currentColor" fillOpacity="0.15" />
            <path d="M12 22a5 5 0 0 0 5-5v-3H7v3a5 5 0 0 0 5 5z" fill="currentColor" fillOpacity="0.15" />
            <circle cx="9" cy="6" r="1.5" fill="currentColor" />
            <circle cx="15" cy="18" r="1.5" fill="currentColor" />
          </svg>
        </span>
      );
    }
    if (file.kind === 'qasm' || file.name.endsWith('.qasm')) {
      return (
        <span className="clean-file-icon qasm">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <rect x="3" y="5" width="18" height="14" rx="2" fill="currentColor" fillOpacity="0.15" />
            <line x1="3" y1="12" x2="21" y2="12" />
          </svg>
        </span>
      );
    }
    if (file.kind === 'markdown' || file.name.endsWith('.md')) {
      return (
        <span className="clean-file-icon md">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
          </svg>
        </span>
      );
    }
    return (
      <span className="clean-file-icon json">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <polyline points="6 9 2 12 6 15" />
          <polyline points="18 9 22 12 18 15" />
        </svg>
      </span>
    );
  };

  const circuitsList = [
    ...DEFAULT_CIRCUITS,
    ...customFiles.filter((f) => f.path.startsWith('circuits/')),
  ];

  const qasmList = [
    ...DEFAULT_QASM,
    ...customFiles.filter((f) => f.path.startsWith('openqasm/')),
  ];

  return (
    <nav className={`vscode-sidebar ${sidebarOpen ? 'open' : 'closed'}`} aria-label="Workspace Explorer">
      {/* 1. Single Clean Top Header (VS Code Native) */}
      <div className="vs-explorer-header">
        <span className="vs-explorer-title">EXPLORER</span>
        <div className="vs-explorer-actions">
          <button
            type="button"
            className="vs-action-btn"
            title="New Circuit File (.py)"
            onClick={() => {
              setTargetFolder('circuits');
              setIsCreatingFile(true);
              setExpandedFolders((p) => ({ ...p, circuits: true }));
              setSectionsOpen((p) => ({ ...p, workspace: true }));
            }}
          >
            <Icon name="filePlus" size={13} />
          </button>

          <button
            type="button"
            className="vs-action-btn"
            title="New Project"
            onClick={onNewProject}
          >
            <Icon name="folderPlus" size={13} />
          </button>

          <button
            type="button"
            className="vs-action-btn"
            title="Refresh Explorer"
            onClick={onRefresh}
          >
            <Icon name="refresh" size={12} />
          </button>

          <button
            type="button"
            className="vs-action-btn"
            title={Object.values(expandedFolders).some(Boolean) ? 'Collapse All Folders' : 'Expand All Folders'}
            onClick={Object.values(expandedFolders).some(Boolean) ? collapseAll : expandAll}
          >
            <Icon name="collapse" size={12} />
          </button>
        </div>
      </div>

      <div className="vs-explorer-scroll">
        {/* SECTION 1: WORKSPACE FILES (PRIMARY EXPANDED SECTION) */}
        <div className="vs-accordion-section">
          <div
            className="vs-section-header"
            onClick={() => toggleSection('workspace')}
            title="Click to toggle workspace files"
          >
            <span className={`vs-chevron ${sectionsOpen.workspace ? 'open' : ''}`}>
              <Icon name="chevron" size={10} />
            </span>
            <span className="vs-section-title">WORKSPACE FILES</span>
            <span className="vs-section-count">{circuitsList.length + qasmList.length + projects.length + 1}</span>
          </div>

          {sectionsOpen.workspace && (
            <div className="vs-tree-container">
              {/* Folder: circuits/ */}
              <div className="vs-folder-block">
                <div
                  className="vs-folder-row"
                  onClick={() => toggleFolder('circuits')}
                >
                  <span className={`vs-chevron ${expandedFolders.circuits ? 'open' : ''}`}>
                    <Icon name="chevron" size={9} />
                  </span>
                  <span className="vs-folder-icon">
                    <Icon name="folder" size={13} />
                  </span>
                  <span className="vs-folder-name">circuits</span>
                  <span className="vs-item-count">{circuitsList.length}</span>
                </div>

                {expandedFolders.circuits && (
                  <div className="vs-folder-children">
                    <div className="vs-indent-guide" />
                    {isCreatingFile && targetFolder === 'circuits' && (
                      <div className="vs-inline-create">
                        <span className="clean-file-icon py">
                          <Icon name="circuit" size={12} />
                        </span>
                        <input
                          ref={createInputRef}
                          type="text"
                          className="vs-create-input"
                          placeholder="filename.py"
                          value={createName}
                          onChange={(e) => setCreateName(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') handleCreateCommit();
                            if (e.key === 'Escape') setIsCreatingFile(false);
                          }}
                          onBlur={handleCreateCommit}
                        />
                      </div>
                    )}

                    {circuitsList.map((file) => {
                      const isActive = activeFileId === file.id || activeFileId === file.name;
                      const isRenaming = renamingId === file.id;

                      return (
                        <div
                          key={file.id}
                          className={`vs-file-row ${isActive ? 'active' : ''}`}
                          onClick={() => onOpenFile(file)}
                          onContextMenu={(e) => {
                            e.preventDefault();
                            setContextMenu({ x: e.clientX, y: e.clientY, file });
                          }}
                        >
                          {renderFileIcon(file)}

                          {isRenaming ? (
                            <input
                              ref={renameInputRef}
                              type="text"
                              className="vs-create-input"
                              value={renameValue}
                              onChange={(e) => setRenameValue(e.target.value)}
                              onKeyDown={(e) => {
                                if (e.key === 'Enter') handleRenameCommit();
                                if (e.key === 'Escape') setRenamingId(null);
                              }}
                              onBlur={handleRenameCommit}
                              onClick={(e) => e.stopPropagation()}
                            />
                          ) : (
                            <span className="vs-file-label" title={file.path}>
                              {file.name}
                            </span>
                          )}

                          {file.qubits && <span className="vs-qubit-tag">{file.qubits}q</span>}

                          {isActive && dirty && <span className="vs-dirty-dot" title="Unsaved modifications">●</span>}

                          <div className="vs-hover-tools">
                            <button
                              type="button"
                              className="vs-tool-btn"
                              title="Rename (F2)"
                              onClick={(e) => {
                                e.stopPropagation();
                                setRenamingId(file.id);
                                setRenameValue(file.name);
                              }}
                            >
                              <Icon name="edit" size={11} />
                            </button>
                            {customFiles.some((cf) => cf.id === file.id) && (
                              <button
                                type="button"
                                className="vs-tool-btn danger"
                                title="Delete File"
                                onClick={(e) => {
                                e.stopPropagation();
                                deleteFile(file.id);
                              }}
                              >
                                <Icon name="trash" size={11} />
                              </button>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* Folder: openqasm/ */}
              <div className="vs-folder-block">
                <div
                  className="vs-folder-row"
                  onClick={() => toggleFolder('openqasm')}
                >
                  <span className={`vs-chevron ${expandedFolders.openqasm ? 'open' : ''}`}>
                    <Icon name="chevron" size={9} />
                  </span>
                  <span className="vs-folder-icon">
                    <Icon name="folder" size={13} />
                  </span>
                  <span className="vs-folder-name">openqasm</span>
                  <span className="vs-item-count">{qasmList.length}</span>
                </div>

                {expandedFolders.openqasm && (
                  <div className="vs-folder-children">
                    <div className="vs-indent-guide" />
                    {qasmList.map((file) => {
                      const isActive = activeFileId === file.id || activeFileId === file.name;
                      return (
                        <div
                          key={file.id}
                          className={`vs-file-row ${isActive ? 'active' : ''}`}
                          onClick={() => onOpenFile(file)}
                          onContextMenu={(e) => {
                            e.preventDefault();
                            setContextMenu({ x: e.clientX, y: e.clientY, file });
                          }}
                        >
                          {renderFileIcon(file)}
                          <span className="vs-file-label" title={file.path}>
                            {file.name}
                          </span>
                          {file.qubits && <span className="vs-qubit-tag">{file.qubits}q</span>}
                          {isActive && dirty && <span className="vs-dirty-dot">●</span>}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* Folder: projects/ */}
              <div className="vs-folder-block">
                <div
                  className="vs-folder-row"
                  onClick={() => toggleFolder('projects')}
                >
                  <span className={`vs-chevron ${expandedFolders.projects ? 'open' : ''}`}>
                    <Icon name="chevron" size={9} />
                  </span>
                  <span className="vs-folder-icon">
                    <Icon name="folder" size={13} />
                  </span>
                  <span className="vs-folder-name">projects</span>
                  <span className="vs-item-count">{projects.length}</span>
                </div>

                {expandedFolders.projects && (
                  <div className="vs-folder-children">
                    <div className="vs-indent-guide" />
                    {projects.length === 0 ? (
                      <div className="vs-empty-hint">No saved projects</div>
                    ) : (
                      projects.map((p) => {
                        const isActive = activeFileId === p.id;
                        return (
                          <div
                            key={p.id}
                            className={`vs-file-row ${isActive ? 'active' : ''}`}
                            onClick={() => onOpenProject(p.id)}
                          >
                            <span className="clean-file-icon py">
                              <Icon name="file" size={12} />
                            </span>
                            <span className="vs-file-label" title={p.name}>
                              {p.name.endsWith('.py') ? p.name : `${p.name}.py`}
                            </span>
                          </div>
                        );
                      })
                    )}
                  </div>
                )}
              </div>

              {/* Root File: README.md */}
              <div
                className={`vs-file-row root ${activeFileId === README_FILE.id ? 'active' : ''}`}
                onClick={() => onOpenFile(README_FILE)}
              >
                {renderFileIcon(README_FILE)}
                <span className="vs-file-label">{README_FILE.name}</span>
              </div>
            </div>
          )}
        </div>

        {/* SECTION 2: QUICK SIMULATION (COLLAPSIBLE ACCORDION) */}
        <div className="vs-accordion-section">
          <div
            className="vs-section-header"
            onClick={() => toggleSection('simulation')}
          >
            <span className={`vs-chevron ${sectionsOpen.simulation ? 'open' : ''}`}>
              <Icon name="chevron" size={10} />
            </span>
            <span className="vs-section-title">QUICK SIMULATION</span>
          </div>

          {sectionsOpen.simulation && (
            <div className="vs-accordion-body">
              <div className="vs-acc-item">
                <span className="vs-acc-label">SHOT COUNT</span>
                <div className="vs-acc-pills">
                  {['512', '1024', '2048', '4096', '8192'].map((s) => (
                    <button
                      key={s}
                      type="button"
                      className={`vs-acc-pill ${shots === s ? 'active' : ''}`}
                      onClick={() => onSetShots?.(s)}
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>

              <div className="vs-acc-item">
                <span className="vs-acc-label">ENGINE</span>
                <div className="vs-acc-box">
                  <strong>AerSimulator</strong>
                  <small>Statevector exact propagation</small>
                </div>
              </div>

              <button
                type="button"
                className="vs-acc-action-btn"
                disabled={busy}
                onClick={onRunKernel}
              >
                <Icon name="play" size={12} />
                <span>{busy ? 'Simulating…' : 'Run Aer Simulation'}</span>
              </button>
            </div>
          )}
        </div>

        {/* SECTION 3: TRANSPILER FORGE (COLLAPSIBLE ACCORDION) */}
        <div className="vs-accordion-section">
          <div
            className="vs-section-header"
            onClick={() => toggleSection('transpile')}
          >
            <span className={`vs-chevron ${sectionsOpen.transpile ? 'open' : ''}`}>
              <Icon name="chevron" size={10} />
            </span>
            <span className="vs-section-title">TRANSPILER FORGE</span>
          </div>

          {sectionsOpen.transpile && (
            <div className="vs-accordion-body">
              <div className="vs-acc-item">
                <span className="vs-acc-label">OPTIMIZATION LEVEL</span>
                <div className="vs-acc-cards">
                  {[
                    { lvl: '0', title: 'Level 0', desc: 'Direct mapping' },
                    { lvl: '1', title: 'Level 1', desc: 'Light cancellations' },
                    { lvl: '2', title: 'Level 2', desc: 'Commutative synthesis' },
                    { lvl: '3', title: 'Level 3', desc: 'Deep synthesis' },
                  ].map((item) => (
                    <button
                      key={item.lvl}
                      type="button"
                      className={`vs-level-btn ${optLevel === item.lvl ? 'active' : ''}`}
                      onClick={() => onSetOptLevel?.(item.lvl)}
                    >
                      <strong>{item.title}</strong>
                      <small>{item.desc}</small>
                    </button>
                  ))}
                </div>
              </div>

              <button
                type="button"
                className="vs-acc-action-btn"
                disabled={busy}
                onClick={onTranspile}
              >
                <Icon name="forge" size={12} />
                <span>Transpile Circuit</span>
              </button>
            </div>
          )}
        </div>

        {/* SECTION 4: EXPERIMENT HISTORY (COLLAPSIBLE ACCORDION) */}
        <div className="vs-accordion-section">
          <div
            className="vs-section-header"
            onClick={() => toggleSection('snapshots')}
          >
            <span className={`vs-chevron ${sectionsOpen.snapshots ? 'open' : ''}`}>
              <Icon name="chevron" size={10} />
            </span>
            <span className="vs-section-title">EXPERIMENT SNAPSHOTS</span>
            {experiments.length > 0 && <span className="vs-section-count">{experiments.length}</span>}
          </div>

          {sectionsOpen.snapshots && (
            <div className="vs-accordion-body">
              {experiments.length === 0 ? (
                <div className="vs-empty-hint">No snapshots recorded in SQLite yet.</div>
              ) : (
                <div className="vs-history-list">
                  {experiments.map((exp) => (
                    <div
                      key={exp.id}
                      className="vs-history-item"
                      onClick={() => onOpenExperiment(exp.id)}
                      title={`Load snapshot: ${exp.name}`}
                    >
                      <div className="vs-hist-top">
                        <strong>{exp.name}</strong>
                        <span className="vs-hist-hash">{(exp.source_hash || '').slice(0, 8)}</span>
                      </div>
                      <span className="vs-hist-date">{formatDate(exp.created_at)}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Explorer Status Bar */}
      <div className="vs-explorer-footer">
        <span className="vs-footer-engine">AerSimulator · Qiskit 2.6</span>
      </div>

      {/* Context Menu */}
      {contextMenu && (
        <div
          className="vscode-context-menu"
          style={{
            top: Math.min(contextMenu.y, window.innerHeight - 200),
            left: Math.min(contextMenu.x, window.innerWidth - 200),
          }}
          onClick={(e) => e.stopPropagation()}
        >
          <button
            type="button"
            className="context-menu-item"
            onClick={() => {
              onOpenFile(contextMenu.file);
              setContextMenu(null);
            }}
          >
            <Icon name="play" size={12} />
            <span>Open in Editor</span>
          </button>

          <button
            type="button"
            className="context-menu-item"
            onClick={() => {
              setRenamingId(contextMenu.file.id);
              setRenameValue(contextMenu.file.name);
              setContextMenu(null);
            }}
          >
            <Icon name="edit" size={12} />
            <span>Rename File</span>
            <kbd>F2</kbd>
          </button>

          <button
            type="button"
            className="context-menu-item"
            onClick={() => {
              duplicateFile(contextMenu.file);
              setContextMenu(null);
            }}
          >
            <Icon name="copy" size={12} />
            <span>Duplicate File</span>
          </button>

          <button
            type="button"
            className="context-menu-item"
            onClick={() => {
              copyPath(contextMenu.file.path);
              setContextMenu(null);
            }}
          >
            <Icon name="search" size={12} />
            <span>Copy Relative Path</span>
          </button>

          <div className="context-menu-sep" />

          <button
            type="button"
            className="context-menu-item danger"
            onClick={() => {
              deleteFile(contextMenu.file.id);
              setContextMenu(null);
            }}
          >
            <Icon name="trash" size={12} />
            <span>Delete File</span>
            <kbd>Del</kbd>
          </button>
        </div>
      )}
    </nav>
  );
}
