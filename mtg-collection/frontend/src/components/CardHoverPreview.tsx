/**
 * Card hover preview — shows the full Scryfall card image on mouse hover.
 */
import { useState, useRef, useEffect } from 'react';
import { tokens } from '@fluentui/react-components';
import type { Card } from '../api';

interface CardHoverPreviewProps {
  card: Card;
  children: React.ReactNode;
}

export function CardHoverPreview({ card, children }: CardHoverPreviewProps) {
  const [show, setShow] = useState(false);
  const [pos, setPos] = useState({ x: 0, y: 0 });
  const wrapperRef = useRef<HTMLDivElement>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout>>();

  const imageUrl = card.image_uri
    ? card.image_uri.replace('/normal/', '/normal/')
    : card.scryfall_id
      ? `https://cards.scryfall.io/normal/front/${card.scryfall_id[0]}/${card.scryfall_id[1]}/${card.scryfall_id}.jpg`
      : '';

  const handleMouseEnter = () => {
    timerRef.current = setTimeout(() => setShow(true), 200);
  };

  const handleMouseLeave = () => {
    clearTimeout(timerRef.current);
    setShow(false);
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    // Card image is ~250px wide, ~350px tall
    let x = e.clientX + 16;
    let y = e.clientY - 175;
    if (x + 260 > vw) x = e.clientX - 270;
    if (y < 8) y = 8;
    if (y + 360 > vh) y = vh - 360;
    setPos({ x, y });
  };

  useEffect(() => {
    return () => clearTimeout(timerRef.current);
  }, []);

  if (!imageUrl) return <>{children}</>;

  return (
    <div
      ref={wrapperRef}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      onMouseMove={handleMouseMove}
      style={{ display: 'contents' }}
    >
      {children}
      {show && (
        <div
          style={{
            position: 'fixed',
            left: pos.x,
            top: pos.y,
            zIndex: 10000,
            pointerEvents: 'none',
            filter: `drop-shadow(0 4px 12px ${tokens.colorNeutralShadowAmbient})`,
          }}
        >
          <img
            src={imageUrl}
            alt={card.name}
            style={{
              width: 250,
              borderRadius: 12,
              display: 'block',
            }}
          />
          {card.oracle_text && (
            <div
              style={{
                marginTop: 6,
                padding: '8px 10px',
                background: tokens.colorNeutralBackground1,
                borderRadius: 8,
                fontSize: 12,
                lineHeight: 1.4,
                maxWidth: 250,
                color: tokens.colorNeutralForeground1,
                whiteSpace: 'pre-wrap',
              }}
            >
              {card.oracle_text}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
