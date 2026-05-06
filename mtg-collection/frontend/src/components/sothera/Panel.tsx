import { makeStyles, mergeClasses, shorthands } from '@griffel/react';
import { sothera } from '../../theme/sothera';
import { CornerTicks } from './CornerTicks';

const useStyles = makeStyles({
  root: {
    backgroundColor: sothera.glassBg,
    ...shorthands.borderWidth('1px'),
    ...shorthands.borderStyle('solid'),
    ...shorthands.borderColor(sothera.glassBorder),
    borderRadius: '2px',
    padding: '22px',
    position: 'relative',
    backdropFilter: 'blur(14px)',
    boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.03)',
    transitionProperty: 'border-color, box-shadow',
    transitionDuration: '160ms',
  },
  glow: {
    boxShadow: `0 0 0 1px ${sothera.glassBorder}, 0 24px 70px -24px rgba(200,80,192,0.25), inset 0 1px 0 rgba(255,255,255,0.04)`,
  },
  tag: {
    position: 'absolute',
    top: '-1px',
    right: '16px',
    fontFamily: sothera.fontMono,
    fontSize: '9px',
    letterSpacing: '1.5px',
    textTransform: 'uppercase',
    padding: '2px 8px',
    ...shorthands.borderWidth('1px'),
    ...shorthands.borderStyle('solid'),
    borderTopWidth: '0',
    borderRadius: '0 0 2px 2px',
  },
});

interface PanelProps {
  children: React.ReactNode;
  corners?: boolean;
  glow?: boolean;
  tag?: string;
  accent?: string;
  className?: string;
  style?: React.CSSProperties;
}

export function Panel({ children, corners, glow, tag, accent, className, style }: PanelProps) {
  const styles = useStyles();
  const accentColor = accent || sothera.fgFaint;

  return (
    <div
      className={mergeClasses(styles.root, glow && styles.glow, className)}
      style={style}
    >
      {corners && <CornerTicks color={accent} />}
      {tag && (
        <span
          className={styles.tag}
          style={{ color: accentColor, borderColor: accentColor }}
        >
          {tag}
        </span>
      )}
      {children}
    </div>
  );
}
