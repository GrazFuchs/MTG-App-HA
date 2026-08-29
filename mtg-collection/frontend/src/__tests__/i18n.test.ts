/**
 * Sprint 10: keeps the i18n sweep from rotting.
 *
 * The sweep moved 433 hardcoded strings into keys across three passes. Nothing
 * about that is self-maintaining — the next component someone writes will have
 * its text inline, exactly like the last forty did — so the check runs in the
 * test suite rather than as a thing to remember.
 *
 * The heavy lifting is in `scripts/i18n-lint.py`, spawned here rather than
 * reimplemented in TypeScript: it is the same command a person runs by hand
 * (`npm run lint:i18n`), so there is one implementation and one verdict.
 *
 * ⚠️ Deliberately no `@fluentui/react-components` import in this file — see
 * the header of overlays.test.tsx for what that costs.
 */
import { execFileSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

import { t, translations } from '../i18n';

const HERE = dirname(fileURLToPath(import.meta.url));
const LINT = resolve(HERE, '../../scripts/i18n-lint.py');

describe('i18n lint', () => {
  it('finds no hardcoded literals, no dead keys and no undefined keys', () => {
    expect(existsSync(LINT)).toBe(true);
    let output = '';
    let failed = false;
    for (const python of ['python', 'python3']) {
      try {
        output = execFileSync(python, [LINT], {
          encoding: 'utf-8',
          env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
        });
        failed = false;
        break;
      } catch (e: any) {
        // ENOENT means this interpreter name does not exist here; a non-zero
        // exit means the lint itself failed and its output is the finding.
        if (e?.code === 'ENOENT') continue;
        output = `${e?.stdout ?? ''}${e?.stderr ?? ''}`;
        failed = true;
        break;
      }
    }
    if (failed) throw new Error(`i18n lint failed:\n${output}`);
    expect(output).toContain('literals: 0');
  }, 60_000);
});

describe('both languages', () => {
  // The sprint asked for a "language smoke: de + en rendering of a screen".
  // Rendering a screen twice would need the module reloaded with a different
  // detected language — `currentLang` is resolved once at import — and would
  // pull Fluent in for the sake of proving something the dictionary already
  // decides. What actually breaks is a key present in one language and not the
  // other, or an empty value: both show up as a raw key or a blank on screen.
  const dict = translations as Record<string, Record<string, string>>;

  it('defines exactly the same keys in en and de', () => {
    expect(Object.keys(dict.en).sort()).toEqual(Object.keys(dict.de).sort());
  });

  it('has no empty translation in either language', () => {
    for (const lang of ['en', 'de']) {
      const blank = Object.entries(dict[lang]).filter(([, v]) => !v.trim());
      expect(`${lang}: ${blank.map(([k]) => k).join(', ')}`).toBe(`${lang}: `);
    }
  });

  it('keeps the same placeholders on both sides', () => {
    // A dropped {count} renders a sentence with a hole in it; an invented one
    // renders literal braces. Neither throws.
    const holes = (v: string) => (v.match(/\{[a-z_]+\}/g) ?? []).sort().join(',');
    const drift = Object.keys(dict.en).filter(k => holes(dict.en[k]) !== holes(dict.de[k]));
    expect(drift).toEqual([]);
  });
});

describe('t()', () => {
  it('substitutes every parameter it is given', () => {
    // The failure this guards against is silent: an unreplaced {count} renders
    // as the literal braces on the page, and nothing throws.
    const s = t('inbox.bulk.select_all_n', { count: 7 });
    expect(s).toContain('7');
    expect(s).not.toContain('{');
  });

  it('falls back to the key when one does not exist, rather than throwing', () => {
    // This is the behaviour the lint's "called but never defined" check exists
    // for: a missing key is invisible at runtime, so it has to be caught here.
    expect(t('no.such.key.exists')).toBe('no.such.key.exists');
  });
});
