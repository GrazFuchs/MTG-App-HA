import { useState } from 'react';
import { Badge, Popover, PopoverTrigger, PopoverSurface, Button, Spinner } from '@fluentui/react-components';
import { api, DeckDetail } from '../../api';
import { sothera } from '../../theme/sothera';

interface Props {
  deck: DeckDetail;
  onUpdate: (d: DeckDetail) => void;
}

/** How the shown bracket got its number, in the order the app trusts them. */
function sourceLabel(deck: DeckDetail): string {
  if (deck.user_bracket) return 'set by you';
  if (deck.computed_bracket) return 'computed from the decklist';
  if (deck.bracket) return 'imported from Archidekt';
  return 'not set';
}

export function UserBracketBadge({ deck, onUpdate }: Props) {
  const [open, setOpen] = useState(false);
  const [why, setWhy] = useState(false);
  const [busy, setBusy] = useState(false);

  const effective = deck.effective_bracket;
  const detail = deck.computed_bracket_detail;

  const handleSelect = async (value: number | null) => {
    setOpen(false);
    const updated = await api.updateDeckUserFields(deck.id, { user_bracket: value });
    onUpdate(updated);
  };

  const handleRecompute = async () => {
    setBusy(true);
    try {
      await api.recomputeDeckBracket(deck.id);
      onUpdate(await api.getDeck(deck.id));
    } finally {
      setBusy(false);
    }
  };

  return (
    <span style={{ display: 'inline-flex', gap: 6, alignItems: 'center' }}>
      <Popover open={open} onOpenChange={(_, d) => setOpen(d.open)}>
        <PopoverTrigger>
          <Badge
            appearance="filled"
            color={deck.user_bracket ? 'brand' : effective ? 'informative' : 'subtle'}
            style={{ cursor: 'pointer' }}
            title={`Bracket ${effective ?? '—'} — ${sourceLabel(deck)}. Click to set your own.`}
          >
            {effective ? `Bracket ${effective}` : 'Set Bracket'}
          </Badge>
        </PopoverTrigger>
        <PopoverSurface>
          <div style={{ fontFamily: sothera.fontMono, fontSize: 10, letterSpacing: 1, color: sothera.fgFaint, marginBottom: 8 }}>
            YOUR BRACKET · overrides the computed one
          </div>
          <div style={{ display: 'flex', gap: 4 }}>
            {[1, 2, 3, 4, 5].map(n => (
              <Button
                key={n}
                size="small"
                appearance={deck.user_bracket === n ? 'primary' : 'subtle'}
                onClick={() => handleSelect(n)}
              >
                {n}
              </Button>
            ))}
            <Button
              size="small"
              appearance="subtle"
              onClick={() => handleSelect(null)}
              title="Clear — fall back to the computed bracket"
            >
              —
            </Button>
          </div>
          {deck.computed_bracket && (
            <div style={{ fontSize: 11, color: sothera.fgMuted, marginTop: 10 }}>
              Computed from the decklist: <b>Bracket {deck.computed_bracket}</b>
            </div>
          )}
        </PopoverSurface>
      </Popover>

      {detail && (
        <Popover open={why} onOpenChange={(_, d) => setWhy(d.open)}>
          <PopoverTrigger>
            <Badge
              appearance="outline"
              color="subtle"
              style={{ cursor: 'pointer' }}
              title="What put this deck in that bracket"
            >
              why?
            </Badge>
          </PopoverTrigger>
          <PopoverSurface style={{ maxWidth: 420 }}>
            <div style={{ fontFamily: sothera.fontMono, fontSize: 10, letterSpacing: 1, color: sothera.fgFaint, marginBottom: 8 }}>
              COMPUTED BRACKET {detail.bracket}
            </div>
            {detail.reasons.length === 0 && (
              <div style={{ fontSize: 12, color: sothera.fgMuted }}>
                No game changers, no complete two-card combo, no mass land denial, no extra-turn plan.
              </div>
            )}
            {detail.reasons.map(r => (
              <div key={r.rule} style={{ marginBottom: 10 }}>
                <div style={{ fontSize: 12, color: sothera.fg }}>
                  <b>At least bracket {r.minimum}</b> — {r.note}
                </div>
                <div style={{ fontSize: 11, color: sothera.fgMuted, marginTop: 2 }}>
                  {r.evidence.join(' · ')}
                </div>
              </div>
            ))}
            <div style={{ fontSize: 10, color: sothera.fgFaint, marginTop: 10, lineHeight: 1.5 }}>
              {detail.scale}
              {detail.coverage.cards_not_classified_by_spellbook > 0 && (
                <>
                  {' '}
                  {detail.coverage.cards_not_classified_by_spellbook} of {detail.counts.cards} cards
                  are not classified by Commander Spellbook, so land denial and extra turns may be
                  under-counted.
                </>
              )}
              {deck.spellbook_bracket_tag && (
                <> Spellbook calls this deck “{deck.spellbook_bracket_tag}” on its own scale.</>
              )}
            </div>
            <div style={{ marginTop: 10 }}>
              <Button size="small" appearance="subtle" onClick={handleRecompute} disabled={busy}>
                {busy ? <Spinner size="tiny" /> : 'Recompute'}
              </Button>
            </div>
          </PopoverSurface>
        </Popover>
      )}
    </span>
  );
}
