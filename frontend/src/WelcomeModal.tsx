import { useEffect, useRef, useState } from 'react';
import { useIntroDialog } from './useIntroDialog';

interface WelcomeModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const STATUS_STAGES = [
  'Initializing Quantum State Engine...',
  'Calibrating Bloch Coordinate Spheres...',
  'Binding Qiskit Aer & OpenQASM Kernel...',
  'Synchronizing Quantum Workspace...',
  'Welcome to QORE Studio • Workspace Ready',
];

export function WelcomeModal({ isOpen, onClose }: WelcomeModalProps) {
  const [exiting, setExiting] = useState(false);
  const [stageIndex, setStageIndex] = useState(0);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;
  const dialogRef = useIntroDialog(isOpen, onClose);

  useEffect(() => {
    if (!isOpen) return;
    setExiting(false);
    setStageIndex(0);

    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    // Min 5 seconds duration requested by user:
    const totalDuration = reducedMotion ? 400 : 5200;
    const fadeOutDelay = reducedMotion ? 250 : 4700;

    // Cycle status messages across the 5 seconds
    const intervalTime = Math.floor(fadeOutDelay / STATUS_STAGES.length);
    const interval = window.setInterval(() => {
      setStageIndex((prev) => Math.min(prev + 1, STATUS_STAGES.length - 1));
    }, intervalTime);

    const exitTimer = window.setTimeout(() => setExiting(true), fadeOutDelay);
    const closeTimer = window.setTimeout(() => onCloseRef.current(), totalDuration);

    return () => {
      window.clearInterval(interval);
      window.clearTimeout(exitTimer);
      window.clearTimeout(closeTimer);
    };
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div
      ref={dialogRef}
      tabIndex={-1}
      className={`qore-entry-screen classical-entry enhanced-quantum-entry ${exiting ? 'entry-fade-out' : 'entry-fade-in'}`}
      role="dialog"
      aria-modal="true"
      aria-label="Welcome to QORE Quantum Studio"
    >
      <div className="classical-entry-light" aria-hidden="true" />
      <div className="quantum-nebula-pulse" aria-hidden="true" />

      <div className="qore-entry-content">
        {/* Cool Multi-Orbital 3D Quantum Engine Logo */}
        <div className="classical-entry-logo enhanced-quantum-logo" aria-hidden="true">
          <div className="quantum-core-halo" />
          <div className="quantum-wave-ring ring-1" />
          <div className="quantum-wave-ring ring-2" />
          <div className="quantum-wave-ring ring-3" />

          {/* 3D-angled electron orbits with glowing orbiting nodes */}
          <div className="quantum-orbit-3d orbit-x">
            <span className="quantum-electron-node node-1" />
          </div>
          <div className="quantum-orbit-3d orbit-y">
            <span className="quantum-electron-node node-2" />
          </div>
          <div className="quantum-orbit-3d orbit-z">
            <span className="quantum-electron-node node-3" />
          </div>

          {/* Central Pulsing Quantum Energy Core */}
          <div className="classical-entry-symbol quantum-core-symbol">
            <svg viewBox="0 0 80 80" width="80" height="80" fill="none">
              <defs>
                <linearGradient id="qoreGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stopColor="#00f0ff" />
                  <stop offset="50%" stopColor="#818cf8" />
                  <stop offset="100%" stopColor="#c084fc" />
                </linearGradient>
                <radialGradient id="qoreCore">
                  <stop offset="0%" stopColor="#ffffff" />
                  <stop offset="35%" stopColor="#38bdf8" />
                  <stop offset="100%" stopColor="transparent" />
                </radialGradient>
              </defs>
              <circle cx="40" cy="40" r="28" stroke="url(#qoreGrad)" strokeWidth="1.2" strokeDasharray="3 4" opacity="0.6" />
              <circle cx="40" cy="40" r="20" stroke="#d6e9f8" strokeWidth="1.6" opacity="0.9" />
              <ellipse cx="40" cy="40" rx="13" ry="29" transform="rotate(45 40 40)" stroke="#38bdf8" strokeWidth="1.5" />
              <ellipse cx="40" cy="40" rx="13" ry="29" transform="rotate(-45 40 40)" stroke="#a855f7" strokeWidth="1.5" />
              <circle cx="40" cy="40" r="8" fill="url(#qoreCore)" />
              <circle cx="40" cy="40" r="3.5" fill="#ffffff" />
            </svg>
          </div>
        </div>

        <span className="classical-entry-brand">QORE · QUANTUM STUDIO</span>
        <h1 className="enhanced-quantum-title">Welcome to QORE</h1>
        <p className="enhanced-quantum-lead">A high-performance workspace for quantum circuits, simulation & research.</p>

        {/* 5-Second Quantum Loading Track */}
        <div className="classical-entry-progress enhanced-progress-5s" aria-hidden="true">
          <span className="progress-fill-5s" />
        </div>

        <div className="classical-entry-status-wrap" role="status" aria-live="polite">
          <span className="quantum-status-dot" />
          <span className="classical-entry-status">{STATUS_STAGES[stageIndex]}</span>
        </div>
        <div className="intro-actions">
          <button type="button" className="clean-button" onClick={onClose}>Continue</button>
        </div>
      </div>
    </div>
  );
}
