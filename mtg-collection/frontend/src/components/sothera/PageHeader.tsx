import { makeStyles, mergeClasses } from '@griffel/react';
import { sothera } from '../../theme/sothera';

const useStyles = makeStyles({
  root: {
    display: 'flex',
    alignItems: 'flex-end',
    justifyContent: 'space-between',
    marginBottom: '26px',
    gap: '24px',
  },
  left: {
    minWidth: 0,
  },
  eyebrow: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    fontFamily: sothera.fontMono,
    fontSize: '10px',
    letterSpacing: '2.5px',
    textTransform: 'uppercase',
    marginBottom: '12px',
  },
  dash: {
    display: 'inline-block',
    width: '24px',
    height: '1px',
  },
  title: {
    fontFamily: sothera.fontDisplay,
    fontSize: '48px',
    fontWeight: 700,
    letterSpacing: '-1.5px',
    lineHeight: '0.95',
    color: sothera.fg,
    '@media (max-width: 768px)': {
      fontSize: '32px',
      letterSpacing: '-1px',
    },
  },
});

interface PageHeaderProps {
  eyebrow?: string;
  title: string;
  right?: React.ReactNode;
  accent?: string;
  className?: string;
}

export function PageHeader({ eyebrow, title, right, accent, className }: PageHeaderProps) {
  const styles = useStyles();
  const accentColor = accent || sothera.fgMuted;

  return (
    <div className={mergeClasses(styles.root, className)}>
      <div className={styles.left}>
        {eyebrow && (
          <div className={styles.eyebrow} style={{ color: accentColor }}>
            <span className={styles.dash} style={{ backgroundColor: accentColor }} />
            {eyebrow}
          </div>
        )}
        <div className={styles.title}>{title}</div>
      </div>
      {right}
    </div>
  );
}
