import { useRef, useState, ReactNode } from 'react';
import { makeStyles, shorthands } from '@griffel/react';
import { api, PriceHistoryEntry } from '../api';
import { Sparkline } from './Sparkline';
import { sothera } from '../theme/sothera';
import { useAccent } from '../main';

const useStyles = makeStyles({
  trigger: {
    cursor: 'help',
    textDecorationLine: 'underline',
    textDecorationStyle: 'dotted',
    textDecorationColor: sothera.fgFaint,
    textUnderlineOffset: '2px',
  },
  popup: {
    position: 'fixed',
    zIndex: 10000,
    backgroundColor: sothera.glassBg,
    ...shorthands.borderWidth('1px'),
    ...shorthands.borderStyle('solid'),
    ...shorthands.borderColor(sothera.glassBorder),
    ...shorthands.borderRadius('4px'),
    padding: '8px 12px',
    backdropFilter: 'blur(12px)',
    boxShadow: '0 8px 24px rgba(0,0,0,0.45)',
  },
});

interface Props {
  /** Card name used to match a Cardmarket product for price history. */
  cardName: string;
  /** The visible trigger content (card name text, etc.). */
  children: ReactNode;
  /** Days of history to display (default 14 = last 2 weeks). */
  days?: number;
  /** Optional override for the popup header label. */
  label?: string;
}

/**
 * Wraps any content with a hover popup showing an interactive price-trend
 * sparkline (Cardmarket trend) for the last `days` days. Fetches lazily on
 * first hover. The popup is hoverable so the cursor can travel along the graph.
 */
export default function PriceTrendHover({ cardName, children, days = 14, label }: Props) {
  const styles = useStyles();
  const { accent } = useAccent();
  const [history, setHistory] = useState<PriceHistoryEntry[] | null>(null);
  const [show, setShow] = useState(false);
  const [pos, setPos] = useState({ x: 0, y: 0 });
  const enterTimer = useRef<ReturnType<typeof setTimeout>>();
  const leaveTimer = useRef<ReturnType<typeof setTimeout>>();
  const fetched = useRef(false);

  const fetchHistory = async () => {
    if (fetched.current) return;
    fetched.current = true;
    try {
      const products = await api.getMatchedProducts(cardName);
      if (products.length > 0) {
        const h = await api.getPriceHistory(products[0].cm_product_id, days);
        setHistory(h.slice(-days));
      } else {
        setHistory([]);
      }
    } catch {
      setHistory([]);
    }
  };

  const handleEnter = (e: React.MouseEvent) => {
    if (leaveTimer.current) clearTimeout(leaveTimer.current);
    const { clientX, clientY } = e;
    enterTimer.current = setTimeout(async () => {
      await fetchHistory();
      setPos({
        x: Math.min(clientX + 16, window.innerWidth - 240),
        y: Math.max(8, clientY - 100),
      });
      setShow(true);
    }, 250);
  };

  const handleLeave = () => {
    if (enterTimer.current) clearTimeout(enterTimer.current);
    leaveTimer.current = setTimeout(() => setShow(false), 200);
  };

  const cancelLeave = () => {
    if (leaveTimer.current) clearTimeout(leaveTimer.current);
  };

  return (
    <span className={styles.trigger} onMouseEnter={handleEnter} onMouseLeave={handleLeave}>
      {children}
      {show && history && (
        <div
          className={styles.popup}
          style={{ left: pos.x, top: pos.y }}
          onMouseEnter={cancelLeave}
          onMouseLeave={handleLeave}
        >
          <div style={{ fontFamily: sothera.fontMono, fontSize: 10, color: sothera.fgFaint, marginBottom: 4, letterSpacing: 1.5, textTransform: 'uppercase' }}>
            {label || `${days}-day trend`}
          </div>
          {history.length > 1 ? (
            <>
              <Sparkline data={history} width={200} height={56} accent={accent.oklch} dot={false} interactive />
              <div style={{ fontFamily: sothera.fontMono, fontSize: 10, color: sothera.fgMuted, marginTop: 4 }}>
                €{history[history.length - 1].trend.toFixed(2)} (latest)
              </div>
            </>
          ) : (
            <div style={{ fontFamily: sothera.fontMono, fontSize: 10, color: sothera.fgFaint }}>
              No price history
            </div>
          )}
        </div>
      )}
    </span>
  );
}
