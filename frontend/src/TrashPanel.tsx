import { useEffect, useRef, useState } from 'react';
import { Icon } from './Icons';
import type { WorkspaceEntry } from './types';
import { getWorkspaceStatus, refreshWorkspaceTrash, restoreWorkspaceEntry, WORKSPACE_CHANGED_EVENT } from './workspace';

export function TrashPanel({ isOpen, onClose, onRestored }: { isOpen: boolean; onClose: () => void; onRestored: (id: string) => void }) {
  const [status, setStatus] = useState(getWorkspaceStatus);
  const [pending, setPending] = useState<string | null>(null);
  const [error, setError] = useState('');
  const [now, setNow] = useState(Date.now());
  const panel = useRef<HTMLDivElement>(null);
  const close = useRef(onClose); close.current = onClose;
  useEffect(() => {
    if (!isOpen) return;
    let mounted = true;
    const sync = () => setStatus(getWorkspaceStatus());
    window.addEventListener(WORKSPACE_CHANGED_EVENT, sync);
    void refreshWorkspaceTrash().catch(reason => { if (mounted) setError(reason instanceof Error ? reason.message : 'Trash could not be loaded.'); });
    const tick = window.setInterval(() => setNow(Date.now()), 30000);
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const frame = requestAnimationFrame(() => panel.current?.querySelector<HTMLButtonElement>('button')?.focus());
    const onKey = (event: KeyboardEvent) => {
      const root = panel.current;
      if (!root) return;
      if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); close.current(); }
      if (event.key !== 'Tab') return;
      const controls = Array.from(root.querySelectorAll<HTMLButtonElement>('button:not(:disabled)'));
      const first = controls[0], last = controls[controls.length - 1];
      if (event.shiftKey && (document.activeElement === first || !root.contains(document.activeElement))) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && (document.activeElement === last || !root.contains(document.activeElement))) { event.preventDefault(); first?.focus(); }
    };
    document.addEventListener('keydown', onKey, true);
    return () => {
      mounted = false; clearInterval(tick); cancelAnimationFrame(frame);
      window.removeEventListener(WORKSPACE_CHANGED_EVENT, sync); document.removeEventListener('keydown', onKey, true);
      if (previous?.isConnected) previous.focus();
    };
  }, [isOpen]);
  async function restore(entry: WorkspaceEntry) {
    setPending(entry.id); setError('');
    try { await restoreWorkspaceEntry(entry); onRestored(entry.id); }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'The file could not be restored.'); }
    finally { setPending(null); }
  }
  if (!isOpen) return null;
  const currentTime = now + status.serverOffset;
  return <div className="modal-overlay glass-backdrop" onMouseDown={event => { if (event.target === event.currentTarget && !pending) onClose(); }}>
    <div ref={panel} className="qore-trash-panel" role="dialog" aria-modal="true" aria-labelledby="qore-trash-title">
      <header><div><span className="eyebrow">YOUR WORKSPACE</span><h2 id="qore-trash-title"><Icon name="restore" size={20} />Recently deleted</h2></div>
        <button type="button" className="icon-close" aria-label="Close recently deleted" onClick={onClose}><Icon name="close" size={15} /></button></header>
      <p className="help">Deleted files and folders can be restored for 48 hours from deletion. Active files never expire. Restoring will not overwrite a file already using the same path.</p>
      {error && <p role="alert" className="error-box">{error}</p>}
      <div className="qore-trash-list">
        {!status.trash.length && <div className="qore-trash-empty"><Icon name="trash" size={30} /><strong>Nothing in Trash</strong><span>Your deleted files will appear here for 48 hours.</span></div>}
        {status.trash.map(entry => {
          const expiry = Date.parse(entry.expires_at ?? '');
          const minutes = Math.max(0, Math.ceil((expiry - currentTime) / 60000));
          const expired = !Number.isFinite(expiry) || expiry <= currentTime;
          return <article className="qore-trash-entry" key={entry.id}>
            <Icon name={entry.type === 'folder' ? 'folder' : 'file'} size={18} />
            <div><strong>{entry.path}</strong><span>{expired ? 'Recovery period expired' : `Expires in ${Math.floor(minutes / 60)}h ${minutes % 60}m`} · {entry.expires_at ? new Date(entry.expires_at).toLocaleString() : ''}</span></div>
            <button type="button" className="button secondary small" disabled={Boolean(pending) || expired} onClick={() => void restore(entry)} aria-label={`Restore ${entry.path}`}>
              <Icon name="restore" size={14} />{pending === entry.id ? 'Restoring…' : 'Restore'}
            </button>
          </article>;
        })}
      </div>
    </div>
  </div>;
}
