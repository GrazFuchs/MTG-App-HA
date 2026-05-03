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

export default function WishlistList() {
  const styles = useStyles();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const [filters, setFilters] = useState<WishlistFilters>(() => filtersFromSearchParams(searchParams));
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
