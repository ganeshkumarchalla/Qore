import React, { useEffect, useRef, useState } from 'react';
import { Icon } from './Icons';
import { runtimeLabel, type Settings } from './types';

const GRAPHITE_ACCENT = '#d8d6d2';

export const defaultSettings: Settings = {
  theme: 'obsidian-void',
  accentColor: GRAPHITE_ACCENT,
  glassmorphism: true,
  fontFamily: "'JetBrains Mono', 'SFMono-Regular', Consolas, monospace",
  fontSize: 14,
  tabSize: 4,
  minimap: false,
  wordWrap: true,
  lineNumbers: 'on',
  cursorStyle: 'line',
  bracketPairColorization: true,
  simulationBackend: 'statevector',
  defaultShots: 1024,
  defaultSeed: 42,
  endianness: 'little',
  noiseSimulation: false,
  depolarizingRate: 0.02,
  readoutErrorRate: 0.015,
  thermalRelaxation: false,
  targetBasis: 'generic',
  defaultOptLevel: 2,
  equivalenceTolerance: '1e-9',
  routingMethod: 'sabre',
  livePulseAnimation: true,
  autoSave: true,
  maxQubitsGuard: 10,
  uiDensity: 'balanced',
  wireStyle: 'minimal',
  autoCloseBrackets: true,
  formatOnSave: true,
  zeroThreshold: '1e-9',
  hardwareTopology: 'ideal',
  errorMitigation: 'none',
  dynamicalDecoupling: 'none',
  commutationAnalysis: true,
  strictUnitaryCheck: true,
  copilotTemperature: 0.2,
  autoExplainCircuit: true,
  streamAiTokens: true,
  terminalFontSize: 13,
  terminalBlink: true,
  defaultProvider: 'ibm',
  resourceErrorBudget: '0.001',
  precisionMode: 'fp64',
};

function graphiteSettings(value: Partial<Settings>): Settings {
  return {
    ...defaultSettings,
    ...value,
    theme: 'obsidian-void',
    accentColor: GRAPHITE_ACCENT,
    glassmorphism: true,
    fontFamily: defaultSettings.fontFamily,
  };
}

export function loadStoredSettings(): Settings {
  try {
    const raw = localStorage.getItem('qore_settings');
    if (raw) {
      const parsed = JSON.parse(raw) as Record<string, unknown>;
      delete parsed.apiKey;
      delete parsed.copilotModel;
      const settings = graphiteSettings(parsed as Partial<Settings>);
      localStorage.setItem('qore_settings', JSON.stringify(settings));
      return settings;
    }
  } catch {
    // Browser storage can be unavailable in private contexts.
  }
  return graphiteSettings({});
}

export function saveStoredSettings(settings: Settings) {
  const safe = graphiteSettings(settings);
  try { localStorage.setItem('qore_settings', JSON.stringify(safe)); } catch { /* Keep the in-memory selection. */ }
  document.documentElement.setAttribute('data-theme', safe.theme);
  document.documentElement.setAttribute('data-glass', 'true');
  document.documentElement.style.setProperty('--vscode-accent', GRAPHITE_ACCENT);
}

function SettingRow({ title, detail, children }: { title: string; detail?: string; children: React.ReactNode }) {
  return <div className="qore-setting-row">
    <div className="qore-setting-copy"><strong>{title}</strong>{detail && <span>{detail}</span>}</div>
    <div className="qore-setting-input">{children}</div>
  </div>;
}

function Toggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: (value: boolean) => void }) {
  return <button type="button" role="switch" aria-label={label} aria-checked={checked}
    className={`qore-settings-switch ${checked ? 'is-on' : ''}`} onClick={() => onChange(!checked)}>
    <span />
  </button>;
}

export function SettingsModal({ settings, versions, onSave, onClose }: {
  settings: Settings;
  versions?: Record<string, string> | null;
  onSave: (next: Settings) => void;
  onClose: () => void;
}) {
  const [current, setCurrent] = useState(() => graphiteSettings(settings));
  const [section, setSection] = useState<'editor' | 'quantum'>('editor');
  const dialogRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;

  useEffect(() => {
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const frame = requestAnimationFrame(() => dialogRef.current?.querySelector<HTMLElement>('.qore-settings-nav button')?.focus());
    const onKeyDown = (event: KeyboardEvent) => {
      const dialog = dialogRef.current;
      if (!dialog) return;
      if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); closeRef.current(); return; }
      if (event.key !== 'Tab') return;
      const controls = Array.from(dialog.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled), select:not(:disabled)'))
        .filter(element => element.offsetParent !== null);
      const first = controls[0], last = controls[controls.length - 1];
      if (!first) { event.preventDefault(); dialog.focus(); return; }
      if (event.shiftKey && (document.activeElement === first || !dialog.contains(document.activeElement))) {
        event.preventDefault(); last.focus();
      } else if (!event.shiftKey && (document.activeElement === last || !dialog.contains(document.activeElement))) {
        event.preventDefault(); first.focus();
      }
    };
    document.addEventListener('keydown', onKeyDown, true);
    return () => { cancelAnimationFrame(frame); document.removeEventListener('keydown', onKeyDown, true); if (previous?.isConnected) previous.focus(); };
  }, []);

  const update = <K extends keyof Settings>(key: K, value: Settings[K]) => setCurrent(previous => ({ ...previous, [key]: value }));
  const save = (event: React.FormEvent) => {
    event.preventDefault();
    const next = graphiteSettings(current);
    saveStoredSettings(next);
    onSave(next);
    onClose();
  };

  return <div className="modal-overlay glass-backdrop" onMouseDown={event => { if (event.target === event.currentTarget) onClose(); }}>
    <div ref={dialogRef} tabIndex={-1} className="modal-card settings-card-window qore-settings" role="dialog" aria-modal="true" aria-labelledby="settings-title">
      <header className="qore-settings-header">
        <div><span className="qore-settings-kicker">QORE / PREFERENCES</span><h2 id="settings-title">Settings & Preferences</h2></div>
        <span className="qore-settings-theme">Graphite</span>
        <button type="button" className="qore-settings-close" aria-label="Close settings" onClick={onClose}><Icon name="close" size={16} /></button>
      </header>
      <form onSubmit={save} className="qore-settings-form">
        <div className="qore-settings-layout">
          <nav className="qore-settings-nav" aria-label="Settings sections">
            <button type="button" className={section === 'editor' ? 'active' : ''} aria-current={section === 'editor' ? 'page' : undefined} onClick={() => setSection('editor')}><Icon name="code" size={16} /> Editor</button>
            <button type="button" className={section === 'quantum' ? 'active' : ''} aria-current={section === 'quantum' ? 'page' : undefined} onClick={() => setSection('quantum')}><Icon name="circuit" size={16} /> Quantum</button>
            <div className="qore-settings-runtime">{runtimeLabel(versions)}<br />Limits are enforced by the server.</div>
          </nav>
          <main className="qore-settings-content">
            {section === 'editor' ? <>
              <div className="qore-settings-section-head"><h3>Editor</h3><p>Readable code, with the same graphite surface as the workbench.</p></div>
              <div className="qore-settings-group">
                <SettingRow title="Font size" detail="Code text in the editor.">
                  <div className="qore-setting-range"><input type="range" aria-label="Editor font size" min="12" max="20" value={current.fontSize} onChange={event => update('fontSize', Number(event.target.value))} /><output>{current.fontSize}px</output></div>
                </SettingRow>
                <SettingRow title="Tab width" detail="Spaces inserted when you press Tab.">
                  <select aria-label="Tab width" value={current.tabSize} onChange={event => update('tabSize', Number(event.target.value))}><option value={2}>2 spaces</option><option value={4}>4 spaces</option></select>
                </SettingRow>
                <SettingRow title="Line numbers"><Toggle label="Line numbers" checked={current.lineNumbers !== 'off'} onChange={value => update('lineNumbers', value ? 'on' : 'off')} /></SettingRow>
                <SettingRow title="Word wrap"><Toggle label="Word wrap" checked={current.wordWrap} onChange={value => update('wordWrap', value)} /></SettingRow>
                <SettingRow title="Minimap"><Toggle label="Minimap" checked={current.minimap} onChange={value => update('minimap', value)} /></SettingRow>
                <SettingRow title="Auto-close brackets"><Toggle label="Auto-close brackets" checked={current.autoCloseBrackets ?? true} onChange={value => update('autoCloseBrackets', value)} /></SettingRow>
                <SettingRow title="Format on paste" detail="Uses a language formatter when one is available."><Toggle label="Format on paste" checked={current.formatOnSave ?? true} onChange={value => update('formatOnSave', value)} /></SettingRow>
              </div>
            </> : <>
              <div className="qore-settings-section-head"><h3>Quantum</h3><p>Defaults for local simulation and Forge. Each run records its actual settings.</p></div>
              <div className="qore-settings-group">
                <SettingRow title="Simulation method" detail="Qiskit Aer chooses the numerical method.">
                  <select aria-label="Simulation method" value={current.simulationBackend} onChange={event => update('simulationBackend', event.target.value as Settings['simulationBackend'])}>
                    <option value="statevector">Statevector</option><option value="matrix_product_state">Matrix product state</option><option value="stabilizer">Stabilizer</option>
                  </select>
                </SettingRow>
                <SettingRow title="Shots" detail="Measurement samples per run.">
                  <select aria-label="Default shots" value={current.defaultShots} onChange={event => update('defaultShots', Number(event.target.value))}>
                    {[512, 1024, 2048, 4096, 8192].map(shots => <option value={shots} key={shots}>{shots.toLocaleString()}</option>)}
                  </select>
                </SettingRow>
                <SettingRow title="Random seed" detail="Use the same seed to reproduce sampled results.">
                  <input type="number" aria-label="Random seed" min="0" max="2147483647" required value={current.defaultSeed} onChange={event => update('defaultSeed', Number(event.target.value))} />
                </SettingRow>
                <SettingRow title="Noise simulation" detail="Apply gate and readout errors in Aer."><Toggle label="Noise simulation" checked={current.noiseSimulation} onChange={value => update('noiseSimulation', value)} /></SettingRow>
                {current.noiseSimulation && <>
                  <SettingRow title="Gate error" detail="Depolarizing probability per gate.">
                    <div className="qore-setting-range"><input type="range" aria-label="Gate error" min="0" max="0.1" step="0.005" value={current.depolarizingRate} onChange={event => update('depolarizingRate', Number(event.target.value))} /><output>{(current.depolarizingRate * 100).toFixed(1)}%</output></div>
                  </SettingRow>
                  <SettingRow title="Readout error" detail="Probability of a flipped measured bit.">
                    <div className="qore-setting-range"><input type="range" aria-label="Readout error" min="0" max="0.15" step="0.005" value={current.readoutErrorRate} onChange={event => update('readoutErrorRate', Number(event.target.value))} /><output>{(current.readoutErrorRate * 100).toFixed(1)}%</output></div>
                  </SettingRow>
                </>}
                <SettingRow title="Forge level" detail="Default optimization strength for a new session.">
                  <select aria-label="Forge optimization level" value={current.defaultOptLevel} onChange={event => update('defaultOptLevel', Number(event.target.value))}>
                    <option value={0}>0 · Preserve structure</option><option value={1}>1 · Light</option><option value={2}>2 · Balanced</option><option value={3}>3 · Aggressive</option>
                  </select>
                </SettingRow>
              </div>
            </>}
          </main>
        </div>
        <footer className="qore-settings-footer">
          <button type="button" className="qore-settings-reset" onClick={() => setCurrent(graphiteSettings({}))}>Reset defaults</button>
          <div><button type="button" onClick={onClose}>Cancel</button><button type="submit" className="qore-settings-save">Save settings</button></div>
        </footer>
      </form>
    </div>
  </div>;
}
