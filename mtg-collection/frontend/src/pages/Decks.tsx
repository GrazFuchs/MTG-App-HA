import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { makeStyles, shorthands } from '@griffel/react';
import { Spinner, Select, Button } from '@fluentui/react-components';
import { api, DeckSummary } from '../api';
import { sothera } from '../theme/sothera';
import { useAccent } from '../main';
import { Panel, PageHeader, SectionHeader } from '../components/sothera';

const useStyles = makeStyles({
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
    gap: '14px',
  },
  card: {
    cursor: 'pointer',
    backgroundColor: sothera.glassBg,
    ...shorthands.borderWidth('1px'),
    ...shorthands.borderStyle('solid'),
    ...shorthands.borderColor(sothera.glassBorder),
    transitionProperty: 'border-color, box-shadow',
    transitionDuration: '160ms',
    position: 'relative',
    ':hover': {
      ...shorthands.borderColor(sothera.fgFaint),
    },
  },
  artWrap: {
    position: 'relative',
    height: '140px',
    overflow: 'hidden',
    borderBottom: `1px solid ${sothera.glassBorder}`,
  },
  artImg: {
    width: '100%',
    height: '100%',
    objectFit: 'cover',
    filter: 'saturate(0.85) contrast(1.05)',
  },
  artOverlay: {
    position: 'absolute',
    inset: '0',
    background: 'linear-gradient(180deg, transparent 30%, rgba(4,4,10,0.85) 100%)',
  },
  bracketTag: {
    position: 'absolute',
    top: '10px',
    left: '10px',
    fontFamily: sothera.fontMono,
    fontSize: '9px',
    letterSpacing: '1.5px',
    color: sothera.fg,
    padding: '3px 7px',
    background: 'rgba(0,0,0,0.45)',
    ...shorthands.borderWidth('1px'),
    ...shorthands.borderStyle('solid'),
  },
  cardBody: {
    padding: '16px',
  },
  cardName: {
    fontFamily: sothera.fontDisplay,
    fontSize: '15px',
    fontWeight: 600,
    color: sothera.fg,
    marginBottom: '8px',
    letterSpacing: '-0.3px',
  },
  cardMeta: {
    display: 'flex',
    gap: '6px',
    alignItems: 'center',
    flexWrap: 'wrap',
  },
  formatBadge: {
    fontFamily: sothera.fontMono,
    fontSize: '9px',
    padding: '3px 7px',
    ...shorthands.borderWidth('1px'),
    ...shorthands.borderStyle('solid'),
    ...shorthands.borderColor(sothera.glassBorder),
    color: sothera.fgMuted,
    letterSpacing: '1.5px',
    textTransform: 'uppercase',
  },
  cardFooter: {
    display: 'flex',
    justifyContent: 'space-between',
    marginTop: '12px',
    paddingTop: '10px',
    borderTop: `1px solid ${sothera.rowBorder}`,
    fontFamily: sothera.fontMono,
    fontSize: '10px',
    color: sothera.fgFaint,
    letterSpacing: '1px',
    textTransform: 'uppercase',
  },
  cardValue: {
    fontWeight: 600,
  },
  emptyMsg: {
    fontFamily: sothera.fontMono,
    fontSize: '13px',
    color: sothera.fgMuted,
    marginTop: '24px',
    letterSpacing: '1px',
  },
});

export default function Decks() {
  const styles = useStyles();
  const navigate = useNavigate();
  const { accent } = useAccent();
  const [decks, setDecks] = useState<DeckSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [bracketFilter, setBracketFilter] = useState('');

  useEffect(() => {
    api.getDecks().then(setDecks).finally(() => setLoading(false));
  }, []);

  const filteredDecks = useMemo(() => {
    if (!bracketFilter) return decks;
    const b = parseInt(bracketFilter, 10);
    return decks.filter(d => d.bracket === b);
  }, [decks, bracketFilter]);

  const grouped = useMemo(() => {
    const map = new Map<string, DeckSummary[]>();
    for (const d of filteredDecks) {
      const folder = d.folder_name || 'Uncategorized';
      if (!map.has(folder)) map.set(folder, []);
      map.get(folder)!.push(d);
    }
    return [...map.entries()].sort(([a], [b]) => {
      if (a === 'Uncategorized') return 1;
      if (b === 'Uncategorized') return -1;
      return a.localeCompare(b);
    });
  }, [filteredDecks]);

  const availableBrackets = useMemo(() => {
    const set = new Set(decks.map(d => d.bracket).filter(b => b > 0));
    return [...set].sort();
  }, [decks]);

  if (loading) return <Spinner label="Loading decks..." />;

  if (decks.length === 0) {
    return (
      <div>
        <PageHeader eyebrow="⌬ INDEX" title="Decks" accent={accent.oklch} />
        <div className={styles.emptyMsg}>No decks synced yet. Go to Settings to trigger a sync from Archidekt.</div>
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        eyebrow={`⌬ INDEX · ${filteredDecks.length} BOUND DECKS`}
        title="Decks"
        accent={accent.oklch}
      />

      {availableBrackets.length > 0 && (
        <div style={{ marginBottom: 16, display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
          <Select
            value={bracketFilter}
            onChange={(_, d) => setBracketFilter(d.value)}
            style={{ minWidth: 180 }}
          >
            <option value="">All Brackets</option>
            {availableBrackets.map(b => (
              <option key={b} value={String(b)}>Bracket {String(b)}</option>
            ))}
          </Select>
          <Button
            appearance="subtle"
            size="small"
            onClick={() => navigate('/decks/compare')}
            style={{ color: sothera.fgMuted, fontFamily: sothera.fontMono, fontSize: 10, letterSpacing: 1 }}
          >
            ⌬ Compare Decks
          </Button>
        </div>
      )}

      {grouped.map(([folder, folderDecks], fi) => (
        <div key={folder} style={{ marginBottom: 36 }}>
          <SectionHeader
            num={String(fi + 1).padStart(2, '0')}
            title={folder}
            right={`${folderDecks.length} DECKS`}
            accent={accent.oklch}
          />
          <div className={styles.grid}>
            {folderDecks.map(d => (
              <div
                key={d.id}
                className={styles.card}
                onClick={() => navigate(`/decks/${d.id}`)}
              >
                {d.featured_image && (
                  <div className={styles.artWrap}>
                    <img src={d.featured_image} alt={d.name} className={styles.artImg} />
                    <div className={styles.artOverlay} />
                    <div style={{ position: 'absolute', inset: 0, background: accent.soft, mixBlendMode: 'color', opacity: 0.35 }} />
                    {d.bracket > 0 && (
                      <div className={styles.bracketTag} style={{ borderColor: accent.oklch }}>
                        BR.{d.bracket}
                      </div>
                    )}
                  </div>
                )}
                <div className={styles.cardBody}>
                  <div className={styles.cardName}>{d.name}</div>
                  <div className={styles.cardMeta}>
                    <span className={styles.formatBadge}>{d.format || 'Unknown'}</span>
                  </div>
                  <div className={styles.cardFooter}>
                    <span>{d.card_count} CARDS</span>
                    <span className={styles.cardValue} style={{ color: accent.oklch }}>
                      {d.commander_name ? `⚔ ${d.commander_name}` : ''}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
