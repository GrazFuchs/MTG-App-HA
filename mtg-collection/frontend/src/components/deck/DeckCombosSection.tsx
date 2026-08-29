import { useEffect, useState } from 'react';
import { makeStyles } from '@griffel/react';
import { Button, Spinner } from '@fluentui/react-components';
import { api, DeckCombo } from '../../api';
import { sothera } from '../../theme/sothera';
import { useAccent } from '../../main';
import { Panel, SectionHeader } from '../sothera';
import { ComboDetailDialog } from './ComboDetailDialog';

import { t } from '../../i18n';
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
  // Collapsed by default — combos are secondary detail.
  const [open, setOpen] = useState<boolean>(() => {
    try { return localStorage.getItem('deck.combosExpanded') === 'true'; } catch { return false; }
  });

  useEffect(() => {
    try { localStorage.setItem('deck.combosExpanded', String(open)); } catch { /* ignore */ }
  }, [open]);

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

  const [wishlistBusy, setWishlistBusy] = useState<number | null>(null);
  const [wishlisted, setWishlisted] = useState<Set<string>>(new Set());
  const [wishlistError, setWishlistError] = useState<string | null>(null);

  /**
   * Put the one missing card on the wishlist, tied to this deck.
   *
   * `deck_id` is the whole point: without it the entry is just another card to
   * buy, and the reason it is wanted — that it finishes a combo *here* — is
   * lost the moment you close the page.
   */
  const addMissingToWishlist = async (cardName: string, comboId: number) => {
    setWishlistBusy(comboId);
    setWishlistError(null);
    try {
      await api.addToWishlist({ card_name: cardName, deck_id: deckId, quantity: 1 });
      setWishlisted(prev => new Set(prev).add(cardName));
    } catch (err) {
      setWishlistError(err instanceof Error ? err.message : String(err));
    } finally {
      setWishlistBusy(null);
    }
  };

  const fullCombos = combos.filter(c => !c.is_partial);
  const partialCombos = combos.filter(c => c.is_partial);

  if (combos.length === 0 && !syncing) {
    return (
      <div style={{ marginBottom: 26 }}>
        <SectionHeader num="" title={t('decks.combos')} right="" accent={accent.oklch} />
        <Panel>
          <div style={{ fontFamily: sothera.fontMono, fontSize: 11, color: sothera.fgFaint, marginBottom: 10 }}>
            {t('decks.combos_empty')}
          </div>
          <Button
            appearance="subtle"
            size="small"
            onClick={handleSync}
            disabled={syncing}
            style={{ color: accent.oklch }}
          >
            {syncing ? t('combos.syncing') : t('decks.combos_detect')}
          </Button>
        </Panel>
      </div>
    );
  }

  return (
    <div style={{ marginBottom: 26 }}>
      <div onClick={() => setOpen(o => !o)} style={{ cursor: 'pointer' }}>
        <SectionHeader
          num=""
          title={`${open ? '▾' : '▸'} Combos`}
          right={t('combo.header_counts', { full: fullCombos.length, partial: partialCombos.length })}
          accent={accent.oklch}
        />
      </div>
      {open && (
      <Panel>
        <div className={styles.comboGrid}>
          {/* Full combos column */}
          <div>
            <div className={styles.columnTitle}>
              {t('combo.col_complete', { count: fullCombos.length })}
            </div>
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
                {t('combo.none_complete')}
              </div>
            )}
          </div>

          {/* Partial combos column */}
          <div>
            <div className={styles.columnTitle}>
              {t('combo.col_partial', { count: partialCombos.length })}
            </div>
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
                    {t('combo.missing', { cards: combo.missing_cards.join(', ') })}
                  </div>
                )}
                {/* The other direction of the combo bridge. The wishlist already
                    says "this card completes a combo in deck X" when you are
                    shopping; this is the same fact from where you actually
                    notice it — looking at the deck. One card only: with two or
                    more missing, which to buy is a decision, not a click. */}
                {combo.missing_cards.length === 1 && (
                  <Button
                    appearance="subtle"
                    size="small"
                    disabled={wishlistBusy === combo.id || wishlisted.has(combo.missing_cards[0])}
                    onClick={(e) => { e.stopPropagation(); addMissingToWishlist(combo.missing_cards[0], combo.id); }}
                    style={{ marginTop: 4, fontSize: 10 }}
                  >
                    {wishlisted.has(combo.missing_cards[0])
                      ? t('combo.on_wishlist')
                      : t('combo.add_missing')}
                  </Button>
                )}
              </div>
            ))}
            {partialCombos.length === 0 && (
              <div style={{ fontSize: 11, color: sothera.fgFaint, fontFamily: sothera.fontMono }}>
                {t('combo.none_partial')}
              </div>
            )}
          </div>
        </div>

        {/* A failed add must be visible: the button goes back to its normal
            state either way, so without this the click looks like it worked. */}
        {wishlistError && (
          <div style={{ marginTop: 10, fontSize: 11, color: sothera.negative, fontFamily: sothera.fontMono }}>
            {t('combo.wishlist_failed', { error: wishlistError })}
          </div>
        )}

        <div style={{ marginTop: 14 }}>
          <Button
            appearance="subtle"
            size="small"
            onClick={handleSync}
            disabled={syncing}
            style={{ color: sothera.fgFaint }}
          >
            {syncing ? t('combos.syncing') : t('decks.combos_refresh')}
          </Button>
        </div>
      </Panel>
      )}

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
