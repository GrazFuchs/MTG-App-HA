import { useEffect, useState, useCallback } from 'react';
import { makeStyles } from '@griffel/react';
import {
  Spinner,
  Button,
  Input,
  Select,
  Dialog,
  DialogSurface,
  DialogTitle,
  DialogBody,
  DialogActions,
  DialogContent,
} from '@fluentui/react-components';
import {
  Search24Regular,
  ChevronLeft24Regular,
  ChevronRight24Regular,
  ChevronDoubleLeft20Regular,
  ChevronDoubleRight20Regular,
} from '@fluentui/react-icons';
import { api, DuplicateEntry } from '../api';
import { sothera } from '../theme/sothera';
import { useAccent } from '../main';
import { Panel, PageHeader } from '../components/sothera';

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
  gridHeader: {
    display: 'grid',
    gridTemplateColumns: '44px 2fr 1.2fr 70px 70px 70px 90px 90px 80px',
    padding: '4px 0 14px',
    borderBottom: `1px solid ${sothera.headerBorder}`,
    fontFamily: sothera.fontMono,
    fontSize: '9px',
    letterSpacing: '2px',
    color: sothera.fgFaint,
    textTransform: 'uppercase',
  },
  gridRow: {
    display: 'grid',
    gridTemplateColumns: '44px 2fr 1.2fr 70px 70px 70px 90px 90px 80px',
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
});

export default function Duplicates() {
  const styles = useStyles();
  const { accent } = useAccent();
  const [items, setItems] = useState<DuplicateEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(100);
  const [loading, setLoading] = useState(true);
  const [searchInput, setSearchInput] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [dialogOpen, setDialogOpen] = useState(false);
  const [selectedCard, setSelectedCard] = useState<DuplicateEntry | null>(null);
  const [listingQty, setListingQty] = useState(1);
  const [listingPrice, setListingPrice] = useState('');
  const [listingCondition, setListingCondition] = useState('NM');
  const [listingLanguage, setListingLanguage] = useState('English');
  const [submitting, setSubmitting] = useState(false);

  const load = useCallback((q: string, currentPage: number) => {
    setLoading(true);
    const params = new URLSearchParams();
    if (q) params.set('search', q);
    params.set('page', String(currentPage));
    params.set('page_size', String(pageSize));
    api.getDuplicates(params)
      .then(res => { setItems(res.items); setTotal(res.total); })
      .catch(() => { setItems([]); setTotal(0); })
      .finally(() => setLoading(false));
  }, [pageSize]);

  useEffect(() => { load(searchQuery, page); }, [load, searchQuery, page]);

  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const handleSearch = () => { setPage(1); setSearchQuery(searchInput.trim()); };

  const openListingDialog = (card: DuplicateEntry) => {
    setSelectedCard(card);
    setListingQty(card.extras);
    setListingPrice(card.price_eur || '0');
    setListingCondition('NM');
    setListingLanguage('English');
    setDialogOpen(true);
  };

  const createListing = async () => {
    if (!selectedCard) return;
    setSubmitting(true);
    try {
      await api.addCardmarketListing({
        card_name: selectedCard.card_name,
        set_name: selectedCard.set_name,
        set_code: selectedCard.set_code,
        quantity: listingQty,
        price: parseFloat(listingPrice) || 0,
        condition: listingCondition,
        language: listingLanguage,
        rarity: selectedCard.rarity,
      });
      setDialogOpen(false);
    } catch { /* ignore */ }
    setSubmitting(false);
  };

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
      </div>

      {loading ? (
        <Spinner label="Loading duplicates..." style={{ marginTop: 24 }} />
      ) : items.length === 0 ? (
        <div style={{ fontFamily: sothera.fontMono, fontSize: 13, color: sothera.fgMuted, marginTop: 24, letterSpacing: 1 }}>No duplicate cards found.</div>
      ) : (
        <>
          <Panel>
            <div className={styles.gridHeader}>
              <div /><div>CARD</div><div>SET</div><div>OWNED</div><div>DECKS</div><div>EXTRA</div><div style={{ textAlign: 'right' }}>EUR</div><div style={{ textAlign: 'right' }}>VALUE</div><div />
            </div>
            {items.map((item, i) => (
              <div key={i} className={styles.gridRow} style={{ borderBottom: i < items.length - 1 ? `1px solid ${sothera.rowBorder}` : 'none' }}>
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
                </div>
                <div style={{ fontFamily: sothera.fontMono, fontSize: 11, color: sothera.fgMuted, letterSpacing: 0.5 }}>{item.set_name} ({item.set_code.toUpperCase()})</div>
                <div style={{ fontFamily: sothera.fontDisplay, fontWeight: 600, color: sothera.fg, fontFeatureSettings: '"tnum"' }}>{item.total_copies}</div>
                <div style={{ fontFamily: sothera.fontMono, fontSize: 11, color: sothera.fgMuted }}>{item.in_decks}</div>
                <div>
                  <span style={{ fontFamily: sothera.fontMono, fontSize: 10, padding: '2px 8px', letterSpacing: 1.5, borderWidth: 1, borderStyle: 'solid', borderColor: accent.oklch, color: accent.oklch }}>
                    {item.extras}
                  </span>
                </div>
                <div style={{ textAlign: 'right', fontFamily: sothera.fontDisplay, fontWeight: 600, color: sothera.fg, fontFeatureSettings: '"tnum"' }}>{item.price_eur ? `€${item.price_eur}` : '—'}</div>
                <div style={{ textAlign: 'right', fontFamily: sothera.fontDisplay, fontWeight: 600, color: sothera.fg, fontFeatureSettings: '"tnum"' }}>{item.price_eur ? `€${(parseFloat(item.price_eur) * item.extras).toFixed(2)}` : '—'}</div>
                <div>
                  <Button size="small" appearance="primary" onClick={() => openListingDialog(item)}>Sell</Button>
                </div>
              </div>
            ))}
          </Panel>
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
        <DialogSurface>
          <DialogTitle>Create Cardmarket Listing</DialogTitle>
          <DialogBody>
            <DialogContent>
              {selectedCard && (
                <>
                  <div style={{ fontWeight: 600, color: sothera.fg }}>{selectedCard.card_name} <span style={{ fontFamily: sothera.fontMono, fontSize: 11, color: sothera.fgMuted }}>— {selectedCard.set_name}</span></div>
                  <div className={styles.formRow}>
                    <div>
                      <div style={{ fontFamily: sothera.fontMono, fontSize: 10, letterSpacing: 1.5, color: sothera.fgFaint, textTransform: 'uppercase' }}>Quantity (max {selectedCard.extras})</div>
                      <Input
                        type="number"
                        min={1}
                        max={selectedCard.extras}
                        value={String(listingQty)}
                        onChange={(_, d) => setListingQty(Math.min(selectedCard.extras, Math.max(1, parseInt(d.value) || 1)))}
                        className={styles.dialogInput}
                      />
                    </div>
                    <div>
                      <div style={{ fontFamily: sothera.fontMono, fontSize: 10, letterSpacing: 1.5, color: sothera.fgFaint, textTransform: 'uppercase' }}>Price (EUR)</div>
                      <Input
                        value={listingPrice}
                        onChange={(_, d) => setListingPrice(d.value)}
                        className={styles.dialogInput}
                      />
                    </div>
                  </div>
                  <div className={styles.formRow}>
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
            <Button appearance="primary" onClick={createListing} disabled={submitting}>
              {submitting ? 'Creating...' : 'Create Listing'}
            </Button>
          </DialogActions>
        </DialogSurface>
      </Dialog>
    </div>
  );
}
