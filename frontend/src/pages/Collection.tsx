import { useEffect, useState, useCallback, useMemo } from 'react';
import {
  makeStyles,
  tokens,
  Title2,
  Body1,
  Caption1,
  Spinner,
  Input,
  Button,
  Select,
  Table,
  TableHeader,
  TableRow,
  TableHeaderCell,
  TableBody,
  TableCell,
} from '@fluentui/react-components';
import {
  Search24Regular,
  ChevronLeft24Regular,
  ChevronRight24Regular,
  ChevronDoubleLeft20Regular,
  ChevronDoubleRight20Regular,
} from '@fluentui/react-icons';
import { api, CollectionEntry, CollectionSet, DeckSummary } from '../api';
import { CardHoverPreview } from '../components/CardHoverPreview';

const useStyles = makeStyles({
  controls: {
    display: 'flex',
    gap: '12px',
    marginTop: '12px',
    flexWrap: 'wrap',
  },
  input: {
    minWidth: '240px',
    flex: 1,
    maxWidth: '420px',
  },
  select: {
    minWidth: '180px',
  },
  tableWrap: {
    marginTop: '16px',
    overflowX: 'auto',
  },
  nameCell: {
    minWidth: '220px',
  },
  hoverAnchor: {
    display: 'inline-block',
    width: '100%',
  },
  cardLink: {
    color: tokens.colorNeutralForeground1,
    textDecoration: 'none',
    '&:hover': {
      textDecoration: 'underline',
      color: tokens.colorBrandForeground1,
    },
  },
  groupHeader: {
    cursor: 'pointer',
    userSelect: 'none',
    backgroundColor: tokens.colorNeutralBackground3,
    '&:hover': {
      backgroundColor: tokens.colorNeutralBackground3Hover,
    },
  },
  chevron: {
    display: 'inline-block',
    transition: 'transform 0.15s ease',
    fontSize: '10px',
    marginRight: '6px',
  },
  chevronOpen: {
    transform: 'rotate(90deg)',
  },
  deckUsage: {
    fontSize: '12px',
  },
  groupRow: {
    fontWeight: 600,
  },
  pagination: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '8px',
    marginTop: '16px',
    flexWrap: 'wrap',
  },
  pageInfo: {
    minWidth: '180px',
    textAlign: 'center' as const,
  },
  hideOnMobile: {
    '@media (max-width: 640px)': {
      display: 'none',
    },
  },
});

function scryfallUrl(card: { set_code: string; collector_number: string; name: string }) {
  if (card.set_code && card.collector_number) {
    return `https://scryfall.com/card/${card.set_code.toLowerCase()}/${card.collector_number}`;
  }
  return `https://scryfall.com/search?q=!"${encodeURIComponent(card.name)}"`;
}

function getCopies(entry: CollectionEntry): number {
  return entry.quantity + entry.foil_quantity;
}

function getFinish(entry: CollectionEntry): string {
  if (entry.quantity > 0 && entry.foil_quantity > 0) return 'Mixed';
  if (entry.foil_quantity > 0) return 'Foil';
  return 'Non-foil';
}

function getPrice(entry: CollectionEntry): string {
  const finish = getFinish(entry);
  if (finish === 'Foil') return entry.card.price_eur_foil || entry.card.price_eur || '—';
  if (finish === 'Mixed') {
    const normal = entry.card.price_eur || '—';
    const foil = entry.card.price_eur_foil || entry.card.price_eur || '—';
    return `${normal} / ${foil}`;
  }
  return entry.card.price_eur || entry.card.price_eur_foil || '—';
}

interface CardGroup {
  name: string;
  entries: CollectionEntry[];
  totalCopies: number;
  inDecks: number;
}

export default function Collection() {
  const styles = useStyles();
  const [entries, setEntries] = useState<CollectionEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(100);
  const [loading, setLoading] = useState(true);
  const [searchInput, setSearchInput] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [sortBy, setSortBy] = useState('added_at');
  const [sortDir, setSortDir] = useState('desc');
  const [sets, setSets] = useState<CollectionSet[]>([]);
  const [selectedSet, setSelectedSet] = useState('');
  const [decks, setDecks] = useState<DeckSummary[]>([]);
  const [selectedDeck, setSelectedDeck] = useState('');
  const [openGroups, setOpenGroups] = useState<Set<string>>(new Set());

  useEffect(() => {
    api.getCollectionSets().then(setSets).catch(() => {});
    api.getDecks().then(setDecks).catch(() => {});
  }, []);

  const load = useCallback((q: string, currentSortBy: string, currentSortDir: string, currentPage: number) => {
    setLoading(true);
    const params = new URLSearchParams();
    if (q) params.set('search', q);
    if (selectedSet) params.set('set_code', selectedSet);
    if (selectedDeck) params.set('deck_id', selectedDeck);
    params.set('sort_by', currentSortBy);
    params.set('sort_dir', currentSortDir);
    params.set('page', String(currentPage));
    params.set('page_size', String(pageSize));
    api.getCollection(params)
      .then(res => { setEntries(res.items); setTotal(res.total); })
      .catch(() => { setEntries([]); setTotal(0); })
      .finally(() => setLoading(false));
  }, [pageSize, selectedSet, selectedDeck]);

  useEffect(() => {
    load(searchQuery, sortBy, sortDir, page);
  }, [load, searchQuery, sortBy, sortDir, page]);

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  const handleSearch = () => { setPage(1); setSearchQuery(searchInput.trim()); };
  const handleSetChange = (value: string) => { setPage(1); setSelectedSet(value); };
  const handleDeckChange = (value: string) => { setPage(1); setSelectedDeck(value); };

  // Group by card name
  const groups = useMemo(() => {
    const map = new Map<string, CardGroup>();
    for (const entry of entries) {
      const name = entry.card.name;
      if (!map.has(name)) {
        map.set(name, { name, entries: [], totalCopies: 0, inDecks: entry.in_decks || 0 });
      }
      const group = map.get(name)!;
      group.entries.push(entry);
      group.totalCopies += getCopies(entry);
      // in_decks is per-name, take the max (they should all be same)
      group.inDecks = Math.max(group.inDecks, entry.in_decks || 0);
    }
    return Array.from(map.values());
  }, [entries]);

  const toggleGroup = (name: string) => {
    setOpenGroups(prev => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  };

  return (
    <div>
      <Title2>Collection ({total} entries, page {page}/{totalPages})</Title2>
      <div className={styles.controls}>
        <Input
          placeholder="Search cards..."
          contentBefore={<Search24Regular />}
          value={searchInput}
          onChange={(_, d) => setSearchInput(d.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          className={styles.input}
        />
        <Button onClick={handleSearch}>Search</Button>
        <Select value={selectedSet} onChange={(_, d) => handleSetChange(d.value)} className={styles.select}>
          <option value="">All Sets</option>
          {sets.map(s => (
            <option key={s.set_code} value={s.set_code}>{s.set_name} ({s.set_code.toUpperCase()})</option>
          ))}
        </Select>
        <Select value={selectedDeck} onChange={(_, d) => handleDeckChange(d.value)} className={styles.select}>
          <option value="">All Decks</option>
          {decks.map(d => (
            <option key={d.id} value={String(d.id)}>{d.name}</option>
          ))}
        </Select>
        <Select value={sortBy} onChange={(_, d) => { setPage(1); setSortBy(d.value); }} className={styles.select}>
          <option value="added_at">Date Added</option>
          <option value="price_eur">Price</option>
          <option value="set">Set</option>
          <option value="archidekt_tags">Collection Tag</option>
          <option value="name">Name</option>
        </Select>
        <Select value={sortDir} onChange={(_, d) => { setPage(1); setSortDir(d.value); }} className={styles.select}>
          <option value="asc">Ascending</option>
          <option value="desc">Descending</option>
        </Select>
      </div>

      {loading ? (
        <Spinner label="Loading collection..." style={{ marginTop: 24 }} />
      ) : entries.length === 0 ? (
        <Body1 style={{ marginTop: 24 }}>
          {searchQuery || selectedSet ? 'No cards found.' : 'Collection is empty. Sync your decks to populate it.'}
        </Body1>
      ) : (
        <>
        <div className={styles.tableWrap}>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHeaderCell>Name</TableHeaderCell>
                <TableHeaderCell>Copies</TableHeaderCell>
                <TableHeaderCell className={styles.hideOnMobile}>In Decks</TableHeaderCell>
                <TableHeaderCell className={styles.hideOnMobile}>Finish</TableHeaderCell>
                <TableHeaderCell className={styles.hideOnMobile}>Edition</TableHeaderCell>
                <TableHeaderCell className={styles.hideOnMobile}>Language</TableHeaderCell>
                <TableHeaderCell>Price (EUR)</TableHeaderCell>
              </TableRow>
            </TableHeader>
            <TableBody>
              {groups.map(group => {
                const isOpen = openGroups.has(group.name);
                if (group.entries.length === 1) {
                  // Single entry — render directly
                  const entry = group.entries[0];
                  return (
                    <TableRow key={entry.id}>
                      <TableCell className={styles.nameCell}>
                        <CardHoverPreview card={entry.card}>
                          <a
                            href={scryfallUrl(entry.card)}
                            target="_blank"
                            rel="noopener noreferrer"
                            className={`${styles.hoverAnchor} ${styles.cardLink}`}
                          >
                            {entry.card.name}
                          </a>
                        </CardHoverPreview>
                      </TableCell>
                      <TableCell>{getCopies(entry)}</TableCell>
                      <TableCell className={`${styles.deckUsage} ${styles.hideOnMobile}`}>
                        {group.inDecks > 0 ? group.inDecks : '—'}
                      </TableCell>
                      <TableCell className={styles.hideOnMobile}>{getFinish(entry)}</TableCell>
                      <TableCell className={styles.hideOnMobile}>{entry.card.set_name || entry.card.set_code || '—'}</TableCell>
                      <TableCell className={styles.hideOnMobile}>{entry.language || '—'}</TableCell>
                      <TableCell>{getPrice(entry) === '—' ? '—' : `€${getPrice(entry)}`}</TableCell>
                    </TableRow>
                  );
                }
                // Multi-entry group — collapsible
                return (
                  <>{/* Fragment for group */}
                    <TableRow
                      key={group.name}
                      className={styles.groupHeader}
                      onClick={() => toggleGroup(group.name)}
                    >
                      <TableCell className={`${styles.nameCell} ${styles.groupRow}`}>
                        <span className={`${styles.chevron} ${isOpen ? styles.chevronOpen : ''}`}>▶</span>
                        {group.name}
                        <Caption1 style={{ marginLeft: 8 }}>({group.entries.length} printings)</Caption1>
                      </TableCell>
                      <TableCell className={styles.groupRow}>{group.totalCopies}</TableCell>
                      <TableCell className={`${styles.groupRow} ${styles.deckUsage} ${styles.hideOnMobile}`}>
                        {group.inDecks > 0 ? group.inDecks : '—'}
                      </TableCell>
                      <TableCell className={styles.hideOnMobile} />
                      <TableCell className={styles.hideOnMobile} />
                      <TableCell className={styles.hideOnMobile} />
                      <TableCell />
                    </TableRow>
                    {isOpen && group.entries.map(entry => (
                      <TableRow key={entry.id}>
                        <TableCell className={styles.nameCell} style={{ paddingLeft: 32 }}>
                          <CardHoverPreview card={entry.card}>
                            <a
                              href={scryfallUrl(entry.card)}
                              target="_blank"
                              rel="noopener noreferrer"
                              className={`${styles.hoverAnchor} ${styles.cardLink}`}
                            >
                              {entry.card.name}
                            </a>
                          </CardHoverPreview>
                        </TableCell>
                        <TableCell>{getCopies(entry)}</TableCell>
                        <TableCell className={`${styles.deckUsage} ${styles.hideOnMobile}`}>
                          {group.inDecks > 0 ? group.inDecks : '—'}
                        </TableCell>
                        <TableCell className={styles.hideOnMobile}>{getFinish(entry)}</TableCell>
                        <TableCell className={styles.hideOnMobile}>{entry.card.set_name || entry.card.set_code || '—'}</TableCell>
                        <TableCell className={styles.hideOnMobile}>{entry.language || '—'}</TableCell>
                        <TableCell>{getPrice(entry) === '—' ? '—' : `€${getPrice(entry)}`}</TableCell>
                      </TableRow>
                    ))}
                  </>
                );
              })}
            </TableBody>
          </Table>
        </div>
        <div className={styles.pagination}>
          <Button
            icon={<ChevronDoubleLeft20Regular />}
            appearance="subtle"
            size="small"
            disabled={page <= 1}
            onClick={() => setPage(1)}
          />
          <Button
            icon={<ChevronLeft24Regular />}
            appearance="subtle"
            size="small"
            disabled={page <= 1}
            onClick={() => setPage(p => Math.max(1, p - 1))}
          />
          <Caption1 className={styles.pageInfo}>
            Page {page} of {totalPages} ({total} entries)
          </Caption1>
          <Button
            icon={<ChevronRight24Regular />}
            appearance="subtle"
            size="small"
            disabled={page >= totalPages}
            onClick={() => setPage(p => Math.min(totalPages, p + 1))}
          />
          <Button
            icon={<ChevronDoubleRight20Regular />}
            appearance="subtle"
            size="small"
            disabled={page >= totalPages}
            onClick={() => setPage(totalPages)}
          />
        </div>
        </>
      )}
    </div>
  );
}
