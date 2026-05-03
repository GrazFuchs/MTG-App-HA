import { useState } from 'react';
import {
  Button,
  Input,
  Textarea,
  Dropdown,
  Option,
  Field,
  MessageBar,
  MessageBarBody,
  Spinner,
  makeStyles,
  tokens,
} from '@fluentui/react-components';
import { Add24Regular } from '@fluentui/react-icons';
import { useQuery } from '@tanstack/react-query';
import { api, WishlistItem, DeckSummary } from '../../api';
import CardNameAutocomplete from './CardNameAutocomplete';
import SetSelector from './SetSelector';
import PrioritySelector from './PrioritySelector';
import OwnedWarning from './OwnedWarning';

const useStyles = makeStyles({
  form: {
    display: 'flex',
    flexDirection: 'column',
    gap: '12px',
    padding: '16px',
    border: `1px solid ${tokens.colorNeutralStroke1}`,
    borderRadius: tokens.borderRadiusMedium,
    marginTop: '12px',
  },
  grid: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: '12px',
    '@media (max-width: 600px)': { gridTemplateColumns: '1fr' },
  },
  actions: { display: 'flex', gap: '8px', alignItems: 'center' },
});

interface Props {
  onAdded: (item: WishlistItem) => void;
}

export default function WishlistAddForm({ onAdded }: Props) {
  const styles = useStyles();
  const [cardName, setCardName] = useState('');
  const [cardSelected, setCardSelected] = useState(false);
  const [setCode, setSetCode] = useState<string | null>(null);
  const [isFoil, setIsFoil] = useState(false);
  const [quantity, setQuantity] = useState(1);
  const [targetPrice, setTargetPrice] = useState('');
  const [priority, setPriority] = useState(3);
  const [deckId, setDeckId] = useState<number | null>(null);
  const [tags, setTags] = useState('');
  const [notes, setNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [warning, setWarning] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [ownedQty, setOwnedQty] = useState(0);

  const { data: decks = [] } = useQuery<DeckSummary[]>({
    queryKey: ['decks'],
    queryFn: () => api.getDecks(),
  });

  const resetForm = () => {
    setCardName('');
    setCardSelected(false);
    setSetCode(null);
    setIsFoil(false);
    setQuantity(1);
    setTargetPrice('');
    setPriority(3);
    setDeckId(null);
    setTags('');
    setNotes('');
    setWarning(null);
    setError(null);
    setOwnedQty(0);
  };

  const handleCardSelect = async (name: string) => {
    setCardSelected(true);
    setSetCode(null);
    setIsFoil(false);
    // Check owned quantity
    try {
      const col = await api.getCollection(new URLSearchParams({ search: name, page_size: '100' }));
      const total = col.items
        .filter(e => e.card.name.toLowerCase() === name.toLowerCase())
        .reduce((sum, e) => sum + e.quantity + e.foil_quantity, 0);
      setOwnedQty(total);
    } catch {
      setOwnedQty(0);
    }
  };

  const handleSubmit = async () => {
    if (!cardName.trim()) return;
    setSubmitting(true);
    setError(null);
    setWarning(null);
    try {
      const parsedPrice = targetPrice ? parseFloat(targetPrice) : 0;
      if (parsedPrice < 0) {
        setError('Target price cannot be negative');
        setSubmitting(false);
        return;
      }
      const result = await api.addToWishlist({
        card_name: cardName.trim(),
        set_code: setCode || undefined,
        is_foil: isFoil,
        quantity,
        target_price_eur: parsedPrice,
        priority,
        deck_id: deckId || undefined,
        tags: tags.trim(),
        notes: notes.trim(),
      });
      resetForm();
      if (result.warning) {
        setWarning(result.warning);
      }
      if (result.item) {
        onAdded(result.item);
      }
    } catch (e: any) {
      if (e.message?.includes('409')) {
        setError('This card+set+foil combination is already on your wishlist');
      } else {
        setError(e.message || 'Failed to add');
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className={styles.form}>
      <Field label="Card">
        <CardNameAutocomplete
          value={cardName}
          onChange={(v) => { setCardName(v); if (cardSelected) setCardSelected(false); }}
          onSelect={handleCardSelect}
        />
      </Field>

      {cardSelected && (
        <>
          <SetSelector
            cardName={cardName}
            selectedSetCode={setCode}
            isFoil={isFoil}
            onSelectionChange={(sc, foil) => { setSetCode(sc); setIsFoil(foil); }}
          />

          <div className={styles.grid}>
            <Field label="Quantity">
              <Input
                type="number"
                min={1}
                max={99}
                value={String(quantity)}
                onChange={(_, d) => setQuantity(Math.max(1, Math.min(99, parseInt(d.value) || 1)))}
              />
            </Field>
            <Field label="Target Price (EUR)">
              <Input
                type="number"
                min={0}
                step={0.01}
                placeholder="0 = no alert"
                value={targetPrice}
                onChange={(_, d) => setTargetPrice(d.value)}
              />
            </Field>
            <Field label="Priority">
              <PrioritySelector value={priority} onChange={setPriority} />
            </Field>
            <Field label="Deck">
              <Dropdown
                placeholder="No deck"
                value={deckId ? decks.find(d => d.id === deckId)?.name || '' : ''}
                onOptionSelect={(_, data) => {
                  setDeckId(data.optionValue === '__none__' ? null : parseInt(data.optionValue as string));
                }}
              >
                <Option value="__none__">No deck</Option>
                {decks.map(d => (
                  <Option key={d.id} value={String(d.id)}>{d.name}</Option>
                ))}
              </Dropdown>
            </Field>
          </div>

          <Field label="Tags" hint="Comma-separated, e.g. 'modern, foil-priority'">
            <Input
              value={tags}
              onChange={(_, d) => setTags(d.value)}
              placeholder="modern, priority-upgrade"
            />
          </Field>

          <Field label="Notes">
            <Textarea
              value={notes}
              onChange={(_, d) => setNotes(d.value)}
              placeholder="Optional notes..."
              maxLength={500}
              resize="vertical"
            />
          </Field>
        </>
      )}

      <OwnedWarning cardName={cardSelected ? cardName : null} ownedQuantity={ownedQty} />

      {warning && (
        <MessageBar intent="warning">
          <MessageBarBody>{warning}</MessageBarBody>
        </MessageBar>
      )}
      {error && (
        <MessageBar intent="error">
          <MessageBarBody>{error}</MessageBarBody>
        </MessageBar>
      )}

      <div className={styles.actions}>
        <Button
          icon={submitting ? <Spinner size="tiny" /> : <Add24Regular />}
          appearance="primary"
          onClick={handleSubmit}
          disabled={!cardName.trim() || submitting}
        >
          {submitting ? 'Adding...' : 'Add to Wishlist'}
        </Button>
      </div>
    </div>
  );
}
