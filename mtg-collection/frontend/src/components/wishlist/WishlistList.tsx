import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { Spinner, Body1, Button, makeStyles, Checkbox } from '@fluentui/react-components';
import { useSearchParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { t } from '../../i18n';
import { api, WishlistItem, WishlistSummary, DeckSummary } from '../../api';
import WishlistSummaryHeader from './WishlistSummaryHeader';
import WishlistFilterBar, {
  WishlistFilters,
  DEFAULT_FILTERS,
  filtersToParams,
  filtersFromSearchParams,
} from './WishlistFilterBar';
import WishlistExportButton from './WishlistExportButton';
import WishlistItemRow from './WishlistItemRow';
import WishlistEditDialog from './WishlistEditDialog';
import WishlistAcquireDialog from './WishlistAcquireDialog';
import WishlistOrderDialog from './WishlistOrderDialog';

const useStyles = makeStyles({
  topRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    flexWrap: 'wrap',
    gap: '12px',
  },
  list: { marginTop: '8px' },
  pagination: {
    display: 'flex',
    justifyContent: 'center',
    gap: '8px',
    marginTop: '16px',
    alignItems: 'center',
  },
});

const PAGE_SIZE = 50;

interface WishlistListProps {
  defaultStatus?: WishlistFilters['status'];
}

export default function WishlistList({ defaultStatus }: WishlistListProps) {
  const styles = useStyles();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const [filters, setFilters] = useState<WishlistFilters>(() => {
    const fromUrl = filtersFromSearchParams(searchParams);
    if (defaultStatus) {
      return { ...fromUrl, status: defaultStatus };
    }
    return fromUrl;
  });
  const [debouncedFilters, setDebouncedFilters] = useState<WishlistFilters>(filters);
  const [page, setPage] = useState(1);
  const [editItem, setEditItem] = useState<WishlistItem | null>(null);
  const [acquireItem, setAcquireItem] = useState<WishlistItem | null>(null);
  const [orderItem, setOrderItem] = useState<WishlistItem | null>(null);
  const [groupByName, setGroupByName] = useState(false);
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Persist filters to URL (scoped: don't leak tab-specific filters up)
  useEffect(() => {
    const params = filtersToParams(filters);
    setSearchParams(params, { replace: true });
  }, [filters, setSearchParams]);

  // Debounce filter changes for API calls (tag input)
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setDebouncedFilters(filters);
      setPage(1);
    }, 300);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [filters]);

  // Fetch decks
  const { data: decks = [] } = useQuery<DeckSummary[]>({
    queryKey: ['decks'],
    queryFn: () => api.getDecks(),
  });

  // Fetch summary (only shown for 'wanted' tab)
  const { data: summary } = useQuery<WishlistSummary>({
    queryKey: ['wishlist-summary'],
    queryFn: () => api.getWishlistSummary(),
    enabled: filters.status === 'wanted',
  });

  // Fetch items with filters
  const { data: items = [], isLoading } = useQuery<WishlistItem[]>({
    queryKey: ['wishlist', debouncedFilters],
    queryFn: () => api.getWishlist(filtersToParams(debouncedFilters)),
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['wishlist'] });
    queryClient.invalidateQueries({ queryKey: ['wishlist-summary'] });
    queryClient.invalidateQueries({ queryKey: ['wishlist-count'] });
  };

  // Mutations
  const dropMutation = useMutation({
    mutationFn: (id: number) => api.updateWishlistItem(id, { status: 'dropped' } as any),
    onSuccess: invalidate,
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.removeFromWishlist(id),
    onSuccess: invalidate,
  });

  const unorderMutation = useMutation({
    mutationFn: (id: number) => api.unorderWishlistItem(id),
    onSuccess: invalidate,
  });

  const notReceivedMutation = useMutation({
    mutationFn: (id: number) => api.markWishlistNotReceived(id),
    onSuccess: invalidate,
  });

  const handleFilterChange = useCallback((next: WishlistFilters) => {
    setFilters(next);
  }, []);

  const handleSaved = () => invalidate();

  // Pagination
  const totalPages = Math.max(1, Math.ceil(items.length / PAGE_SIZE));
  const pagedItems = items.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  // Group by card name
  const groupedItems = useMemo(() => {
    if (!groupByName) return null;
    const map = new Map<string, WishlistItem[]>();
    for (const item of pagedItems) {
      const key = item.card_name;
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(item);
    }
    return map;
  }, [groupByName, pagedItems]);

  const toggleGroupExpand = (name: string) => {
    setExpandedGroups(prev => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name); else next.add(name);
      return next;
    });
  };

  return (
    <div>
      {summary && filters.status === 'wanted' && <WishlistSummaryHeader summary={summary} />}

      <div className={styles.topRow}>
        <WishlistFilterBar filters={filters} onChange={handleFilterChange} decks={decks} />
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <Checkbox
            label="Group by name"
            checked={groupByName}
            onChange={(_, d) => setGroupByName(!!d.checked)}
          />
          <WishlistExportButton />
        </div>
      </div>

      {isLoading ? (
        <Spinner label={t('common.loading')} />
      ) : items.length === 0 ? (
        <Body1 style={{ marginTop: 24 }}>{t('wishlist.empty')}</Body1>
      ) : (
        <>
          <div className={styles.list}>
            {groupByName && groupedItems ? (
              Array.from(groupedItems.entries()).map(([name, groupItems]) => (
                <div key={name}>
                  {groupItems.length > 1 ? (
                    <>
                      <div
                        onClick={() => toggleGroupExpand(name)}
                        style={{ cursor: 'pointer', padding: '8px 12px', fontWeight: 600, fontSize: 14, display: 'flex', alignItems: 'center', gap: 8, borderBottom: '1px solid var(--colorNeutralStroke2)' }}
                      >
                        <span style={{ transition: 'transform 0.15s', display: 'inline-block', transform: expandedGroups.has(name) ? 'rotate(90deg)' : 'none', fontSize: 10 }}>▶</span>
                        {name}
                        <span style={{ fontSize: 11, fontWeight: 400, opacity: 0.6 }}>({groupItems.length} printings)</span>
                      </div>
                      {expandedGroups.has(name) && groupItems.map(item => (
                        <WishlistItemRow
                          key={item.id}
                          item={item}
                          onEdit={setEditItem}
                          onAcquire={id => { const found = items.find(i => i.id === id); if (found) setAcquireItem(found); }}
                          onOrder={item => setOrderItem(item)}
                          onUnorder={id => unorderMutation.mutate(id)}
                          onNotReceived={id => notReceivedMutation.mutate(id)}
                          onDrop={id => dropMutation.mutate(id)}
                          onDelete={id => deleteMutation.mutate(id)}
                        />
                      ))}
                    </>
                  ) : (
                    <WishlistItemRow
                      key={groupItems[0].id}
                      item={groupItems[0]}
                      onEdit={setEditItem}
                      onAcquire={id => { const found = items.find(i => i.id === id); if (found) setAcquireItem(found); }}
                      onOrder={item => setOrderItem(item)}
                      onUnorder={id => unorderMutation.mutate(id)}
                      onNotReceived={id => notReceivedMutation.mutate(id)}
                      onDrop={id => dropMutation.mutate(id)}
                      onDelete={id => deleteMutation.mutate(id)}
                    />
                  )}
                </div>
              ))
            ) : (
              pagedItems.map(item => (
                <WishlistItemRow
                  key={item.id}
                  item={item}
                  onEdit={setEditItem}
                  onAcquire={id => {
                    const found = items.find(i => i.id === id);
                    if (found) setAcquireItem(found);
                  }}
                  onOrder={item => setOrderItem(item)}
                  onUnorder={id => unorderMutation.mutate(id)}
                  onNotReceived={id => notReceivedMutation.mutate(id)}
                  onDrop={id => dropMutation.mutate(id)}
                  onDelete={id => deleteMutation.mutate(id)}
                />
              ))
            )}
          </div>

          {totalPages > 1 && (
            <div className={styles.pagination}>
              <Button
                appearance="subtle"
                disabled={page <= 1}
                onClick={() => setPage(p => p - 1)}
              >
                ←
              </Button>
              <Body1>{t('common.page_of', { page, total: totalPages })}</Body1>
              <Button
                appearance="subtle"
                disabled={page >= totalPages}
                onClick={() => setPage(p => p + 1)}
              >
                →
              </Button>
            </div>
          )}
        </>
      )}

      {editItem && (
        <WishlistEditDialog
          item={editItem}
          decks={decks}
          onClose={() => setEditItem(null)}
          onSaved={handleSaved}
        />
      )}

      {acquireItem && (
        <WishlistAcquireDialog
          item={acquireItem}
          onClose={() => setAcquireItem(null)}
          onAcquired={invalidate}
        />
      )}

      {orderItem && (
        <WishlistOrderDialog
          item={orderItem}
          onClose={() => setOrderItem(null)}
          onOrdered={invalidate}
        />
      )}
    </div>
  );
}

