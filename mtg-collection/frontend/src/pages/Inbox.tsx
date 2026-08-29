import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { makeStyles } from '@griffel/react';
import { Button, Checkbox, Input, Select, Spinner } from '@fluentui/react-components';
import {
  ChevronLeft24Regular,
  ChevronRight24Regular,
  Search24Regular,
} from '@fluentui/react-icons';
import { api, AcquisitionEvent, TriageDecisionPayload, InboxAcquisitionStats } from '../api';
import { sothera } from '../theme/sothera';
import { useAccent } from '../main';
import { PageHeader } from '../components/sothera';
import { t } from '../i18n';
import { BUCKET_EMOJI, colorName, colorOptions } from '../utils/colors';
import AcquisitionCard from '../components/inbox/AcquisitionCard';
import InboxHistory from '../components/inbox/InboxHistory';
import { ErrorBanner } from '../components/ErrorBanner';
import { ErrorBoundary } from '../components/ErrorBoundary';
import { getColorBucket, groupByColorBucket, BUCKET_KEYS, BucketKey } from '../utils/colors';

import { dropDecided, type InboxPage } from './inboxList';
// Re-export for unit tests
export { getColorBucket, groupByColorBucket, BUCKET_KEYS };
export type { BucketKey };

const FILTER_OPTIONS = [
  { value: '', label: 'inbox.filter.all' },
  { value: 'needs_sell', label: 'inbox.filter.needs_sell' },
  { value: 'needs_keep', label: 'inbox.filter.needs_keep' },
] as const;

// 'L' (lands) is a filter value only: the grouping buckets come from the card's
// colour identity, and a land has none.
const COLOR_FILTER_OPTIONS = colorOptions(['W', 'U', 'B', 'R', 'G', 'Multi', 'Colorless', 'L']);

const SORT_OPTIONS = [
  { value: 'newest', label: 'inbox.sort_newest' },
  { value: 'color', label: 'inbox.sort_color' },
  { value: 'set', label: 'inbox.sort_set' },
  { value: 'name', label: 'inbox.sort_name' },
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
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const [page, setPage] = useState(1);
  const [pageSize] = useState(50);
  const [minValue, setMinValue] = useState(0);
  const [skipped, setSkipped] = useState<Set<number>>(new Set());
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [decisionError, setDecisionError] = useState<string | null>(null);
  const [lastDecision, setLastDecision] = useState<{ ids: number[]; label: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [searchInput, setSearchInput] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [colorFilter, setColorFilter] = useState('');
  const [sortBy, setSortBy] = useState('newest');
  const [view, setView] = useState<'triage' | 'history'>('triage');

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

  const { data: eventsData, isLoading: loading, isError: loadError, refetch: refetchEvents } = useQuery({
    queryKey: ['inbox-pending', page, pageSize, minValue, activeFilter, searchQuery, colorFilter, sortBy],
    queryFn: () => api.getPendingTriage(page, pageSize, minValue, activeFilter, searchQuery, colorFilter, sortBy),
    staleTime: 30_000,
  });

  const { data: stats, refetch: refetchStats } = useQuery<InboxAcquisitionStats>({
    queryKey: ['inbox-stats'],
    queryFn: () => api.getInboxStats(),
    staleTime: 30_000,
  });

  const backfillColors = useMutation({
    mutationFn: () => api.backfillInboxColors(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['inbox-pending'] });
    },
  });

  const events = eventsData?.items ?? [];
  const total = eventsData?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  /**
   * Take decided cards out of the loaded page instead of refetching it.
   *
   * Invalidating `inbox-pending` replaced the whole list, which re-collapsed
   * the colour groups and threw the scroll position away after every single
   * decision — with 137 cards in one bucket that is the difference between
   * triaging and hunting for your place again.
   */
  const dropFromList = (ids: number[]) => {
    queryClient.setQueriesData<InboxPage>(
      { queryKey: ['inbox-pending'] },
      (old) => dropDecided(old, ids),
    );
    queryClient.invalidateQueries({ queryKey: ['inbox-stats'] });
    setSelected(prev => {
      const next = new Set(prev);
      ids.forEach(id => next.delete(id));
      return next;
    });
  };

  const handleDecide = async (eventId: number, payload: TriageDecisionPayload) => {
    // No catch at all used to live here: a rejected decision vanished into the
    // console while the card sat there looking undecided.
    try {
      await api.decideTriage(eventId, payload);
      setDecisionError(null);
      dropFromList([eventId]);
      setLastDecision({ ids: [eventId], label: t('inbox.undo_one', { action: payload.action }) });
    } catch (err) {
      setDecisionError(err instanceof Error ? err.message : String(err));
      throw err;
    }
  };

  const bulkDecide = async (action: 'keep' | 'dismiss') => {
    const ids = [...selected];
    if (!ids.length) return;
    setBusy(true);
    try {
      const res = await api.bulkDecideTriage(ids, action, defaultSource ?? undefined);
      dropFromList(res.event_ids);
      setDecisionError(
        res.failed.length
          ? t('inbox.bulk.partial_failure', { failed: res.failed.length, total: ids.length, error: res.failed[0].error })
          : null,
      );
      if (res.event_ids.length) {
        setLastDecision({ ids: res.event_ids, label: t('inbox.undo_many', { count: res.event_ids.length, action }) });
      }
    } catch (err) {
      setDecisionError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  /** `POST /undo` shipped without a single caller — 964 decisions with no way back. */
  const undoLast = async () => {
    if (!lastDecision) return;
    setBusy(true);
    try {
      await Promise.all(lastDecision.ids.map(id => api.undoTriage(id)));
      setLastDecision(null);
      queryClient.invalidateQueries({ queryKey: ['inbox-pending'] });
      queryClient.invalidateQueries({ queryKey: ['inbox-stats'] });
    } catch (err) {
      setDecisionError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const visibleIds = events.map(e => e.id);
  const allVisibleSelected = visibleIds.length > 0 && visibleIds.every(id => selected.has(id));

  const toggleOne = (id: number, on: boolean) =>
    setSelected(prev => {
      const next = new Set(prev);
      if (on) next.add(id); else next.delete(id);
      return next;
    });

  const toggleAllVisible = (on: boolean) =>
    setSelected(prev => {
      const next = new Set(prev);
      visibleIds.forEach(id => (on ? next.add(id) : next.delete(id)));
      return next;
    });

  /**
   * K and D decide the current selection.
   *
   * Deliberately not "the focused card": with a hundred cards in one bucket
   * the thing you are working on is the selection, and a shortcut that acts on
   * whatever the browser considers focused is a shortcut nobody can predict.
   * Selling stays out of it — it needs a price.
   */
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      if (target && /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName)) return;
      if (e.metaKey || e.ctrlKey || e.altKey || !selected.size) return;
      const key = e.key.toLowerCase();
      if (key === 'k') { e.preventDefault(); void bulkDecide('keep'); }
      if (key === 'd') { e.preventDefault(); void bulkDecide('dismiss'); }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });

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

  // Whether the empty result is something the user asked for. Without this the
  // page cannot tell "your filter matched nothing" from "the backend failed",
  // and reported the first as the second.
  const hasActiveFilters = Boolean(
    searchQuery || colorFilter || activeFilter || minValue > 0
  );

  const clearFilters = () => {
    setSearchInput('');
    setSearchQuery('');
    setColorFilter('');
    setMinValue(0);
    setSearchParams({});
    setPage(1);
  };

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
          <span>{t('inbox.stats.pending')}: {stats.pending_count}</span>
          <span>{t('inbox.stats.decided_30d')}: {stats.decided_last_30d}</span>
          {Object.entries(stats.by_state_30d).map(([state, count]) => (
            <span key={state}>{state}: {count}</span>
          ))}
        </div>
      )}

      {/* Triage / History view toggle */}
      <div className={styles.filterRow}>
        {(['triage', 'history'] as const).map(v => (
          <button
            key={v}
            className={styles.filterPill}
            onClick={() => setView(v)}
            style={view === v ? { backgroundColor: accent.soft, borderColor: accent.oklch, color: sothera.fg } : undefined}
          >
            {v === 'triage' ? t('inbox.tab_triage') : t('inbox.tab_history')}
          </button>
        ))}
      </div>

      {view === 'history' ? (
        <InboxHistory />
      ) : (
      <>
      {/* Filter bar */}
      <div className={styles.filterRow}>
        {FILTER_OPTIONS.map(opt => (
          <button
            key={opt.value}
            className={styles.filterPill}
            onClick={() => setFilter(opt.value)}
            style={activeFilter === opt.value ? { backgroundColor: accent.soft, borderColor: accent.oklch, color: sothera.fg } : undefined}
          >
            {t(opt.label)}
          </button>
        ))}
      </div>

      <div className={styles.controls}>
        <Input
          placeholder={t('inbox.search')}
          contentBefore={<Search24Regular />}
          value={searchInput}
          onChange={(_, d) => setSearchInput(d.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') { setSearchQuery(searchInput.trim()); setPage(1); } }}
          style={{ minWidth: 200, maxWidth: 320, flex: 1 }}
        />
        <Select
          value={colorFilter}
          onChange={(_, d) => { setColorFilter(d.value); setPage(1); }}
          className={styles.select}
          aria-label={t('inbox.color_filter')}
        >
          {COLOR_FILTER_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
        </Select>
        <Select
          value={sortBy}
          onChange={(_, d) => { setSortBy(d.value); setPage(1); }}
          className={styles.select}
          aria-label={t('inbox.sort_by')}
        >
          {SORT_OPTIONS.map(o => <option key={o.value} value={o.value}>{t('inbox.sort_by')}: {t(o.label)}</option>)}
        </Select>
        <span style={{ fontFamily: sothera.fontMono, fontSize: '10px', letterSpacing: '1px', color: sothera.fgFaint, textTransform: 'uppercase' }}>
          {t('inbox.min_value')}
        </span>
        <Select value={String(minValue)} onChange={(_, d) => { setMinValue(parseFloat(d.value)); setPage(1); }} className={styles.select}>
          <option value="0">{t('common.all')}</option>
          <option value="0.5">€0.50+</option>
          <option value="1">€1+</option>
          <option value="5">€5+</option>
          <option value="10">€10+</option>
          <option value="50">€50+</option>
        </Select>
        <Button
          size="small"
          appearance="subtle"
          disabled={backfillColors.isPending}
          onClick={() => backfillColors.mutate()}
          title={t('inbox.refetch_colors')}
        >
          {backfillColors.isPending ? t('inbox.enriching') : '↻ Fix colors'}
        </Button>
      </div>

      {loading ? (
        <Spinner label={t('inbox.loading')} style={{ marginTop: 24 }} />
      ) : loadError ? (
        /* A failed request is the ONLY thing that earns the error banner.
           A filter that matches nothing is a normal, expected answer — it used
           to land here too and accused the backend of losing 140 cards. */
        <ErrorBanner
          title={t('inbox.error.title')}
          message={t('inbox.error.api_failed', { count: String(stats?.pending_count ?? 0) })}
          action={<Button onClick={() => refetchEvents()}>{t('common.retry')}</Button>}
        />
      ) : visibleEvents.length === 0 && hasActiveFilters ? (
        <div className={styles.empty}>
          <div style={{ fontSize: 28, marginBottom: 10 }}>🔍</div>
          <div>{t('inbox.no_matches')}</div>
          <div style={{ fontFamily: sothera.fontMono, fontSize: 11, color: sothera.fgFaint, marginTop: 8, letterSpacing: '0.5px' }}>
            {t('inbox.no_matches_hint', { count: String(pendingCount) })}
          </div>
          <div style={{ marginTop: 16 }}>
            <Button size="small" onClick={clearFilters}>{t('inbox.clear_filters')}</Button>
          </div>
        </div>
      ) : visibleEvents.length === 0 && skipped.size > 0 ? (
        <div className={styles.empty}>
          <div>{t('inbox.all_skipped')}</div>
          <div style={{ marginTop: 16 }}>
            <Button size="small" onClick={() => setSkipped(new Set())}>{t('inbox.unskip')}</Button>
          </div>
        </div>
      ) : visibleEvents.length === 0 ? (
        <div className={styles.empty}>
          {t('inbox.empty_celebration')}
        </div>
      ) : (
        <ErrorBoundary fallback={(err, retry) => (
          <ErrorBanner
            title={t('inbox.render_failed')}
            message={`Render-Fehler: ${err.message}`}
            action={<Button onClick={retry}>{t('common.retry')}</Button>}
          />
        )}>
          <>
            {decisionError && (
              <div style={{ marginBottom: 12 }}>
                <ErrorBanner
                  title={t('inbox.decision_failed')}
                  message={decisionError}
                  action={<Button size="small" onClick={() => setDecisionError(null)}>{t('inbox.action.dismiss')}</Button>}
                />
              </div>
            )}

            {lastDecision && (
              <div style={{
                marginBottom: 12, padding: '8px 12px', display: 'flex', gap: 12,
                alignItems: 'center', background: sothera.glassBg,
                border: `1px solid ${sothera.glassBorder}`, borderRadius: 4,
              }}>
                <span style={{ fontSize: 12, color: sothera.fgMuted }}>
                  {t('inbox.decided_label', { label: lastDecision.label })}
                </span>
                <Button size="small" appearance="subtle" disabled={busy} onClick={undoLast}>
                  {t('common.undo')}
                </Button>
                <Button size="small" appearance="transparent" onClick={() => setLastDecision(null)}>
                  ✕
                </Button>
              </div>
            )}

            {/* Bulk bar. The real workload is a bulk import landing at once —
                127 of the 137 open cards are worth under 50 cents — so the
                unit of work is a selection, not a card. */}
            <div style={{
              marginBottom: 12, display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap',
            }}>
              <Checkbox
                label={t('inbox.bulk.select_all_n', { count: visibleIds.length })}
                checked={allVisibleSelected}
                onChange={(_, d) => toggleAllVisible(!!d.checked)}
              />
              <span style={{ fontSize: 12, color: sothera.fgMuted, fontFamily: sothera.fontMono }}>
                {t('inbox.bulk.selected', { count: selected.size })}
              </span>
              <Button size="small" disabled={!selected.size || busy} onClick={() => bulkDecide('keep')}>
                {t('inbox.action.keep_n', { count: selected.size })}
              </Button>
              <Button size="small" disabled={!selected.size || busy} onClick={() => bulkDecide('dismiss')}>
                {t('inbox.action.dismiss_n', { count: selected.size })}
              </Button>
              <span style={{ fontSize: 10, color: sothera.fgFaint, fontFamily: sothera.fontMono }}>
                {t('inbox.shortcut_hint')}
              </span>
            </div>

            {activeBuckets.map(bucket => {
              const bucketEvents = grouped.get(bucket)!.map(item => item._ev);
              const isOpen = openColors.has(bucket);
              return (
                <div key={bucket} className={styles.bucketSection}>
                  <div className={styles.bucketHeader} onClick={() => toggleBucket(bucket)}>
                    <span style={{ transition: 'transform 0.15s', transform: isOpen ? 'rotate(90deg)' : 'none', fontSize: 10 }}>▶</span>
                    <span>{BUCKET_EMOJI[bucket] ?? BUCKET_EMOJI.Unknown} {colorName(bucket)} ({bucketEvents.length})</span>
                  </div>
                  {isOpen && bucketEvents.map(event => (
                    <div key={event.id} style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
                      <Checkbox
                        checked={selected.has(event.id)}
                        onChange={(_, d) => toggleOne(event.id, !!d.checked)}
                        aria-label={`Select ${event.card.name}`}
                        style={{ marginTop: 12 }}
                      />
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <AcquisitionCard
                          event={event}
                          onDecide={handleDecide}
                          onSkip={handleSkip}
                          defaultSource={defaultSource}
                          onSourceChange={handleSourceChange}
                        />
                      </div>
                    </div>
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
      </>
      )}
    </div>
  );
}
