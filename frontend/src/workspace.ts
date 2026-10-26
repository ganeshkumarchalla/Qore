import type { WorkspaceFile } from './Explorer';
import type { WorkspaceEntry, WorkspaceSnapshot } from './types';

export const WORKSPACE_STORAGE_KEY = 'qore_workspace_files';
export const WORKSPACE_CHANGED_EVENT = 'qore:workspace-changed';
type PendingEntry = { entry: WorkspaceFile | WorkspaceEntry; expectedVersion: number; type: 'file' | 'folder'; conflict?: boolean;
  draftId?: string; relatedDraftIds?: string[]; replaces?: string[] };
export type WorkspaceStatus = { owner: string | null; ready: boolean; saving: boolean; pending: number; error: string; conflicts: number; trash: WorkspaceEntry[]; lastDeletedId: string | null; serverOffset: number; lockedFiles: string[] };

let workspaceOwner: string | null = null;
let files: WorkspaceFile[] | null = null;
let folderEntries: WorkspaceEntry[] = [];
let pending = new Map<string, PendingEntry>();
let activeFileId: string | null = null;
let metadataPending = false;
let ready = false;
let saving = false;
let syncError = '';
let trash: WorkspaceEntry[] = [];
let lastDeletedId: string | null = null;
let serverOffset = 0;
let generation = 0;
let controller = new AbortController();
let timer: number | undefined;
let flight: Promise<boolean> | null = null;
let mutationOpen = false;
let recoveryWarning = '';
let recoveryCopies: { backupKey: string; raw: string }[] = [];
let ownJournalKey: string | null = null;
const deleting = new Set<string>();
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export function newWorkspaceId(): string { return crypto.randomUUID(); }
export function getWorkspaceStorageKey(): string { return workspaceOwner ? WORKSPACE_STORAGE_KEY + ':' + encodeURIComponent(workspaceOwner) : WORKSPACE_STORAGE_KEY; }
function key(suffix: string) { return getWorkspaceStorageKey() + suffix; }
function notify() { window.dispatchEvent(new Event(WORKSPACE_CHANGED_EVENT)); }
function read<T>(suffix: string, fallback: T): T {
  try { const value = localStorage.getItem(key(suffix)); return value ? JSON.parse(value) as T : fallback; } catch { return fallback; }
}
function isFile(value: unknown): value is WorkspaceFile {
  if (!value || typeof value !== 'object') return false;
  const file = value as Partial<WorkspaceFile>;
  return ['id', 'name', 'path', 'source'].every(field => typeof (file as Record<string, unknown>)[field] === 'string')
    && file.type === 'file' && ['python', 'qasm', 'json', 'markdown'].includes(String(file.kind));
}
function isFolder(value: unknown): value is WorkspaceEntry {
  if (!value || typeof value !== 'object') return false;
  const entry = value as Partial<WorkspaceEntry>;
  return entry.type === 'folder' && ['id', 'name', 'path'].every(field => typeof (entry as Record<string, unknown>)[field] === 'string');
}
function validPending(value: unknown): value is [string, PendingEntry] {
  if (!Array.isArray(value) || value.length !== 2 || typeof value[0] !== 'string' || !value[1] || typeof value[1] !== 'object') return false;
  const change = value[1] as Partial<PendingEntry>;
  return Number.isSafeInteger(change.expectedVersion) && Number(change.expectedVersion) >= 0
    && (change.conflict === undefined || typeof change.conflict === 'boolean')
    && (change.draftId === undefined || typeof change.draftId === 'string')
    && [change.relatedDraftIds, change.replaces].every(ids => ids === undefined || Array.isArray(ids) && ids.every(id => typeof id === 'string'))
    && (change.type === 'file' ? isFile(change.entry) : change.type === 'folder' && isFolder(change.entry))
    && change.entry?.id === value[0];
}
function preserveRecoveryData(suffix: string, raw: string) {
  recoveryWarning = 'Unreadable browser recovery data has been preserved on this device.';
  const copy = { backupKey: key(':unreadable' + suffix + ':') + Date.now() + ':' + recoveryCopies.length, raw };
  try { localStorage.setItem(copy.backupKey, raw); }
  catch { recoveryCopies.push(copy); }
}
function parseOutbox(raw: string | null, suffix: string) {
  const empty = { entries: [] as [string, PendingEntry][], activeFileId: undefined as string | null | undefined, metadataPending: false };
  if (!raw) return empty;
  let parsed: unknown;
  try { parsed = JSON.parse(raw); } catch { preserveRecoveryData(suffix, raw); return empty; }
  const value = parsed && typeof parsed === 'object' ? parsed as Record<string, unknown> : {};
  const entries = Array.isArray(value.entries) ? value.entries.filter(validPending) : [];
  const active = value.activeFileId;
  if (!Array.isArray(value.entries) || entries.length !== value.entries.length
    || (active !== undefined && active !== null && typeof active !== 'string')
    || (value.metadataPending !== undefined && typeof value.metadataPending !== 'boolean')) preserveRecoveryData(suffix, raw);
  return { entries, activeFileId: active === null || typeof active === 'string' ? active : undefined,
    metadataPending: value.metadataPending === true };
}
function draftIds(change: PendingEntry): string[] { return [...new Set([change.draftId, ...(change.relatedDraftIds ?? [])].filter((id): id is string => Boolean(id)))]; }
function acknowledgeDraft(change: PendingEntry) {
  for (const id of [...draftIds(change), ...(change.replaces ?? [])]) localStorage.setItem(key(':outbox-ack:') + id, '1');
}
function readOutbox() {
  const legacy = parseOutbox(localStorage.getItem(key(':outbox')), ':outbox');
  const candidates = [...legacy.entries];
  for (const journalKey of Object.keys(localStorage).filter(item => item.startsWith(key(':outbox-journal:')))) {
    candidates.push(...parseOutbox(localStorage.getItem(journalKey), ':journal').entries);
  }
  const byId = new Map<string, PendingEntry>(), seen = new Set<string>();
  for (const [id, value] of candidates) {
    const change: PendingEntry = { ...value, draftId: value.draftId ?? newWorkspaceId() };
    if (seen.has(change.draftId!) || localStorage.getItem(key(':outbox-ack:') + change.draftId)) continue;
    seen.add(change.draftId!);
    const prior = byId.get(id);
    if (!prior) { byId.set(id, change); continue; }
    if (same(prior.entry, change.entry)) { prior.relatedDraftIds = [...new Set([...(prior.relatedDraftIds ?? []), ...draftIds(change)])]; continue; }
    if (change.type !== 'file' || prior.type !== 'file') {
      prior.conflict = true; recoveryWarning = 'Conflicting offline folder changes are preserved in browser recovery storage.'; continue;
    }
    prior.conflict = true;
    const original = change.entry;
    const dot = original.name.lastIndexOf('.'), stem = dot > 0 ? original.name.slice(0, dot) : original.name;
    const extension = dot > 0 ? original.name.slice(dot) : '';
    const directory = original.path.includes('/') ? original.path.slice(0, original.path.lastIndexOf('/') + 1) : '';
    const recoveredId = newWorkspaceId(), name = stem.slice(0, 64) + '_recovered_' + recoveredId.slice(0, 8) + extension;
    byId.set(recoveredId, { ...change, entry: { ...original, id: recoveredId, path: directory + name, name, version: 0 }, expectedVersion: 0, conflict: false });
    recoveryWarning = 'Different offline versions were preserved as separate recovered files. Review them before continuing.';
  }
  return { ...legacy, entries: [...byId.entries()] };
}
function cleanAcknowledgedJournals() {
  const references = new Set<string>();
  for (const journalKey of Object.keys(localStorage).filter(item => item.startsWith(key(':outbox-journal:')))) {
    let parsed: unknown;
    try { parsed = JSON.parse(localStorage.getItem(journalKey) ?? 'null'); } catch { continue; }
    const entries = (parsed as { entries?: unknown } | null)?.entries;
    if (!Array.isArray(entries) || !entries.every(validPending) || entries.some(([, change]) => !change.draftId)) continue;
    if (entries.every(([, change]) => draftIds(change).every(id => localStorage.getItem(key(':outbox-ack:') + id)))) {
      localStorage.removeItem(journalKey);
    } else for (const [, change] of entries) for (const id of draftIds(change)) references.add(id);
  }
  // The compatibility mirror can still contain a just-acknowledged entry.
  const mirror: unknown = read(':outbox', {});
  const entries = (mirror as { entries?: unknown } | null)?.entries;
  if (Array.isArray(entries)) for (const item of entries) if (validPending(item)) for (const id of draftIds(item[1])) references.add(id);
  for (const ackKey of Object.keys(localStorage).filter(item => item.startsWith(key(':outbox-ack:')))) {
    if (!references.has(ackKey.slice(key(':outbox-ack:').length))) localStorage.removeItem(ackKey);
  }
}
function persist() {
  // Outbox is written before the disposable server cache. It contains drafts,
  // their original versions and owner-scoped identifiers, never credentials.
  // Never replace an unreadable original unless its recovery copy succeeded.
  for (const copy of recoveryCopies) {
    try { localStorage.setItem(copy.backupKey, copy.raw); }
    catch { throw new Error('Browser recovery storage is full. Unreadable drafts remain untouched; copy your current draft before leaving.'); }
  }
  recoveryCopies = [];
  const original = localStorage.getItem(getWorkspaceStorageKey());
  for (const change of pending.values()) change.draftId ??= newWorkspaceId();
  const outbox = JSON.stringify({ entries: [...pending.entries()], activeFileId, metadataPending });
  const nextJournalKey = workspaceOwner && pending.size ? key(':outbox-journal:') + newWorkspaceId() : null;
  const durableKey = nextJournalKey ?? key(':outbox');
  try { localStorage.setItem(durableKey, outbox); }
  catch {
    let disposableCloudMirror = false;
    try {
      const cached: unknown = original ? JSON.parse(original) : [];
      disposableCloudMirror = Boolean(workspaceOwner) && Array.isArray(cached)
        && cached.every(file => isFile(file) && Boolean(file.version));
    } catch { /* An unreadable or legacy source cache must remain untouched. */ }
    if (!disposableCloudMirror) throw new Error('Browser recovery storage is full. Copy your current draft before leaving this page.');
    localStorage.removeItem(getWorkspaceStorageKey());
    try { localStorage.setItem(durableKey, outbox); }
    catch { throw new Error('Browser recovery storage is full. Your current draft remains open; copy it before leaving this page.'); }
  }
  if (nextJournalKey) {
    try { localStorage.setItem(key(':outbox'), outbox); } catch { /* This mirror is disposable; the immutable journal succeeded. */ }
  }
  for (const change of pending.values()) {
    for (const id of change.replaces ?? []) localStorage.setItem(key(':outbox-ack:') + id, '1');
    change.replaces = [];
  }
  if (ownJournalKey) localStorage.removeItem(ownJournalKey);
  ownJournalKey = nextJournalKey;
  if (workspaceOwner) cleanAcknowledgedJournals();
  if (original) {
    let valid = false;
    try { const parsed: unknown = JSON.parse(original); valid = Array.isArray(parsed) && parsed.every(isFile); } catch { /* Preserve unreadable legacy data before replacing its cache. */ }
    if (!valid) localStorage.setItem(key(':unreadable-cache:') + Date.now(), original);
  }
  const cache = JSON.stringify(files ?? []);
  try { localStorage.setItem(getWorkspaceStorageKey(), workspaceOwner && cache.length > 1_000_000 ? '[]' : cache); }
  catch (reason) { if (!workspaceOwner) throw reason; }
  try {
    localStorage.setItem(key(':folderEntries'), JSON.stringify(folderEntries));
    localStorage.setItem(key(':active'), JSON.stringify(activeFileId));
  } catch (reason) { if (!workspaceOwner) throw reason; }
}
function statusError(reason: unknown): string { return reason instanceof Error ? reason.message : 'Workspace synchronization failed. Your draft is preserved locally.'; }
class WorkspaceError extends Error { constructor(message: string, public status: number) { super(message); } }
async function request<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const epoch = generation;
  const accountSignal = controller.signal, bounded = new AbortController();
  const cancel = () => bounded.abort();
  accountSignal.addEventListener('abort', cancel, { once: true });
  if (accountSignal.aborted) bounded.abort();
  const timeout = window.setTimeout(() => bounded.abort(), 15000);
  let response: Response;
  let data: unknown;
  try {
    response = await fetch('/api/workspace' + path, { method, credentials: 'same-origin', signal: bounded.signal,
      headers: body === undefined ? {} : { 'Content-Type': 'application/json' }, body: body === undefined ? undefined : JSON.stringify(body) });
    data = await response.json().catch(() => null);
  } finally { clearTimeout(timeout); accountSignal.removeEventListener('abort', cancel); }
  if (epoch !== generation) throw new WorkspaceError('The account changed. This draft remains in its original account.', 409);
  if (response.status === 401) window.dispatchEvent(new Event('qore:session-expired'));
  if (!response.ok) throw new WorkspaceError(response.status === 409
    ? 'A newer cloud version or a deletion conflicts with this draft. Duplicate the file to keep a separate copy; no cloud content was overwritten.'
    : (data as { error?: { message?: string } } | null)?.error?.message ?? 'Workspace service is unavailable. Your draft remains on this device.', response.status);
  return data as T;
}
function toFile(entry: WorkspaceEntry): WorkspaceFile {
  return { id: entry.id, path: entry.path, name: entry.name, source: entry.source, kind: entry.kind ?? 'python',
    type: 'file', version: entry.version, updated_at: entry.updated_at, syncState: 'saved' };
}
function same(left: WorkspaceFile | WorkspaceEntry, right: WorkspaceFile | WorkspaceEntry) {
  return left.path === right.path && left.source === right.source && left.kind === right.kind;
}
function putPending(file: WorkspaceFile) {
  const previous = pending.get(file.id);
  pending.set(file.id, { entry: { ...file, syncState: 'pending' }, type: 'file',
    expectedVersion: previous?.expectedVersion ?? file.version ?? 0, conflict: previous?.conflict,
    draftId: newWorkspaceId(), replaces: [...draftIds(previous ?? {} as PendingEntry), ...(previous?.replaces ?? [])] });
}
function schedule() {
  if (timer !== undefined) window.clearTimeout(timer);
  if (workspaceOwner && ready && !mutationOpen) timer = window.setTimeout(() => { void flushWorkspaceChanges(); }, 650);
}
export function setWorkspaceOwner(userId: string | null) {
  const next = userId?.trim() || null;
  if (workspaceOwner === next && files !== null) return;
  if (timer !== undefined) window.clearTimeout(timer);
  controller.abort(); controller = new AbortController(); generation++;
  workspaceOwner = next; ready = !next; saving = false; flight = null; syncError = ''; recoveryWarning = ''; recoveryCopies = []; ownJournalKey = null;
  const cached: unknown = read('', []);
  files = Array.isArray(cached) ? cached.filter(isFile) : [];
  const rawFolders = localStorage.getItem(key(':folderEntries'));
  let cachedFolders: unknown = [];
  try { cachedFolders = rawFolders ? JSON.parse(rawFolders) : []; }
  catch { preserveRecoveryData(':folders', rawFolders!); }
  folderEntries = Array.isArray(cachedFolders) ? cachedFolders.filter(isFolder) : [];
  if (rawFolders && (!Array.isArray(cachedFolders) || folderEntries.length !== cachedFolders.length)) preserveRecoveryData(':folders', rawFolders);
  const outbox = readOutbox();
  pending = new Map(outbox.entries);
  // The server mirror is disposable and may be absent because of storage quota.
  // Unsynchronized drafts must still be visible when a refresh happens offline.
  const recoveredFiles = new Map(files.map(file => [file.id, file]));
  const recoveredFolders = new Map(folderEntries.map(folder => [folder.id, folder]));
  for (const [id, change] of pending) {
    if (change.type === 'file') recoveredFiles.set(id, { ...change.entry, type: 'file', kind: change.entry.kind ?? 'python', syncState: change.conflict ? 'conflict' : 'pending' } as WorkspaceFile);
    else recoveredFolders.set(id, change.entry as WorkspaceEntry);
  }
  files = [...recoveredFiles.values()]; folderEntries = [...recoveredFolders.values()];
  activeFileId = outbox.activeFileId === undefined ? read<string | null>(':active', null) : outbox.activeFileId;
  metadataPending = outbox.metadataPending ?? false;
  trash = []; lastDeletedId = null; deleting.clear(); mutationOpen = false;
  notify();
}
export function getWorkspaceStatus(): WorkspaceStatus {
  return { owner: workspaceOwner, ready, saving, pending: pending.size + Number(metadataPending), error: [syncError, recoveryWarning].filter(Boolean).join(' '),
    conflicts: [...pending.values()].filter(value => value.conflict).length, trash: [...trash], lastDeletedId, serverOffset, lockedFiles: [...deleting] };
}
export function loadWorkspaceFiles(): WorkspaceFile[] {
  if (files === null) setWorkspaceOwner(workspaceOwner);
  return [...(files ?? [])];
}
export function getActiveWorkspaceFile(): WorkspaceFile | undefined { return loadWorkspaceFiles().find(file => file.id === activeFileId); }
function applySnapshot(snapshot: WorkspaceSnapshot, migrateLegacy = false) {
  const cloud = new Map(snapshot.files.map(entry => [entry.id, toFile(entry)]));
  const prior = loadWorkspaceFiles();
  if (migrateLegacy && workspaceOwner) {
    const idMap = new Map<string, string>();
    for (const file of prior) {
      if (file.version || pending.has(file.id)) continue;
      const existing = snapshot.files.find(entry => entry.path === file.path);
      if (existing && same(existing, file)) { idMap.set(file.id, existing.id); continue; }
      const id = uuid.test(file.id) ? file.id : newWorkspaceId();
      idMap.set(file.id, id);
      const migrated = { ...file, id, version: 0, syncState: 'pending' as const };
      putPending(migrated);
      if (existing) pending.get(id)!.conflict = true;
    }
    if (activeFileId && idMap.has(activeFileId)) { activeFileId = idMap.get(activeFileId)!; metadataPending = true; }
    const legacyFolders = read<string[]>(':folders', []);
    for (const path of legacyFolders) {
      if (snapshot.folders.some(folder => folder.path === path) || folderEntries.some(folder => folder.path === path)) continue;
      const entry = makeFolder(path); folderEntries.push(entry);
      pending.set(entry.id, { entry, expectedVersion: 0, type: 'folder' });
    }
  }
  for (const [id, change] of [...pending]) {
    if (change.type !== 'file') continue;
    const remote = cloud.get(id);
    if (remote && same(remote, change.entry)) { acknowledgeDraft(change); pending.delete(id); continue; }
    const occupied = snapshot.files.some(entry => entry.path === change.entry.path && entry.id !== id);
    const conflict = change.conflict || occupied || snapshot.trash.some(entry => entry.id === id)
      || (remote ? remote.version !== change.expectedVersion : change.expectedVersion > 0);
    change.conflict = conflict;
    cloud.set(id, { ...change.entry, type: 'file', kind: change.entry.kind ?? 'python',
      syncState: conflict ? 'conflict' : 'pending' } as WorkspaceFile);
  }
  files = [...cloud.values()];
  const folders = new Map(snapshot.folders.map(entry => [entry.id, entry]));
  for (const [id, change] of pending) if (change.type === 'folder') {
    const remote = folders.get(id);
    if (remote && remote.path === change.entry.path) { acknowledgeDraft(change); pending.delete(id); continue; }
    folders.set(id, change.entry as WorkspaceEntry);
  }
  folderEntries = [...folders.values()];
  trash = snapshot.trash; lastDeletedId = snapshot.last_deleted_id;
  serverOffset = Date.parse(snapshot.server_time) - Date.now();
  if (!metadataPending) activeFileId = snapshot.active_file_id;
  if (activeFileId && !files.some(file => file.id === activeFileId)) { activeFileId = null; metadataPending = false; }
  syncError = [...pending.values()].some(change => change.conflict) ? 'A newer cloud version exists. Local drafts are preserved; duplicate a conflicted file to keep a separate copy.' : '';
  persist(); notify();
}
export async function initializeWorkspace(userId: string | null): Promise<void> {
  setWorkspaceOwner(userId);
  if (!userId) { ready = true; notify(); return; }
  const epoch = generation;
  try {
    if (flight) await flight;
    const snapshot = await request<WorkspaceSnapshot>('');
    if (epoch !== generation) return;
    applySnapshot(snapshot, true); ready = true; notify(); schedule();
  } catch (reason) {
    if (epoch !== generation) return;
    syncError = 'Cloud workspace could not be loaded. Cached drafts are preserved. ' + statusError(reason);
    ready = false; notify();
    throw reason;
  }
}
export function saveWorkspaceFiles(next: WorkspaceFile[]) {
  const prior = loadWorkspaceFiles();
  for (const file of next) {
    const before = prior.find(item => item.id === file.id);
    if (deleting.has(file.id)) continue;
    if (!before || !same(before, file)) { if (workspaceOwner) putPending(file); }
  }
  files = next.filter(file => !deleting.has(file.id)).map(file => {
    const change = pending.get(file.id);
    return { ...file, syncState: workspaceOwner ? change ? change.conflict ? 'conflict' : 'pending' : 'saved' : 'local' };
  });
  persist(); notify(); schedule();
}
export function updateWorkspaceBuffer(id: string, source: string) {
  const current = loadWorkspaceFiles();
  if (!current.some(file => file.id === id) || deleting.has(id)) return;
  saveWorkspaceFiles(current.map(file => file.id === id ? { ...file, source } : file));
}
export async function flushWorkspaceChanges(): Promise<boolean> {
  if (!workspaceOwner) return true;
  if (!ready) return false;
  if (flight) { await flight; return pending.size && !syncError ? flushWorkspaceChanges() : !syncError; }
  if (timer !== undefined) window.clearTimeout(timer);
  const epoch = generation;
  saving = true; syncError = [...pending.values()].some(change => change.conflict) ? 'A newer cloud version conflicts with a preserved local draft. Keep that draft as a new file to resolve it.' : ''; notify();
  flight = (async () => {
    for (const [id, change] of [...pending]) {
      if (epoch !== generation) return false;
      if (change.conflict || deleting.has(id)) continue;
      try {
        const entry = change.entry;
        const payload = change.type === 'file'
          ? { path: entry.path, source: entry.source, kind: entry.kind, expected_version: change.expectedVersion }
          : { path: entry.path, expected_version: change.expectedVersion };
        const stored = await request<WorkspaceEntry>('/' + (change.type === 'file' ? 'files' : 'folders') + '/' + id, 'PUT', payload);
        if (epoch !== generation) return false;
        acknowledgeDraft(change);
        const latest = pending.get(id);
        if (latest === change) pending.delete(id);
        else if (latest) { latest.expectedVersion = stored.version; latest.entry = { ...latest.entry, version: stored.version }; }
        if (change.type === 'file') files = loadWorkspaceFiles().map(file => file.id === id
          ? { ...file, version: stored.version, updated_at: stored.updated_at, syncState: pending.has(id) ? 'pending' : 'saved' } : file);
        else folderEntries = folderEntries.map(folder => folder.id === id ? stored : folder);
        persist(); notify();
      } catch (reason) {
        if (epoch !== generation) return false;
        change.conflict = reason instanceof WorkspaceError && reason.status === 409;
        files = loadWorkspaceFiles().map(file => file.id === id ? { ...file, syncState: change.conflict ? 'conflict' : 'error' } : file);
        syncError = statusError(reason); persist(); notify();
      }
    }
    if (metadataPending && !pending.size && !syncError) {
      try {
        const selected = activeFileId;
        await request<WorkspaceSnapshot>('/state', 'PATCH', { active_file_id: selected });
        if (epoch !== generation) return false;
        if (selected === activeFileId) metadataPending = false;
        persist();
      } catch (reason) { if (epoch === generation) syncError = statusError(reason); }
    }
    return !pending.size && !syncError;
  })();
  try { return await flight; }
  finally {
    if (epoch === generation) { flight = null; saving = false; notify(); if (pending.size && !syncError && ![...pending.values()].some(value => value.conflict)) schedule(); }
  }
}
export async function retryWorkspaceSync() {
  if (workspaceOwner) await initializeWorkspace(workspaceOwner);
  return flushWorkspaceChanges();
}
export async function keepWorkspaceDraftAsCopy(id: string): Promise<WorkspaceFile> {
  const original = loadWorkspaceFiles().find(file => file.id === id);
  if (!original || !pending.get(id)?.conflict) throw new Error('This file has no conflicting draft.');
  const extension = original.name.includes('.') ? original.name.slice(original.name.lastIndexOf('.')) : '';
  const stem = original.name.slice(0, original.name.length - extension.length);
  const directory = original.path.includes('/') ? original.path.slice(0, original.path.lastIndexOf('/') + 1) : '';
  let name = stem + '_recovered' + extension, suffix = 2;
  while (loadWorkspaceFiles().some(file => file.path === directory + name)) name = stem + '_recovered_' + suffix++ + extension;
  const copy: WorkspaceFile = { ...original, id: newWorkspaceId(), path: directory + name, name, version: 0, syncState: 'pending' };
  saveWorkspaceFiles([copy, ...loadWorkspaceFiles()]);
  await flushWorkspaceChanges();
  if (pending.has(copy.id)) throw new Error('The recovery copy remains on this device. Retry sync before resolving this conflict.');
  const resolved = pending.get(id);
  if (resolved) acknowledgeDraft(resolved);
  pending.delete(id);
  setActiveWorkspaceFile(copy.id);
  if (workspaceOwner) await initializeWorkspace(workspaceOwner);
  return loadWorkspaceFiles().find(file => file.id === copy.id) ?? copy;
}
export function setActiveWorkspaceFile(id: string | null) {
  activeFileId = id; metadataPending = Boolean(workspaceOwner);
  persist(); notify(); schedule();
}
export function loadWorkspaceFolders(): string[] {
  const stored = workspaceOwner ? folderEntries.map(folder => folder.path) : read<string[]>(':folders', ['circuits', 'openqasm']);
  const derived = loadWorkspaceFiles().flatMap(file => file.path.includes('/') ? [file.path.slice(0, file.path.lastIndexOf('/'))] : []);
  return [...new Set([...stored, ...derived].flatMap(path => {
    const parts = path.split('/');
    return parts.map((_, index) => parts.slice(0, index + 1).join('/'));
  }))];
}
function makeFolder(path: string): WorkspaceEntry {
  return { id: newWorkspaceId(), path, name: path.split('/').pop() ?? path, type: 'folder', source: '', kind: null,
    version: 0, created_at: '', updated_at: '', deleted_at: null, expires_at: null };
}
export function saveWorkspaceFolders(paths: string[]) {
  const clean = [...new Set(paths.map(path => path.trim()).filter(Boolean))];
  if (workspaceOwner) for (const path of clean) {
    if (folderEntries.some(folder => folder.path === path)) continue;
    const entry = makeFolder(path); folderEntries.push(entry); pending.set(entry.id, { entry, expectedVersion: 0, type: 'folder' });
  }
  localStorage.setItem(key(':folders'), JSON.stringify(clean));
  persist(); notify(); schedule();
}
async function freshFolder(path: string): Promise<WorkspaceEntry> {
  if (!await flushWorkspaceChanges()) throw new Error(syncError || 'Save pending drafts before changing this folder.');
  applySnapshot(await request<WorkspaceSnapshot>(''));
  let folder = folderEntries.find(entry => entry.path === path);
  if (!folder) {
    folder = makeFolder(path);
    folder = await request<WorkspaceEntry>('/folders/' + folder.id, 'PUT', { path, expected_version: 0 });
  }
  return folder;
}
async function changeStructure(operation: () => Promise<void>) {
  if (mutationOpen) throw new Error('Another workspace change is in progress. Please wait.');
  const epoch = generation;
  mutationOpen = true;
  if (timer !== undefined) window.clearTimeout(timer);
  try { await operation(); }
  finally { if (epoch === generation) { mutationOpen = false; notify(); schedule(); } }
}
export async function renameWorkspaceFolder(oldPath: string, newPath: string) { return changeStructure(async () => {
  if (!workspaceOwner) {
    saveWorkspaceFolders(loadWorkspaceFolders().map(path => path === oldPath || path.startsWith(oldPath + '/')
      ? newPath + path.slice(oldPath.length) : path));
    saveWorkspaceFiles(loadWorkspaceFiles().map(file => file.path.startsWith(oldPath + '/')
      ? { ...file, path: newPath + file.path.slice(oldPath.length), name: file.name } : file));
    return;
  }
  const folder = await freshFolder(oldPath);
  await request('/folders/' + folder.id, 'PUT', { path: newPath, expected_version: folder.version });
  applySnapshot(await request<WorkspaceSnapshot>(''));
}); }
export async function deleteWorkspaceFile(id: string) { return changeStructure(async () => {
  const file = loadWorkspaceFiles().find(entry => entry.id === id);
  if (!file) return;
  if (!workspaceOwner) { files = loadWorkspaceFiles().filter(entry => entry.id !== id); persist(); notify(); return; }
  if (!await flushWorkspaceChanges()) throw new Error(syncError || 'Save pending edits before deleting this file.');
  const stored = loadWorkspaceFiles().find(entry => entry.id === id)!;
  deleting.add(id);
  notify();
  try {
    const snapshot = await request<WorkspaceSnapshot>('/files/' + id, 'DELETE', { expected_version: stored.version });
    pending.delete(id); applySnapshot(snapshot);
  } finally { deleting.delete(id); notify(); }
}); }
export async function deleteWorkspaceFolder(path: string) { return changeStructure(async () => {
  if (!workspaceOwner) {
    localStorage.setItem(key(':folders'), JSON.stringify(loadWorkspaceFolders().filter(folder => folder !== path && !folder.startsWith(path + '/'))));
    files = loadWorkspaceFiles().filter(file => !file.path.startsWith(path + '/')); persist(); notify(); return;
  }
  const folder = await freshFolder(path);
  const descendants = loadWorkspaceFiles().filter(file => file.path.startsWith(path + '/')).map(file => file.id);
  descendants.forEach(id => deleting.add(id));
  notify();
  try { applySnapshot(await request<WorkspaceSnapshot>('/folders/' + folder.id, 'DELETE', { expected_version: folder.version })); }
  finally { descendants.forEach(id => deleting.delete(id)); notify(); }
}); }
export async function refreshWorkspaceTrash() {
  if (!workspaceOwner) return;
  const result = await request<{ trash: WorkspaceEntry[]; retention_hours: number; server_time: string }>('/trash');
  trash = result.trash; serverOffset = Date.parse(result.server_time) - Date.now(); notify();
}
export async function restoreWorkspaceEntry(entry: WorkspaceEntry) { return changeStructure(async () => {
  if (!workspaceOwner) return;
  if (!await flushWorkspaceChanges()) throw new Error(syncError || 'Resolve pending edits before restoring files.');
  applySnapshot(await request<WorkspaceSnapshot>('/' + (entry.type === 'folder' ? 'folders' : 'files') + '/' + entry.id + '/restore', 'POST'));
}); }
export async function undoWorkspaceDeletion() { return changeStructure(async () => {
  if (!workspaceOwner || !lastDeletedId) return;
  if (!await flushWorkspaceChanges()) throw new Error(syncError || 'Resolve pending edits before undoing a deletion.');
  applySnapshot(await request<WorkspaceSnapshot>('/undo', 'POST'));
}); }
export function addStarterFile(): WorkspaceFile {
  const list = loadWorkspaceFiles();
  let path = 'circuits/my_first_qubits.py', suffix = 2;
  while (list.some(file => file.path === path)) path = 'circuits/my_first_qubits_' + suffix++ + '.py';
  const file: WorkspaceFile = { id: newWorkspaceId(), name: path.split('/').pop()!, path, type: 'file', kind: 'python', qubits: 3,
    source: '# My first three qubits — a GHZ state\n# Run this circuit: only 000 and 111 should be measured.\nfrom qiskit import QuantumCircuit\n\nqc = QuantumCircuit(3, 3)\n\nqc.h(0)\nqc.cx(0, 1)\nqc.cx(1, 2)\n\nqc.measure(0, 0)\nqc.measure(1, 1)\nqc.measure(2, 2)\n' };
  saveWorkspaceFiles([file, ...list]); return file;
}
export function addBlankFile(): WorkspaceFile {
  const list = loadWorkspaceFiles();
  let path = 'circuits/untitled.py', suffix = 2;
  while (list.some(file => file.path === path)) path = 'circuits/untitled_' + suffix++ + '.py';
  const file: WorkspaceFile = { id: newWorkspaceId(), name: path.split('/').pop()!, path, type: 'file', kind: 'python', source: '' };
  saveWorkspaceFiles([file, ...list]); return file;
}
export function addQasmStarterFile(): WorkspaceFile {
  const list = loadWorkspaceFiles();
  let path = 'openqasm/qaoa_maxcut.qasm', suffix = 2;
  while (list.some(file => file.path === path)) path = 'openqasm/qaoa_maxcut_' + suffix++ + '.qasm';
  const file: WorkspaceFile = { id: newWorkspaceId(), name: path.split('/').pop()!, path, type: 'file', kind: 'qasm', qubits: 4,
    source: 'OPENQASM 2.0;\ninclude "qelib1.inc";\n\n// 4-Qubit QAOA Max-Cut Graph Partition\nqreg q[4];\ncreg c[4];\n\nh q[0];\nh q[1];\nh q[2];\nh q[3];\n\ncx q[0], q[1];\nrz(0.45) q[1];\ncx q[0], q[1];\n\ncx q[1], q[2];\nrz(0.45) q[2];\ncx q[1], q[2];\n\nrx(0.62) q[0];\nrx(0.62) q[1];\nrx(0.62) q[2];\nrx(0.62) q[3];\n\nmeasure q -> c;\n' };
  saveWorkspaceFiles([file, ...list]); return file;
}
