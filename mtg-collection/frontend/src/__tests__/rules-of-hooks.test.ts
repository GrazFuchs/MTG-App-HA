/**
 * Der eine Fehler, den TypeScript nicht sieht: ein Hook hinter einem fruehen
 * Return.
 *
 * `DeckCombosSection` hatte ab 0.46.0 drei `useState` unterhalb von
 * `if (loading) return <Spinner />`. Der erste Render (waehrend geladen wird)
 * ruft sie nicht auf, der zweite schon — React bricht das mit
 * "Rendered more hooks than during the previous render" ab (minified #310),
 * und die Deck-Seite rendert gar nicht mehr. `tsc` ist dabei gruen, die
 * bestehenden Tests auch: das Bauteil wurde von keinem gerendert.
 *
 * Das Werkzeug dafuer waere `eslint-plugin-react-hooks`. Solange hier kein
 * ESLint laeuft, macht dieser Test die billige Haelfte davon — er liest die
 * Dateien, statt sie zu rendern, und kostet deshalb Millisekunden statt der
 * Minuten, die ein Fluent-Import kostet (siehe die Warnung in overlays.test).
 *
 * Bewusste Grenze: geprueft wird nur die Einrueckungsebene der Komponente
 * selbst (zwei Leerzeichen). Ein Hook in einem `if`-Block waere tiefer
 * eingerueckt und rutscht durch — das ist der seltenere Fall, und ein Scanner,
 * der Fehlalarme produziert, wird abgeschaltet statt repariert.
 */
import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

const SRC = join(__dirname, '..');

/** Beginn einer neuen Top-Level-Deklaration — setzt die Suche zurueck. */
const TOP = /^(export\s+)?(default\s+)?(async\s+)?(function|const|class)\b/;
/** Ein `return` auf Komponentenebene, mit oder ohne vorangestelltes `if`. */
const RETURN = /^ {2}(if \(.*\)\s*)?return[\s;<(]/;
/** Ein Hook-Aufruf auf Komponentenebene, inkl. `useState<T>(…)`. */
const HOOK = /^ {2}(const\s+.*?=\s*)?use[A-Z]\w*(<[^;()]*>)?\(/;

function sourceFiles(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name !== '__tests__' && entry.name !== 'node_modules') out.push(...sourceFiles(full));
    } else if (entry.name.endsWith('.tsx') || entry.name.endsWith('.ts')) {
      out.push(full);
    }
  }
  return out;
}

describe('rules of hooks', () => {
  it('ruft keinen Hook unterhalb eines fruehen Returns auf', () => {
    const findings: string[] = [];

    for (const file of sourceFiles(SRC)) {
      const rel = file.slice(SRC.length + 1).replace(/\\/g, '/');
      let returnedAt: number | null = null;

      readFileSync(file, 'utf-8').split('\n').forEach((line, idx) => {
        if (TOP.test(line)) {
          returnedAt = null;
        } else if (RETURN.test(line)) {
          returnedAt ??= idx + 1;
        } else if (returnedAt !== null && HOOK.test(line)) {
          findings.push(`${rel}:${idx + 1} — Hook nach dem return in Zeile ${returnedAt}: ${line.trim()}`);
        }
      });
    }

    expect(findings).toEqual([]);
  });
});
