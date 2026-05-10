import { useState } from 'react';
import {
  Dialog,
  DialogSurface,
  DialogBody,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Input,
  Dropdown,
  Option,
  Field,
  Spinner,
  MessageBar,
  MessageBarBody,
} from '@fluentui/react-components';
import { api, WishlistItem, WishlistSource } from '../../api';

const SOURCE_OPTIONS: { value: WishlistSource; label: string }[] = [
  { value: 'cardmarket', label: 'Cardmarket' },
  { value: 'whatnot', label: 'Whatnot' },
  { value: 'booster', label: 'Booster' },
  { value: 'trade', label: 'Trade' },
  { value: 'gift', label: 'Gift' },
  { value: 'shop', label: 'Shop' },
  { value: 'secret_lair', label: 'Secret Lair' },
  { value: 'other', label: 'Other' },
];

interface Props {
  item: WishlistItem;
  onClose: () => void;
  onAcquired: () => void;
}

export default function WishlistAcquireDialog({ item, onClose, onAcquired }: Props) {
  // Pre-fill with expected_price_eur if set (from prior order)
  const [price, setPrice] = useState(
    item.expected_price_eur != null ? String(item.expected_price_eur) : ''
  );
  const [source, setSource] = useState<WishlistSource | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleConfirm = async () => {
    setSaving(true);
    setError(null);
    try {
      const paid = price !== '' ? parseFloat(price) : undefined;
      await api.acquireWishlistItem(item.id, paid, source ?? undefined);
      onAcquired();
      onClose();
    } catch (e: any) {
      setError(e.message || 'Failed to mark as acquired');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open onOpenChange={(_, d) => { if (!d.open) onClose(); }}>
      <DialogSurface>
        <DialogBody>
          <DialogTitle>Mark as Received: {item.card_name}</DialogTitle>
          <DialogContent style={{ display: 'flex', flexDirection: 'column', gap: '12px', paddingTop: '12px' }}>
            {item.is_ordered && item.expected_price_eur != null && (
              <MessageBar intent="info">
                <MessageBarBody>
                  Expected price: €{item.expected_price_eur.toFixed(2)} — pre-filled below
                </MessageBarBody>
              </MessageBar>
            )}

            <Field label="Paid Price (EUR)" hint="Leave empty if unknown">
              <Input
                type="number"
                min={0}
                step={0.01}
                placeholder="e.g. 12.50"
                value={price}
                onChange={(_, d) => setPrice(d.value)}
              />
            </Field>

            <Field label="Source">
              <Dropdown
                placeholder="Select source (optional)"
                value={source ? SOURCE_OPTIONS.find(o => o.value === source)?.label : ''}
                onOptionSelect={(_, d) => setSource(d.optionValue as WishlistSource)}
              >
                {SOURCE_OPTIONS.map(o => (
                  <Option key={o.value} value={o.value}>{o.label}</Option>
                ))}
              </Dropdown>
            </Field>

            {error && (
              <MessageBar intent="error">
                <MessageBarBody>{error}</MessageBarBody>
              </MessageBar>
            )}
          </DialogContent>
          <DialogActions>
            <Button appearance="secondary" onClick={onClose} disabled={saving}>Cancel</Button>
            <Button appearance="primary" onClick={handleConfirm} disabled={saving}>
              {saving ? <Spinner size="extra-tiny" /> : 'Mark as Received'}
            </Button>
          </DialogActions>
        </DialogBody>
      </DialogSurface>
    </Dialog>
  );
}
