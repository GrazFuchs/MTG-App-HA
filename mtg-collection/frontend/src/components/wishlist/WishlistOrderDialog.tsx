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
  Field,
  Spinner,
  MessageBar,
  MessageBarBody,
} from '@fluentui/react-components';
import { api, WishlistItem } from '../../api';

interface Props {
  item: WishlistItem;
  onClose: () => void;
  onOrdered: () => void;
}

export default function WishlistOrderDialog({ item, onClose, onOrdered }: Props) {
  const [price, setPrice] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleConfirm = async () => {
    setSaving(true);
    setError(null);
    try {
      const expected = price !== '' ? parseFloat(price) : undefined;
      await api.markWishlistOrdered(item.id, expected);
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
            <Field label="Expected Price (EUR)" hint="Price you paid / agreed upon (optional)">
              <Input
                type="number"
                min={0}
                step={0.01}
                placeholder="e.g. 12.50"
                value={price}
                onChange={(_, d) => setPrice(d.value)}
                autoFocus
              />
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
              {saving ? <Spinner size="extra-tiny" /> : '📦 Mark as Ordered'}
            </Button>
          </DialogActions>
        </DialogBody>
      </DialogSurface>
    </Dialog>
  );
}
