/**
 * The deck check — what a 60-card deck gets instead of a bracket and a power
 * score. Size, sideboard, copies, and whether every card is legal in the
 * format the deck claims.
 *
 * Shown for every format, Commander included: a Commander deck is 100 singleton
 * cards and that is checkable too. It sits below the bracket rather than
 * replacing it, because the two answer different questions — what the deck is
 * capable of, and whether it is a deck at all.
 */
import { useQuery } from '@tanstack/react-query';
import { makeStyles } from '@griffel/react';
import { Badge, Button, Spinner } from '@fluentui/react-components';
import { api, DeckLegality, LegalityViolation } from '../../api';
import { sothera } from '../../theme/sothera';
import { useAccent } from '../../main';
import { Panel, SectionHeader } from '../sothera';
import { t } from '../../i18n';

const useStyles = makeStyles({
  row: {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
    padding: '7px 0',
    fontFamily: sothera.fontMono,
    fontSize: '12px',
  },
  counts: {
    display: 'flex',
    gap: '18px',
    flexWrap: 'wrap',
    fontFamily: sothera.fontMono,
    fontSize: '11px',
    color: sothera.fgMuted,
    letterSpacing: '1px',
    marginBottom: '10px',
  },
  note: {
    fontFamily: sothera.fontMono,
    fontSize: '11px',
    color: sothera.fgFaint,
    marginTop: '10px',
    lineHeight: 1.5,
  },
});

/** One line per rule, in the order a player would check them. */
const KIND_LABEL: Record<LegalityViolation['kind'], string> = {
  size: 'deck.legality_size',
  sideboard: 'deck.legality_sideboard',
  copies: 'deck.legality_copies',
  legality: 'deck.legality_card',
};

export function DeckLegalitySection({ deckId }: { deckId: number }) {
  const styles = useStyles();
  const { accent } = useAccent();

  const { data, isLoading, refetch, isFetching } = useQuery<DeckLegality>({
    queryKey: ['deck-legality', deckId],
    queryFn: () => api.getDeckLegality(deckId),
    staleTime: 5 * 60_000,
  });

  if (isLoading) return <Spinner size="tiny" />;
  if (!data) return null;

  // A format we do not recognise: say that nothing was checked rather than
  // showing an empty list, which would read as a clean bill of health.
  if (!data.checked) {
    return (
      <div style={{ marginBottom: 26 }}>
        <SectionHeader num="--" title={t('deck.legality_title')} accent={accent.oklch} />
        <Panel>
          <div className={styles.note}>{t('deck.legality_unchecked')}</div>
        </Panel>
      </div>
    );
  }

  const { violations } = data;
  return (
    <div style={{ marginBottom: 26 }}>
      <SectionHeader
        num="--"
        title={t('deck.legality_title')}
        right={violations.length === 0 ? t('deck.legality_ok') : `${violations.length}`}
        accent={accent.oklch}
      />
      <Panel>
        <div className={styles.counts}>
          <span>
            {t('deck.legality_main')}: {data.main_count}
            {data.rules?.main_min ? ` / ${data.rules.main_min}+` : ''}
          </span>
          {data.rules?.side_max ? (
            <span>
              {t('deck.legality_side')}: {data.side_count} / {data.rules.side_max}
            </span>
          ) : null}
          <span>
            {t('deck.legality_copies_label')}: {data.rules?.max_copies}
          </span>
          <span>{data.format}</span>
        </div>

        {violations.length === 0 ? (
          <div className={styles.row}>
            <Badge appearance="tint" color="success">✓</Badge>
            <span>{t('deck.legality_all_good')}</span>
          </div>
        ) : (
          violations.map((v, i) => (
            <div
              key={i}
              className={styles.row}
              style={{
                borderBottom: i < violations.length - 1 ? `1px solid ${sothera.rowBorder}` : 'none',
              }}
            >
              <Badge appearance="tint" color="danger" style={{ minWidth: 74 }}>
                {t(KIND_LABEL[v.kind] ?? 'deck.legality_card')}
              </Badge>
              <span style={{ color: sothera.fg }}>{v.detail}</span>
            </div>
          ))
        )}

        {/* Cards nobody could answer for are neither passed nor failed, and
            saying so is the point — a checker that rounds an unknown to "fine"
            has quietly stopped checking. */}
        {data.unknown_legality > 0 && (
          <div className={styles.note}>
            ⚠ {t('deck.legality_unknown', { count: data.unknown_legality })}
          </div>
        )}

        <Button
          appearance="subtle"
          size="small"
          disabled={isFetching}
          onClick={() => api.getDeckLegality(deckId, true).then(() => refetch())}
          style={{ marginTop: 10, fontFamily: sothera.fontMono, fontSize: 10, letterSpacing: 1 }}
        >
          {isFetching ? t('deck.legality_checking') : t('deck.legality_recheck')}
        </Button>
      </Panel>
    </div>
  );
}
