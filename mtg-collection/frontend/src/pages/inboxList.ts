import type { AcquisitionEvent } from '../api';

export interface InboxPage {
  items: AcquisitionEvent[];
  total: number;
}

/**
 * Remove decided cards from the loaded page.
 *
 * Extracted from the component so it can be tested at all. The behaviour it
 * encodes is the Sprint-08 fix: deciding used to invalidate the whole
 * `inbox-pending` query, so the list reloaded, the colour groups re-collapsed
 * and the scroll position was lost after *every single decision*. With 137
 * cards in one bucket that is the difference between triaging a backlog and
 * repeatedly finding your place in it.
 *
 * Two details that are easy to get wrong and are what the tests pin down:
 *
 *   * `total` must drop only by the ids that were actually on this page.
 *     Subtracting `ids.length` blindly makes the counter drift below the real
 *     figure as soon as a bulk decision spans a page boundary.
 *   * An unknown id is not an error. The undo bar can replay ids that a
 *     refetch has already removed, and throwing there would turn a harmless
 *     race into a visible failure.
 */
export function dropDecided(page: InboxPage | undefined, ids: number[]): InboxPage | undefined {
  if (!page) return page;
  const gone = new Set(ids);
  const removed = page.items.filter(e => gone.has(e.id)).length;
  return {
    ...page,
    items: page.items.filter(e => !gone.has(e.id)),
    total: Math.max(0, page.total - removed),
  };
}
