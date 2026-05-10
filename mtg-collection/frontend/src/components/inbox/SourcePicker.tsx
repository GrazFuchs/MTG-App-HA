import { makeStyles } from '@griffel/react';
import { sothera } from '../../theme/sothera';
import { useAccent } from '../../main';

const SOURCES = ['cardmarket', 'whatnot', 'booster', 'trade', 'gift', 'shop', 'secret_lair', 'other'] as const;

const useStyles = makeStyles({
  root: {
    display: 'flex',
    gap: '6px',
    flexWrap: 'wrap',
  },
  pill: {
    padding: '4px 10px',
    fontSize: '10px',
    fontFamily: sothera.fontMono,
    letterSpacing: '1px',
    textTransform: 'uppercase',
    cursor: 'pointer',
    border: `1px solid ${sothera.glassBorder}`,
    borderRadius: '2px',
    background: 'transparent',
    color: sothera.fgMuted,
    transitionProperty: 'all',
    transitionDuration: '120ms',
    ':hover': {
      color: sothera.fg,
    },
  },
});

interface SourcePickerProps {
  value: string | null;
  onChange: (source: string) => void;
}

export default function SourcePicker({ value, onChange }: SourcePickerProps) {
  const styles = useStyles();
  const { accent } = useAccent();

  return (
    <div className={styles.root}>
      {SOURCES.map(s => (
        <button
          key={s}
          className={styles.pill}
          onClick={() => onChange(s)}
          style={
            value === s
              ? { backgroundColor: accent.soft, borderColor: accent.oklch, color: sothera.fg }
              : undefined
          }
        >
          {s}
        </button>
      ))}
    </div>
  );
}
