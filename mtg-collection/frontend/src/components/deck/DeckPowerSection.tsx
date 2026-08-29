import { useState } from 'react';
import { Button, Spinner } from '@fluentui/react-components';
import { api, DeckDetail } from '../../api';
import { sothera } from '../../theme/sothera';
import { useAccent } from '../../main';
import { Panel, SectionHeader } from '../sothera';

import { t } from '../../i18n';
interface Props {
  deck: DeckDetail;
  onUpdate: (d: DeckDetail) => void;
}

function Figure({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div style={{ minWidth: 92 }}>
      <div style={{
        fontFamily: sothera.fontMono, fontSize: 9, letterSpacing: 1.4,
        color: sothera.fgFaint, textTransform: 'uppercase',
      }}>
        {label}
      </div>
      <div style={{
        fontFamily: sothera.fontDisplay, fontSize: 22, fontWeight: 600,
        color: sothera.fg, fontFeatureSettings: '"tnum"', lineHeight: 1.2,
      }}>
        {value}
      </div>
      {hint && (
        <div style={{ fontSize: 10, color: sothera.fgMuted, marginTop: 2 }}>{hint}</div>
      )}
    </div>
  );
}

/**
 * The edhpowerlevel port. Score first, level second: the original's author
 * recommends comparing the score between decks and calls the level the softer
 * reading of the two.
 */
export function DeckPowerSection({ deck, onUpdate }: Props) {
  const { accent } = useAccent();
  const [busy, setBusy] = useState(false);
  const detail = deck.power_detail;

  const recompute = async () => {
    setBusy(true);
    try {
      await api.recomputeDeckPower(deck.id);
      onUpdate(await api.getDeck(deck.id));
    } finally {
      setBusy(false);
    }
  };

  const openReference = async () => {
    const { url } = await api.getDeckPowerReferenceUrl(deck.id);
    window.open(url, '_blank', 'noopener');
  };

  if (!detail) {
    return (
      <div style={{ marginBottom: 26 }}>
        <SectionHeader num="" title={t('power.title')} right="" accent={accent.oklch} />
        <Panel>
          <div style={{ fontFamily: sothera.fontMono, fontSize: 11, color: sothera.fgFaint, marginBottom: 10 }}>
            {t('power.not_scored')}
          </div>
          <Button appearance="subtle" size="small" onClick={recompute} disabled={busy} style={{ color: accent.oklch }}>
            {busy ? <Spinner size="tiny" /> : t('power.compute')}
          </Button>
        </Panel>
      </div>
    );
  }

  const byCmc = Object.entries(detail.impact_by_cmc);
  const peak = Math.max(...byCmc.map(([, v]) => v), 1);

  return (
    <div style={{ marginBottom: 26 }}>
      <SectionHeader
        num=""
        title={t('power.title')}
        right={`SCORE ${Math.round(detail.score)} · LEVEL ${detail.power_level.toFixed(1)}`}
        accent={accent.oklch}
      />
      <Panel>
        <div style={{ display: 'flex', gap: 26, flexWrap: 'wrap', marginBottom: 18 }}>
          <Figure label={t('power.score')} value={String(Math.round(detail.score))} hint="0–1000 · compare this" />
          <Figure label={t('power.level')} value={detail.power_level.toFixed(1)} hint="0–10" />
          <Figure label={t('power.efficiency')} value={detail.efficiency.toFixed(1)} hint="higher is faster" />
          <Figure label={t('power.tipping_point')} value={String(detail.tipping_point)} hint="mana for 65% of the power" />
          <Figure label={t('power.avg_cost')} value={detail.avg_cost.toFixed(2)} hint={`${detail.lands} lands`} />
        </div>

        {byCmc.length > 0 && (
          <div style={{ marginBottom: 18 }}>
            <div style={{
              fontFamily: sothera.fontMono, fontSize: 9, letterSpacing: 1.4,
              color: sothera.fgFaint, textTransform: 'uppercase', marginBottom: 8,
            }}>
              {t('power.by_mana_value')}
            </div>
            <div style={{ display: 'flex', alignItems: 'flex-end', gap: 6, height: 60 }}>
              {byCmc.map(([cmc, value]) => (
                <div key={cmc} style={{ textAlign: 'center', flex: '0 0 26px' }}>
                  <div
                    title={`${value} impact at mana value ${cmc}`}
                    style={{
                      height: Math.max(2, (value / peak) * 46),
                      background: accent.oklch,
                      opacity: Number(cmc) === detail.tipping_point ? 1 : 0.45,
                    }}
                  />
                  <div style={{ fontFamily: sothera.fontMono, fontSize: 9, color: sothera.fgFaint, marginTop: 3 }}>
                    {Number(cmc) % 1 === 0 ? Number(cmc) : cmc}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {detail.top_cards.length > 0 && (
          <div style={{ marginBottom: 16 }}>
            <div style={{
              fontFamily: sothera.fontMono, fontSize: 9, letterSpacing: 1.4,
              color: sothera.fgFaint, textTransform: 'uppercase', marginBottom: 6,
            }}>
              {t('power.carrying')}
            </div>
            {detail.top_cards.slice(0, 5).map(c => (
              <div key={c.name} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: sothera.fgMuted, padding: '2px 0' }}>
                <span>{c.name}</span>
                <span style={{ fontFamily: sothera.fontMono }}>{c.impact.toFixed(1)}</span>
              </div>
            ))}
          </div>
        )}

        <div style={{ fontSize: 10, color: sothera.fgFaint, lineHeight: 1.6, marginBottom: 12 }}>
          {detail.caveat} It is a separate reading from the bracket: combos, game changers and land
          denial go into that one and never into this. Popularity is scored against a card
          distribution from {detail.pop_curve_derived}.
        </div>

        <div style={{ display: 'flex', gap: 8 }}>
          <Button appearance="subtle" size="small" onClick={recompute} disabled={busy} style={{ color: sothera.fgMuted }}>
            {busy ? <Spinner size="tiny" /> : t('power.recompute')}
          </Button>
          <Button appearance="subtle" size="small" onClick={openReference} style={{ color: sothera.fgMuted }}>
            {t('power.reference')}
          </Button>
        </div>
      </Panel>
    </div>
  );
}
