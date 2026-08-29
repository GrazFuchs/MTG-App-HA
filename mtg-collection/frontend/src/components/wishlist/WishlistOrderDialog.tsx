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
  Field,
  Spinner,
  MessageBar,
  MessageBarBody,
  Dropdown,
  Option,
  Checkbox,
} from '@fluentui/react-components';
import { api, WishlistItem, CardPrinting } from '../../api';

import { t } from '../../i18n';
interface Props {
  item: WishlistItem;
  onClose: () => void;
  onOrdered: () => void;
}

export default function WishlistOrderDialog({ item, onClose, onOrdered }: Props) {
  const [price, setPrice] = useState('');
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
      const expected = price !== '' ? parseFloat(price) : undefined;
      await api.markWishlistOrdered(item.id, expected, selectedSetCode || undefined, isFoil);
      onOrdered();
      onClose();
    } catch (e: any) {
      setError(e.message || 'Failed to mark as ordered');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open onOpenChange={(_, d) => { if (!d.open) onClose(); }}>
      <DialogSurface>
        <DialogBody>
          <DialogTitle>Mark as Ordered: {item.card_name}</DialogTitle>
          <DialogContent style={{ display: 'flex', flexDirection: 'column', gap: '12px', paddingTop: '12px' }}>
            <Field label={t('wishlist.expected_price')} hint="Price you paid / agreed upon (optional)">
              <Input
                type="number"
                min={0}
                step={0.01}
                placeholder={t('common.example_price')}
                value={price}
                onChange={(_, d) => setPrice(d.value)}
                autoFocus
              />
            </Field>

            {printings.length > 0 && (
              <Field label={t('common.set_version')}>
                <Dropdown
                  placeholder={t('common.select_printing')}
                  value={printings.find(p => p.set_code === selectedSetCode)
                    ? `${printings.find(p => p.set_code === selectedSetCode)!.set_name} (${selectedSetCode?.toUpperCase()})`
                    : selectedSetCode?.toUpperCase() || t('wishlist.any_short')}
                  onOptionSelect={(_, d) => setSelectedSetCode(d.optionValue === '__any__' ? null : d.optionValue as string)}
                >
                  <Option value="__any__">{t('common.any_printing')}</Option>
                  {printings.map(p => (
                    <Option key={p.set_code} value={p.set_code} text={`${p.set_name} (${p.set_code.toUpperCase()})`}>
                      {p.set_name} ({p.set_code.toUpperCase()})
                    </Option>
                  ))}
                </Dropdown>
              </Field>
            )}

            <Checkbox
              label={t('cards.foil')}
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
            <Button appearance="secondary" onClick={onClose} disabled={saving}>{t('common.cancel')}</Button>
            <Button appearance="primary" onClick={handleConfirm} disabled={saving}>
              {saving ? <Spinner size="extra-tiny" /> : '📦 Mark as Ordered'}
            </Button>
          </DialogActions>
        </DialogBody>
      </DialogSurface>
    </Dialog>
  );
}
