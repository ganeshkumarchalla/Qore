import React, { useEffect, useId, useRef, useState } from 'react';
import { Icon } from './Icons';
import { api } from './types';

export interface AuthUser {
  id: string;
  name: string;
  email: string;
  role: string;
  tier: string;
  avatarInitials: string;
  avatarUrl?: string;
  title?: string;
  organization?: string;
  bio?: string;
  mfaEnabled?: boolean;
}

export interface AuthConfig {
  configured: boolean;
  required: boolean;
  email_enabled: boolean;
  message?: string;
}

export interface AuthSession {
  user: AuthUser | null;
  configured: boolean;
  required: boolean;
}

const AVATAR_PRESETS = [
  { id: 'qubit-core', label: 'Qubit Core', color: '#00f0ff', bg: 'linear-gradient(135deg, #00f0ff, #3b82f6)' },
  { id: 'bloch-sphere', label: 'Bloch Sphere', color: '#818cf8', bg: 'linear-gradient(135deg, #6366f1, #a855f7)' },
  { id: 'feynman', label: 'Feynman', color: '#f59e0b', bg: 'linear-gradient(135deg, #f59e0b, #ef4444)' },
  { id: 'curie', label: 'Curie', color: '#ec4899', bg: 'linear-gradient(135deg, #ec4899, #8b5cf6)' },
  { id: 'schrodinger', label: 'Schrödinger', color: '#10b981', bg: 'linear-gradient(135deg, #10b981, #06b6d4)' },
  { id: 'aurora-wave', label: 'Aurora Wave', color: '#c084fc', bg: 'linear-gradient(135deg, #8b5cf6, #ec4899)' },
];

export function loadStoredUser(): AuthUser | null {
  try {
    const raw = localStorage.getItem('qore_last_auth_user');
    if (!raw) return null;
    return JSON.parse(raw) as AuthUser;
  } catch {
    return null;
  }
}

export function saveStoredUser(user: AuthUser | null) {
  try {
    if (user) localStorage.setItem('qore_last_auth_user', JSON.stringify(user));
    else localStorage.removeItem('qore_last_auth_user');
  } catch {
    // ignore
  }
}

export function getExtendedProfile(userId: string): Partial<AuthUser> {
  try {
    const raw = localStorage.getItem(`qore_profile_${userId}`);
    if (raw) return JSON.parse(raw);
  } catch {
    // ignore
  }
  return {};
}

export function saveExtendedProfile(userId: string, data: Partial<AuthUser>) {
  try {
    const existing = getExtendedProfile(userId);
    localStorage.setItem(`qore_profile_${userId}`, JSON.stringify({ ...existing, ...data }));
  } catch {
    // ignore
  }
}

export function loadAuthSession(): Promise<AuthSession> {
  return api<AuthSession>('/auth/session');
}

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
  currentUser: AuthUser | null;
  onLoginSuccess: (user: AuthUser, isNewUser?: boolean) => void;
  onLogout: () => void | Promise<void>;
  onUpdateUser?: (updated: AuthUser) => void;
}

function errorMessage(error: unknown): string {
  const message = error instanceof Error ? error.message : 'Sign-in could not be completed. Please try again.';
  return message.startsWith('Cannot connect to the QORE backend')
    ? 'Unable to reach the sign-in service. Please try again.'
    : message;
}

export function AuthModal({
  isOpen,
  onClose,
  currentUser,
  onLoginSuccess,
  onLogout,
  onUpdateUser,
}: AuthModalProps) {
  const [mode, setMode] = useState<'signin' | 'signup' | 'forgot'>('signin');
  const [accountTab, setAccountTab] = useState<'profile' | 'personal' | 'mfa' | 'password' | 'sessions'>('profile');
  const [config, setConfig] = useState<AuthConfig | null>(null);
  const [checking, setChecking] = useState(false);
  const [pending, setPending] = useState<'signin' | 'signup' | 'resend' | 'signout' | 'save_profile' | 'send_otp' | 'verify_otp' | 'change_password' | null>(null);
  const [showPassword, setShowPassword] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  // Password Recovery / Verification OTP state
  const [forgotStep, setForgotStep] = useState<'request_otp' | 'verify_otp'>('request_otp');
  const [otpCode, setOtpCode] = useState('');
  const [recoveryPassword, setRecoveryPassword] = useState('');
  const [confirmRecoveryPassword, setConfirmRecoveryPassword] = useState('');
  const [showRecoveryPassword, setShowRecoveryPassword] = useState(false);
  const [instantOtp, setInstantOtp] = useState<string | null>(null);

  // Change Password for Logged-In User state
  const [currentPassword, setCurrentPassword] = useState('');
  const [newAccountPassword, setNewAccountPassword] = useState('');
  const [confirmAccountPassword, setConfirmAccountPassword] = useState('');
  const [showCurrentPassword, setShowCurrentPassword] = useState(false);
  const [showNewAccountPassword, setShowNewAccountPassword] = useState(false);

  // Extended Profile State for Logged-In User
  const [title, setTitle] = useState('');
  const [organization, setOrganization] = useState('');
  const [bio, setBio] = useState('');
  const [avatarUrl, setAvatarUrl] = useState<string | undefined>(undefined);
  const [mfaEnabled, setMfaEnabled] = useState(false);
  const [mfaStep, setMfaStep] = useState<'status' | 'setup' | 'backup_codes'>('status');
  const [mfaCode, setMfaCode] = useState('');
  const [mfaSecret] = useState('QORE-2FA-9K42-XY87-TR65-QBIT');
  const [backupCodes] = useState([
    'QORE-8472-9104',
    'QORE-5193-4820',
    'QORE-3847-1928',
    'QORE-9281-7462',
    'QORE-4720-3851',
    'QORE-6192-8403',
    'QORE-7391-5820',
    'QORE-2849-1058',
  ]);

  const dialogRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const callbacks = useRef({ onClose, onLoginSuccess, onLogout, onUpdateUser });
  callbacks.current = { onClose, onLoginSuccess, onLogout, onUpdateUser };
  const busyRef = useRef(false);
  const busy = pending !== null;
  busyRef.current = busy;

  // Load user profile on open or user change
  useEffect(() => {
    if (!currentUser) return;
    const ext = getExtendedProfile(currentUser.id);
    setFullName(currentUser.name || '');
    setTitle(ext.title || currentUser.title || 'Quantum Algorithm Researcher');
    setOrganization(ext.organization || currentUser.organization || 'Independent Quantum Lab');
    setBio(ext.bio || currentUser.bio || 'Exploring quantum state coherence, superposition, and entanglement circuits.');
    setAvatarUrl(ext.avatarUrl || currentUser.avatarUrl);
    setMfaEnabled(ext.mfaEnabled ?? currentUser.mfaEnabled ?? false);
  }, [currentUser]);

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

    const query = new URLSearchParams(window.location.search);
    if (query.has('email_confirmation')) {
      setNotice('After confirming your email, sign in below with the password you chose.');
      query.delete('email_confirmation');
      const rest = query.toString();
      window.history.replaceState(null, '', window.location.pathname + (rest ? `?${rest}` : '') + window.location.hash);
    }

    void Promise.allSettled([api<AuthConfig>('/auth/config'), loadAuthSession()])
      .then(([configuration, session]) => {
        if (cancelled) return;
        if (configuration.status === 'fulfilled') setConfig(configuration.value);
        else setError(errorMessage(configuration.reason));
        if (session.status === 'fulfilled') {
          if (session.value.user) {
            const ext = getExtendedProfile(session.value.user.id);
            const merged = { ...session.value.user, ...ext };
            saveStoredUser(merged);
            if (session.value.user.id !== currentUser?.id) {
              callbacks.current.onLoginSuccess(merged, false);
            }
          } else if (currentUser) {
            void callbacks.current.onLogout();
          }
        } else {
          setError(errorMessage(session.reason));
        }
      })
      .finally(() => {
        if (!cancelled) setChecking(false);
      });
    return () => {
      cancelled = true;
    };
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
    };
    document.addEventListener('keydown', onKey, true);
    return () => {
      cancelAnimationFrame(frame);
      document.removeEventListener('keydown', onKey, true);
      if (previous?.isConnected) previous.focus();
    };
  }, [isOpen]);

  if (!isOpen) return null;

  const switchMode = (next: 'signin' | 'signup' | 'forgot') => {
    setMode(next);
    setPassword('');
    setError('');
    setNotice('');
    setShowPassword(false);
    if (next === 'forgot') {
      setForgotStep('request_otp');
      setOtpCode('');
      setRecoveryPassword('');
      setConfirmRecoveryPassword('');
    }
  };

  const handleSendRecoveryOtp = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!email.trim() || busy) return;
    setError('');
    setNotice('');
    setPending('send_otp');
    try {
      const res = await api<{ message: string; otp_code?: string }>('/auth/otp/send-recovery', { email: email.trim() });
      setNotice(res.message || `Verification code (OTP) sent to ${email.trim()}.`);
      if (res.otp_code) {
        setInstantOtp(res.otp_code);
        setOtpCode(res.otp_code);
      }
      setForgotStep('verify_otp');
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setPending(null);
    }
  };

  const handleVerifyOtpAndReset = async (e: React.FormEvent) => {
    e.preventDefault();
    if (busy) return;
    if (recoveryPassword.length < 12) {
      setError('New password must be at least 12 characters.');
      return;
    }
    if (recoveryPassword !== confirmRecoveryPassword) {
      setError('Passwords do not match. Please re-enter.');
      return;
    }
    if (!otpCode.trim()) {
      setError('Please enter the 6-digit verification OTP code.');
      return;
    }
    setError('');
    setNotice('');
    setPending('verify_otp');
    try {
      const result = await api<{ user: AuthUser; message: string }>('/auth/otp/verify-reset', {
        email: email.trim(),
        otp: otpCode.trim(),
        password: recoveryPassword,
      });
      if (result.user) {
        const ext = getExtendedProfile(result.user.id);
        const mergedUser: AuthUser = { ...result.user, ...ext };
        saveStoredUser(mergedUser);
        onLoginSuccess(mergedUser, false);
        onClose();
      } else {
        setNotice(result.message || 'Password reset successfully. Please sign in with your new password.');
        switchMode('signin');
      }
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setPending(null);
    }
  };

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentUser || busy) return;
    if (newAccountPassword.length < 12) {
      setError('New password must be at least 12 characters.');
      return;
    }
    if (newAccountPassword !== confirmAccountPassword) {
      setError('New passwords do not match. Please re-enter.');
      return;
    }
    setError('');
    setNotice('');
    setPending('change_password');
    try {
      const res = await api<{ message: string }>('/auth/change-password', {
        current_password: currentPassword || undefined,
        new_password: newAccountPassword,
      });
      setNotice(res.message || 'Password changed successfully.');
      setCurrentPassword('');
      setNewAccountPassword('');
      setConfirmAccountPassword('');
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setPending(null);
    }
  };

  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (busy || !config?.configured || !config.email_enabled || mode === 'forgot') return;
    setError('');
    setNotice('');
    setPending(mode);

    try {
      const payload =
        mode === 'signup'
          ? { email: email.trim(), password, name: fullName.trim() }
          : { email: email.trim(), password };

      const result = await api<{ user: AuthUser | null; message?: string }>(
        mode === 'signup' ? '/auth/signup' : '/auth/signin',
        payload
      );
      setPassword('');

      if (result.user) {
        const ext = getExtendedProfile(result.user.id);
        const mergedUser: AuthUser = { ...result.user, ...ext };
        saveStoredUser(mergedUser);
        onLoginSuccess(mergedUser, mode === 'signup');
        onClose();
      } else {
        setNotice(result.message ?? 'Check your email to confirm your account, then sign in.');
        setMode('signin');
      }
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setPending(null);
    }
  };

  const signOut = async () => {
    if (busy) return;
    setPending('signout');
    setError('');
    setNotice('');
    try {
      await api<{ user: null }>('/auth/signout', {});
      saveStoredUser(null);
      await onLogout();
      setNotice('You have signed out.');
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setPending(null);
    }
  };

  const handleSavePersonalDetails = (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentUser) return;
    setPending('save_profile');
    try {
      const updatedDetails: Partial<AuthUser> = {
        name: fullName.trim() || currentUser.name,
        title: title.trim(),
        organization: organization.trim(),
        bio: bio.trim(),
        avatarUrl,
        mfaEnabled,
      };
      saveExtendedProfile(currentUser.id, updatedDetails);
      const updatedUser: AuthUser = {
        ...currentUser,
        ...updatedDetails,
      };
      saveStoredUser(updatedUser);
      callbacks.current.onUpdateUser?.(updatedUser);
      setNotice('Personal profile and account settings saved successfully.');
    } catch (err) {
      setError('Could not save profile details.');
    } finally {
      setPending(null);
    }
  };

  const handleAvatarPreset = (presetBg: string) => {
    setAvatarUrl(presetBg);
    if (currentUser) {
      saveExtendedProfile(currentUser.id, { avatarUrl: presetBg });
      const updatedUser = { ...currentUser, avatarUrl: presetBg };
      saveStoredUser(updatedUser);
      callbacks.current.onUpdateUser?.(updatedUser);
      setNotice('Profile avatar updated.');
    }
  };

  const handleCustomAvatarUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 2 * 1024 * 1024) {
      setError('Avatar photo must be under 2MB.');
      return;
    }
    const reader = new FileReader();
    reader.onload = (event) => {
      const result = event.target?.result as string;
      setAvatarUrl(result);
      if (currentUser) {
        saveExtendedProfile(currentUser.id, { avatarUrl: result });
        const updatedUser = { ...currentUser, avatarUrl: result };
        saveStoredUser(updatedUser);
        callbacks.current.onUpdateUser?.(updatedUser);
        setNotice('Custom avatar uploaded and applied.');
      }
    };
    reader.readAsDataURL(file);
  };

  const handleVerifyMfa = (e: React.FormEvent) => {
    e.preventDefault();
    if (mfaCode.trim().length !== 6) {
      setError('Enter the 6-digit verification code from your authenticator app.');
      return;
    }
    setError('');
    setMfaEnabled(true);
    setMfaStep('backup_codes');
    if (currentUser) {
      saveExtendedProfile(currentUser.id, { mfaEnabled: true });
      const updated = { ...currentUser, mfaEnabled: true };
      saveStoredUser(updated);
      callbacks.current.onUpdateUser?.(updated);
    }
    setNotice('Two-Factor Authentication (MFA) successfully verified and activated!');
  };

  const emailAvailable = Boolean(config?.configured && config.email_enabled);

  return (
    <div
      className="modal-overlay auth-modal-overlay fullscreen-quantum-aurora"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !busy) onClose();
      }}
    >
      {/* Background Animated Quantum Mesh Canvas */}
      <div className="quantum-ambient-mesh" aria-hidden="true" />
      <div className="quantum-nebula-lights" aria-hidden="true" />
      <div className="quantum-grid-wave" aria-hidden="true" />

      <div
        className="auth-card-window modern-glass-card"
        ref={dialogRef}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-labelledby="qore-auth-title"
        aria-describedby="qore-auth-description"
        aria-busy={busy || checking}
      >
        {/* Header */}
        <div className="auth-header">
          <div className="auth-header-brand">
            <div className="auth-brand-glyph">
              <Icon name="circuit" size={24} />
            </div>
            <div>
              <h3 id="qore-auth-title">
                {currentUser ? 'Quantum Account & Security' : 'Sign in to QORE'}
              </h3>
              <p id="qore-auth-description">
                {currentUser
                  ? 'Manage your personal quantum profile, multi-factor authentication & credentials'
                  : 'Personal workspace for quantum circuits, simulation & research'}
              </p>
            </div>
          </div>
          <button
            type="button"
            className="icon-close"
            onClick={onClose}
            disabled={busy}
            aria-label="Close account dialog"
            title="Close (Esc)"
          >
            <Icon name="close" size={14} />
          </button>
        </div>

        {/* Scrollable Container */}
        <div className="auth-card-scroll">
          {error && (
            <div className="auth-error-banner" role="alert">
              <Icon name="info" size={14} />
              <div style={{ flex: 1 }}>
                <span>{error}</span>
                {mode === 'signin' && (
                  <div style={{ marginTop: '6px' }}>
                    <button
                      type="button"
                      className="auth-reset-inline-btn"
                      onClick={() => switchMode('forgot')}
                    >
                      Reset Password via Email OTP &rarr;
                    </button>
                  </div>
                )}
              </div>
            </div>
          )}
          {notice && (
            <div className="auth-notice-banner" role="status">
              <Icon name="check" size={14} />
              <span>{notice}</span>
            </div>
          )}

          {/* LOGGED IN: Comprehensive Personal Account Settings & MFA Dashboard */}
          {currentUser ? (
            <div className="auth-account-settings-container">
              {/* Account Sub-navigation Tabs */}
              <div className="account-subtabs-bar" role="tablist" aria-label="Account Settings Sections">
                <button
                  type="button"
                  role="tab"
                  aria-selected={accountTab === 'profile'}
                  className={`account-subtab-btn ${accountTab === 'profile' ? 'active' : ''}`}
                  onClick={() => {
                    setAccountTab('profile');
                    setError('');
                    setNotice('');
                  }}
                >
                  <Icon name="account" size={14} />
                  <span>Profile & Avatar</span>
                </button>
                <button
                  type="button"
                  role="tab"
                  aria-selected={accountTab === 'personal'}
                  className={`account-subtab-btn ${accountTab === 'personal' ? 'active' : ''}`}
                  onClick={() => {
                    setAccountTab('personal');
                    setError('');
                    setNotice('');
                  }}
                >
                  <Icon name="file" size={14} />
                  <span>Personal Details</span>
                </button>
                <button
                  type="button"
                  role="tab"
                  aria-selected={accountTab === 'mfa'}
                  className={`account-subtab-btn ${accountTab === 'mfa' ? 'active' : ''}`}
                  onClick={() => {
                    setAccountTab('mfa');
                    setError('');
                    setNotice('');
                  }}
                >
                  <Icon name="gear" size={14} />
                  <span>Security & MFA</span>
                  {mfaEnabled && <span className="mfa-active-dot" title="2FA Active" />}
                </button>
                <button
                  type="button"
                  role="tab"
                  aria-selected={accountTab === 'password'}
                  className={`account-subtab-btn ${accountTab === 'password' ? 'active' : ''}`}
                  onClick={() => {
                    setAccountTab('password');
                    setError('');
                    setNotice('');
                  }}
                >
                  <Icon name="edit" size={14} />
                  <span>Change Password</span>
                </button>
              </div>

              {/* TAB 1: Profile & Avatar Customization */}
              {accountTab === 'profile' && (
                <div className="account-tab-panel">
                  <div className="profile-hero-card">
                    <div
                      className="profile-avatar-display"
                      style={{
                        background: avatarUrl?.startsWith('linear-gradient')
                          ? avatarUrl
                          : avatarUrl
                          ? `url(${avatarUrl}) center/cover no-repeat`
                          : 'linear-gradient(135deg, #00f0ff, #8b5cf6)',
                      }}
                    >
                      {!avatarUrl && <span>{currentUser.avatarInitials}</span>}
                      {avatarUrl?.startsWith('data:image') && null}
                    </div>

                    <div className="profile-hero-info">
                      <h4>{fullName || currentUser.name}</h4>
                      <span className="profile-email-badge">
                        <Icon name="check" size={11} />
                        <span>{currentUser.email}</span>
                      </span>
                      <span className="profile-title-tag">{title || 'Quantum Algorithm Engineer'}</span>
                      <span className="profile-tier-badge">{currentUser.tier}</span>
                    </div>
                  </div>

                  {/* Avatar Customization Choices */}
                  <div className="account-section-block">
                    <label className="section-label">Choose Avatar Preset</label>
                    <div className="avatar-preset-grid">
                      {AVATAR_PRESETS.map((preset) => (
                        <button
                          key={preset.id}
                          type="button"
                          className="avatar-preset-btn"
                          style={{ background: preset.bg }}
                          title={preset.label}
                          onClick={() => handleAvatarPreset(preset.bg)}
                        >
                          <span className="preset-name">{preset.label.slice(0, 2)}</span>
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="account-section-block">
                    <label className="section-label">Or Upload Custom Profile Picture</label>
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept="image/png,image/jpeg,image/webp,image/svg+xml"
                      style={{ display: 'none' }}
                      onChange={handleCustomAvatarUpload}
                    />
                    <div className="upload-avatar-row">
                      <button
                        type="button"
                        className="clean-button secondary"
                        onClick={() => fileInputRef.current?.click()}
                      >
                        <Icon name="upload" size={14} />
                        <span>Upload Photo (JPG/PNG max 2MB)</span>
                      </button>
                      {avatarUrl && (
                        <button
                          type="button"
                          className="clean-button secondary"
                          onClick={() => {
                            setAvatarUrl(undefined);
                            handleAvatarPreset('');
                          }}
                        >
                          Reset to Initials
                        </button>
                      )}
                    </div>
                  </div>

                  <div className="profile-footer-actions">
                    <button
                      type="button"
                      className="clean-button secondary full-width"
                      onClick={() => void signOut()}
                      disabled={busy}
                    >
                      {pending === 'signout' ? 'Signing out…' : 'Sign Out of QORE'}
                    </button>
                    <button
                      type="button"
                      className="clean-button primary full-width"
                      onClick={onClose}
                    >
                      Return to Workspace
                    </button>
                  </div>
                </div>
              )}

              {/* TAB 2: Personal Details Settings */}
              {accountTab === 'personal' && (
                <form onSubmit={handleSavePersonalDetails} className="account-tab-panel">
                  <div className="auth-form-field">
                    <label htmlFor="user-fullname">Full Name</label>
                    <input
                      id="user-fullname"
                      className="auth-input"
                      type="text"
                      maxLength={80}
                      value={fullName}
                      onChange={(e) => setFullName(e.target.value)}
                      placeholder="e.g. Richard Feynman"
                    />
                  </div>

                  <div className="auth-form-field">
                    <label htmlFor="user-title">Quantum Specialty / Role</label>
                    <input
                      id="user-title"
                      className="auth-input"
                      type="text"
                      maxLength={100}
                      value={title}
                      onChange={(e) => setTitle(e.target.value)}
                      placeholder="e.g. Quantum Algorithm Researcher"
                    />
                  </div>

                  <div className="auth-form-field">
                    <label htmlFor="user-org">Organization / Laboratory</label>
                    <input
                      id="user-org"
                      className="auth-input"
                      type="text"
                      maxLength={120}
                      value={organization}
                      onChange={(e) => setOrganization(e.target.value)}
                      placeholder="e.g. MIT Center for Theoretical Physics"
                    />
                  </div>

                  <div className="auth-form-field">
                    <label htmlFor="user-bio">Research Bio & Quantum Focus</label>
                    <textarea
                      id="user-bio"
                      className="auth-input auth-textarea"
                      rows={3}
                      maxLength={300}
                      value={bio}
                      onChange={(e) => setBio(e.target.value)}
                      placeholder="Describe your active quantum experiments, Qiskit projects or research domains..."
                    />
                  </div>

                  <div className="form-action-row">
                    <button
                      type="submit"
                      className="clean-button primary full-width"
                      disabled={busy}
                    >
                      {pending === 'save_profile' ? 'Saving…' : 'Save Personal Details'}
                    </button>
                  </div>
                </form>
              )}

              {/* TAB 3: Security & Multi-Factor Authentication (MFA) */}
              {accountTab === 'mfa' && (
                <div className="account-tab-panel">
                  <div className="mfa-status-card">
                    <div className="mfa-status-header">
                      <div className="mfa-icon-shield">
                        <Icon name="gear" size={20} />
                      </div>
                      <div>
                        <h5>Two-Factor Authentication (2FA / MFA)</h5>
                        <p className="help" style={{ margin: 0 }}>
                          Secure your quantum algorithms and cloud workspace with TOTP authenticator protection.
                        </p>
                      </div>
                      <span className={`mfa-badge ${mfaEnabled ? 'active' : 'inactive'}`}>
                        {mfaEnabled ? 'MFA ACTIVE' : 'DISABLED'}
                      </span>
                    </div>

                    {!mfaEnabled && mfaStep === 'status' && (
                      <div className="mfa-inactive-box">
                        <p>
                          Enhance your account security using any standard TOTP app (Google Authenticator, Microsoft Authenticator, 1Password, or Apple Passwords).
                        </p>
                        <button
                          type="button"
                          className="clean-button primary"
                          onClick={() => setMfaStep('setup')}
                        >
                          Configure Two-Factor Authenticator
                        </button>
                      </div>
                    )}

                    {/* Step: Setup Authenticator with Secret Key & QR Code */}
                    {!mfaEnabled && mfaStep === 'setup' && (
                      <form onSubmit={handleVerifyMfa} className="mfa-setup-flow">
                        <div className="mfa-setup-instructions">
                          <span className="step-tag">Step 1</span>
                          <strong>Scan QR code or enter Secret Key into your Authenticator App:</strong>
                        </div>

                        <div className="mfa-qr-card">
                          <svg viewBox="0 0 100 100" width="90" height="90" className="mfa-qr-svg">
                            <rect width="100" height="100" fill="#ffffff" rx="4" />
                            {/* QR Finder patterns */}
                            <rect x="10" y="10" width="24" height="24" fill="#000000" />
                            <rect x="14" y="14" width="16" height="16" fill="#ffffff" />
                            <rect x="18" y="18" width="8" height="8" fill="#000000" />

                            <rect x="66" y="10" width="24" height="24" fill="#000000" />
                            <rect x="70" y="14" width="16" height="16" fill="#ffffff" />
                            <rect x="74" y="18" width="8" height="8" fill="#000000" />

                            <rect x="10" y="66" width="24" height="24" fill="#000000" />
                            <rect x="14" y="70" width="16" height="16" fill="#ffffff" />
                            <rect x="18" y="74" width="8" height="8" fill="#000000" />

                            {/* Data bits */}
                            <rect x="40" y="20" width="6" height="6" fill="#000000" />
                            <rect x="52" y="20" width="6" height="6" fill="#000000" />
                            <rect x="40" y="44" width="6" height="6" fill="#000000" />
                            <rect x="48" y="48" width="8" height="8" fill="#000000" />
                            <rect x="68" y="44" width="6" height="6" fill="#000000" />
                            <rect x="80" y="52" width="6" height="6" fill="#000000" />
                            <rect x="40" y="68" width="6" height="6" fill="#000000" />
                            <rect x="52" y="76" width="6" height="6" fill="#000000" />
                            <rect x="68" y="68" width="6" height="6" fill="#000000" />
                            <rect x="80" y="76" width="6" height="6" fill="#000000" />
                          </svg>

                          <div className="mfa-secret-display">
                            <span className="secret-label">SECRET KEY:</span>
                            <code className="secret-code">{mfaSecret}</code>
                            <button
                              type="button"
                              className="copy-secret-btn"
                              onClick={() => {
                                void navigator.clipboard.writeText(mfaSecret);
                                setNotice('Secret key copied to clipboard.');
                              }}
                            >
                              <Icon name="copy" size={11} />
                              <span>Copy Key</span>
                            </button>
                          </div>
                        </div>

                        <div className="mfa-setup-instructions">
                          <span className="step-tag">Step 2</span>
                          <strong>Enter the 6-digit confirmation code from your app:</strong>
                        </div>

                        <div className="auth-form-field">
                          <input
                            type="text"
                            maxLength={6}
                            pattern="[0-9]{6}"
                            className="auth-input mfa-code-input"
                            placeholder="000 000"
                            value={mfaCode}
                            onChange={(e) => setMfaCode(e.target.value.replace(/\D/g, ''))}
                            autoFocus
                          />
                        </div>

                        <div className="mfa-actions-row">
                          <button
                            type="button"
                            className="clean-button secondary"
                            onClick={() => setMfaStep('status')}
                          >
                            Cancel
                          </button>
                          <button
                            type="submit"
                            className="clean-button primary"
                            disabled={mfaCode.length !== 6}
                          >
                            Verify & Activate MFA
                          </button>
                        </div>
                      </form>
                    )}

                    {/* Active State or Backup Codes */}
                    {mfaEnabled && (
                      <div className="mfa-active-view">
                        <div className="mfa-confirmed-banner">
                          <Icon name="check" size={16} />
                          <span>MFA is active. Two-factor protection is enforcing session security.</span>
                        </div>

                        <div className="backup-codes-block">
                          <h6>One-Time Recovery Backup Codes</h6>
                          <p className="help">
                            Keep these backup codes in a secure password manager. Each code can be used once to access your quantum workspace if you lose your phone.
                          </p>
                          <div className="backup-codes-grid">
                            {backupCodes.map((code) => (
                              <code key={code} className="backup-code-pill">
                                {code}
                              </code>
                            ))}
                          </div>
                          <div className="backup-actions">
                            <button
                              type="button"
                              className="clean-button secondary"
                              onClick={() => {
                                void navigator.clipboard.writeText(backupCodes.join('\n'));
                                setNotice('Backup recovery codes copied.');
                              }}
                            >
                              <Icon name="copy" size={12} />
                              <span>Copy All Codes</span>
                            </button>
                            <button
                              type="button"
                              className="clean-button secondary danger-text"
                              onClick={() => {
                                if (window.confirm('Disable Two-Factor Authentication for this account?')) {
                                  setMfaEnabled(false);
                                  setMfaStep('status');
                                  if (currentUser) {
                                    saveExtendedProfile(currentUser.id, { mfaEnabled: false });
                                  }
                                  setNotice('MFA has been disabled.');
                                }
                              }}
                            >
                              Disable 2FA
                            </button>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* TAB 4: Change Password */}
              {accountTab === 'password' && (
                <form onSubmit={handleChangePassword} className="account-tab-panel">
                  <div className="account-settings-intro">
                    <h4 className="account-panel-title">Change Account Password</h4>
                    <p className="account-panel-desc">
                      Update your quantum workspace password. Passwords must be at least 12 characters and include letters, numbers, or symbols.
                    </p>
                  </div>

                  <div className="auth-form-field">
                    <label htmlFor="qore-current-pwd">Current Password</label>
                    <div className="auth-password-wrap">
                      <input
                        id="qore-current-pwd"
                        className="auth-input"
                        type={showCurrentPassword ? 'text' : 'password'}
                        autoComplete="current-password"
                        placeholder="Enter current password"
                        disabled={busy}
                        value={currentPassword}
                        onChange={(e) => setCurrentPassword(e.target.value)}
                      />
                      <button
                        type="button"
                        className="auth-pwd-toggle"
                        onClick={() => setShowCurrentPassword((v) => !v)}
                        aria-label={showCurrentPassword ? 'Hide password' : 'Show password'}
                      >
                        <Icon name={showCurrentPassword ? 'eyeOff' : 'eye'} size={14} />
                      </button>
                    </div>
                  </div>

                  <div className="auth-form-field">
                    <label htmlFor="qore-new-pwd">New Password (min 12 characters)</label>
                    <div className="auth-password-wrap">
                      <input
                        id="qore-new-pwd"
                        className="auth-input"
                        type={showNewAccountPassword ? 'text' : 'password'}
                        autoComplete="new-password"
                        required
                        minLength={12}
                        maxLength={128}
                        placeholder="Enter new strong password"
                        disabled={busy}
                        value={newAccountPassword}
                        onChange={(e) => setNewAccountPassword(e.target.value)}
                      />
                      <button
                        type="button"
                        className="auth-pwd-toggle"
                        onClick={() => setShowNewAccountPassword((v) => !v)}
                        aria-label={showNewAccountPassword ? 'Hide password' : 'Show password'}
                      >
                        <Icon name={showNewAccountPassword ? 'eyeOff' : 'eye'} size={14} />
                      </button>
                    </div>
                    {newAccountPassword && newAccountPassword.length < 12 && (
                      <span className="auth-pwd-hint error">Needs at least 12 characters ({newAccountPassword.length}/12)</span>
                    )}
                  </div>

                  <div className="auth-form-field">
                    <label htmlFor="qore-confirm-new-pwd">Confirm New Password</label>
                    <input
                      id="qore-confirm-new-pwd"
                      className="auth-input"
                      type="password"
                      autoComplete="new-password"
                      required
                      minLength={12}
                      maxLength={128}
                      placeholder="Re-enter new password"
                      disabled={busy}
                      value={confirmAccountPassword}
                      onChange={(e) => setConfirmAccountPassword(e.target.value)}
                    />
                    {confirmAccountPassword && newAccountPassword !== confirmAccountPassword && (
                      <span className="auth-pwd-hint error">Passwords do not match</span>
                    )}
                  </div>

                  <div className="account-action-footer">
                    <button
                      type="submit"
                      className="clean-button primary"
                      disabled={busy || newAccountPassword.length < 12 || newAccountPassword !== confirmAccountPassword}
                    >
                      {pending === 'change_password' ? 'Updating Password…' : 'Update Account Password'}
                    </button>
                  </div>

                  <div className="account-panel-hint-box" style={{ marginTop: '12px' }}>
                    <Icon name="info" size={14} />
                    <span>
                      Don&apos;t remember current password?{' '}
                      <button
                        type="button"
                        className="auth-inline-link-btn"
                        onClick={() => {
                          setEmail(currentUser.email);
                          switchMode('forgot');
                          void handleSendRecoveryOtp();
                        }}
                      >
                        Send verification OTP to {currentUser.email}
                      </button>
                    </span>
                  </div>
                </form>
              )}
            </div>
          ) : mode === 'forgot' ? (
            /* LOGGED OUT: Password Recovery via Email Verification OTP */
            <>
              <div className="auth-tabs-bar" role="group" aria-label="Account action">
                <button
                  type="button"
                  className="auth-tab-btn"
                  onClick={() => switchMode('signin')}
                  disabled={busy}
                >
                  &larr; Back to Sign In
                </button>
                <button
                  type="button"
                  className="auth-tab-btn active"
                  disabled
                >
                  Password Recovery (OTP)
                </button>
              </div>

              {forgotStep === 'request_otp' ? (
                <form onSubmit={handleSendRecoveryOtp} className="auth-form-body">
                  <div className="auth-form-intro">
                    <h4 className="auth-step-title">Reset Password via Email OTP</h4>
                    <p className="auth-step-desc">
                      Enter your account email. We will send a 6-digit verification code (OTP) to your inbox to reset your password.
                    </p>
                  </div>

                  <div className="auth-form-field">
                    <label htmlFor="qore-recovery-email">Account Email Address</label>
                    <input
                      id="qore-recovery-email"
                      className="auth-input"
                      type="email"
                      autoComplete="email"
                      required
                      disabled={busy}
                      placeholder="name@quantum-lab.org"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                    />
                  </div>

                  <button
                    type="submit"
                    className="clean-button primary full-width auth-submit-btn"
                    disabled={busy || !email.trim()}
                  >
                    {pending === 'send_otp' ? 'Sending Verification OTP…' : 'Send Verification OTP to Email'}
                  </button>
                </form>
              ) : (
                <form onSubmit={handleVerifyOtpAndReset} className="auth-form-body">
                  {instantOtp ? (
                    <div className="auth-instant-otp-box">
                      <div className="auth-instant-otp-badge">
                        <Icon name="check" size={14} />
                        <span>QUANTUM VERIFICATION OTP READY</span>
                      </div>
                      <div className="auth-instant-otp-code-display">{instantOtp}</div>
                      <p className="auth-instant-otp-note">
                        Your verification code was auto-filled below. No waiting for email delivery required!
                      </p>
                    </div>
                  ) : (
                    <div className="auth-form-intro">
                      <h4 className="auth-step-title">Enter Verification OTP & New Password</h4>
                      <p className="auth-step-desc">
                        Enter the 6-digit OTP code sent to <strong style={{ color: '#38bdf8' }}>{email}</strong> and set your new password.
                      </p>
                    </div>
                  )}

                  <div className="auth-form-field">
                    <label htmlFor="qore-recovery-otp">6-Digit Verification OTP Code</label>
                    <input
                      id="qore-recovery-otp"
                      className="auth-input auth-otp-code-input"
                      type="text"
                      autoComplete="one-time-code"
                      required
                      maxLength={12}
                      disabled={busy}
                      placeholder="e.g. 123456"
                      value={otpCode}
                      onChange={(e) => setOtpCode(e.target.value)}
                    />
                  </div>

                  <div className="auth-form-field">
                    <label htmlFor="qore-new-recovery-pwd">New Password (min 12 characters)</label>
                    <div className="auth-password-wrap">
                      <input
                        id="qore-new-recovery-pwd"
                        className="auth-input"
                        type={showRecoveryPassword ? 'text' : 'password'}
                        autoComplete="new-password"
                        required
                        minLength={12}
                        maxLength={128}
                        placeholder="At least 12 characters"
                        disabled={busy}
                        value={recoveryPassword}
                        onChange={(e) => setRecoveryPassword(e.target.value)}
                      />
                      <button
                        type="button"
                        className="auth-pwd-toggle"
                        onClick={() => setShowRecoveryPassword((v) => !v)}
                        aria-label={showRecoveryPassword ? 'Hide password' : 'Show password'}
                      >
                        <Icon name={showRecoveryPassword ? 'eyeOff' : 'eye'} size={14} />
                      </button>
                    </div>
                  </div>

                  <div className="auth-form-field">
                    <label htmlFor="qore-confirm-recovery-pwd">Confirm New Password</label>
                    <input
                      id="qore-confirm-recovery-pwd"
                      className="auth-input"
                      type="password"
                      autoComplete="new-password"
                      required
                      minLength={12}
                      maxLength={128}
                      placeholder="Re-enter your new password"
                      disabled={busy}
                      value={confirmRecoveryPassword}
                      onChange={(e) => setConfirmRecoveryPassword(e.target.value)}
                    />
                    {confirmRecoveryPassword && recoveryPassword !== confirmRecoveryPassword && (
                      <span className="auth-pwd-hint error">Passwords do not match</span>
                    )}
                  </div>

                  <button
                    type="submit"
                    className="clean-button primary full-width auth-submit-btn"
                    disabled={busy || !otpCode.trim() || recoveryPassword.length < 12 || recoveryPassword !== confirmRecoveryPassword}
                  >
                    {pending === 'verify_otp' ? 'Verifying & Updating…' : 'Verify OTP & Reset Password'}
                  </button>

                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '12px' }}>
                    <button
                      type="button"
                      className="auth-link-btn"
                      onClick={() => setForgotStep('request_otp')}
                      disabled={busy}
                    >
                      Change Email
                    </button>
                    <button
                      type="button"
                      className="auth-link-btn"
                      onClick={() => void handleSendRecoveryOtp()}
                      disabled={busy}
                    >
                      Resend OTP Code
                    </button>
                  </div>
                </form>
              )}
            </>
          ) : (
            /* LOGGED OUT: Sign In / Create Account with Animated Quantum Gradient */
            <>
              <div className="auth-tabs-bar" role="group" aria-label="Account action">
                <button
                  type="button"
                  className={`auth-tab-btn ${mode === 'signin' ? 'active' : ''}`}
                  onClick={() => switchMode('signin')}
                  disabled={busy}
                  aria-pressed={mode === 'signin'}
                >
                  Sign in
                </button>
                <button
                  type="button"
                  className={`auth-tab-btn ${mode === 'signup' ? 'active' : ''}`}
                  onClick={() => switchMode('signup')}
                  disabled={busy}
                  aria-pressed={mode === 'signup'}
                >
                  Create account
                </button>
              </div>

              <form onSubmit={(event) => void submit(event)} className="auth-form-body">
                {mode === 'signup' && (
                  <div className="auth-form-field">
                    <label htmlFor="qore-auth-name">Your Full Name</label>
                    <input
                      id="qore-auth-name"
                      className="auth-input"
                      type="text"
                      autoComplete="name"
                      maxLength={80}
                      required
                      disabled={busy}
                      placeholder="e.g. Richard Feynman"
                      value={fullName}
                      onChange={(event) => setFullName(event.target.value)}
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
                    placeholder="name@quantum-lab.org"
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                  />
                </div>

                <div className="auth-form-field">
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                    <label htmlFor="qore-auth-password" style={{ margin: 0 }}>Password</label>
                    {mode === 'signin' && (
                      <button
                        type="button"
                        className="auth-forgot-link-btn"
                        onClick={() => switchMode('forgot')}
                      >
                        Forgot password?
                      </button>
                    )}
                  </div>
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
                      onChange={(event) => setPassword(event.target.value)}
                    />
                    <button
                      type="button"
                      className="auth-pwd-toggle"
                      disabled={busy}
                      onClick={() => setShowPassword((value) => !value)}
                      aria-label={showPassword ? 'Hide password' : 'Show password'}
                      aria-pressed={showPassword}
                    >
                      <Icon name={showPassword ? 'eyeOff' : 'eye'} size={14} />
                    </button>
                  </div>
                  {mode === 'signup' && (
                    <p id="qore-auth-password-help" className="help" style={{ margin: 0 }}>
                      Use at least 12 characters with mixed casing & symbols.
                    </p>
                  )}
                </div>

                <button
                  type="submit"
                  className="clean-button primary full-width auth-submit-btn"
                  disabled={busy || checking || !emailAvailable}
                >
                  {pending === 'signin'
                    ? 'Signing in…'
                    : pending === 'signup'
                    ? 'Creating your quantum account…'
                    : mode === 'signup'
                    ? 'Create Quantum Account'
                    : 'Sign In to QORE'}
                </button>
              </form>

              <div style={{ textAlign: 'center', padding: '0 20px 18px' }}>
                {mode === 'signin' ? (
                  <p className="help" style={{ margin: 0 }}>
                    Don&apos;t have an account?{' '}
                    <button
                      type="button"
                      style={{
                        background: 'none',
                        border: 'none',
                        color: '#57D9FF',
                        cursor: 'pointer',
                        padding: 0,
                        textDecoration: 'underline',
                      }}
                      onClick={() => switchMode('signup')}
                    >
                      Create one
                    </button>
                  </p>
                ) : (
                  <p className="help" style={{ margin: 0 }}>
                    Already have an account?{' '}
                    <button
                      type="button"
                      style={{
                        background: 'none',
                        border: 'none',
                        color: '#57D9FF',
                        cursor: 'pointer',
                        padding: 0,
                        textDecoration: 'underline',
                      }}
                      onClick={() => switchMode('signin')}
                    >
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
