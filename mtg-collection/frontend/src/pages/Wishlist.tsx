import { useState } from 'react';
import { makeStyles } from '@griffel/react';
import { TabList, Tab, Badge } from '@fluentui/react-components';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import { t } from '../i18n';
import { useAccent } from '../main';
import { PageHeader } from '../components/sothera';
import WishlistAddForm from '../components/wishlist/WishlistAddForm';
import WishlistList from '../components/wishlist/WishlistList';
import { api, WishlistItem } from '../api';

const useStyles = makeStyles({
  page: { display: 'flex', flexDirection: 'column', gap: '8px' },
  tabRow: { marginBottom: '4px' },
});

type WishlistTab = 'wanted' | 'acquired' | 'not_received' | 'dropped';

const TABS: { value: WishlistTab; label: string }[] = [
  { value: 'wanted',       label: 'wishlist.tab_active' },
  { value: 'acquired',     label: 'wishlist.tab_history' },
  { value: 'not_received', label: 'wishlist.tab_lost' },
  { value: 'dropped',      label: 'wishlist.tab_dropped' },
];

function useTabCount(status: WishlistTab) {
  const params = new URLSearchParams();
  params.set('status', status);
  params.set('page_size', '200');
  const { data } = useQuery<WishlistItem[]>({
    queryKey: ['wishlist-count', status],
    queryFn: () => api.getWishlist(params),
    staleTime: 60_000,
  });
  return data?.length ?? null;
}

export default function Wishlist() {
  const styles = useStyles();
  const { accent } = useAccent();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();

  // Tab state persisted in URL: ?tab=acquired etc.
  const tabFromUrl = (searchParams.get('tab') as WishlistTab | null);
  const validTabs = new Set<WishlistTab>(['wanted', 'acquired', 'not_received', 'dropped']);
  const [activeTab, setActiveTab] = useState<WishlistTab>(
    tabFromUrl && validTabs.has(tabFromUrl) ? tabFromUrl : 'wanted'
  );

  const handleTabSelect = (tab: WishlistTab) => {
    setActiveTab(tab);
    const next = new URLSearchParams(searchParams);
    next.set('tab', tab);
    setSearchParams(next, { replace: true });
  };

  const [refreshKey, setRefreshKey] = useState(0);

  const wantedCount     = useTabCount('wanted');
  const acquiredCount   = useTabCount('acquired');
  const lostCount       = useTabCount('not_received');
  const droppedCount    = useTabCount('dropped');

  const counts: Record<WishlistTab, number | null> = {
    wanted:       wantedCount,
    acquired:     acquiredCount,
    not_received: lostCount,
    dropped:      droppedCount,
  };

  const triggerRefresh = () => {
    setRefreshKey(k => k + 1);
    queryClient.invalidateQueries({ queryKey: ['wishlist'] });
    queryClient.invalidateQueries({ queryKey: ['wishlist-summary'] });
    queryClient.invalidateQueries({ queryKey: ['wishlist-count'] });
  };

  return (
    <div className={styles.page}>
      <PageHeader eyebrow="✧ ACQUISITIONS" title={t('wishlist.title')} accent={accent.oklch} />
      <WishlistAddForm onAdded={triggerRefresh} />

      <div className={styles.tabRow}>
        <TabList
          selectedValue={activeTab}
          onTabSelect={(_, d) => handleTabSelect(d.value as WishlistTab)}
          appearance="subtle"
        >
          {TABS.map(tab => (
            <Tab key={tab.value} value={tab.value}>
              {t(tab.label as any)}
              {counts[tab.value] !== null && (
                <Badge
                  appearance="tint"
                  size="small"
                  style={{ marginLeft: 6 }}
                >
                  {counts[tab.value]}
                </Badge>
              )}
            </Tab>
          ))}
        </TabList>
      </div>

      <WishlistList key={`${activeTab}-${refreshKey}`} defaultStatus={activeTab} />
    </div>
  );
}
