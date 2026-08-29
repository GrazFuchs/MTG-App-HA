import { useEffect, useState } from 'react';
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
  Checkbox,
  MessageBar,
  MessageBarBody,
} from '@fluentui/react-components';
import { t } from '../../i18n';
import { api, WishlistItem, DeckSummary, CardPrinting } from '../../api';
import PrioritySelector from './PrioritySelector';


/** Share of the current market price the suggestion button fills in. */
const SUGGESTED_SHARE = 0.85;
interface Props {
  item: WishlistItem;
  decks: DeckSummary[];
  onClose: () => void;
  onSaved: (updated: WishlistItem) => void;
}

export default function WishlistEditDialog({ item, decks, onClose, onSaved }: Props) {
  const [targetPrice, setTargetPrice] = useState(String(item.target_price_eur || ''));

  // A round fraction of the current market, deliberately not a computed
  // "fair price": the wishlist is about what you are willing to pay, and any
  // cleverer number would look like advice the data cannot support.
  const suggestedTarget = item.current_price_eur && item.current_price_eur > 0
    ? Math.round(item.current_price_eur * SUGGESTED_SHARE * 100) / 100
    : null;
  const targetHint = item.current_price_eur
    ? t('wishlist.market_short', { price: item.current_price_eur.toFixed(2) })
    : undefined;
  const [priority, setPriority] = useState(item.priority);
  const [status, setStatus] = useState<WishlistItem['status']>(item.status);
  const [deckId, setDeckId] = useState<number | null>(item.deck_id);
  const [tags, setTags] = useState(item.tags.join(', '));
  const [notes, setNotes] = useState(item.notes);
  const [printings, setPrintings] = useState<CardPrinting[]>([]);
  const [selectedSetCode, setSelectedSetCode] = useState<string | null>(item.set_code || null);
  const [isFoil, setIsFoil] = useState(item.is_foil);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (item.card_name) {
      api.getCardPrintings(item.card_name).then(setPrintings).catch(() => {});
    }
  }, [item.card_name]);

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
        set_code: selectedSetCode || undefined,
        is_foil: isFoil,
      });
      // Status change via separate endpoints if needed
      if (status !== item.status) {
        if (status === 'acquired') {
          await api.acquireWishlistItem(item.id);
        } else if (status === 'dropped') {
          await api.updateWishlistItem(item.id, { status: 'dropped' } as any);
        } else if (status === 'wanted') {
          // PATCH re-opens the item and clears terminal-state flags.
          // (POST /restore is for soft-deleted items only and always
          // answered 400 here — this path was a dead end.)
          await api.updateWishlistItem(item.id, { status: 'wanted' } as any);
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
            <Field label={t('wishlist.target_price')} hint={targetHint}>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <Input
                  type="number"
                  min={0}
                  step={0.01}
                  value={targetPrice}
                  onChange={(_, d) => setTargetPrice(d.value)}
                  style={{ flex: 1 }}
                />
                {/* A target of 0 means "never alert me", and 25 of these entries
                    had one because setting a sensible number by hand means
                    looking up the price first. 85 % of the current market is a
                    starting point, not a recommendation — it is filled into the
                    field, not saved, so it can be argued with. */}
                {suggestedTarget !== null && (
                  <Button
                    appearance="subtle"
                    size="small"
                    onClick={() => setTargetPrice(suggestedTarget.toFixed(2))}
                    title={t('wishlist.suggest_target_hint', { pct: SUGGESTED_SHARE * 100 })}
                  >
                    {t('wishlist.suggest_target', { price: suggestedTarget.toFixed(2) })}
                  </Button>
                )}
              </div>
            </Field>

            <Field label={t('wishlist.priority_label')}>
              <PrioritySelector value={priority} onChange={setPriority} />
            </Field>

            {printings.length > 0 && (
              <Field label={t('common.set_version')}>
                <Dropdown
                  placeholder={t('common.any_printing')}
                  value={printings.find(p => p.set_code === selectedSetCode)
                    ? `${printings.find(p => p.set_code === selectedSetCode)!.set_name} (${selectedSetCode?.toUpperCase()})`
                    : selectedSetCode?.toUpperCase() || t('common.any_printing')}
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

            <Checkbox label={t('cards.foil')} checked={isFoil} onChange={(_, d) => setIsFoil(!!d.checked)} />

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
                placeholder={t('wishlist.tags_placeholder')}
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
