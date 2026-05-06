import { makeStyles, mergeClasses, shorthands } from '@griffel/react';
import { sothera } from '../../theme/sothera';

const useStyles = makeStyles({
  root: {
    display: 'flex',
    alignItems: 'center',
    gap: '14px',
    marginTop: '32px',
    marginBottom: '14px',
  },
  num: {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    minWidth: '32px',
    height: '22px',
    padding: '0 6px',
    ...shorthands.borderWidth('1px'),
    ...shorthands.borderStyle('solid'),
    fontFamily: sothera.fontMono,
    fontSize: '10px',
    letterSpacing: '1px',
    fontWeight: 600,
  },
  title: {
    fontFamily: sothera.fontDisplay,
    fontSize: '16px',
    fontWeight: 600,
    letterSpacing: '1px',
    color: sothera.fg,
    textTransform: 'uppercase',
  },
  divider: {
    flex: 1,
    height: '1px',
    backgroundColor: sothera.glassBorder,
  },
  right: {
    fontFamily: sothera.fontMono,
    fontSize: '10px',
    color: sothera.fgFaint,
    letterSpacing: '1.5px',
    textTransform: 'uppercase',
  },
});

interface SectionHeaderProps {
  num?: string;
  title: string;
  right?: string;
  accent?: string;
  className?: string;
}

export function SectionHeader({ num, title, right, accent, className }: SectionHeaderProps) {
  const styles = useStyles();
  const accentColor = accent || sothera.fgMuted;

  return (
    <div className={mergeClasses(styles.root, className)}>
      {num && (
        <span className={styles.num} style={{ color: accentColor, borderColor: accentColor }}>
          {num}
        </span>
      )}
      <span className={styles.title}>{title}</span>
      <div className={styles.divider} />
      {right && <span className={styles.right}>{right}</span>}
    </div>
  );
}
