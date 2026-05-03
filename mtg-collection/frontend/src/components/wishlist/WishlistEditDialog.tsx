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
  Textarea,
  Dropdown,
  Option,
  Field,
  Spinner,
  MessageBar,
  MessageBarBody,
} from '@fluentui/react-components';
import { t } from '../../i18n';
import { api, WishlistItem, DeckSummary } from '../../api';
import PrioritySelector from './PrioritySelector';

interface Props {
  item: WishlistItem;
  decks: DeckSummary[];
  onClose: () => void;
  onSaved: (updated: WishlistItem) => void;
}

export default function WishlistEditDialog({ item, decks, onClose, onSaved }: Props) {
  const [targetPrice, setTargetPrice] = useState(String(item.target_price_eur || ''));
  const [priority, setPriority] = useState(item.priority);
  const [status, setStatus] = useState<WishlistItem['status']>(item.status);
  const [deckId, setDeckId] = useState<number | null>(item.deck_id);
  const [tags, setTags] = useState(item.tags.join(', '));
  const [notes, setNotes] = useState(item.notes);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      const updated = await api.updateWishlistItem(item.id, {
        target_price_eur: targetPrice ? parseFloat(targetPrice) : 0,
        priority,
        deck_id: deckId || undefined,
        tags: tags.trim(),
        notes: notes.trim(),
      });
      // Status change via separate endpoints if needed
      if (status !== item.status) {
        if (status === 'acquired') {
          await api.acquireWishlistItem(item.id);
        } else if (status === 'dropped') {
          await api.updateWishlistItem(item.id, { status: 'dropped' } as any);
        } else if (status === 'wanted') {
          await api.restoreWishlistItem(item.id);
        }
      }
      onSaved(updated);
      onClose();
    } catch (e: any) {
      setError(e.message || 'Failed to save');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open onOpenChange={(_, d) => { if (!d.open) onClose(); }}>
      <DialogSurface>
        <DialogBody>
          <DialogTitle>{t('wishlist.edit_title')}: {item.card_name}</DialogTitle>
          <DialogContent style={{ display: 'flex', flexDirection: 'column', gap: '12px', paddingTop: '12px' }}>
            <Field label={t('wishlist.target_price')}>
              <Input
                type="number"
                min={0}
                step={0.01}
                value={targetPrice}
                onChange={(_, d) => setTargetPrice(d.value)}
              />
            </Field>

            <Field label={t('wishlist.priority_label')}>
              <PrioritySelector value={priority} onChange={setPriority} />
            </Field>

            <Field label={t('wishlist.status_label')}>
              <Dropdown
                value={t(`wishlist.status_${status}`)}
                onOptionSelect={(_, d) => setStatus(d.optionValue as WishlistItem['status'])}
              >
                <Option value="wanted">{t('wishlist.status_wanted')}</Option>
                <Option value="acquired">{t('wishlist.status_acquired')}</Option>
                <Option value="dropped">{t('wishlist.status_dropped')}</Option>
              </Dropdown>
            </Field>

            <Field label={t('wishlist.deck_label')}>
              <Dropdown
                placeholder={t('wishlist.no_deck')}
                value={deckId ? decks.find(d => d.id === deckId)?.name || '' : ''}
                onOptionSelect={(_, d) => setDeckId(d.optionValue === '__none__' ? null : parseInt(d.optionValue as string))}
              >
                <Option value="__none__">{t('wishlist.no_deck')}</Option>
                {decks.map(d => (
                  <Option key={d.id} value={String(d.id)}>{d.name}</Option>
                ))}
              </Dropdown>
            </Field>

            <Field label={t('wishlist.tags_label')}>
              <Input
                value={tags}
                onChange={(_, d) => setTags(d.value)}
                placeholder="modern, priority-upgrade"
              />
            </Field>

            <Field label={t('wishlist.notes_label')}>
              <Textarea
                value={notes}
                onChange={(_, d) => setNotes(d.value)}
                maxLength={500}
                resize="vertical"
              />
            </Field>

            {error && (
              <MessageBar intent="error">
                <MessageBarBody>{error}</MessageBarBody>
              </MessageBar>
            )}
          </DialogContent>
          <DialogActions>
            <Button appearance="secondary" onClick={onClose}>{t('common.cancel')}</Button>
            <Button
              appearance="primary"
              onClick={handleSave}
              disabled={saving}
              icon={saving ? <Spinner size="tiny" /> : undefined}
            >
              {saving ? t('common.saving') : t('common.save')}
            </Button>
          </DialogActions>
        </DialogBody>
      </DialogSurface>
    </Dialog>
  );
}
