import React, { useEffect, useRef, useState } from 'react';
import { Icon } from './Icons';
import { formatDate, type ExperimentSummary, type Project } from './types';
import { getWorkspaceStorageKey, loadWorkspaceFiles, saveWorkspaceFiles, WORKSPACE_CHANGED_EVENT } from './workspace';

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
  onFileDeleted?: (id: string) => void;
  onFileRenamed?: (previousId: string, file: WorkspaceFile) => void;
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


export function Explorer({
  sidebarOpen,
  activeFileId,
  onOpenFile,
  onFileDeleted,
  onFileRenamed,
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
  const [customFiles, setCustomFiles] = useState<WorkspaceFile[]>(loadWorkspaceFiles);
  const [fileError, setFileError] = useState('');

  useEffect(() => {
    const sync = () => setCustomFiles(loadWorkspaceFiles());
    const storage = (event: StorageEvent) => { if (event.key === null || event.key === getWorkspaceStorageKey()) sync(); };
    window.addEventListener(WORKSPACE_CHANGED_EVENT, sync);
    window.addEventListener('storage', storage);
    return () => {
      window.removeEventListener(WORKSPACE_CHANGED_EVENT, sync);
      window.removeEventListener('storage', storage);
    };
  }, []);

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
  const createCommitted = useRef(false);

  useEffect(() => {
    if (isCreatingFile) {
      createCommitted.current = false;
      const timer = setTimeout(() => createInputRef.current?.focus(), 50);
      return () => clearTimeout(timer);
    }
  }, [isCreatingFile]);

  useEffect(() => {
    if (renamingId) {
      const timer = setTimeout(() => {
        renameInputRef.current?.focus();
        renameInputRef.current?.select();
      }, 50);
      return () => clearTimeout(timer);
    }
  }, [renamingId]);

  useEffect(() => {
    const handleOutsideClick = () => setContextMenu(null);
    window.addEventListener('click', handleOutsideClick);
    return () => window.removeEventListener('click', handleOutsideClick);
  }, []);

  const saveCustomFiles = (files: WorkspaceFile[]) => {
    try {
      saveWorkspaceFiles(files);
      setCustomFiles(files);
      setFileError('');
      return true;
    } catch {
      setFileError('Your workspace could not be saved. Check browser storage before trying again. Existing files were not changed.');
      return false;
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
    if (createCommitted.current) return;
    const raw = createName.trim();
    if (!raw) {
      setIsCreatingFile(false);
      return;
    }

    const fileName = raw.includes('.') ? raw : `${raw}.py`;
    if (fileName.length > 100 || /[\\/:*?"<>|]/.test(fileName) || fileName.startsWith('.')) {
      setFileError('Use a file name of 1–100 characters, without path separators or reserved characters.');
      return;
    }
    const isQasm = fileName.endsWith('.qasm');
    const isJson = fileName.endsWith('.json');
    const isMd = fileName.endsWith('.md');
    const kind: WorkspaceFile['kind'] = isQasm ? 'qasm' : isJson ? 'json' : isMd ? 'markdown' : 'python';
    const path = `${targetFolder}/${fileName}`;
    if (customFiles.some((file) => file.path === path)) {
      setFileError('A file with that name already exists. Choose another name.');
      return;
    }

    const newFile: WorkspaceFile = {
      id: path,
      name: fileName,
      path,
      type: 'file',
      kind,
      source: '',
    };

    const nextFiles = [newFile, ...customFiles];
    if (!saveCustomFiles(nextFiles)) return;
    createCommitted.current = true;
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
    if (newName.length > 100 || /[\\/:*?"<>|]/.test(newName) || newName.startsWith('.')) {
      setFileError('Choose a valid file name without path separators or reserved characters.');
      return;
    }
    const previous = customFiles.find((file) => file.id === renamingId);
    if (!previous) { setRenamingId(null); return; }
    const newPath = previous.path.slice(0, previous.path.lastIndexOf('/') + 1) + newName;
    if (customFiles.some((file) => file.id !== renamingId && file.path === newPath)) {
      setFileError('A file with that name already exists.');
      return;
    }
    const updated = customFiles.map((f) => {
      if (f.id === renamingId) {
        const parts = f.path.split('/');
        parts[parts.length - 1] = newName;
        const kind: WorkspaceFile['kind'] = newName.endsWith('.qasm') ? 'qasm' : newName.endsWith('.json') ? 'json' : newName.endsWith('.md') ? 'markdown' : 'python';
        return { ...f, id: newPath, name: newName, path: parts.join('/'), kind };
      }
      return f;
    });
    if (!saveCustomFiles(updated)) return;
    const renamed = updated.find((file) => file.id === newPath);
    if (renamed) onFileRenamed?.(renamingId, renamed);
    setRenamingId(null);
  };

  const deleteFile = (id: string) => {
    const file = customFiles.find((item) => item.id === id);
    if (!file || !window.confirm(`Delete "${file.name}" from this browser workspace?${activeFileId === id && dirty ? ' Unsaved edits will also be discarded.' : ''}`)) return;
    const updated = customFiles.filter((f) => f.id !== id);
    if (saveCustomFiles(updated)) onFileDeleted?.(id);
  };

  const duplicateFile = (file: WorkspaceFile) => {
    const baseName = file.name.replace(/(\.[^.]+)$/, '');
    const ext = file.name.includes('.') ? file.name.slice(file.name.lastIndexOf('.')) : '.py';
    let copyName = `${baseName}_copy${ext}`;
    const folder = file.path.slice(0, file.path.lastIndexOf('/') + 1);
    let copyPath = `${folder}${copyName}`;
    let suffix = 2;
    while (customFiles.some((item) => item.path === copyPath)) {
      copyName = `${baseName}_copy_${suffix++}${ext}`;
      copyPath = `${folder}${copyName}`;
    }

    const newFile: WorkspaceFile = {
      ...file,
      id: copyPath,
      name: copyName,
      path: copyPath,
    };

    if (!saveCustomFiles([newFile, ...customFiles])) return;
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

  const renderTreeFile = (file: WorkspaceFile) => {
    const isActive = activeFileId === file.id;
    return (
      <div key={file.id} role="button" tabIndex={0} aria-label={`Open ${file.path}`}
        className={`vs-file-row ${isActive ? 'active' : ''}`}
        onClick={() => { if (renamingId !== file.id) onOpenFile(file); }}
        onKeyDown={(event) => { if (event.target === event.currentTarget && (event.key === 'Enter' || event.key === ' ')) { event.preventDefault(); onOpenFile(file); } }}
        onContextMenu={(event) => { event.preventDefault(); setContextMenu({ x: event.clientX, y: event.clientY, file }); }}>
        {renderFileIcon(file)}
        {renamingId === file.id ? (
          <input ref={renameInputRef} type="text" className="vs-create-input" aria-label={`Rename ${file.name}`}
            value={renameValue} onChange={(event) => setRenameValue(event.target.value)}
            onKeyDown={(event) => { event.stopPropagation(); if (event.key === 'Enter') handleRenameCommit(); if (event.key === 'Escape') setRenamingId(null); }}
            onBlur={handleRenameCommit} onClick={(event) => event.stopPropagation()} />
        ) : <span className="vs-file-label" title={file.path}>{file.name}</span>}
        {file.qubits && <span className="vs-qubit-tag">{file.qubits}q</span>}
        {isActive && dirty && <span className="vs-dirty-dot" title="Unsaved modifications">●</span>}
        <div className="vs-hover-tools">
          <button type="button" className="vs-tool-btn" title={`Rename ${file.name}`} onClick={(event) => { event.stopPropagation(); setRenamingId(file.id); setRenameValue(file.name); }}><Icon name="edit" size={11} /></button>
          <button type="button" className="vs-tool-btn danger" title={`Delete ${file.name}`} onClick={(event) => { event.stopPropagation(); deleteFile(file.id); }}><Icon name="trash" size={11} /></button>
        </div>
      </div>
    );
  };

  const circuitsList = customFiles.filter((f) => f.path.startsWith('circuits/'));

  const qasmList = customFiles.filter((f) => f.path.startsWith('openqasm/'));
  const rootFiles = customFiles.filter((f) => !f.path.startsWith('circuits/') && !f.path.startsWith('openqasm/'));

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
        {fileError && <p className="vs-workspace-error" role="alert">{fileError}</p>}
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
            <span className="vs-section-count">{customFiles.length + projects.length}</span>
          </div>

          {sectionsOpen.workspace && (
            <div className="vs-tree-container">
              {customFiles.length === 0 && projects.length === 0 && !isCreatingFile && <p className="vs-empty-hint">Your workspace is empty. Choose Get Started, or create a file.</p>}
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

                    {circuitsList.map(renderTreeFile)}
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
                    {qasmList.map(renderTreeFile)}
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

              {rootFiles.map(renderTreeFile)}
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
                <div className="vs-empty-hint">No snapshots recorded yet.</div>
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
