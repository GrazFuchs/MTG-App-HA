import { useState, useEffect, useRef, useCallback } from 'react';
import { Spinner, Body1, Button, makeStyles } from '@fluentui/react-components';
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

  return (
    <div>
      {summary && filters.status === 'wanted' && <WishlistSummaryHeader summary={summary} />}

      <div className={styles.topRow}>
        <WishlistFilterBar filters={filters} onChange={handleFilterChange} decks={decks} />
        <WishlistExportButton />
      </div>

      {isLoading ? (
        <Spinner label={t('common.loading')} />
      ) : items.length === 0 ? (
        <Body1 style={{ marginTop: 24 }}>{t('wishlist.empty')}</Body1>
      ) : (
        <>
          <div className={styles.list}>
            {pagedItems.map(item => (
              <WishlistItemRow
                key={item.id}
                item={item}
                onEdit={setEditItem}
                onAcquire={id => {
                  // Quick acquire without dialog if item has expected_price_eur
                  const found = items.find(i => i.id === id);
                  if (found) setAcquireItem(found);
                }}
                onOrder={item => setOrderItem(item)}
                onUnorder={id => unorderMutation.mutate(id)}
                onNotReceived={id => notReceivedMutation.mutate(id)}
                onDrop={id => dropMutation.mutate(id)}
                onDelete={id => deleteMutation.mutate(id)}
              />
            ))}
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
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Persist filters to URL
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

  // Fetch summary
  const { data: summary } = useQuery<WishlistSummary>({
    queryKey: ['wishlist-summary'],
    queryFn: () => api.getWishlistSummary(),
  });

  // Fetch items with filters
  const { data: items = [], isLoading } = useQuery<WishlistItem[]>({
    queryKey: ['wishlist', debouncedFilters],
    queryFn: () => api.getWishlist(filtersToParams(debouncedFilters)),
  });

  // Mutations
  const acquireMutation = useMutation({
    mutationFn: (id: number) => api.acquireWishlistItem(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['wishlist'] });
      queryClient.invalidateQueries({ queryKey: ['wishlist-summary'] });
    },
  });

  const dropMutation = useMutation({
    mutationFn: (id: number) => api.updateWishlistItem(id, { status: 'dropped' } as any),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['wishlist'] });
      queryClient.invalidateQueries({ queryKey: ['wishlist-summary'] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.removeFromWishlist(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['wishlist'] });
      queryClient.invalidateQueries({ queryKey: ['wishlist-summary'] });
    },
  });

  const handleFilterChange = useCallback((next: WishlistFilters) => {
    setFilters(next);
  }, []);

  const handleSaved = () => {
    queryClient.invalidateQueries({ queryKey: ['wishlist'] });
    queryClient.invalidateQueries({ queryKey: ['wishlist-summary'] });
  };

  // Pagination
  const totalPages = Math.max(1, Math.ceil(items.length / PAGE_SIZE));
  const pagedItems = items.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  return (
    <div>
      {summary && <WishlistSummaryHeader summary={summary} />}

      <div className={styles.topRow}>
        <WishlistFilterBar filters={filters} onChange={handleFilterChange} decks={decks} />
        <WishlistExportButton />
      </div>

      {isLoading ? (
        <Spinner label={t('common.loading')} />
      ) : items.length === 0 ? (
        <Body1 style={{ marginTop: 24 }}>{t('wishlist.empty')}</Body1>
      ) : (
        <>
          <div className={styles.list}>
            {pagedItems.map(item => (
              <WishlistItemRow
                key={item.id}
                item={item}
                onEdit={setEditItem}
                onAcquire={id => acquireMutation.mutate(id)}
                onDrop={id => dropMutation.mutate(id)}
                onDelete={id => deleteMutation.mutate(id)}
              />
            ))}
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
    </div>
  );
}
