import type { WorkspaceFile } from './Explorer';

export const WORKSPACE_STORAGE_KEY = 'qore_workspace_files';
export const WORKSPACE_CHANGED_EVENT = 'qore:workspace-changed';
let workspaceOwner: string | null = null;

export function getWorkspaceStorageKey(): string {
  return workspaceOwner ? `${WORKSPACE_STORAGE_KEY}:${encodeURIComponent(workspaceOwner)}` : WORKSPACE_STORAGE_KEY;
}

export function setWorkspaceOwner(userId: string | null): void {
  const nextOwner = userId?.trim() || null;
  if (workspaceOwner === nextOwner) return;
  workspaceOwner = nextOwner;
  // Existing guest files remain in their original cache. An authenticated
  // workspace starts independently and can never inherit another owner's files.
  window.dispatchEvent(new Event(WORKSPACE_CHANGED_EVENT));
}

function isWorkspaceFile(value: unknown): value is WorkspaceFile {
  if (!value || typeof value !== 'object') return false;
  const file = value as Record<string, unknown>;
  return ['id', 'name', 'path', 'source'].every((key) => typeof file[key] === 'string')
    && file.type === 'file' && ['python', 'qasm', 'json', 'markdown'].includes(String(file.kind));
}

export function loadWorkspaceFiles(): WorkspaceFile[] {
  try {
    const raw = localStorage.getItem(getWorkspaceStorageKey());
    const value: unknown = raw ? JSON.parse(raw) : [];
    return Array.isArray(value) ? value.filter(isWorkspaceFile) : [];
  } catch {
    return [];
  }
}

export function saveWorkspaceFiles(files: WorkspaceFile[]): void {
  // A malformed older cache must never be silently overwritten by a new file.
  const storageKey = getWorkspaceStorageKey();
  const existing = localStorage.getItem(storageKey);
  if (existing) {
    const parsed: unknown = JSON.parse(existing);
    if (!Array.isArray(parsed) || !parsed.every(isWorkspaceFile)) {
      throw new Error('Your saved workspace could not be read. Export or recover its stored data before adding files.');
    }
  }
  localStorage.setItem(storageKey, JSON.stringify(files));
  window.dispatchEvent(new Event(WORKSPACE_CHANGED_EVENT));
}

export function addStarterFile(): WorkspaceFile {
  const files = loadWorkspaceFiles();
  let path = 'circuits/my_first_qubits.py';
  let suffix = 2;
  while (files.some((file) => file.path === path)) path = `circuits/my_first_qubits_${suffix++}.py`;
  const file: WorkspaceFile = {
    id: path, name: path.split('/').pop()!, path, type: 'file', kind: 'python', qubits: 3,
    source: `# My first three qubits — a GHZ state
# Run this circuit: only 000 and 111 should be measured.
from qiskit import QuantumCircuit

qc = QuantumCircuit(3, 3)

# Prepare a superposition, then connect all three qubits.
qc.h(0)
qc.cx(0, 1)
qc.cx(1, 2)

# Read each qubit into its matching classical bit.
qc.measure(0, 0)
qc.measure(1, 1)
qc.measure(2, 2)
`,
  };
  saveWorkspaceFiles([file, ...files]);
  return file;
}

export function addBlankFile(): WorkspaceFile {
  const files = loadWorkspaceFiles();
  let path = 'circuits/untitled.py';
  let suffix = 2;
  while (files.some((file) => file.path === path)) path = `circuits/untitled_${suffix++}.py`;
  const file: WorkspaceFile = { id: path, name: path.split('/').pop()!, path, type: 'file', kind: 'python', source: '' };
  saveWorkspaceFiles([file, ...files]);
  return file;
}
