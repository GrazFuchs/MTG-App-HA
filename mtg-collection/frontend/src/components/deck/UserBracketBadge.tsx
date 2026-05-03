import { useState } from 'react';
import { Badge, Popover, PopoverTrigger, PopoverSurface, Button } from '@fluentui/react-components';
import { api, DeckDetail } from '../../api';

interface Props {
  deck: DeckDetail;
  onUpdate: (d: DeckDetail) => void;
}

export function UserBracketBadge({ deck, onUpdate }: Props) {
  const [open, setOpen] = useState(false);

  const handleSelect = async (value: number | null) => {
    setOpen(false);
    const updated = await api.updateDeckUserFields(deck.id, { user_bracket: value });
    onUpdate(updated);
  };

  return (
    <span style={{ display: 'inline-flex', gap: 4, alignItems: 'center' }}>
      {deck.bracket > 0 && (
        <Badge appearance="outline" color="informative" title="Archidekt Bracket">
          B{deck.bracket}
        </Badge>
      )}
      <Popover open={open} onOpenChange={(_, d) => setOpen(d.open)}>
        <PopoverTrigger>
          <Badge
            appearance="filled"
            color={deck.user_bracket ? 'brand' : 'subtle'}
            style={{ cursor: 'pointer' }}
            title="Your Bracket (click to edit)"
          >
            {deck.user_bracket ? `My B${deck.user_bracket}` : 'Set Bracket'}
          </Badge>
        </PopoverTrigger>
        <PopoverSurface style={{ display: 'flex', gap: 4 }}>
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
          <Button size="small" appearance="subtle" onClick={() => handleSelect(null)}>—</Button>
        </PopoverSurface>
      </Popover>
    </span>
  );
}
