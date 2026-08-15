export type ColorBucket = 'W' | 'U' | 'B' | 'R' | 'G' | 'M' | 'C' | 'L';

/** Bucket keys used by the Inbox triage view — superset of ColorBucket. */
export type BucketKey = 'W' | 'U' | 'B' | 'R' | 'G' | 'Multi' | 'Colorless' | 'Unknown';

export const BUCKET_KEYS: BucketKey[] = ['W', 'U', 'B', 'R', 'G', 'Multi', 'Colorless', 'Unknown'];

/**
 * Every spelling of a colour the API has been seen to send, mapped to its
 * letter. Archidekt reports colours by name ("Green") where Scryfall reports
 * letters ("G"); the backend now normalises on write, but a browser holding a
 * cached response from before that must not fall back to filing every card
 * under Colorless — which is exactly what this classifier used to do.
 */
const COLOR_NAME_TO_LETTER: Record<string, string> = {
  W: 'W', WHITE: 'W',
  U: 'U', BLUE: 'U',
  B: 'B', BLACK: 'B',
  R: 'R', RED: 'R',
  G: 'G', GREEN: 'G',
};

/** Map one raw colour token to its WUBRG letter, or null if unrecognised. */
function toLetter(token: string): string | null {
  return COLOR_NAME_TO_LETTER[token.trim().toUpperCase()] ?? null;
}

/**
 * Robust color-bucket classifier for the Inbox page.
 * Handles: null/undefined card, null/undefined/empty/JSON-string/CSV-string
 * color_identity, full colour names, plain string[], or any other garbage —
 * never throws.
 */
export function getColorBucket(card: unknown): BucketKey {
  if (card == null || typeof card !== 'object') return 'Unknown';
  const ci = (card as Record<string, unknown>).color_identity;

  let colors: string[];
  if (Array.isArray(ci)) {
    colors = ci.map(String);
  } else if (typeof ci === 'string') {
    const trimmed = ci.trim();
    if (trimmed === '' || trimmed === '[]') {
      colors = [];
    } else if (trimmed.startsWith('[')) {
      try {
        const parsed = JSON.parse(trimmed);
        colors = Array.isArray(parsed) ? parsed.map(String) : [];
      } catch {
        colors = [];
      }
    } else if (/^[WUBRG]+$/.test(trimmed)) {
      // Concatenated color letters with no delimiter: 'W', 'WU', 'WUBRG'
      colors = trimmed.split('');
    } else {
      // Comma- or space-separated: 'W,U' or 'W U'
      colors = trimmed.split(/[,\s]+/).filter(Boolean);
    }
  } else {
    colors = [];
  }

  const letters = new Set(
    colors.map(toLetter).filter((c): c is string => c !== null)
  );
  if (letters.size === 0) return 'Colorless';
  if (letters.size === 1) return [...letters][0] as BucketKey;
  return 'Multi';
}

/**
 * Groups items by color bucket. Pre-initialises ALL BucketKey slots so
 * .get() never returns undefined.
 */
export function groupByColorBucket<T extends { card: unknown }>(items: T[]): Map<BucketKey, T[]> {
  const buckets = new Map<BucketKey, T[]>(BUCKET_KEYS.map(k => [k, []]));
  for (const item of items) {
    const key = getColorBucket(item.card);
    if (!buckets.has(key)) {
      console.warn('[groupByColorBucket] unexpected bucket key:', key);
      buckets.set(key, []);
    }
    buckets.get(key)!.push(item);
  }
  return buckets;
}

export function getColorBucketLegacy(card: { color_identity: string[] | null | undefined; type_line: string }): ColorBucket {
  if (card.type_line && card.type_line.includes('Land')) return 'L';
  const ci = card.color_identity || [];
  if (ci.length === 0) return 'C';
  if (ci.length >= 2) return 'M';
  return ci[0] as ColorBucket;
}

export const BUCKET_ORDER: ColorBucket[] = ['W', 'U', 'B', 'R', 'G', 'M', 'C', 'L'];

export const BUCKET_LABELS: Record<ColorBucket, string> = {
  W: 'White', U: 'Blue', B: 'Black', R: 'Red', G: 'Green',
  M: 'Multicolor', C: 'Colorless', L: 'Land',
};

export const BUCKET_EMOJI: Record<ColorBucket, string> = {
  W: '⚪', U: '🔵', B: '⚫', R: '🔴', G: '🟢',
  M: '🌈', C: '◆', L: '🟤',
};
