import { useEffect, useState, useCallback, useMemo } from 'react';
import { makeStyles } from '@griffel/react';
import {
  Spinner,
  Input,
  Button,
  Select,
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
import { useMediaQuery } from '../hooks/useMediaQuery';
import { sothera } from '../theme/sothera';
import { useAccent } from '../main';
import { Panel, PageHeader, SectionHeader } from '../components/sothera';
import { t } from '../i18n';

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

const useStyles = makeStyles({
  controls: {
    display: 'flex',
    gap: '12px',
    marginBottom: '16px',
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
  gridHeader: {
    display: 'grid',
    gridTemplateColumns: '2fr 80px 80px 80px 1.5fr 80px 100px',
    padding: '4px 0 14px',
    borderBottom: `1px solid ${sothera.headerBorder}`,
    fontFamily: sothera.fontMono,
    fontSize: '9px',
    letterSpacing: '2px',
    color: sothera.fgFaint,
    textTransform: 'uppercase',
    '@media (max-width: 768px)': {
      display: 'none',
    },
  },
  gridRow: {
    display: 'grid',
    gridTemplateColumns: '2fr 80px 80px 80px 1.5fr 80px 100px',
    padding: '12px 0',
    fontSize: '13px',
    alignItems: 'center',
    '@media (max-width: 768px)': {
      gridTemplateColumns: '1fr auto',
      gap: '4px',
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
  groupHeader: {
    cursor: 'pointer',
    userSelect: 'none',
    backgroundColor: 'rgba(255,255,255,0.02)',
    ':hover': {
      backgroundColor: 'rgba(255,255,255,0.04)',
    },
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
    fontFamily: sothera.fontMono,
    fontSize: '11px',
    color: sothera.fgMuted,
    letterSpacing: '1px',
    minWidth: '180px',
    textAlign: 'center',
  },
  mobileCard: {
    padding: '12px',
    marginBottom: '8px',
  },
});

export default function Collection() {
  const styles = useStyles();
  const { accent } = useAccent();
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
  const isMobile = useMediaQuery('(max-width: 600px)');

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
      <PageHeader
        eyebrow={`☷ INDEX · ${total} REGISTERED`}
        title="Collection"
        accent={accent.oklch}
        right={
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontFamily: sothera.fontMono, fontSize: 10, letterSpacing: 2, color: sothera.fgFaint, textTransform: 'uppercase' }}>PAGE {page} OF {totalPages}</div>
            <div style={{ fontFamily: sothera.fontDisplay, fontSize: 22, fontWeight: 600, color: sothera.fg, fontFeatureSettings: '"tnum"', marginTop: 4 }}>{total} entries</div>
          </div>
        }
      />

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
        <div style={{ fontFamily: sothera.fontMono, fontSize: 13, color: sothera.fgMuted, marginTop: 24, letterSpacing: 1 }}>
          {searchQuery || selectedSet ? 'No cards found.' : 'Collection is empty. Sync your decks to populate it.'}
        </div>
      ) : (
        <>
          {isMobile ? (
            <div>
              {entries.map(entry => (
                <Panel key={entry.id} className={styles.mobileCard}>
                  <CardHoverPreview card={entry.card}>
                    <a href={scryfallUrl(entry.card)} target="_blank" rel="noopener noreferrer" className={styles.cardLink}>
                      <strong>{entry.card.name}</strong>
                    </a>
                  </CardHoverPreview>
                  <div style={{ fontFamily: sothera.fontMono, fontSize: 11, color: sothera.fgMuted, marginTop: 4 }}>{entry.card.set_name || entry.card.set_code}</div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4 }}>
                    <span style={{ fontFamily: sothera.fontMono, fontSize: 11, color: sothera.fgMuted }}>Qty: {getCopies(entry)} ({getFinish(entry)})</span>
                    <span style={{ fontFamily: sothera.fontDisplay, fontWeight: 600, color: sothera.fg }}>{getPrice(entry) === '—' ? '—' : `€${getPrice(entry)}`}</span>
                  </div>
                </Panel>
              ))}
            </div>
          ) : (
            <Panel>
              <div className={styles.gridHeader}>
                <div>NAME</div><div>COPIES</div><div>IN DECKS</div><div>FINISH</div><div>EDITION</div><div>LANG</div><div style={{ textAlign: 'right' }}>EUR</div>
              </div>
              {groups.map(group => {
                const isOpen = openGroups.has(group.name);
                if (group.entries.length === 1) {
                  const entry = group.entries[0];
                  return (
                    <div key={entry.id} className={styles.gridRow} style={{ borderBottom: `1px solid ${sothera.rowBorder}` }}>
                      <div>
                        <CardHoverPreview card={entry.card}>
                          <a href={scryfallUrl(entry.card)} target="_blank" rel="noopener noreferrer" className={styles.cardLink}>{entry.card.name}</a>
                        </CardHoverPreview>
                        {entry.cardmarket_listing_count > 0 && (
                          <span
                            title={t('collection.listed_on_cardmarket', { qty: String(entry.cardmarket_listed_qty) })}
                            style={{ marginLeft: 6, fontSize: 11, cursor: 'default', color: sothera.fgFaint }}
                          >
                            🛒{entry.cardmarket_listed_qty > 1 ? entry.cardmarket_listed_qty : ''}
                          </span>
                        )}
                      </div>
                      <div style={{ fontFamily: sothera.fontDisplay, fontWeight: 600, color: sothera.fg, fontFeatureSettings: '"tnum"' }}>{getCopies(entry)}</div>
                      <div style={{ fontFamily: sothera.fontMono, fontSize: 11, color: sothera.fgMuted }}>{group.inDecks > 0 ? group.inDecks : '—'}</div>
                      <div style={{ fontFamily: sothera.fontMono, fontSize: 11, color: sothera.fgMuted }}>{getFinish(entry)}</div>
                      <div style={{ fontFamily: sothera.fontMono, fontSize: 11, color: sothera.fgMuted, letterSpacing: 0.5 }}>{entry.card.set_name || entry.card.set_code || '—'}</div>
                      <div style={{ fontFamily: sothera.fontMono, fontSize: 11, color: sothera.fgMuted }}>{entry.language || '—'}</div>
                      <div style={{ textAlign: 'right', fontFamily: sothera.fontDisplay, fontWeight: 600, color: sothera.fg, fontFeatureSettings: '"tnum"' }}>{getPrice(entry) === '—' ? '—' : `€${getPrice(entry)}`}</div>
                    </div>
                  );
                }
                return (
                  <div key={group.name}>
                    <div className={`${styles.gridRow} ${styles.groupHeader}`} style={{ borderBottom: `1px solid ${sothera.rowBorder}` }} onClick={() => toggleGroup(group.name)}>
                      <div style={{ fontWeight: 600, color: sothera.fg }}>
                        <span style={{ transition: 'transform 0.15s', display: 'inline-block', transform: isOpen ? 'rotate(90deg)' : 'none', fontSize: 10, marginRight: 6 }}>▶</span>
                        {group.name}
                        <span style={{ fontFamily: sothera.fontMono, fontSize: 10, marginLeft: 8, color: sothera.fgFaint }}>({group.entries.length} printings)</span>
                      </div>
                      <div style={{ fontFamily: sothera.fontDisplay, fontWeight: 600, color: sothera.fg }}>{group.totalCopies}</div>
                      <div style={{ fontFamily: sothera.fontMono, fontSize: 11, color: sothera.fgMuted }}>{group.inDecks > 0 ? group.inDecks : '—'}</div>
                      <div /><div /><div /><div />
                    </div>
                    {isOpen && group.entries.map(entry => (
                      <div key={entry.id} className={styles.gridRow} style={{ borderBottom: `1px solid ${sothera.rowBorder}`, paddingLeft: 32 }}>
                        <div>
                          <CardHoverPreview card={entry.card}>
                            <a href={scryfallUrl(entry.card)} target="_blank" rel="noopener noreferrer" className={styles.cardLink}>{entry.card.name}</a>
                          </CardHoverPreview>
                          {entry.cardmarket_listing_count > 0 && (
                            <span
                              title={t('collection.listed_on_cardmarket', { qty: String(entry.cardmarket_listed_qty) })}
                              style={{ marginLeft: 6, fontSize: 11, cursor: 'default', color: sothera.fgFaint }}
                            >
                              🛒{entry.cardmarket_listed_qty > 1 ? entry.cardmarket_listed_qty : ''}
                            </span>
                          )}
                        </div>
                        <div style={{ fontFamily: sothera.fontDisplay, fontWeight: 600, color: sothera.fg }}>{getCopies(entry)}</div>
                        <div style={{ fontFamily: sothera.fontMono, fontSize: 11, color: sothera.fgMuted }}>{group.inDecks > 0 ? group.inDecks : '—'}</div>
                        <div style={{ fontFamily: sothera.fontMono, fontSize: 11, color: sothera.fgMuted }}>{getFinish(entry)}</div>
                        <div style={{ fontFamily: sothera.fontMono, fontSize: 11, color: sothera.fgMuted }}>{entry.card.set_name || entry.card.set_code || '—'}</div>
                        <div style={{ fontFamily: sothera.fontMono, fontSize: 11, color: sothera.fgMuted }}>{entry.language || '—'}</div>
                        <div style={{ textAlign: 'right', fontFamily: sothera.fontDisplay, fontWeight: 600, color: sothera.fg }}>{getPrice(entry) === '—' ? '—' : `€${getPrice(entry)}`}</div>
                      </div>
                    ))}
                  </div>
                );
              })}
            </Panel>
          )}
          <div className={styles.pagination}>
            <Button icon={<ChevronDoubleLeft20Regular />} appearance="subtle" size="small" disabled={page <= 1} onClick={() => setPage(1)} />
            <Button icon={<ChevronLeft24Regular />} appearance="subtle" size="small" disabled={page <= 1} onClick={() => setPage(p => Math.max(1, p - 1))} />
            <span className={styles.pageInfo}>Page {page} of {totalPages} ({total} entries)</span>
            <Button icon={<ChevronRight24Regular />} appearance="subtle" size="small" disabled={page >= totalPages} onClick={() => setPage(p => Math.min(totalPages, p + 1))} />
            <Button icon={<ChevronDoubleRight20Regular />} appearance="subtle" size="small" disabled={page >= totalPages} onClick={() => setPage(totalPages)} />
          </div>
        </>
      )}
    </div>
  );
}
