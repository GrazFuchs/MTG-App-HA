import { useState, useCallback, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
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
import { CardmarketButton } from '../components/CardmarketButton';
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

/** Colour chips, in WUBRG order plus colourless. */
const COLOR_CHIPS = [
  { value: 'W', label: 'White', symbol: '⚪' },
  { value: 'U', label: 'Blue', symbol: '🔵' },
  { value: 'B', label: 'Black', symbol: '⚫' },
  { value: 'R', label: 'Red', symbol: '🔴' },
  { value: 'G', label: 'Green', symbol: '🟢' },
  { value: 'C', label: 'Colorless', symbol: '◆' },
] as const;

/**
 * How a multi-colour selection is read. Several colours are ambiguous on their
 * own — "green and blue" can mean either of these — so the mode is explicit
 * rather than guessed.
 */
const COLOR_MODES = [
  { value: 'any', label: 'has any of', hint: t('collection.mode_any') },
  { value: 'all', label: 'has all of', hint: t('collection.mode_all') },
  { value: 'exact', label: 'is exactly', hint: t('collection.mode_exact') },
  { value: 'exclude', label: 'has none of', hint: t('collection.mode_none') },
] as const;

const CARD_TYPES = [
  'Creature', 'Instant', 'Sorcery', 'Enchantment',
  'Artifact', 'Planeswalker', 'Land', 'Battle', 'Kindred',
] as const;

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
  filterBlock: {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
    marginBottom: '16px',
    paddingBottom: '14px',
    borderBottom: `1px solid ${sothera.glassBorder}`,
  },
  filterLine: {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
    flexWrap: 'wrap',
  },
  filterLabel: {
    fontFamily: sothera.fontMono,
    fontSize: '10px',
    letterSpacing: '2px',
    color: sothera.fgFaint,
    textTransform: 'uppercase',
    minWidth: '54px',
  },
  chipRow: {
    display: 'flex',
    gap: '6px',
    flexWrap: 'wrap',
  },
  chip: {
    padding: '4px 10px',
    fontSize: '11px',
    fontFamily: sothera.fontMono,
    letterSpacing: '0.5px',
    cursor: 'pointer',
    border: `1px solid ${sothera.glassBorder}`,
    borderRadius: '2px',
    background: 'transparent',
    color: sothera.fgMuted,
    transitionProperty: 'border-color, color, background-color',
    transitionDuration: '140ms',
    ':hover': {
      color: sothera.fg,
    },
  },
  chipClear: {
    fontFamily: sothera.fontMono,
    fontSize: '10px',
    letterSpacing: '1px',
    color: sothera.fgFaint,
    background: 'none',
    border: 'none',
    cursor: 'pointer',
    padding: '4px 2px',
    textDecoration: 'underline',
    ':hover': {
      color: sothera.fg,
    },
  },
});

export default function Collection() {
  const styles = useStyles();
  const { accent } = useAccent();
  // Seeded from the URL so the Dashboard tiles and alert rows can deep-link
  // here ("show me this card", "sort by value").
  const [urlParams] = useSearchParams();
  const [page, setPage] = useState(1);
  const [pageSize] = useState(100);
  const [searchInput, setSearchInput] = useState(() => urlParams.get('search') ?? '');
  const [searchQuery, setSearchQuery] = useState(() => urlParams.get('search') ?? '');
  const [sortBy, setSortBy] = useState(() => urlParams.get('sort_by') ?? 'added_at');
  const [sortDir, setSortDir] = useState(() => urlParams.get('sort_dir') ?? 'desc');
  const [selectedSet, setSelectedSet] = useState('');
  const [selectedDeck, setSelectedDeck] = useState('');
  const [selectedTag, setSelectedTag] = useState('');
  const [selectedColors, setSelectedColors] = useState<string[]>([]);
  const [colorMode, setColorMode] = useState('any');
  const [selectedTypes, setSelectedTypes] = useState<string[]>([]);
  const [openGroups, setOpenGroups] = useState<Set<string>>(new Set());
  // 768, not 600. The column header hides at 768 and the row grid collapses
  // to two columns at 768, but the card layout only started at 600 — so between
  // 601 and 768 px the table showed unlabelled columns with no header to say
  // what they were. One breakpoint, no dead zone.
  const isMobile = useMediaQuery('(max-width: 768px)');

  const { data: sets = [] } = useQuery<CollectionSet[]>({
    queryKey: ['collection-sets'],
    queryFn: () => api.getCollectionSets(),
    staleTime: 5 * 60_000,
  });

  const { data: tags = [] } = useQuery<string[]>({
    queryKey: ['collection-tags'],
    queryFn: () => api.getCollectionTags(),
    staleTime: 5 * 60_000,
  });

  const { data: decks = [] } = useQuery<DeckSummary[]>({
    queryKey: ['decks'],
    queryFn: () => api.getDecks(),
    staleTime: 5 * 60_000,
  });

  const collectionParams = useMemo(() => {
    const params = new URLSearchParams();
    if (searchQuery) params.set('search', searchQuery);
    if (selectedSet) params.set('set_code', selectedSet);
    if (selectedDeck) params.set('deck_id', selectedDeck);
    if (selectedTag) params.set('collection_tag', selectedTag);
    if (selectedColors.length) {
      params.set('color', selectedColors.join(','));
      params.set('color_mode', colorMode);
    }
    if (selectedTypes.length) params.set('card_type', selectedTypes.join(','));
    params.set('sort_by', sortBy);
    params.set('sort_dir', sortDir);
    params.set('page', String(page));
    params.set('page_size', String(pageSize));
    return params;
  }, [searchQuery, selectedSet, selectedDeck, selectedTag, selectedColors, colorMode,
      selectedTypes, sortBy, sortDir, page, pageSize]);

  const { data: collectionData, isLoading: loading } = useQuery({
    queryKey: ['collection', collectionParams.toString()],
    queryFn: () => api.getCollection(collectionParams),
    staleTime: 60_000,
  });

  const entries = collectionData?.items ?? [];
  const total = collectionData?.total ?? 0;

  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const handleSearch = useCallback(() => { setPage(1); setSearchQuery(searchInput.trim()); }, [searchInput]);
  const handleSetChange = (value: string) => { setPage(1); setSelectedSet(value); };
  const handleDeckChange = (value: string) => { setPage(1); setSelectedDeck(value); };
  const handleTagChange = (value: string) => { setPage(1); setSelectedTag(value); };

  const toggleColor = (value: string) => {
    setPage(1);
    setSelectedColors(prev =>
      prev.includes(value) ? prev.filter(c => c !== value) : [...prev, value]
    );
  };
  const toggleType = (value: string) => {
    setPage(1);
    setSelectedTypes(prev =>
      prev.includes(value) ? prev.filter(c => c !== value) : [...prev, value]
    );
  };

  const activeFilterCount =
    (searchQuery ? 1 : 0) + (selectedSet ? 1 : 0) + (selectedDeck ? 1 : 0) +
    (selectedTag ? 1 : 0) + (selectedColors.length ? 1 : 0) + (selectedTypes.length ? 1 : 0);

  const resetFilters = () => {
    setPage(1);
    setSearchInput('');
    setSearchQuery('');
    setSelectedSet('');
    setSelectedDeck('');
    setSelectedTag('');
    setSelectedColors([]);
    setColorMode('any');
    setSelectedTypes([]);
  };

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
        title={t('collection.title')}
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
          placeholder={t('collection.search')}
          contentBefore={<Search24Regular />}
          value={searchInput}
          onChange={(_, d) => setSearchInput(d.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          className={styles.input}
        />
        <Button onClick={handleSearch}>{t('common.search')}</Button>
        <Select value={selectedSet} onChange={(_, d) => handleSetChange(d.value)} className={styles.select}>
          <option value="">{t('common.all_sets')}</option>
          {sets.map(s => (
            <option key={s.set_code} value={s.set_code}>{s.set_name} ({s.set_code.toUpperCase()})</option>
          ))}
        </Select>
        <Select value={selectedDeck} onChange={(_, d) => handleDeckChange(d.value)} className={styles.select}>
          <option value="">{t('common.all_decks')}</option>
          {decks.map(d => (
            <option key={d.id} value={String(d.id)}>{d.name}</option>
          ))}
        </Select>
        {tags.length > 0 && (
          <Select value={selectedTag} onChange={(_, d) => handleTagChange(d.value)} className={styles.select} aria-label={t('collection.tag_filter')}>
            <option value="">{t('common.all_tags')}</option>
            {tags.map(tag => (
              <option key={tag} value={tag}>{tag}</option>
            ))}
          </Select>
        )}
        <Select value={sortBy} onChange={(_, d) => { setPage(1); setSortBy(d.value); }} className={styles.select}>
          <option value="added_at">{t('collection.sort_added')}</option>
          <option value="price_eur">{t('collection.sort_price')}</option>
          <option value="set">{t('collection.sort_set')}</option>
          <option value="archidekt_tags">{t('collection.sort_tag')}</option>
          <option value="name">{t('collection.sort_name')}</option>
        </Select>
        <Select value={sortDir} onChange={(_, d) => { setPage(1); setSortDir(d.value); }} className={styles.select}>
          <option value="asc">{t('collection.asc')}</option>
          <option value="desc">{t('collection.desc')}</option>
        </Select>
      </div>

      {/* Colour + type filters. Colours are chips rather than a dropdown
          because the selection is a set, and the mode selector next to them is
          what makes "green and blue" unambiguous. */}
      <div className={styles.filterBlock}>
        <div className={styles.filterLine}>
          <span className={styles.filterLabel}>{t('collection.colour')}</span>
          <Select
            value={colorMode}
            onChange={(_, d) => { setPage(1); setColorMode(d.value); }}
            aria-label={t('collection.colour_mode_hint')}
            title={COLOR_MODES.find(m => m.value === colorMode)?.hint}
            style={{ minWidth: 130 }}
          >
            {COLOR_MODES.map(m => (
              <option key={m.value} value={m.value}>{m.label}</option>
            ))}
          </Select>
          <div className={styles.chipRow}>
            {COLOR_CHIPS.map(c => {
              const on = selectedColors.includes(c.value);
              return (
                <button
                  key={c.value}
                  type="button"
                  className={styles.chip}
                  aria-pressed={on}
                  title={c.label}
                  onClick={() => toggleColor(c.value)}
                  style={on ? { backgroundColor: accent.soft, borderColor: accent.oklch, color: sothera.fg } : undefined}
                >
                  <span aria-hidden="true">{c.symbol}</span> {c.label}
                </button>
              );
            })}
          </div>
          {selectedColors.length > 0 && (
            <button type="button" className={styles.chipClear} onClick={() => { setPage(1); setSelectedColors([]); }}>
              {t('common.clear')}
            </button>
          )}
        </div>

        <div className={styles.filterLine}>
          <span className={styles.filterLabel}>{t('collection.type')}</span>
          <div className={styles.chipRow}>
            {CARD_TYPES.map(ct => {
              const on = selectedTypes.includes(ct);
              return (
                <button
                  key={ct}
                  type="button"
                  className={styles.chip}
                  aria-pressed={on}
                  onClick={() => toggleType(ct)}
                  style={on ? { backgroundColor: accent.soft, borderColor: accent.oklch, color: sothera.fg } : undefined}
                >
                  {ct}
                </button>
              );
            })}
          </div>
          {selectedTypes.length > 0 && (
            <button type="button" className={styles.chipClear} onClick={() => { setPage(1); setSelectedTypes([]); }}>
              {t('common.clear')}
            </button>
          )}
        </div>

        {activeFilterCount > 0 && (
          <div className={styles.filterLine}>
            <span className={styles.filterLabel}>
              {activeFilterCount} filter{activeFilterCount === 1 ? '' : 's'} · {total} match{total === 1 ? '' : 'es'}
            </span>
            <button type="button" className={styles.chipClear} onClick={resetFilters}>
              {t('common.reset_all')}
            </button>
          </div>
        )}
      </div>

      {loading ? (
        <Spinner label={t('collection.loading')} style={{ marginTop: 24 }} />
      ) : entries.length === 0 ? (
        <div style={{ fontFamily: sothera.fontMono, fontSize: 13, color: sothera.fgMuted, marginTop: 24, letterSpacing: 1 }}>
          {activeFilterCount > 0 ? (
            <>
              No cards match these filters.{' '}
              <button type="button" className={styles.chipClear} onClick={resetFilters}>{t('common.reset_all')}</button>
            </>
          ) : t('collection.empty')}
        </div>
      ) : (
        <>
          {isMobile ? (
            <div>
              {entries.map(entry => (
                <Panel key={entry.id} className={styles.mobileCard}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                    <CardHoverPreview card={entry.card}>
                      <a href={scryfallUrl(entry.card)} target="_blank" rel="noopener noreferrer" className={styles.cardLink}>
                        <strong>{entry.card.name}</strong>
                      </a>
                    </CardHoverPreview>
                    <CardmarketButton cardName={entry.card.name} />
                  </div>
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
                <div>{t('col.name')}</div><div>{t('col.copies')}</div><div>{t('col.in_decks')}</div><div>{t('col.finish')}</div><div>{t('col.edition')}</div><div>{t('col.lang')}</div><div style={{ textAlign: 'right' }}>{t('col.eur')}</div>
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
                        <CardmarketButton cardName={entry.card.name} />
                        {entry.cardmarket_listing_count > 0 && (
                          <span
                            title={t('collection.listed_on_cardmarket', { qty: String(entry.cardmarket_listed_qty) })}
                            style={{ marginLeft: 6, fontSize: 11, cursor: 'default', color: sothera.fgFaint }}
                          >
                            🛒{entry.cardmarket_listed_qty > 1 ? entry.cardmarket_listed_qty : ''}
                          </span>
                        )}
                        {entry.archidekt_tags && (
                          <span style={{ marginLeft: 6, fontSize: 9, fontFamily: sothera.fontMono, padding: '1px 5px', letterSpacing: 0.5, border: `1px solid ${sothera.glassBorder}`, color: sothera.fgFaint }}>{entry.archidekt_tags}</span>
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
                          <CardmarketButton cardName={entry.card.name} />
                          {entry.cardmarket_listing_count > 0 && (
                            <span
                              title={t('collection.listed_on_cardmarket', { qty: String(entry.cardmarket_listed_qty) })}
                              style={{ marginLeft: 6, fontSize: 11, cursor: 'default', color: sothera.fgFaint }}
                            >
                              🛒{entry.cardmarket_listed_qty > 1 ? entry.cardmarket_listed_qty : ''}
                            </span>
                          )}
                          {entry.archidekt_tags && (
                            <span style={{ marginLeft: 6, fontSize: 9, fontFamily: sothera.fontMono, padding: '1px 5px', letterSpacing: 0.5, border: `1px solid ${sothera.glassBorder}`, color: sothera.fgFaint }}>{entry.archidekt_tags}</span>
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
