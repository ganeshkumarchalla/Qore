import React, { createContext, useContext, useEffect, useId, useRef, useState } from 'react';
import { Icon, type IconName } from './Icons';
import type { Settings, Theme } from './types';
import type { AuthUser } from './AuthModal';

export const defaultSettings: Settings = {
  theme: 'obsidian-void',
  accentColor: '#6ea8d8',
  glassmorphism: true,
  fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
  fontSize: 13,
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
  wireStyle: 'neon',
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

function normalizeTheme(theme: string | undefined): Theme {
  void theme;
  return 'obsidian-void';
}

export function loadStoredSettings(): Settings {
  try {
    const raw = localStorage.getItem('qore_settings');
    if (raw) {
      const parsed = JSON.parse(raw) as Record<string, unknown>;
      // Remove fields from older builds that incorrectly allowed credentials or
      // provider selection to be stored in browser-local settings.
      delete parsed.apiKey;
      delete parsed.copilotModel;
      if (typeof parsed.theme === 'string') parsed.theme = normalizeTheme(parsed.theme);
      localStorage.setItem('qore_settings', JSON.stringify(parsed));
      return { ...defaultSettings, ...parsed } as Settings;
    }
  } catch {
    // fallback
  }
  return defaultSettings;
}

export function saveStoredSettings(settings: Settings) {
  try {
    const safeSettings = { ...settings } as Record<string, unknown>;
    delete safeSettings.apiKey;
    delete safeSettings.copilotModel;
    localStorage.setItem('qore_settings', JSON.stringify(safeSettings));
    document.documentElement.setAttribute('data-theme', settings.theme);
    if (settings.glassmorphism) {
      document.documentElement.setAttribute('data-glass', 'true');
    } else {
      document.documentElement.removeAttribute('data-glass');
    }
    document.documentElement.style.setProperty('--vscode-accent', settings.accentColor);
  } catch {
    // ignore
  }
}

type SettingCategory = 'account' | 'optics' | 'editor' | 'kernel' | 'hardware' | 'transpiler' | 'copilot';
const SettingName = createContext<string | undefined>(undefined);

// Clean iOS / macOS styled toggle switch
function CustomToggle({
  checked,
  onChange,
  disabled,
}: {
  checked: boolean;
  onChange: (next: boolean) => void;
  disabled?: boolean;
}) {
  const accessibleName = useContext(SettingName);
  return (
    <button
      type="button"
      role="switch"
      aria-label={accessibleName}
      aria-checked={checked}
      disabled={disabled}
      className={`clean-toggle-switch ${checked ? 'active' : ''}`}
      onClick={() => onChange(!checked)}
    >
      <span className="clean-toggle-knob" />
    </button>
  );
}

// Clean standardized setting row
function SettingRow({
  title,
  desc,
  control,
  disabled = false,
  reason,
}: {
  title: string;
  desc: string;
  control: React.ReactNode;
  disabled?: boolean;
  reason?: 'Unavailable in this runtime' | 'Server controlled';
}) {
  const identity = useId();
  return (
    <div className="clean-setting-row">
      <div className="clean-setting-info">
        <span className="clean-setting-title" id={`${identity}-title`}>{title}</span>
        <span className="clean-setting-desc" id={`${identity}-description`}>{desc}</span>
        {disabled && <span className="clean-setting-desc" id={`${identity}-availability`}
          style={{ color: '#b9cbe0', fontSize: 10, marginTop: 4 }}>{reason ?? 'Unavailable in this runtime'}</span>}
      </div>
      <SettingName.Provider value={title}>
        <fieldset className="clean-setting-control" disabled={disabled}
          aria-labelledby={`${identity}-title`}
          aria-describedby={`${identity}-description${disabled ? ` ${identity}-availability` : ''}`}
          style={{ border: 0, padding: 0, margin: 0, opacity: disabled ? 0.48 : 1 }}>
          {control}
        </fieldset>
      </SettingName.Provider>
    </div>
  );
}

// Clean standardized setting card container
function SettingCard({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="clean-setting-card">
      <div className="clean-card-header">
        <span>{title}</span>
      </div>
      <div className="clean-card-body">{children}</div>
    </div>
  );
}

export function SettingsModal({
  settings,
  onSave,
  onClose,
  currentUser,
  onOpenAuth,
}: {
  settings: Settings;
  onSave: (next: Settings) => void;
  onClose: () => void;
  currentUser?: AuthUser | null;
  onOpenAuth?: () => void;
}) {
  const [current, setCurrent] = useState<Settings>({
    ...defaultSettings,
    ...settings,
    theme: normalizeTheme(settings.theme),
  });
  const [category, setCategory] = useState<SettingCategory>('optics');
  const [searchQuery, setSearchQuery] = useState('');
  const [copiedNotification, setCopiedNotification] = useState(false);
  const dialogRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef(onClose);
  const notificationTimer = useRef<number | null>(null);
  closeRef.current = onClose;

  useEffect(() => {
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const frame = requestAnimationFrame(() => dialogRef.current?.querySelector<HTMLInputElement>('.settings-search-input')?.focus());
    const handleKey = (e: KeyboardEvent) => {
      const dialog = dialogRef.current;
      if (!dialog) return;
      if (e.key === 'Escape') {
        e.preventDefault(); e.stopPropagation(); closeRef.current();
      }
      if (e.key !== 'Tab') return;
      const controls = Array.from(dialog.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled), select:not(:disabled), a[href], [tabindex="0"]'))
        .filter(element => element.offsetParent !== null);
      const first = controls[0], last = controls[controls.length - 1];
      if (!first) { e.preventDefault(); dialog.focus(); return; }
      if (e.shiftKey && (document.activeElement === first || !dialog.contains(document.activeElement))) {
        e.preventDefault(); last.focus();
      } else if (!e.shiftKey && (document.activeElement === last || !dialog.contains(document.activeElement))) {
        e.preventDefault(); first.focus();
      }
    };
    document.addEventListener('keydown', handleKey, true);
    return () => {
      cancelAnimationFrame(frame);
      document.removeEventListener('keydown', handleKey, true);
      if (notificationTimer.current !== null) window.clearTimeout(notificationTimer.current);
      if (previous?.isConnected) previous.focus();
    };
  }, []);

  const update = <K extends keyof Settings>(key: K, value: Settings[K]) => {
    setCurrent((prev) => {
      const next = { ...prev, [key]: value };
      if (key === 'theme') {
        document.documentElement.setAttribute('data-theme', value as string);
      }
      if (key === 'accentColor') {
        document.documentElement.style.setProperty('--vscode-accent', value as string);
      }
      if (key === 'glassmorphism') {
        if (value) document.documentElement.setAttribute('data-glass', 'true');
        else document.documentElement.removeAttribute('data-glass');
      }
      return next;
    });
  };

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    saveStoredSettings(current);
    onSave(current);
    onClose();
  };

  const resetDefaults = () => {
    setCurrent({ ...defaultSettings });
    saveStoredSettings(defaultSettings);
  };

  const exportSettingsJSON = () => {
    const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(current, null, 2));
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute('href', dataStr);
    downloadAnchor.setAttribute('download', 'qore_settings.json');
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
    setCopiedNotification(true);
    if (notificationTimer.current !== null) window.clearTimeout(notificationTimer.current);
    notificationTimer.current = window.setTimeout(() => setCopiedNotification(false), 2000);
  };

  const themeOptions: { id: Theme; name: string; desc: string; preview: string }[] = [
    { id: 'obsidian-void', name: 'QORE Graphite', desc: 'Permanent platform theme', preview: '#19232e' },
  ];

  const accentColors = [{ label: 'QORE Blue', color: '#6ea8d8' }];

  const categoryMeta: Record<SettingCategory, { title: string; count: number; icon: IconName }> = {
    account: { title: 'Account & Security (MFA)', count: 4, icon: 'account' },
    optics: { title: 'Workspace & Optics', count: 7, icon: 'code' },
    editor: { title: 'Monaco Editor & Terminal', count: 10, icon: 'file' },
    kernel: { title: 'Quantum Kernel (Aer)', count: 7, icon: 'circuit' },
    hardware: { title: 'Physical QPUs & Noise', count: 9, icon: 'lab' },
    transpiler: { title: 'Transpiler & Forge', count: 6, icon: 'forge' },
    copilot: { title: 'AI Copilot & Cloud', count: 6, icon: 'spark' },
  };

  const matchesSearch = (text: string) => {
    if (!searchQuery.trim()) return true;
    return text.toLowerCase().includes(searchQuery.toLowerCase().trim());
  };

  return (
    <div
      className="modal-overlay glass-backdrop"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div ref={dialogRef} tabIndex={-1} className="modal-card settings-card-window" role="dialog" aria-modal="true" aria-labelledby="settings-title">
        {/* 1. Modal Top Header */}
        <div className="settings-top-header">
          <div className="settings-header-title">
            <Icon name="gear" size={16} />
            <h3 id="settings-title">Settings & Preferences</h3>
          </div>
          <button type="button" className="icon-close" aria-label="Close settings" onClick={onClose} title="Close (Esc)">
            <Icon name="close" size={14} />
          </button>
        </div>

        {/* 2. Dedicated Full-Width Search Banner Row (Successfully Placed & Spacious) */}
        <div className="settings-search-banner-row">
          <div className="settings-search-box-wrap">
            <Icon name="search" size={14} />
            <input
              type="text"
              className="settings-search-input"
              aria-label="Search settings"
              placeholder="Search settings (e.g. shots, noise, theme, font size, seed, density)..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
            {searchQuery && (
              <button
                type="button"
                className="search-clear-btn"
                onClick={() => setSearchQuery('')}
                title="Clear search"
              >
                <Icon name="close" size={12} />
              </button>
            )}
          </div>
        </div>

        <form onSubmit={handleSave} className="settings-form-container">
          <div className="settings-form-layout">
            {/* 3. Left Secondary Sidebar */}
            <aside className="settings-nav-sidebar" aria-label="Settings categories">
              <div className="settings-sidebar-heading">CATEGORIES</div>

              {(Object.keys(categoryMeta) as SettingCategory[]).map((catKey) => {
                const meta = categoryMeta[catKey];
                const isActive = category === catKey && !searchQuery.trim();
                return (
                  <button
                    key={catKey}
                    type="button"
                    className={`settings-nav-item ${isActive ? 'active' : ''}`}
                    onClick={() => {
                      setCategory(catKey);
                      setSearchQuery('');
                    }}
                  >
                    <Icon name={meta.icon} size={15} />
                    <span className="nav-item-label">{meta.title}</span>
                    <span className="settings-category-badge">{meta.count}</span>
                  </button>
                );
              })}

              <div className="settings-sidebar-spacer" />

              <div className="settings-sidebar-footer-tip">
                <span>Qiskit Aer 0.18</span>
                <span>QORE Quantum OS</span>
              </div>
            </aside>

            {/* 4. Right Main Content Area */}
            <div className="settings-content-area">
              {/* Category Breadcrumb Bar */}
              <div className="settings-breadcrumb-bar">
                <span>Preferences</span>
                <span className="breadcrumb-sep">/</span>
                <strong>{categoryMeta[category].title}</strong>
                {searchQuery && (
                  <span className="search-filter-tag">Filter: &ldquo;{searchQuery}&rdquo;</span>
                )}
              </div>

              {/* CATEGORY 0: ACCOUNT & SECURITY (MFA) */}
              {category === 'account' && (
                <div className="settings-group-stack">
                  {matchesSearch('account profile name email identity role tier specialty affiliation bio') && (
                    <SettingCard title="QUANTUM IDENTITY & PROFILE">
                      {currentUser ? (
                        <div className="settings-account-hero">
                          <div
                            className="settings-account-avatar"
                            style={
                              currentUser.avatarUrl && currentUser.avatarUrl.startsWith('linear-gradient')
                                ? { background: currentUser.avatarUrl }
                                : { background: 'linear-gradient(135deg, #00f0ff, #3b82f6)' }
                            }
                          >
                            {currentUser.avatarUrl && currentUser.avatarUrl.startsWith('data:') ? (
                              <img src={currentUser.avatarUrl} alt={currentUser.name} className="avatar-img-round-pill" />
                            ) : (
                              <span>{currentUser.avatarInitials || currentUser.name.slice(0, 2).toUpperCase()}</span>
                            )}
                          </div>
                          <div className="settings-account-details">
                            <strong>{currentUser.name}</strong>
                            <span className="settings-account-email">{currentUser.email}</span>
                            <div className="settings-badge-row">
                              <span className="settings-tag-pill">{currentUser.tier.toUpperCase()} TIER</span>
                              <span className="settings-tag-pill">{currentUser.role}</span>
                              {currentUser.organization && <span className="settings-tag-pill">{currentUser.organization}</span>}
                            </div>
                            {currentUser.title && (
                              <div style={{ marginTop: '4px', fontSize: '11.5px', color: '#94a3b8' }}>
                                Specialty: <span style={{ color: '#e2e8f0' }}>{currentUser.title}</span>
                              </div>
                            )}
                            {currentUser.bio && (
                              <div style={{ marginTop: '2px', fontSize: '11.5px', color: '#cbd5e1', fontStyle: 'italic' }}>
                                &ldquo;{currentUser.bio}&rdquo;
                              </div>
                            )}
                          </div>
                          <div>
                            <button
                              type="button"
                              className="settings-action-btn primary"
                              onClick={() => {
                                onClose();
                                onOpenAuth?.();
                              }}
                            >
                              <Icon name="edit" size={14} />
                              <span>Edit Profile</span>
                            </button>
                          </div>
                        </div>
                      ) : (
                        <div className="settings-guest-box">
                          <p>You are working as a Guest. Sign in to sync circuits, save quantum experiments, customize your profile, and enable 2FA / MFA.</p>
                          <div>
                            <button
                              type="button"
                              className="settings-action-btn primary"
                              onClick={() => {
                                onClose();
                                onOpenAuth?.();
                              }}
                            >
                              <Icon name="account" size={14} />
                              <span>Sign In / Create Account</span>
                            </button>
                          </div>
                        </div>
                      )}
                    </SettingCard>
                  )}

                  {matchesSearch('mfa 2fa security authenticator totp two-factor backup codes') && (
                    <SettingCard title="TWO-FACTOR AUTHENTICATION (MFA / TOTP)">
                      <SettingRow
                        title="TOTP Authenticator Protection"
                        desc="Protect your account and quantum circuits with time-based one-time codes from Google Authenticator, Authy, or 1Password."
                        control={
                          <div className="settings-mfa-inline">
                            <span className={`mfa-inline-badge ${currentUser?.mfaEnabled ? 'active' : 'inactive'}`}>
                              {currentUser?.mfaEnabled ? 'ACTIVE (MFA ENABLED)' : 'NOT CONFIGURED'}
                            </span>
                            <button
                              type="button"
                              className="settings-action-btn"
                              onClick={() => {
                                onClose();
                                onOpenAuth?.();
                              }}
                            >
                              <Icon name="gear" size={13} />
                              <span>{currentUser?.mfaEnabled ? 'Manage 2FA & Codes' : 'Configure 2FA'}</span>
                            </button>
                          </div>
                        }
                      />
                    </SettingCard>
                  )}

                  {matchesSearch('workspace enclave cryptography isolation data security') && (
                    <SettingCard title="DATA ISOLATION & ENCLAVE">
                      <SettingRow
                        title="Per-Account Quantum Sandbox"
                        desc="Circuit drafts and execution metrics are cryptographically isolated per user identifier."
                        control={<span className="settings-tag-pill" style={{ color: '#38bdf8' }}>ENCLAVE VERIFIED</span>}
                      />
                      <SettingRow
                        title="Identity Enclave"
                        desc="Authentication is managed directly by QORE Supabase Enclave with secure HTTP cookies."
                        control={<span className="settings-tag-pill" style={{ color: '#34d399' }}>CONNECTED</span>}
                      />
                    </SettingCard>
                  )}
                </div>
              )}

              {/* CATEGORY 1: WORKSPACE & OPTICS */}
              {category === 'optics' && (
                <div className="settings-group-stack">
                  {matchesSearch('theme signature palette obsidian hyperion cobalt cryo plasma') && (
                    <SettingCard title="SIGNATURE THEME PALETTE">
                      <div className="theme-grid-clean">
                        {themeOptions.map((t) => (
                          <button
                            key={t.id}
                            type="button"
                            className={`theme-card-clean ${current.theme === t.id ? 'active' : ''}`}
                            onClick={() => update('theme', t.id)}
                          >
                            <div className="theme-color-chip" style={{ background: t.preview }} />
                            <div className="theme-text-meta">
                              <strong>{t.name}</strong>
                              <small>{t.desc}</small>
                            </div>
                            {current.theme === t.id && <span className="theme-check-dot" />}
                          </button>
                        ))}
                      </div>
                    </SettingCard>
                  )}

                  {matchesSearch('accent color luminescence highlight cyan violet emerald amber') && (
                    <SettingCard title="ACCENT LUMINESCENCE">
                      <SettingRow
                        title="Accent Luminescence Color"
                        desc="Primary color applied across active wires, selected tabs, and matrix highlights."
                        control={
                          <div className="accent-color-row-clean">
                            {accentColors.map((c) => (
                              <button
                                key={c.color}
                                type="button"
                                className={`accent-swatch-clean ${current.accentColor === c.color ? 'active' : ''}`}
                                style={{ backgroundColor: c.color }}
                                title={c.label}
                                onClick={() => update('accentColor', c.color)}
                              />
                            ))}
                          </div>
                        }
                      />
                    </SettingCard>
                  )}

                  {matchesSearch('ui density compact balanced comfortable wire style shaders glass') && (
                    <SettingCard title="DISPLAY & SHADERS">
                      <SettingRow disabled reason="Unavailable in this runtime"
                        title="Workbench UI Density"
                        desc="Adjust padding and height scale across explorer rows, topbar, and tabs."
                        control={
                          <div className="clean-segmented-control">
                            {(['compact', 'balanced', 'comfortable'] as const).map((density) => (
                              <button
                                key={density}
                                type="button"
                                className={`seg-btn ${current.uiDensity === density ? 'active' : ''}`}
                                onClick={() => update('uiDensity', density)}
                              >
                                {density.toUpperCase()}
                              </button>
                            ))}
                          </div>
                        }
                      />

                      <SettingRow disabled reason="Unavailable in this runtime"
                        title="Circuit Wire Shader Style"
                        desc="Rendering aesthetic for quantum circuit wires, registers, and gate conduits."
                        control={
                          <div className="clean-segmented-control">
                            {(['neon', 'blueprint', 'minimal'] as const).map((ws) => (
                              <button
                                key={ws}
                                type="button"
                                className={`seg-btn ${current.wireStyle === ws ? 'active' : ''}`}
                                onClick={() => update('wireStyle', ws)}
                              >
                                {ws.toUpperCase()}
                              </button>
                            ))}
                          </div>
                        }
                      />

                      <SettingRow
                        title="Glassmorphism & Depth Shaders"
                        desc="Apply layered backdrop blur shaders across sidebars and floating panels."
                        control={
                          <CustomToggle
                            checked={current.glassmorphism}
                            onChange={(val) => update('glassmorphism', val)}
                          />
                        }
                      />

                      <SettingRow disabled reason="Unavailable in this runtime"
                        title="Live State Pulse Propagation"
                        desc="Real-time wave animations traversing quantum gates and wires during execution."
                        control={
                          <CustomToggle
                            checked={current.livePulseAnimation ?? true}
                            onChange={(val) => update('livePulseAnimation', val)}
                          />
                        }
                      />

                      <SettingRow disabled reason="Unavailable in this runtime"
                        title="Background Auto-Save"
                        desc="Silently persist active circuit buffer changes to storage in background."
                        control={
                          <CustomToggle
                            checked={current.autoSave ?? true}
                            onChange={(val) => update('autoSave', val)}
                          />
                        }
                      />
                    </SettingCard>
                  )}
                </div>
              )}

              {/* CATEGORY 2: MONACO EDITOR */}
              {category === 'editor' && (
                <div className="settings-group-stack">
                  <SettingCard title="TYPOGRAPHY & DISPLAY">
                    <SettingRow
                      title={`Editor Font Size (${current.fontSize}px)`}
                      desc="Base font scale used in the Monaco circuit editor."
                      control={
                        <div className="clean-slider-group">
                          <input
                            type="range"
                            aria-label="Editor font size"
                            min="11"
                            max="18"
                            className="clean-range-slider"
                            value={current.fontSize}
                            onChange={(e) => update('fontSize', Number(e.target.value))}
                          />
                          <span className="clean-val-pill">{current.fontSize}px</span>
                        </div>
                      }
                    />

                    <SettingRow disabled reason="Unavailable in this runtime"
                      title={`Terminal Font Size (${current.terminalFontSize ?? 13}px)`}
                      desc="Font scale utilized across integrated terminal sessions and command consoles."
                      control={
                        <div className="clean-slider-group">
                          <input
                            type="range"
                            min="10"
                            max="18"
                            className="clean-range-slider"
                            value={current.terminalFontSize ?? 13}
                            onChange={(e) => update('terminalFontSize', Number(e.target.value))}
                          />
                          <span className="clean-val-pill">{current.terminalFontSize ?? 13}px</span>
                        </div>
                      }
                    />

                    <SettingRow disabled reason="Unavailable in this runtime"
                      title="Terminal Cursor Blinking"
                      desc="Smooth blinking caret animation inside the active shell console."
                      control={
                        <CustomToggle
                          checked={current.terminalBlink ?? true}
                          onChange={(val) => update('terminalBlink', val)}
                        />
                      }
                    />

                    <SettingRow
                      title="Line Numbers"
                      desc="Display mode for the code editor line numbering gutter."
                      control={
                        <div className="clean-segmented-control">
                          {(['on', 'relative', 'off'] as const).map((mode) => (
                            <button
                              key={mode}
                              type="button"
                              className={`seg-btn ${current.lineNumbers === mode ? 'active' : ''}`}
                              onClick={() => update('lineNumbers', mode)}
                            >
                              {mode.toUpperCase()}
                            </button>
                          ))}
                        </div>
                      }
                    />

                    <SettingRow
                      title="Cursor Style"
                      desc="Insertion caret rendering style in the editor."
                      control={
                        <div className="clean-segmented-control">
                          {(['line', 'block', 'underline'] as const).map((style) => (
                            <button
                              key={style}
                              type="button"
                              className={`seg-btn ${current.cursorStyle === style ? 'active' : ''}`}
                              onClick={() => update('cursorStyle', style)}
                            >
                              {style.toUpperCase()}
                            </button>
                          ))}
                        </div>
                      }
                    />
                  </SettingCard>

                  <SettingCard title="EDITOR BEHAVIOR & FORMATTING">
                    <SettingRow
                      title="Tab Indentation Width"
                      desc="Number of spaces inserted per indentation level."
                      control={
                        <div className="clean-segmented-control">
                          {[2, 4].map((ts) => (
                            <button
                              key={ts}
                              type="button"
                              className={`seg-btn ${current.tabSize === ts ? 'active' : ''}`}
                              onClick={() => update('tabSize', ts)}
                            >
                              {ts} SPACES
                            </button>
                          ))}
                        </div>
                      }
                    />

                    <SettingRow
                      title="Word Wrap"
                      desc="Soft-wrap long lines without requiring horizontal scrolling."
                      control={
                        <CustomToggle
                          checked={current.wordWrap}
                          onChange={(val) => update('wordWrap', val)}
                        />
                      }
                    />

                    <SettingRow
                      title="Code Minimap"
                      desc="Display overview minimap navigation column on the right edge."
                      control={
                        <CustomToggle
                          checked={current.minimap}
                          onChange={(val) => update('minimap', val)}
                        />
                      }
                    />

                    <SettingRow
                      title="Bracket Pair Colorization"
                      desc="Colorize matching pairs of brackets, parentheses, and braces."
                      control={
                        <CustomToggle
                          checked={current.bracketPairColorization}
                          onChange={(val) => update('bracketPairColorization', val)}
                        />
                      }
                    />

                    <SettingRow
                      title="Auto-Close Brackets & Quotes"
                      desc="Automatically insert matching closing delimiter when typing (, [, or quotes."
                      control={
                        <CustomToggle
                          checked={current.autoCloseBrackets ?? true}
                          onChange={(val) => update('autoCloseBrackets', val)}
                        />
                      }
                    />

                    <SettingRow
                      title="Format Code on Paste"
                      desc="Ask the editor's language formatter to format pasted code when available."
                      control={
                        <CustomToggle
                          checked={current.formatOnSave ?? true}
                          onChange={(val) => update('formatOnSave', val)}
                        />
                      }
                    />
                  </SettingCard>
                </div>
              )}

              {/* CATEGORY 3: QUANTUM KERNEL */}
              {category === 'kernel' && (
                <div className="settings-group-stack">
                  <SettingCard title="SIMULATION EXECUTION ENGINE">
                    <SettingRow
                      title="Simulation Engine Backend"
                      desc="Mathematical execution algorithm executed locally inside Qiskit Aer."
                      control={
                        <div className="clean-segmented-control">
                          {[
                            { id: 'statevector', label: 'Statevector' },
                            { id: 'matrix_product_state', label: 'MPS' },
                            { id: 'stabilizer', label: 'Stabilizer' },
                          ].map((b) => (
                            <button
                              key={b.id}
                              type="button"
                              className={`seg-btn ${current.simulationBackend === b.id ? 'active' : ''}`}
                              onClick={() => update('simulationBackend', b.id as any)}
                            >
                              {b.label}
                            </button>
                          ))}
                        </div>
                      }
                    />

                    <SettingRow
                      title="Default Measurement Shots"
                      desc="Number of stochastic projective measurement samples per run."
                      control={
                        <div className="clean-segmented-control">
                          {[512, 1024, 2048, 4096, 8192].map((s) => (
                            <button
                              key={s}
                              type="button"
                              className={`seg-btn ${current.defaultShots === s ? 'active' : ''}`}
                              onClick={() => update('defaultShots', s)}
                            >
                              {s}
                            </button>
                          ))}
                        </div>
                      }
                    />

                    <SettingRow
                      title="Deterministic RNG Seed"
                      desc="Fixed random number generator seed ensuring reproducible measurements."
                      control={
                        <input
                          type="number"
                          aria-label="Deterministic RNG seed"
                          min="0"
                          max="2147483647"
                          required
                          className="clean-number-input"
                          value={current.defaultSeed}
                          onChange={(e) => update('defaultSeed', Number(e.target.value))}
                        />
                      }
                    />

                    <SettingRow disabled reason="Server controlled"
                      title="Classical Bit Ordering (Endianness)"
                      desc="Results use little-endian classical indices. Big-endian conversion is unavailable."
                      control={
                        <div className="clean-segmented-control">
                          <button
                            type="button"
                            className="seg-btn active"
                            onClick={() => update('endianness', 'little')}
                          >
                            LITTLE-ENDIAN
                          </button>
                          <button
                            type="button"
                            className="seg-btn"
                            onClick={() => update('endianness', 'big')}
                          >
                            BIG-ENDIAN
                          </button>
                        </div>
                      }
                    />
                  </SettingCard>

                  <SettingCard title="SAFETY & PRECISION THRESHOLDS">
                    <SettingRow disabled reason="Server controlled"
                      title="Max Qubit Safety Guard (10 Qubits)"
                      desc="The backend enforces this limit. Browser preferences cannot change it."
                      control={
                        <div className="clean-slider-group">
                          <input
                            type="range"
                            min="4"
                            max="10"
                            className="clean-range-slider"
                            value={10}
                            onChange={(e) => update('maxQubitsGuard', Number(e.target.value))}
                          />
                          <span className="clean-val-pill">10 Qubits</span>
                        </div>
                      }
                    />

                    <SettingRow disabled reason="Unavailable in this runtime"
                      title="Zero Amplitude Pruning Threshold"
                      desc="Amplitudes |c_i|² below this cutoff are rendered as exact zeros in HUD."
                      control={
                        <select
                          className="clean-select"
                          value={current.zeroThreshold ?? '1e-9'}
                          onChange={(e) => update('zeroThreshold', e.target.value)}
                        >
                          <option value="1e-12">1e-12 (Exact numerical)</option>
                          <option value="1e-9">1e-9 (Standard default)</option>
                          <option value="1e-6">1e-6 (Noise filtered)</option>
                        </select>
                      }
                    />

                    <SettingRow disabled reason="Server controlled"
                      title="Numerical Precision Mode"
                      desc="Floating point numerical precision for complex statevector amplitude propagation."
                      control={
                        <div className="clean-segmented-control">
                          <button
                            type="button"
                            className="seg-btn active"
                            onClick={() => update('precisionMode', 'fp64')}
                          >
                            FP64 (DOUBLE)
                          </button>
                          <button
                            type="button"
                            className="seg-btn"
                            onClick={() => update('precisionMode', 'fp32')}
                          >
                            FP32 (SINGLE)
                          </button>
                        </div>
                      }
                    />
                  </SettingCard>
                </div>
              )}

              {/* CATEGORY 4: PHYSICAL QPUS & NOISE */}
              {category === 'hardware' && (
                <div className="settings-group-stack">
                  <SettingCard title="HARDWARE TOPOLOGY & CLOUD PROVIDERS">
                    <SettingRow disabled reason="Unavailable in this runtime"
                      title="Default Cloud Provider Execution"
                      desc="Primary target ecosystem for cloud execution, transpilation, and hardware routing."
                      control={
                        <div className="clean-segmented-control">
                          {[
                            { id: 'ibm', label: 'IBM Quantum' },
                            { id: 'azure', label: 'Azure Quantum' },
                            { id: 'rigetti', label: 'Rigetti QCS' },
                          ].map((p) => (
                            <button
                              key={p.id}
                              type="button"
                              className={`seg-btn ${(current.defaultProvider ?? 'ibm') === p.id ? 'active' : ''}`}
                              onClick={() => update('defaultProvider', p.id as any)}
                            >
                              {p.label}
                            </button>
                          ))}
                        </div>
                      }
                    />

                    <SettingRow disabled reason="Unavailable in this runtime"
                      title="Fault-Tolerant Error Budget"
                      desc="Allowable logical error probability budget for QDK resource estimation."
                      control={
                        <select
                          className="clean-select"
                          value={current.resourceErrorBudget ?? '0.001'}
                          onChange={(e) => update('resourceErrorBudget', e.target.value as any)}
                        >
                          <option value="0.01">1e-2 (1% - NISQ / Early Fault-Tolerance)</option>
                          <option value="0.001">1e-3 (0.1% - Standard High-Fidelity Target)</option>
                          <option value="0.0001">1e-4 (0.01% - Ultra-Strict Precision)</option>
                        </select>
                      }
                    />

                    <SettingRow disabled reason="Unavailable in this runtime"
                      title="Target Hardware Coupling Architecture"
                      desc="Physical chip topology used for routing and 2-qubit gate coupling checks."
                      control={
                        <select
                          className="clean-select"
                          value={current.hardwareTopology ?? 'ideal'}
                          onChange={(e) => update('hardwareTopology', e.target.value as any)}
                        >
                          <option value="ideal">Ideal All-to-All Full Connectivity</option>
                          <option value="ibm_heron">IBM Heron 156Q (Heavy-Hexagon)</option>
                          <option value="ibm_eagle">IBM Eagle 127Q (Heavy-Hexagon)</option>
                          <option value="rigetti_ankaa">Rigetti Ankaa-9 (Square Planar)</option>
                          <option value="quantinuum_h1">Quantinuum H1 (Trapped-Ion)</option>
                        </select>
                      }
                    />
                  </SettingCard>

                  <SettingCard title="PHYSICAL NOISE CHANNELS">
                    <SettingRow
                      title="Simulate Hardware Noise"
                      desc="Inject depolarizing error channels and readout confusion matrices via Aer."
                      control={
                        <CustomToggle
                          checked={current.noiseSimulation}
                          onChange={(val) => update('noiseSimulation', val)}
                        />
                      }
                    />

                    {current.noiseSimulation && (
                      <>
                        <SettingRow
                          title={`Depolarizing Gate Error (${(current.depolarizingRate * 100).toFixed(1)}%)`}
                          desc="Single-qubit gate depolarizing probability (2-qubit gates undergo 2p error)."
                          control={
                            <div className="clean-slider-group">
                              <input
                                type="range"
                                aria-label="Depolarizing gate error"
                                min="0.001"
                                max="0.10"
                                step="0.005"
                                className="clean-range-slider"
                                value={current.depolarizingRate}
                                onChange={(e) => update('depolarizingRate', Number(e.target.value))}
                              />
                              <span className="clean-val-pill">{current.depolarizingRate}</span>
                            </div>
                          }
                        />

                        <SettingRow
                          title={`Readout Measurement Error (${(current.readoutErrorRate * 100).toFixed(1)}%)`}
                          desc="Detector bit-flip probability during classical register measurement."
                          control={
                            <div className="clean-slider-group">
                              <input
                                type="range"
                                aria-label="Readout measurement error"
                                min="0.005"
                                max="0.15"
                                step="0.005"
                                className="clean-range-slider"
                                value={current.readoutErrorRate}
                                onChange={(e) => update('readoutErrorRate', Number(e.target.value))}
                              />
                              <span className="clean-val-pill">{current.readoutErrorRate}</span>
                            </div>
                          }
                        />

                        <SettingRow disabled reason="Unavailable in this runtime"
                          title="Thermal Relaxation & Dephasing (T1 / T2)"
                          desc="Simulate energy decay (T1) and dephasing (T2) times on physical qubits."
                          control={
                            <CustomToggle
                              checked={current.thermalRelaxation ?? false}
                              onChange={(val) => update('thermalRelaxation', val)}
                            />
                          }
                        />
                      </>
                    )}
                  </SettingCard>

                  <SettingCard title="ERROR MITIGATION & SUPPRESSION">
                    <SettingRow disabled reason="Unavailable in this runtime"
                      title="Readout Error Mitigation Strategy"
                      desc="Post-processing calibration filter applied to measurement histograms."
                      control={
                        <select
                          className="clean-select"
                          value={current.errorMitigation ?? 'none'}
                          onChange={(e) => update('errorMitigation', e.target.value as any)}
                        >
                          <option value="none">None (Raw Measurement Counts)</option>
                          <option value="inversion">Full Calibration Matrix Inversion</option>
                          <option value="m3_twirled">M3 Twirled Matrix-Free Mitigator</option>
                        </select>
                      }
                    />

                    <SettingRow disabled reason="Unavailable in this runtime"
                      title="Dynamical Decoupling Pulse Sequence"
                      desc="Insert refocusing pi-pulses into idle qubit wires to suppress dephasing noise."
                      control={
                        <select
                          className="clean-select"
                          value={current.dynamicalDecoupling ?? 'none'}
                          onChange={(e) => update('dynamicalDecoupling', e.target.value as any)}
                        >
                          <option value="none">Disabled (No Idle Pulses)</option>
                          <option value="cpmg">CPMG (Carr-Purcell-Meiboom-Gill)</option>
                          <option value="xy4">XY4 (Robust 4-pulse sequence)</option>
                          <option value="udd">UDD (Uhrig Dynamical Decoupling)</option>
                        </select>
                      }
                    />
                  </SettingCard>
                </div>
              )}

              {/* CATEGORY 5: TRANSPILER & FORGE */}
              {category === 'transpiler' && (
                <div className="settings-group-stack">
                  <SettingCard title="PASS MANAGER OPTIMIZATION">
                    <SettingRow
                      title="Transpiler Optimization Level"
                      desc="Optimization depth executed by Qiskit PassManager."
                      control={
                        <select
                          className="clean-select"
                          value={current.defaultOptLevel}
                          aria-label="Transpiler optimization level"
                          onChange={(e) => update('defaultOptLevel', Number(e.target.value))}
                        >
                          <option value={0}>Level 0 — Direct Native Mapping</option>
                          <option value={1}>Level 1 — Light Gate Cancellations</option>
                          <option value={2}>Level 2 — Commutative Synthesis (Default)</option>
                          <option value={3}>Level 3 — Aggressive Depth Minimization</option>
                        </select>
                      }
                    />

                    <SettingRow disabled reason="Unavailable in this runtime"
                      title="Qubit Layout & Routing Heuristic"
                      desc="Algorithm used for placing SWAP operations across hardware couplings."
                      control={
                        <select
                          className="clean-select"
                          value={current.routingMethod ?? 'sabre'}
                          onChange={(e) => update('routingMethod', e.target.value as any)}
                        >
                          <option value="sabre">SABRE (Swap-based heuristic, recommended)</option>
                          <option value="stochastic">Stochastic SWAP placer</option>
                          <option value="basic">Basic nearest-neighbor routing</option>
                          <option value="lookahead">Lookahead forward heuristic</option>
                        </select>
                      }
                    />

                    <SettingRow disabled reason="Unavailable in this runtime"
                      title="Target Hardware Basis Gates"
                      desc="Native physical gate set decomposed into during transpilation."
                      control={
                        <div className="clean-segmented-control">
                          {[
                            { id: 'generic', label: 'Generic' },
                            { id: 'ibm', label: 'IBM' },
                            { id: 'rigetti', label: 'Rigetti' },
                            { id: 'ionq', label: 'IonQ' },
                          ].map((b) => (
                            <button
                              key={b.id}
                              type="button"
                              className={`seg-btn ${current.targetBasis === b.id ? 'active' : ''}`}
                              onClick={() => update('targetBasis', b.id as any)}
                            >
                              {b.label}
                            </button>
                          ))}
                        </div>
                      }
                    />
                  </SettingCard>

                  <SettingCard title="UNITARY EQUIVALENCE VALIDATION">
                    <SettingRow disabled reason="Server controlled"
                      title="Commutation Analysis & Gate Cancellation"
                      desc="Commute compatible rotation gates past control qubits to maximize cancel pairs."
                      control={
                        <CustomToggle
                          checked={current.commutationAnalysis ?? true}
                          onChange={(val) => update('commutationAnalysis', val)}
                        />
                      }
                    />

                    <SettingRow disabled reason="Server controlled"
                      title="Strict Unitary Verification (U† U = I)"
                      desc="The backend checks supported candidates. Inspect the validation evidence for each run."
                      control={
                        <CustomToggle
                          checked={true}
                          onChange={(val) => update('strictUnitaryCheck', val)}
                        />
                      }
                    />

                    <SettingRow disabled reason="Server controlled"
                      title="Equivalence Numerical Tolerance"
                      desc="Maximum floating point deviation threshold allowed in operator verification."
                      control={
                        <select
                          className="clean-select"
                          value="1e-9"
                          onChange={(e) => update('equivalenceTolerance', e.target.value)}
                        >
                          <option value="1e-9">1e-9 (Strict numerical tolerance)</option>
                          <option value="1e-7">1e-7 (Standard tolerance)</option>
                          <option value="1e-5">1e-5 (Permissive tolerance)</option>
                        </select>
                      }
                    />
                  </SettingCard>
                </div>
              )}

              {/* CATEGORY 6: AI COPILOT & CLOUD */}
              {category === 'copilot' && (
                <div className="settings-group-stack">
                  <SettingCard title="GEMINI COPILOT ENGINE">
                    <SettingRow disabled reason="Server controlled"
                      title="Server-Managed Provider"
                      desc="Credentials and model selection are configured on the backend. QORE never stores AI credentials in browser settings."
                      control={
                        <span className="clean-val-pill">SERVER ONLY</span>
                      }
                    />

                    <SettingRow disabled reason="Server controlled"
                      title={`Copilot Temperature (${current.copilotTemperature ?? 0.2})`}
                      desc="0.0 for mathematically deterministic code; 0.8 for creative quantum algorithms."
                      control={
                        <div className="clean-slider-group">
                          <input
                            type="range"
                            min="0.0"
                            max="1.0"
                            step="0.05"
                            className="clean-range-slider"
                            value={current.copilotTemperature ?? 0.2}
                            onChange={(e) => update('copilotTemperature', Number(e.target.value))}
                          />
                          <span className="clean-val-pill">{current.copilotTemperature ?? 0.2}</span>
                        </div>
                      }
                    />
                  </SettingCard>

                  <SettingCard title="REASONING & SANDBOX SECURITY">
                    <SettingRow disabled reason="Unavailable in this runtime"
                      title="Auto-Explain Generated Circuits in Chat"
                      desc="Provide step-by-step gate breakdown and unitary metrics with code proposals."
                      control={
                        <CustomToggle
                          checked={current.autoExplainCircuit ?? true}
                          onChange={(val) => update('autoExplainCircuit', val)}
                        />
                      }
                    />

                    <SettingRow disabled reason="Unavailable in this runtime"
                      title="Stream Token Generation Animation"
                      desc="Render words progressively as they are generated by the Gemini engine."
                      control={
                        <CustomToggle
                          checked={current.streamAiTokens ?? true}
                          onChange={(val) => update('streamAiTokens', val)}
                        />
                      }
                    />

                    <SettingRow
                      title="Bounded AST Sandbox Isolation"
                      desc="User circuits parse through AST verification and are never passed to eval/exec."
                      control={<span className="clean-badge-pill success">Enforced Sandbox</span>}
                    />
                  </SettingCard>
                </div>
              )}
            </div>
          </div>

          {/* 5. Modal Footer Actions */}
          <div className="settings-modal-footer">
            <div className="footer-left-btns">
              <button type="button" className="clean-button secondary small" onClick={resetDefaults}>
                Reset Defaults
              </button>
              <button type="button" className="clean-button secondary small" onClick={exportSettingsJSON}>
                <Icon name="copy" size={12} />
                <span>{copiedNotification ? 'Exported!' : 'Export JSON'}</span>
              </button>
            </div>

            <div className="footer-right-btns">
              <button type="button" className="clean-button secondary small" onClick={onClose}>
                Cancel
              </button>
              <button type="submit" className="clean-button primary small">
                Apply & Save Settings
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}
