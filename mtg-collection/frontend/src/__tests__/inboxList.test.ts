/**
 * Sprint 08's third render-behaviour test, deferred from Sprint 09 and landed
 * here: what happens to the loaded list when a card is decided.
 *
 * Sprint 09 shipped tests for two of the three classes it named (overlay
 * stacking, visible failure) and left this one open because it "needs a mocked
 * API layer". It turned out not to: the behaviour worth pinning is a pure
 * transform of the cached page, and once it was extracted from the component
 * there was nothing to mock. That extraction is `pages/inboxList.ts`.
 *
 * To be exact about what these do and do not prove: the *counting* rules below
 * came in with 0.43.0, so they pin current behaviour rather than catching an
 * older bug. What they guard is the next change — the obvious "simplification"
 * of subtracting `ids.length` is wrong, and nothing on screen would say so.
 * The invalidate-versus-patch decision itself lives in the component and is not
 * covered here.
 *
 * ⚠️ Deliberately no `@fluentui/react-components` import — see overlays.test.tsx.
 */
import { describe, expect, it } from 'vitest';

import { dropDecided, type InboxPage } from '../pages/inboxList';
import type { AcquisitionEvent } from '../api';

const ev = (id: number) => ({ id } as AcquisitionEvent);
const page = (ids: number[], total: number): InboxPage => ({ items: ids.map(ev), total });

describe('dropDecided', () => {
  it('removes the decided cards and leaves the rest in place', () => {
    // The point is the *order and identity* of what stays: a refetch would
    // rebuild this list, re-collapse the colour groups and lose the scroll.
    const next = dropDecided(page([1, 2, 3, 4], 4), [2, 4])!;
    expect(next.items.map(e => e.id)).toEqual([1, 3]);
    expect(next.total).toBe(2);
  });

  it('counts only the ids that were on this page', () => {
    // A bulk decision can span a page boundary. Subtracting ids.length blindly
    // walks the counter below the real number of pending cards, and nothing
    // ever corrects it because the next page load overwrites a wrong total
    // with a right one only if you happen to reload.
    const next = dropDecided(page([1, 2], 137), [1, 2, 900, 901])!;
    expect(next.items).toHaveLength(0);
    expect(next.total).toBe(135);
  });

  it('never drives the total below zero', () => {
    const next = dropDecided(page([1], 0), [1])!;
    expect(next.total).toBe(0);
  });

  it('ignores unknown ids instead of failing', () => {
    // The undo bar can replay ids a refetch has already removed. That race is
    // harmless and must not surface as an error.
    const next = dropDecided(page([1, 2], 2), [99])!;
    expect(next.items.map(e => e.id)).toEqual([1, 2]);
    expect(next.total).toBe(2);
  });

  it('passes an empty cache through untouched', () => {
    expect(dropDecided(undefined, [1])).toBeUndefined();
  });
});
