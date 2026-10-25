import { useEffect, useRef, useState } from 'react';

interface WelcomeModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function WelcomeModal({ isOpen, onClose }: WelcomeModalProps) {
  const [exiting, setExiting] = useState(false);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    if (!isOpen) return;
    setExiting(false);
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const exitTimer = window.setTimeout(() => setExiting(true), reducedMotion ? 180 : 1600);
    const closeTimer = window.setTimeout(() => onCloseRef.current(), reducedMotion ? 260 : 2100);
    return () => {
      window.clearTimeout(exitTimer);
      window.clearTimeout(closeTimer);
      document.body.style.overflow = previousOverflow;
    };
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div className={`qore-entry-screen classical-entry ${exiting ? 'entry-fade-out' : 'entry-fade-in'}`} role="status" aria-live="polite" aria-label="Welcome to qubit">
      <div className="classical-entry-light" aria-hidden="true" />
      <div className="qore-entry-content">
        <div className="classical-entry-logo" aria-hidden="true">
          <span className="classical-orbit orbit-one" />
          <span className="classical-orbit orbit-two" />
          <span className="classical-orbit orbit-three" />
          <span className="classical-entry-symbol"><svg viewBox="0 0 80 80" width="80" height="80" fill="none">
            <circle cx="40" cy="40" r="19" stroke="#d6e9f8" strokeWidth="1.7" />
            <ellipse cx="40" cy="40" rx="12" ry="29" transform="rotate(45 40 40)" stroke="#8bb7dc" strokeWidth="1.6" />
            <ellipse cx="40" cy="40" rx="12" ry="29" transform="rotate(-45 40 40)" stroke="#9dabc9" strokeWidth="1.6" />
            <circle cx="40" cy="40" r="4" fill="#f4f9ff" />
          </svg></span>
        </div>
        <span className="classical-entry-brand">QORE</span>
        <h1>Welcome to qubit</h1>
        <p>A clear start for your quantum ideas.</p>
        <div className="classical-entry-progress" aria-hidden="true"><span /></div>
        <span className="classical-entry-status">Opening your workspace</span>
      </div>
    </div>
  );
}
