#!/usr/bin/env python3
"""
Third pass of the Sprint-10 i18n sweep: prose inside template literals.

Passes 1 and 2 moved 407 literals. This is the last shape left, and the one no
regex over quoted strings can see, because the text is interleaved with the
value it describes:

    title={`Show ${card.name} in the collection`}
    {` · ${g.missed_land_drops} missed lands`}

Every one becomes a parameterised key, which is what `t(key, params)` was for
all along. Where the sentence puts the value in a different place in German —
"Bracket 3, aus der Deckliste berechnet" — the parameter carries it, so the word
order is the translator's to choose rather than the code's.
"""
from __future__ import annotations

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

NEW_KEYS: dict[str, tuple[str, str]] = {
    'cards.used_in': ('Used in: {decks}', 'Verwendet in: {decks}'),
    'price.trend_days': ('{days}-day trend', '{days}-Tage-Trend'),
    'perf.missed_lands_n': (' · {count} missed lands', ' · {count} fehlende Länder'),
    'bracket.source_user': ('set by you', 'von dir gesetzt'),
    'bracket.source_computed': ('computed from the decklist', 'aus der Deckliste berechnet'),
    'bracket.source_archidekt': ('imported from Archidekt', 'von Archidekt übernommen'),
    'bracket.source_none': ('not set', 'nicht gesetzt'),
    'bracket.badge_title': ('Bracket {bracket} — {source}. Click to set your own.',
                            'Bracket {bracket} — {source}. Klicken, um ein eigenes zu setzen.'),
    'bracket.computed_title': ('Bracket {bracket}, computed from the decklist',
                               'Bracket {bracket}, aus der Deckliste berechnet'),
    'inbox.history.listed_at': (' · Listed at €{price}', ' · Gelistet für €{price}'),
    'wishlist.market_short': ('Market: €{price}', 'Markt: €{price}'),
    'wishlist.no_target_inline': ('no target', 'kein Ziel'),
    'wishlist.completes_combo': ('Completes a combo in {deck}', 'Vervollständigt eine Combo in {deck}'),
    'wishlist.any_short': ('Any', 'Beliebig'),
    'dashboard.show_in_collection': ('Show {name} in the collection', '{name} in der Sammlung zeigen'),
    'power.badge_title': ('Power score {score} of 1000 (level {level}) — demand times curve efficiency, not what the deck can do',
                          'Power-Score {score} von 1000 (Level {level}) — Nachfrage mal Kurveneffizienz, nicht was das Deck kann'),
    'duplicates.extras_tooltip': ('Total extras: {extras}', 'Überschuss gesamt: {extras}'),
    'duplicates.already_listed': (', {count} already listed', ', {count} bereits gelistet'),
    'settings.restore_failed': ('Restore failed: {error}', 'Wiederherstellung fehlgeschlagen: {error}'),
    'settings.unknown_error': ('Unknown error', 'Unbekannter Fehler'),
    'time.minutes_ago': ('{n}m ago', 'vor {n} Min.'),
    'time.hours_ago': ('{n}h ago', 'vor {n} Std.'),
    'time.days_ago': ('{n}d ago', 'vor {n} Tg.'),
}

E: list[tuple[str, str, str, int]] = []


def add(path: str, pairs: list[tuple[str, str, int]]) -> None:
    for old, new, n in pairs:
        E.append((path, old, new, n))


add('src/components/OwnedBadge.tsx', [
    ("`Used in: ${inDecks.join(', ')}`", "t('cards.used_in', { decks: inDecks.join(', ') })", 1),
])
add('src/components/PriceTrendHover.tsx', [
    ("`${days}-day trend`", "t('price.trend_days', { days })", 1),
])
add('src/components/deck/DeckPerformanceSection.tsx', [
    ("` · ${g.missed_land_drops} missed lands`",
     "t('perf.missed_lands_n', { count: g.missed_land_drops })", 1),
])
add('src/components/deck/UserBracketBadge.tsx', [
    ("if (deck.user_bracket) return 'set by you';",
     "if (deck.user_bracket) return t('bracket.source_user');", 1),
    ("if (deck.computed_bracket) return 'computed from the decklist';",
     "if (deck.computed_bracket) return t('bracket.source_computed');", 1),
    ("if (deck.bracket) return 'imported from Archidekt';",
     "if (deck.bracket) return t('bracket.source_archidekt');", 1),
    ("  return 'not set';", "  return t('bracket.source_none');", 1),
    ("{`Bracket ${effective ?? '—'} — ${sourceLabel(deck)}. Click to set your own.`}",
     "{t('bracket.badge_title', { bracket: effective ?? '—', source: sourceLabel(deck) })}", 1),
])
add('src/components/inbox/InboxHistory.tsx', [
    ("` · Listed at €${snap.listing_price_eur.toFixed(2)}`",
     "t('inbox.history.listed_at', { price: snap.listing_price_eur.toFixed(2) })", 1),
])
add('src/components/wishlist/WishlistItemRow.tsx', [
    ("<div>Market: €{current.toFixed(2)}</div>",
     "<div>{t('wishlist.market_short', { price: current.toFixed(2) })}</div>", 1),
    ("`€${target.toFixed(2)}` : 'no target'",
     "`€${target.toFixed(2)}` : t('wishlist.no_target_inline')", 1),
    ("{`Completes a combo in ${item.completes_combo_in[0]}`}",
     "{t('wishlist.completes_combo', { deck: item.completes_combo_in[0] })}", 1),
])
add('src/components/wishlist/WishlistAcquireDialog.tsx', [
    ("selectedSetCode?.toUpperCase() || 'Any'}", "selectedSetCode?.toUpperCase() || t('wishlist.any_short')}", 1),
])
add('src/components/wishlist/WishlistOrderDialog.tsx', [
    ("selectedSetCode?.toUpperCase() || 'Any'}", "selectedSetCode?.toUpperCase() || t('wishlist.any_short')}", 1),
])
add('src/components/wishlist/WishlistEditDialog.tsx', [
    ("selectedSetCode?.toUpperCase() || 'Any printing'}",
     "selectedSetCode?.toUpperCase() || t('common.any_printing')}", 1),
])
add('src/pages/Dashboard.tsx', [
    ("`Show ${a.card_name} in the collection`", "t('dashboard.show_in_collection', { name: a.card_name })", 1),
    ("`Show ${m.card_name} in the collection`", "t('dashboard.show_in_collection', { name: m.card_name })", 1),
    ("`Show ${b.card_name} in the collection`", "t('dashboard.show_in_collection', { name: b.card_name })", 1),
    ("`Show ${s.card_name} in the collection`", "t('dashboard.show_in_collection', { name: s.card_name })", 1),
])
add('src/pages/Decks.tsx', [
    ("`Bracket ${d.effective_bracket}, computed from the decklist`",
     "t('bracket.computed_title', { bracket: d.effective_bracket })", 1),
    ("`Power score ${Math.round(d.power_score)} of 1000 (level ${d.power_level?.toFixed(1)}) — demand times curve efficiency, not what the deck can do`",
     "t('power.badge_title', { score: Math.round(d.power_score), level: d.power_level?.toFixed(1) ?? '—' })", 1),
])
add('src/pages/Duplicates.tsx', [
    ("`Total extras: ${item.extras}${item.listed_quantity > 0 ? `, ${item.listed_quantity} already listed` : ''}`",
     "t('duplicates.extras_tooltip', { extras: item.extras })"
     " + (item.listed_quantity > 0 ? t('duplicates.already_listed', { count: item.listed_quantity }) : '')", 1),
])
add('src/pages/Settings.tsx', [
    ("`Restore failed: ${data.error || 'Unknown error'}`",
     "t('settings.restore_failed', { error: data.error || t('settings.unknown_error') })", 1),
])
add('src/components/deck/AIAssessmentBox.tsx', [
    ("return `${mins}m ago`;", "return t('time.minutes_ago', { n: mins });", 1),
    ("return `${hours}h ago`;", "return t('time.hours_ago', { n: hours });", 1),
    ("return `${days}d ago`;", "return t('time.days_ago', { n: days });", 1),
])


def main() -> int:
    apply = '--apply' in sys.argv
    misses: list[str] = []
    per_file: dict[str, list[tuple[str, str, int]]] = {}
    for path, old, new, n in E:
        per_file.setdefault(path, []).append((old, new, n))

    changed = done = 0
    for path, pairs in per_file.items():
        full = os.path.join(ROOT, path)
        text = original = io.open(full, encoding='utf-8').read()
        for old, new, want in pairs:
            got = text.count(old)
            if got != want:
                misses.append(f'{path}: {got}x (want {want}x)  {old[:70]}')
                continue
            text = text.replace(old, new)
            done += 1
        if text != original:
            changed += 1
            if apply:
                io.open(full, 'w', encoding='utf-8', newline='\n').write(text)

    print(f'Dateien: {changed}   Ersetzungen: {done}/{len(E)}')
    for m in misses:
        print('  MISS ' + m)
    print('\n(dry run)' if not apply else '\ngeschrieben.')
    return 1 if misses else 0


if __name__ == '__main__':
    sys.exit(main())
