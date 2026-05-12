import { useEffect, useState, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { makeStyles } from '@griffel/react';
import { Button, Select, Spinner } from '@fluentui/react-components';
import {
  ChevronLeft24Regular,
  ChevronRight24Regular,
} from '@fluentui/react-icons';
import { api, AcquisitionEvent, TriageDecisionPayload, InboxAcquisitionStats } from '../api';
import { sothera } from '../theme/sothera';
import { useAccent } from '../main';
import { PageHeader } from '../components/sothera';
import { t } from '../i18n';
import AcquisitionCard from '../components/inbox/AcquisitionCard';
import { ErrorBanner } from '../components/ErrorBanner';
import { ErrorBoundary } from '../components/ErrorBoundary';
import { getColorBucket, groupByColorBucket, BUCKET_KEYS, BucketKey } from '../utils/colors';

// Re-export for unit tests
export { getColorBucket, groupByColorBucket, BUCKET_KEYS };
export type { BucketKey };

const INBOX_BUCKET_LABELS: Record<BucketKey, string> = {
  W: 'White', U: 'Blue', B: 'Black', R: 'Red', G: 'Green',
  Multi: 'Multicolor', Colorless: 'Colorless', Unknown: 'Unknown',
};
const INBOX_BUCKET_EMOJI: Record<BucketKey, string> = {
  W: '⚪', U: '🔵', B: '⚫', R: '🔴', G: '🟢',
  Multi: '🌈', Colorless: '◆', Unknown: '❓',
};

const FILTER_OPTIONS = [
  { value: '', label: 'All pending' },
  { value: 'needs_sell', label: 'Suggested: Sell' },
  { value: 'needs_keep', label: 'Suggested: Keep' },
] as const;

const useStyles = makeStyles({
  controls: {
    display: 'flex',
    gap: '12px',
    marginBottom: '16px',
    flexWrap: 'wrap',
    alignItems: 'center',
  },
  filterRow: {
    display: 'flex',
    gap: '8px',
    marginBottom: '12px',
    flexWrap: 'wrap',
  },
  filterPill: {
    padding: '4px 12px',
    fontSize: '11px',
    fontFamily: sothera.fontMono,
    letterSpacing: '1px',
    cursor: 'pointer',
    border: `1px solid ${sothera.glassBorder}`,
    borderRadius: '2px',
    background: 'transparent',
    color: sothera.fgMuted,
  },
  select: {
    minWidth: '140px',
  },
  pagination: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '8px',
    marginTop: '16px',
  },
  pageInfo: {
    fontFamily: sothera.fontMono,
    fontSize: '11px',
    color: sothera.fgMuted,
    letterSpacing: '1px',
    minWidth: '180px',
    textAlign: 'center',
  },
  empty: {
    textAlign: 'center',
    padding: '48px 16px',
    fontFamily: sothera.fontDisplay,
    fontSize: '16px',
    color: sothera.fgMuted,
  },
  statsRow: {
    display: 'flex',
    gap: '16px',
    marginBottom: '16px',
    fontFamily: sothera.fontMono,
    fontSize: '11px',
    color: sothera.fgMuted,
    letterSpacing: '0.5px',
  },
  bucketHeader: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    padding: '10px 0',
    cursor: 'pointer',
    userSelect: 'none',
    borderBottom: `1px solid ${sothera.rowBorder}`,
    fontFamily: sothera.fontMono,
    fontSize: '12px',
    letterSpacing: '1px',
    color: sothera.fgMuted,
    marginBottom: '4px',
  },
  bucketSection: {
    marginBottom: '16px',
  },
});

export default function Inbox() {
  const styles = useStyles();
  const { accent } = useAccent();
  const [searchParams, setSearchParams] = useSearchParams();
  const [events, setEvents] = useState<AcquisitionEvent[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(50);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [minValue, setMinValue] = useState(0);
  const [stats, setStats] = useState<InboxAcquisitionStats | null>(null);
  const [skipped, setSkipped] = useState<Set<number>>(new Set());

  const activeFilter = searchParams.get('filter') || '';

  // Collapse state — localStorage backed
  const [openColors, setOpenColors] = useState<Set<BucketKey>>(() => {
    try {
      const stored = localStorage.getItem('inbox.openColors');
      return stored ? new Set(JSON.parse(stored)) as Set<BucketKey> : new Set(BUCKET_KEYS);
    } catch {
      return new Set(BUCKET_KEYS);
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem('inbox.openColors', JSON.stringify([...openColors]));
    } catch { /* ignore */ }
  }, [openColors]);

  // Persist last source in sessionStorage
  const [defaultSource, setDefaultSource] = useState<string | null>(() => {
    try {
      return sessionStorage.getItem('inbox_last_source') || null;
    } catch {
      return null;
    }
  });

  const handleSourceChange = (source: string) => {
    setDefaultSource(source);
    try {
      sessionStorage.setItem('inbox_last_source', source);
    } catch { /* ignore */ }
  };

  const loadEvents = useCallback(() => {
    setLoading(true);
    setLoadError(false);
    api.getPendingTriage(page, pageSize, minValue, activeFilter)
      .then(res => {
        setEvents(res.items);
        setTotal(res.total);
      })
      .catch(() => {
        setEvents([]);
        setTotal(0);
        setLoadError(true);
      })
      .finally(() => setLoading(false));
  }, [page, pageSize, minValue, activeFilter]);

  const loadStats = useCallback(() => {
    api.getInboxStats().then(setStats).catch(() => {});
  }, []);

  useEffect(() => {
    loadEvents();
    loadStats();
  }, [loadEvents, loadStats]);

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  const handleDecide = async (eventId: number, payload: TriageDecisionPayload) => {
    await api.decideTriage(eventId, payload);
    setEvents(prev => prev.filter(e => e.id !== eventId));
    setTotal(prev => prev - 1);
    if (stats) {
      setStats({ ...stats, pending_count: stats.pending_count - 1 });
    }
  };

  const handleSkip = (eventId: number) => {
    setSkipped(prev => new Set(prev).add(eventId));
  };

  const setFilter = (f: string) => {
    setPage(1);
    if (f) {
      setSearchParams({ filter: f });
    } else {
      setSearchParams({});
    }
  };

  const visibleEvents = events.filter(e => !skipped.has(e.id));
  const pendingCount = stats?.pending_count ?? total;

  // Group by color bucket — pre-filled map prevents undefined.push crash
  const grouped = groupByColorBucket(visibleEvents.map(e => ({ card: e.card, _ev: e })));
  // activeBuckets: maintain BUCKET_KEYS order, skip empty
  const activeBuckets = BUCKET_KEYS.filter(b => (grouped.get(b)?.length || 0) > 0);

  const toggleBucket = (bucket: BucketKey) => {
    setOpenColors(prev => {
      const next = new Set(prev);
      if (next.has(bucket)) next.delete(bucket);
      else next.add(bucket);
      return next;
    });
  };

  return (
    <div>
      <PageHeader
        eyebrow="⊕ TRIAGE · INBOX"
        title={t('inbox.title', { count: String(pendingCount) })}
        accent={accent.oklch}
      />

      {stats && (
        <div className={styles.statsRow}>
          <span>Pending: {stats.pending_count}</span>
          <span>Decided (30d): {stats.decided_last_30d}</span>
          {Object.entries(stats.by_state_30d).map(([state, count]) => (
            <span key={state}>{state}: {count}</span>
          ))}
        </div>
      )}

      {/* Filter bar */}
      <div className={styles.filterRow}>
        {FILTER_OPTIONS.map(opt => (
          <button
            key={opt.value}
            className={styles.filterPill}
            onClick={() => setFilter(opt.value)}
            style={activeFilter === opt.value ? { backgroundColor: accent.soft, borderColor: accent.oklch, color: sothera.fg } : undefined}
          >
            {opt.label}
          </button>
        ))}
      </div>

      <div className={styles.controls}>
        <span style={{ fontFamily: sothera.fontMono, fontSize: '10px', letterSpacing: '1px', color: sothera.fgFaint, textTransform: 'uppercase' }}>
          Min value
        </span>
        <Select value={String(minValue)} onChange={(_, d) => { setMinValue(parseFloat(d.value)); setPage(1); }} className={styles.select}>
          <option value="0">All</option>
          <option value="0.5">€0.50+</option>
          <option value="1">€1+</option>
          <option value="5">€5+</option>
          <option value="10">€10+</option>
          <option value="50">€50+</option>
        </Select>
      </div>

      {loading ? (
        <Spinner label="Loading inbox..." style={{ marginTop: 24 }} />
      ) : loadError && (stats?.pending_count ?? 0) > 0 ? (
        <ErrorBanner
          title={t('inbox.error.title')}
          message={t('inbox.error.api_failed', { count: String(stats!.pending_count) })}
          action={<Button onClick={loadEvents}>{t('common.retry')}</Button>}
        />
      ) : visibleEvents.length === 0 && (stats?.pending_count ?? 0) === 0 ? (
        <div className={styles.empty}>
          {t('inbox.empty_celebration')}
        </div>
      ) : visibleEvents.length === 0 && (stats?.pending_count ?? 0) > 0 ? (
        <ErrorBanner
          title={t('inbox.error.title')}
          message={t('inbox.error.api_failed', { count: String(stats!.pending_count) })}
          action={<Button onClick={loadEvents}>{t('common.retry')}</Button>}
        />
      ) : (
        <ErrorBoundary fallback={(err, retry) => (
          <ErrorBanner
            title="Inbox-Liste konnte nicht gerendert werden"
            message={`Render-Fehler: ${err.message}`}
            action={<Button onClick={retry}>{t('common.retry')}</Button>}
          />
        )}>
          <>
            {activeBuckets.map(bucket => {
              const bucketEvents = grouped.get(bucket)!.map(item => item._ev);
              const isOpen = openColors.has(bucket);
              return (
                <div key={bucket} className={styles.bucketSection}>
                  <div className={styles.bucketHeader} onClick={() => toggleBucket(bucket)}>
                    <span style={{ transition: 'transform 0.15s', transform: isOpen ? 'rotate(90deg)' : 'none', fontSize: 10 }}>▶</span>
                    <span>{INBOX_BUCKET_EMOJI[bucket]} {INBOX_BUCKET_LABELS[bucket]} ({bucketEvents.length})</span>
                  </div>
                  {isOpen && bucketEvents.map(event => (
                    <AcquisitionCard
                      key={event.id}
                      event={event}
                      onDecide={handleDecide}
                      onSkip={handleSkip}
                      defaultSource={defaultSource}
                      onSourceChange={handleSourceChange}
                    />
                  ))}
                </div>
              );
            })}

            {totalPages > 1 && (
              <div className={styles.pagination}>
                <Button icon={<ChevronLeft24Regular />} appearance="subtle" size="small" disabled={page <= 1} onClick={() => setPage(p => Math.max(1, p - 1))} />
                <span className={styles.pageInfo}>Page {page} of {totalPages}</span>
                <Button icon={<ChevronRight24Regular />} appearance="subtle" size="small" disabled={page >= totalPages} onClick={() => setPage(p => Math.min(totalPages, p + 1))} />
              </div>
            )}
          </>
        </ErrorBoundary>
      )}
    </div>
  );
}
