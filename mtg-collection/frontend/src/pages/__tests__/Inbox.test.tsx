import { describe, it, expect } from 'vitest';
// Import directly from the utility module to avoid pulling in api.ts (which
// references `window` at module load and breaks the Node test environment).
// getColorBucket and groupByColorBucket are re-exported from Inbox.tsx for
// convenience, but the authoritative source is utils/colors.ts.
import { getColorBucket, groupByColorBucket, BUCKET_KEYS } from '../../utils/colors';

describe('getColorBucket', () => {
  it('returns Unknown for null card', () => {
    expect(getColorBucket(null)).toBe('Unknown');
  });

  it('returns Unknown for undefined card', () => {
    expect(getColorBucket(undefined)).toBe('Unknown');
  });

  it('returns Colorless for null color_identity', () => {
    expect(getColorBucket({ color_identity: null })).toBe('Colorless');
  });

  it('returns Colorless for empty string color_identity', () => {
    expect(getColorBucket({ color_identity: '' })).toBe('Colorless');
  });

  it('returns Colorless for JSON empty array string', () => {
    expect(getColorBucket({ color_identity: '[]' })).toBe('Colorless');
  });

  it('returns W for single-letter string', () => {
    expect(getColorBucket({ color_identity: 'W' })).toBe('W');
  });

  it('returns G for single-element array', () => {
    expect(getColorBucket({ color_identity: ['G'] })).toBe('G');
  });

  it('returns Multi for CSV string WU', () => {
    expect(getColorBucket({ color_identity: 'WU' })).toBe('Multi');
  });

  it('returns Multi for multi-element array', () => {
    expect(getColorBucket({ color_identity: ['W', 'U', 'B'] })).toBe('Multi');
  });

  it('returns Multi for JSON array string', () => {
    expect(getColorBucket({ color_identity: '["W","U"]' })).toBe('Multi');
  });

  it('does not throw for numeric color_identity', () => {
    expect(() => getColorBucket({ color_identity: 42 })).not.toThrow();
  });

  it('returns Colorless for unknown single letter not in WUBRG', () => {
    expect(getColorBucket({ color_identity: 'X' })).toBe('Colorless');
  });
});

describe('groupByColorBucket', () => {
  it('does not throw and returns Map with all 8 keys for mixed/bad inputs', () => {
    const items = [
      { card: null },
      { card: { color_identity: '' } },
      { card: { color_identity: 'X' } },
    ];
    let result: Map<string, unknown[]>;
    expect(() => {
      result = groupByColorBucket(items);
    }).not.toThrow();
    for (const key of BUCKET_KEYS) {
      expect(result!.has(key)).toBe(true);
    }
  });

  it('places null-card items into Unknown bucket', () => {
    const items = [{ card: null }];
    const result = groupByColorBucket(items);
    expect(result.get('Unknown')?.length).toBe(1);
  });

  it('places W card into W bucket', () => {
    const items = [{ card: { color_identity: 'W' } }];
    const result = groupByColorBucket(items);
    expect(result.get('W')?.length).toBe(1);
  });

  it('places multi-color card into Multi bucket', () => {
    const items = [{ card: { color_identity: ['R', 'G'] } }];
    const result = groupByColorBucket(items);
    expect(result.get('Multi')?.length).toBe(1);
  });
});
