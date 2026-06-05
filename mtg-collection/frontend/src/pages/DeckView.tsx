import { useMemo, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { makeStyles, shorthands } from '@griffel/react';
import { Spinner, Button, Tooltip } from '@fluentui/react-components';
import { api, DeckDetail, DeckCardEntry } from '../api';
import { ManaCost, ManaSymbol } from '../components/ManaSymbol';
import { CardHoverPreview } from '../components/CardHoverPreview';
import { UserBracketBadge } from '../components/deck/UserBracketBadge';
import { GameplanBox } from '../components/deck/GameplanBox';
import { AIAssessmentBox } from '../components/deck/AIAssessmentBox';
import { DeckCombosSection } from '../components/deck/DeckCombosSection';
import { DeckCompletenessSection } from '../components/deck/DeckCompletenessSection';
import { sothera } from '../theme/sothera';
import { useAccent } from '../main';
import { Panel, SectionHeader, CornerTicks } from '../components/sothera';

const COLOR_MAP: Record<string, string> = {
  W: '#F9FAF4', U: '#0E68AB', B: '#150B00', R: '#D3202A', G: '#00733E',
};

const SIDEBOARD_CATEGORIES = new Set([
  'Sideboard', 'Maybeboard', 'Considering', 'Slot In', 'Slot Out',
]);

function scryfallUrl(card: { set_code: string; collector_number: string; name: string }) {
  if (card.set_code && card.collector_number) {
    return `https://scryfall.com/card/${card.set_code.toLowerCase()}/${card.collector_number}`;
  }
  return `https://scryfall.com/search?q=!"${encodeURIComponent(card.name)}"`;
}

const useStyles = makeStyles({
  page: { maxWidth: '1200px' },
  backLink: {
    cursor: 'pointer',
    fontFamily: sothera.fontMono,
    fontSize: '11px',
    letterSpacing: '2px',
    color: sothera.fgFaint,
    textTransform: 'uppercase',
    marginBottom: '14px',
  },
  hero: {
    position: 'relative',
    height: '280px',
    overflow: 'hidden',
    marginBottom: '22px',
    backgroundColor: sothera.glassBg,
    ...shorthands.borderWidth('1px'),
    ...shorthands.borderStyle('solid'),
    ...shorthands.borderColor(sothera.glassBorder),
  },
  heroImg: {
    position: 'absolute',
    inset: '0',
    width: '100%',
    height: '100%',
    objectFit: 'cover',
    filter: 'saturate(0.8) contrast(1.08)',
  },
  heroOverlay: {
    position: 'absolute',
    inset: '0',
    background: 'linear-gradient(180deg, rgba(4,4,10,0.3) 0%, rgba(4,4,10,0.65) 50%, rgba(4,4,10,0.98) 100%)',
  },
  heroScanline: {
    position: 'absolute',
    inset: '0',
    pointerEvents: 'none',
    backgroundImage: 'repeating-linear-gradient(180deg, transparent 0, transparent 3px, rgba(255,255,255,0.015) 3px, rgba(255,255,255,0.015) 4px)',
  },
  heroContent: {
    position: 'absolute',
    inset: '0',
    padding: '32px 36px',
    display: 'flex',
    flexDirection: 'column',
    justifyContent: 'flex-end',
  },
  heroTitle: {
    fontFamily: sothera.fontDisplay,
    fontSize: '48px',
    fontWeight: 700,
    letterSpacing: '-1.6px',
    lineHeight: 1,
    color: sothera.fg,
    '@media (max-width: 768px)': {
      fontSize: '28px',
    },
  },
  heroMeta: {
    display: 'flex',
    gap: '16px',
    marginTop: '14px',
    alignItems: 'center',
    flexWrap: 'wrap',
  },
  chartGrid: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr 1fr',
    gap: '14px',
    marginBottom: '26px',
    '@media (max-width: 768px)': {
      gridTemplateColumns: '1fr',
    },
  },
  chartLabel: {
    fontFamily: sothera.fontMono,
    fontSize: '10px',
    letterSpacing: '2px',
    color: sothera.fgFaint,
    textTransform: 'uppercase',
  },
  cardRow: {
    display: 'grid',
    gridTemplateColumns: '50px 2fr 80px 1.6fr 80px',
    padding: '12px 0',
    fontSize: '13px',
    alignItems: 'center',
    '@media (max-width: 768px)': {
      gridTemplateColumns: '40px 1fr 60px',
    },
  },
  cardLink: {
    color: sothera.fg,
    textDecoration: 'none',
    fontWeight: 500,
    ':hover': {
      textDecoration: 'underline',
    },
  },
  sideboardSection: {
    marginTop: '32px',
    opacity: 0.7,
  },
});

export default function DeckView() {
  const styles = useStyles();
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { accent } = useAccent();
  const queryClient = useQueryClient();

  const { data: deck, isLoading: loading, error } = useQuery<DeckDetail>({
    queryKey: ['deck', Number(id)],
    queryFn: () => api.getDeck(Number(id)),
    enabled: !!id,
    staleTime: 5 * 60_000,
  });

  const errorMsg = error ? (error as Error).message : null;

  const setDeck = (updated: DeckDetail) => {
    queryClient.setQueryData(['deck', Number(id)], updated);
  };

  const { mainCards, sideboardCards, commander, colorIdentity, totalValue, extraCategories } = useMemo(() => {
    if (!deck) return { mainCards: new Map<string, DeckCardEntry[]>(), sideboardCards: new Map<string, DeckCardEntry[]>(), commander: null, colorIdentity: [] as string[], totalValue: 0, extraCategories: new Map<number, string[]>() };
    const main = new Map<string, DeckCardEntry[]>();
    const side = new Map<string, DeckCardEntry[]>();
    const extras = new Map<number, string[]>(); // card_id -> additional categories
    let cmd: DeckCardEntry | null = null;
    const colors = new Set<string>();
    let value = 0;

    for (const entry of deck.cards) {
      if (entry.is_commander) cmd = entry;
      const rawCat = entry.category || 'Other';
      const categories = rawCat.split(',').map(c => c.trim()).filter(Boolean);
      const primaryCat = categories[0] || 'Other';
      if (categories.length > 1) {
        extras.set(entry.card.id, categories.slice(1));
      }
      (entry.card.color_identity || []).forEach(c => colors.add(c));
      const price = parseFloat(entry.card.price_eur) || 0;
      value += price * entry.quantity;

      if (SIDEBOARD_CATEGORIES.has(primaryCat)) {
        if (!side.has(primaryCat)) side.set(primaryCat, []);
        side.get(primaryCat)!.push(entry);
      } else {
        if (!main.has(primaryCat)) main.set(primaryCat, []);
        main.get(primaryCat)!.push(entry);
      }
    }
    return {
      mainCards: main,
      sideboardCards: side,
      commander: cmd,
      colorIdentity: Array.from(colors),
      totalValue: value,
      extraCategories: extras,
    };
  }, [deck]);

  if (loading) return <Spinner label="Loading deck..." />;
  if (!id) return <div style={{ fontFamily: sothera.fontMono, color: sothera.fgMuted }}>No deck ID provided.</div>;
  if (errorMsg) return <div style={{ fontFamily: sothera.fontMono, color: sothera.fgMuted }}>Error: {errorMsg}</div>;
  if (!deck) return <div style={{ fontFamily: sothera.fontMono, color: sothera.fgMuted }}>Deck not found.</div>;

  const manaCurve = (() => {
    const cmc: Record<number, number> = {};
    for (const c of deck.cards) {
      if (SIDEBOARD_CATEGORIES.has(c.category || '')) continue;
      if (c.card.type_line.includes('Land')) continue;
      const bucket = Math.min(Math.floor(c.card.cmc), 7);
      cmc[bucket] = (cmc[bucket] || 0) + c.quantity;
    }
    return Array.from({ length: 8 }, (_, i) => ({ label: i === 7 ? '7+' : String(i), count: cmc[i] || 0 }));
  })();
  const curveMax = Math.max(...manaCurve.map(b => b.count), 1);

  const colorPips = (() => {
    const pips: Record<string, number> = { W: 0, U: 0, B: 0, R: 0, G: 0 };
    for (const c of deck.cards) {
      if (SIDEBOARD_CATEGORIES.has(c.category || '')) continue;
      for (const ch of (c.card.mana_cost || '')) {
        if (ch in pips) pips[ch] += c.quantity;
      }
    }
    return Object.entries(pips).filter(([, v]) => v > 0).map(([color, count]) => ({ color, count }));
  })();
  const pipMax = Math.max(...colorPips.map(p => p.count), 1);

  const mainCount = deck.cards
    .filter(e => !SIDEBOARD_CATEGORIES.has(e.category || ''))
    .reduce((s, e) => s + e.quantity, 0);

  return (
    <div className={styles.page}>
      <div className={styles.backLink} onClick={() => navigate('/decks')}>← ALL DECKS</div>

      {/* Hero banner */}
      <div className={styles.hero}>
        {commander?.card.image_art_crop && (
          <>
            <img src={commander.card.image_art_crop} alt={deck.name} className={styles.heroImg} />
            <div className={styles.heroOverlay} />
            <div style={{ position: 'absolute', inset: 0, background: accent.soft, mixBlendMode: 'color', opacity: 0.4 }} />
            <div className={styles.heroScanline} />
          </>
        )}
        <CornerTicks color={accent.oklch} />
        <div className={styles.heroContent}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontFamily: sothera.fontMono, fontSize: 10, letterSpacing: 2.5, color: accent.oklch, textTransform: 'uppercase', marginBottom: 12 }}>
            <span style={{ display: 'inline-block', width: 24, height: 1, background: accent.oklch }} />
            DOSSIER · {deck.format} · BRACKET {deck.bracket || '—'}
          </div>
          <div className={styles.heroTitle}>{deck.name}</div>
          <div className={styles.heroMeta}>
            {(commander?.card.mana_cost ? [commander.card.mana_cost] : colorIdentity).length > 0 && (
              <div style={{ display: 'flex', gap: 4 }}>
                {commander?.card.mana_cost ? (
                  <ManaCost cost={commander.card.mana_cost} size={22} />
                ) : (
                  colorIdentity.map(c => <ManaSymbol key={c} symbol={c} size={22} />)
                )}
              </div>
            )}
            <span style={{ fontFamily: sothera.fontMono, fontSize: 12, color: sothera.fgMuted, letterSpacing: 1 }}>· {mainCount} CARDS ·</span>
            <span style={{ fontFamily: sothera.fontDisplay, fontSize: 20, fontWeight: 600, color: accent.oklch, letterSpacing: -0.5 }}>€{totalValue.toFixed(2)}</span>
            {deck.archidekt_id && (
              <a href={`https://archidekt.com/decks/${deck.archidekt_id}`} target="_blank" rel="noopener noreferrer">
                <Button appearance="subtle" size="small" style={{ color: sothera.fgFaint }}>Archidekt ↗</Button>
              </a>
            )}
            {deck.commander_name && (
              <a
                href={`https://edhrec.com/commanders/${deck.commander_name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '')}`}
                target="_blank"
                rel="noopener noreferrer"
              >
                <Button appearance="subtle" size="small" style={{ color: sothera.fgFaint }}>EDHREC ↗</Button>
              </a>
            )}
          </div>
        </div>
      </div>

      {/* Bracket & Gameplan */}
      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginBottom: 16 }}>
        <UserBracketBadge deck={deck} onUpdate={setDeck} />
      </div>
      <GameplanBox deck={deck} onUpdate={setDeck} />
      <AIAssessmentBox deck={deck} />

      {/* Combos & Completeness */}
      <DeckCombosSection deckId={deck.id} />
      <DeckCompletenessSection deckId={deck.id} />

      {/* Charts row */}
      <div className={styles.chartGrid}>
        <Panel>
          <div className={styles.chartLabel}>MANA CURVE</div>
          <svg width="100%" height="100" viewBox="0 0 240 100" style={{ marginTop: 14 }}>
            {manaCurve.map((b, i) => {
              const barH = curveMax > 0 ? (b.count / curveMax) * 75 : 0;
              const x = i * 30 + 4;
              return (
                <g key={i}>
                  <rect x={x} y={90 - barH} width={22} height={barH} fill={accent.oklch} opacity={0.75} rx={1} />
                  <text x={x + 11} y={98} textAnchor="middle" fontSize="9" fill={sothera.fgFaint} fontFamily="JetBrains Mono">{b.label}</text>
                  {b.count > 0 && <text x={x + 11} y={90 - barH - 3} textAnchor="middle" fontSize="8" fill={sothera.fgMuted} fontFamily="JetBrains Mono">{b.count}</text>}
                </g>
              );
            })}
          </svg>
        </Panel>
        <Panel>
          <div className={styles.chartLabel}>COLOR PIPS</div>
          <div style={{ display: 'flex', gap: 10, alignItems: 'flex-end', height: 100, marginTop: 14 }}>
            {colorPips.map(p => {
              const barH = (p.count / pipMax) * 75;
              return (
                <div key={p.color} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4, flex: 1 }}>
                  <span style={{ fontFamily: sothera.fontMono, fontSize: 9, color: sothera.fgMuted }}>{p.count}</span>
                  <div style={{ width: '100%', height: barH, background: COLOR_MAP[p.color] || '#888', opacity: 0.8, border: p.color === 'W' ? `1px solid ${sothera.glassBorder}` : 'none' }} />
                  <img src={`https://svgs.scryfall.io/card-symbols/${p.color}.svg`} width={16} height={16} alt={p.color} />
                </div>
              );
            })}
          </div>
        </Panel>
        <Panel>
          <div className={styles.chartLabel}>COMPOSITION</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 14 }}>
            {(() => {
              const comp: Record<string, number> = {};
              for (const e of deck.cards) {
                if (SIDEBOARD_CATEGORIES.has(e.category || '')) continue;
                const t = e.card.type_line;
                const cat = t.includes('Land') ? 'Lands' : t.includes('Creature') ? 'Creatures' : t.includes('Artifact') ? 'Artifacts' : t.includes('Enchantment') ? 'Enchantments' : 'Inst/Sorc';
                comp[cat] = (comp[cat] || 0) + e.quantity;
              }
              return Object.entries(comp).sort(([, a], [, b]) => b - a).map(([label, n]) => (
                <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <div style={{ width: n * 2.4, height: 6, background: accent.oklch, opacity: 0.75 }} />
                  <div style={{ flex: 1, fontFamily: sothera.fontMono, fontSize: 10, color: sothera.fgMuted, letterSpacing: 1, textTransform: 'uppercase' }}>{label}</div>
                  <div style={{ fontFamily: sothera.fontDisplay, fontSize: 13, fontWeight: 600, color: sothera.fg, fontFeatureSettings: '"tnum"' }}>{n}</div>
                </div>
              ));
            })()}
          </div>
        </Panel>
      </div>

      {/* Card lists */}
      {Array.from(mainCards.entries()).map(([cat, cards], idx) => (
        <div key={cat} style={{ marginBottom: 26 }}>
          <SectionHeader num={String(idx + 1).padStart(2, '0')} title={cat} right={`${cards.reduce((s: number, c: DeckCardEntry) => s + c.quantity, 0)} ENTRIES`} accent={accent.oklch} />
          <Panel>
            {cards.map((entry, i) => {
              const extras = extraCategories.get(entry.card.id);
              return (
              <CardHoverPreview key={i} card={entry.card}>
                <div className={styles.cardRow} style={{ borderBottom: i < cards.length - 1 ? `1px solid ${sothera.rowBorder}` : 'none' }}>
                  <div style={{ fontFamily: sothera.fontMono, fontSize: 11, letterSpacing: 1, color: sothera.fgFaint }}>×{entry.quantity}</div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <a
                      href={scryfallUrl(entry.card)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className={styles.cardLink}
                      onClick={(e) => e.stopPropagation()}
                    >
                      {entry.card.name}
                      {entry.is_commander && ' ⭐'}
                    </a>
                    {extras && (
                      <Tooltip content={extras.join(', ')} relationship="description">
                        <span style={{ fontSize: 9, fontFamily: sothera.fontMono, padding: '1px 5px', letterSpacing: 1, border: `1px solid ${sothera.glassBorder}`, color: sothera.fgFaint, cursor: 'default' }}>+{extras.length}</span>
                      </Tooltip>
                    )}
                  </div>
                  <div><ManaCost cost={entry.card.mana_cost} size={14} /></div>
                  <div style={{ fontFamily: sothera.fontMono, fontSize: 11, color: sothera.fgMuted, letterSpacing: 0.5 }}>{entry.card.type_line}</div>
                  <div style={{ textAlign: 'right', fontFamily: sothera.fontDisplay, fontWeight: 600, fontFeatureSettings: '"tnum"', color: sothera.fg }}>
                    {entry.card.price_eur ? `€${entry.card.price_eur}` : ''}
                  </div>
                </div>
              </CardHoverPreview>
              );
            })}
          </Panel>
        </div>
      ))}

      {sideboardCards.size > 0 && (
        <div className={styles.sideboardSection}>
          {Array.from(sideboardCards.entries()).map(([cat, cards], idx) => (
            <div key={cat} style={{ marginBottom: 26 }}>
              <SectionHeader num={String(mainCards.size + idx + 1).padStart(2, '0')} title={cat} right={`${cards.reduce((s: number, c: DeckCardEntry) => s + c.quantity, 0)} ENTRIES`} accent={accent.oklch} />
              <Panel>
                {cards.map((entry, i) => (
                  <CardHoverPreview key={i} card={entry.card}>
                    <div className={styles.cardRow} style={{ borderBottom: i < cards.length - 1 ? `1px solid ${sothera.rowBorder}` : 'none' }}>
                      <div style={{ fontFamily: sothera.fontMono, fontSize: 11, letterSpacing: 1, color: sothera.fgFaint }}>×{entry.quantity}</div>
                      <div>
                        <a href={scryfallUrl(entry.card)} target="_blank" rel="noopener noreferrer" className={styles.cardLink} onClick={(e) => e.stopPropagation()}>
                          {entry.card.name}
                        </a>
                      </div>
                      <div><ManaCost cost={entry.card.mana_cost} size={14} /></div>
                      <div style={{ fontFamily: sothera.fontMono, fontSize: 11, color: sothera.fgMuted }}>{entry.card.type_line}</div>
                      <div style={{ textAlign: 'right', fontFamily: sothera.fontDisplay, fontWeight: 600, color: sothera.fg }}>
                        {entry.card.price_eur ? `€${entry.card.price_eur}` : ''}
                      </div>
                    </div>
                  </CardHoverPreview>
                ))}
              </Panel>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
