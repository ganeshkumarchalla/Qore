export type IconName = 'code' | 'circuit' | 'lab' | 'forge' | 'research' | 'spark' | 'plus' | 'chevron' | 'play' | 'check' | 'save' | 'folder' | 'clock' | 'arrow' | 'edit' | 'close' | 'menu' | 'refresh' | 'info' | 'copy' | 'gear' | 'search' | 'file' | 'filePlus' | 'folderPlus' | 'trash' | 'collapse' | 'expand' | 'filter' | 'more' | 'python' | 'explorer' | 'terminal' | 'cube' | 'eye' | 'eyeOff' | 'account' | 'upload' | 'download';
const paths: Record<IconName, React.ReactNode> = {
  account: (
    <>
      <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
      <circle cx="12" cy="7" r="4" />
    </>
  ),
  code: <><path d="m8 7-5 5 5 5m8-10 5 5-5 5m-3-13-2 16"/></>, circuit: <><path d="M2 7h20M2 17h20M8 7v10"/><circle cx="8" cy="7" r="2"/><rect x="14" y="13" width="6" height="8" rx="1"/></>,
  lab: <><path d="M9 3h6m-5 0v7L4 20h16l-6-10V3M8 14h8"/></>, forge: <><path d="m13 2-9 12h7l-1 8 10-12h-7z"/></>, research: <><path d="M5 3h14v18H5zM9 7h6M9 11h6M9 15h3"/></>, spark: <><path d="m12 2 2.5 7.5L22 12l-7.5 2.5L12 22l-2.5-7.5L2 12l7.5-2.5z"/></>,
  plus: <path d="M12 5v14M5 12h14"/>, chevron: <path d="m9 5 7 7-7 7"/>, play: <path d="m8 4 12 8-12 8z"/>, check: <path d="m5 12 4 4L19 6"/>, save: <><path d="M4 3h13l3 3v15H4zM8 3v6h8V3M8 21v-8h8v8"/></>, folder: <path d="M3 6h7l2 3h9v11H3z"/>, clock: <><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></>, arrow: <path d="M4 12h16m-6-6 6 6-6 6"/>, edit: <><path d="m4 16 12-12 4 4L8 20H4zM13 7l4 4"/></>, close: <path d="m6 6 12 12M6 18 18 6"/>, menu: <path d="M4 6h16M4 12h16M4 18h16"/>, refresh: <><path d="M20 10a8 8 0 1 0-2 8M20 3v7h-7"/></>, info: <><circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7h.01"/></>, copy: <><rect x="8" y="8" width="12" height="13" rx="2"/><path d="M16 8V3H3v13h5"/></>,
  gear: <><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></>,
  search: <><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></>,
  file: <><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></>,
  filePlus: <><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="12" y1="18" x2="12" y2="12"/><line x1="9" y1="15" x2="15" y2="15"/></>,
  folderPlus: <><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/><line x1="12" y1="11" x2="12" y2="17"/><line x1="9" y1="14" x2="15" y2="14"/></>,
  trash: <><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></>,
  collapse: <><polyline points="4 14 10 14 10 20"/><polyline points="20 10 14 10 14 4"/><line x1="14" y1="10" x2="21" y2="3"/><line x1="3" y1="21" x2="10" y2="14"/></>,
  expand: <><polyline points="15 3 21 3 21 9"/><polyline points="9 21 3 21 3 15"/><line x1="21" y1="3" x2="14" y2="10"/><line x1="3" y1="21" x2="10" y2="14"/></>,
  filter: <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/>,
  more: <><circle cx="12" cy="12" r="1.5"/><circle cx="19" cy="12" r="1.5"/><circle cx="5" cy="12" r="1.5"/></>,
  python: <><path d="M12 2c-3.3 0-6 1.3-6 3.5v2.5h6v1H4.5C2.5 9 1 10.8 1 13s1.5 4 3.5 4h1.5v-2.5c0-1.7 1.3-3 3-3h5c1.7 0 3-1.3 3-3V5.5C17 3.3 14.8 2 12 2zm-1.5 2a1 1 0 1 1 0 2 1 1 0 0 1 0-2zm1.5 18c3.3 0 6-1.3 6-3.5V16h-6v-1h7.5c2 0 3.5-1.8 3.5-4s-1.5-4-3.5-4H18v2.5c0 1.7-1.3 3-3 3h-5c-1.7 0-3 1.3-3 3v3c0 2.2 2.2 3.5 5 3.5zm1.5-2a1 1 0 1 1 0-2 1 1 0 0 1 0 2z"/></>,
  explorer: (
    <>
      <path d="M15.5 2H8.6c-.9 0-1.6.7-1.6 1.6v13.8c0 .9.7 1.6 1.6 1.6h9.8c.9 0 1.6-.7 1.6-1.6V6.5L15.5 2z" />
      <path d="M15 2v5h5" />
      <path d="M4 6.5C3.4 6.5 3 7 3 7.6v13.8C3 22 3.5 22.5 4.1 22.5h9.8c.6 0 1.1-.4 1.1-1" />
    </>
  ),
  terminal: (
    <>
      <polyline points="4 17 10 11 4 5" />
      <line x1="12" y1="19" x2="20" y2="19" />
    </>
  ),
  cube: (
    <>
      <path d="m21 16-9 5-9-5V8l9-5 9 5z" />
      <path d="m3.27 6.96 8.73 4.99 8.73-4.99" />
      <line x1="12" y1="21.5" x2="12" y2="11.95" />
    </>
  ),
  eye: (
    <>
      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
      <circle cx="12" cy="12" r="3" />
    </>
  ),
  upload: <><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></>,
  download: <><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></>,
  eyeOff: (
    <>
      <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
      <line x1="1" y1="1" x2="23" y2="23" />
    </>
  ),
};
export function Icon({ name, size = 18 }: { name: IconName; size?: number }) { return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.65" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>; }
export function Logo() { return <svg viewBox="0 0 44 44" width="36" height="36" fill="none" aria-hidden="true"><circle cx="20" cy="20" r="13" stroke="#57D9FF" strokeWidth="2.4"/><ellipse cx="20" cy="20" rx="5" ry="13" transform="rotate(43 20 20)" stroke="#9A83FF" strokeWidth="1.5"/><path d="m29 29 9 9" stroke="#57D9FF" strokeWidth="3"/><circle cx="20" cy="20" r="2.5" fill="#57D9FF"/></svg>; }
