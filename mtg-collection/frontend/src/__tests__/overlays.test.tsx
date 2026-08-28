/**
 * Sprint 09: the first component tests this project has had.
 *
 * The release history is a series of display bugs — an unreachable sell dialog
 * (0.34.1), a hover popup drawn over (0.22.0), duplicated listing rows
 * (0.17.3) — and the reason they kept shipping is written in the old test
 * setup: it ran under `environment: 'node'`, so nothing was ever rendered.
 * These are the minimum that would have caught the class.
 *
 * ⚠️ Deliberately no `@fluentui/react-components` import anywhere in this file.
 * Pulling the component library into a test costs minutes of transform time on
 * the first run, and none of the behaviour under test needs it: what is being
 * checked is *where* a node ends up in the DOM and *whether* a failure becomes
 * visible, not how a button looks.
 */
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { ErrorBoundary } from '../components/ErrorBoundary';
import { OverlayPortal } from '../components/OverlayPortal';

describe('OverlayPortal', () => {
  it('escapes the panel it is written inside', () => {
    // The Sothera Panel's backdrop-filter makes it a containing block for
    // fixed-position descendants *and* a stacking context, so an overlay left
    // inside it competes for z-index only within that panel — and every card
    // painted later draws over it. That is the 0.34.1 bug, and it was still
    // present in the price-trend popup until this sprint.
    const { container } = render(
      <div data-testid="panel" style={{ backdropFilter: 'blur(14px)' }}>
        <OverlayPortal>
          <div data-testid="overlay">Confirm</div>
        </OverlayPortal>
      </div>,
    );

    const overlay = screen.getByTestId('overlay');
    expect(overlay).toBeInTheDocument();
    expect(container.querySelector('[data-testid="overlay"]')).toBeNull();
    expect(overlay.closest('[data-testid="panel"]')).toBeNull();
    expect(document.body.contains(overlay)).toBe(true);
  });

  it('keeps the trigger where it was written', () => {
    // Only the overlay moves. If the trigger travelled too, hover and click
    // handlers would fire from the wrong place in the tree.
    const { container } = render(
      <div data-testid="panel">
        <span data-testid="trigger">Sol Ring</span>
        <OverlayPortal>
          <div data-testid="overlay">trend</div>
        </OverlayPortal>
      </div>,
    );

    expect(container.querySelector('[data-testid="trigger"]')).not.toBeNull();
  });
});

function Boom(): JSX.Element {
  throw new Error('the backend said no');
}

describe('ErrorBoundary around a page', () => {
  it('shows the failure instead of an empty page', () => {
    // "Nothing rendered" and "there is nothing to show" look identical to a
    // reader — which is how a dead /api/stats came to display €0.00 under a
    // green SYNCED badge.
    render(
      <ErrorBoundary fallback={(err) => <div role="alert">Failed: {err.message}</div>}>
        <Boom />
      </ErrorBoundary>,
    );

    expect(screen.getByRole('alert')).toHaveTextContent('the backend said no');
  });

  it('leaves a healthy page alone', () => {
    render(
      <ErrorBoundary fallback={() => <div>should not appear</div>}>
        <div>the real content</div>
      </ErrorBoundary>,
    );

    expect(screen.getByText('the real content')).toBeInTheDocument();
    expect(screen.queryByText('should not appear')).toBeNull();
  });
});
