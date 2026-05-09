import { makeStyles, shorthands } from '@griffel/react';
import { Dialog, DialogSurface, DialogBody, DialogTitle, DialogContent } from '@fluentui/react-components';
import { DeckCombo } from '../../api';
import { sothera } from '../../theme/sothera';
import { useAccent } from '../../main';

const useStyles = makeStyles({
  overlay: {
    backgroundColor: 'rgba(4,4,10,0.85)',
  },
  surface: {
    maxWidth: '560px',
    backgroundColor: sothera.glassBg,
    border: `1px solid ${sothera.glassBorder}`,
    color: sothera.fg,
  },
  section: {
    marginBottom: '14px',
  },
  sectionLabel: {
    fontFamily: sothera.fontMono,
    fontSize: '9px',
    letterSpacing: '2px',
    color: sothera.fgFaint,
    textTransform: 'uppercase',
    marginBottom: '6px',
  },
  cardChip: {
    display: 'inline-block',
    padding: '3px 8px',
    marginRight: '6px',
    marginBottom: '4px',
    fontSize: '11px',
    fontFamily: sothera.fontMono,
    backgroundColor: 'rgba(255,255,255,0.04)',
    border: `1px solid ${sothera.glassBorder}`,
    borderRadius: '2px',
  },
  missingChip: {
    backgroundColor: 'rgba(255, 80, 80, 0.1)',
    ...shorthands.borderColor('rgba(255, 80, 80, 0.3)'),
    color: '#ff6b6b',
  },
  resultItem: {
    padding: '4px 0',
    fontSize: '12px',
    color: sothera.fgMuted,
  },
  prose: {
    fontSize: '12px',
    lineHeight: 1.6,
    color: sothera.fgMuted,
    whiteSpace: 'pre-wrap',
  },
});

interface Props {
  combo: DeckCombo;
  open: boolean;
  onClose: () => void;
}

export function ComboDetailDialog({ combo, open, onClose }: Props) {
  const styles = useStyles();
  const { accent } = useAccent();

  return (
    <Dialog open={open} onOpenChange={(_, d) => { if (!d.open) onClose(); }}>
      <DialogSurface className={styles.surface}>
        <DialogBody>
          <DialogTitle style={{ fontFamily: sothera.fontDisplay, color: sothera.fg }}>
            {combo.name}
            {combo.is_partial && (
              <span style={{ marginLeft: 8, fontSize: 11, color: '#ff6b6b', fontFamily: sothera.fontMono }}>
                PARTIAL
              </span>
            )}
          </DialogTitle>
          <DialogContent>
            {combo.color_identity && (
              <div style={{ fontFamily: sothera.fontMono, fontSize: 10, color: accent.oklch, letterSpacing: 1.5, marginBottom: 14 }}>
                {combo.color_identity}
              </div>
            )}

            <div className={styles.section}>
              <div className={styles.sectionLabel}>CARDS INVOLVED</div>
              {combo.cards.map((card) => (
                <span
                  key={card}
                  className={`${styles.cardChip} ${combo.missing_cards.includes(card) ? styles.missingChip : ''}`}
                >
                  {card}
                </span>
              ))}
            </div>

            {combo.missing_cards.length > 0 && (
              <div className={styles.section}>
                <div className={styles.sectionLabel}>MISSING CARDS</div>
                {combo.missing_cards.map((card) => (
                  <span key={card} className={`${styles.cardChip} ${styles.missingChip}`}>
                    {card}
                  </span>
                ))}
              </div>
            )}

            {combo.result.length > 0 && (
              <div className={styles.section}>
                <div className={styles.sectionLabel}>RESULT</div>
                {combo.result.map((r, i) => (
                  <div key={i} className={styles.resultItem}>• {r}</div>
                ))}
              </div>
            )}

            {combo.prerequisites && (
              <div className={styles.section}>
                <div className={styles.sectionLabel}>PREREQUISITES</div>
                <div className={styles.prose}>{combo.prerequisites}</div>
              </div>
            )}

            {combo.steps && (
              <div className={styles.section}>
                <div className={styles.sectionLabel}>STEPS</div>
                <div className={styles.prose}>{combo.steps}</div>
              </div>
            )}

            {combo.combo_id && (
              <a
                href={`https://commanderspellbook.com/combo/${combo.combo_id}`}
                target="_blank"
                rel="noopener noreferrer"
                style={{ fontSize: 11, fontFamily: sothera.fontMono, color: accent.oklch }}
              >
                View on Commander Spellbook ↗
              </a>
            )}
          </DialogContent>
        </DialogBody>
      </DialogSurface>
    </Dialog>
  );
}
