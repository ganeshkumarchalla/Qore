import React, { useEffect, useState } from 'react';
import { Icon } from './Icons';
import type { AuthUser } from './AuthModal';
import { runtimeLabel } from './types';

interface AuthSuccessBannerProps {
  user: AuthUser;
  isNewUser?: boolean;
  onDismiss: () => void;
  versions?: Record<string, string> | null;
}

export function AuthSuccessBanner({ user, isNewUser, onDismiss, versions }: AuthSuccessBannerProps) {
  const [exiting, setExiting] = useState(false);

  useEffect(() => {
    // Show centered screen smoothly for 4.8 seconds, then glide out
    const dismissTimer = window.setTimeout(() => {
      setExiting(true);
      window.setTimeout(onDismiss, 700);
    }, 4600);

    return () => window.clearTimeout(dismissTimer);
  }, [onDismiss]);

  const handleManualClose = () => {
    setExiting(true);
    window.setTimeout(onDismiss, 700);
  };

  return (
    <div
      className={`auth-success-middle-overlay ${exiting ? 'overlay-fade-out' : 'overlay-fade-in'}`}
      role="status"
      aria-live="polite"
    >
      {/* Background Quantum Mesh & Ambient Aura Flare */}
      <div className="auth-middle-ambient-mesh" aria-hidden="true" />
      <div className="auth-middle-center-glow" aria-hidden="true" />

      {/* Centered Quantum Modal Card */}
      <div className={`auth-success-middle-card ${exiting ? 'card-zoom-out' : 'card-zoom-in'}`}>
        {/* Top Floating Close Button */}
        <button
          type="button"
          className="auth-middle-close-btn"
          onClick={handleManualClose}
          aria-label="Continue to workspace"
          title="Continue (Esc)"
        >
          <Icon name="close" size={14} />
        </button>

        {/* 3D Animated Quantum Checkmark Badge with Orbital Rings */}
        <div className="auth-middle-icon-stage" aria-hidden="true">
          <div className="auth-orbit-ring ring-primary" />
          <div className="auth-orbit-ring ring-secondary" />
          <div className="auth-orbit-node node-a" />
          <div className="auth-orbit-node node-b" />
          <div className="auth-core-shield">
            <div className="auth-core-pulse" />
            <div className="auth-check-glyph">
              <Icon name="check" size={26} />
            </div>
          </div>
        </div>

        {/* Status Pill */}
        <div className="auth-middle-status-row">
          <span className="auth-middle-pill">
            <span className="auth-live-pulse-dot" />
            <span>QUANTUM SESSION VERIFIED · AER RUNTIME ACTIVE</span>
          </span>
        </div>

        {/* Typography */}
        <h2 className="auth-middle-title">
          {isNewUser ? 'Account Created Successfully' : 'Authentication Successful'}
        </h2>
        <p className="auth-middle-subtitle">
          {isNewUser
            ? 'Your private quantum enclave, circuit repository, and simulation cache are provisioned.'
            : 'Welcome back to QORE. Your private quantum workspace and telemetry are synchronized.'}
        </p>

        {/* User Identity Enclave Card */}
        <div className="auth-middle-user-badge">
          <div
            className="auth-middle-avatar"
            style={
              user.avatarUrl && user.avatarUrl.startsWith('linear-gradient')
                ? { background: user.avatarUrl }
                : { background: 'linear-gradient(135deg, #00f0ff, #6366f1)' }
            }
          >
            {user.avatarUrl && user.avatarUrl.startsWith('data:') ? (
              <img src={user.avatarUrl} alt={user.name} className="auth-avatar-photo" />
            ) : (
              <span>{user.avatarInitials || (user.name || 'User').slice(0, 2).toUpperCase()}</span>
            )}
          </div>
          <div className="auth-middle-user-info">
            <div className="auth-middle-user-name-row">
              <strong className="auth-middle-user-name">{user.name || 'Quantum Researcher'}</strong>
              <span className="auth-user-tier-tag">{(user.tier || 'pro').toUpperCase()} TIER</span>
            </div>
            <span className="auth-middle-user-email">{user.email}</span>
            {user.title && <span className="auth-middle-user-role">{user.title}</span>}
          </div>
        </div>

        {/* Quantum Enclave Verification Checklist */}
        <div className="auth-middle-checklist">
          <div className="auth-check-item">
            <Icon name="check" size={12} />
            <span>{runtimeLabel(versions)} Ready</span>
          </div>
          <div className="auth-check-item">
            <Icon name="check" size={12} />
            <span>AES Cryptographic Sandbox</span>
          </div>
          <div className="auth-check-item">
            <Icon name="check" size={12} />
            <span>Cloud Synchronized</span>
          </div>
        </div>

        {/* Action Button */}
        <div className="auth-middle-action-row">
          <button
            type="button"
            className="auth-middle-proceed-btn"
            onClick={handleManualClose}
          >
            <span>{isNewUser ? 'Proceed to Quantum Calibration' : 'Open Quantum Studio'}</span>
            <Icon name="arrow" size={14} />
          </button>
        </div>

        {/* Smooth Countdown Progress Bar Line */}
        <div className="auth-middle-timer-track" aria-hidden="true">
          <div className="auth-middle-timer-fill" />
        </div>
      </div>
    </div>
  );
}
