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

  useEffect(() => {
    if (isOpen) {
      setQuery('');
      setSelectedIndex(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [isOpen]);

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
      onClose();
    }
  };

  if (!isOpen) return null;

  return (
    <div
      className="command-palette-backdrop"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="command-palette-card" role="dialog" aria-modal="true">
        <div className="palette-input-wrap">
          <Icon name="search" size={16} />
          <input
            ref={inputRef}
            type="text"
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

        <div className="palette-list" role="listbox">
          {filtered.length === 0 ? (
            <div className="palette-empty">No matching commands</div>
          ) : (
            filtered.map((cmd, idx) => (
              <div
                key={cmd.id}
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
