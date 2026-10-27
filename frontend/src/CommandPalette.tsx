import { useEffect, useRef, useState } from 'react';
import { Icon, type IconName } from './Icons';

export type CommandItem = {
  id: string;
  title: string;
  category: string;
  icon: IconName;
  shortcut?: string;
  action: () => void;
};

export function CommandPalette({
  isOpen,
  onClose,
  commands,
}: {
  isOpen: boolean;
  onClose: () => void;
  commands: CommandItem[];
}) {
  const [query, setQuery] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const openerRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!isOpen) return;
    openerRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    setQuery('');
    setSelectedIndex(0);
    const timer = window.setTimeout(() => inputRef.current?.focus(), 50);
    return () => window.clearTimeout(timer);
  }, [isOpen]);

  const closeAndRestoreFocus = () => {
    const opener = openerRef.current;
    onClose();
    opener?.focus();
  };

  const filtered = commands.filter((cmd) => {
    const q = query.toLowerCase();
    return (
      cmd.title.toLowerCase().includes(q) ||
      cmd.category.toLowerCase().includes(q)
    );
  });

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex((idx) => (idx + 1) % (filtered.length || 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex((idx) => (idx - 1 + (filtered.length || 1)) % (filtered.length || 1));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      const chosen = filtered[selectedIndex];
      if (chosen) {
        onClose();
        chosen.action();
      }
    } else if (e.key === 'Escape') {
      e.preventDefault();
      closeAndRestoreFocus();
    } else if (e.key === 'Tab') {
      e.preventDefault();
      inputRef.current?.focus();
    }
  };

  if (!isOpen) return null;

  return (
    <div
      className="command-palette-backdrop"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) closeAndRestoreFocus();
      }}
    >
      <div className="command-palette-card" role="dialog" aria-modal="true" aria-label="Command Palette">
        <div className="palette-input-wrap">
          <Icon name="search" size={16} />
          <input
            ref={inputRef}
            type="text"
            role="combobox"
            aria-label="Search commands"
            aria-autocomplete="list"
            aria-expanded="true"
            aria-controls="qore-command-list"
            aria-activedescendant={filtered.length ? `qore-command-${filtered[selectedIndex]?.id ?? filtered[0].id}` : undefined}
            className="palette-input"
            placeholder="Type a command or search action (e.g. simulate, bloch, gate, settings)..."
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setSelectedIndex(0);
            }}
            onKeyDown={handleKeyDown}
          />
          <kbd className="palette-esc">ESC</kbd>
        </div>

        <div className="palette-list" role="listbox" id="qore-command-list">
          {filtered.length === 0 ? (
            <div className="palette-empty">No matching commands</div>
          ) : (
            filtered.map((cmd, idx) => (
              <div
                key={cmd.id}
                id={`qore-command-${cmd.id}`}
                role="option"
                aria-selected={idx === selectedIndex}
                className={`palette-item ${idx === selectedIndex ? 'selected' : ''}`}
                onClick={() => {
                  onClose();
                  cmd.action();
                }}
                onMouseEnter={() => setSelectedIndex(idx)}
              >
                <div className="palette-item-left">
                  <Icon name={cmd.icon} size={15} />
                  <span className="palette-item-title">{cmd.title}</span>
                  <span className="palette-category-badge">{cmd.category}</span>
                </div>
                {cmd.shortcut && <kbd className="palette-shortcut">{cmd.shortcut}</kbd>}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
