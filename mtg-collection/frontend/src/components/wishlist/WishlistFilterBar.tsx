import {
  makeStyles,
  Dropdown,
  Option,
  Input,
  Checkbox,
  Button,
} from '@fluentui/react-components';
import { Dismiss24Regular } from '@fluentui/react-icons';
import { t } from '../../i18n';
import type { DeckSummary } from '../../api';

const useStyles = makeStyles({
  bar: {
    display: 'flex',
    gap: '10px',
    flexWrap: 'wrap',
    alignItems: 'center',
    marginBottom: '12px',
  },
});

export interface WishlistFilters {
  status: 'wanted' | 'acquired' | 'dropped' | 'all';
  priority: number | null;
  deckId: number | null;
  tag: string | null;
  isDealOnly: boolean;
  sort: 'priority' | 'added_at' | 'target_price' | 'current_price' | 'delta_eur';
}

export const DEFAULT_FILTERS: WishlistFilters = {
  status: 'wanted',
  priority: null,
  deckId: null,
  tag: null,
  isDealOnly: false,
  sort: 'priority',
};

export function filtersToParams(f: WishlistFilters): URLSearchParams {
  const p = new URLSearchParams();
  if (f.status !== 'all') p.set('status', f.status);
  if (f.priority != null) p.set('priority', String(f.priority));
  if (f.deckId != null) p.set('deck_id', String(f.deckId));
  if (f.tag) p.set('tag', f.tag);
  if (f.isDealOnly) p.set('deals_only', 'true');
  p.set('sort', f.sort);
  return p;
}

export function filtersFromSearchParams(sp: URLSearchParams): WishlistFilters {
  return {
    status: (sp.get('status') as WishlistFilters['status']) || 'wanted',
    priority: sp.has('priority') ? parseInt(sp.get('priority')!) : null,
    deckId: sp.has('deck_id') ? parseInt(sp.get('deck_id')!) : null,
    tag: sp.get('tag') || null,
    isDealOnly: sp.get('deals_only') === 'true',
    sort: (sp.get('sort') as WishlistFilters['sort']) || 'priority',
  };
}

interface Props {
  filters: WishlistFilters;
  onChange: (next: WishlistFilters) => void;
  decks: DeckSummary[];
}

const STATUS_OPTIONS: { value: WishlistFilters['status']; label: string }[] = [
  { value: 'all', label: 'wishlist.filter_all' },
  { value: 'wanted', label: 'wishlist.filter_wanted' },
  { value: 'acquired', label: 'wishlist.filter_acquired' },
  { value: 'dropped', label: 'wishlist.filter_dropped' },
];

const SORT_OPTIONS: { value: WishlistFilters['sort']; label: string }[] = [
  { value: 'priority', label: 'wishlist.sort_priority' },
  { value: 'added_at', label: 'wishlist.sort_added' },
  { value: 'target_price', label: 'wishlist.sort_target' },
  { value: 'current_price', label: 'wishlist.sort_current' },
  { value: 'delta_eur', label: 'wishlist.sort_delta' },
];

export default function WishlistFilterBar({ filters, onChange, decks }: Props) {
  const styles = useStyles();

  const update = (patch: Partial<WishlistFilters>) => onChange({ ...filters, ...patch });

  return (
    <div className={styles.bar}>
      <Dropdown
        placeholder={t('wishlist.filter_status')}
        value={t(STATUS_OPTIONS.find(o => o.value === filters.status)!.label)}
        onOptionSelect={(_, d) => update({ status: d.optionValue as WishlistFilters['status'] })}
        style={{ minWidth: '120px' }}
      >
        {STATUS_OPTIONS.map(o => (
          <Option key={o.value} value={o.value}>{t(o.label)}</Option>
        ))}
      </Dropdown>

      <Dropdown
        placeholder={t('wishlist.filter_priority')}
        value={filters.priority != null ? `${'★'.repeat(filters.priority)}+` : t('wishlist.filter_priority')}
        onOptionSelect={(_, d) => update({ priority: d.optionValue === '__all__' ? null : parseInt(d.optionValue as string) })}
        style={{ minWidth: '110px' }}
      >
        <Option value="__all__">{t('wishlist.filter_all')}</Option>
        {[5, 4, 3, 2, 1].map(p => (
          <Option key={p} value={String(p)} text={`${'★'.repeat(p)}${'☆'.repeat(5 - p)}`}>{'★'.repeat(p)}{'☆'.repeat(5 - p)}</Option>
        ))}
      </Dropdown>

      <Dropdown
        placeholder={t('wishlist.filter_deck')}
        value={filters.deckId != null ? (decks.find(d => d.id === filters.deckId)?.name || '') : t('wishlist.filter_deck')}
        onOptionSelect={(_, d) => update({ deckId: d.optionValue === '__all__' ? null : parseInt(d.optionValue as string) })}
        style={{ minWidth: '140px' }}
      >
        <Option value="__all__">{t('wishlist.filter_all')}</Option>
        {decks.map(d => (
          <Option key={d.id} value={String(d.id)}>{d.name}</Option>
        ))}
      </Dropdown>

      <Input
        placeholder={t('wishlist.filter_tag')}
        value={filters.tag || ''}
        onChange={(_, d) => update({ tag: d.value || null })}
        style={{ width: '130px' }}
      />

      <Checkbox
        label={t('wishlist.deals_only')}
        checked={filters.isDealOnly}
        onChange={(_, d) => update({ isDealOnly: !!d.checked })}
      />

      <Dropdown
        value={t(SORT_OPTIONS.find(o => o.value === filters.sort)!.label)}
        onOptionSelect={(_, d) => update({ sort: d.optionValue as WishlistFilters['sort'] })}
        style={{ minWidth: '140px' }}
      >
        {SORT_OPTIONS.map(o => (
          <Option key={o.value} value={o.value}>{t(o.label)}</Option>
        ))}
      </Dropdown>

      <Button
        icon={<Dismiss24Regular />}
        appearance="subtle"
        onClick={() => onChange(DEFAULT_FILTERS)}
        title={t('wishlist.filter_reset')}
      />
    </div>
  );
}
