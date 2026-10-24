import React, { useState } from 'react';
import { Icon } from './Icons';

export interface AuthUser {
  id: string;
  name: string;
  email: string;
  role: string;
  tier: string;
  avatarInitials: string;
  token: string;
  syncedCircuits: number;
}

const DEFAULT_GUEST_USER: AuthUser = {
  id: 'guest-dev-01',
  name: 'Quantum Engineer',
  email: 'engineer@qore.local',
  role: 'Quantum Researcher',
  tier: 'Local Kernel',
  avatarInitials: 'QE',
  token: 'tok_local_guest_dev',
  syncedCircuits: 5,
};

export function loadStoredUser(): AuthUser | null {
  // Authentication is intentionally owned by Supabase Auth. Do not hydrate
  // identities or bearer tokens from localStorage.
  return null;
}

export function saveStoredUser(_user: AuthUser | null) { /* Supabase owns the session cookie. */ }

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
  currentUser: AuthUser | null;
  onLoginSuccess: (user: AuthUser) => void;
  onLogout: () => void;
}

export function AuthModal({
  isOpen,
  onClose,
  currentUser,
  onLoginSuccess,
  onLogout,
}: AuthModalProps) {
  const [mode, setMode] = useState<'signin' | 'signup'>('signin');
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  // Sign In State
  const [signInEmail, setSignInEmail] = useState('');
  const [signInPassword, setSignInPassword] = useState('');

  // Sign Up State
  const [signUpName, setSignUpName] = useState('');
  const [signUpEmail, setSignUpEmail] = useState('');
  const [signUpPassword, setSignUpPassword] = useState('');
  const [signUpRole, setSignUpRole] = useState('Quantum Algorithm Researcher');

  if (!isOpen) return null;

  const handleSignIn = (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg('');

    if (!signInEmail.trim() || !signInPassword) {
      setErrorMsg('Please enter both email and password.');
      return;
    }

    setErrorMsg('Supabase Auth is not connected yet. Configure the QORE backend auth provider before signing in.');
  };

  const handleSignUp = (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg('');

    if (!signUpName.trim()) {
      setErrorMsg('Please enter your full name.');
      return;
    }
    if (!signUpEmail.trim() || !signUpEmail.includes('@')) {
      setErrorMsg('Please enter a valid email address.');
      return;
    }
    if (signUpPassword.length < 6) {
      setErrorMsg('Password must be at least 6 characters.');
      return;
    }

    setErrorMsg('Supabase Auth is not connected yet. Configure the QORE backend auth provider before creating an account.');
  };

  const handleContinueAsGuest = () => {
    setErrorMsg('Guest mode is disabled in the production workspace. Connect Supabase Auth to continue.');
  };

  return (
    <div
      className="modal-overlay glass-backdrop auth-modal-overlay"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="auth-card-window" role="dialog" aria-modal="true">
        {/* Top Header */}
        <div className="auth-header">
          <div className="auth-header-brand">
            <svg viewBox="0 0 44 44" width="32" height="32" fill="none" className="auth-logo-svg">
              <circle cx="22" cy="22" r="13" stroke="#38bdf8" strokeWidth="2.4" />
              <ellipse cx="22" cy="22" rx="5" ry="14" transform="rotate(45 22 22)" stroke="#818cf8" strokeWidth="1.5" />
              <circle cx="22" cy="22" r="3" fill="#38bdf8" />
            </svg>
            <div>
              <h3>QORE Quantum Account</h3>
              <p>Secure QORE identity · Supabase Auth</p>
            </div>
          </div>
          <button type="button" className="icon-close" onClick={onClose} title="Close (Esc)">
            <Icon name="close" size={14} />
          </button>
        </div>

        {/* If user is already signed in, show profile dashboard */}
        {currentUser ? (
          <div className="auth-profile-dashboard">
            <div className="auth-avatar-hero">
              <div className="avatar-circle-large">{currentUser.avatarInitials}</div>
              <h4>{currentUser.name}</h4>
              <span className="auth-user-email">{currentUser.email}</span>
              <span className="auth-tier-badge">{currentUser.tier}</span>
            </div>

            <div className="auth-profile-details">
              <div className="profile-detail-row">
                <span className="detail-label">Designation:</span>
                <span className="detail-val">{currentUser.role}</span>
              </div>
              <div className="profile-detail-row">
                <span className="detail-label">Cloud Workspace:</span>
                <span className="detail-val success-val">Connected & Synced</span>
              </div>
              <div className="profile-detail-row">
                <span className="detail-label">Simulations Stored:</span>
                <span className="detail-val">{currentUser.syncedCircuits} circuits</span>
              </div>
              <div className="profile-detail-row">
                <span className="detail-label">Hardware Authorization:</span>
                <span className="detail-val">Qiskit Aer · Q# Net8 Runtime</span>
              </div>
            </div>

            <div className="auth-profile-actions">
              <button
                type="button"
                className="clean-button secondary full-width"
                onClick={() => {
                  onLogout();
                  saveStoredUser(null);
                }}
              >
                Sign Out of QORE
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
        ) : (
          <>
            {/* Tab Switcher */}
            <div className="auth-tabs-bar">
              <button
                type="button"
                className={`auth-tab-btn ${mode === 'signin' ? 'active' : ''}`}
                onClick={() => {
                  setMode('signin');
                  setErrorMsg('');
                }}
              >
                Sign In
              </button>
              <button
                type="button"
                className={`auth-tab-btn ${mode === 'signup' ? 'active' : ''}`}
                onClick={() => {
                  setMode('signup');
                  setErrorMsg('');
                }}
              >
                Create Account
              </button>
            </div>

            {errorMsg && (
              <div className="auth-error-banner">
                <Icon name="info" size={13} />
                <span>{errorMsg}</span>
              </div>
            )}

            {/* Sign In Form */}
            {mode === 'signin' && (
              <form onSubmit={handleSignIn} className="auth-form-body">
                <div className="auth-form-field">
                  <label>Email or Quantum Developer ID</label>
                  <input
                    type="email"
                    className="auth-input"
                    placeholder="researcher@quantum.org"
                    value={signInEmail}
                    onChange={(e) => setSignInEmail(e.target.value)}
                    autoFocus
                  />
                </div>

                <div className="auth-form-field">
                  <div className="field-label-split">
                    <label>Password</label>
                  </div>
                  <div className="auth-password-wrap">
                    <input
                      type={showPassword ? 'text' : 'password'}
                      className="auth-input"
                      placeholder="••••••••••••"
                      value={signInPassword}
                      onChange={(e) => setSignInPassword(e.target.value)}
                    />
                    <button
                      type="button"
                      className="auth-pwd-toggle"
                      onClick={() => setShowPassword(!showPassword)}
                      title={showPassword ? 'Hide password' : 'Show password'}
                    >
                      <Icon name={showPassword ? 'eyeOff' : 'eye'} size={13} />
                    </button>
                  </div>
                </div>

                <button
                  type="submit"
                  className="clean-button primary full-width auth-submit-btn"
                  disabled={isLoading}
                >
                  {isLoading ? 'Authenticating with QORE...' : 'Sign In to Studio'}
                </button>

                <div className="auth-divider">
                  <span>OR</span>
                </div>

                <button
                  type="button"
                  className="clean-button secondary full-width guest-btn"
                  onClick={handleContinueAsGuest}
                >
                  <Icon name="code" size={13} />
                  <span>Guest access disabled in production mode</span>
                </button>
              </form>
            )}

            {/* Sign Up Form */}
            {mode === 'signup' && (
              <form onSubmit={handleSignUp} className="auth-form-body">
                <div className="auth-form-field">
                  <label>Full Name</label>
                  <input
                    type="text"
                    className="auth-input"
                    placeholder="Dr. Alex Mercer"
                    value={signUpName}
                    onChange={(e) => setSignUpName(e.target.value)}
                    autoFocus
                  />
                </div>

                <div className="auth-form-field">
                  <label>Work or University Email</label>
                  <input
                    type="email"
                    className="auth-input"
                    placeholder="alex.mercer@oxford.edu"
                    value={signUpEmail}
                    onChange={(e) => setSignUpEmail(e.target.value)}
                  />
                </div>

                <div className="auth-form-field">
                  <label>Research Role / Specialization</label>
                  <select
                    className="clean-select full-width auth-select"
                    value={signUpRole}
                    onChange={(e) => setSignUpRole(e.target.value)}
                  >
                    <option value="Quantum Algorithm Researcher">Quantum Algorithm Researcher</option>
                    <option value="Quantum Software Engineer">Quantum Software Engineer</option>
                    <option value="Quantum Hardware Physicist">Quantum Hardware Physicist</option>
                    <option value="Graduate Student / Postdoc">Graduate Student / Postdoc</option>
                    <option value="Quantum Explorer">Quantum Explorer</option>
                  </select>
                </div>

                <div className="auth-form-field">
                  <label>Create Password</label>
                  <div className="auth-password-wrap">
                    <input
                      type={showPassword ? 'text' : 'password'}
                      className="auth-input"
                      placeholder="Minimum 6 characters"
                      value={signUpPassword}
                      onChange={(e) => setSignUpPassword(e.target.value)}
                    />
                    <button
                      type="button"
                      className="auth-pwd-toggle"
                      onClick={() => setShowPassword(!showPassword)}
                      title={showPassword ? 'Hide password' : 'Show password'}
                    >
                      <Icon name={showPassword ? 'eyeOff' : 'eye'} size={13} />
                    </button>
                  </div>
                </div>

                <button
                  type="submit"
                  className="clean-button primary full-width auth-submit-btn"
                  disabled={isLoading}
                >
                  {isLoading ? 'Creating Account...' : 'Create Free Developer Account'}
                </button>
              </form>
            )}
          </>
        )}
      </div>
    </div>
  );
}
