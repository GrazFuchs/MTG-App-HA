import { useState, useEffect } from 'react';
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
  Checkbox,
  MessageBar,
  MessageBarBody,
} from '@fluentui/react-components';
import { api, WishlistItem, WishlistSource, CardPrinting } from '../../api';

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
  const [printings, setPrintings] = useState<CardPrinting[]>([]);
  const [selectedSetCode, setSelectedSetCode] = useState<string | null>(item.set_code || null);
  const [isFoil, setIsFoil] = useState(item.is_foil);

  useEffect(() => {
    if (item.card_name) {
      api.getCardPrintings(item.card_name).then(setPrintings).catch(() => {});
    }
  }, [item.card_name]);

  const handleConfirm = async () => {
    setSaving(true);
    setError(null);
    try {
      const paid = price !== '' ? parseFloat(price) : undefined;
      await api.acquireWishlistItem(item.id, paid, source ?? undefined, selectedSetCode || undefined, isFoil);
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

            {printings.length > 0 && (
              <Field label="Set / Version">
                <Dropdown
                  placeholder="Select printing"
                  value={printings.find(p => p.set_code === selectedSetCode)
                    ? `${printings.find(p => p.set_code === selectedSetCode)!.set_name} (${selectedSetCode?.toUpperCase()})`
                    : selectedSetCode?.toUpperCase() || 'Any'}
                  onOptionSelect={(_, d) => setSelectedSetCode(d.optionValue === '__any__' ? null : d.optionValue as string)}
                >
                  <Option value="__any__">Any printing</Option>
                  {printings.map(p => (
                    <Option key={p.set_code} value={p.set_code} text={`${p.set_name} (${p.set_code.toUpperCase()})`}>
                      {p.set_name} ({p.set_code.toUpperCase()})
                    </Option>
                  ))}
                </Dropdown>
              </Field>
            )}

            <Checkbox
              label="Foil"
              checked={isFoil}
              onChange={(_, d) => setIsFoil(!!d.checked)}
            />

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
