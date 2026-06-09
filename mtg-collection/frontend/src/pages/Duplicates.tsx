import { useState, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { makeStyles } from '@griffel/react';
import {
  Spinner,
  Button,
  Input,
  Select,
  Tooltip,
  Dialog,
  DialogSurface,
  DialogTitle,
  DialogBody,
  DialogActions,
  DialogContent,
  Checkbox,
} from '@fluentui/react-components';
import {
  Search24Regular,
  ChevronLeft24Regular,
  ChevronRight24Regular,
  ChevronDoubleLeft20Regular,
  ChevronDoubleRight20Regular,
  ArrowUp16Regular,
  ArrowDown16Regular,
} from '@fluentui/react-icons';
import { api, DuplicateEntry, DuplicatePrinting, CollectionSet } from '../api';
import { sothera } from '../theme/sothera';
import { useAccent } from '../main';
import { Panel, PageHeader } from '../components/sothera';

const COLOR_OPTIONS: { value: string; label: string }[] = [
  { value: '', label: 'All Colors' },
  { value: 'W', label: '⚪ White' },
  { value: 'U', label: '🔵 Blue' },
  { value: 'B', label: '⚫ Black' },
  { value: 'R', label: '🔴 Red' },
  { value: 'G', label: '🟢 Green' },
  { value: 'MONO', label: '◐ Monocolor' },
  { value: 'M', label: '🌈 Multicolor' },
  { value: 'C', label: '◆ Colorless' },
  { value: 'L', label: '🟤 Land' },
];

const SORT_OPTIONS: { value: string; label: string }[] = [
  { value: 'extras_value_desc', label: 'Value desc' },
  { value: 'extras_desc', label: 'Extras desc' },
  { value: 'name_asc', label: 'Name asc' },
  { value: 'set_asc', label: 'Set asc' },
  { value: 'color_asc', label: 'Color asc' },
];

const useStyles = makeStyles({
  controls: {
    display: 'flex',
    gap: '12px',
    marginBottom: '16px',
    flexWrap: 'wrap',
  },
  input: {
    minWidth: '200px',
    flex: 1,
    maxWidth: '360px',
  },
  filterSelect: {
    minWidth: '140px',
  },
  gridHeader: {
    display: 'grid',
    gridTemplateColumns: '44px 2fr 1.2fr 70px 70px 70px 90px 100px 80px',
    padding: '4px 0 14px',
    borderBottom: `1px solid ${sothera.headerBorder}`,
    fontFamily: sothera.fontMono,
    fontSize: '9px',
    letterSpacing: '2px',
    color: sothera.fgFaint,
    textTransform: 'uppercase',
  },
  sortableHeader: {
    cursor: 'pointer',
    userSelect: 'none' as const,
    display: 'flex',
    alignItems: 'center',
    gap: '2px',
    ':hover': {
      color: sothera.fg,
    },
  },
  gridRow: {
    display: 'grid',
    gridTemplateColumns: '44px 2fr 1.2fr 70px 70px 70px 90px 100px 80px',
    padding: '12px 0',
    fontSize: '13px',
    alignItems: 'center',
  },
  cardLink: {
    color: sothera.fg,
    textDecoration: 'none',
    fontWeight: 500,
    ':hover': {
      textDecoration: 'underline',
    },
  },
  cardImg: {
    width: '32px',
    height: '44px',
    borderRadius: '4px',
    objectFit: 'cover' as const,
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
  formRow: {
    display: 'flex',
    gap: '12px',
    marginTop: '8px',
    flexWrap: 'wrap',
  },
  dialogInput: {
    width: '100%',
    marginTop: '8px',
  },
  printingRow: {
    display: 'grid',
    gridTemplateColumns: '1fr 80px 80px 80px 120px',
    alignItems: 'center',
    gap: '8px',
    padding: '8px 0',
    borderBottom: `1px solid ${sothera.rowBorder}`,
    fontSize: '12px',
  },
  printingHeader: {
    display: 'grid',
    gridTemplateColumns: '1fr 80px 80px 80px 120px',
    gap: '8px',
    padding: '4px 0 8px',
    fontFamily: sothera.fontMono,
    fontSize: '9px',
    letterSpacing: '1.5px',
    color: sothera.fgFaint,
    textTransform: 'uppercase',
  },
});

function DuplicateRow({ item, onSell, accent, i, total }: { item: DuplicateEntry; onSell: (item: DuplicateEntry) => void; accent: any; i: number; total: number }) {
  const styles = useStyles();
  const price = item.is_foil ? (item.price_eur_foil || item.price_eur) : item.price_eur;
  const extraValue = price ? (parseFloat(price) * item.extras_after_listings).toFixed(2) : null;
  return (
    <div className={styles.gridRow} style={{ borderBottom: i < total - 1 ? `1px solid ${sothera.rowBorder}` : 'none' }}>
      <div>{item.image_uri && <img src={item.image_uri} alt="" className={styles.cardImg} />}</div>
      <div>
        <a
          href={`https://scryfall.com/card/${item.set_code.toLowerCase()}/${item.collector_number}`}
          target="_blank"
          rel="noopener noreferrer"
          className={styles.cardLink}
        >
          {item.card_name}
        </a>
        {item.is_foil && <span style={{ marginLeft: 6, fontSize: 10, color: '#c9a227', fontWeight: 600 }}>◆ Foil</span>}
      </div>
      <div style={{ fontFamily: sothera.fontMono, fontSize: 11, color: sothera.fgMuted, letterSpacing: 0.5 }}>{item.set_name} ({item.set_code.toUpperCase()})</div>
      <div style={{ fontFamily: sothera.fontDisplay, fontWeight: 600, color: sothera.fg, fontFeatureSettings: '"tnum"' }}>{item.total_copies}</div>
      <div style={{ fontFamily: sothera.fontMono, fontSize: 11, color: sothera.fgMuted }}>{item.in_decks}</div>
      <div>
        <Tooltip content={`Total extras: ${item.extras}${item.listed_quantity > 0 ? `, ${item.listed_quantity} already listed` : ''}`} relationship="description">
          <span style={{ fontFamily: sothera.fontMono, fontSize: 10, padding: '2px 8px', letterSpacing: 1.5, borderWidth: 1, borderStyle: 'solid', borderColor: accent.oklch, color: accent.oklch }}>
            {item.extras_after_listings}
          </span>
        </Tooltip>
        {item.listed_quantity > 0 && <span style={{ marginLeft: 4, fontSize: 9, color: sothera.fgFaint }}>({item.listed_quantity} listed)</span>}
      </div>
      <div style={{ textAlign: 'right', fontFamily: sothera.fontDisplay, fontWeight: 600, color: sothera.fg, fontFeatureSettings: '"tnum"' }}>{price ? `€${price}` : '—'}</div>
      <div style={{ textAlign: 'right', fontFamily: sothera.fontDisplay, fontWeight: 600, color: sothera.fg, fontFeatureSettings: '"tnum"', paddingRight: 16 }}>{extraValue ? `€${extraValue}` : '—'}</div>
      <div style={{ paddingLeft: 4 }}>
        <Button size="small" appearance="primary" onClick={() => onSell(item)}>Sell</Button>
      </div>
    </div>
  );
}

export default function Duplicates() {
  const styles = useStyles();
  const { accent } = useAccent();
  const [searchParams, setSearchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [pageSize] = useState(100);
  const [searchInput, setSearchInput] = useState(searchParams.get('search') || '');
  const [dialogOpen, setDialogOpen] = useState(false);
  const [selectedCard, setSelectedCard] = useState<DuplicateEntry | null>(null);
  const [printings, setPrintings] = useState<DuplicatePrinting[]>([]);
  const [printingsLoading, setPrintingsLoading] = useState(false);
  const [bulkEntries, setBulkEntries] = useState<{ printing: DuplicatePrinting; qty: number; price: string }[]>([]);
  const [listingCondition, setListingCondition] = useState('NM');
  const [listingLanguage, setListingLanguage] = useState('English');
  const [submitting, setSubmitting] = useState(false);
  const [includeListed, setIncludeListed] = useState(false);

  const colorFilter = searchParams.get('color') || '';
  const setFilter = searchParams.get('set') || '';
  const sortParam = searchParams.get('sort') || 'extras_value_desc';

  const [sortBy, sortDir] = (() => {
    const last = sortParam.lastIndexOf('_');
    const dir = sortParam.slice(last + 1);
    const by = sortParam.slice(0, last);
    return [by, dir];
  })();

  const setParam = (key: string, value: string) => {
    const next = new URLSearchParams(searchParams);
    if (value) next.set(key, value); else next.delete(key);
    next.delete('page');
    setSearchParams(next);
    setPage(1);
  };

  const toggleSort = (col: string) => {
    const current = sortParam;
    const newDir = current === `${col}_desc` ? 'asc' : 'desc';
    setParam('sort', `${col}_${newDir}`);
  };

  const SortIcon = ({ col }: { col: string }) => {
    if (sortBy !== col) return null;
    return sortDir === 'desc' ? <ArrowDown16Regular /> : <ArrowUp16Regular />;
  };

  const { data: availableSets = [] } = useQuery<CollectionSet[]>({
    queryKey: ['duplicate-sets', searchParams.get('search') || '', colorFilter],
    queryFn: () => {
      const p = new URLSearchParams();
      const q = searchParams.get('search') || '';
      if (q) p.set('search', q);
      if (colorFilter) p.set('color', colorFilter);
      return api.getDuplicateSets(p);
    },
    staleTime: 60_000,
  });

  const duplicatesParams = useMemo(() => {
    const params = new URLSearchParams();
    const q = searchParams.get('search') || '';
    if (q) params.set('search', q);
    if (colorFilter) params.set('color', colorFilter);
    if (setFilter) params.set('set_code', setFilter);
    params.set('sort_by', sortBy);
    params.set('sort_dir', sortDir);
    params.set('page', String(page));
    params.set('page_size', String(pageSize));
    if (includeListed) params.set('include_listed', 'true');
    return params;
  }, [searchParams, colorFilter, setFilter, sortBy, sortDir, page, pageSize, includeListed]);

  const { data: duplicatesData, isLoading: loading } = useQuery({
    queryKey: ['duplicates', duplicatesParams.toString()],
    queryFn: () => api.getDuplicates(duplicatesParams),
    staleTime: 60_000,
  });

  const items = duplicatesData?.items ?? [];
  const total = duplicatesData?.total ?? 0;

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  const handleSearch = () => {
    setParam('search', searchInput.trim());
  };

  const openListingDialog = async (card: DuplicateEntry) => {
    setSelectedCard(card);
    setDialogOpen(true);
    setPrintingsLoading(true);
    try {
      const data = await api.getDuplicatePrintings(card.card_name);
      setPrintings(data);
      setBulkEntries(data.map(p => ({
        printing: p,
        qty: 0,
        price: p.is_foil ? (p.price_eur_foil || p.price_eur || '0') : (p.price_eur || '0'),
      })));
    } catch {
      setPrintings([]);
      setBulkEntries([]);
    }
    setPrintingsLoading(false);
  };

  const updateBulkQty = (idx: number, qty: number) => {
    setBulkEntries(prev => prev.map((e, i) => i === idx ? { ...e, qty } : e));
  };

  const updateBulkPrice = (idx: number, price: string) => {
    setBulkEntries(prev => prev.map((e, i) => i === idx ? { ...e, price } : e));
  };

  const createBulkListings = async () => {
    const toCreate = bulkEntries.filter(e => e.qty > 0);
    if (toCreate.length === 0) return;
    setSubmitting(true);
    try {
      for (const entry of toCreate) {
        await api.addCardmarketListing({
          card_name: entry.printing.card_name,
          set_name: entry.printing.set_name,
          set_code: entry.printing.set_code,
          quantity: entry.qty,
          price: parseFloat(entry.price) || 0,
          condition: listingCondition,
          language: listingLanguage,
          is_foil: entry.printing.is_foil,
          rarity: entry.printing.rarity,
        });
      }
      setDialogOpen(false);
      queryClient.invalidateQueries({ queryKey: ['cardmarket-listings'] });
      queryClient.invalidateQueries({ queryKey: ['cardmarket-stats'] });
      queryClient.invalidateQueries({ queryKey: ['duplicates'] });
      queryClient.invalidateQueries({ queryKey: ['duplicate-sets'] });
    } catch { /* ignore */ }
    setSubmitting(false);
  };

  const renderItems = (itemList: DuplicateEntry[]) => (
    <>
      <div className={styles.gridHeader}>
        <div />
        <div className={styles.sortableHeader} onClick={() => toggleSort('name')}>CARD <SortIcon col="name" /></div>
        <div className={styles.sortableHeader} onClick={() => toggleSort('set')}>SET <SortIcon col="set" /></div>
        <div>OWNED</div>
        <div>DECKS</div>
        <div className={styles.sortableHeader} onClick={() => toggleSort('extras')}>EXTRA <SortIcon col="extras" /></div>
        <div className={styles.sortableHeader} onClick={() => toggleSort('extras_value')} style={{ textAlign: 'right' }}>EUR <SortIcon col="extras_value" /></div>
        <div style={{ textAlign: 'right' }}>VALUE</div>
        <div />
      </div>
      {itemList.map((item, i) => (
        <DuplicateRow key={`${item.card_id}-${item.set_code}-${item.is_foil}`} item={item} onSell={openListingDialog} accent={accent} i={i} total={itemList.length} />
      ))}
    </>
  );

  const totalBulkQty = bulkEntries.reduce((s, e) => s + e.qty, 0);

  return (
    <div>
      <PageHeader
        eyebrow={`◫ SURPLUS · ${total} CANDIDATES`}
        title="Duplicates"
        accent={accent.oklch}
      />

      <div className={styles.controls}>
        <Input
          placeholder="Search duplicates..."
          contentBefore={<Search24Regular />}
          value={searchInput}
          onChange={(_, d) => setSearchInput(d.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          className={styles.input}
        />
        <Button onClick={handleSearch}>Search</Button>
        <Select value={colorFilter} onChange={(_, d) => setParam('color', d.value)} className={styles.filterSelect}>
          {COLOR_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
        </Select>
        <Select value={setFilter} onChange={(_, d) => setParam('set', d.value)} className={styles.filterSelect}>
          <option value="">All Sets</option>
          {availableSets.map(s => <option key={s.set_code} value={s.set_code}>{s.set_name}</option>)}
        </Select>
        <Select value={sortParam} onChange={(_, d) => setParam('sort', d.value)} className={styles.filterSelect}>
          {SORT_OPTIONS.map(o => <option key={o.value} value={o.value}>Sort: {o.label}</option>)}
        </Select>
        <Checkbox
          checked={includeListed}
          onChange={(_, d) => { setIncludeListed(!!d.checked); setPage(1); }}
          label="Show fully listed"
        />
      </div>

      {loading ? (
        <Spinner label="Loading duplicates..." style={{ marginTop: 24 }} />
      ) : items.length === 0 ? (
        <div style={{ fontFamily: sothera.fontMono, fontSize: 13, color: sothera.fgMuted, marginTop: 24, letterSpacing: 1 }}>No duplicate cards found.</div>
      ) : (
        <>
          <Panel>{renderItems(items)}</Panel>
          <div className={styles.pagination}>
            <Button icon={<ChevronDoubleLeft20Regular />} appearance="subtle" size="small" disabled={page <= 1} onClick={() => setPage(1)} />
            <Button icon={<ChevronLeft24Regular />} appearance="subtle" size="small" disabled={page <= 1} onClick={() => setPage(p => Math.max(1, p - 1))} />
            <span className={styles.pageInfo}>Page {page} of {totalPages} ({total} entries)</span>
            <Button icon={<ChevronRight24Regular />} appearance="subtle" size="small" disabled={page >= totalPages} onClick={() => setPage(p => Math.min(totalPages, p + 1))} />
            <Button icon={<ChevronDoubleRight20Regular />} appearance="subtle" size="small" disabled={page >= totalPages} onClick={() => setPage(totalPages)} />
          </div>
        </>
      )}

      <Dialog open={dialogOpen} onOpenChange={(_, d) => setDialogOpen(d.open)}>
        <DialogSurface style={{ maxWidth: 680 }}>
          <DialogTitle>Sell: {selectedCard?.card_name}</DialogTitle>
          <DialogBody>
            <DialogContent>
              {printingsLoading ? (
                <Spinner label="Loading printings..." size="small" />
              ) : (
                <>
                  <div style={{ marginBottom: 12, fontFamily: sothera.fontMono, fontSize: 10, color: sothera.fgFaint, letterSpacing: 1.5 }}>
                    SELECT PRINTINGS TO LIST ({printings.length} available)
                  </div>
                  <div className={styles.printingHeader}>
                    <div>PRINTING</div>
                    <div>COPIES</div>
                    <div>LISTED</div>
                    <div>QTY</div>
                    <div>PRICE €</div>
                  </div>
                  {bulkEntries.map((entry, idx) => {
                    const p = entry.printing;
                    const maxQty = Math.max(p.total_copies - p.listed_for_printing, 0);
                    return (
                      <div key={`${p.card_id}-${p.set_code}-${p.is_foil}`} className={styles.printingRow}>
                        <div>
                          <span style={{ fontWeight: 500 }}>{p.set_name}</span>
                          <span style={{ fontFamily: sothera.fontMono, fontSize: 10, color: sothera.fgMuted, marginLeft: 6 }}>({p.set_code.toUpperCase()})</span>
                          {p.is_foil && <span style={{ marginLeft: 6, fontSize: 10, color: '#c9a227', fontWeight: 600 }}>◆ Foil</span>}
                        </div>
                        <div style={{ fontFamily: sothera.fontMono, fontSize: 12 }}>{p.total_copies}</div>
                        <div style={{ fontFamily: sothera.fontMono, fontSize: 12, color: sothera.fgMuted }}>{p.listed_for_printing}</div>
                        <div>
                          <Input
                            type="number"
                            min={0}
                            max={maxQty}
                            value={String(entry.qty)}
                            onChange={(_, d) => updateBulkQty(idx, Math.min(maxQty, Math.max(0, parseInt(d.value) || 0)))}
                            style={{ width: 60 }}
                            size="small"
                          />
                        </div>
                        <div>
                          <Input
                            value={entry.price}
                            onChange={(_, d) => updateBulkPrice(idx, d.value)}
                            style={{ width: 80 }}
                            size="small"
                          />
                        </div>
                      </div>
                    );
                  })}
                  <div className={styles.formRow} style={{ marginTop: 16 }}>
                    <div>
                      <div style={{ fontFamily: sothera.fontMono, fontSize: 10, letterSpacing: 1.5, color: sothera.fgFaint, textTransform: 'uppercase' }}>Condition</div>
                      <Select value={listingCondition} onChange={(_, d) => setListingCondition(d.value)} className={styles.dialogInput}>
                        <option value="MT">Mint</option>
                        <option value="NM">Near Mint</option>
                        <option value="EX">Excellent</option>
                        <option value="GD">Good</option>
                        <option value="LP">Light Played</option>
                        <option value="PL">Played</option>
                        <option value="PO">Poor</option>
                      </Select>
                    </div>
                    <div>
                      <div style={{ fontFamily: sothera.fontMono, fontSize: 10, letterSpacing: 1.5, color: sothera.fgFaint, textTransform: 'uppercase' }}>Language</div>
                      <Select value={listingLanguage} onChange={(_, d) => setListingLanguage(d.value)} className={styles.dialogInput}>
                        <option>English</option>
                        <option>German</option>
                        <option>French</option>
                        <option>Spanish</option>
                        <option>Italian</option>
                        <option>Japanese</option>
                        <option>Chinese</option>
                        <option>Korean</option>
                        <option>Portuguese</option>
                        <option>Russian</option>
                      </Select>
                    </div>
                  </div>
                </>
              )}
            </DialogContent>
          </DialogBody>
          <DialogActions>
            <Button appearance="secondary" onClick={() => setDialogOpen(false)}>Cancel</Button>
            <Button appearance="primary" onClick={createBulkListings} disabled={submitting || totalBulkQty === 0}>
              {submitting ? 'Creating...' : `Create ${totalBulkQty} Listing${totalBulkQty !== 1 ? 's' : ''}`}
            </Button>
          </DialogActions>
        </DialogSurface>
      </Dialog>
    </div>
  );
}
