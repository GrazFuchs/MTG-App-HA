import { describe, expect, it } from 'vitest';
import { recentForm, winRateTone } from '../deckPerformance';

describe('recentForm', () => {
  it('returns empty string for no games', () => {
    expect(recentForm([])).toBe('');
  });

  it('maps results to W/L/D newest-first', () => {
    expect(recentForm([{ result: 'win' }, { result: 'loss' }, { result: 'draw' }])).toBe('W-L-D');
  });

  it('limits to the most recent N games', () => {
    const games = [
      { result: 'win' as const }, { result: 'win' as const }, { result: 'loss' as const },
      { result: 'draw' as const }, { result: 'win' as const }, { result: 'loss' as const },
    ];
    expect(recentForm(games, 3)).toBe('W-W-L');
  });
});

describe('winRateTone', () => {
  it('classifies high win rates as good', () => {
    expect(winRateTone(60)).toBe('good');
    expect(winRateTone(55)).toBe('good');
  });
  it('classifies mid win rates', () => {
    expect(winRateTone(50)).toBe('mid');
    expect(winRateTone(40)).toBe('mid');
  });
  it('classifies low win rates as bad', () => {
    expect(winRateTone(39)).toBe('bad');
    expect(winRateTone(0)).toBe('bad');
  });
});
