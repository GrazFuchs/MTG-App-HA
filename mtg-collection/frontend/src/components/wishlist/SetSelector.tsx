import { useState, useEffect } from 'react';
import {
  Dropdown,
  Option,
  Checkbox,
  Spinner,
  Caption1,
  makeStyles,
  tokens,
} from '@fluentui/react-components';
import { api, CardPrinting } from '../../api';

const useStyles = makeStyles({
  wrapper: { display: 'flex', flexDirection: 'column', gap: '8px' },
  row: { display: 'flex', gap: '12px', alignItems: 'center' },
  price: { color: tokens.colorNeutralForeground3, fontSize: '12px' },
});

interface Props {
  cardName: string;
  selectedSetCode: string | null;
  isFoil: boolean;
  onSelectionChange: (setCode: string | null, isFoil: boolean) => void;
}

export default function SetSelector({ cardName, selectedSetCode, isFoil, onSelectionChange }: Props) {
  const styles = useStyles();
  const [printings, setPrintings] = useState<CardPrinting[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!cardName) {
      setPrintings([]);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    api.getCardPrintings(cardName)
      .then(data => {
        if (!cancelled) setPrintings(data);
      })
      .catch(e => {
        if (!cancelled) {
          setError(e.message);
          setPrintings([]);
        }
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [cardName]);

  if (!cardName) return null;
  if (loading) return <Spinner size="tiny" label="Loading printings..." />;
  if (error) return <Caption1>Could not load printings. Proceed without set.</Caption1>;

  const selectedPrinting = printings.find(p => p.set_code === selectedSetCode);
  const foilAvailable = selectedPrinting ? selectedPrinting.is_foil_available : printings.some(p => p.is_foil_available);

  const formatPrice = (p: CardPrinting) => {
    const parts: string[] = [];
    if (p.price_eur != null) parts.push(`€${p.price_eur.toFixed(2)}`);
    if (p.price_eur_foil != null) parts.push(`Foil €${p.price_eur_foil.toFixed(2)}`);
    return parts.length > 0 ? parts.join(' / ') : 'No price';
  };

  return (
    <div className={styles.wrapper}>
      <div className={styles.row}>
        <Dropdown
          placeholder="Any printing"
          value={selectedSetCode ? `${printings.find(p => p.set_code === selectedSetCode)?.set_name || selectedSetCode} (${selectedSetCode.toUpperCase()})` : 'Any printing'}
          onOptionSelect={(_, data) => {
            const code = data.optionValue === '__any__' ? null : (data.optionValue || null);
            onSelectionChange(code, isFoil);
          }}
          style={{ minWidth: '240px' }}
        >
          <Option value="__any__">Any printing</Option>
          {printings.map(p => (
            <Option key={p.scryfall_id} value={p.set_code} text={`${p.set_name} (${p.set_code.toUpperCase()})`}>
              {p.set_name} ({p.set_code.toUpperCase()}) — <span className={styles.price}>{formatPrice(p)}</span>
            </Option>
          ))}
        </Dropdown>
        <Checkbox
          label="Foil"
          checked={isFoil}
          disabled={!foilAvailable}
          onChange={(_, data) => onSelectionChange(selectedSetCode, !!data.checked)}
        />
      </div>
    </div>
  );
}
