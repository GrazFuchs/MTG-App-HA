import { useState } from 'react';
import { makeStyles } from '@griffel/react';
import {
  Button,
  Badge,
  Spinner,
  Slider,
  Field,
  Body1,
  Caption1,
} from '@fluentui/react-components';
import { useQuery } from '@tanstack/react-query';
import { api, ListingHealthBucket, ListingHealthResponse } from '../../api';
import { sothera } from '../../theme/sothera';
import { Panel } from '../sothera';

const useStyles = makeStyles({
  summary: {
    display: 'flex',
    gap: '16px',
    flexWrap: 'wrap',
    marginBottom: '12px',
    alignItems: 'center',
  },
  bucketChip: {
    display: 'flex',
    gap: '6px',
    alignItems: 'center',
    cursor: 'pointer',
    padding: '4px 10px',
    borderRadius: '6px',
    border: `1px solid ${sothera.glassBorder}`,
    userSelect: 'none',
  },
  bucketChipActive: {
    backgroundColor: sothera.glassBg,
  },
  table: {
    width: '100%',
    borderCollapse: 'collapse' as const,
    fontSize: '13px',
  },
  th: {
    textAlign: 'left' as const,
    fontFamily: sothera.fontMono,
    fontSize: '9px',
    letterSpacing: '2px',
    color: sothera.fgFaint,
    textTransform: 'uppercase' as const,
    padding: '6px 8px',
    borderBottom: `1px solid ${sothera.headerBorder}`,
  },
  td: {
    padding: '8px',
    borderBottom: `1px solid ${sothera.rowBorder}`,
    verticalAlign: 'middle' as const,
  },
  underpriced: { color: '#22c55e', fontWeight: 600 },
  overpriced: { color: '#ef4444', fontWeight: 600 },
  fair: { color: sothera.fgMuted },
  thresholdRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    marginBottom: '12px',
    flexWrap: 'wrap',
  },
});

type BucketKey = 'underpriced' | 'overpriced' | 'fair' | 'no_match';

const BUCKET_CONFIG: { key: BucketKey; label: string; color: 'success' | 'danger' | 'subtle' | 'warning' }[] = [
  { key: 'underpriced', label: 'Underpriced', color: 'success' },
  { key: 'overpriced',  label: 'Overpriced',  color: 'danger' },
  { key: 'fair',        label: 'Fair',         color: 'subtle' },
  { key: 'no_match',   label: 'No Data',       color: 'warning' },
];

function DeltaCell({ delta, bucket }: { delta: number; bucket: BucketKey }) {
  const styles = useStyles();
  const cls = bucket === 'underpriced' ? styles.underpriced : bucket === 'overpriced' ? styles.overpriced : styles.fair;
  return (
    <span className={cls}>
      {delta > 0 ? '+' : ''}{delta.toFixed(1)}%
    </span>
  );
}

export default function ListingHealthPanel() {
  const styles = useStyles();
  const [threshold, setThreshold] = useState(15);
  const [activeBucket, setActiveBucket] = useState<BucketKey>('overpriced');

  const { data, isLoading, refetch } = useQuery<ListingHealthResponse>({
    queryKey: ['listing-health', threshold],
    queryFn: () => api.getListingHealth(threshold),
    staleTime: 5 * 60_000,
  });

  const rows: (ListingHealthBucket | { listing_id: number; card_name: string; my_price: number })[] =
    data ? (activeBucket === 'no_match' ? data.no_match : data[activeBucket]) : [];

  const showSuggested = activeBucket === 'underpriced' || activeBucket === 'overpriced';

  return (
    <Panel>
      <div className={styles.thresholdRow}>
        <Field label={`Threshold: ±${threshold}%`} style={{ flex: '0 0 220px' }}>
          <Slider
            min={0}
            max={50}
            step={1}
            value={threshold}
            onChange={(_, d) => setThreshold(d.value)}
          />
        </Field>
        <Button size="small" appearance="subtle" onClick={() => refetch()}>Refresh</Button>
      </div>

      <div className={styles.summary}>
        {BUCKET_CONFIG.map(cfg => (
          <div
            key={cfg.key}
            className={`${styles.bucketChip} ${activeBucket === cfg.key ? styles.bucketChipActive : ''}`}
            onClick={() => setActiveBucket(cfg.key)}
          >
            <Badge color={cfg.color} appearance={activeBucket === cfg.key ? 'filled' : 'tint'}>
              {data ? data[cfg.key].length : '—'}
            </Badge>
            <Caption1>{cfg.label}</Caption1>
          </div>
        ))}
      </div>

      {isLoading ? (
        <Spinner size="small" label="Analyzing listings..." />
      ) : !data || rows.length === 0 ? (
        <Body1 style={{ marginTop: 12, color: sothera.fgMuted }}>
          No listings in this category.
        </Body1>
      ) : (
        <table className={styles.table}>
          <thead>
            <tr>
              <th className={styles.th}>Card</th>
              <th className={styles.th}>My Price</th>
              {showSuggested && <th className={styles.th}>Trend</th>}
              {showSuggested && <th className={styles.th}>Suggested</th>}
              {showSuggested && <th className={styles.th}>Δ</th>}
            </tr>
          </thead>
          <tbody>
            {rows.map(row => (
              <tr key={row.listing_id}>
                <td className={styles.td}>{row.card_name}</td>
                <td className={styles.td}>€{row.my_price.toFixed(2)}</td>
                {showSuggested && 'trend_price' in row && (
                  <>
                    <td className={styles.td}>€{(row as ListingHealthBucket).trend_price.toFixed(2)}</td>
                    <td className={styles.td}>€{(row as ListingHealthBucket).suggested_price.toFixed(2)}</td>
                    <td className={styles.td}>
                      <DeltaCell delta={(row as ListingHealthBucket).delta_pct} bucket={activeBucket} />
                    </td>
                  </>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Panel>
  );
}
