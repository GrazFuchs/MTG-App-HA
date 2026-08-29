import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { makeStyles, mergeClasses, shorthands } from '@griffel/react';
import { Spinner } from '@fluentui/react-components';
import { api, CollectionStats, InboxAcquisitionStats, PriceAlert, SyncStatus, ValueSnapshot, MtgStocksMover, MtgStocksSignals, WishlistSummary } from '../api';
import { ErrorBanner } from '../components/ErrorBanner';
import { Sparkline } from '../components/Sparkline';
import { t } from '../i18n';
import { sothera } from '../theme/sothera';
import { useAccent } from '../main';
import { Panel, PageHeader, SectionHeader, DeltaBadge } from '../components/sothera';

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
  heroPanel: {
    padding: '32px',
    marginBottom: '18px',
  },
  heroGrid: {
    display: 'grid',
    gridTemplateColumns: '1.05fr 1.95fr',
    gap: '40px',
    alignItems: 'center',
    '@media (max-width: 768px)': {
      gridTemplateColumns: '1fr',
    },
  },
  eyebrowLabel: {
    fontFamily: sothera.fontMono,
    fontSize: '10px',
    letterSpacing: '2.5px',
    color: sothera.fgFaint,
    textTransform: 'uppercase',
  },
  heroValue: {
    fontFamily: sothera.fontDisplay,
    fontSize: '60px',
    fontWeight: 700,
    letterSpacing: '-3px',
    lineHeight: 1,
    margin: '14px 0 4px',
    color: sothera.fg,
    fontFeatureSettings: '"tnum"',
    '@media (max-width: 768px)': {
      fontSize: '40px',
      letterSpacing: '-1.5px',
    },
  },
  subGrid: {
    marginTop: '22px',
    paddingTop: '16px',
    borderTop: `1px solid ${sothera.glassBorder}`,
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: '16px',
  },
  subValue: {
    fontFamily: sothera.fontDisplay,
    fontSize: '22px',
    fontWeight: 600,
    color: sothera.fgMuted,
    marginTop: '4px',
    fontFeatureSettings: '"tnum"',
    letterSpacing: '-0.5px',
  },
  statCards: {
    display: 'grid',
    gridTemplateColumns: 'repeat(5, 1fr)',
    gap: '14px',
    marginBottom: '36px',
    '@media (max-width: 1100px)': {
      gridTemplateColumns: 'repeat(3, 1fr)',
    },
    '@media (max-width: 768px)': {
      gridTemplateColumns: 'repeat(2, 1fr)',
    },
  },
  statCardInner: {
    cursor: 'pointer',
    transitionProperty: 'border-color, transform',
    transitionDuration: '160ms',
    ':hover': {
      ...shorthands.borderColor(sothera.fgFaint),
    },
    ':focus-visible': {
      ...shorthands.borderColor(sothera.fg),
      outlineStyle: 'none',
    },
  },
  clickableRow: {
    cursor: 'pointer',
    ':hover': {
      backgroundColor: 'rgba(255,255,255,0.03)',
    },
  },
  statLabel: {
    fontFamily: sothera.fontMono,
    fontSize: '10px',
    letterSpacing: '2px',
    color: sothera.fgFaint,
    textTransform: 'uppercase',
  },
  statValue: {
    fontFamily: sothera.fontDisplay,
    fontSize: '34px',
    fontWeight: 700,
    marginTop: '12px',
    color: sothera.fg,
    fontFeatureSettings: '"tnum"',
    letterSpacing: '-1px',
  },
  statSub: {
    fontFamily: sothera.fontMono,
    fontSize: '11px',
    color: sothera.fgMuted,
    marginTop: '2px',
    letterSpacing: '0.5px',
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
  alertRow: {
    display: 'grid',
    gridTemplateColumns: '2fr 1fr 120px',
    padding: '14px 0',
    borderBottom: `1px solid ${sothera.rowBorder}`,
    fontSize: '13px',
    alignItems: 'center',
    '@media (max-width: 768px)': {
      gridTemplateColumns: '1fr',
      gap: '4px',
    },
  },
  alertName: {
    fontWeight: 500,
    color: sothera.fg,
  },
  alertSuggestion: {
    fontFamily: sothera.fontMono,
    fontSize: '11px',
    color: sothera.fgMuted,
    letterSpacing: '0.5px',
  },
  alertSpike: {
    textAlign: 'right',
    fontFamily: sothera.fontMono,
    fontSize: '11px',
    fontWeight: 600,
    letterSpacing: '0.5px',
  },
  alertPrice: {
    fontFamily: sothera.fontMono,
    fontSize: '10px',
    color: sothera.fgFaint,
    letterSpacing: '0.5px',
    marginTop: '2px',
  },
});

export default function Dashboard() {
  const styles = useStyles();
  const navigate = useNavigate();
  const { accent } = useAccent();
  const { data: stats, isLoading: statsLoading, isError: statsError } = useQuery<CollectionStats>({
    queryKey: ['stats'],
    queryFn: () => api.getStats(),
    staleTime: 30_000,
  });
  const { data: alerts = [], isLoading: alertsLoading, isError: alertsError } = useQuery<PriceAlert[]>({
    queryKey: ['priceAlerts'],
    queryFn: () => api.getPriceAlerts(),
    staleTime: 5 * 60_000,
  });
  const { data: syncStatus } = useQuery<SyncStatus>({
    queryKey: ['syncStatus'],
    queryFn: () => api.getSyncStatus(),
    staleTime: 60_000,
  });
  const { data: valueHistory = [] } = useQuery<ValueSnapshot[]>({
    queryKey: ['valueHistory'],
    queryFn: () => api.getValueHistory(90),
    staleTime: 5 * 60_000,
  });
  const { data: mtgStocks } = useQuery<{ enabled: boolean }>({
    queryKey: ['mtgstocksStatus'],
    queryFn: () => api.getMtgStocksStatus(),
    staleTime: 10 * 60_000,
  });
  const mtgStocksOn = !!mtgStocks?.enabled;
  const { data: movers = [] } = useQuery<MtgStocksMover[]>({
    queryKey: ['mtgstocksMovers'],
    queryFn: () => api.getMtgStocksMovers(20),
    staleTime: 5 * 60_000,
    enabled: mtgStocksOn,
  });
  const { data: signals } = useQuery<MtgStocksSignals>({
    queryKey: ['mtgstocksSignals'],
    queryFn: () => api.getMtgStocksSignals(),
    staleTime: 5 * 60_000,
    enabled: mtgStocksOn,
  });
  const { data: inbox } = useQuery<InboxAcquisitionStats>({
    queryKey: ['inbox-stats'],
    queryFn: () => api.getInboxStats(),
    staleTime: 30_000,
  });
  const { data: wishlist } = useQuery<WishlistSummary>({
    queryKey: ['wishlist-summary'],
    queryFn: () => api.getWishlistSummary(),
    staleTime: 5 * 60_000,
  });
  const [openGroups, setOpenGroups] = useState<Set<string>>(new Set());

  if (statsLoading || alertsLoading) return <Spinner label={t('common.loading')} />;

  const tierMap = new Map<string, PriceAlert[]>();
  for (const tier of PRICE_TIERS) tierMap.set(tier.label, []);
  for (const a of alerts) {
    const tierLabel = getPriceTier(a.trend);
    tierMap.get(tierLabel)?.push(a);
  }

  const pendingCount = inbox?.pending_count ?? 0;

  // Real sync state for the header. SQLite timestamps are UTC but naive
  // ("2026-08-23 01:15:13"), so the space→T + Z suffix makes Date() parse
  // them as UTC instead of local time.
  const lastSync = syncStatus?.last_sync ?? null;
  const lastSyncDate = lastSync?.finished_at
    ? new Date(lastSync.finished_at.includes('+') || lastSync.finished_at.endsWith('Z')
        ? lastSync.finished_at
        : lastSync.finished_at.replace(' ', 'T') + 'Z')
    : null;
  const syncState: { label: string; color: string; glow: string } = !lastSync
    ? { label: t('dashboard.never_synced'), color: sothera.fgMuted, glow: 'transparent' }
    : lastSync.status === 'completed'
      ? { label: t('dashboard.synced'), color: sothera.positive, glow: 'oklch(0.78 0.17 150 / 0.6)' }
      : lastSync.status === 'running'
        ? { label: t('dashboard.syncing'), color: sothera.fgMuted, glow: 'transparent' }
        : { label: lastSync.status.toUpperCase(), color: sothera.negative, glow: 'oklch(0.70 0.20 25 / 0.6)' };

  // Real 90-day performance from the value snapshots (oldest vs newest).
  const firstSnap = valueHistory.length >= 2 ? valueHistory[0] : null;
  const lastSnap = valueHistory.length >= 2 ? valueHistory[valueHistory.length - 1] : null;
  const deltaPct = firstSnap && lastSnap && firstSnap.value_eur > 0
    ? ((lastSnap.value_eur - firstSnap.value_eur) / firstSnap.value_eur) * 100
    : null;
  const deltaDays = firstSnap && lastSnap
    ? Math.max(1, Math.round((new Date(lastSnap.date).getTime() - new Date(firstSnap.date).getTime()) / 86_400_000))
    : null;

  /** Open the collection filtered to one card — where an alert row leads. */
  const openCard = (name: string) =>
    navigate(`/collection?search=${encodeURIComponent(name)}`);

  return (
    <div>
      <PageHeader
        eyebrow="◇ DOSSIER · QUARTERLY READOUT"
        title={t('dashboard.vault')}
        accent={accent.oklch}
        right={
          <div style={{ textAlign: 'right' }}>
            <div className={styles.eyebrowLabel}>{t('dashboard.last_sync')}</div>
            <div style={{ fontFamily: sothera.fontMono, fontSize: 13, color: sothera.fgMuted, letterSpacing: 1, marginTop: 4 }}>
              {lastSyncDate
                ? `${lastSyncDate.toLocaleDateString('en-CA').replace(/-/g, '.')} · ${lastSyncDate.toLocaleTimeString('en', { hour12: false })}`
                : '—'}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, justifyContent: 'flex-end', marginTop: 4 }}>
              <span style={{ width: 6, height: 6, borderRadius: '50%', background: syncState.color, boxShadow: `0 0 8px ${syncState.glow}` }} />
              <span style={{ fontFamily: sothera.fontMono, fontSize: 10, color: syncState.color, letterSpacing: 1.5 }}>{syncState.label}</span>
            </div>
          </div>
        }
      />

      {(statsError || alertsError) && (
        <div style={{ marginBottom: 16 }}>
          <ErrorBanner
            title={t('dashboard.backend_unreachable')}
            message={statsError
              ? 'Collection stats could not be loaded — the numbers below are placeholders, not facts. Check the add-on log.'
              : t('dashboard.alerts_failed')}
          />
        </div>
      )}

      {/* Hero value panel — the headline number is the collection, so it opens it */}
      <Panel corners glow accent={accent.oklch} className={styles.heroPanel}
        style={{ background: `linear-gradient(135deg, ${accent.soft} 0%, transparent 50%)`, cursor: 'pointer' }}
        role="link"
        tabIndex={0}
        title={t('dashboard.open_collection')}
        onClick={() => navigate('/collection?sort_by=price_eur&sort_dir=desc')}
        onKeyDown={e => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            navigate('/collection?sort_by=price_eur&sort_dir=desc');
          }
        }}
      >
        <div className={styles.heroGrid}>
          <div>
            <div className={styles.eyebrowLabel}>{t('dashboard.aggregate')}</div>
            <div className={styles.heroValue}>
              {statsError
                ? '—'
                : `€${(stats?.total_value_eur ?? 0).toLocaleString('en', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
            </div>
            {deltaPct !== null && (
              <div style={{ marginTop: 14 }}>
                <DeltaBadge
                  value={`${deltaPct >= 0 ? '+' : ''}${deltaPct.toFixed(2)}%`}
                  sub={`vs. ${deltaDays}d`}
                  positive={deltaPct >= 0}
                />
              </div>
            )}
            <div className={styles.subGrid}>
              <div>
                <div className={styles.eyebrowLabel}>{t('dashboard.usd_mirror')}</div>
                <div className={styles.subValue}>
                  ${(stats?.total_value_usd ?? 0).toLocaleString('en', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </div>
              </div>
              <div>
                <div className={styles.eyebrowLabel}>{t('dashboard.listings_value')}</div>
                <div className={styles.subValue}>
                  €{(stats?.cardmarket_total_value ?? 0).toFixed(2)}
                </div>
              </div>
            </div>
          </div>
          {valueHistory.length >= 2 && (
            <Sparkline
              data={valueHistory.map(v => ({ v: v.value_eur, date: v.date }))}
              accent={accent.oklch}
              dot
            />
          )}
        </div>
      </Panel>

      {/* Stat cards — each one is the entrance to the page it summarises.
          Inbox sits first when something is pending: it is the only tile that
          represents work waiting, and it was missing from here entirely. */}
      <div className={styles.statCards}>
        {[
          {
            l: t('dashboard.inbox'),
            g: '⊕',
            v: String(pendingCount),
            sub: pendingCount > 0 ? t('dashboard.inbox_waiting') : t('dashboard.inbox_done'),
            to: '/inbox',
            urgent: pendingCount > 0,
          },
          {
            l: t('dashboard.total_cards'),
            g: '☷',
            v: (stats?.total_cards ?? 0).toLocaleString(),
            sub: t('dashboard.unique_sub', { count: (stats?.unique_cards ?? 0).toLocaleString() }),
            to: '/collection',
          },
          {
            l: t('dashboard.decks'),
            g: '⌬',
            v: String(stats?.total_decks ?? 0),
            sub: t('dashboard.decks_sub'),
            to: '/decks',
          },
          {
            l: t('dashboard.on_market'),
            g: '⌖',
            v: `€${(stats?.cardmarket_total_value ?? 0).toFixed(2)}`,
            sub: t('dashboard.listings_sub', { count: stats?.total_cardmarket_listings ?? 0 }),
            to: '/cardmarket',
          },
          {
            l: t('nav.wishlist'),
            g: '✧',
            v: String(wishlist?.total_items ?? 0),
            sub: wishlist
              ? t('dashboard.wishlist_sub', { value: wishlist.total_current_eur.toFixed(2) })
              : t('dashboard.wishlist_tracking'),
            to: '/wishlist',
          },
        ].map(m => (
          <Panel
            key={m.l}
            className={styles.statCardInner}
            role="link"
            tabIndex={0}
            title={`Open ${m.l}`}
            onClick={() => navigate(m.to)}
            onKeyDown={e => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                navigate(m.to);
              }
            }}
            style={m.urgent ? { borderColor: accent.oklch } : undefined}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span className={styles.statLabel}>{m.l}</span>
              <span style={{ fontSize: 14, color: m.urgent ? accent.oklch : sothera.fgFainter }}>{m.g}</span>
            </div>
            <div className={styles.statValue} style={m.urgent ? { color: accent.oklch } : undefined}>{m.v}</div>
            <div className={styles.statSub}>{m.sub}</div>
          </Panel>
        ))}
      </div>

      {/* Price Alerts */}
      {alerts.length > 0 && (
        <>
          <SectionHeader num="01" title={t('dashboard.anomalies')} right={`${alerts.length} DETECTED`} accent={accent.oklch} />
          <Panel>
            {[...PRICE_TIERS].reverse()
              .filter(tier => (tierMap.get(tier.label)?.length || 0) > 0)
              .map(tier => {
                const tierAlerts = tierMap.get(tier.label)!;
                const isOpen = openGroups.has(tier.label);
                return (
                  <div key={tier.label}>
                    <div
                      className={styles.alertGroupHeader}
                      onClick={() => setOpenGroups(prev => {
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
                      <div
                        key={i}
                        className={mergeClasses(styles.alertRow, styles.clickableRow)}
                        role="link"
                        tabIndex={0}
                        title={t('dashboard.show_in_collection', { name: a.card_name })}
                        onClick={() => openCard(a.card_name)}
                        onKeyDown={e => {
                          if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openCard(a.card_name); }
                        }}
                      >
                        <div>
                          <span className={styles.alertName}>{a.card_name}</span>
                          {a.set_code && (
                            <span style={{ fontFamily: sothera.fontMono, fontSize: 10, marginLeft: 8, padding: '2px 6px', letterSpacing: 1.5, border: `1px solid ${sothera.glassBorder}`, color: sothera.fgMuted }}>
                              {a.set_code.toUpperCase()}
                            </span>
                          )}
                        </div>
                        <div className={styles.alertSuggestion}>{a.suggestion}</div>
                        <div className={styles.alertSpike} style={{ color: accent.oklch }}>
                          +{a.spike_pct}%
                          <div className={styles.alertPrice}>€{a.avg30} → €{a.trend}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                );
              })}
          </Panel>
        </>
      )}

      {/* MTGStocks: Collection Movers */}
      {mtgStocksOn && movers.length > 0 && (
        <>
          <SectionHeader num="02" title={t('dashboard.movers')} right={`MTGSTOCKS · ${movers.length}`} accent={accent.oklch} />
          <Panel>
            {movers.map((m, i) => {
              const up = m.direction === 'up';
              const color = up ? sothera.positive : sothera.negative;
              return (
                <div
                  key={i}
                  className={mergeClasses(styles.alertRow, styles.clickableRow)}
                  role="link"
                  tabIndex={0}
                  title={t('dashboard.show_in_collection', { name: m.card_name })}
                  onClick={() => openCard(m.card_name)}
                  onKeyDown={e => {
                    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openCard(m.card_name); }
                  }}
                >
                  <div>
                    <span className={styles.alertName}>{m.card_name}</span>
                    {m.is_foil && <span style={{ marginLeft: 6, fontSize: 11 }}>◆</span>}
                    {m.set_code && (
                      <span style={{ fontFamily: sothera.fontMono, fontSize: 10, marginLeft: 8, padding: '2px 6px', letterSpacing: 1.5, border: `1px solid ${sothera.glassBorder}`, color: sothera.fgMuted }}>
                        {m.set_code.toUpperCase()}
                      </span>
                    )}
                  </div>
                  <div className={styles.alertSuggestion}>
                    {m.kind === 'market' ? 'market' : 'avg'} · {m.interest_type || 'move'} · {m.owned} owned
                  </div>
                  <div className={styles.alertSpike} style={{ color }}>
                    {up ? '+' : ''}{m.percentage}%
                    {m.present_price != null && (
                      <div className={styles.alertPrice}>
                        {m.past_price != null ? `$${m.past_price.toFixed(2)} → ` : ''}${m.present_price.toFixed(2)}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </Panel>
        </>
      )}

      {/* MTGStocks: Buy/Sell Signals */}
      {mtgStocksOn && signals && (signals.buy.length > 0 || signals.sell.length > 0) && (
        <>
          <SectionHeader num="03" title={t('dashboard.signals')} right={`${signals.buy.length} BUY · ${signals.sell.length} SELL`} accent={accent.oklch} />
          <Panel>
            {signals.buy.map((b, i) => (
              <div
                key={`b${i}`}
                className={mergeClasses(styles.alertRow, styles.clickableRow)}
                role="link"
                tabIndex={0}
                title={t('dashboard.show_in_collection', { name: b.card_name })}
                onClick={() => openCard(b.card_name)}
                onKeyDown={e => {
                  if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openCard(b.card_name); }
                }}
              >
                <div>
                  <span style={{ fontFamily: sothera.fontMono, fontSize: 10, marginRight: 8, padding: '2px 6px', letterSpacing: 1.5, border: `1px solid ${sothera.positive}`, color: sothera.positive }}>{t('dashboard.buy')}</span>
                  <span className={styles.alertName}>{b.card_name}</span>
                </div>
                <div className={styles.alertSuggestion}>near all-time low (+{b.pct_above_low}%)</div>
                <div className={styles.alertSpike} style={{ color: sothera.positive }}>
                  ${b.current_usd.toFixed(2)}
                  <div className={styles.alertPrice}>ATL ${b.all_time_low.toFixed(2)}</div>
                </div>
              </div>
            ))}
            {signals.sell.map((s, i) => (
              <div
                key={`s${i}`}
                className={mergeClasses(styles.alertRow, styles.clickableRow)}
                role="link"
                tabIndex={0}
                title={t('dashboard.show_in_collection', { name: s.card_name })}
                onClick={() => openCard(s.card_name)}
                onKeyDown={e => {
                  if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openCard(s.card_name); }
                }}
              >
                <div>
                  <span style={{ fontFamily: sothera.fontMono, fontSize: 10, marginRight: 8, padding: '2px 6px', letterSpacing: 1.5, border: `1px solid ${sothera.negative}`, color: sothera.negative }}>{t('dashboard.sell')}</span>
                  <span className={styles.alertName}>{s.card_name}</span>
                </div>
                <div className={styles.alertSuggestion}>
                  {s.pct_of_high}% of ATH · {s.unused_copies} unused cop{s.unused_copies === 1 ? 'y' : 'ies'}
                </div>
                <div className={styles.alertSpike} style={{ color: sothera.negative }}>
                  ${s.current_usd.toFixed(2)}
                  <div className={styles.alertPrice}>ATH ${s.all_time_high.toFixed(2)}</div>
                </div>
              </div>
            ))}
          </Panel>
        </>
      )}
    </div>
  );
}
