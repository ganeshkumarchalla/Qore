import React, { useEffect, useState } from 'react';

interface WelcomeModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectCircuit?: (source: string, name: string) => void;
}

export function WelcomeModal({ isOpen, onClose }: WelcomeModalProps) {
  const [exiting, setExiting] = useState(false);

  useEffect(() => {
    if (!isOpen) return;
    setExiting(false);
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' || e.key === 'Enter' || e.key === ' ') {
        handleEnter();
      }
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [isOpen]);

  if (!isOpen) return null;

  const handleEnter = () => {
    setExiting(true);
    localStorage.setItem('qore_welcome_v2_dismissed', 'true');
    setTimeout(() => {
      setExiting(false);
      onClose();
    }, 450);
  };

  return (
    <div
      className={`qore-entry-screen ${exiting ? 'entry-fade-out' : 'entry-fade-in'}`}
      onClick={handleEnter}
      role="dialog"
      aria-modal="true"
      aria-label="Welcome to Qore"
    >
      {/* Dynamic Cosmic Gradient Auroras */}
      <div className="qore-aurora-blob aura-cyan" />
      <div className="qore-aurora-blob aura-purple" />
      <div className="qore-aurora-blob aura-magenta" />

      {/* Central Interactive Animation Box */}
      <div className="qore-entry-content" onClick={(e) => e.stopPropagation()}>
        {/* Quantum Orbital Energy Core */}
        <div className="qore-orbital-core">
          <div className="qore-orbit-ring ring-1" />
          <div className="qore-orbit-ring ring-2" />
          <div className="qore-orbit-ring ring-3" />
          <div className="qore-core-nucleus">
            <svg viewBox="0 0 64 64" width="76" height="76" fill="none" className="qore-core-svg">
              <defs>
                <linearGradient id="qoreGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stopColor="#00f0ff" />
                  <stop offset="50%" stopColor="#8b5cf6" />
                  <stop offset="100%" stopColor="#ec4899" />
                </linearGradient>
              </defs>
              <circle cx="32" cy="32" r="18" stroke="url(#qoreGrad)" strokeWidth="3" opacity="0.9" />
              <ellipse cx="32" cy="32" rx="9" ry="27" transform="rotate(40 32 32)" stroke="url(#qoreGrad)" strokeWidth="2" />
              <ellipse cx="32" cy="32" rx="9" ry="27" transform="rotate(-40 32 32)" stroke="#38bdf8" strokeWidth="2" opacity="0.8" />
              <circle cx="32" cy="32" r="5" fill="#00f0ff" className="qore-pulse-photon" />
            </svg>
          </div>
        </div>

        {/* ONLY FEATURING: "Welcome to Qore" */}
        <h1 className="qore-hero-gradient-text">Welcome to Qore</h1>

        {/* Minimal Classic Entry Pill */}
        <button
          type="button"
          className="qore-enter-studio-btn"
          onClick={handleEnter}
          autoFocus
          title="Press Enter or Click to Enter QORE"
        >
          <span>Enter</span>
          <span className="qore-btn-arrow">→</span>
        </button>
        <p className="qore-entry-hint">Press Enter, Space, or click Enter to open your workspace</p>
      </div>
    </div>
  );
}
