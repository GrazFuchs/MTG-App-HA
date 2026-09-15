import { useState } from 'react';
import { Badge, Popover, PopoverTrigger, PopoverSurface, Button } from '@fluentui/react-components';
import { api } from '../../api';
import { sothera } from '../../theme/sothera';

import { t } from '../../i18n';

/**
 * Whether a rules violation on this deck is worth interrupting someone for.
 *
 * The first full deck check over the real collection found three decks, and two
 * of them were drafts: 43 cards out of 60, and 2 cards out of 60, both sitting
 * in "Work in Progress". Neither is a fault — a deck being built is not
 * *illegal*, the question simply does not apply to it yet. Announcing it as a
 * fault is how a checker gets switched off rather than fixed.
 *
 * ⚠️ **This silences the notification, never the check.** The deck check below
 * still runs and still lists every violation, the API still answers, and the
 * Home Assistant sensor still carries `violations`. What stops is the push and
 * the fault-board card.
 *
 * Three states, same as the bracket and `binds_copies`: the Archidekt folder
 * decides by default and is re-derived on every sync, a hand-set answer lives
 * in its own column that a sync never writes, and "—" hands the deck back to
 * its folder rather than freezing the current value — those are different
 * statements about who is in charge.
 *
 * Takes the four fields it needs rather than a whole `DeckDetail`, so the deck
 * list can show the same control as the deck page. One component, because two
 * copies of "the same toggle" is exactly how the bracket readers drifted apart
 * for a whole deploy (0.47.0 → 0.47.1).
 */
export interface LegalityPushDeck {
  id: number;
  legality_push: boolean;
  legality_push_override: boolean | null;
  folder_name: string;
}

interface Props {
  deck: LegalityPushDeck;
  /** Called after the change landed, so the caller can refresh its own copy. */
  onUpdated: () => void;
  /** In the deck list the badge sits inside a tile that navigates on click. */
  compact?: boolean;
}

export function LegalityPushBadge({ deck, onUpdated, compact }: Props) {
  const [open, setOpen] = useState(false);
  const overridden = deck.legality_push_override !== null;

  const set = async (value: boolean | null) => {
    setOpen(false);
    await api.updateDeckUserFields(deck.id, { legality_push_override: value });
    onUpdated();
  };

  // In the deck list the badge is a *marker*: it appears only when a deck is
  // silenced or was decided by hand, because a row of "announces: yes" chips
  // on every tile would say nothing. On the deck page it is a *control* and is
  // always there — a switch you can only find once it is already flipped is
  // not a switch.
  if (compact && deck.legality_push && !overridden) return null;

  return (
    <Popover open={open} onOpenChange={(_, d) => setOpen(d.open)}>
      <PopoverTrigger>
        <Badge
          appearance={overridden ? 'filled' : 'outline'}
          color={deck.legality_push ? 'informative' : 'warning'}
          size={compact ? 'small' : 'medium'}
          style={{ cursor: 'pointer' }}
          // The tile underneath navigates to the deck. Without this, opening
          // the popover would also leave the page it belongs to.
          onClick={(e: React.MouseEvent) => e.stopPropagation()}
          title={
            overridden
              ? t('legality_push.title_manual')
              : t('legality_push.title_folder', { folder: deck.folder_name })
          }
        >
          {deck.legality_push ? t('legality_push.on') : t('legality_push.off')}
        </Badge>
      </PopoverTrigger>
      <PopoverSurface style={{ maxWidth: 380 }} onClick={(e: React.MouseEvent) => e.stopPropagation()}>
        <div style={{ fontFamily: sothera.fontMono, fontSize: 10, letterSpacing: 1, color: sothera.fgFaint, marginBottom: 8 }}>
          {t('legality_push.heading')}
        </div>
        <div style={{ fontSize: 12, color: sothera.fgMuted, marginBottom: 10, lineHeight: 1.5 }}>
          {t('legality_push.explain')}
        </div>
        <div style={{ display: 'flex', gap: 4 }}>
          <Button
            size="small"
            appearance={deck.legality_push_override === true ? 'primary' : 'subtle'}
            onClick={() => set(true)}
          >
            {t('legality_push.on')}
          </Button>
          <Button
            size="small"
            appearance={deck.legality_push_override === false ? 'primary' : 'subtle'}
            onClick={() => set(false)}
          >
            {t('legality_push.off')}
          </Button>
          <Button size="small" appearance="subtle" onClick={() => set(null)} title={t('legality_push.clear')}>
            —
          </Button>
        </div>
        <div style={{ fontSize: 11, color: sothera.fgFaint, marginTop: 10, lineHeight: 1.5 }}>
          {overridden
            ? t('legality_push.source_manual')
            : t('legality_push.source_folder', { folder: deck.folder_name || '—' })}
        </div>
      </PopoverSurface>
    </Popover>
  );
}
