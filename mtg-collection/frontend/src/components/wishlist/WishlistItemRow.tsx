import {
  makeStyles,
  tokens,
  Badge,
  Caption1,
  Menu,
  MenuTrigger,
  MenuPopover,
  MenuList,
  MenuItem,
  Button,
} from '@fluentui/react-components';
import {
  MoreHorizontal24Regular,
  Edit24Regular,
  Checkmark24Regular,
  ArrowDown24Regular,
  Delete24Regular,
  Open24Regular,
  Box24Regular,
  DismissCircle24Regular,
} from '@fluentui/react-icons';
import { t } from '../../i18n';
import { useMediaQuery } from '../../hooks/useMediaQuery';
import PriceTrendHover from '../PriceTrendHover';
import type { WishlistItem } from '../../api';

const useStyles = makeStyles({
  row: {
    display: 'grid',
    gridTemplateColumns: '48px 1fr 50px 100px 200px 80px 100px 48px',
    gap: '8px',
    alignItems: 'center',
    padding: '8px 12px',
    borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
    ':hover': { backgroundColor: tokens.colorNeutralBackground1Hover },
  },
  mobileRow: {
    display: 'flex',
    gap: '12px',
    padding: '12px',
    borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
    ':hover': { backgroundColor: tokens.colorNeutralBackground1Hover },
  },
  img: {
    width: '44px',
    height: '62px',
    objectFit: 'cover',
    borderRadius: '3px',
    backgroundColor: tokens.colorNeutralBackground3,
  },
  mobileImg: {
    width: '56px',
    height: '78px',
    objectFit: 'cover',
    borderRadius: '4px',
    backgroundColor: tokens.colorNeutralBackground3,
  },
  mobileInfo: { flex: 1, display: 'flex', flexDirection: 'column', gap: '4px' },
  name: { fontWeight: 600, fontSize: '14px' },
  tags: { display: 'flex', gap: '4px', flexWrap: 'wrap', marginTop: '2px' },
  priceCell: { fontSize: '13px', lineHeight: '1.4' },
  deal: { color: tokens.colorPaletteGreenForeground1, fontWeight: 600 },
  above: { color: tokens.colorNeutralForeground3 },
  deltaPositive: { color: tokens.colorPaletteRedForeground1, fontSize: '12px' },
  deltaNegative: { color: tokens.colorPaletteGreenForeground1, fontSize: '12px' },
  orderedBadge: { marginLeft: '4px' },
  sourceBadge: { fontSize: '11px', color: tokens.colorNeutralForeground3 },
});

interface Props {
  item: WishlistItem;
  onEdit: (item: WishlistItem) => void;
  onAcquire: (id: number) => void;
  onOrder: (item: WishlistItem) => void;
  onUnorder: (id: number) => void;
  onNotReceived: (id: number) => void;
  onDrop: (id: number) => void;
  onDelete: (id: number) => void;
}

function PriceDisplay({ item }: { item: WishlistItem }) {
  const styles = useStyles();
  const current = item.current_price_eur;
  const target = item.target_price_eur;

  // History view: show paid_price + Δ vs current market
  if (item.status === 'acquired') {
    const paid = item.paid_price_eur;
    return (
      <div className={styles.priceCell}>
        <div>Paid: {paid != null ? `€${paid.toFixed(2)}` : '—'}</div>
        {current != null && <div>Market: €{current.toFixed(2)}</div>}
        {item.price_delta_eur != null && item.price_delta_pct != null && (
          <div className={item.price_delta_eur > 0 ? styles.deltaPositive : styles.deltaNegative}>
            {item.price_delta_eur > 0 ? '+' : ''}€{item.price_delta_eur.toFixed(2)}
            {' '}({item.price_delta_pct > 0 ? '+' : ''}{item.price_delta_pct.toFixed(0)}%)
          </div>
        )}
      </div>
    );
  }

  if (current == null) {
    return <span className={styles.above}>— / {target > 0 ? `€${target.toFixed(2)}` : '—'}</span>;
  }

  const delta = target > 0 ? current - target : null;
  const pct = target > 0 ? ((current - target) / target) * 100 : null;
  const isDeal = item.is_deal;

  return (
    <div className={styles.priceCell}>
      <div>
        {t('wishlist.target_short')}: {target > 0 ? `€${target.toFixed(2)}` : '—'}
      </div>
      <div>
        {t('wishlist.current_short')}: €{current.toFixed(2)}
      </div>
      {delta != null && (
        <div className={isDeal ? styles.deal : styles.above}>
          {delta >= 0 ? '+' : ''}€{delta.toFixed(2)}
          {pct != null && ` (${pct >= 0 ? '+' : ''}${pct.toFixed(0)}%)`}
        </div>
      )}
    </div>
  );
}

function StatusBadge({ item }: { item: WishlistItem }) {
  const colorMap = { wanted: 'informative', acquired: 'success', dropped: 'danger', not_received: 'warning' } as const;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4, alignItems: 'flex-start' }}>
      <Badge appearance="filled" color={colorMap[item.status] || 'informative'}>
        {t(`wishlist.status_${item.status}`)}
      </Badge>
      {item.is_ordered && item.status === 'wanted' && (
        <Badge
          appearance="tint"
          color="brand"
          size="small"
          shape="rounded"
          style={{ fontSize: 10, fontWeight: 600, whiteSpace: 'nowrap' }}
        >
          📦 {t('wishlist.status_ordered')}{item.expected_price_eur != null ? ` · €${item.expected_price_eur.toFixed(2)}` : ''}
        </Badge>
      )}
      {item.source && (
        <Caption1 style={{ fontSize: 10, color: tokens.colorNeutralForeground3 }}>{item.source}</Caption1>
      )}
    </div>
  );
}

export default function WishlistItemRow({ item, onEdit, onAcquire, onOrder, onUnorder, onNotReceived, onDrop, onDelete }: Props) {
  const styles = useStyles();
  const isMobile = useMediaQuery('(max-width: 768px)');

  const cardmarketUrl = `https://www.cardmarket.com/en/Magic/Products/Search?searchString=${encodeURIComponent(item.card_name)}`;

  const actionsMenu = (
    <Menu>
      <MenuTrigger disableButtonEnhancement>
        <Button icon={<MoreHorizontal24Regular />} appearance="subtle" size="small" aria-label="Actions" />
      </MenuTrigger>
      <MenuPopover>
        <MenuList>
          <MenuItem icon={<Edit24Regular />} onClick={() => onEdit(item)}>{t('wishlist.action_edit')}</MenuItem>
          {item.status === 'wanted' && !item.is_ordered && (
            <MenuItem icon={<Box24Regular />} onClick={() => onOrder(item)}>{t('wishlist.action_order')}</MenuItem>
          )}
          {item.status === 'wanted' && item.is_ordered && (
            <MenuItem icon={<DismissCircle24Regular />} onClick={() => onUnorder(item.id)}>{t('wishlist.action_unorder')}</MenuItem>
          )}
          {item.status === 'wanted' && (
            <MenuItem icon={<Checkmark24Regular />} onClick={() => onAcquire(item.id)}>{t('wishlist.action_acquire')}</MenuItem>
          )}
          {item.status === 'wanted' && item.is_ordered && (
            <MenuItem icon={<DismissCircle24Regular />} onClick={() => onNotReceived(item.id)}>{t('wishlist.action_not_received')}</MenuItem>
          )}
          {item.status === 'wanted' && (
            <MenuItem icon={<ArrowDown24Regular />} onClick={() => onDrop(item.id)}>{t('wishlist.action_drop')}</MenuItem>
          )}
          <MenuItem icon={<Delete24Regular />} onClick={() => onDelete(item.id)}>{t('wishlist.action_delete')}</MenuItem>
          <MenuItem icon={<Open24Regular />} onClick={() => window.open(cardmarketUrl, '_blank')}>{t('wishlist.action_cardmarket')}</MenuItem>
        </MenuList>
      </MenuPopover>
    </Menu>
  );

  if (isMobile) {
    return (
      <div className={styles.mobileRow}>
        {item.image_uri ? (
          <img src={item.image_uri} alt={item.card_name} className={styles.mobileImg} loading="lazy" />
        ) : (
          <div className={styles.mobileImg} />
        )}
        <div className={styles.mobileInfo}>
          <div className={styles.name}>
            <PriceTrendHover cardName={item.card_name} cardId={item.card_id}>{item.card_name}</PriceTrendHover>
            {item.is_foil && <Badge appearance="outline" size="small" style={{ marginLeft: 4 }}>◆</Badge>}
            {item.set_code && <Caption1 style={{ marginLeft: 6 }}>{item.set_code.toUpperCase()}</Caption1>}
          </div>
          <div>{'★'.repeat(item.priority)}{'☆'.repeat(5 - item.priority)} × {item.quantity}</div>
          <PriceDisplay item={item} />
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <StatusBadge item={item} />
            {item.deck_name && <Caption1>{item.deck_name}</Caption1>}
          </div>
          {item.tags.length > 0 && (
            <div className={styles.tags}>
              {item.tags.map(tag => <Badge key={tag} appearance="outline" size="small">{tag}</Badge>)}
            </div>
          )}
        </div>
        {actionsMenu}
      </div>
    );
  }

  return (
    <div className={styles.row}>
      {item.image_uri ? (
        <img src={item.image_uri} alt={item.card_name} className={styles.img} loading="lazy" />
      ) : (
        <div className={styles.img} />
      )}
      <div>
        <PriceTrendHover cardName={item.card_name} cardId={item.card_id}>
          <span className={styles.name}>{item.card_name}</span>
        </PriceTrendHover>
        {item.is_foil && <Badge appearance="outline" size="small" style={{ marginLeft: 4 }}>◆ Foil</Badge>}
        {item.set_code && <Caption1 style={{ marginLeft: 6 }}>({item.set_code.toUpperCase()})</Caption1>}
        {item.tags.length > 0 && (
          <div className={styles.tags}>
            {item.tags.map(tag => <Badge key={tag} appearance="outline" size="small">{tag}</Badge>)}
          </div>
        )}
      </div>
      <Caption1>{item.quantity}</Caption1>
      <div>{'★'.repeat(item.priority)}{'☆'.repeat(5 - item.priority)}</div>
      <PriceDisplay item={item} />
      <StatusBadge item={item} />
      <Caption1>{item.deck_name || '—'}</Caption1>
      {actionsMenu}
    </div>
  );
}

