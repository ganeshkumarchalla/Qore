import { useEffect, useRef, useState } from 'react';
import { Logo } from './Icons';
import { useIntroDialog } from './useIntroDialog';

interface WelcomeModalProps {
  isOpen: boolean;
  onClose: () => void;
}

/** A brief, automatic brand transition into the workspace. */
export function WelcomeModal({ isOpen, onClose }: WelcomeModalProps) {
  const [exiting, setExiting] = useState(false);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;
  const dialogRef = useIntroDialog(isOpen, onClose);

  useEffect(() => {
    if (!isOpen) return;
    setExiting(false);
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const exitTimer = window.setTimeout(() => setExiting(true), reducedMotion ? 80 : 1050);
    const closeTimer = window.setTimeout(() => onCloseRef.current(), reducedMotion ? 180 : 1500);
    return () => {
      window.clearTimeout(exitTimer);
      window.clearTimeout(closeTimer);
    };
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div
      ref={dialogRef}
      tabIndex={-1}
      className={`qore-entry-screen qore-icon-entry ${exiting ? 'entry-fade-out' : 'entry-fade-in'}`}
      role="dialog"
      aria-modal="true"
      aria-label="Opening QORE"
    >
      <div className="qore-icon-entry-halo" aria-hidden="true" />
      <div className="qore-icon-entry-mark" aria-hidden="true"><Logo /></div>
      <span className="sr-only" role="status">Opening QORE workspace</span>
    </div>
  );
}
