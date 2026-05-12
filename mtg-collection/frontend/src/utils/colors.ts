export type ColorBucket = 'W' | 'U' | 'B' | 'R' | 'G' | 'M' | 'C' | 'L';

/** Bucket keys used by the Inbox triage view — superset of ColorBucket. */
export type BucketKey = 'W' | 'U' | 'B' | 'R' | 'G' | 'Multi' | 'Colorless' | 'Unknown';

export const BUCKET_KEYS: BucketKey[] = ['W', 'U', 'B', 'R', 'G', 'Multi', 'Colorless', 'Unknown'];

const WUBRG = new Set(['W', 'U', 'B', 'R', 'G']);

/**
 * Robust color-bucket classifier for the Inbox page.
 * Handles: null/undefined card, null/undefined/empty/JSON-string/CSV-string
 * color_identity, plain string[], or any other garbage — never throws.
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

  const filtered = colors.filter(c => WUBRG.has(c));
  if (filtered.length === 0) return 'Colorless';
  if (filtered.length === 1) return filtered[0] as BucketKey;
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
