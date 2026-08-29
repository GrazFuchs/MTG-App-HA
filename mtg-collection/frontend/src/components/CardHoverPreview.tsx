/**
 * Card preview — the full Scryfall image, on hover *and* on tap/keyboard.
 *
 * Hover alone was not enough. The card image is the primary way to identify a
 * card during triage — the name alone does not tell you which printing you are
 * looking at — and on a phone there is no hover at all, so on the device where
 * the inbox is most often worked through, the image was simply unreachable.
 *
 * So the wrapper is focusable and toggles on click/Enter/Space, and Escape
 * closes it. Hover still works exactly as before for mouse users; the tap path
 * is additive.
 *
 * Renders through OverlayPortal (into document.body), guaranteeing correct
 * position and z-index regardless of ancestor CSS.
 */
import { useState, useRef, useEffect } from 'react';
import { OverlayPortal } from './OverlayPortal';
import { tokens } from '@fluentui/react-components';
import type { Card } from '../api';
import { t } from '../i18n';

interface CardHoverPreviewProps {
  card: Card;
  children: React.ReactNode;
  /** When wrapping a table row, set this — wrapper becomes <tr> instead of <span>. */
  asTableRow?: boolean;
}

const PREVIEW_W = 250;
const PREVIEW_H = 350;
const ORACLE_EXTRA_H = 120;

export function CardHoverPreview({ card, children, asTableRow }: CardHoverPreviewProps) {
  const [show, setShow] = useState(false);
  const [pinned, setPinned] = useState(false);
  const [pos, setPos] = useState({ x: 0, y: 0 });
  const timerRef = useRef<ReturnType<typeof setTimeout>>();

  const imageUrl = card.image_uri || (card.scryfall_id
    ? `https://cards.scryfall.io/normal/front/${card.scryfall_id[0]}/${card.scryfall_id[1]}/${card.scryfall_id}.jpg`
    : '');

  const computePos = (clientX: number, clientY: number) => {
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    const totalH = PREVIEW_H + (card.oracle_text ? ORACLE_EXTRA_H : 0);

    // Prefer right of cursor; flip to left if would overflow
    let x = clientX + 16;
    if (x + PREVIEW_W + 8 > vw) x = clientX - PREVIEW_W - 16;
    if (x < 8) x = 8;

    // Vertically center on cursor; clamp to viewport
    let y = clientY - PREVIEW_H / 2;
    if (y < 8) y = 8;
    if (y + totalH > vh - 8) y = vh - totalH - 8;
    if (y < 8) y = 8; // for very small viewports

    return { x, y };
  };

  const handleMouseEnter = (e: React.MouseEvent) => {
    const x = e.clientX;
    const y = e.clientY;
    timerRef.current = setTimeout(() => {
      setPos(computePos(x, y));
      setShow(true);
    }, 200);
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (show) {
      setPos(computePos(e.clientX, e.clientY));
    }
  };

  const handleMouseLeave = () => {
    clearTimeout(timerRef.current);
    if (!pinned) setShow(false);
  };

  /**
   * Tap or Enter/Space pins the preview open until dismissed. Anchored to the
   * element's own box rather than to a pointer position, because a keyboard
   * has no pointer and a tap coordinate is the finger, not the card.
   */
  const togglePinned = (target: HTMLElement) => {
    if (pinned) {
      setPinned(false);
      setShow(false);
      return;
    }
    const r = target.getBoundingClientRect();
    clearTimeout(timerRef.current);
    setPos(computePos(Math.min(r.right, window.innerWidth - 8), r.top + r.height / 2));
    setPinned(true);
    setShow(true);
  };

  // Hide preview if user scrolls or window resizes (avoids stale fixed-position)
  useEffect(() => {
    if (!show) return;
    const hide = () => { setShow(false); setPinned(false); };
    window.addEventListener('scroll', hide, true); // capture for nested scrollers
    window.addEventListener('resize', hide);
    return () => {
      window.removeEventListener('scroll', hide, true);
      window.removeEventListener('resize', hide);
    };
  }, [show]);

  // Escape closes a pinned preview. Without it the only way out on a touch
  // device would be to find the element again and tap it a second time.
  useEffect(() => {
    if (!pinned) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { setPinned(false); setShow(false); }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [pinned]);

  useEffect(() => () => clearTimeout(timerRef.current), []);

  if (!imageUrl) return <>{children}</>;

  const eventHandlers = {
    onMouseEnter: handleMouseEnter,
    onMouseMove: handleMouseMove,
    onMouseLeave: handleMouseLeave,
    onClick: (e: React.MouseEvent) => togglePinned(e.currentTarget as HTMLElement),
    onKeyDown: (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        togglePinned(e.currentTarget as HTMLElement);
      }
    },
    tabIndex: 0,
    role: 'button',
    'aria-expanded': show,
    'aria-label': t('cards.preview', { name: card.name }),
  };

  // For table rows: wrap with a <tr> that the parent <tbody> accepts.
  // For everything else: an inline <span> avoids breaking flow.
  const Wrapper = asTableRow ? 'tr' : 'span';
  const wrapperStyle = asTableRow
    ? undefined
    : { display: 'inline' };

  return (
    <>
      <Wrapper {...eventHandlers} style={wrapperStyle as any}>
        {children}
      </Wrapper>
      {show && (
        <OverlayPortal>
        <div
          style={{
            position: 'fixed',
            left: pos.x,
            top: pos.y,
            zIndex: 2147483000, // max safe int territory; survives Fluent dialogs
            pointerEvents: 'none',
            filter: `drop-shadow(0 4px 12px rgba(0,0,0,0.4))`,
          }}
        >
          <img
            src={imageUrl}
            alt={card.name}
            style={{ width: PREVIEW_W, borderRadius: 12, display: 'block' }}
          />
          {card.oracle_text && (
            <div style={{
              marginTop: 6,
              padding: '8px 10px',
              background: tokens.colorNeutralBackground1,
              borderRadius: 8,
              fontSize: 12,
              lineHeight: 1.4,
              maxWidth: PREVIEW_W,
              color: tokens.colorNeutralForeground1,
              whiteSpace: 'pre-wrap',
            }}>
              {card.oracle_text}
            </div>
          )}
        </div>
        </OverlayPortal>
      )}
    </>
  );
}
