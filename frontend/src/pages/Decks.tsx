import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  makeStyles,
  tokens,
  Card,
  CardHeader,
  CardPreview,
  Title2,
  Title3,
  Body1,
  Caption1,
  Spinner,
  Badge,
  Divider,
  Select,
} from '@fluentui/react-components';
import { api, DeckSummary } from '../api';

const useStyles = makeStyles({
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
    gap: '16px',
    marginTop: '12px',
  },
  card: {
    cursor: 'pointer',
    '&:hover': { boxShadow: tokens.shadow8 },
  },
  img: {
    width: '100%',
    height: '160px',
    objectFit: 'cover',
  },
  meta: {
    display: 'flex',
    gap: '8px',
    marginTop: '4px',
    flexWrap: 'wrap',
  },
  folderSection: { marginTop: '24px' },
  folderHeader: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    cursor: 'pointer',
    userSelect: 'none',
    marginBottom: '4px',
  },
  chevron: {
    display: 'inline-block',
    transition: 'transform 0.2s ease',
    fontSize: '12px',
  },
  chevronOpen: { transform: 'rotate(90deg)' },
});

export default function Decks() {
  const styles = useStyles();
  const navigate = useNavigate();
  const [decks, setDecks] = useState<DeckSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [openFolders, setOpenFolders] = useState<Set<string> | null>(null);
  const [bracketFilter, setBracketFilter] = useState('');

  useEffect(() => {
    api.getDecks().then(d => {
      setDecks(d);
      setOpenFolders(new Set(d.map(dk => dk.folder_name || 'Uncategorized')));
    }).finally(() => setLoading(false));
  }, []);

  const filteredDecks = useMemo(() => {
    if (!bracketFilter) return decks;
    const b = parseInt(bracketFilter, 10);
    return decks.filter(d => d.bracket === b);
  }, [decks, bracketFilter]);

  const grouped = useMemo(() => {
    const map = new Map<string, DeckSummary[]>();
    for (const d of filteredDecks) {
      const folder = d.folder_name || 'Uncategorized';
      if (!map.has(folder)) map.set(folder, []);
      map.get(folder)!.push(d);
    }
    return [...map.entries()].sort(([a], [b]) => {
      if (a === 'Uncategorized') return 1;
      if (b === 'Uncategorized') return -1;
      return a.localeCompare(b);
    });
  }, [filteredDecks]);

  const toggleFolder = (folder: string) => {
    setOpenFolders(prev => {
      const next = new Set(prev ?? []);
      if (next.has(folder)) next.delete(folder);
      else next.add(folder);
      return next;
    });
  };

  const availableBrackets = useMemo(() => {
    const set = new Set(decks.map(d => d.bracket).filter(b => b > 0));
    return [...set].sort();
  }, [decks]);

  if (loading) return <Spinner label="Loading decks..." />;

  if (decks.length === 0) {
    return (
      <div>
        <Title2>Decks</Title2>
        <Body1 style={{ marginTop: 16 }}>
          No decks synced yet. Go to Settings to trigger a sync from Archidekt.
        </Body1>
      </div>
    );
  }

  return (
    <div>
      <Title2>Decks ({filteredDecks.length}{bracketFilter ? ` of ${decks.length}` : ''})</Title2>
      {availableBrackets.length > 0 && (
        <div style={{ marginTop: 8 }}>
          <Select
            value={bracketFilter}
            onChange={(_, d) => setBracketFilter(d.value)}
            style={{ minWidth: 180 }}
          >
            <option value="">All Brackets</option>
            {availableBrackets.map(b => (
              <option key={b} value={String(b)}>Bracket {String(b)}</option>
            ))}
          </Select>
        </div>
      )}
      {grouped.map(([folder, folderDecks]) => {
        const isOpen = openFolders?.has(folder) ?? true;
        return (
          <div key={folder} className={styles.folderSection}>
            <div className={styles.folderHeader} onClick={() => toggleFolder(folder)}>
              <span className={`${styles.chevron} ${isOpen ? styles.chevronOpen : ''}`}>▶</span>
              <Title3>{folder} ({folderDecks.length})</Title3>
            </div>
            <Divider />
            {isOpen && (
              <div className={styles.grid}>
                {folderDecks.map(d => (
                  <Card key={d.id} className={styles.card} onClick={() => navigate(`/decks/${d.id}`)}>
                    {d.featured_image && (
                      <CardPreview>
                        <img src={d.featured_image} alt={d.name} className={styles.img} />
                      </CardPreview>
                    )}
                    <CardHeader
                      header={<Body1><strong>{d.name}</strong></Body1>}
                      description={
                        <div className={styles.meta}>
                          <Badge appearance="outline">{d.format || 'Unknown'}</Badge>
                          {d.bracket > 0 && <Badge appearance="outline" color="informative">Bracket {String(d.bracket)}</Badge>}
                          <Caption1>{String(d.card_count)} cards</Caption1>
                          {d.commander_name && <Caption1>{'\u2694'} {d.commander_name}</Caption1>}
                        </div>
                      }
                    />
                  </Card>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
