import { useEffect, useState, useCallback } from 'react';
import {
  makeStyles,
  tokens,
  Title2,
  Body1,
  Caption1,
  Spinner,
  Button,
  Input,
  Select,
  Table,
  TableHeader,
  TableRow,
  TableHeaderCell,
  TableBody,
  TableCell,
  Badge,
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
    minWidth: '140px',
  },
  tableWrap: {
    marginTop: '16px',
    overflowX: 'auto',
  },
  cardLink: {
    color: tokens.colorNeutralForeground1,
    textDecoration: 'none',
    '&:hover': {
      textDecoration: 'underline',
      color: tokens.colorBrandForeground1,
    },
  },
  cardImg: {
    width: '32px',
    height: '44px',
    borderRadius: '4px',
    objectFit: 'cover',
    verticalAlign: 'middle',
    marginRight: '8px',
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
  dialogInput: {
    width: '100%',
    marginTop: '8px',
  },
  formRow: {
    display: 'flex',
    gap: '12px',
    marginTop: '8px',
    flexWrap: 'wrap',
  },
});

export default function Duplicates() {
  const styles = useStyles();
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
      <Title2>Duplicates ({total} cards with extras)</Title2>
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
        <Body1 style={{ marginTop: 24 }}>No duplicate cards found.</Body1>
      ) : (
        <>
          <div className={styles.tableWrap}>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHeaderCell>Card</TableHeaderCell>
                  <TableHeaderCell>Set</TableHeaderCell>
                  <TableHeaderCell>Owned</TableHeaderCell>
                  <TableHeaderCell>In Decks</TableHeaderCell>
                  <TableHeaderCell>Extras</TableHeaderCell>
                  <TableHeaderCell>Price (EUR)</TableHeaderCell>
                  <TableHeaderCell>Extra Value</TableHeaderCell>
                  <TableHeaderCell />
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((item, i) => (
                  <TableRow key={i}>
                    <TableCell>
                      {item.image_uri && <img src={item.image_uri} alt="" className={styles.cardImg} />}
                      <a
                        href={`https://scryfall.com/card/${item.set_code.toLowerCase()}/${item.collector_number}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className={styles.cardLink}
                      >
                        {item.card_name}
                      </a>
                    </TableCell>
                    <TableCell>
                      <Caption1>{item.set_name} ({item.set_code.toUpperCase()})</Caption1>
                    </TableCell>
                    <TableCell>{item.total_copies}</TableCell>
                    <TableCell>{item.in_decks}</TableCell>
                    <TableCell>
                      <Badge appearance="filled" color="warning">{item.extras}</Badge>
                    </TableCell>
                    <TableCell>{item.price_eur ? `€${item.price_eur}` : '—'}</TableCell>
                    <TableCell>
                      {item.price_eur ? `€${(parseFloat(item.price_eur) * item.extras).toFixed(2)}` : '—'}
                    </TableCell>
                    <TableCell>
                      <Button size="small" appearance="primary" onClick={() => openListingDialog(item)}>
                        Sell
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          <div className={styles.pagination}>
            <Button icon={<ChevronDoubleLeft20Regular />} appearance="subtle" size="small" disabled={page <= 1} onClick={() => setPage(1)} />
            <Button icon={<ChevronLeft24Regular />} appearance="subtle" size="small" disabled={page <= 1} onClick={() => setPage(p => Math.max(1, p - 1))} />
            <Caption1 className={styles.pageInfo}>Page {page} of {totalPages} ({total} entries)</Caption1>
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
                  <Body1><strong>{selectedCard.card_name}</strong> — {selectedCard.set_name}</Body1>
                  <div className={styles.formRow}>
                    <div>
                      <Caption1>Quantity (max {selectedCard.extras})</Caption1>
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
                      <Caption1>Price (EUR)</Caption1>
                      <Input
                        value={listingPrice}
                        onChange={(_, d) => setListingPrice(d.value)}
                        className={styles.dialogInput}
                      />
                    </div>
                  </div>
                  <div className={styles.formRow}>
                    <div>
                      <Caption1>Condition</Caption1>
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
                      <Caption1>Language</Caption1>
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
