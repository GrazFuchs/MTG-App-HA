import { useState, useRef, useEffect, useCallback } from 'react';
import { Input, makeStyles, tokens, Spinner } from '@fluentui/react-components';
import { api } from '../../api';

const useStyles = makeStyles({
  wrapper: { position: 'relative', width: '100%' },
  dropdown: {
    position: 'absolute',
    top: '100%',
    left: 0,
    right: 0,
    zIndex: 100,
    backgroundColor: tokens.colorNeutralBackground1,
    border: `1px solid ${tokens.colorNeutralStroke1}`,
    borderRadius: tokens.borderRadiusMedium,
    boxShadow: tokens.shadow8,
    maxHeight: '240px',
    overflowY: 'auto',
  },
  option: {
    padding: '8px 12px',
    cursor: 'pointer',
    ':hover': { backgroundColor: tokens.colorNeutralBackground1Hover },
  },
  optionActive: {
    padding: '8px 12px',
    cursor: 'pointer',
    backgroundColor: tokens.colorNeutralBackground1Selected,
  },
  spinner: { position: 'absolute', right: '8px', top: '8px' },
});

interface Props {
  value: string;
  onChange: (name: string) => void;
  onSelect: (name: string) => void;
}

export default function CardNameAutocomplete({ value, onChange, onSelect }: Props) {
  const styles = useStyles();
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const abortRef = useRef<AbortController | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);

  const fetchSuggestions = useCallback(async (query: string) => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setLoading(true);
    try {
      const result = await api.autocomplete(query);
      if (!controller.signal.aborted) {
        setSuggestions(result.data || []);
        setIsOpen(true);
        setActiveIndex(-1);
      }
    } catch (e) {
      if (!(e instanceof DOMException && e.name === 'AbortError')) {
        setSuggestions([]);
      }
    } finally {
      if (!controller.signal.aborted) setLoading(false);
    }
  }, []);

  const handleInputChange = (val: string) => {
    onChange(val);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (val.length >= 2) {
      debounceRef.current = setTimeout(() => fetchSuggestions(val), 300);
    } else {
      setSuggestions([]);
      setIsOpen(false);
    }
  };

  const handleSelect = (name: string) => {
    onChange(name);
    onSelect(name);
    setIsOpen(false);
    setSuggestions([]);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!isOpen || suggestions.length === 0) return;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveIndex(i => Math.min(i + 1, suggestions.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveIndex(i => Math.max(i - 1, 0));
    } else if (e.key === 'Enter' && activeIndex >= 0) {
      e.preventDefault();
      handleSelect(suggestions[activeIndex]);
    } else if (e.key === 'Escape') {
      setIsOpen(false);
    }
  };

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      abortRef.current?.abort();
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, []);

  return (
    <div ref={wrapperRef} className={styles.wrapper}>
      <Input
        placeholder="Card name..."
        value={value}
        onChange={(_, d) => handleInputChange(d.value)}
        onKeyDown={handleKeyDown}
        onFocus={() => { if (suggestions.length > 0) setIsOpen(true); }}
        style={{ width: '100%' }}
        aria-autocomplete="list"
        aria-expanded={isOpen}
      />
      {loading && <Spinner size="tiny" className={styles.spinner} />}
      {isOpen && suggestions.length > 0 && (
        <div className={styles.dropdown} role="listbox">
          {suggestions.map((name, i) => (
            <div
              key={name}
              className={i === activeIndex ? styles.optionActive : styles.option}
              role="option"
              aria-selected={i === activeIndex}
              onMouseDown={() => handleSelect(name)}
              onMouseEnter={() => setActiveIndex(i)}
            >
              {name}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
