import { ReactNode } from 'react';
import { createPortal } from 'react-dom';

/**
 * Renders overlay content into `document.body` instead of where it is written.
 *
 * **Every floating overlay in this app must go through here**, and the reason is
 * a property of the design system rather than of any one component: the Sothera
 * `Panel` carries `backdrop-filter: blur(14px)`, and a filtered element becomes
 * both a containing block for `position: fixed` descendants *and* a stacking
 * context. An overlay mounted inside a panel therefore competes for z-index
 * only within that panel — and every card painted later in the document draws
 * over it, whatever number it declares.
 *
 * That is not a hypothetical. It shipped twice: the inbox sell dialog was
 * unreachable under the cards below it (0.34.1), and the price-trend popup
 * carried the identical defect until 0.42.0. `z-index: 10000` looks like the
 * fix and is not one.
 *
 * The rule, then: **no `position: fixed` inside a `Panel` without this
 * component.** Positioning still works the way the author expects, because in
 * `document.body` the coordinates are viewport coordinates — which is what the
 * `fixed` was asking for all along.
 */
export function OverlayPortal({ children }: { children: ReactNode }) {
  if (typeof document === 'undefined') return null;
  return createPortal(children, document.body);
}
