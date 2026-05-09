import { useEffect, useState } from 'react';
import { makeStyles } from '@griffel/react';
import { Button, Spinner } from '@fluentui/react-components';
import { api, DeckCompletenessResponse } from '../../api';
import { sothera } from '../../theme/sothera';
import { useAccent } from '../../main';
import { Panel, SectionHeader } from '../sothera';

const useStyles = makeStyles({
  progressBar: {
    height: '8px',
    backgroundColor: 'rgba(255,255,255,0.06)',
    borderRadius: '2px',
    overflow: 'hidden',
    marginTop: '10px',
    marginBottom: '14px',
  },
  progressFill: {
    height: '100%',
    borderRadius: '2px',
    transitionProperty: 'width',
    transitionDuration: '400ms',
  },
  missingRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '6px 0',
    fontSize: '12px',
    fontFamily: sothera.fontMono,
  },
  collapseTrigger: {
    cursor: 'pointer',
    fontFamily: sothera.fontMono,
    fontSize: '10px',
    letterSpacing: '1.5px',
    color: sothera.fgFaint,
    textTransform: 'uppercase',
    marginTop: '10px',
  },
});

interface Props {
  deckId: number;
}

export function DeckCompletenessSection({ deckId }: Props) {
  const styles = useStyles();
  const { accent } = useAccent();
  const [data, setData] = useState<DeckCompletenessResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(false);
  const [addingToWishlist, setAddingToWishlist] = useState(false);

  useEffect(() => {
    api.getDeckCompleteness(deckId)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [deckId]);

  if (loading) return <Spinner size="tiny" />;
  if (!data) return null;

  const handleAddAllToWishlist = async () => {
    setAddingToWishlist(true);
    try {
      for (const card of data.missing_cards) {
        await api.addToWishlist({
          card_name: card.name,
          quantity: card.quantity_needed,
          priority: 3,
        });
      }
    } catch {
      // Best effort
    }
    setAddingToWishlist(false);
  };

  return (
    <div style={{ marginBottom: 26 }}>
      <SectionHeader
        num=""
        title="Deck Completeness"
        right={`${data.owned_unique} / ${data.total_unique_cards}`}
        accent={accent.oklch}
      />
      <Panel>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 12 }}>
          <span style={{ fontFamily: sothera.fontDisplay, fontSize: 24, fontWeight: 700, color: accent.oklch }}>
            {data.completeness_pct}%
          </span>
          <span style={{ fontFamily: sothera.fontMono, fontSize: 11, color: sothera.fgMuted, letterSpacing: 1 }}>
            OWNED: {data.owned_unique} / {data.total_unique_cards} CARDS
          </span>
        </div>

        <div className={styles.progressBar}>
          <div
            className={styles.progressFill}
            style={{ width: `${data.completeness_pct}%`, backgroundColor: accent.oklch }}
          />
        </div>

        {data.missing_cards.length > 0 && (
          <>
            <div style={{ fontFamily: sothera.fontMono, fontSize: 11, color: sothera.fgMuted, marginBottom: 10 }}>
              Missing {data.missing_cards.length} cards · acquisition cost €{data.total_acquisition_cost_eur.toFixed(2)}
            </div>

            <div
              className={styles.collapseTrigger}
              onClick={() => setExpanded(!expanded)}
            >
              {expanded ? '▾' : '▸'} MOST EXPENSIVE MISSING
            </div>

            {expanded && (
              <div style={{ marginTop: 8 }}>
                {data.most_expensive_missing.map((card) => (
                  <div key={card.name} className={styles.missingRow}>
                    <span style={{ color: sothera.fg }}>{card.name}</span>
                    <span style={{ color: accent.oklch }}>
                      {card.current_market_price_eur > 0 ? `€${card.current_market_price_eur.toFixed(2)}` : '—'}
                    </span>
                  </div>
                ))}

                <Button
                  appearance="subtle"
                  size="small"
                  disabled={addingToWishlist}
                  onClick={handleAddAllToWishlist}
                  style={{ marginTop: 12, color: sothera.fgMuted }}
                >
                  {addingToWishlist ? 'Adding...' : 'Add all missing to wishlist'}
                </Button>
              </div>
            )}
          </>
        )}
      </Panel>
    </div>
  );
}
