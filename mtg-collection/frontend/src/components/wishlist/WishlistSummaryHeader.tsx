import { makeStyles, tokens, Badge, Card } from '@fluentui/react-components';
import { t } from '../../i18n';
import type { WishlistSummary } from '../../api';

const useStyles = makeStyles({
  row: {
    display: 'flex',
    gap: '12px',
    flexWrap: 'wrap',
    marginTop: '12px',
    marginBottom: '12px',
  },
  tile: {
    padding: '12px 16px',
    minWidth: '140px',
    flex: '1 1 auto',
  },
  label: {
    fontSize: '12px',
    color: tokens.colorNeutralForeground3,
    marginBottom: '4px',
  },
  value: {
    fontSize: '20px',
    fontWeight: 600,
  },
  dealsTile: {
    backgroundColor: tokens.colorPaletteGreenBackground1,
  },
});

interface Props {
  summary: WishlistSummary;
}

export default function WishlistSummaryHeader({ summary }: Props) {
  const styles = useStyles();

  const priorityDisplay = [5, 4, 3, 2, 1]
    .filter(p => (summary.by_priority[p] || 0) > 0)
    .map(p => `${'★'.repeat(p)} (${summary.by_priority[p]})`)
    .join(' | ');

  return (
    <div className={styles.row}>
      <Card className={styles.tile}>
        <div className={styles.label}>{t('wishlist.total_items')}</div>
        <div className={styles.value}>{summary.total_items}</div>
      </Card>
      <Card className={styles.tile}>
        <div className={styles.label}>{t('wishlist.total_target')}</div>
        <div className={styles.value}>€{summary.total_target_eur.toFixed(2)}</div>
      </Card>
      <Card className={styles.tile}>
        <div className={styles.label}>{t('wishlist.current_market')}</div>
        <div className={styles.value}>€{summary.total_current_eur.toFixed(2)}</div>
      </Card>
      <Card className={`${styles.tile} ${summary.items_below_target > 0 ? styles.dealsTile : ''}`}>
        <div className={styles.label}>{t('wishlist.below_target')}</div>
        <div className={styles.value}>
          {summary.items_below_target}
          {summary.items_below_target > 0 && (
            <Badge appearance="filled" color="success" style={{ marginLeft: 8, verticalAlign: 'middle' }}>
              {t('wishlist.deals_available')}
            </Badge>
          )}
        </div>
      </Card>
      {priorityDisplay && (
        <Card className={styles.tile}>
          <div className={styles.label}>{t('wishlist.by_priority')}</div>
          <div style={{ fontSize: '14px' }}>{priorityDisplay}</div>
        </Card>
      )}
    </div>
  );
}
