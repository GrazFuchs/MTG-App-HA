export type ColorBucket = 'W' | 'U' | 'B' | 'R' | 'G' | 'M' | 'C' | 'L';

export function getColorBucket(card: { color_identity: string[] | null | undefined; type_line: string }): ColorBucket {
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
