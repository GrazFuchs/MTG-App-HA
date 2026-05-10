import { useEffect, useState, useCallback } from 'react';
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

const useStyles = makeStyles({
  controls: {
    display: 'flex',
    gap: '12px',
    marginBottom: '16px',
    flexWrap: 'wrap',
    alignItems: 'center',
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
});

export default function Inbox() {
  const styles = useStyles();
  const { accent } = useAccent();
  const [events, setEvents] = useState<AcquisitionEvent[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [loading, setLoading] = useState(true);
  const [minValue, setMinValue] = useState(0);
  const [stats, setStats] = useState<InboxAcquisitionStats | null>(null);
  const [skipped, setSkipped] = useState<Set<number>>(new Set());

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
    api.getPendingTriage(page, pageSize, minValue)
      .then(res => {
        setEvents(res.items);
        setTotal(res.total);
      })
      .catch(() => {
        setEvents([]);
        setTotal(0);
      })
      .finally(() => setLoading(false));
  }, [page, pageSize, minValue]);

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
    // Remove from list with animation effect (simple filter)
    setEvents(prev => prev.filter(e => e.id !== eventId));
    setTotal(prev => prev - 1);
    if (stats) {
      setStats({ ...stats, pending_count: stats.pending_count - 1 });
    }
  };

  const handleSkip = (eventId: number) => {
    setSkipped(prev => new Set(prev).add(eventId));
  };

  const visibleEvents = events.filter(e => !skipped.has(e.id));
  const pendingCount = stats?.pending_count ?? total;

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
      ) : visibleEvents.length === 0 ? (
        <div className={styles.empty}>
          {t('inbox.empty')}
        </div>
      ) : (
        <>
          {visibleEvents.map(event => (
            <AcquisitionCard
              key={event.id}
              event={event}
              onDecide={handleDecide}
              onSkip={handleSkip}
              defaultSource={defaultSource}
              onSourceChange={handleSourceChange}
            />
          ))}

          {totalPages > 1 && (
            <div className={styles.pagination}>
              <Button icon={<ChevronLeft24Regular />} appearance="subtle" size="small" disabled={page <= 1} onClick={() => setPage(p => Math.max(1, p - 1))} />
              <span className={styles.pageInfo}>Page {page} of {totalPages}</span>
              <Button icon={<ChevronRight24Regular />} appearance="subtle" size="small" disabled={page >= totalPages} onClick={() => setPage(p => Math.min(totalPages, p + 1))} />
            </div>
          )}
        </>
      )}
    </div>
  );
}
