import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { makeStyles, shorthands } from '@griffel/react';
import { Spinner } from '@fluentui/react-components';
import { api, CollectionStats, PriceAlert, ValueSnapshot } from '../api';
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
    gridTemplateColumns: 'repeat(4, 1fr)',
    gap: '14px',
    marginBottom: '36px',
    '@media (max-width: 768px)': {
      gridTemplateColumns: 'repeat(2, 1fr)',
    },
  },
  statCardInner: {
    cursor: 'pointer',
    transitionProperty: 'border-color',
    transitionDuration: '160ms',
    ':hover': {
      ...shorthands.borderColor(sothera.fgFaint),
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
  const { accent } = useAccent();
  const { data: stats, isLoading: statsLoading } = useQuery<CollectionStats>({
    queryKey: ['stats'],
    queryFn: () => api.getStats(),
    staleTime: 30_000,
  });
  const { data: alerts = [], isLoading: alertsLoading } = useQuery<PriceAlert[]>({
    queryKey: ['priceAlerts'],
    queryFn: () => api.getPriceAlerts(),
    staleTime: 5 * 60_000,
  });
  const { data: valueHistory = [] } = useQuery<ValueSnapshot[]>({
    queryKey: ['valueHistory'],
    queryFn: () => api.getValueHistory(90),
    staleTime: 5 * 60_000,
  });
  const [openGroups, setOpenGroups] = useState<Set<string>>(new Set());

  if (statsLoading || alertsLoading) return <Spinner label="Loading..." />;

  const tierMap = new Map<string, PriceAlert[]>();
  for (const tier of PRICE_TIERS) tierMap.set(tier.label, []);
  for (const a of alerts) {
    const t = getPriceTier(a.trend);
    tierMap.get(t)?.push(a);
  }

  return (
    <div>
      <PageHeader
        eyebrow="◇ DOSSIER · QUARTERLY READOUT"
        title="The Vault"
        accent={accent.oklch}
        right={
          <div style={{ textAlign: 'right' }}>
            <div className={styles.eyebrowLabel}>LAST SYNC</div>
            <div style={{ fontFamily: sothera.fontMono, fontSize: 13, color: sothera.fgMuted, letterSpacing: 1, marginTop: 4 }}>
              {new Date().toISOString().slice(0, 10).replace(/-/g, '.')} · {new Date().toLocaleTimeString('en', { hour12: false })}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, justifyContent: 'flex-end', marginTop: 4 }}>
              <span style={{ width: 6, height: 6, borderRadius: '50%', background: sothera.positive, boxShadow: `0 0 8px oklch(0.78 0.17 150 / 0.6)` }} />
              <span style={{ fontFamily: sothera.fontMono, fontSize: 10, color: sothera.positive, letterSpacing: 1.5 }}>SYNCED</span>
            </div>
          </div>
        }
      />

      {/* Hero value panel */}
      <Panel corners glow accent={accent.oklch} className={styles.heroPanel}
        style={{ background: `linear-gradient(135deg, ${accent.soft} 0%, transparent 50%)` }}>
        <div className={styles.heroGrid}>
          <div>
            <div className={styles.eyebrowLabel}>AGGREGATE HOLDINGS · EUR</div>
            <div className={styles.heroValue}>
              €{(stats?.total_value_eur ?? 0).toLocaleString('en', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </div>
            <div style={{ marginTop: 14 }}>
              <DeltaBadge value="+7.70%" sub="vs. 90d" positive />
            </div>
            <div className={styles.subGrid}>
              <div>
                <div className={styles.eyebrowLabel}>USD MIRROR</div>
                <div className={styles.subValue}>
                  ${(stats?.total_value_usd ?? 0).toLocaleString('en', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </div>
              </div>
              <div>
                <div className={styles.eyebrowLabel}>LISTINGS VALUE</div>
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

      {/* Stat cards */}
      <div className={styles.statCards}>
        {[
          { l: 'Total Cards', g: '☷', v: (stats?.total_cards ?? 0).toLocaleString(), sub: `${(stats?.unique_cards ?? 0).toLocaleString()} unique` },
          { l: 'Decks', g: '⌬', v: String(stats?.total_decks ?? 0), sub: 'synced from Archidekt' },
          { l: 'On Market', g: '⌖', v: `€${(stats?.cardmarket_total_value ?? 0).toFixed(2)}`, sub: `${stats?.total_cardmarket_listings ?? 0} listings` },
          { l: 'Wishlist', g: '✧', v: '—', sub: 'tracking' },
        ].map((m, i) => (
          <Panel key={i} style={{ cursor: 'pointer' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span className={styles.statLabel}>{m.l}</span>
              <span style={{ fontSize: 14, color: sothera.fgFainter }}>{m.g}</span>
            </div>
            <div className={styles.statValue}>{m.v}</div>
            <div className={styles.statSub}>{m.sub}</div>
          </Panel>
        ))}
      </div>

      {/* Price Alerts */}
      {alerts.length > 0 && (
        <>
          <SectionHeader num="01" title="Market Anomalies" right={`${alerts.length} DETECTED`} accent={accent.oklch} />
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
                      <div key={i} className={styles.alertRow}>
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
    </div>
  );
}
