import { useState } from 'react';
import { Title2, makeStyles } from '@fluentui/react-components';
import { useQueryClient } from '@tanstack/react-query';
import { t } from '../i18n';
import WishlistAddForm from '../components/wishlist/WishlistAddForm';
import WishlistList from '../components/wishlist/WishlistList';

const useStyles = makeStyles({
  page: { display: 'flex', flexDirection: 'column', gap: '8px' },
});

export default function Wishlist() {
  const styles = useStyles();
  const queryClient = useQueryClient();
  const [refreshKey, setRefreshKey] = useState(0);

  const triggerRefresh = () => {
    setRefreshKey(k => k + 1);
    queryClient.invalidateQueries({ queryKey: ['wishlist'] });
    queryClient.invalidateQueries({ queryKey: ['wishlist-summary'] });
  };

  return (
    <div className={styles.page}>
      <Title2>{t('wishlist.title')}</Title2>
      <WishlistAddForm onAdded={triggerRefresh} />
      <WishlistList key={refreshKey} />
    </div>
  );
}
