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
    '&:hover': {
      boxShadow: tokens.shadow8,
    },
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
  folderSection: {
    marginTop: '24px',
  },
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
  chevronOpen: {
    transform: 'rotate(90deg)',
  },
});

export default function Decks() {
  const styles = useStyles();
  const navigate = useNavigate();
  const [decks, setDecks] = useState<DeckSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [openFolders, setOpenFolders] = useState<Set<string>>(new Set());

  useEffect(() => {
    api.getDecks().then(setDecks).finally(() => setLoading(false));
  }, []);

  const grouped = useMemo(() => {
    const map = new Map<string, DeckSummary[]>();
    for (const d of decks) {
      const folder = d.folder_name || 'Uncategorized';
      if (!map.has(folder)) map.set(folder, []);
      map.get(folder)!.push(d);
    }
    const sorted = [...map.entries()].sort(([a], [b]) => {
      if (a === 'Uncategorized') return 1;
      if (b === 'Uncategorized') return -1;
      return a.localeCompare(b);
    });
    return sorted;
  }, [decks]);

  const toggleFolder = (folder: string) => {
    setOpenFolders(prev => {
      const next = new Set(prev);
      if (next.has(folder)) next.delete(folder);
      else next.add(folder);
      return next;
    });
  };

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

  const renderDeckCard = (d: DeckSummary) => (
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
            {d.bracket > 0 && <Badge appearance="outline" color="informative">Bracket {d.bracket}</Badge>}
            <Caption1>{d.card_count} cards</Caption1>
            {d.commander_name && <Caption1>⚔ {d.commander_name}</Caption1>}
          </div>
        }
      />
    </Card>
  );

  return (
    <div>
      <Title2>Decks ({decks.length})</Title2>
      {grouped.map(([folder, folderDecks]) => {
        const isOpen = openFolders.has(folder);
        return (
          <div key={folder} className={styles.folderSection}>
            <div className={styles.folderHeader} onClick={() => toggleFolder(folder)}>
              <span className={`${styles.chevron} ${isOpen ? styles.chevronOpen : ''}`}>▶</span>
              <Title3>{folder} ({folderDecks.length})</Title3>
            </div>
            <Divider />
            {isOpen && (
              <div className={styles.grid}>
                {folderDecks.map(renderDeckCard)}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
