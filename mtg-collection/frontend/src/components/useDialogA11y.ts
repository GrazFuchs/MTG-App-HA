import { useEffect, useRef } from 'react';

/**
 * The three things a hand-built modal has to do that a `<div>` does not.
 *
 * Fluent's `<Dialog>` already does all of this, and most dialogs in the app use
 * it. Two do not — they are portalled overlays built by hand because they need
 * to escape a `backdrop-filter` stacking context — and those two had none of it:
 * Escape did nothing, Tab walked out of the dialog and into the page behind it,
 * and closing left focus on whatever the portal had detached.
 *
 *   1. **Escape closes.** On a phone the backdrop tap is the only other way out,
 *      and with a keyboard there was none at all.
 *   2. **Tab stays inside.** A modal that leaks focus to the page underneath is
 *      worse than no modal: the user is typing into a form they cannot see.
 *   3. **Focus comes back.** On close, focus returns to whatever opened the
 *      dialog, so the next Tab continues where the user was.
 *
 * Returns a ref to put on the dialog element.
 */
export function useDialogA11y(open: boolean, onClose: () => void) {
  const ref = useRef<HTMLDivElement>(null);
  const restoreTo = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open) return;
    restoreTo.current = document.activeElement as HTMLElement | null;

    const focusable = () => Array.from(
      ref.current?.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), '
        + 'textarea:not([disabled]), [tabindex]:not([tabindex="-1"])') ?? [],
    ).filter(el => el.offsetParent !== null || el === document.activeElement);

    // Move focus in, so the first Tab lands inside rather than back on the page.
    focusable()[0]?.focus();

    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation();
        onClose();
        return;
      }
      if (e.key !== 'Tab') return;
      const items = focusable();
      if (items.length === 0) return;
      const first = items[0];
      const last = items[items.length - 1];
      const active = document.activeElement;
      // Wrap at both ends. Without this the browser walks on to the page behind.
      if (e.shiftKey && (active === first || !ref.current?.contains(active))) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && active === last) {
        e.preventDefault();
        first.focus();
      }
    };

    document.addEventListener('keydown', onKey, true);
    return () => {
      document.removeEventListener('keydown', onKey, true);
      restoreTo.current?.focus?.();
    };
  }, [open, onClose]);

  return ref;
}
