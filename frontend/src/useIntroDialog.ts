import { useEffect, useRef } from 'react';

/** Keep keyboard navigation inside the introduction until it closes. */
export function useIntroDialog(isOpen: boolean, onDismiss: () => void) {
  const containerRef = useRef<HTMLDivElement>(null);
  const dismissRef = useRef(onDismiss);
  dismissRef.current = onDismiss;

  useEffect(() => {
    if (!isOpen) return;
    const container = containerRef.current;
    if (!container) return;
    const previousFocus = document.activeElement;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    container.focus();

    const handleKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        event.stopPropagation();
        dismissRef.current();
      } else if (event.key === 'Tab') {
        const buttons = Array.from(container.querySelectorAll<HTMLButtonElement>('button:not(:disabled)'));
        const first = buttons[0];
        const last = buttons[buttons.length - 1];
        if (!first) {
          event.preventDefault();
          container.focus();
        } else if (!container.contains(document.activeElement) || document.activeElement === container) {
          event.preventDefault();
          (event.shiftKey ? last : first).focus();
        } else if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }
      // App shortcuts must not run underneath a modal introduction.
      event.stopPropagation();
    };
    const keepFocus = (event: FocusEvent) => {
      if (event.target instanceof Node && !container.contains(event.target)) container.focus();
    };
    document.addEventListener('keydown', handleKey, true);
    document.addEventListener('focusin', keepFocus);
    return () => {
      document.removeEventListener('keydown', handleKey, true);
      document.removeEventListener('focusin', keepFocus);
      document.body.style.overflow = previousOverflow;
      if (previousFocus instanceof HTMLElement && previousFocus.isConnected) previousFocus.focus();
    };
  }, [isOpen]);

  return containerRef;
}
