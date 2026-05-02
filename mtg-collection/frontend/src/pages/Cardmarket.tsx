import { useEffect, useState, useRef } from 'react';
import {
  makeStyles,
  tokens,
  Title2,
  Title3,
  Body1,
  Body2,
  Caption1,
  Spinner,
  Input,
  Button,
  Card,
  CardHeader,
  Badge,
  MessageBar,
  MessageBarBody,
  Table,
  TableHeader,
  TableRow,
  TableHeaderCell,
  TableBody,
  TableCell,
  Divider,
  Subtitle2,
} from '@fluentui/react-components';
import { ArrowUpload24Regular, Search24Regular, ArrowDownload24Regular, ChartMultiple24Regular } from '@fluentui/react-icons';
import { api, CardmarketListing, PriceAlert, PriceHistoryEntry } from '../api';
import { Sparkline } from '../components/Sparkline';

const useStyles = makeStyles({
  controls: {
    display: 'flex',
    gap: '12px',
    marginTop: '12px',
    flexWrap: 'wrap',
    alignItems: 'center',
  },
  statsRow: {
    display: 'flex',
    gap: '16px',
    marginTop: '12px',
    flexWrap: 'wrap',
  },
  statCard: {
    padding: '12px 16px',
    minWidth: '120px',
  },
  tableWrap: {
    marginTop: '16px',
    overflowX: 'auto',
  },
  alertsSection: {
    marginTop: '24px',
    marginBottom: '24px',
  },
  alertCard: {
    padding: '12px 16px',
    marginTop: '8px',
  },
  alertGroupHeader: {
    cursor: 'pointer',
    userSelect: 'none',
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    padding: '8px 0',
  },
  alertGroupChevron: {
    display: 'inline-block',
    transition: 'transform 0.15s ease',
    fontSize: '10px',
  },
  alertGroupChevronOpen: {
    transform: 'rotate(90deg)',
  },
  alertRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: '12px',
    flexWrap: 'wrap',
  },
  sparklineCell: {
    position: 'relative',
  },
  sparklinePopup: {
    position: 'fixed',
    zIndex: 10000,
    background: tokens.colorNeutralBackground1,
    border: `1px solid ${tokens.colorNeutralStroke1}`,
    borderRadius: '8px',
    padding: '8px 12px',
    boxShadow: tokens.shadow16,
    pointerEvents: 'none',
  },
});

const PRICE_TIERS = [
  { max: 0.5, label: 'Under €0.50', emoji: '🟤' },
  { max: 1, label: '€0.50 – €1.00', emoji: '⚪' },
  { max: 2, label: '€1.00 – €2.00', emoji: '🟢' },
  { max: 5, label: '€2.00 – €5.00', emoji: '🔵' },
  { max: 10, label: '€5.00 – €10.00', emoji: '🟣' },
  { max: 20, label: '€10.00 – €20.00', emoji: '🟠' },
  { max: Infinity, label: '€20.00+', emoji: '🔴' },
];

function getPriceTier(trend: number): string {
  for (const tier of PRICE_TIERS) {
    if (trend < tier.max) return tier.label;
  }
  return PRICE_TIERS[PRICE_TIERS.length - 1].label;
}

function getPriceTierEmoji(label: string): string {
  return PRICE_TIERS.find(t => t.label === label)?.emoji || '';
}

function PriceCell({ cardName }: { cardName: string }) {
  const styles = useStyles();
  const [history, setHistory] = useState<PriceHistoryEntry[] | null>(null);
  const [show, setShow] = useState(false);
  const [pos, setPos] = useState({ x: 0, y: 0 });
  const timerRef = useRef<ReturnType<typeof setTimeout>>();
  const historyRef = useRef<PriceHistoryEntry[] | null>(null);

  const fetchHistory = async () => {
    if (historyRef.current !== null) return;
    try {
      const products = await api.getMatchedProducts(cardName);
      if (products.length > 0) {
        const h = await api.getPriceHistory(products[0].cm_product_id);
        historyRef.current = h;
        setHistory(h);
      } else {
        historyRef.current = [];
        setHistory([]);
      }
    } catch {
      historyRef.current = [];
      setHistory([]);
    }
  };

  const handleMouseEnter = (e: React.MouseEvent) => {
    const { clientX, clientY } = e;
    timerRef.current = setTimeout(async () => {
      await fetchHistory();
      setPos({ x: clientX + 16, y: clientY - 40 });
      setShow(true);
    }, 300);
  };

  const handleMouseLeave = () => {
    clearTimeout(timerRef.current);
    setShow(false);
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    setPos({ x: e.clientX + 16, y: e.clientY - 40 });
  };

  return (
    <span
      className={styles.sparklineCell}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      onMouseMove={handleMouseMove}
    >
      {cardName}
      {show && history && history.length > 1 && (
        <div className={styles.sparklinePopup} style={{ left: pos.x, top: pos.y }}>
          <Caption1 style={{ display: 'block', marginBottom: 4 }}>30-Day Price Trend</Caption1>
          <Sparkline data={history} width={180} height={48} />
          <Caption1 style={{ display: 'block', marginTop: 4 }}>
            €{history[history.length - 1].trend.toFixed(2)} (latest)
          </Caption1>
        </div>
      )}
    </span>
  );
}

export default function Cardmarket() {
  const styles = useStyles();
  const fileRef = useRef<HTMLInputElement>(null);
  const [listings, setListings] = useState<CardmarketListing[]>([]);
  const [stats, setStats] = useState<{ unique_listings: number; total_quantity: number; total_value: number } | null>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [importing, setImporting] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [msg, setMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [alerts, setAlerts] = useState<PriceAlert[]>([]);
  const [alertsLoading, setAlertsLoading] = useState(false);
  const [syncingPrices, setSyncingPrices] = useState(false);
  const [openAlertGroups, setOpenAlertGroups] = useState<Set<string>>(new Set());

  const load = (q = '') => {
    setLoading(true);
    const params = new URLSearchParams();
    if (q) params.set('search', q);
    params.set('page_size', '100');
    Promise.all([api.getCardmarketListings(params), api.getCardmarketStats()])
      .then(([l, s]) => { setListings(l); setStats(s); })
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  useEffect(() => {
    setAlertsLoading(true);
    api.getPriceAlerts().then(setAlerts).catch(() => {}).finally(() => setAlertsLoading(false));
  }, []);

  const handleImport = async () => {
    const file = fileRef.current?.files?.[0];
    if (!file) return;
    setImporting(true);
    setMsg(null);
    try {
      const result = await api.importCardmarketCSV(file);
      setMsg({ type: 'success', text: `Imported ${result.imported} of ${result.total_rows} listings (${result.errors} errors)` });
      load(search);
    } catch (e: any) {
      setMsg({ type: 'error', text: e.message });
    } finally {
      setImporting(false);
    }
  };

  return (
    <div>
      <Title2>Cardmarket Listings</Title2>

      <div className={styles.controls}>
        <Input
          placeholder="Search listings..."
          contentBefore={<Search24Regular />}
          value={search}
          onChange={(_, d) => setSearch(d.value)}
          onKeyDown={(e) => e.key === 'Enter' && load(search)}
          style={{ minWidth: 200, flex: 1, maxWidth: 400 }}
        />
        <input type="file" ref={fileRef} accept=".csv" style={{ display: 'none' }} onChange={handleImport} />
        <Button
          icon={<ArrowUpload24Regular />}
          appearance="primary"
          onClick={() => fileRef.current?.click()}
          disabled={importing}
        >
          {importing ? 'Importing...' : 'Import CSV'}
        </Button>

        <Button
          icon={<ArrowDownload24Regular />}
          appearance="secondary"
          onClick={async () => {
            setExporting(true);
            setMsg(null);
            try {
              await api.exportCardmarketCSV();
              setMsg({ type: 'success', text: 'CSV exported successfully' });
            } catch (e: any) {
              setMsg({ type: 'error', text: e.message });
            } finally {
              setExporting(false);
            }
          }}
          disabled={exporting || listings.length === 0}
        >
          {exporting ? 'Exporting...' : 'Export CSV'}
        </Button>
        <Button
          icon={<ChartMultiple24Regular />}
          appearance="secondary"
          onClick={async () => {
            setSyncingPrices(true);
            setMsg(null);
            try {
              const result = await api.syncPrices();
              setMsg({ type: 'success', text: `Price sync: ${result.products_matched} products matched, ${result.prices_stored} prices stored` });
              // Reload alerts after price sync
              api.getPriceAlerts().then(setAlerts).catch(() => {});
            } catch (e: any) {
              setMsg({ type: 'error', text: `Price sync failed: ${e.message}` });
            } finally {
              setSyncingPrices(false);
            }
          }}
          disabled={syncingPrices}
        >
          {syncingPrices ? 'Syncing Prices...' : 'Sync Prices'}
        </Button>
      </div>

      {msg && (
        <MessageBar intent={msg.type === 'success' ? 'success' : 'error'} style={{ marginTop: 8 }}>
          <MessageBarBody>{msg.text}</MessageBarBody>
        </MessageBar>
      )}

      {stats && (
        <div className={styles.statsRow}>
          <Card className={styles.statCard}>
            <Caption1>Unique Listings</Caption1>
            <Body1><strong>{stats.unique_listings}</strong></Body1>
          </Card>
          <Card className={styles.statCard}>
            <Caption1>Total Quantity</Caption1>
            <Body1><strong>{stats.total_quantity}</strong></Body1>
          </Card>
          <Card className={styles.statCard}>
            <Caption1>Total Value</Caption1>
            <Body1><strong>€{stats.total_value.toFixed(2)}</strong></Body1>
          </Card>
        </div>
      )}

      {/* Price Alerts */}
      {!alertsLoading && alerts.length > 0 && (
        <div className={styles.alertsSection}>
          <Title3>📈 Price Spike Alerts ({alerts.length})</Title3>
          {(() => {
            // Group alerts by price tier
            const tierMap = new Map<string, PriceAlert[]>();
            for (const tier of PRICE_TIERS) {
              tierMap.set(tier.label, []);
            }
            for (const a of alerts) {
              const tierLabel = getPriceTier(a.trend);
              tierMap.get(tierLabel)!.push(a);
            }
            // Render tiers in reverse order (highest first)
            return [...PRICE_TIERS].reverse()
              .filter(tier => (tierMap.get(tier.label)?.length || 0) > 0)
              .map(tier => {
                const tierAlerts = tierMap.get(tier.label)!;
                const isOpen = openAlertGroups.has(tier.label);
                return (
                  <div key={tier.label} style={{ marginTop: 8 }}>
                    <div
                      className={styles.alertGroupHeader}
                      onClick={() => setOpenAlertGroups(prev => {
                        const next = new Set(prev);
                        if (next.has(tier.label)) next.delete(tier.label);
                        else next.add(tier.label);
                        return next;
                      })}
                    >
                      <span className={`${styles.alertGroupChevron} ${isOpen ? styles.alertGroupChevronOpen : ''}`}>▶</span>
                      <Subtitle2>{tier.emoji} {tier.label} ({tierAlerts.length})</Subtitle2>
                    </div>
                    {isOpen && tierAlerts.map((a, i) => (
                      <Card key={i} className={styles.alertCard}>
                        <div className={styles.alertRow}>
                          <div>
                            <Body2><strong>{a.card_name}</strong> — {a.expansion}</Body2>
                            <Caption1 style={{ display: 'block' }}>{a.suggestion}</Caption1>
                          </div>
                          <div style={{ textAlign: 'right' }}>
                            <Badge appearance="filled" color="danger">+{a.spike_pct}%</Badge>
                            <Caption1 style={{ display: 'block', marginTop: 4 }}>
                              €{a.avg30} → €{a.trend}
                            </Caption1>
                          </div>
                        </div>
                      </Card>
                    ))}
                  </div>
                );
              });
          })()}
        </div>
      )}

      <Divider style={{ margin: '16px 0' }} />

      {loading ? (
        <Spinner label="Loading..." style={{ marginTop: 24 }} />
      ) : listings.length === 0 ? (
        <Body1 style={{ marginTop: 24 }}>No listings. Sync from profile or import a CSV.</Body1>
      ) : (
        <div className={styles.tableWrap}>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHeaderCell>Card</TableHeaderCell>
                <TableHeaderCell>Set</TableHeaderCell>
                <TableHeaderCell>Rarity</TableHeaderCell>
                <TableHeaderCell>Qty</TableHeaderCell>
                <TableHeaderCell>Price</TableHeaderCell>
                <TableHeaderCell>Condition</TableHeaderCell>
                <TableHeaderCell>Language</TableHeaderCell>
                <TableHeaderCell>Reverse Holo</TableHeaderCell>
                <TableHeaderCell>Source</TableHeaderCell>
              </TableRow>
            </TableHeader>
            <TableBody>
              {listings.map((l) => (
                <TableRow key={l.id} style={l.source === 'manual' ? { backgroundColor: 'rgba(255, 183, 77, 0.12)' } : undefined}>
                  <TableCell><PriceCell cardName={l.card_name} /></TableCell>
                  <TableCell>{l.set_name || l.set_code}</TableCell>
                  <TableCell>{l.rarity || '—'}</TableCell>
                  <TableCell>{l.quantity}</TableCell>
                  <TableCell>€{l.price.toFixed(2)}</TableCell>
                  <TableCell>{l.condition_full || l.condition}</TableCell>
                  <TableCell>{l.language}</TableCell>
                  <TableCell>{l.reverse_holo ? <Badge appearance="tint" color="important">Holo</Badge> : '—'}</TableCell>
                  <TableCell>
                    <Badge appearance="tint" color={l.source === 'manual' ? 'warning' : 'brand'}>
                      {l.source || 'import'}
                    </Badge>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
