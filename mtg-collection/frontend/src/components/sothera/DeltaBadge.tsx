import { makeStyles, mergeClasses, shorthands } from '@griffel/react';
import { sothera } from '../../theme/sothera';

const useStyles = makeStyles({
  root: {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
    flexWrap: 'wrap',
  },
  badge: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '4px',
    padding: '3px 8px',
    fontFamily: sothera.fontMono,
    fontSize: '11px',
    fontWeight: 600,
    letterSpacing: '0.5px',
    ...shorthands.borderWidth('1px'),
    ...shorthands.borderStyle('solid'),
  },
  sub: {
    fontFamily: sothera.fontMono,
    fontSize: '11px',
    color: sothera.fgMuted,
    letterSpacing: '0.5px',
  },
});

interface DeltaBadgeProps {
  value: string;
  sub?: string;
  positive?: boolean;
  className?: string;
}

export function DeltaBadge({ value, sub, positive = true, className }: DeltaBadgeProps) {
  const styles = useStyles();
  const color = positive ? sothera.positive : sothera.negative;
  const bg = positive ? sothera.positiveSoft : sothera.negativeSoft;
  const borderColor = positive
    ? 'oklch(0.78 0.17 150 / 0.30)'
    : 'oklch(0.70 0.20 25 / 0.30)';

  return (
    <div className={mergeClasses(styles.root, className)}>
      <span className={styles.badge} style={{ color, backgroundColor: bg, borderColor }}>
        {positive ? '▲' : '▼'} {value}
      </span>
      {sub && <span className={styles.sub}>{sub}</span>}
    </div>
  );
}
