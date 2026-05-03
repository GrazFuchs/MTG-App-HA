import { useEffect, useMemo, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  makeStyles,
  tokens,
  Title2,
  Title3,
  Body1,
  Body2,
  Caption1,
  Spinner,
  Badge,
  Divider,
  Button,
} from '@fluentui/react-components';
import { api, DeckDetail, DeckCardEntry } from '../api';
import { ManaCost, ManaSymbol } from '../components/ManaSymbol';
import { CardHoverPreview } from '../components/CardHoverPreview';
import { UserBracketBadge } from '../components/deck/UserBracketBadge';
import { GameplanBox } from '../components/deck/GameplanBox';
import { AIAssessmentBox } from '../components/deck/AIAssessmentBox';

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
  headerRow: {
    display: 'flex',
    gap: '20px',
    alignItems: 'flex-start',
    marginBottom: '16px',
    flexWrap: 'wrap',
  },
  commanderImg: {
    width: '180px',
    borderRadius: '12px',
    flexShrink: 0,
  },
  headerInfo: {
    flex: 1,
    minWidth: '200px',
  },
  meta: {
    display: 'flex',
    gap: '8px',
    flexWrap: 'wrap',
    alignItems: 'center',
    marginTop: '8px',
  },
  categorySection: {
    marginTop: '20px',
  },
  table: {
    width: '100%',
    borderCollapse: 'collapse',
    marginTop: '8px',
    fontSize: '14px',
  },
  th: {
    textAlign: 'left',
    padding: '4px 8px',
    borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
    fontWeight: 600,
    fontSize: '12px',
    color: tokens.colorNeutralForeground3,
  },
  td: {
    padding: '4px 8px',
    borderBottom: `1px solid ${tokens.colorNeutralStroke3}`,
    verticalAlign: 'middle',
  },
  cardLink: {
    color: tokens.colorNeutralForeground1,
    textDecoration: 'none',
    '&:hover': {
      textDecoration: 'underline',
      color: tokens.colorBrandForeground1,
    },
  },
  sideboardSection: {
    marginTop: '32px',
    opacity: 0.7,
  },
  sideboardLabel: {
    fontStyle: 'italic',
  },
  valueCell: {
    textAlign: 'right',
    whiteSpace: 'nowrap',
  },
});

export default function DeckView() {
  const styles = useStyles();
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [deck, setDeck] = useState<DeckDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (id) {
      api.getDeck(Number(id))
        .then(setDeck)
        .catch((e) => setError(e.message))
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
      setError('No deck ID provided.');
    }
  }, [id]);

  const { mainCards, sideboardCards, commander, colorIdentity, totalValue } = useMemo(() => {
    if (!deck) return { mainCards: new Map(), sideboardCards: new Map(), commander: null, colorIdentity: [] as string[], totalValue: 0 };
    const main = new Map<string, DeckCardEntry[]>();
    const side = new Map<string, DeckCardEntry[]>();
    let cmd: DeckCardEntry | null = null;
    const colors = new Set<string>();
    let value = 0;

    for (const entry of deck.cards) {
      if (entry.is_commander) cmd = entry;
      const cat = entry.category || 'Other';
      (entry.card.color_identity || []).forEach(c => colors.add(c));
      const price = parseFloat(entry.card.price_eur) || 0;
      value += price * entry.quantity;

      if (SIDEBOARD_CATEGORIES.has(cat)) {
        if (!side.has(cat)) side.set(cat, []);
        side.get(cat)!.push(entry);
      } else {
        if (!main.has(cat)) main.set(cat, []);
        main.get(cat)!.push(entry);
      }
    }
    return {
      mainCards: main,
      sideboardCards: side,
      commander: cmd,
      colorIdentity: Array.from(colors),
      totalValue: value,
    };
  }, [deck]);

  if (loading) return <Spinner label="Loading deck..." />;
  if (error) return <Body1>Error loading deck: {error}</Body1>;
  if (!deck) return <Body1>Deck not found.</Body1>;

  // Mana curve (non-land, non-sideboard, grouped by CMC 0-7+)
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

  // Color pips from mana costs
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

  const renderCardTable = (cards: DeckCardEntry[]) => (
    <table className={styles.table}>
      <thead>
        <tr>
          <th className={styles.th} style={{ width: 32 }}>#</th>
          <th className={styles.th}>Name</th>
          <th className={styles.th}>Mana</th>
          <th className={styles.th}>Type</th>
          <th className={styles.th} style={{ textAlign: 'right' }}>Price</th>
        </tr>
      </thead>
      <tbody>
        {cards.map((entry, i) => (
          <CardHoverPreview key={i} card={entry.card}>
            <tr>
              <td className={styles.td}>{entry.quantity}</td>
              <td className={styles.td}>
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
              </td>
              <td className={styles.td}><ManaCost cost={entry.card.mana_cost} size={14} /></td>
              <td className={styles.td}><Caption1>{entry.card.type_line}</Caption1></td>
              <td className={`${styles.td} ${styles.valueCell}`}>
                {entry.card.price_eur ? `€${entry.card.price_eur}` : ''}
              </td>
            </tr>
          </CardHoverPreview>
        ))}
      </tbody>
    </table>
  );

  return (
    <div className={styles.page}>
      {/* Header */}
      <div className={styles.headerRow}>
        {commander?.card.image_uri && (
          <img src={commander.card.image_uri} alt={commander.card.name} className={styles.commanderImg} />
        )}
        <div className={styles.headerInfo}>
          <Title2>{deck.name}</Title2>
          <div className={styles.meta}>
            <Badge appearance="outline">{deck.format || 'Unknown'}</Badge>
            <UserBracketBadge deck={deck} onUpdate={setDeck} />
            {commander?.card.mana_cost ? (
              <ManaCost cost={commander.card.mana_cost} size={18} />
            ) : colorIdentity.length > 0 && (
              <span style={{ display: 'inline-flex', gap: 2, alignItems: 'center' }}>
                {colorIdentity.map(c => (
                  <ManaSymbol key={c} symbol={c} size={18} />
                ))}
              </span>
            )}
            <Caption1>{mainCount} cards</Caption1>
            {totalValue > 0 && <Caption1>€{totalValue.toFixed(2)}</Caption1>}
            {deck.archidekt_id && (
              <a href={`https://archidekt.com/decks/${deck.archidekt_id}`} target="_blank" rel="noopener noreferrer">
                <Button appearance="subtle" size="small">Archidekt ↗</Button>
              </a>
            )}
            {deck.commander_name && (
              <a
                href={`https://edhrec.com/commanders/${deck.commander_name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '')}`}
                target="_blank"
                rel="noopener noreferrer"
              >
                <Button appearance="subtle" size="small">EDHREC ↗</Button>
              </a>
            )}
          </div>
          {deck.commander_name && <Body2 style={{ marginTop: 6 }}>Commander: {deck.commander_name}</Body2>}
          {deck.description && <Body1 style={{ marginTop: 8, opacity: 0.8 }}>{deck.description}</Body1>}
          <GameplanBox deck={deck} onUpdate={setDeck} />
          <AIAssessmentBox deck={deck} />
        </div>
      </div>

      <Divider />

      {/* Mana Curve & Color Pips */}
      {/* TOP_PAD reserves vertical space above bars so count labels are never clipped */}
      <div style={{ display: 'flex', gap: 32, flexWrap: 'wrap', marginTop: 16, marginBottom: 16 }}>
        {manaCurve.some(b => b.count > 0) && (() => {
          const TOP_PAD = 14;
          const BAR_H = 60;
          const LABEL_Y = TOP_PAD + BAR_H + 15;
          return (
            <div>
              <Caption1 style={{ display: 'block', marginBottom: 4 }}>Mana Curve</Caption1>
              <svg width={manaCurve.length * 28} height={TOP_PAD + BAR_H + 20}>
                {manaCurve.map((b, i) => {
                  const barH = (b.count / curveMax) * BAR_H;
                  return (
                    <g key={i}>
                      <rect x={i * 28 + 4} y={TOP_PAD + BAR_H - barH} width={20} height={barH} fill={tokens.colorBrandBackground} rx={2} />
                      <text x={i * 28 + 14} y={LABEL_Y} textAnchor="middle" fontSize={10} fill={tokens.colorNeutralForeground3}>{b.label}</text>
                      {b.count > 0 && <text x={i * 28 + 14} y={TOP_PAD + BAR_H - barH - 3} textAnchor="middle" fontSize={9} fill={tokens.colorNeutralForeground2}>{b.count}</text>}
                    </g>
                  );
                })}
              </svg>
            </div>
          );
        })()}
        {colorPips.length > 0 && (() => {
          const TOP_PAD = 14;
          const BAR_H = 60;
          const LABEL_Y = TOP_PAD + BAR_H + 15;
          return (
            <div>
              <Caption1 style={{ display: 'block', marginBottom: 4 }}>Color Pips</Caption1>
              <svg width={colorPips.length * 36} height={TOP_PAD + BAR_H + 20}>
                {colorPips.map((p, i) => {
                  const barH = (p.count / pipMax) * BAR_H;
                  return (
                    <g key={i}>
                      <rect x={i * 36 + 4} y={TOP_PAD + BAR_H - barH} width={28} height={barH} fill={COLOR_MAP[p.color] || '#888'} rx={2}
                        stroke={tokens.colorNeutralStroke1} strokeWidth={p.color === 'W' ? 1 : 0} />
                      <text x={i * 36 + 18} y={LABEL_Y} textAnchor="middle" fontSize={10} fill={tokens.colorNeutralForeground3}>{p.color}</text>
                      <text x={i * 36 + 18} y={TOP_PAD + BAR_H - barH - 3} textAnchor="middle" fontSize={9} fill={tokens.colorNeutralForeground2}>{p.count}</text>
                    </g>
                  );
                })}
              </svg>
            </div>
          );
        })()}
      </div>

      {/* Main deck categories */}
      {Array.from(mainCards.entries()).map(([cat, cards]) => (
        <div key={cat} className={styles.categorySection}>
          <Title3>{cat} ({cards.reduce((s: number, c: DeckCardEntry) => s + c.quantity, 0)})</Title3>
          {renderCardTable(cards)}
        </div>
      ))}

      {/* Sideboard / Maybeboard */}
      {sideboardCards.size > 0 && (
        <div className={styles.sideboardSection}>
          <Divider />
          {Array.from(sideboardCards.entries()).map(([cat, cards]) => (
            <div key={cat} className={styles.categorySection}>
              <Title3 className={styles.sideboardLabel}>{cat} ({cards.reduce((s: number, c: DeckCardEntry) => s + c.quantity, 0)})</Title3>
              {renderCardTable(cards)}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
