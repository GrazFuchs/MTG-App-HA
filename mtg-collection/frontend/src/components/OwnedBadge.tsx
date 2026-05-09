import { makeStyles } from '@griffel/react';
import { sothera } from '../theme/sothera';

const useStyles = makeStyles({
  badge: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '4px',
    padding: '2px 7px',
    fontSize: '10px',
    fontFamily: sothera.fontMono,
    letterSpacing: '0.5px',
    borderRadius: '2px',
  },
  owned: {
    backgroundColor: 'rgba(0, 180, 80, 0.15)',
    color: sothera.positive,
    border: `1px solid rgba(0, 180, 80, 0.3)`,
  },
  foil: {
    backgroundColor: 'rgba(180, 130, 255, 0.15)',
    color: 'oklch(0.78 0.12 290)',
    border: `1px solid rgba(180, 130, 255, 0.3)`,
  },
  deckTooltip: {
    position: 'relative',
    cursor: 'help',
  },
});

interface OwnedBadgeProps {
  ownedQuantity: number;
  ownedFoilQuantity?: number;
  inDecks?: string[];
}

export function OwnedBadge({ ownedQuantity, ownedFoilQuantity = 0, inDecks = [] }: OwnedBadgeProps) {
  const styles = useStyles();

  if (ownedQuantity === 0 && ownedFoilQuantity === 0) return null;

  return (
    <span style={{ display: 'inline-flex', gap: 4, alignItems: 'center' }}>
      {ownedQuantity > 0 && (
        <span
          className={`${styles.badge} ${styles.owned}`}
          title={inDecks.length > 0 ? `Used in: ${inDecks.join(', ')}` : undefined}
        >
          ✓ Owned ({ownedQuantity}×)
        </span>
      )}
      {ownedFoilQuantity > 0 && (
        <span className={`${styles.badge} ${styles.foil}`}>
          ✦ Foil ({ownedFoilQuantity}×)
        </span>
      )}
    </span>
  );
}
