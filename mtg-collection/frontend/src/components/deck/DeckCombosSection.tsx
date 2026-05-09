import { useEffect, useState } from 'react';
import { makeStyles } from '@griffel/react';
import { Button, Spinner } from '@fluentui/react-components';
import { api, DeckCombo } from '../../api';
import { sothera } from '../../theme/sothera';
import { useAccent } from '../../main';
import { Panel, SectionHeader } from '../sothera';
import { ComboDetailDialog } from './ComboDetailDialog';

const useStyles = makeStyles({
  comboGrid: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: '16px',
    '@media (max-width: 768px)': {
      gridTemplateColumns: '1fr',
    },
  },
  columnTitle: {
    fontFamily: sothera.fontMono,
    fontSize: '10px',
    letterSpacing: '1.5px',
    color: sothera.fgFaint,
    textTransform: 'uppercase',
    marginBottom: '10px',
  },
  comboItem: {
    padding: '10px 12px',
    cursor: 'pointer',
    borderBottom: `1px solid ${sothera.rowBorder}`,
    transitionProperty: 'background-color',
    transitionDuration: '120ms',
    ':hover': {
      backgroundColor: 'rgba(255,255,255,0.03)',
    },
  },
  comboName: {
    fontSize: '13px',
    fontWeight: 500,
    color: sothera.fg,
    marginBottom: '4px',
  },
  comboMeta: {
    fontSize: '10px',
    fontFamily: sothera.fontMono,
    color: sothera.fgFaint,
    letterSpacing: '0.5px',
  },
  missingHint: {
    fontSize: '10px',
    fontFamily: sothera.fontMono,
    color: '#ff6b6b',
    marginTop: '3px',
  },
});

interface Props {
  deckId: number;
}

export function DeckCombosSection({ deckId }: Props) {
  const styles = useStyles();
  const { accent } = useAccent();
  const [combos, setCombos] = useState<DeckCombo[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [selectedCombo, setSelectedCombo] = useState<DeckCombo | null>(null);

  const loadCombos = () => {
    setLoading(true);
    api.getDeckCombos(deckId)
      .then(setCombos)
      .catch(() => setCombos([]))
      .finally(() => setLoading(false));
  };

  useEffect(loadCombos, [deckId]);

  const handleSync = async () => {
    setSyncing(true);
    try {
      await api.syncDeckCombos(deckId);
      loadCombos();
    } catch {
      // ignore
    }
    setSyncing(false);
  };

  if (loading) return <Spinner size="tiny" />;

  const fullCombos = combos.filter(c => !c.is_partial);
  const partialCombos = combos.filter(c => c.is_partial);

  if (combos.length === 0 && !syncing) {
    return (
      <div style={{ marginBottom: 26 }}>
        <SectionHeader num="" title="Combos" right="" accent={accent.oklch} />
        <Panel>
          <div style={{ fontFamily: sothera.fontMono, fontSize: 11, color: sothera.fgFaint, marginBottom: 10 }}>
            No combos cached yet.
          </div>
          <Button
            appearance="subtle"
            size="small"
            onClick={handleSync}
            disabled={syncing}
            style={{ color: accent.oklch }}
          >
            {syncing ? 'Syncing...' : 'Detect Combos from Spellbook'}
          </Button>
        </Panel>
      </div>
    );
  }

  return (
    <div style={{ marginBottom: 26 }}>
      <SectionHeader
        num=""
        title="Combos in this Deck"
        right={`${fullCombos.length} ACTIVE · ${partialCombos.length} PARTIAL`}
        accent={accent.oklch}
      />
      <Panel>
        <div className={styles.comboGrid}>
          {/* Full combos column */}
          <div>
            <div className={styles.columnTitle}>Active ({fullCombos.length})</div>
            {fullCombos.map(combo => (
              <div
                key={combo.id}
                className={styles.comboItem}
                onClick={() => setSelectedCombo(combo)}
              >
                <div className={styles.comboName}>▶ {combo.name}</div>
                <div className={styles.comboMeta}>
                  {combo.color_identity} · {combo.result.slice(0, 2).join(', ')}
                </div>
              </div>
            ))}
            {fullCombos.length === 0 && (
              <div style={{ fontSize: 11, color: sothera.fgFaint, fontFamily: sothera.fontMono }}>
                No full combos detected
              </div>
            )}
          </div>

          {/* Partial combos column */}
          <div>
            <div className={styles.columnTitle}>Partial ({partialCombos.length} — 1 card away)</div>
            {partialCombos.map(combo => (
              <div
                key={combo.id}
                className={styles.comboItem}
                onClick={() => setSelectedCombo(combo)}
              >
                <div className={styles.comboName}>▶ {combo.name}</div>
                <div className={styles.comboMeta}>
                  {combo.color_identity} · {combo.result.slice(0, 2).join(', ')}
                </div>
                {combo.missing_cards.length > 0 && (
                  <div className={styles.missingHint}>
                    + Add: {combo.missing_cards.join(', ')}
                  </div>
                )}
              </div>
            ))}
            {partialCombos.length === 0 && (
              <div style={{ fontSize: 11, color: sothera.fgFaint, fontFamily: sothera.fontMono }}>
                No partial combos detected
              </div>
            )}
          </div>
        </div>

        <div style={{ marginTop: 14 }}>
          <Button
            appearance="subtle"
            size="small"
            onClick={handleSync}
            disabled={syncing}
            style={{ color: sothera.fgFaint }}
          >
            {syncing ? 'Refreshing...' : 'Refresh from Spellbook'}
          </Button>
        </div>
      </Panel>

      {selectedCombo && (
        <ComboDetailDialog
          combo={selectedCombo}
          open={!!selectedCombo}
          onClose={() => setSelectedCombo(null)}
        />
      )}
    </div>
  );
}
