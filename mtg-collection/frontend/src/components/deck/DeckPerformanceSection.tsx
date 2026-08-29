import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Button,
  Spinner,
  Dialog,
  DialogSurface,
  DialogBody,
  DialogTitle,
  DialogContent,
  DialogActions,
  Input,
  Textarea,
  Dropdown,
  Option,
  Checkbox,
  Field,
  Badge,
} from '@fluentui/react-components';
import { Add16Regular, Delete16Regular } from '@fluentui/react-icons';
import { api, DeckGame, DeckGamePayload, DeckPerformanceStats, GameResult } from '../../api';
import { sothera } from '../../theme/sothera';
import { useAccent } from '../../main';
import { Panel, SectionHeader } from '../sothera';
import { recentForm, winRateTone } from '../../utils/deckPerformance';

import { t } from '../../i18n';
interface Props {
  deckId: number;
}

const RESULT_COLOR: Record<GameResult, 'success' | 'danger' | 'warning'> = {
  win: 'success', loss: 'danger', draw: 'warning',
};
const TONE_COLOR = { good: '#3fb950', mid: '#d29922', bad: '#f85149' } as const;

const todayISO = () => new Date().toISOString().slice(0, 10);

const emptyForm: DeckGamePayload = {
  result: 'win', played_at: todayISO(), on_play: false, pod_size: 4,
  mulligans: 0, missed_land_drops: 0, turns: 0,
  opponents: '', what_worked: '', what_didnt: '', notes: '',
};

function Stat({ label, value, color }: { label: string; value: string | number; color?: string }) {
  return (
    <div style={{ minWidth: 92 }}>
      <div style={{ fontFamily: sothera.fontDisplay, fontSize: 22, fontWeight: 700, color: color || sothera.fg, fontFeatureSettings: '"tnum"' }}>{value}</div>
      <div style={{ fontFamily: sothera.fontMono, fontSize: 9, letterSpacing: 1.5, color: sothera.fgFaint, textTransform: 'uppercase' }}>{label}</div>
    </div>
  );
}

export function DeckPerformanceSection({ deckId }: Props) {
  const { accent } = useAccent();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<DeckGamePayload>(emptyForm);

  const { data: perf } = useQuery<DeckPerformanceStats>({
    queryKey: ['deck-performance', deckId],
    queryFn: () => api.getDeckPerformance(deckId),
  });
  const { data: games = [], isLoading } = useQuery<DeckGame[]>({
    queryKey: ['deck-games', deckId],
    queryFn: () => api.getDeckGames(deckId),
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['deck-performance', deckId] });
    queryClient.invalidateQueries({ queryKey: ['deck-games', deckId] });
  };

  const addGame = useMutation({
    mutationFn: (data: DeckGamePayload) => api.addDeckGame(deckId, data),
    onSuccess: () => { invalidate(); setOpen(false); setForm({ ...emptyForm, played_at: todayISO() }); },
  });
  const removeGame = useMutation({
    mutationFn: (gameId: number) => api.deleteDeckGame(deckId, gameId),
    onSuccess: invalidate,
  });

  const upd = (patch: Partial<DeckGamePayload>) => setForm(f => ({ ...f, ...patch }));
  const numUpd = (key: keyof DeckGamePayload, v: string) => upd({ [key]: Math.max(0, parseInt(v) || 0) } as Partial<DeckGamePayload>);

  if (isLoading) return <Spinner size="tiny" />;

  const winColor = perf ? TONE_COLOR[winRateTone(perf.win_rate)] : sothera.fg;

  return (
    <div style={{ marginBottom: 26 }}>
      <SectionHeader
        num=""
        title={t('perf.title')}
        right={`${perf?.games ?? 0} GAMES`}
        accent={accent.oklch}
      />
      <Panel>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12 }}>
          <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap' }}>
            <Stat label={t('perf.win_rate')} value={`${perf?.win_rate ?? 0}%`} color={winColor} />
            <Stat label={t('perf.wld')} value={`${perf?.wins ?? 0}/${perf?.losses ?? 0}/${perf?.draws ?? 0}`} />
            <Stat label={t('perf.recent_form')} value={recentForm(games) || '—'} />
            <Stat label={t('perf.on_play_win')} value={`${perf?.on_play_win_rate ?? 0}%`} />
            <Stat label={t('perf.avg_mulligans')} value={perf?.avg_mulligans ?? 0} />
            <Stat label={t('perf.avg_missed_lands')} value={perf?.avg_missed_land_drops ?? 0} />
            <Stat label={t('perf.avg_turns')} value={perf?.avg_turns ?? 0} />
          </div>
          <Button appearance="primary" size="small" icon={<Add16Regular />} onClick={() => { setForm({ ...emptyForm, played_at: todayISO() }); setOpen(true); }}>
            {t('perf.log_game')}
          </Button>
        </div>

        {games.length === 0 ? (
          <div style={{ fontFamily: sothera.fontMono, fontSize: 12, color: sothera.fgMuted, marginTop: 16, letterSpacing: 0.5 }}>
            {t('perf.empty')}
          </div>
        ) : (
          <div style={{ marginTop: 16 }}>
            {games.map(g => (
              <div key={g.id} style={{ display: 'flex', gap: 12, padding: '10px 0', borderTop: `1px solid ${sothera.rowBorder}`, alignItems: 'flex-start' }}>
                <Badge appearance="filled" color={RESULT_COLOR[g.result]} size="small" style={{ textTransform: 'uppercase', minWidth: 44 }}>{g.result}</Badge>
                <div style={{ flex: 1 }}>
                  <div style={{ fontFamily: sothera.fontMono, fontSize: 11, color: sothera.fgMuted }}>
                    {g.played_at}
                    {g.on_play ? ' · on the play' : ' · on the draw'}
                    {g.turns ? ` · ${g.turns} turns` : ''}
                    {g.mulligans ? ` · ${g.mulligans} mull` : ''}
                    {g.missed_land_drops ? t('perf.missed_lands_n', { count: g.missed_land_drops }) : ''}
                    {g.opponents ? ` · vs ${g.opponents}` : ''}
                  </div>
                  {(g.what_worked || g.what_didnt || g.notes) && (
                    <div style={{ fontSize: 12, color: sothera.fg, marginTop: 4, lineHeight: 1.5 }}>
                      {g.what_worked && <div>✅ {g.what_worked}</div>}
                      {g.what_didnt && <div>⚠️ {g.what_didnt}</div>}
                      {g.notes && <div style={{ color: sothera.fgMuted }}>{g.notes}</div>}
                    </div>
                  )}
                </div>
                <Button appearance="subtle" size="small" icon={<Delete16Regular />} aria-label={t('perf.delete_game')} onClick={() => removeGame.mutate(g.id)} />
              </div>
            ))}
          </div>
        )}
      </Panel>

      <Dialog open={open} onOpenChange={(_, d) => setOpen(d.open)}>
        <DialogSurface style={{ maxWidth: 520 }}>
          <DialogBody>
            <DialogTitle>{t('perf.log_a_game')}</DialogTitle>
            <DialogContent style={{ display: 'flex', flexDirection: 'column', gap: 12, paddingTop: 8 }}>
              <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                <Field label={t('common.result')}>
                  <Dropdown
                    value={String(form.result)}
                    selectedOptions={[String(form.result)]}
                    onOptionSelect={(_, d) => upd({ result: d.optionValue as GameResult })}
                  >
                    <Option value="win">{t('perf.win')}</Option>
                    <Option value="loss">{t('perf.loss')}</Option>
                    <Option value="draw">{t('perf.draw')}</Option>
                  </Dropdown>
                </Field>
                <Field label={t('common.date')}>
                  <Input type="date" value={form.played_at || ''} onChange={(_, d) => upd({ played_at: d.value })} />
                </Field>
              </div>

              <Checkbox label={t('perf.on_the_play')} checked={!!form.on_play} onChange={(_, d) => upd({ on_play: !!d.checked })} />

              <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                <Field label={t('perf.pod_size')}><Input type="number" min={1} max={8} value={String(form.pod_size)} onChange={(_, d) => numUpd('pod_size', d.value)} style={{ width: 90 }} /></Field>
                <Field label={t('perf.mulligans')}><Input type="number" min={0} value={String(form.mulligans)} onChange={(_, d) => numUpd('mulligans', d.value)} style={{ width: 90 }} /></Field>
                <Field label={t('perf.missed_lands')}><Input type="number" min={0} value={String(form.missed_land_drops)} onChange={(_, d) => numUpd('missed_land_drops', d.value)} style={{ width: 110 }} /></Field>
                <Field label={t('perf.turns')}><Input type="number" min={0} value={String(form.turns)} onChange={(_, d) => numUpd('turns', d.value)} style={{ width: 90 }} /></Field>
              </div>

              <Field label={t('perf.opponents')}>
                <Input value={form.opponents || ''} onChange={(_, d) => upd({ opponents: d.value })} placeholder={t('perf.opponents_hint')} />
              </Field>
              <Field label={t('perf.what_worked')}>
                <Textarea value={form.what_worked || ''} onChange={(_, d) => upd({ what_worked: d.value })} resize="vertical" />
              </Field>
              <Field label={t('perf.what_didnt')}>
                <Textarea value={form.what_didnt || ''} onChange={(_, d) => upd({ what_didnt: d.value })} resize="vertical" />
              </Field>
              <Field label={t('wishlist.notes_label')}>
                <Textarea value={form.notes || ''} onChange={(_, d) => upd({ notes: d.value })} resize="vertical" />
              </Field>
            </DialogContent>
            <DialogActions>
              <Button appearance="secondary" onClick={() => setOpen(false)}>{t('common.cancel')}</Button>
              <Button appearance="primary" disabled={addGame.isPending} onClick={() => addGame.mutate(form)}>
                {addGame.isPending ? t('perf.saving') : t('perf.save_game')}
              </Button>
            </DialogActions>
          </DialogBody>
        </DialogSurface>
      </Dialog>
    </div>
  );
}
