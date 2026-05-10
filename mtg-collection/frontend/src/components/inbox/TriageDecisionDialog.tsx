import { useState } from 'react';
import { makeStyles } from '@griffel/react';
import { Button, Input, Select } from '@fluentui/react-components';
import { sothera } from '../../theme/sothera';
import { useAccent } from '../../main';
import { t } from '../../i18n';

const useStyles = makeStyles({
  overlay: {
    position: 'fixed',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: 'rgba(0,0,0,0.6)',
    zIndex: 1000,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  },
  dialog: {
    width: '420px',
    maxWidth: '90vw',
    padding: '24px',
    backgroundColor: sothera.glassBg,
    border: `1px solid ${sothera.glassBorder}`,
    borderRadius: '4px',
  },
  title: {
    fontFamily: sothera.fontDisplay,
    fontSize: '16px',
    fontWeight: 600,
    color: sothera.fg,
    marginBottom: '16px',
  },
  field: {
    marginBottom: '12px',
  },
  label: {
    fontFamily: sothera.fontMono,
    fontSize: '10px',
    letterSpacing: '1.5px',
    textTransform: 'uppercase',
    color: sothera.fgFaint,
    marginBottom: '4px',
  },
  actions: {
    display: 'flex',
    gap: '8px',
    justifyContent: 'flex-end',
    marginTop: '16px',
  },
});

interface TriageDecisionDialogProps {
  open: boolean;
  onClose: () => void;
  onConfirm: (data: {
    listing_price_eur: number;
    listing_condition: string;
    listing_language: string;
    listing_quantity: number;
    sell_collection_id?: number | null;
  }) => void;
  mode: 'sold_new' | 'swap';
  cardName: string;
  estimatedPrice: number;
  suggestedSellId: number | null;
  existingPrintings: Array<{
    collection_id: number;
    set_code: string;
    set_name: string;
    is_foil: boolean;
    price_eur: string;
  }>;
}

export default function TriageDecisionDialog({
  open,
  onClose,
  onConfirm,
  mode,
  cardName,
  estimatedPrice,
  suggestedSellId,
  existingPrintings,
}: TriageDecisionDialogProps) {
  const styles = useStyles();
  const { accent } = useAccent();
  const [price, setPrice] = useState(String(estimatedPrice || 0));
  const [condition, setCondition] = useState('NM');
  const [language, setLanguage] = useState('English');
  const [quantity, setQuantity] = useState(1);
  const [sellId, setSellId] = useState<number | null>(suggestedSellId);

  if (!open) return null;

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.dialog} onClick={(e: React.MouseEvent) => e.stopPropagation()}>
        <div className={styles.title}>
          {mode === 'swap' ? `Swap — sell old copy of ${cardName}` : `Sell new copy — ${cardName}`}
        </div>

        <div className={styles.field}>
          <div className={styles.label}>Price (EUR)</div>
          <Input
            type="number"
            value={price}
            onChange={(_, d) => setPrice(d.value)}
            min={0}
            step={0.01}
          />
        </div>

        <div className={styles.field}>
          <div className={styles.label}>Condition</div>
          <Select value={condition} onChange={(_, d) => setCondition(d.value)}>
            <option value="MT">MT</option>
            <option value="NM">NM</option>
            <option value="EX">EX</option>
            <option value="GD">GD</option>
            <option value="LP">LP</option>
            <option value="PL">PL</option>
          </Select>
        </div>

        <div className={styles.field}>
          <div className={styles.label}>Language</div>
          <Select value={language} onChange={(_, d) => setLanguage(d.value)}>
            <option value="English">English</option>
            <option value="German">German</option>
            <option value="French">French</option>
            <option value="Italian">Italian</option>
            <option value="Spanish">Spanish</option>
            <option value="Japanese">Japanese</option>
          </Select>
        </div>

        <div className={styles.field}>
          <div className={styles.label}>Quantity</div>
          <Input
            type="number"
            value={String(quantity)}
            onChange={(_, d) => setQuantity(Math.max(1, parseInt(d.value) || 1))}
            min={1}
          />
        </div>

        {mode === 'swap' && existingPrintings.length > 0 && (
          <div className={styles.field}>
            <div className={styles.label}>Copy to sell</div>
            <Select
              value={String(sellId || '')}
              onChange={(_, d) => setSellId(d.value ? parseInt(d.value) : null)}
            >
              {existingPrintings.map(p => (
                <option key={p.collection_id} value={String(p.collection_id)}>
                  {p.set_name || p.set_code} {p.is_foil ? '(Foil)' : ''} — €{p.price_eur}
                </option>
              ))}
            </Select>
          </div>
        )}

        <div className={styles.actions}>
          <Button appearance="subtle" onClick={onClose}>{t('common.cancel')}</Button>
          <Button
            appearance="primary"
            onClick={() => onConfirm({
              listing_price_eur: parseFloat(price) || 0,
              listing_condition: condition,
              listing_language: language,
              listing_quantity: quantity,
              sell_collection_id: mode === 'swap' ? sellId : undefined,
            })}
            style={{ backgroundColor: accent.oklch }}
          >
            Create Listing
          </Button>
        </div>
      </div>
    </div>
  );
}
