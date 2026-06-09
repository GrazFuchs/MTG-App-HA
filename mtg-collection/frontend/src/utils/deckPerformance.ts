import type { DeckGame, GameResult } from '../api';

const RESULT_SYMBOL: Record<GameResult, string> = { win: 'W', loss: 'L', draw: 'D' };

/**
 * Compact recent-form string from the most-recent N games.
 * Games are expected newest-first (as returned by the API).
 */
export function recentForm(games: Pick<DeckGame, 'result'>[], n = 5): string {
  return games.slice(0, n).map(g => RESULT_SYMBOL[g.result] ?? '?').join('-');
}

/** Tone bucket for a win-rate percentage, for colouring. */
export function winRateTone(rate: number): 'good' | 'mid' | 'bad' {
  if (rate >= 55) return 'good';
  if (rate >= 40) return 'mid';
  return 'bad';
}
