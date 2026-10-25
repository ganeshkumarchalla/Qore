import { useEffect, useState } from 'react';
import { Icon } from './Icons';
import type { AuthUser } from './AuthModal';

interface AuthSuccessBannerProps {
  user: AuthUser;
  isNewUser?: boolean;
  onDismiss: () => void;
}

export function AuthSuccessBanner({ user, isNewUser, onDismiss }: AuthSuccessBannerProps) {
  const [exiting, setExiting] = useState(false);

  useEffect(() => {
    // Show banner smoothly for 4.8 seconds, then glide out
    const dismissTimer = window.setTimeout(() => {
      setExiting(true);
      window.setTimeout(onDismiss, 800);
    }, 4500);

    return () => window.clearTimeout(dismissTimer);
  }, [onDismiss]);

  const handleManualClose = () => {
    setExiting(true);
    window.setTimeout(onDismiss, 800);
  };

  return (
    <div
      className={`auth-success-banner-wrap ${exiting ? 'banner-slide-up' : 'banner-slide-down'}`}
      role="status"
      aria-live="polite"
    >
      <div className="auth-success-banner">
        {/* Animated Glow Halos */}
        <div className="auth-success-halo" aria-hidden="true" />
        <div className="auth-success-pulse-ring" aria-hidden="true" />

        <div className="auth-success-icon-box">
          <div className="auth-success-check-icon">
            <Icon name="check" size={16} />
          </div>
        </div>

        <div className="auth-success-info">
          <div className="auth-success-title-row">
            <span className="auth-success-title">
              {isNewUser ? 'Account Created Successfully' : 'Authentication Successful'}
            </span>
            <span className="auth-success-pill">
              <span className="auth-live-dot" />
              <span>Workspace Connected</span>
            </span>
          </div>
          <p className="auth-success-user-text">
            Welcome, <strong className="auth-user-highlight">{user.name || user.email}</strong> • Your quantum circuits, states & evidence are securely synchronized.
          </p>
        </div>

        <button
          type="button"
          className="auth-success-close-btn"
          onClick={handleManualClose}
          aria-label="Dismiss notification"
          title="Dismiss notification"
        >
          <Icon name="close" size={13} />
        </button>

        {/* 4.5s Smooth Disappearing Countdown Line */}
        <div className="auth-success-progress-line" aria-hidden="true" />
      </div>
    </div>
  );
}
