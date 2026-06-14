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
  status: 'wanted' | 'acquired' | 'dropped' | 'not_received' | 'all';
  priority: number | null;
  deckId: number | null;
  tag: string | null;
  color: string | null;
  ordered: 'all' | 'ordered' | 'unordered';
  isDealOnly: boolean;
  sort: 'priority' | 'added_at' | 'target_price' | 'current_price' | 'delta_eur';
}

export const DEFAULT_FILTERS: WishlistFilters = {
  status: 'wanted',
  priority: null,
  deckId: null,
  tag: null,
  color: null,
  ordered: 'all',
  isDealOnly: false,
  sort: 'priority',
};

export function filtersToParams(f: WishlistFilters): URLSearchParams {
  const p = new URLSearchParams();
  if (f.status !== 'all') p.set('status', f.status);
  if (f.priority != null) p.set('priority', String(f.priority));
  if (f.deckId != null) p.set('deck_id', String(f.deckId));
  if (f.tag) p.set('tag', f.tag);
  if (f.color) p.set('color', f.color);
  if (f.ordered === 'ordered') p.set('is_ordered', 'true');
  else if (f.ordered === 'unordered') p.set('is_ordered', 'false');
  if (f.isDealOnly) p.set('deals_only', 'true');
  p.set('sort', f.sort);
  return p;
}

export function filtersFromSearchParams(sp: URLSearchParams): WishlistFilters {
  const isOrdered = sp.get('is_ordered');
  return {
    status: (sp.get('status') as WishlistFilters['status']) || 'wanted',
    priority: sp.has('priority') ? parseInt(sp.get('priority')!) : null,
    deckId: sp.has('deck_id') ? parseInt(sp.get('deck_id')!) : null,
    tag: sp.get('tag') || null,
    color: sp.get('color') || null,
    ordered: isOrdered === 'true' ? 'ordered' : isOrdered === 'false' ? 'unordered' : 'all',
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
  { value: 'not_received', label: 'wishlist.status_not_received' },
];

const SORT_OPTIONS: { value: WishlistFilters['sort']; label: string }[] = [
  { value: 'priority', label: 'wishlist.sort_priority' },
  { value: 'added_at', label: 'wishlist.sort_added' },
  { value: 'target_price', label: 'wishlist.sort_target' },
  { value: 'current_price', label: 'wishlist.sort_current' },
  { value: 'delta_eur', label: 'wishlist.sort_delta' },
];

const ORDERED_OPTIONS: { value: WishlistFilters['ordered']; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'ordered', label: '📦 Ordered' },
  { value: 'unordered', label: 'Not ordered' },
];

const COLOR_OPTIONS: { value: string; label: string }[] = [
  { value: '', label: 'All Colors' },
  { value: 'W', label: '⚪ White' },
  { value: 'U', label: '🔵 Blue' },
  { value: 'B', label: '⚫ Black' },
  { value: 'R', label: '🔴 Red' },
  { value: 'G', label: '🟢 Green' },
  { value: 'M', label: '🌈 Multi' },
  { value: 'C', label: '◆ Colorless' },
  { value: 'L', label: '🟤 Lands' },
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

      <Dropdown
        placeholder="Color"
        value={COLOR_OPTIONS.find(o => o.value === (filters.color || ''))?.label || 'All Colors'}
        onOptionSelect={(_, d) => update({ color: d.optionValue || null })}
        style={{ minWidth: '120px' }}
      >
        {COLOR_OPTIONS.map(o => (
          <Option key={o.value} value={o.value}>{o.label}</Option>
        ))}
      </Dropdown>

      {filters.status === 'wanted' && (
        <Dropdown
          placeholder="Ordered"
          value={ORDERED_OPTIONS.find(o => o.value === filters.ordered)?.label || 'All'}
          onOptionSelect={(_, d) => update({ ordered: (d.optionValue as WishlistFilters['ordered']) || 'all' })}
          style={{ minWidth: '130px' }}
        >
          {ORDERED_OPTIONS.map(o => (
            <Option key={o.value} value={o.value}>{o.label}</Option>
          ))}
        </Dropdown>
      )}

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
