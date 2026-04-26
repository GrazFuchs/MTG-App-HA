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
import { ManaCost } from '../components/ManaSymbol';
import { CardHoverPreview } from '../components/CardHoverPreview';

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
  colorDots: {
    display: 'inline-flex',
    gap: '3px',
    alignItems: 'center',
  },
  colorDot: {
    width: '14px',
    height: '14px',
    borderRadius: '50%',
    border: `1px solid ${tokens.colorNeutralStroke1}`,
    display: 'inline-block',
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
            {deck.bracket > 0 && <Badge appearance="outline" color="informative">Bracket {deck.bracket}</Badge>}
            {colorIdentity.length > 0 && (
              <span className={styles.colorDots}>
                {colorIdentity.map(c => (
                  <span key={c} className={styles.colorDot} style={{ backgroundColor: COLOR_MAP[c] || '#888' }} title={c} />
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
        </div>
      </div>

      <Divider />

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
