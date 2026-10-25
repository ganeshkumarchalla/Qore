import React, { useEffect, useRef, useState } from 'react';
import { Icon } from './Icons';
import { api } from './types';

export interface AuthUser {
  id: string;
  name: string;
  email: string;
  role: string;
  tier: string;
  avatarInitials: string;
}

export interface AuthConfig {
  configured: boolean;
  required: boolean;
  google_enabled: boolean;
  email_enabled: boolean;
  message?: string;
}

export interface AuthSession {
  user: AuthUser | null;
  configured: boolean;
  required: boolean;
}

// Public profile state is always restored from the verified server session.
export function loadStoredUser(): AuthUser | null { return null; }
export function loadAuthSession(): Promise<AuthSession> { return api<AuthSession>('/auth/session'); }

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
  currentUser: AuthUser | null;
  onLoginSuccess: (user: AuthUser) => void;
  /** The modal revokes the session; this callback clears the parent workspace. */
  onLogout: () => void | Promise<void>;
}

function errorMessage(error: unknown): string {
  const message = error instanceof Error ? error.message : 'Sign-in could not be completed. Please try again.';
  return message.startsWith('Cannot connect to the QORE backend')
    ? 'Unable to reach the sign-in service. Please try again.'
    : message;
}

function GoogleMark() {
  return <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
    <path fill="#4285F4" d="M21.6 12.23c0-.71-.06-1.39-.18-2.05H12v3.88h5.38a4.6 4.6 0 0 1-2 3.02v2.51h3.24c1.9-1.75 2.98-4.33 2.98-7.36Z" />
    <path fill="#34A853" d="M12 22c2.7 0 4.96-.9 6.62-2.41l-3.24-2.51c-.9.6-2.04.96-3.38.96-2.6 0-4.8-1.76-5.59-4.12H3.06v2.59A10 10 0 0 0 12 22Z" />
    <path fill="#FBBC05" d="M6.41 13.92a6 6 0 0 1 0-3.84V7.49H3.06a10 10 0 0 0 0 9.02l3.35-2.59Z" />
    <path fill="#EA4335" d="M12 5.96c1.47 0 2.79.51 3.82 1.51l2.86-2.87A9.6 9.6 0 0 0 12 2a10 10 0 0 0-8.94 5.49l3.35 2.59A5.89 5.89 0 0 1 12 5.96Z" />
  </svg>;
}

export function AuthModal({ isOpen, onClose, currentUser, onLoginSuccess, onLogout }: AuthModalProps) {
  const [mode, setMode] = useState<'signin' | 'signup'>('signin');
  const [config, setConfig] = useState<AuthConfig | null>(null);
  const [checking, setChecking] = useState(false);
  const [pending, setPending] = useState<'signin' | 'signup' | 'google' | 'signout' | null>(null);
  const [showPassword, setShowPassword] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const dialogRef = useRef<HTMLDivElement>(null);
  const callbacks = useRef({ onClose, onLoginSuccess, onLogout });
  callbacks.current = { onClose, onLoginSuccess, onLogout };
  const busyRef = useRef(false);
  const busy = pending !== null;
  busyRef.current = busy;

  useEffect(() => {
    if (!isOpen) {
      setPassword('');
      setShowPassword(false);
      return;
    }
    let cancelled = false;
    setChecking(true);
    setConfig(null);
    setError('');
    setNotice('');
    void Promise.allSettled([api<AuthConfig>('/auth/config'), loadAuthSession()])
      .then(([configuration, session]) => {
        if (cancelled) return;
        if (configuration.status === 'fulfilled') setConfig(configuration.value);
        else setError(errorMessage(configuration.reason));
        if (session.status === 'fulfilled') {
          if (session.value.user && session.value.user.id !== currentUser?.id) callbacks.current.onLoginSuccess(session.value.user);
          else if (currentUser) void callbacks.current.onLogout();
        } else {
          setError(errorMessage(session.reason));
        }
      })
      .finally(() => { if (!cancelled) setChecking(false); });
    return () => { cancelled = true; };
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) return;
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const frame = requestAnimationFrame(() => dialogRef.current?.focus());
    const onKey = (event: KeyboardEvent) => {
      const dialog = dialogRef.current;
      if (!dialog) return;
      if (event.key === 'Escape' && !busyRef.current) {
        event.preventDefault();
        event.stopPropagation();
        callbacks.current.onClose();
      }
      if (event.key !== 'Tab') return;
      const elements = Array.from(dialog.querySelectorAll<HTMLElement>(
        'button:not([disabled]), input:not([disabled]), a[href], select:not([disabled]), [tabindex="0"]'
      )).filter(element => element.offsetParent !== null);
      if (!elements.length) {
        event.preventDefault();
        dialog.focus();
        return;
      }
      const first = elements[0], last = elements[elements.length - 1];
      if (event.shiftKey && (document.activeElement === first || document.activeElement === dialog)) {
        event.preventDefault(); last.focus();
      } else if (!event.shiftKey && (document.activeElement === last || !dialog.contains(document.activeElement))) {
        event.preventDefault(); first.focus();
      }
    };
    const onPageShow = () => { setPending(null); };
    document.addEventListener('keydown', onKey, true);
    window.addEventListener('pageshow', onPageShow);
    return () => {
      cancelAnimationFrame(frame);
      document.removeEventListener('keydown', onKey, true);
      window.removeEventListener('pageshow', onPageShow);
      if (previous?.isConnected) previous.focus();
    };
  }, [isOpen]);

  if (!isOpen) return null;

  const switchMode = (next: 'signin' | 'signup') => {
    setMode(next); setPassword(''); setError(''); setNotice(''); setShowPassword(false);
  };

  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (busy || !config?.configured || !config.email_enabled) return;
    setError(''); setNotice(''); setPending(mode);
    try {
      const payload = mode === 'signup'
        ? { email: email.trim(), password, name: fullName.trim() }
        : { email: email.trim(), password };
      const result = await api<{ user: AuthUser | null; message?: string }>(
        mode === 'signup' ? '/auth/signup' : '/auth/signin', payload
      );
      setPassword('');
      if (result.user) {
        onLoginSuccess(result.user);
        onClose();
      } else {
        setNotice(result.message ?? 'Check your email to confirm your account, then sign in.');
        setMode('signin');
      }
    } catch (reason) { setError(errorMessage(reason)); }
    finally { setPending(null); }
  };

  const signOut = async () => {
    if (busy) return;
    setPending('signout'); setError(''); setNotice('');
    try {
      await api<{ user: null }>('/auth/signout', {});
      await onLogout();
      setNotice('You have signed out.');
    } catch (reason) { setError(errorMessage(reason)); }
    finally { setPending(null); }
  };

  const checkAvailability = async () => {
    setChecking(true);
    setError('');
    try { setConfig(await api<AuthConfig>('/auth/config')); }
    catch (reason) { setError(errorMessage(reason)); }
    finally { setChecking(false); }
  };
  const googleAvailable = Boolean(config?.configured && config.google_enabled);
  const emailAvailable = Boolean(config?.configured && config.email_enabled);
  const providerMessage = checking ? 'Checking sign-in availability…'
    : !config?.configured ? 'Secure sign-in is being configured for this workspace.'
    : config.message ?? (!config.google_enabled ? 'Google sign-in is not enabled for this workspace yet.' : 'Your sign-in session is protected by the QORE backend.');

  return (
    <div className="modal-overlay glass-backdrop auth-modal-overlay"
      onMouseDown={event => { if (event.target === event.currentTarget && !busy) onClose(); }}>
      <div className="auth-card-window" ref={dialogRef} tabIndex={-1}
        role="dialog" aria-modal="true" aria-labelledby="qore-auth-title" aria-describedby="qore-auth-description"
        aria-busy={busy || checking} style={{ maxHeight: 'min(90dvh, 760px)', outline: 'none' }}>
        <div className="auth-header">
          <div className="auth-header-brand">
            <Icon name="account" size={30} />
            <div>
              <h3 id="qore-auth-title">Your QORE Account</h3>
              <p id="qore-auth-description">Personal workspace for your quantum circuits & simulations</p>
            </div>
          </div>
          <button type="button" className="icon-close" onClick={onClose} disabled={busy} aria-label="Close account dialog">
            <Icon name="close" size={14} />
          </button>
        </div>

        <div style={{ overflowY: 'auto', minHeight: 0 }}>
          {error && <div className="auth-error-banner" role="alert"><Icon name="info" size={14} /><span>{error}</span></div>}
          {notice && <p className="help" role="status" style={{ padding: '12px 20px', margin: 0, color: '#57D9FF' }}>{notice}</p>}

          {currentUser ? (
            <div className="auth-profile-dashboard">
              <div className="auth-avatar-hero">
                <div className="avatar-circle-large" aria-hidden="true">{currentUser.avatarInitials}</div>
                <h4>{currentUser.name}</h4>
                <span className="auth-user-email">{currentUser.email}</span>
                <span className="auth-tier-badge">{currentUser.tier}</span>
              </div>
              <p className="help">You are signed in. Your cloud projects and experiments belong to your account.</p>
              <div className="auth-profile-actions">
                <button type="button" className="clean-button secondary full-width" onClick={() => void signOut()} disabled={busy}>
                  {pending === 'signout' ? 'Signing out…' : 'Sign out'}
                </button>
                <button type="button" className="clean-button primary full-width" onClick={onClose} disabled={busy}>Return to workspace</button>
              </div>
            </div>
          ) : (
            <>
              <div className="auth-tabs-bar" role="group" aria-label="Account action">
                <button type="button" className={`auth-tab-btn ${mode === 'signin' ? 'active' : ''}`} onClick={() => switchMode('signin')} disabled={busy} aria-pressed={mode === 'signin'}>Sign in</button>
                <button type="button" className={`auth-tab-btn ${mode === 'signup' ? 'active' : ''}`} onClick={() => switchMode('signup')} disabled={busy} aria-pressed={mode === 'signup'}>Create account</button>
              </div>

              <div className="auth-form-body">
                <button type="button" className="clean-button secondary full-width guest-btn"
                  disabled={checking || busy || !googleAvailable} aria-describedby="qore-auth-provider-status"
                  onClick={() => { if (googleAvailable) { setPending('google'); window.location.assign('/api/auth/google'); } }}>
                  <GoogleMark /><span>{pending === 'google' ? 'Opening Google…' : 'Continue with Google'}</span>
                </button>
                <p id="qore-auth-provider-status" className="help" role="status" style={{ margin: 0 }}>{providerMessage}</p>
                {!checking && !googleAvailable && <button type="button" className="clean-button secondary small" disabled={busy} onClick={() => void checkAvailability()}>Check sign-in availability</button>}
              </div>
              {emailAvailable && <div className="auth-divider"><span>OR USE EMAIL</span></div>}
              <form onSubmit={event => void submit(event)} className="auth-form-body">
                {mode === 'signup' && (
                  <div className="auth-form-field">
                    <label htmlFor="qore-auth-name">Your Name</label>
                    <input
                      id="qore-auth-name"
                      className="auth-input"
                      type="text"
                      autoComplete="name"
                      maxLength={80}
                      required
                      disabled={busy}
                      placeholder="e.g. Marie Curie"
                      value={fullName}
                      onChange={event => setFullName(event.target.value)}
                    />
                  </div>
                )}

                <div className="auth-form-field">
                  <label htmlFor="qore-auth-email">Email Address</label>
                  <input
                    id="qore-auth-email"
                    className="auth-input"
                    type="email"
                    autoComplete="email"
                    maxLength={254}
                    required
                    disabled={busy}
                    placeholder="name@example.com"
                    value={email}
                    onChange={event => setEmail(event.target.value)}
                  />
                </div>

                <div className="auth-form-field">
                  <label htmlFor="qore-auth-password">Password</label>
                  <div className="auth-password-wrap">
                    <input
                      id="qore-auth-password"
                      className="auth-input"
                      type={showPassword ? 'text' : 'password'}
                      autoComplete={mode === 'signup' ? 'new-password' : 'current-password'}
                      required
                      disabled={busy}
                      minLength={mode === 'signup' ? 12 : 1}
                      maxLength={mode === 'signup' ? 128 : 512}
                      placeholder={mode === 'signup' ? 'At least 12 characters' : 'Enter password'}
                      aria-describedby={mode === 'signup' ? 'qore-auth-password-help' : undefined}
                      value={password}
                      onChange={event => setPassword(event.target.value)}
                    />
                    <button
                      type="button"
                      className="auth-pwd-toggle"
                      disabled={busy}
                      onClick={() => setShowPassword(value => !value)}
                      aria-label={showPassword ? 'Hide password' : 'Show password'}
                      aria-pressed={showPassword}
                    >
                      <Icon name={showPassword ? 'eyeOff' : 'eye'} size={14} />
                    </button>
                  </div>
                  {mode === 'signup' && (
                    <p id="qore-auth-password-help" className="help" style={{ margin: 0 }}>
                      Use at least 12 characters.
                    </p>
                  )}
                </div>

                <button type="submit" className="clean-button primary full-width auth-submit-btn" disabled={busy || checking || !emailAvailable}>
                  {pending === 'signin' ? 'Signing in…' : pending === 'signup' ? 'Creating your account…' : mode === 'signup' ? 'Create Account' : 'Sign In to QORE'}
                </button>
              </form>

              <div style={{ textAlign: 'center', padding: '0 20px 18px' }}>
                {mode === 'signin' ? (
                  <p className="help" style={{ margin: 0 }}>
                    Don&apos;t have an account?{' '}
                    <button type="button" style={{ background: 'none', border: 'none', color: '#57D9FF', cursor: 'pointer', padding: 0, textDecoration: 'underline' }} onClick={() => switchMode('signup')}>
                      Create one
                    </button>
                  </p>
                ) : (
                  <p className="help" style={{ margin: 0 }}>
                    Already have an account?{' '}
                    <button type="button" style={{ background: 'none', border: 'none', color: '#57D9FF', cursor: 'pointer', padding: 0, textDecoration: 'underline' }} onClick={() => switchMode('signin')}>
                      Sign in
                    </button>
                  </p>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
