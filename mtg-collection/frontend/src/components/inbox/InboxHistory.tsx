import { useState } from 'react';
import { makeStyles } from '@griffel/react';
import { Button, Spinner, Badge } from '@fluentui/react-components';
import { ChevronLeft24Regular, ChevronRight24Regular } from '@fluentui/react-icons';
import { useQuery } from '@tanstack/react-query';
import { api, AcquisitionHistoryItem } from '../../api';
import { sothera } from '../../theme/sothera';

const STATE_LABELS: Record<string, string> = {
  keep: 'Kept',
  sold_new: 'Sold (new copy)',
  swapped: 'Swapped',
  swap: 'Swapped',
  dismiss: 'Dismissed',
};
const STATE_COLOR: Record<string, 'success' | 'warning' | 'danger' | 'informative' | 'brand'> = {
  keep: 'success',
  sold_new: 'warning',
  swapped: 'brand',
  swap: 'brand',
  dismiss: 'informative',
};

const useStyles = makeStyles({
  row: {
    display: 'grid',
    gridTemplateColumns: '44px 1fr auto',
    gap: '12px',
    alignItems: 'center',
    padding: '10px 12px',
    borderBottom: `1px solid ${sothera.rowBorder}`,
  },
  img: { width: '40px', height: '56px', objectFit: 'cover', borderRadius: '3px' },
  name: { fontWeight: 600, fontSize: '14px', color: sothera.fg },
  meta: { fontFamily: sothera.fontMono, fontSize: '10px', color: sothera.fgFaint, letterSpacing: '0.5px' },
  right: { display: 'flex', flexDirection: 'column', gap: '4px', alignItems: 'flex-end' },
  detailBtn: { fontFamily: sothera.fontMono, fontSize: '10px', color: sothera.fgMuted, cursor: 'pointer', background: 'none', border: 'none', padding: 0 },
  detail: {
    gridColumn: '1 / -1',
    marginTop: '8px',
    padding: '10px 12px',
    backgroundColor: 'rgba(255,255,255,0.03)',
    borderRadius: '4px',
    fontSize: '12px',
    color: sothera.fgMuted,
  },
  detailLabel: { fontFamily: sothera.fontMono, fontSize: '9px', letterSpacing: '1.5px', textTransform: 'uppercase', color: sothera.fgFaint, marginBottom: '4px' },
  pagination: { display: 'flex', justifyContent: 'center', gap: '8px', marginTop: '16px', alignItems: 'center' },
  pageInfo: { fontFamily: sothera.fontMono, fontSize: '12px', color: sothera.fgMuted },
  empty: { fontFamily: sothera.fontMono, fontSize: '12px', color: sothera.fgFaint, padding: '24px', textAlign: 'center' },
});

function fmtDate(iso: string | null): string {
  if (!iso) return '—';
  return iso.replace('T', ' ').slice(0, 16);
}

function HistoryRow({ item }: { item: AcquisitionHistoryItem }) {
  const styles = useStyles();
  const [open, setOpen] = useState(false);
  const snap = item.snapshot;
  const stateLabel = STATE_LABELS[item.triage_state] || item.triage_state;

  return (
    <>
      <div className={styles.row}>
        {item.image_uri
          ? <img src={item.image_uri} alt={item.card_name} className={styles.img} loading="lazy" />
          : <div className={styles.img} style={{ backgroundColor: 'rgba(255,255,255,0.05)' }} />}
        <div>
          <div className={styles.name}>
            {item.card_name}
            {item.is_foil && <Badge appearance="outline" size="small" style={{ marginLeft: 6 }}>◆ Foil</Badge>}
          </div>
          <div className={styles.meta}>
            {(item.set_name || item.set_code || '').toString()} · ×{item.qty_delta} · {item.condition}/{item.language}
            {item.source ? ` · ${item.source}` : ''}
          </div>
          {snap && (
            <button className={styles.detailBtn} onClick={() => setOpen(o => !o)}>
              {open ? '▾ hide details' : '▸ how it was booked'}
            </button>
          )}
        </div>
        <div className={styles.right}>
          <Badge appearance="filled" color={STATE_COLOR[item.triage_state] || 'informative'}>{stateLabel}</Badge>
          <span className={styles.meta}>{fmtDate(item.decided_at)}</span>
        </div>
      </div>
      {open && snap && (
        <div className={styles.detail}>
          <div className={styles.detailLabel}>Suggestion shown at confirmation</div>
          <div style={{ marginBottom: 8 }}>
            <strong>{snap.suggestion.action}</strong> — {snap.suggestion.reason}
            {snap.suggestion.suggested_sell_price_eur > 0 && ` · est. €${snap.suggestion.suggested_sell_price_eur.toFixed(2)}`}
          </div>
          <div className={styles.detailLabel}>State at that time</div>
          <div style={{ marginBottom: snap.existing_printings.length ? 8 : 0 }}>
            In decks: {snap.in_decks} · Market price: {snap.card.price_eur ? `€${snap.card.price_eur}` : '—'}
            {snap.listing_price_eur != null && ` · Listed at €${snap.listing_price_eur.toFixed(2)}`}
          </div>
          {snap.existing_printings.length > 0 && (
            <>
              <div className={styles.detailLabel}>Other copies owned then</div>
              <div>
                {snap.existing_printings.map((p, i) => (
                  <span key={i} style={{ fontFamily: sothera.fontMono, fontSize: 11 }}>
                    {(p.set_code || '?').toUpperCase()}{p.is_foil ? ' ◆' : ''} ×{p.quantity + p.foil_quantity}
                    {i < snap.existing_printings.length - 1 ? ' · ' : ''}
                  </span>
                ))}
              </div>
            </>
          )}
        </div>
      )}
    </>
  );
}

export default function InboxHistory() {
  const styles = useStyles();
  const [page, setPage] = useState(1);
  const { data, isLoading } = useQuery({
    queryKey: ['inbox-history', page],
    queryFn: () => api.getAcquisitionHistory(page, 50),
    staleTime: 30_000,
  });

  if (isLoading) return <Spinner label="Loading history..." style={{ marginTop: 24 }} />;

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / 50));

  if (items.length === 0) {
    return <div className={styles.empty}>No booked acquisitions yet — decisions you confirm in the Inbox appear here.</div>;
  }

  return (
    <div>
      {items.map(it => <HistoryRow key={it.event_id} item={it} />)}
      {totalPages > 1 && (
        <div className={styles.pagination}>
          <Button icon={<ChevronLeft24Regular />} appearance="subtle" size="small" disabled={page <= 1} onClick={() => setPage(p => Math.max(1, p - 1))} />
          <span className={styles.pageInfo}>Page {page} of {totalPages}</span>
          <Button icon={<ChevronRight24Regular />} appearance="subtle" size="small" disabled={page >= totalPages} onClick={() => setPage(p => p + 1)} />
        </div>
      )}
    </div>
  );
}
