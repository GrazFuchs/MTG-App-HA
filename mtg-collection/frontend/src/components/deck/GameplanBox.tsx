import { useState } from 'react';
import {
  Body1,
  Button,
  Dialog,
  DialogSurface,
  DialogBody,
  DialogTitle,
  DialogContent,
  DialogActions,
  Textarea,
  Caption1,
} from '@fluentui/react-components';
import { api, DeckDetail } from '../../api';

interface Props {
  deck: DeckDetail;
  onUpdate: (d: DeckDetail) => void;
}

export function GameplanBox({ deck, onUpdate }: Props) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState(deck.gameplan);

  const handleSave = async () => {
    const updated = await api.updateDeckUserFields(deck.id, { gameplan: text });
    onUpdate(updated);
    setOpen(false);
  };

  return (
    <div style={{ marginTop: 8 }}>
      {deck.gameplan ? (
        <Body1 style={{ whiteSpace: 'pre-wrap', opacity: 0.85 }}>{deck.gameplan}</Body1>
      ) : (
        <Caption1 style={{ opacity: 0.5 }}>No gameplan set</Caption1>
      )}
      <Button
        size="small"
        appearance="subtle"
        onClick={() => { setText(deck.gameplan); setOpen(true); }}
        style={{ marginLeft: 8 }}
      >
        {deck.gameplan ? 'Edit' : 'Add Gameplan'}
      </Button>
      <Dialog open={open} onOpenChange={(_, d) => setOpen(d.open)}>
        <DialogSurface>
          <DialogBody>
            <DialogTitle>Gameplan</DialogTitle>
            <DialogContent>
              <Textarea
                value={text}
                onChange={(_, d) => setText(d.value)}
                maxLength={500}
                rows={4}
                style={{ width: '100%' }}
              />
              <Caption1>{text.length}/500</Caption1>
            </DialogContent>
            <DialogActions>
              <Button onClick={() => setOpen(false)}>Cancel</Button>
              <Button appearance="primary" onClick={handleSave}>Save</Button>
            </DialogActions>
          </DialogBody>
        </DialogSurface>
      </Dialog>
    </div>
  );
}
