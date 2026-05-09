import { useEffect, useState, Fragment } from 'react';
import { useSearchParams } from 'react-router-dom';
import { makeStyles, shorthands } from '@griffel/react';
import { Button, Select, Spinner } from '@fluentui/react-components';
import { api, DeckSummary, DeckCompareResponse } from '../api';
import { sothera } from '../theme/sothera';
import { useAccent } from '../main';
import { Panel, PageHeader, SectionHeader } from '../components/sothera';
import { ManaSymbol } from '../components/ManaSymbol';

const useStyles = makeStyles({
  controls: {
    display: 'flex',
    gap: '10px',
    alignItems: 'center',
    flexWrap: 'wrap',
    marginBottom: '20px',
  },
  matrix: {
    display: 'grid',
    gap: '1px',
    backgroundColor: sothera.glassBorder,
    ...shorthands.borderWidth('1px'),
    ...shorthands.borderStyle('solid'),
    ...shorthands.borderColor(sothera.glassBorder),
    marginBottom: '20px',
  },
  matrixCell: {
    padding: '10px 14px',
    backgroundColor: sothera.glassBg,
    fontFamily: sothera.fontMono,
    fontSize: '12px',
    textAlign: 'center',
  },
  matrixHeader: {
    fontWeight: 600,
    color: sothera.fgMuted,
    fontSize: '11px',
    letterSpacing: '0.5px',
  },
  cardList: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: '6px',
    marginTop: '8px',
  },
  cardChip: {
    display: 'inline-block',
    padding: '3px 8px',
    fontSize: '11px',
    fontFamily: sothera.fontMono,
    backgroundColor: 'rgba(255,255,255,0.04)',
    border: `1px solid ${sothera.glassBorder}`,
    borderRadius: '2px',
  },
  uniqueSection: {
    marginTop: '14px',
    marginBottom: '14px',
  },
  showMore: {
    cursor: 'pointer',
    fontFamily: sothera.fontMono,
    fontSize: '10px',
    letterSpacing: '1.5px',
    color: sothera.fgFaint,
    marginTop: '8px',
  },
});

export default function DeckCompare() {
  const styles = useStyles();
  const { accent } = useAccent();
  const [searchParams, setSearchParams] = useSearchParams();
  const [allDecks, setAllDecks] = useState<DeckSummary[]>([]);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [result, setResult] = useState<DeckCompareResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [expandedUnique, setExpandedUnique] = useState<Record<number, boolean>>({});

  // Load all decks for selection
  useEffect(() => {
    api.getDecks().then(setAllDecks);
  }, []);

  // Parse URL params
  useEffect(() => {
    const idsParam = searchParams.get('ids');
    if (idsParam) {
      const ids = idsParam.split(',').map(Number).filter(n => n > 0);
      setSelectedIds(ids);
    }
  }, [searchParams]);

  // Fetch comparison when we have 2+ IDs
  useEffect(() => {
    if (selectedIds.length >= 2) {
      setLoading(true);
      api.compareDecks(selectedIds)
        .then(setResult)
        .catch(() => setResult(null))
        .finally(() => setLoading(false));
    } else {
      setResult(null);
    }
  }, [selectedIds]);

  const addDeck = (id: number) => {
    if (id && !selectedIds.includes(id) && selectedIds.length < 4) {
      const newIds = [...selectedIds, id];
      setSelectedIds(newIds);
      setSearchParams({ ids: newIds.join(',') });
    }
  };

  const removeDeck = (id: number) => {
    const newIds = selectedIds.filter(x => x !== id);
    setSelectedIds(newIds);
    if (newIds.length > 0) {
      setSearchParams({ ids: newIds.join(',') });
    } else {
      setSearchParams({});
    }
  };

  const reset = () => {
    setSelectedIds([]);
    setSearchParams({});
    setResult(null);
  };

  const gridCols = result ? result.decks.length + 1 : 1;

  return (
    <div>
      <PageHeader eyebrow="⌬ ANALYSIS" title="Compare Decks" accent={accent.oklch} />

      {/* Selection controls */}
      <div className={styles.controls}>
        {selectedIds.map(id => {
          const deck = allDecks.find(d => d.id === id);
          return (
            <span key={id} style={{
              display: 'inline-flex', alignItems: 'center', gap: 6,
              padding: '4px 10px', fontSize: 11, fontFamily: sothera.fontMono,
              backgroundColor: accent.soft, border: `1px solid ${accent.oklch}`,
              borderRadius: 2, color: sothera.fg,
            }}>
              {deck?.name || `Deck #${id}`}
              <span style={{ cursor: 'pointer', color: sothera.fgFaint }} onClick={() => removeDeck(id)}>✕</span>
            </span>
          );
        })}
        {selectedIds.length < 4 && (
          <Select
            value=""
            onChange={(_, d) => { if (d.value) addDeck(Number(d.value)); }}
            style={{ minWidth: 180 }}
          >
            <option value="">+ Add deck</option>
            {allDecks
              .filter(d => !selectedIds.includes(d.id))
              .map(d => <option key={d.id} value={String(d.id)}>{d.name}</option>)}
          </Select>
        )}
        {selectedIds.length > 0 && (
          <Button appearance="subtle" size="small" onClick={reset} style={{ color: sothera.fgFaint }}>
            Reset
          </Button>
        )}
      </div>

      {loading && <Spinner label="Comparing decks..." />}

      {result && (
        <>
          {/* Color Identity */}
          <Panel>
            <div style={{ display: 'flex', gap: 16, alignItems: 'center', flexWrap: 'wrap' }}>
              <span style={{ fontFamily: sothera.fontMono, fontSize: 10, color: sothera.fgFaint, letterSpacing: 1.5 }}>
                UNION:
              </span>
              {result.color_identity_union.map(c => <ManaSymbol key={c} symbol={c} size={18} />)}
              <span style={{ fontFamily: sothera.fontMono, fontSize: 10, color: sothera.fgFaint, letterSpacing: 1.5, marginLeft: 16 }}>
                INTERSECTION:
              </span>
              {result.color_identity_intersection.length > 0
                ? result.color_identity_intersection.map(c => <ManaSymbol key={c} symbol={c} size={18} />)
                : <span style={{ fontFamily: sothera.fontMono, fontSize: 10, color: sothera.fgFaint }}>∅</span>
              }
            </div>
          </Panel>

          {/* Overlap Matrix */}
          <div style={{ marginTop: 20, marginBottom: 20 }}>
            <SectionHeader num="01" title="Overlap Matrix" right="" accent={accent.oklch} />
            <div
              className={styles.matrix}
              style={{ gridTemplateColumns: `repeat(${gridCols}, 1fr)` }}
            >
              {/* Header row */}
              <div className={`${styles.matrixCell} ${styles.matrixHeader}`} />
              {result.decks.map(d => (
                <div key={d.id} className={`${styles.matrixCell} ${styles.matrixHeader}`}>
                  {d.name}
                </div>
              ))}
              {/* Data rows */}
              {result.decks.map(rowDeck => (
                <Fragment key={`row-${rowDeck.id}`}>
                  <div className={`${styles.matrixCell} ${styles.matrixHeader}`}>
                    {rowDeck.name}
                  </div>
                  {result.decks.map(colDeck => {
                    if (rowDeck.id === colDeck.id) {
                      return <div key={`${rowDeck.id}-${colDeck.id}`} className={styles.matrixCell} style={{ color: sothera.fgFaint }}>—</div>;
                    }
                    const pair = result.pairwise_overlap.find(
                      p => (p.deck_a === rowDeck.id && p.deck_b === colDeck.id) ||
                           (p.deck_a === colDeck.id && p.deck_b === rowDeck.id)
                    );
                    return (
                      <div key={`${rowDeck.id}-${colDeck.id}`} className={styles.matrixCell} style={{ color: accent.oklch, fontWeight: 600 }}>
                        {pair?.overlap_count ?? 0} ∩
                      </div>
                    );
                  })}
                </Fragment>
              ))}
            </div>
          </div>

          {/* Common Cards */}
          <div style={{ marginBottom: 20 }}>
            <SectionHeader num="02" title="Common Cards" right={`${result.common_cards.length} SHARED`} accent={accent.oklch} />
            <Panel>
              <div className={styles.cardList}>
                {result.common_cards.map(c => (
                  <span key={c.name} className={styles.cardChip}>{c.name}</span>
                ))}
                {result.common_cards.length === 0 && (
                  <span style={{ fontSize: 11, color: sothera.fgFaint, fontFamily: sothera.fontMono }}>No cards in common</span>
                )}
              </div>
            </Panel>
          </div>

          {/* Unique to each deck */}
          <SectionHeader num="03" title="Unique Cards" right="" accent={accent.oklch} />
          {result.decks.map(deck => {
            const uniqueCards = result.unique_to[deck.id] || [];
            const isExpanded = expandedUnique[deck.id];
            const displayCards = isExpanded ? uniqueCards : uniqueCards.slice(0, 10);
            return (
              <div key={deck.id} className={styles.uniqueSection}>
                <Panel>
                  <div style={{ fontFamily: sothera.fontDisplay, fontSize: 13, fontWeight: 600, color: sothera.fg, marginBottom: 8 }}>
                    Unique to {deck.name} ({uniqueCards.length})
                  </div>
                  <div className={styles.cardList}>
                    {displayCards.map(c => (
                      <span key={c.name} className={styles.cardChip}>{c.name}</span>
                    ))}
                  </div>
                  {uniqueCards.length > 10 && (
                    <div
                      className={styles.showMore}
                      onClick={() => setExpandedUnique(prev => ({ ...prev, [deck.id]: !prev[deck.id] }))}
                    >
                      {isExpanded ? '▾ Show less' : `▸ Show all ${uniqueCards.length}`}
                    </div>
                  )}
                </Panel>
              </div>
            );
          })}
        </>
      )}

      {!loading && selectedIds.length < 2 && (
        <div style={{ fontFamily: sothera.fontMono, fontSize: 12, color: sothera.fgMuted, marginTop: 20 }}>
          Select at least 2 decks to compare.
        </div>
      )}
    </div>
  );
}
