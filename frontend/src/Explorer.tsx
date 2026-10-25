import React, { useEffect, useRef, useState } from 'react';
import { Icon } from './Icons';
import { formatDate, type ExperimentSummary, type Project } from './types';
import {
  deleteWorkspaceFolder,
  deleteWorkspaceFile,
  getWorkspaceStorageKey,
  loadWorkspaceFiles,
  loadWorkspaceFolders,
  newWorkspaceId,
  renameWorkspaceFolder,
  saveWorkspaceFiles,
  saveWorkspaceFolders,
  WORKSPACE_CHANGED_EVENT,
} from './workspace';

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
  version?: number;
  updated_at?: string;
  syncState?: 'local' | 'pending' | 'saved' | 'error' | 'conflict';
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

  // Dynamic user folders
  const [folders, setFolders] = useState<string[]>(loadWorkspaceFolders);

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
  const [noticeMessage, setNoticeMessage] = useState('');
  const folderMutation = useRef(false);

  // Synchronize with workspace events
  useEffect(() => {
    const sync = () => {
      setCustomFiles(loadWorkspaceFiles());
      setFolders(loadWorkspaceFolders());
    };
    const storage = (event: StorageEvent) => {
      if (event.key === null || event.key.startsWith(getWorkspaceStorageKey())) sync();
    };
    window.addEventListener(WORKSPACE_CHANGED_EVENT, sync);
    window.addEventListener('storage', storage);
    return () => {
      window.removeEventListener(WORKSPACE_CHANGED_EVENT, sync);
      window.removeEventListener('storage', storage);
    };
  }, []);

  // Notice banner auto-clear
  useEffect(() => {
    if (noticeMessage) {
      const timer = setTimeout(() => setNoticeMessage(''), 3000);
      return () => clearTimeout(timer);
    }
  }, [noticeMessage]);

  // Inline file creation states
  const [isCreatingFile, setIsCreatingFile] = useState(false);
  const [createFileName, setCreateFileName] = useState('');
  const [targetFolder, setTargetFolder] = useState('circuits');

  // Inline folder creation states
  const [isCreatingFolder, setIsCreatingFolder] = useState(false);
  const [createFolderName, setCreateFolderName] = useState('');

  // Inline file rename states
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState('');

  // Inline folder rename states
  const [renamingFolder, setRenamingFolder] = useState<string | null>(null);
  const [renameFolderValue, setRenameFolderValue] = useState('');

  // Move-to modal/popover state
  const [movingFile, setMovingFile] = useState<WorkspaceFile | null>(null);
  const [targetMoveFolder, setTargetMoveFolder] = useState('');

  // Right-click context menus
  const [fileContextMenu, setFileContextMenu] = useState<{
    x: number;
    y: number;
    file: WorkspaceFile;
  } | null>(null);

  const [folderContextMenu, setFolderContextMenu] = useState<{
    x: number;
    y: number;
    folder: string;
  } | null>(null);

  const createFileRef = useRef<HTMLInputElement>(null);
  const createFolderRef = useRef<HTMLInputElement>(null);
  const renameFileRef = useRef<HTMLInputElement>(null);
  const renameFolderRef = useRef<HTMLInputElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const createCommitted = useRef(false);

  useEffect(() => {
    if (isCreatingFile) {
      createCommitted.current = false;
      const timer = setTimeout(() => createFileRef.current?.focus(), 50);
      return () => clearTimeout(timer);
    }
  }, [isCreatingFile]);

  useEffect(() => {
    if (isCreatingFolder) {
      const timer = setTimeout(() => createFolderRef.current?.focus(), 50);
      return () => clearTimeout(timer);
    }
  }, [isCreatingFolder]);

  useEffect(() => {
    if (renamingId) {
      const timer = setTimeout(() => {
        renameFileRef.current?.focus();
        renameFileRef.current?.select();
      }, 50);
      return () => clearTimeout(timer);
    }
  }, [renamingId]);

  useEffect(() => {
    if (renamingFolder) {
      const timer = setTimeout(() => {
        renameFolderRef.current?.focus();
        renameFolderRef.current?.select();
      }, 50);
      return () => clearTimeout(timer);
    }
  }, [renamingFolder]);

  useEffect(() => {
    const handleOutsideClick = () => {
      setFileContextMenu(null);
      setFolderContextMenu(null);
    };
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
      setFileError('Your workspace could not be saved. Check browser storage before trying again.');
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
    const closed: Record<string, boolean> = { projects: false, experiments: false };
    folders.forEach((f) => { closed[f] = false; });
    setExpandedFolders(closed);
  };

  const expandAll = () => {
    const open: Record<string, boolean> = { projects: true, experiments: true };
    folders.forEach((f) => { open[f] = true; });
    setExpandedFolders(open);
  };

  // --- Folder Management ---
  const handleCreateFolderCommit = () => {
    const raw = createFolderName.trim().replace(/[\\/:*?"<>|]/g, '');
    if (!raw) {
      setIsCreatingFolder(false);
      return;
    }
    if (folders.includes(raw) || raw === 'projects' || raw === 'experiments') {
      setFileError(`Folder "${raw}" already exists.`);
      return;
    }
    const nextFolders = [...folders, raw];
    saveWorkspaceFolders(nextFolders);
    setFolders(nextFolders);
    setExpandedFolders((prev) => ({ ...prev, [raw]: true }));
    setIsCreatingFolder(false);
    setCreateFolderName('');
    setNoticeMessage(`Folder "${raw}" created.`);
  };

  const handleRenameFolderCommit = async () => {
    if (folderMutation.current) return;
    if (!renamingFolder || !renameFolderValue.trim()) {
      setRenamingFolder(null);
      return;
    }
    const newName = renameFolderValue.trim().replace(/[\\/:*?"<>|]/g, '');
    if (!newName || newName === renamingFolder) {
      setRenamingFolder(null);
      return;
    }
    if (folders.includes(newName) || newName === 'projects' || newName === 'experiments') {
      setFileError(`Folder "${newName}" already exists.`);
      return;
    }
    folderMutation.current = true;
    try { await renameWorkspaceFolder(renamingFolder, newName); }
    catch (reason) { setFileError(reason instanceof Error ? reason.message : 'Folder could not be renamed.'); return; }
    finally { folderMutation.current = false; }
    setFolders(loadWorkspaceFolders());
    const updatedFiles = loadWorkspaceFiles();
    setCustomFiles(updatedFiles);

    // Update active file reference if it lived in renamed folder
    if (customFiles.find(file => file.id === activeFileId)?.path.startsWith(`${renamingFolder}/`)) {
      const activeFile = updatedFiles.find((f) => f.id === activeFileId);
      if (activeFile) onFileRenamed?.(activeFileId, activeFile);
    }

    setExpandedFolders((prev) => {
      const next = { ...prev };
      next[newName] = next[renamingFolder] ?? true;
      delete next[renamingFolder];
      return next;
    });
    setRenamingFolder(null);
    setNoticeMessage(`Renamed folder to "${newName}".`);
  };

  const handleDeleteFolder = async (folderName: string) => {
    const filesInFolder = customFiles.filter((f) => f.path.startsWith(`${folderName}/`));
    const confirmMsg = filesInFolder.length > 0
      ? `Delete folder "${folderName}" and all ${filesInFolder.length} file(s) inside it?`
      : `Delete empty folder "${folderName}"?`;
    if (!window.confirm(confirmMsg)) return;

    try { await deleteWorkspaceFolder(folderName); }
    catch (reason) { setFileError(reason instanceof Error ? reason.message : 'Folder could not be deleted.'); return; }
    filesInFolder.forEach((f) => onFileDeleted?.(f.id));
    setFolders(loadWorkspaceFolders());
    setCustomFiles(loadWorkspaceFiles());
    setNoticeMessage(`Deleted folder "${folderName}".`);
  };

  const handleDuplicateFolder = (folderName: string) => {
    let copyName = `${folderName}_copy`;
    let suffix = 2;
    while (folders.includes(copyName)) {
      copyName = `${folderName}_copy_${suffix++}`;
    }
    const filesToCopy = customFiles.filter((f) => f.path.startsWith(`${folderName}/`));
    const newFiles: WorkspaceFile[] = filesToCopy.map((f) => {
      const rest = f.path.slice(folderName.length + 1);
      const newPath = `${copyName}/${rest}`;
      return {
        ...f,
        id: newWorkspaceId(),
        path: newPath,
        version: 0,
        syncState: 'pending',
      };
    });
    saveWorkspaceFolders([...folders, copyName]);
    setFolders(loadWorkspaceFolders());
    saveCustomFiles([...newFiles, ...customFiles]);
    setExpandedFolders((prev) => ({ ...prev, [copyName]: true }));
    setNoticeMessage(`Duplicated "${folderName}" to "${copyName}".`);
  };

  // --- File Management ---
  const handleCreateFileCommit = () => {
    if (createCommitted.current) return;
    const raw = createFileName.trim();
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
    const folder = targetFolder || 'circuits';
    const path = `${folder}/${fileName}`;

    if (customFiles.some((file) => file.path === path)) {
      setFileError(`"${fileName}" already exists in ${folder}. Choose another name.`);
      return;
    }

    const defaultSource = '';

    const newFile: WorkspaceFile = {
      id: newWorkspaceId(),
      name: fileName,
      path,
      type: 'file',
      kind,
      source: defaultSource,
    };

    const nextFiles = [newFile, ...customFiles];
    if (!saveCustomFiles(nextFiles)) return;
    createCommitted.current = true;
    onOpenFile(newFile);
    setIsCreatingFile(false);
    setCreateFileName('');
    setNoticeMessage(`Created ${fileName}`);
  };

  const handleRenameFileCommit = () => {
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
    if (!previous) {
      setRenamingId(null);
      return;
    }
    const folder = previous.path.includes('/') ? previous.path.slice(0, previous.path.lastIndexOf('/') + 1) : '';
    const newPath = `${folder}${newName}`;
    if (customFiles.some((file) => file.id !== renamingId && file.path === newPath)) {
      setFileError('A file with that name already exists in this folder.');
      return;
    }
    const updated = customFiles.map((f) => {
      if (f.id === renamingId) {
        const isQasm = newName.endsWith('.qasm');
        const isJson = newName.endsWith('.json');
        const isMd = newName.endsWith('.md');
        const kind: WorkspaceFile['kind'] = isQasm ? 'qasm' : isJson ? 'json' : isMd ? 'markdown' : 'python';
        return { ...f, name: newName, path: newPath, kind };
      }
      return f;
    });
    if (!saveCustomFiles(updated)) return;
    const renamed = updated.find((file) => file.id === renamingId);
    if (renamed) onFileRenamed?.(renamingId, renamed);
    setRenamingId(null);
    setNoticeMessage(`Rename queued: ${newName}`);
  };

  const handleDeleteFile = async (id: string) => {
    const file = customFiles.find((item) => item.id === id);
    if (!file || !window.confirm(`Move "${file.name}" to Trash? Signed-in files can be restored for 48 hours.`)) return;
    try {
      await deleteWorkspaceFile(id);
      onFileDeleted?.(id);
      setCustomFiles(loadWorkspaceFiles());
      setNoticeMessage(`Moved ${file.name} to Trash.`);
    } catch (reason) { setFileError(reason instanceof Error ? reason.message : 'The file could not be deleted.'); }
  };

  const handleDuplicateFile = (file: WorkspaceFile) => {
    const baseName = file.name.replace(/(\.[^.]+)$/, '');
    const ext = file.name.includes('.') ? file.name.slice(file.name.lastIndexOf('.')) : '.py';
    let copyName = `${baseName}_copy${ext}`;
    const folder = file.path.includes('/') ? file.path.slice(0, file.path.lastIndexOf('/') + 1) : '';
    let copyPath = `${folder}${copyName}`;
    let suffix = 2;
    while (customFiles.some((item) => item.path === copyPath)) {
      copyName = `${baseName}_copy_${suffix++}${ext}`;
      copyPath = `${folder}${copyName}`;
    }

    const newFile: WorkspaceFile = {
      ...file,
      id: newWorkspaceId(),
      name: copyName,
      path: copyPath,
      version: 0,
      syncState: 'pending',
    };

    if (!saveCustomFiles([newFile, ...customFiles])) return;
    onOpenFile(newFile);
    setNoticeMessage(`Duplicated as ${copyName}`);
  };

  // --- Move File to Destination Folder ---
  const handleMoveFileCommit = () => {
    if (!movingFile || !targetMoveFolder) {
      setMovingFile(null);
      return;
    }
    const cleanFolder = targetMoveFolder.trim().replace(/\/+$/, '');
    const newPath = `${cleanFolder}/${movingFile.name}`;
    if (newPath === movingFile.path) {
      setMovingFile(null);
      return;
    }
    if (customFiles.some((f) => f.id !== movingFile.id && f.path === newPath)) {
      setFileError(`A file named "${movingFile.name}" already exists in "${cleanFolder}".`);
      return;
    }
    const updated = customFiles.map((f) => {
      if (f.id === movingFile.id) {
        return { ...f, path: newPath };
      }
      return f;
    });
    if (saveCustomFiles(updated)) {
      const moved = updated.find((f) => f.id === movingFile.id);
      if (moved) onFileRenamed?.(movingFile.id, moved);
      setNoticeMessage(`Moved "${movingFile.name}" to "${cleanFolder}/"`);
    }
    setMovingFile(null);
  };

  // --- Export / Download File ---
  const downloadFile = (file: WorkspaceFile) => {
    const blob = new Blob([file.source || ''], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = file.name;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    setNoticeMessage(`Downloaded ${file.name}`);
  };

  // --- Export Full Workspace Backup ---
  const exportAllFiles = () => {
    const payload = {
      workspace: 'QORE Quantum IDE',
      version: '1.0',
      exportedAt: new Date().toISOString(),
      folders,
      files: customFiles,
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `qore_workspace_backup_${new Date().toISOString().slice(0, 10)}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    setNoticeMessage('Workspace backup downloaded.');
  };

  // --- Copy File Contents to Clipboard ---
  const copyFileContent = (file: WorkspaceFile) => {
    if (navigator.clipboard) {
      navigator.clipboard.writeText(file.source || '');
      setNoticeMessage(`Copied code of "${file.name}" to clipboard.`);
    }
  };

  const copyPath = (path: string) => {
    if (navigator.clipboard) {
      navigator.clipboard.writeText(path);
      setNoticeMessage(`Copied path "${path}"`);
    }
  };

  // --- Import / Upload Files from Host OS ---
  const triggerImport = (folder: string = 'circuits') => {
    setTargetFolder(folder);
    fileInputRef.current?.click();
  };

  const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (!files || files.length === 0) return;
    const folder = targetFolder || 'circuits';
    const loadedFiles: WorkspaceFile[] = [];

    Array.from(files).forEach((file) => {
      const reader = new FileReader();
      reader.onload = (e) => {
        const source = String(e.target?.result || '');
        let name = file.name;
        let path = `${folder}/${name}`;
        let suffix = 2;
        const stem = name.replace(/(\.[^.]+)$/, '');
        const extension = name.includes('.') ? name.slice(name.lastIndexOf('.')) : '';
        while ([...customFiles, ...loadedFiles].some(entry => entry.path === path)) {
          name = `${stem}_import_${suffix++}${extension}`;
          path = `${folder}/${name}`;
        }
        const isQasm = name.endsWith('.qasm');
        const isJson = name.endsWith('.json');
        const isMd = name.endsWith('.md');
        const kind: WorkspaceFile['kind'] = isQasm ? 'qasm' : isJson ? 'json' : isMd ? 'markdown' : 'python';
        const newFile: WorkspaceFile = {
          id: newWorkspaceId(),
          name,
          path,
          type: 'file',
          kind,
          source,
        };
        loadedFiles.push(newFile);

        if (loadedFiles.length === files.length) {
          const nextFiles = [...loadedFiles, ...customFiles];
          saveCustomFiles(nextFiles);
          if (loadedFiles[0]) onOpenFile(loadedFiles[0]);
          setNoticeMessage(`Imported ${loadedFiles.length} file(s) into "${folder}/".`);
        }
      };
      reader.readAsText(file);
    });
    event.target.value = '';
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
      <div
        key={file.id}
        role="button"
        tabIndex={0}
        aria-label={`Open ${file.path}`}
        className={`vs-file-row ${isActive ? 'active' : ''}`}
        onClick={() => {
          if (renamingId !== file.id) onOpenFile(file);
        }}
        onKeyDown={(event) => {
          if (event.target === event.currentTarget && (event.key === 'Enter' || event.key === ' ')) {
            event.preventDefault();
            onOpenFile(file);
          }
        }}
        onContextMenu={(event) => {
          event.preventDefault();
          event.stopPropagation();
          setFolderContextMenu(null);
          setFileContextMenu({ x: event.clientX, y: event.clientY, file });
        }}
      >
        {renderFileIcon(file)}
        {renamingId === file.id ? (
          <input
            ref={renameFileRef}
            type="text"
            className="vs-create-input"
            aria-label={`Rename ${file.name}`}
            value={renameValue}
            onChange={(event) => setRenameValue(event.target.value)}
            onKeyDown={(event) => {
              event.stopPropagation();
              if (event.key === 'Enter') handleRenameFileCommit();
              if (event.key === 'Escape') setRenamingId(null);
            }}
            onBlur={handleRenameFileCommit}
            onClick={(event) => event.stopPropagation()}
          />
        ) : (
          <span className="vs-file-label" title={file.path}>
            {file.name}
          </span>
        )}
        {file.qubits && <span className="vs-qubit-tag">{file.qubits}q</span>}
        {isActive && dirty && <span className="vs-dirty-dot" title="Unsaved modifications">●</span>}

        {/* Hover Action Tools for File */}
        <div className="vs-hover-tools">
          <button
            type="button"
            className="vs-tool-btn"
            title={`Download ${file.name}`}
            onClick={(event) => {
              event.stopPropagation();
              downloadFile(file);
            }}
          >
            <Icon name="download" size={11} />
          </button>
          <button
            type="button"
            className="vs-tool-btn"
            title={`Duplicate ${file.name}`}
            onClick={(event) => {
              event.stopPropagation();
              handleDuplicateFile(file);
            }}
          >
            <Icon name="copy" size={11} />
          </button>
          <button
            type="button"
            className="vs-tool-btn"
            title={`Rename ${file.name} (F2)`}
            onClick={(event) => {
              event.stopPropagation();
              setRenamingId(file.id);
              setRenameValue(file.name);
            }}
          >
            <Icon name="edit" size={11} />
          </button>
          <button
            type="button"
            className="vs-tool-btn danger"
            title={`Delete ${file.name}`}
            onClick={(event) => {
              event.stopPropagation();
              handleDeleteFile(file.id);
            }}
          >
            <Icon name="trash" size={11} />
          </button>
        </div>
      </div>
    );
  };

  const renderFolderBlock = (folderName: string) => {
    const isExpanded = !!expandedFolders[folderName];
    const filesInFolder = customFiles.filter((f) => f.path.startsWith(`${folderName}/`));

    return (
      <div key={folderName} className="vs-folder-block">
        <div
          className="vs-folder-row"
          onClick={() => toggleFolder(folderName)}
          onContextMenu={(event) => {
            event.preventDefault();
            event.stopPropagation();
            setFileContextMenu(null);
            setFolderContextMenu({ x: event.clientX, y: event.clientY, folder: folderName });
          }}
        >
          <span className={`vs-chevron ${isExpanded ? 'open' : ''}`}>
            <Icon name="chevron" size={9} />
          </span>
          <span className="vs-folder-icon">
            <Icon name="folder" size={13} />
          </span>

          {renamingFolder === folderName ? (
            <input
              ref={renameFolderRef}
              type="text"
              className="vs-create-input"
              aria-label={`Rename folder ${folderName}`}
              value={renameFolderValue}
              onChange={(e) => setRenameFolderValue(e.target.value)}
              onKeyDown={(e) => {
                e.stopPropagation();
                if (e.key === 'Enter') handleRenameFolderCommit();
                if (e.key === 'Escape') setRenamingFolder(null);
              }}
              onBlur={handleRenameFolderCommit}
              onClick={(e) => e.stopPropagation()}
            />
          ) : (
            <span className="vs-folder-name" title={`Folder: ${folderName}/`}>
              {folderName}
            </span>
          )}

          <span className="vs-item-count">{filesInFolder.length}</span>

          {/* Hover Action Tools for Folder */}
          <div className="vs-hover-tools">
            <button
              type="button"
              className="vs-tool-btn"
              title={`New File inside ${folderName}`}
              onClick={(e) => {
                e.stopPropagation();
                setTargetFolder(folderName);
                setIsCreatingFile(true);
                setExpandedFolders((p) => ({ ...p, [folderName]: true }));
              }}
            >
              <Icon name="filePlus" size={11} />
            </button>
            <button
              type="button"
              className="vs-tool-btn"
              title={`Upload Files into ${folderName}`}
              onClick={(e) => {
                e.stopPropagation();
                triggerImport(folderName);
              }}
            >
              <Icon name="upload" size={11} />
            </button>
            <button
              type="button"
              className="vs-tool-btn"
              title={`Rename Folder "${folderName}"`}
              onClick={(e) => {
                e.stopPropagation();
                setRenamingFolder(folderName);
                setRenameFolderValue(folderName);
              }}
            >
              <Icon name="edit" size={11} />
            </button>
            <button
              type="button"
              className="vs-tool-btn danger"
              title={`Delete Folder "${folderName}"`}
              onClick={(e) => {
                e.stopPropagation();
                handleDeleteFolder(folderName);
              }}
            >
              <Icon name="trash" size={11} />
            </button>
          </div>
        </div>

        {isExpanded && (
          <div className="vs-folder-children">
            <div className="vs-indent-guide" />
            {isCreatingFile && targetFolder === folderName && (
              <div className="vs-inline-create">
                <span className="clean-file-icon py">
                  <Icon name="circuit" size={12} />
                </span>
                <input
                  ref={createFileRef}
                  type="text"
                  className="vs-create-input"
                  placeholder="filename.py (or .qasm, .json, .md)"
                  value={createFileName}
                  onChange={(e) => setCreateFileName(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') handleCreateFileCommit();
                    if (e.key === 'Escape') setIsCreatingFile(false);
                  }}
                  onBlur={handleCreateFileCommit}
                />
              </div>
            )}
            {filesInFolder.length === 0 && !isCreatingFile && (
              <div className="vs-empty-hint" style={{ paddingLeft: '22px', fontSize: '11px', opacity: 0.6 }}>
                Empty folder (click + to add file)
              </div>
            )}
            {filesInFolder.map(renderTreeFile)}
          </div>
        )}
      </div>
    );
  };

  const rootFiles = customFiles.filter((f) => !folders.some((fld) => f.path.startsWith(`${fld}/`)));

  return (
    <nav className={`vscode-sidebar ${sidebarOpen ? 'open' : 'closed'}`} aria-label="Workspace Explorer">
      {/* Hidden File Input for OS Uploads */}
      <input
        ref={fileInputRef}
        type="file"
        multiple
        accept=".py,.qasm,.json,.md,.txt"
        style={{ display: 'none' }}
        onChange={handleFileUpload}
      />

      {/* 1. Header Toolbar (Full IDE File & Folder Controls) */}
      <div className="vs-explorer-header">
        <span className="vs-explorer-title">EXPLORER</span>
        <div className="vs-explorer-actions">
          <button
            type="button"
            className="vs-action-btn"
            title="New File (in active folder)"
            onClick={() => {
              setTargetFolder(folders[0] || 'circuits');
              setIsCreatingFile(true);
              setSectionsOpen((p) => ({ ...p, workspace: true }));
            }}
          >
            <Icon name="filePlus" size={13} />
          </button>

          <button
            type="button"
            className="vs-action-btn"
            title="New Folder"
            onClick={() => {
              setIsCreatingFolder(true);
              setSectionsOpen((p) => ({ ...p, workspace: true }));
            }}
          >
            <Icon name="folderPlus" size={13} />
          </button>

          <button
            type="button"
            className="vs-action-btn"
            title="Import / Upload Files from Computer"
            onClick={() => triggerImport(folders[0] || 'circuits')}
          >
            <Icon name="upload" size={13} />
          </button>

          <button
            type="button"
            className="vs-action-btn"
            title="Export Workspace Backup (.json)"
            onClick={exportAllFiles}
          >
            <Icon name="download" size={13} />
          </button>

          <button
            type="button"
            className="vs-action-btn"
            title="New Cloud Project"
            onClick={onNewProject}
          >
            <Icon name="plus" size={13} />
          </button>

          <button
            type="button"
            className="vs-action-btn"
            title="Refresh Explorer"
            onClick={() => {
              setCustomFiles(loadWorkspaceFiles());
              setFolders(loadWorkspaceFolders());
              onRefresh();
            }}
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
        {noticeMessage && (
          <div className="vs-workspace-notice" role="status" style={{ padding: '4px 10px', fontSize: '11px', color: '#57D9FF', background: 'rgba(87, 217, 255, 0.08)', borderBottom: '1px solid rgba(87, 217, 255, 0.2)' }}>
            {noticeMessage}
          </div>
        )}

        {/* SECTION 1: WORKSPACE FILES */}
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
              {/* Inline Folder Creation Row */}
              {isCreatingFolder && (
                <div className="vs-inline-create" style={{ padding: '4px 8px 4px 18px', background: 'rgba(87, 217, 255, 0.06)' }}>
                  <Icon name="folder" size={13} />
                  <input
                    ref={createFolderRef}
                    type="text"
                    className="vs-create-input"
                    placeholder="New folder name..."
                    value={createFolderName}
                    onChange={(e) => setCreateFolderName(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') handleCreateFolderCommit();
                      if (e.key === 'Escape') setIsCreatingFolder(false);
                    }}
                    onBlur={handleCreateFolderCommit}
                  />
                </div>
              )}

              {/* Dynamic Folders */}
              {folders.map(renderFolderBlock)}

              {/* Projects Folder */}
              <div className="vs-folder-block">
                <div className="vs-folder-row" onClick={() => toggleFolder('projects')}>
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

              {/* Any Root Files */}
              {rootFiles.map(renderTreeFile)}
            </div>
          )}
        </div>

        {/* SECTION 2: QUICK SIMULATION */}
        <div className="vs-accordion-section">
          <div className="vs-section-header" onClick={() => toggleSection('simulation')}>
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

        {/* SECTION 3: TRANSPILER FORGE */}
        <div className="vs-accordion-section">
          <div className="vs-section-header" onClick={() => toggleSection('transpile')}>
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

        {/* SECTION 4: EXPERIMENT HISTORY */}
        <div className="vs-accordion-section">
          <div className="vs-section-header" onClick={() => toggleSection('snapshots')}>
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

      {/* Move File Destination Modal */}
      {movingFile && (
        <div className="vscode-modal-overlay" onClick={() => setMovingFile(null)}>
          <div className="vscode-modal-dialog" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '340px' }}>
            <h3 style={{ fontSize: '13px', fontWeight: 600, marginBottom: '8px', color: '#E1E4EA' }}>
              Move &ldquo;{movingFile.name}&rdquo;
            </h3>
            <p style={{ fontSize: '12px', color: '#9DA7B8', marginBottom: '12px' }}>
              Select target folder:
            </p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginBottom: '14px' }}>
              {folders.map((fld) => (
                <button
                  key={fld}
                  type="button"
                  className={`vs-level-btn ${targetMoveFolder === fld ? 'active' : ''}`}
                  style={{ textAlign: 'left', padding: '6px 10px' }}
                  onClick={() => setTargetMoveFolder(fld)}
                >
                  <Icon name="folder" size={12} />
                  <span style={{ marginLeft: '6px' }}>{fld}/</span>
                </button>
              ))}
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
              <button type="button" className="vs-btn secondary" onClick={() => setMovingFile(null)}>
                Cancel
              </button>
              <button
                type="button"
                className="vs-btn primary"
                disabled={!targetMoveFolder}
                onClick={handleMoveFileCommit}
              >
                Move File
              </button>
            </div>
          </div>
        </div>
      )}

      {/* File Context Menu */}
      {fileContextMenu && (
        <div
          className="vscode-context-menu"
          style={{
            top: Math.min(fileContextMenu.y, window.innerHeight - 260),
            left: Math.min(fileContextMenu.x, window.innerWidth - 220),
          }}
          onClick={(e) => e.stopPropagation()}
        >
          <button
            type="button"
            className="context-menu-item"
            onClick={() => {
              onOpenFile(fileContextMenu.file);
              setFileContextMenu(null);
            }}
          >
            <Icon name="play" size={12} />
            <span>Open in Editor</span>
          </button>

          <button
            type="button"
            className="context-menu-item"
            onClick={() => {
              setRenamingId(fileContextMenu.file.id);
              setRenameValue(fileContextMenu.file.name);
              setFileContextMenu(null);
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
              handleDuplicateFile(fileContextMenu.file);
              setFileContextMenu(null);
            }}
          >
            <Icon name="copy" size={12} />
            <span>Duplicate File</span>
          </button>

          <button
            type="button"
            className="context-menu-item"
            onClick={() => {
              downloadFile(fileContextMenu.file);
              setFileContextMenu(null);
            }}
          >
            <Icon name="download" size={12} />
            <span>Download File</span>
          </button>

          <button
            type="button"
            className="context-menu-item"
            onClick={() => {
              copyFileContent(fileContextMenu.file);
              setFileContextMenu(null);
            }}
          >
            <Icon name="code" size={12} />
            <span>Copy Code</span>
          </button>

          <button
            type="button"
            className="context-menu-item"
            onClick={() => {
              copyPath(fileContextMenu.file.path);
              setFileContextMenu(null);
            }}
          >
            <Icon name="search" size={12} />
            <span>Copy Relative Path</span>
          </button>

          <button
            type="button"
            className="context-menu-item"
            onClick={() => {
              setMovingFile(fileContextMenu.file);
              setTargetMoveFolder(folders[0] || 'circuits');
              setFileContextMenu(null);
            }}
          >
            <Icon name="folder" size={12} />
            <span>Move to Folder…</span>
          </button>

          <div className="context-menu-sep" />

          <button
            type="button"
            className="context-menu-item danger"
            onClick={() => {
              handleDeleteFile(fileContextMenu.file.id);
              setFileContextMenu(null);
            }}
          >
            <Icon name="trash" size={12} />
            <span>Delete File</span>
            <kbd>Del</kbd>
          </button>
        </div>
      )}

      {/* Folder Context Menu */}
      {folderContextMenu && (
        <div
          className="vscode-context-menu"
          style={{
            top: Math.min(folderContextMenu.y, window.innerHeight - 240),
            left: Math.min(folderContextMenu.x, window.innerWidth - 220),
          }}
          onClick={(e) => e.stopPropagation()}
        >
          <button
            type="button"
            className="context-menu-item"
            onClick={() => {
              setTargetFolder(folderContextMenu.folder);
              setIsCreatingFile(true);
              setExpandedFolders((p) => ({ ...p, [folderContextMenu.folder]: true }));
              setFolderContextMenu(null);
            }}
          >
            <Icon name="filePlus" size={12} />
            <span>New File in &ldquo;{folderContextMenu.folder}&rdquo;</span>
          </button>

          <button
            type="button"
            className="context-menu-item"
            onClick={() => {
              triggerImport(folderContextMenu.folder);
              setFolderContextMenu(null);
            }}
          >
            <Icon name="upload" size={12} />
            <span>Upload Files Here</span>
          </button>

          <button
            type="button"
            className="context-menu-item"
            onClick={() => {
              setRenamingFolder(folderContextMenu.folder);
              setRenameFolderValue(folderContextMenu.folder);
              setFolderContextMenu(null);
            }}
          >
            <Icon name="edit" size={12} />
            <span>Rename Folder</span>
          </button>

          <button
            type="button"
            className="context-menu-item"
            onClick={() => {
              handleDuplicateFolder(folderContextMenu.folder);
              setFolderContextMenu(null);
            }}
          >
            <Icon name="copy" size={12} />
            <span>Duplicate Folder</span>
          </button>

          <div className="context-menu-sep" />

          <button
            type="button"
            className="context-menu-item danger"
            onClick={() => {
              handleDeleteFolder(folderContextMenu.folder);
              setFolderContextMenu(null);
            }}
          >
            <Icon name="trash" size={12} />
            <span>Delete Folder</span>
          </button>
        </div>
      )}
    </nav>
  );
}
