import { useState } from 'react';
import { makeStyles } from '@griffel/react';
import { useQueryClient } from '@tanstack/react-query';
import { t } from '../i18n';
import { useAccent } from '../main';
import { PageHeader } from '../components/sothera';
import WishlistAddForm from '../components/wishlist/WishlistAddForm';
import WishlistList from '../components/wishlist/WishlistList';

const useStyles = makeStyles({
  page: { display: 'flex', flexDirection: 'column', gap: '8px' },
});

export default function Wishlist() {
  const styles = useStyles();
  const { accent } = useAccent();
  const queryClient = useQueryClient();
  const [refreshKey, setRefreshKey] = useState(0);

  const triggerRefresh = () => {
    setRefreshKey(k => k + 1);
    queryClient.invalidateQueries({ queryKey: ['wishlist'] });
    queryClient.invalidateQueries({ queryKey: ['wishlist-summary'] });
  };

  return (
    <div className={styles.page}>
      <PageHeader eyebrow="✧ ACQUISITIONS" title={t('wishlist.title')} accent={accent.oklch} />
      <WishlistAddForm onAdded={triggerRefresh} />
      <WishlistList key={refreshKey} />
    </div>
  );
}
