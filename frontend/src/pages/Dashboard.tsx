import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  makeStyles,
  tokens,
  Card,
  CardHeader,
  Title2,
  Title3,
  Body1,
  Body2,
  Caption1,
  Spinner,
  Badge,
  Subtitle2,
} from '@fluentui/react-components';
import { api, CollectionStats, PriceAlert, ValueSnapshot } from '../api';
import { Sparkline } from '../components/Sparkline';
import { t } from '../i18n';

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
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))',
    gap: '16px',
    marginTop: '16px',
  },
  card: {
    padding: '16px',
  },
  value: {
    fontSize: tokens.fontSizeHero800,
    fontWeight: tokens.fontWeightBold,
    color: tokens.colorBrandForeground1,
  },
  alertsSection: {
    marginTop: '24px',
  },
  alertGroupHeader: {
    cursor: 'pointer',
    userSelect: 'none' as const,
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    padding: '8px 0',
  },
  chevron: {
    display: 'inline-block',
    transition: 'transform 0.15s ease',
    fontSize: '10px',
  },
  chevronOpen: {
    transform: 'rotate(90deg)',
  },
  alertCard: {
    padding: '12px 16px',
    marginTop: '8px',
  },
  alertRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: '12px',
    flexWrap: 'wrap' as const,
  },
});

export default function Dashboard() {
  const styles = useStyles();
  const { data: stats, isLoading: statsLoading } = useQuery<CollectionStats>({
    queryKey: ['stats'],
    queryFn: () => api.getStats(),
  });
  const { data: alerts = [], isLoading: alertsLoading } = useQuery<PriceAlert[]>({
    queryKey: ['priceAlerts'],
    queryFn: () => api.getPriceAlerts(),
  });
  const { data: valueHistory = [] } = useQuery<ValueSnapshot[]>({
    queryKey: ['valueHistory'],
    queryFn: () => api.getValueHistory(90),
  });
  const [openGroups, setOpenGroups] = useState<Set<string>>(new Set());

  const loading = statsLoading || alertsLoading;

  if (loading) return <Spinner label="Loading..." />;

  const tierMap = new Map<string, PriceAlert[]>();
  for (const tier of PRICE_TIERS) tierMap.set(tier.label, []);
  for (const a of alerts) {
    const t = getPriceTier(a.trend);
    tierMap.get(t)?.push(a);
  }

  return (
    <div>
      <Title2>{t('dashboard.title')}</Title2>

      <div className={styles.grid}>
        <Card className={styles.card}>
          <CardHeader header={<Body1>{t('dashboard.total_cards')}</Body1>} />
          <div className={styles.value}>{stats?.total_cards ?? 0}</div>
        </Card>
        <Card className={styles.card}>
          <CardHeader header={<Body1>{t('dashboard.unique_cards')}</Body1>} />
          <div className={styles.value}>{stats?.unique_cards ?? 0}</div>
        </Card>
        <Card className={styles.card}>
          <CardHeader header={<Body1>{t('dashboard.value_eur')}</Body1>} />
          <div className={styles.value}>€{stats?.total_value_eur?.toFixed(2) ?? '0.00'}</div>
        </Card>
        <Card className={styles.card}>
          <CardHeader header={<Body1>{t('dashboard.value_usd')}</Body1>} />
          <div className={styles.value}>${stats?.total_value_usd?.toFixed(2) ?? '0.00'}</div>
        </Card>
        <Card className={styles.card}>
          <CardHeader header={<Body1>{t('dashboard.decks')}</Body1>} />
          <div className={styles.value}>{stats?.total_decks ?? 0}</div>
        </Card>
        <Card className={styles.card}>
          <CardHeader header={<Body1>{t('dashboard.cardmarket_listings')}</Body1>} />
          <div className={styles.value}>{stats?.total_cardmarket_listings ?? 0}</div>
          <Caption1>Value: €{stats?.cardmarket_total_value?.toFixed(2) ?? '0.00'}</Caption1>
        </Card>
      </div>

      {valueHistory.length >= 2 && (
        <Card className={styles.card} style={{ marginTop: 16, maxWidth: 400 }}>
          <CardHeader header={<Body1>{t('dashboard.value_history')}</Body1>} />
          <Sparkline
            data={valueHistory.map(v => ({ trend: v.value_eur }))}
            width={360}
            height={48}
          />
          <Caption1>
            {valueHistory[0].date} — {valueHistory[valueHistory.length - 1].date}
          </Caption1>
        </Card>
      )}

      {alerts.length > 0 && (
        <div className={styles.alertsSection}>
          <Title3>📈 Price Spike Alerts ({alerts.length})</Title3>
          {[...PRICE_TIERS].reverse()
            .filter(tier => (tierMap.get(tier.label)?.length || 0) > 0)
            .map(tier => {
              const tierAlerts = tierMap.get(tier.label)!;
              const isOpen = openGroups.has(tier.label);
              return (
                <div key={tier.label} style={{ marginTop: 8 }}>
                  <div
                    className={styles.alertGroupHeader}
                    onClick={() => setOpenGroups(prev => {
                      const next = new Set(prev);
                      if (next.has(tier.label)) next.delete(tier.label);
                      else next.add(tier.label);
                      return next;
                    })}
                  >
                    <span className={`${styles.chevron} ${isOpen ? styles.chevronOpen : ''}`}>▶</span>
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
            })}
        </div>
      )}
    </div>
  );
}
