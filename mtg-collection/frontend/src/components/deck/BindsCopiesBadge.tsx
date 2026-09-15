import { useState } from 'react';
import { Badge, Popover, PopoverTrigger, PopoverSurface, Button } from '@fluentui/react-components';
import { api, DeckDetail } from '../../api';
import { sothera } from '../../theme/sothera';

import { t } from '../../i18n';

interface Props {
  deck: DeckDetail;
  onUpdate: (d: DeckDetail) => void;
}

/**
 * Whether this deck's cards count as spoken for.
 *
 * A disassembled deck still has a decklist, but its cards are back in the box:
 * counting them as demand is what made 432 owned cards read as unavailable and
 * held ~130 € out of the surplus. The Archidekt folder decides by default
 * (`Disassembled`, `Older Versions`), and that decision is re-derived on every
 * sync — so the hand-set answer lives in its own column, exactly like the
 * bracket, and a sync can never undo it.
 *
 * Three states, and the badge says which one you are looking at: derived from
 * the folder, or set by hand. "—" hands the deck back to its folder rather
 * than setting the same value by hand, because those are different statements
 * about who is in charge.
 */
export function BindsCopiesBadge({ deck, onUpdate }: Props) {
  const [open, setOpen] = useState(false);
  const overridden = deck.binds_copies_override !== null;

  const set = async (value: boolean | null) => {
    setOpen(false);
    onUpdate(await api.updateDeckUserFields(deck.id, { binds_copies_override: value }));
  };

  // Only worth a badge when the answer is "no" or when someone decided it by
  // hand. A binding deck in a normal folder is the default and needs no chip.
  if (deck.binds_copies && !overridden) return null;

  return (
    <Popover open={open} onOpenChange={(_, d) => setOpen(d.open)}>
      <PopoverTrigger>
        <Badge
          appearance={overridden ? 'filled' : 'outline'}
          color={deck.binds_copies ? 'informative' : 'warning'}
          style={{ cursor: 'pointer' }}
          title={
            overridden
              ? t('binds.title_manual')
              : t('binds.title_folder', { folder: deck.folder_name })
          }
        >
          {deck.binds_copies ? t('binds.binds') : t('binds.not_binding')}
        </Badge>
      </PopoverTrigger>
      <PopoverSurface style={{ maxWidth: 360 }}>
        <div style={{ fontFamily: sothera.fontMono, fontSize: 10, letterSpacing: 1, color: sothera.fgFaint, marginBottom: 8 }}>
          {t('binds.heading')}
        </div>
        <div style={{ fontSize: 12, color: sothera.fgMuted, marginBottom: 10, lineHeight: 1.5 }}>
          {t('binds.explain')}
        </div>
        <div style={{ display: 'flex', gap: 4 }}>
          <Button
            size="small"
            appearance={deck.binds_copies_override === true ? 'primary' : 'subtle'}
            onClick={() => set(true)}
          >
            {t('binds.binds')}
          </Button>
          <Button
            size="small"
            appearance={deck.binds_copies_override === false ? 'primary' : 'subtle'}
            onClick={() => set(false)}
          >
            {t('binds.not_binding')}
          </Button>
          <Button size="small" appearance="subtle" onClick={() => set(null)} title={t('binds.clear')}>
            —
          </Button>
        </div>
        <div style={{ fontSize: 11, color: sothera.fgFaint, marginTop: 10, lineHeight: 1.5 }}>
          {overridden
            ? t('binds.source_manual')
            : t('binds.source_folder', { folder: deck.folder_name || '—' })}
        </div>
      </PopoverSurface>
    </Popover>
  );
}
