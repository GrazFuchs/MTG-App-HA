#!/usr/bin/env python3
"""
i18n lint. Run by `npm run lint:i18n`, and by the test suite via
`src/__tests__/i18n.test.ts`, so the Sprint-10 sweep cannot silently rot.

It answers three questions:

  1. Is any user-facing string still hardcoded in a component?
  2. Is any key defined but unreachable?
  3. Do `en` and `de` define the same keys?

**On (2): a key counts as used if it appears as a quoted string anywhere in
`src`, not only inside a `t(...)` call.** Half this app's dropdowns store the
key in the option (`{ value: 'color', label: 'inbox.sort_color' }`) and
translate at the render site with `t(o.label)`. A checker that only looks for
`t('…')` reports every one of those as dead — which is exactly what happened
while writing this, and would have led to deleting keys that are in daily use.

The ALLOW list is for text that must not be translated: brand names, operating
system names, and the like. Keep it short and say why.
"""
from __future__ import annotations

import io
import os
import re
import sys

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src')

# JSX text nodes and the props that end up on screen.
JSX_TEXT = re.compile(r'>\s*([A-Za-zÄÖÜäöüß][^<>{}\n]{2,})\s*<')
PROPS = re.compile(
    r'\b(?:label|title|placeholder|aria-label|content|header|description)\s*=\s*'
    r'["\']([^"\'{}]{3,})["\']')

# Comments are stripped before scanning. Prose in a JSDoc block trips every
# pattern here — `<button> now (see SortHeader): the sort controls were <div
# onClick>` reads exactly like JSX text — and an allow-list entry per comment
# would grow forever and go stale the moment someone rewords one.
COMMENTS = re.compile(r'/\*.*?\*/|(?<![:\w])//[^\n]*', re.S)

# Text that stays as it is. Every entry is a name, not a sentence.
ALLOW = {
    'MTG',                      # brand
    'Archidekt ↗', 'EDHREC ↗',  # site names
    'macOS:', 'Windows:', 'Linux:',  # OS names in the MCP wizard
    'Cardmarket', 'Claude Desktop', 'Home Assistant', 'Scryfall',
    'Promise',                  # `=> Promise<void>` in a type, not JSX text
}

# Dotted strings that look like keys but are not: localStorage names and a
# filename. Without this the key-shaped-string check reports them every run,
# and a check that always complains is one nobody reads.
NOT_KEYS = {'deck.combosExpanded', 'inbox.openColors', 'wishlist.json'}

# Nothing is exempt any more — stripping comments removed the only reason
# a file was ever on this list.
SKIP_FILES: set[str] = set()


def defined_keys(text: str, lang: str) -> set[str]:
    start = text.index('  %s: {' % lang)
    end = text.index('\n  },', start)
    return set(re.findall(r"^\s*'([^']+)':", text[start:end], re.M))


def main() -> int:
    i18n = io.open(os.path.join(SRC, 'i18n.ts'), encoding='utf-8').read()
    en, de = defined_keys(i18n, 'en'), defined_keys(i18n, 'de')

    literals: list[str] = []
    corpus: list[str] = []
    for root, dirs, files in os.walk(SRC):
        dirs[:] = [d for d in dirs if d != '__tests__']
        for f in sorted(files):
            if not f.endswith(('.ts', '.tsx')):
                continue
            path = os.path.join(root, f)
            rel = os.path.relpath(path, os.path.dirname(SRC)).replace('\\', '/')
            text = io.open(path, encoding='utf-8').read()
            if rel != 'src/i18n.ts':
                corpus.append(text)
            if not f.endswith('.tsx') or rel in SKIP_FILES:
                continue
            text = COMMENTS.sub('', text)
            for m in JSX_TEXT.finditer(text):
                v = m.group(1).strip()
                if v and v not in ALLOW and any(c.isalpha() for c in v):
                    literals.append('%s: %s' % (rel, v))
            for m in PROPS.finditer(text):
                v = m.group(1)
                if v not in ALLOW:
                    literals.append('%s: %s= %s' % (rel, 'prop', v))

    blob = '\n'.join(corpus)
    used = {k for k in (en | de) if ("'%s'" % k) in blob or ('"%s"' % k) in blob}
    dead = sorted((en | de) - used)

    # Keys the code calls that nobody defined. This is the check that matters
    # most: a missing definition does not throw — t() falls back to printing the
    # key itself, so the page shows `inbox.sort_set` where a word belongs. That
    # exact key slipped in during the sweep and this check is what found it.
    # Both spellings count: the direct `t('inbox.title')` and the indirect
    # `label: 'inbox.sort_set'` that a render site later feeds to `t()`. The
    # second is what this codebase does for every dropdown, and leaving it out
    # is why the first version of this check found nothing while the sort menu
    # was quietly printing `inbox.sort_set` on screen.
    called = set(re.findall(r"\bt\(\s*'([^']+)'", blob))
    called |= {m for m in re.findall(r"'([a-z][a-z0-9_]*(?:\.[A-Za-z0-9_]+)+)'", blob)
               if m.split('.')[0] in {k.split('.')[0] for k in (en | de)}}
    undefined = sorted(called - (en | de) - NOT_KEYS)

    problems = 0
    if undefined:
        problems += 1
        print('%d keys called but never defined (these render as raw keys):' % len(undefined))
        for k in undefined:
            print('  ' + k)
    if literals:
        problems += 1
        print('%d hardcoded literals:' % len(literals))
        for line in literals:
            print('  ' + line)
    if dead:
        problems += 1
        print('%d unreachable keys:' % len(dead))
        for k in dead:
            print('  ' + k)
    if en != de:
        problems += 1
        print('en/de out of sync — only in en: %s / only in de: %s'
              % (sorted(en - de), sorted(de - en)))

    print('\nkeys: %d  used: %d  literals: %d' % (len(en), len(used), len(literals)))
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
