/**
 * Render MTG mana symbols using Scryfall's SVG API.
 * Converts mana cost strings like "{2}{W}{U}" into inline SVG images.
 */

const SYMBOL_BASE = 'https://svgs.scryfall.io/card-symbols';

/** Map a single mana symbol token (without braces) to its SVG filename */
function symbolUrl(sym: string): string {
  // Scryfall uses uppercase, slash for hybrid: {W/U} → WU.svg
  const cleaned = sym.toUpperCase().replace(/\//g, '');
  return `${SYMBOL_BASE}/${cleaned}.svg`;
}

/** Render a single mana symbol by its letter (e.g. "W", "U", "2") */
export function ManaSymbol({ symbol, size = 16 }: { symbol: string; size?: number }) {
  return (
    <img
      src={symbolUrl(symbol)}
      alt={`{${symbol}}`}
      title={`{${symbol}}`}
      width={size}
      height={size}
      style={{ display: 'inline-block', verticalAlign: 'middle' }}
      onError={e => {
        // Fallback to a text badge if the SVG fails to load
        const el = e.currentTarget;
        el.style.display = 'none';
        const span = document.createElement('span');
        span.textContent = `{${symbol}}`;
        span.style.cssText = 'font-size:11px;font-family:monospace;opacity:0.7';
        el.parentElement?.insertBefore(span, el.nextSibling);
      }}
    />
  );
}

/** Parse "{2}{W}{U}" → ["2", "W", "U"] */
function parseManaCost(cost: string): string[] {
  const matches = cost.match(/\{([^}]+)\}/g);
  if (!matches) return [];
  return matches.map(m => m.slice(1, -1));
}

interface ManaCostProps {
  cost: string;
  size?: number;
}

export function ManaCost({ cost, size = 16 }: ManaCostProps) {
  if (!cost) return null;
  const symbols = parseManaCost(cost);
  return (
    <span style={{ display: 'inline-flex', gap: 1, alignItems: 'center', verticalAlign: 'middle' }}>
      {symbols.map((sym, i) => (
        <img
          key={i}
          src={symbolUrl(sym)}
          alt={`{${sym}}`}
          title={`{${sym}}`}
          width={size}
          height={size}
          style={{ display: 'inline-block' }}
        />
      ))}
    </span>
  );
}

interface ManaTextProps {
  text: string;
  size?: number;
}

/** Render oracle text with inline mana symbols */
export function ManaText({ text, size = 14 }: ManaTextProps) {
  if (!text) return null;
  // Split on {X} tokens, keeping them
  const parts = text.split(/(\{[^}]+\})/g);
  return (
    <span>
      {parts.map((part, i) => {
        const match = part.match(/^\{([^}]+)\}$/);
        if (match) {
          return (
            <img
              key={i}
              src={symbolUrl(match[1])}
              alt={part}
              width={size}
              height={size}
              style={{ display: 'inline-block', verticalAlign: 'text-bottom', margin: '0 1px' }}
            />
          );
        }
        return <span key={i}>{part}</span>;
      })}
    </span>
  );
}
