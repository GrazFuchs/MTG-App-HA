import { useState, useRef, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { makeStyles, shorthands } from '@griffel/react';
import {
  Spinner,
  Input,
  Button,
  MessageBar,
  MessageBarBody,
  Select,
} from '@fluentui/react-components';
import { ArrowUpload24Regular, ArrowDownload24Regular, ChartMultiple24Regular } from '@fluentui/react-icons';
import { api, CardmarketListing, PriceAlert, PriceHistoryEntry, CollectionSet } from '../api';
import { Sparkline } from '../components/Sparkline';
import { CardmarketWorkflowBanner } from '../components/cardmarket/CardmarketWorkflowBanner';
import ListingHealthPanel from '../components/cardmarket/ListingHealthPanel';
import { CardHoverPreview } from '../components/CardHoverPreview';
import { sothera } from '../theme/sothera';
import { useAccent } from '../main';
import { Panel, PageHeader, SectionHeader } from '../components/sothera';

const COLOR_OPTIONS = [
  { value: '', label: 'All Colors' },
  { value: 'W', label: '⚪ White' },
  { value: 'U', label: '🔵 Blue' },
  { value: 'B', label: '⚫ Black' },
  { value: 'R', label: '🔴 Red' },
  { value: 'G', label: '🟢 Green' },
  { value: 'M', label: '🌈 Multicolor' },
  { value: 'C', label: '◆ Colorless' },
  { value: 'L', label: '🟤 Land' },
];

const SORT_OPTIONS = [
  { value: 'source_asc', label: 'Pending first' },
  { value: 'price_desc', label: 'Price desc' },
  { value: 'name_asc', label: 'Name asc' },
  { value: 'set_asc', label: 'Set asc' },
  { value: 'color_asc', label: 'Color asc' },
  { value: 'qty_desc', label: 'Quantity desc' },
];

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

const useStyles = makeStyles({
  controls: {
    display: 'flex',
    gap: '8px',
    marginBottom: '16px',
    flexWrap: 'wrap',
  },
  btn: {
    padding: '10px 16px',
    fontFamily: sothera.fontMono,
    fontSize: '11px',
    letterSpacing: '2px',
    fontWeight: 600,
    cursor: 'pointer',
    ...shorthands.borderWidth('1px'),
    ...shorthands.borderStyle('solid'),
  },
  gridHeader: {
    display: 'grid',
    gridTemplateColumns: '2fr 80px 70px 70px 90px 90px 100px 90px',
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
    gridTemplateColumns: '2fr 80px 70px 70px 90px 90px 100px 90px',
    padding: '14px 0',
    fontSize: '13px',
    alignItems: 'center',
  },
  alertGroupHeader: {
    cursor: 'pointer',
    userSelect: 'none',
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
    padding: '12px 0',
    borderBottom: `1px solid ${sothera.rowBorder}`,
    fontFamily: sothera.fontMono,
    fontSize: '12px',
    letterSpacing: '1px',
    color: sothera.fgMuted,
  },
  sparklinePopup: {
    position: 'fixed',
    zIndex: 10000,
    backgroundColor: sothera.glassBg,
    ...shorthands.borderWidth('1px'),
    ...shorthands.borderStyle('solid'),
    ...shorthands.borderColor(sothera.glassBorder),
    padding: '8px 12px',
    pointerEvents: 'none',
    backdropFilter: 'blur(12px)',
  },
});

function PriceCell({ cardName, accent }: { cardName: string; accent: string }) {
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
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      onMouseMove={handleMouseMove}
      style={{ cursor: 'default' }}
    >
      {cardName}
      {show && history && history.length > 1 && (
        <div className={styles.sparklinePopup} style={{ left: pos.x, top: pos.y }}>
          <div style={{ fontFamily: sothera.fontMono, fontSize: 10, color: sothera.fgFaint, marginBottom: 4, letterSpacing: 1.5, textTransform: 'uppercase' }}>30-DAY TREND</div>
          <Sparkline data={history} width={180} height={48} accent={accent} dot={false} />
          <div style={{ fontFamily: sothera.fontMono, fontSize: 10, color: sothera.fgMuted, marginTop: 4 }}>
            €{history[history.length - 1].trend.toFixed(2)} (latest)
          </div>
        </div>
      )}
    </span>
  );
}

export default function Cardmarket() {
  const styles = useStyles();
  const { accent } = useAccent();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const fileRef = useRef<HTMLInputElement>(null);
  const [searchInput, setSearchInput] = useState(searchParams.get('search') || '');
  const [committedSearch, setCommittedSearch] = useState(searchParams.get('search') || '');
  const [exporting, setExporting] = useState(false);
  const [msg, setMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [openAlertGroups, setOpenAlertGroups] = useState<Set<string>>(new Set());

  const colorFilter = searchParams.get('color') || '';
  const setCodeFilter = searchParams.get('set') || '';
  const sourceFilter = searchParams.get('source') || '';
  const sortParam = searchParams.get('sort') || 'source_asc';

  const [sortBy, sortDir] = (() => {
    const last = sortParam.lastIndexOf('_');
    return [sortParam.slice(0, last), sortParam.slice(last + 1)];
  })();

  const setParam = (key: string, value: string) => {
    const next = new URLSearchParams(searchParams);
    if (value) next.set(key, value); else next.delete(key);
    setSearchParams(next);
  };

  const listingsParams = useMemo(() => {
    const params = new URLSearchParams();
    if (committedSearch) params.set('search', committedSearch);
    if (colorFilter) params.set('color', colorFilter);
    if (setCodeFilter) params.set('set_code', setCodeFilter);
    if (sourceFilter) params.set('source', sourceFilter);
    params.set('sort_by', sortBy);
    params.set('sort_dir', sortDir);
    params.set('page_size', '200');
    return params;
  }, [committedSearch, colorFilter, setCodeFilter, sourceFilter, sortBy, sortDir]);

  const { data: listingsData, isLoading: loading } = useQuery({
    queryKey: ['cardmarket-listings', listingsParams.toString()],
    queryFn: () => api.getCardmarketListings(listingsParams),
    staleTime: 60_000,
  });

  const { data: stats } = useQuery({
    queryKey: ['cardmarket-stats'],
    queryFn: () => api.getCardmarketStats(),
    staleTime: 60_000,
  });

  const { data: availableSets = [] } = useQuery<CollectionSet[]>({
    queryKey: ['collection-sets'],
    queryFn: () => api.getCollectionSets(),
    staleTime: 5 * 60_000,
  });

  const { data: alerts = [], isLoading: alertsLoading } = useQuery<PriceAlert[]>({
    queryKey: ['price-alerts'],
    queryFn: () => api.getPriceAlerts(),
    staleTime: 5 * 60_000,
  });

  const listings = listingsData?.items ?? [];
  const listingsTotal = listingsData?.total ?? 0;

  const importMutation = useMutation({
    mutationFn: (file: File) => api.importCardmarketCSV(file),
    onSuccess: (result) => {
      const details = result.error_details?.length ? `\n${result.error_details[0]}` : '';
      const msgType = result.errors > 0 && result.imported === 0 ? 'error' : 'success';
      setMsg({ type: msgType, text: `Imported ${result.imported} of ${result.total_rows} listings (${result.errors} errors)${details}` });
      queryClient.invalidateQueries({ queryKey: ['cardmarket-listings'] });
      queryClient.invalidateQueries({ queryKey: ['cardmarket-stats'] });
    },
    onError: (e: any) => setMsg({ type: 'error', text: e.message }),
  });

  const syncPricesMutation = useMutation({
    mutationFn: () => api.syncPrices(),
    onSuccess: (result) => {
      setMsg({ type: 'success', text: `Price sync: ${result.products_matched} matched, ${result.prices_stored} stored` });
      queryClient.invalidateQueries({ queryKey: ['price-alerts'] });
    },
    onError: (e: any) => setMsg({ type: 'error', text: e.message }),
  });

  const importing = importMutation.isPending;
  const syncingPrices = syncPricesMutation.isPending;

  const handleImport = () => {
    const file = fileRef.current?.files?.[0];
    if (!file) return;
    setMsg(null);
    importMutation.mutate(file);
  };

  const totalValue = stats?.total_value ?? 0;
  const totalQty = stats?.total_quantity ?? 0;

  return (
    <div>
      <PageHeader
        eyebrow="⌖ COMMERCE TERMINAL · CARDMARKET LINK"
        title="Cardmarket"
        accent={accent.oklch}
        right={
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontFamily: sothera.fontMono, fontSize: 10, letterSpacing: 2, color: sothera.fgFaint, textTransform: 'uppercase' }}>LISTINGS · TOTAL VALUE</div>
            <div style={{ fontFamily: sothera.fontDisplay, fontSize: 28, fontWeight: 700, color: sothera.fg, fontFeatureSettings: '"tnum"', letterSpacing: -0.8 }}>€{totalValue.toFixed(2)}</div>
            <div style={{ fontFamily: sothera.fontMono, fontSize: 11, color: accent.oklch, letterSpacing: 1.5 }}>{stats?.unique_cards ?? 0} CARDS · {stats?.total_rows ?? 0} LISTINGS · {totalQty} COPIES</div>
          </div>
        }
      />

      <CardmarketWorkflowBanner
        onImport={() => fileRef.current?.click()}
        onExport={async () => {
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
        exporting={exporting}
        hasListings={listings.length > 0}
      />

      {/* Action buttons */}
      <div className={styles.controls}>
        <input type="file" ref={fileRef} accept=".csv" style={{ display: 'none' }} onChange={handleImport} />
        {[
          { l: '⇡ IMPORT CSV', primary: true, onClick: () => fileRef.current?.click(), disabled: importing },
          { l: '⇣ EXPORT CSV', primary: false, onClick: async () => {
            setExporting(true); setMsg(null);
            try { await api.exportCardmarketCSV(); setMsg({ type: 'success', text: 'CSV exported successfully' }); } catch (e: any) { setMsg({ type: 'error', text: e.message }); } finally { setExporting(false); }
          }, disabled: exporting || listings.length === 0 },
          { l: '↯ SYNC PRICES', primary: false, onClick: () => { setMsg(null); syncPricesMutation.mutate(); }, disabled: syncingPrices },
        ].map(b => (
          <div
            key={b.l}
            className={styles.btn}
            onClick={b.disabled ? undefined : b.onClick}
            style={{
              background: b.primary ? accent.oklch : sothera.glassBg,
              color: b.primary ? '#04040A' : sothera.fg,
              borderColor: b.primary ? accent.oklch : sothera.glassBorder,
              opacity: b.disabled ? 0.5 : 1,
              cursor: b.disabled ? 'default' : 'pointer',
            }}
          >
            {b.l}
          </div>
        ))}
        <Input
          placeholder="Search..."
          value={searchInput}
          onChange={(_, d) => setSearchInput(d.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') setCommittedSearch(searchInput.trim());
          }}
          style={{ minWidth: 200, flex: 1, maxWidth: 300, marginLeft: 'auto' }}
        />
      </div>

      {/* Filter toolbar */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
        <Select value={colorFilter} onChange={(_, d) => setParam('color', d.value)} style={{ minWidth: 140 }}>
          {COLOR_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
        </Select>
        <Select value={setCodeFilter} onChange={(_, d) => setParam('set', d.value)} style={{ minWidth: 140 }}>
          <option value="">All Sets</option>
          {availableSets.map(s => <option key={s.set_code} value={s.set_code}>{s.set_name}</option>)}
        </Select>
        <Select value={sourceFilter} onChange={(_, d) => setParam('source', d.value)} style={{ minWidth: 140 }}>
          <option value="">All Sources</option>
          <option value="manual">Manual (Draft)</option>
          <option value="import">Imported</option>
        </Select>
        <Select value={sortParam} onChange={(_, d) => setParam('sort', d.value)} style={{ minWidth: 160 }}>
          {SORT_OPTIONS.map(o => <option key={o.value} value={o.value}>Sort: {o.label}</option>)}
        </Select>
      </div>

      {msg && (
        <MessageBar intent={msg.type === 'success' ? 'success' : 'error'} style={{ marginTop: 8, marginBottom: 8 }}>
          <MessageBarBody>{msg.text}</MessageBarBody>
        </MessageBar>
      )}

      {/* Price Alerts */}
      {!alertsLoading && alerts.length > 0 && (
        <>
          <SectionHeader num="01" title="Price Spike Alerts" right={`${alerts.length} DETECTED`} accent={accent.oklch} />
          <Panel>
            {(() => {
              const tierMap = new Map<string, PriceAlert[]>();
              for (const tier of PRICE_TIERS) tierMap.set(tier.label, []);
              for (const a of alerts) tierMap.get(getPriceTier(a.trend))!.push(a);
              return [...PRICE_TIERS].reverse()
                .filter(tier => (tierMap.get(tier.label)?.length || 0) > 0)
                .map(tier => {
                  const tierAlerts = tierMap.get(tier.label)!;
                  const isOpen = openAlertGroups.has(tier.label);
                  return (
                    <div key={tier.label}>
                      <div
                        className={styles.alertGroupHeader}
                        onClick={() => setOpenAlertGroups(prev => {
                          const next = new Set(prev);
                          if (next.has(tier.label)) next.delete(tier.label);
                          else next.add(tier.label);
                          return next;
                        })}
                      >
                        <span style={{ transition: 'transform 0.15s', transform: isOpen ? 'rotate(90deg)' : 'none', fontSize: 10 }}>▶</span>
                        <span>{tier.emoji} {tier.label} ({tierAlerts.length})</span>
                      </div>
                      {isOpen && tierAlerts.map((a, i) => (
                        <div key={i} style={{ display: 'grid', gridTemplateColumns: '2fr 1fr 120px', padding: '14px 0', borderBottom: `1px solid ${sothera.rowBorder}`, fontSize: 13, alignItems: 'center' }}>
                          <div>
                            <span style={{ fontWeight: 500, color: sothera.fg }}>{a.card_name}</span>
                            <span style={{ fontFamily: sothera.fontMono, fontSize: 10, marginLeft: 8, color: sothera.fgMuted }}>{a.expansion}</span>
                          </div>
                          <div style={{ fontFamily: sothera.fontMono, fontSize: 11, color: sothera.fgMuted }}>{a.suggestion}</div>
                          <div style={{ textAlign: 'right', fontFamily: sothera.fontMono, fontSize: 11, fontWeight: 600, color: accent.oklch }}>
                            +{a.spike_pct}%
                            <div style={{ fontFamily: sothera.fontMono, fontSize: 10, color: sothera.fgFaint, marginTop: 2 }}>€{a.avg30} → €{a.trend}</div>
                          </div>
                        </div>
                      ))}
                    </div>
                  );
                });
            })()}
          </Panel>
        </>
      )}

      {/* Listings table */}
      <SectionHeader num="02" title="Active Listings" right={`${listingsTotal} LISTINGS`} accent={accent.oklch} />
      {loading ? (
        <Spinner label="Loading..." style={{ marginTop: 24 }} />
      ) : listings.length === 0 ? (
        <div style={{ fontFamily: sothera.fontMono, fontSize: 13, color: sothera.fgMuted, marginTop: 16, letterSpacing: 1 }}>No listings. Sync from profile or import a CSV.</div>
      ) : (() => {
        const pendingListings = listings.filter(l => l.source === 'manual');
        const liveListings = listings.filter(l => l.source !== 'manual');
        const showSections = sortBy === 'source' && pendingListings.length > 0 && liveListings.length > 0;

        const renderRow = (l: CardmarketListing, i: number, total: number) => (
          <div key={l.id} className={styles.gridRow} style={{
            borderBottom: i < total - 1 ? `1px solid ${sothera.rowBorder}` : 'none',
            background: l.source === 'manual' ? 'rgba(255,140,0,0.05)' : undefined,
          }}>
            <div style={{ fontWeight: 500, color: sothera.fg }}>
              {l.card ? (
                <CardHoverPreview card={l.card}>
                  <span style={{ cursor: 'default' }}>{l.card_name}</span>
                </CardHoverPreview>
              ) : (
                <PriceCell cardName={l.card_name} accent={accent.oklch} />
              )}
            </div>
            <div style={{ fontFamily: sothera.fontMono, fontSize: 11, color: sothera.fgMuted, letterSpacing: 0.5 }}>{l.set_name || l.set_code?.toUpperCase() || '—'}</div>
            <div style={{ fontFamily: sothera.fontDisplay, fontWeight: 600, color: sothera.fg, fontFeatureSettings: '"tnum"' }}>{l.quantity}</div>
            <div style={{ fontFamily: sothera.fontMono, fontSize: 11, color: sothera.fgMuted }}>{l.condition || '—'}</div>
            <div style={{ fontFamily: sothera.fontMono, fontSize: 11, color: sothera.fgMuted }}>{l.language}</div>
            <div>
              <span style={{ fontFamily: sothera.fontMono, fontSize: 9, padding: '2px 6px', letterSpacing: 1.5, borderWidth: 1, borderStyle: 'solid', borderColor: l.source === 'manual' ? accent.oklch : sothera.glassBorder, color: l.source === 'manual' ? accent.oklch : sothera.fgMuted }}>
                {l.source === 'manual' ? '✏ DRAFT' : (l.source || 'import').toUpperCase()}
              </span>
            </div>
            <div style={{ textAlign: 'right', fontFamily: sothera.fontDisplay, fontWeight: 600, color: sothera.fg, fontFeatureSettings: '"tnum"' }}>€{l.price.toFixed(2)}</div>
            <div style={{ textAlign: 'right', fontFamily: sothera.fontMono, fontSize: 11, color: sothera.fgMuted }}>{l.rarity || '—'}</div>
          </div>
        );

        const gridHeader = (
          <div className={styles.gridHeader}>
            <div>NAME</div><div>SET</div><div>QTY</div><div>COND</div><div>LANG</div><div>SOURCE</div><div style={{ textAlign: 'right' }}>EUR</div><div style={{ textAlign: 'right' }}>RARITY</div>
          </div>
        );

        if (showSections) {
          return (
            <>
              <Panel>
                <div style={{ fontFamily: sothera.fontMono, fontSize: 11, letterSpacing: 1.5, color: accent.oklch, marginBottom: 8, textTransform: 'uppercase' }}>
                  ✏️ Pending Listings ({pendingListings.length}) — not yet on Cardmarket
                </div>
                {gridHeader}
                {pendingListings.map((l, i) => renderRow(l, i, pendingListings.length))}
              </Panel>
              <div style={{ height: 16 }} />
              <Panel>
                <div style={{ fontFamily: sothera.fontMono, fontSize: 11, letterSpacing: 1.5, color: sothera.fgMuted, marginBottom: 8, textTransform: 'uppercase' }}>
                  ✅ Live on Cardmarket ({liveListings.length})
                </div>
                {gridHeader}
                {liveListings.map((l, i) => renderRow(l, i, liveListings.length))}
              </Panel>
            </>
          );
        }

        return (
          <Panel>
            {gridHeader}
            {listings.map((l, i) => renderRow(l, i, listings.length))}
          </Panel>
        );
      })()}

      {/* Listing Health */}
      <SectionHeader num="03" title="Listing Health" right="vs TREND" accent={accent.oklch} />
      <ListingHealthPanel />
    </div>
  );
}
