import { useState } from 'react';
import { makeStyles } from '@griffel/react';
import { Button } from '@fluentui/react-components';
import { AcquisitionEvent, TriageDecisionPayload } from '../../api';
import { CardHoverPreview } from '../CardHoverPreview';
import { sothera } from '../../theme/sothera';
import { useAccent } from '../../main';
import { Panel } from '../sothera';
import { t } from '../../i18n';
import SourcePicker from './SourcePicker';
import TriageDecisionDialog from './TriageDecisionDialog';

const useStyles = makeStyles({
  card: {
    padding: '16px',
    marginBottom: '12px',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: '12px',
  },
  cardName: {
    fontFamily: sothera.fontDisplay,
    fontSize: '16px',
    fontWeight: 600,
    color: sothera.fg,
  },
  badge: {
    fontFamily: sothera.fontMono,
    fontSize: '10px',
    letterSpacing: '1px',
    color: sothera.fgMuted,
    padding: '2px 8px',
    border: `1px solid ${sothera.glassBorder}`,
    borderRadius: '2px',
  },
  info: {
    fontFamily: sothera.fontMono,
    fontSize: '12px',
    color: sothera.fgMuted,
    lineHeight: '1.6',
    marginBottom: '12px',
  },
  printings: {
    marginBottom: '12px',
  },
  printingRow: {
    fontFamily: sothera.fontMono,
    fontSize: '11px',
    color: sothera.fgMuted,
    padding: '2px 0',
  },
  suggestion: {
    padding: '8px 12px',
    marginBottom: '12px',
    borderLeft: '3px solid',
    fontFamily: sothera.fontMono,
    fontSize: '11px',
    color: sothera.fgMuted,
    lineHeight: '1.5',
  },
  sourceSection: {
    marginBottom: '12px',
  },
  sourceLabel: {
    fontFamily: sothera.fontMono,
    fontSize: '10px',
    letterSpacing: '1.5px',
    textTransform: 'uppercase',
    color: sothera.fgFaint,
    marginBottom: '6px',
  },
  actions: {
    display: 'flex',
    gap: '8px',
    flexWrap: 'wrap',
    alignItems: 'center',
  },
  warning: {
    fontFamily: sothera.fontMono,
    fontSize: '10px',
    color: sothera.negative,
    marginLeft: '8px',
  },
});

interface AcquisitionCardProps {
  event: AcquisitionEvent;
  onDecide: (eventId: number, payload: TriageDecisionPayload) => Promise<void>;
  onSkip: (eventId: number) => void;
  defaultSource: string | null;
  onSourceChange: (source: string) => void;
}

export default function AcquisitionCard({
  event,
  onDecide,
  onSkip,
  defaultSource,
  onSourceChange,
}: AcquisitionCardProps) {
  const styles = useStyles();
  const { accent } = useAccent();
  const [source, setSource] = useState<string | null>(defaultSource);
  const [dialogMode, setDialogMode] = useState<'sold_new' | 'swap' | null>(null);
  const [busy, setBusy] = useState(false);

  const handleSourceChange = (s: string) => {
    setSource(s);
    onSourceChange(s);
  };

  const handleDecide = async (payload: TriageDecisionPayload) => {
    setBusy(true);
    try {
      await onDecide(event.id, payload);
    } finally {
      setBusy(false);
    }
  };

  const price = event.is_foil
    ? event.card.price_eur_foil || event.card.price_eur
    : event.card.price_eur || event.card.price_eur_foil;

  const suggestionColor =
    event.suggestion.action === 'swap' ? accent.oklch
    : event.suggestion.action === 'sold_new' ? sothera.negative
    : sothera.positive;

  return (
    <Panel className={styles.card}>
      <div className={styles.header}>
        <CardHoverPreview card={event.card}>
          <span className={styles.cardName}>{event.card.name}</span>
        </CardHoverPreview>
        <span className={styles.badge}>
          +{event.qty_delta} added {new Date(event.created_at).toLocaleDateString()}
        </span>
      </div>

      <div className={styles.info}>
        New: {event.card.set_name || event.card.set_code} ({event.card.set_code.toUpperCase()}),{' '}
        {event.is_foil ? 'foil' : 'non-foil'}, {event.condition}, {event.language}
        {price ? ` — €${price}` : ''}
      </div>

      {event.existing_printings.length > 0 && (
        <div className={styles.printings}>
          <div className={styles.sourceLabel}>You already own:</div>
          {event.existing_printings.map((p, i) => (
            <div key={i} className={styles.printingRow}>
              • {p.quantity + p.foil_quantity}× {p.set_name || p.set_code} ({p.is_foil ? 'foil' : 'non-foil'}) — €{p.price_eur}
            </div>
          ))}
          <div className={styles.printingRow}>
            In decks: {event.in_decks}
            {event.existing_printings.length > 0 && (
              <span>
                {' '}(surplus: {(event.existing_printings.reduce((s, p) => s + p.quantity + p.foil_quantity, 0) + event.qty_delta) - event.in_decks})
              </span>
            )}
          </div>
        </div>
      )}

      <div className={styles.suggestion} style={{ borderLeftColor: suggestionColor }}>
        💡{' '}
        {event.suggestion.action === 'swap' && t('inbox.suggestion.swap', { old_set: event.existing_printings.find(p => p.collection_id === event.suggestion.sell_collection_id)?.set_code || '?' })}
        {event.suggestion.action === 'sold_new' && t('inbox.suggestion.sell_new')}
        {event.suggestion.action === 'keep' && t('inbox.suggestion.keep')}
        <br />
        <span style={{ fontSize: '10px' }}>{event.suggestion.reason}</span>
      </div>

      <div className={styles.sourceSection}>
        <div className={styles.sourceLabel}>{t('inbox.source.label')}</div>
        <SourcePicker value={source} onChange={handleSourceChange} />
      </div>

      <div className={styles.actions}>
        {event.suggestion.action === 'swap' && (
          <Button
            appearance="primary"
            size="small"
            disabled={busy}
            onClick={() => setDialogMode('swap')}
            style={{ backgroundColor: accent.oklch }}
          >
            {t('inbox.action.swap')}
          </Button>
        )}
        <Button
          appearance="outline"
          size="small"
          disabled={busy}
          onClick={() => setDialogMode('sold_new')}
        >
          {t('inbox.action.sell_new')}
        </Button>
        <Button
          appearance="outline"
          size="small"
          disabled={busy}
          onClick={() => {
            if (!source) return;
            handleDecide({ action: 'keep', source });
          }}
        >
          {t('inbox.action.keep')}
        </Button>
        {!source && (
          <span className={styles.warning}>← select source first</span>
        )}
        <Button
          appearance="subtle"
          size="small"
          disabled={busy}
          onClick={() => handleDecide({ action: 'dismiss' })}
        >
          {t('inbox.action.dismiss')}
        </Button>
        <Button
          appearance="subtle"
          size="small"
          onClick={() => onSkip(event.id)}
        >
          {t('inbox.action.skip')}
        </Button>
      </div>

      <TriageDecisionDialog
        open={dialogMode !== null}
        onClose={() => setDialogMode(null)}
        onConfirm={(data) => {
          setDialogMode(null);
          handleDecide({
            action: dialogMode!,
            source: source || undefined,
            ...data,
          });
        }}
        mode={dialogMode || 'sold_new'}
        cardName={event.card.name}
        estimatedPrice={event.suggestion.estimated_price_eur}
        suggestedPrice={event.suggestion.suggested_sell_price_eur}
        qtyDelta={event.qty_delta}
        suggestedSellId={event.suggestion.sell_collection_id}
        existingPrintings={event.existing_printings}
      />
    </Panel>
  );
}
