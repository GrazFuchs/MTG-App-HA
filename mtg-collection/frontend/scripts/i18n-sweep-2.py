#!/usr/bin/env python3
"""
Second pass of the Sprint-10 i18n sweep.

Pass 1 (`i18n-sweep.py`) scanned JSX text nodes and string props, and moved 324
literals. It could not see a whole further class, and it was the 45 keys left
over as "defined but unreachable" that gave it away: every one of them named a
piece of UI that plainly exists, so the text had to be hardcoded *somewhere the
scanner did not look*. It was in four shapes:

  * object literals feeding a `.map()` — `{ l: 'Total Cards', … }`
  * options arrays — `{ value: 'source_asc', label: 'Pending first' }`
  * ternaries inside JSX — `{busy ? 'Adding...' : 'Add all missing…'}`
  * JSX text interleaved with expressions — `✏️ Pending Listings ({n}) — …`

The dead-key list turned out to be the better scanner. Where a key already
existed for the text, it is reused; the rest are new.
"""
from __future__ import annotations

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

NEW_KEYS: dict[str, tuple[str, str]] = {
    'dashboard.inbox': ('Inbox', 'Eingang'),
    'dashboard.inbox_waiting': ('waiting for triage', 'warten auf Triage'),
    'dashboard.inbox_done': ('all triaged', 'alles triagiert'),
    'dashboard.unique_sub': ('{count} unique', '{count} einzigartig'),
    'dashboard.decks_sub': ('synced from Archidekt', 'von Archidekt synchronisiert'),
    'dashboard.on_market': ('On Market', 'Am Markt'),
    'dashboard.listings_sub': ('{count} listings', '{count} Angebote'),
    'dashboard.wishlist_sub': ('€{value} to buy', '€{value} zu kaufen'),
    'dashboard.wishlist_tracking': ('tracking', 'wird verfolgt'),
    'dashboard.never_synced': ('NEVER SYNCED', 'NIE SYNCHRONISIERT'),
    'dashboard.synced': ('SYNCED', 'SYNCHRONISIERT'),
    'dashboard.syncing': ('SYNCING…', 'SYNCHRONISIERT…'),
    'dashboard.alerts_failed': ('Price alerts could not be loaded. Check the add-on log.',
                                'Preisalarme konnten nicht geladen werden. Add-on-Log prüfen.'),
    'sort.price_desc': ('Price desc', 'Preis absteigend'),
    'sort.name_asc': ('Name asc', 'Name aufsteigend'),
    'sort.set_asc': ('Set asc', 'Set aufsteigend'),
    'sort.color_asc': ('Color asc', 'Farbe aufsteigend'),
    'sort.qty_desc': ('Quantity desc', 'Menge absteigend'),
    'sort.value_desc': ('Value desc', 'Wert absteigend'),
    'sort.extras_desc': ('Extras desc', 'Überschuss absteigend'),
    'sort.most_copies': ('Most copies', 'Meiste Kopien'),
    'cardmarket.csv_exported': ('CSV exported successfully', 'CSV erfolgreich exportiert'),
    'cardmarket.section_pending_n': ('✏️ Pending Listings ({count}) — not yet on Cardmarket',
                                     '✏️ Ausstehende Angebote ({count}) — noch nicht auf Cardmarket'),
    'cardmarket.section_live_n': ('✅ Live on Cardmarket ({count})',
                                  '✅ Live auf Cardmarket ({count})'),
    'health.underpriced': ('Underpriced', 'Zu billig'),
    'health.overpriced': ('Overpriced', 'Zu teuer'),
    'health.fair': ('Fair', 'Fair'),
    'health.no_data': ('No Data', 'Keine Daten'),
    'combos.syncing': ('Syncing...', 'Wird synchronisiert...'),
    'completeness.adding': ('Adding...', 'Wird hinzugefügt...'),
    'completeness.summary': ('Missing {count} cards · acquisition cost €{cost}',
                             '{count} Karten fehlen · Beschaffungskosten €{cost}'),
    'perf.saving': ('Saving…', 'Wird gespeichert…'),
    'perf.save_game': ('Save game', 'Partie speichern'),
    'power.compute': ('Compute power score', 'Power-Score berechnen'),
    'power.recompute': ('Recompute', 'Neu berechnen'),
    'gameplan.edit': ('Edit', 'Bearbeiten'),
    'gameplan.add': ('Add Gameplan', 'Spielplan anlegen'),
    'bracket.set': ('Set Bracket', 'Bracket setzen'),
    'history.kept': ('Kept', 'Behalten'),
    'history.sold_new': ('Sold (new copy)', 'Verkauft (neue Kopie)'),
    'history.swapped': ('Swapped', 'Getauscht'),
    'history.dismissed': ('Dismissed', 'Verworfen'),
    'wishlist.adding': ('Adding...', 'Wird hinzugefügt...'),
    'wishlist.add_to': ('Add to Wishlist', 'Zur Wunschliste'),
    'wishlist.mark_received': ('Mark as Received', 'Als erhalten markieren'),
    'wishlist.no_price': ('No price', 'Kein Preis'),
    'source.cardmarket': ('Cardmarket', 'Cardmarket'),
    'source.whatnot': ('Whatnot', 'Whatnot'),
    'source.booster': ('Booster', 'Booster'),
    'source.trade': ('Trade', 'Tausch'),
    'source.gift': ('Gift', 'Geschenk'),
    'source.shop': ('Shop', 'Laden'),
    'source.other': ('Other', 'Sonstige'),
    'collection.mode_any': ('Cards containing at least one selected colour',
                            'Karten mit mindestens einer gewählten Farbe'),
    'collection.mode_all': ('Cards containing every selected colour (and possibly more)',
                            'Karten mit allen gewählten Farben (und ggf. mehr)'),
    'collection.mode_exact': ('Cards whose colour identity is precisely the selection',
                              'Karten, deren Farbidentität genau der Auswahl entspricht'),
    'collection.mode_none': ('Cards containing none of the selected colours',
                             'Karten ohne jede der gewählten Farben'),
    'duplicates.mono': ('MONO', 'MONO'),
    'duplicates.creating': ('Creating...', 'Wird angelegt...'),
    'type.lands': ('Lands', 'Länder'),
    'type.creatures': ('Creatures', 'Kreaturen'),
    'type.artifacts': ('Artifacts', 'Artefakte'),
    'type.enchantments': ('Enchantments', 'Verzauberungen'),
    'type.instants_sorceries': ('Inst/Sorc', 'Spontan/Hexerei'),
    'inbox.tab_triage': ('Triage', 'Triage'),
    'inbox.tab_history': ('History', 'Verlauf'),
    'inbox.enriching': ('Enriching…', 'Wird angereichert…'),
    'settings.credentials_set': ('Credentials set', 'Zugangsdaten hinterlegt'),
    'settings.public_only': ('Public only', 'Nur öffentlich'),
    'settings.username_set': ('Username set', 'Benutzername hinterlegt'),
    'settings.not_configured': ('Not configured', 'Nicht konfiguriert'),
    'settings.auth': ('Auth', 'Anmeldung'),
    'settings.autosync': ('Auto-sync', 'Auto-Sync'),
    'settings.disabled': ('Disabled', 'Deaktiviert'),
    'settings.syncing': ('Syncing...', 'Synchronisiert...'),
    'settings.sync_now': ('Sync Now', 'Jetzt synchronisieren'),
    'settings.resyncing': ('Resyncing...', 'Wird neu synchronisiert...'),
    'settings.full_resync': ('Full Resync', 'Vollständiger Resync'),
}

E: list[tuple[str, str, str, int]] = []


def add(path: str, pairs: list[tuple[str, str, int]]) -> None:
    for old, new, n in pairs:
        E.append((path, old, new, n))


add('src/pages/Dashboard.tsx', [
    ("l: 'Inbox',", "l: t('dashboard.inbox'),", 1),
    ("sub: pendingCount > 0 ? 'waiting for triage' : 'all triaged',",
     "sub: pendingCount > 0 ? t('dashboard.inbox_waiting') : t('dashboard.inbox_done'),", 1),
    ("l: 'Total Cards',", "l: t('dashboard.total_cards'),", 1),
    ("sub: `${(stats?.unique_cards ?? 0).toLocaleString()} unique`,",
     "sub: t('dashboard.unique_sub', { count: (stats?.unique_cards ?? 0).toLocaleString() }),", 1),
    ("l: 'Decks',", "l: t('dashboard.decks'),", 1),
    ("sub: 'synced from Archidekt',", "sub: t('dashboard.decks_sub'),", 1),
    ("l: 'On Market',", "l: t('dashboard.on_market'),", 1),
    ("sub: `${stats?.total_cardmarket_listings ?? 0} listings`,",
     "sub: t('dashboard.listings_sub', { count: stats?.total_cardmarket_listings ?? 0 }),", 1),
    ("l: 'Wishlist',", "l: t('nav.wishlist'),", 1),
    ("? `€${wishlist.total_current_eur.toFixed(2)} to buy`\n              : 'tracking',",
     "? t('dashboard.wishlist_sub', { value: wishlist.total_current_eur.toFixed(2) })\n              : t('dashboard.wishlist_tracking'),", 1),
    ("{ label: 'NEVER SYNCED',", "{ label: t('dashboard.never_synced'),", 1),
    ("{ label: 'SYNCED',", "{ label: t('dashboard.synced'),", 1),
    ("{ label: 'SYNCING…',", "{ label: t('dashboard.syncing'),", 1),
    (": 'Price alerts could not be loaded. Check the add-on log.'}",
     ": t('dashboard.alerts_failed')}", 1),
])

add('src/pages/Cardmarket.tsx', [
    ("{ value: '', label: 'All Colors' },", "{ value: '', label: t('color.all') },", 1),
    ("{ value: 'source_asc', label: 'Pending first' },",
     "{ value: 'source_asc', label: t('cardmarket.sort.pending_first') },", 1),
    ("{ value: 'price_desc', label: 'Price desc' },",
     "{ value: 'price_desc', label: t('sort.price_desc') },", 1),
    ("{ value: 'name_asc', label: 'Name asc' },",
     "{ value: 'name_asc', label: t('sort.name_asc') },", 1),
    ("{ value: 'set_asc', label: 'Set asc' },",
     "{ value: 'set_asc', label: t('sort.set_asc') },", 1),
    ("{ value: 'color_asc', label: 'Color asc' },",
     "{ value: 'color_asc', label: t('sort.color_asc') },", 1),
    ("{ value: 'qty_desc', label: 'Quantity desc' },",
     "{ value: 'qty_desc', label: t('sort.qty_desc') },", 1),
    ("'CSV exported successfully'", "t('cardmarket.csv_exported')", 2),
    ("✏️ Pending Listings ({pendingListings.length}) — not yet on Cardmarket",
     "{t('cardmarket.section_pending_n', { count: pendingListings.length })}", 1),
    ("✅ Live on Cardmarket ({liveListings.length})",
     "{t('cardmarket.section_live_n', { count: liveListings.length })}", 1),
])

add('src/components/cardmarket/ListingHealthPanel.tsx', [
    ("'Underpriced'", "t('health.underpriced')", 1),
    ("'Overpriced'", "t('health.overpriced')", 1),
    ("'Fair'", "t('health.fair')", 1),
    ("'No Data'", "t('health.no_data')", 1),
])

add('src/components/deck/DeckCombosSection.tsx', [
    ("'Syncing...'", "t('combos.syncing')", 1),
    ("'Detect Combos from Spellbook'", "t('decks.combos_detect')", 1),
    ("'Refreshing...'", "t('combos.syncing')", 1),
    ("'Refresh from Spellbook'", "t('decks.combos_refresh')", 1),
])

add('src/components/deck/DeckCompletenessSection.tsx', [
    ("'Adding...'", "t('completeness.adding')", 1),
    ("'Add all missing to wishlist'", "t('decks.completeness_wishlist')", 1),
    ("Missing {data.missing_cards.length} cards · acquisition cost €{data.total_acquisition_cost_eur.toFixed(2)}",
     "{t('completeness.summary', { count: data.missing_cards.length, cost: data.total_acquisition_cost_eur.toFixed(2) })}", 1),
])

add('src/components/deck/DeckPerformanceSection.tsx', [
    ("'Saving…'", "t('perf.saving')", 1),
    ("'Save game'", "t('perf.save_game')", 1),
])

add('src/components/deck/DeckPowerSection.tsx', [
    ("'Compute power score'", "t('power.compute')", 1),
    ("'Recompute'", "t('power.recompute')", 1),
])

add('src/components/deck/GameplanBox.tsx', [
    ("'Edit'", "t('gameplan.edit')", 1),
    ("'Add Gameplan'", "t('gameplan.add')", 1),
])

add('src/components/deck/UserBracketBadge.tsx', [
    ("'Set Bracket'", "t('bracket.set')", 1),
    ("'Recompute'", "t('power.recompute')", 1),
])

add('src/components/inbox/InboxHistory.tsx', [
    ("'Kept'", "t('history.kept')", 1),
    ("'Sold (new copy)'", "t('history.sold_new')", 1),
    ("'Swapped'", "t('history.swapped')", 2),
    ("'Dismissed'", "t('history.dismissed')", 1),
])

add('src/components/wishlist/SetSelector.tsx', [
    ("'No price'", "t('wishlist.no_price')", 1),
])

add('src/components/wishlist/WishlistAddForm.tsx', [
    ("'Adding...'", "t('wishlist.adding')", 1),
    ("'Add to Wishlist'", "t('wishlist.add_to')", 1),
])

add('src/components/wishlist/WishlistAcquireDialog.tsx', [
    ("'Mark as Received'", "t('wishlist.mark_received')", 1),
])

add('src/pages/Collection.tsx', [
    ("'Cards containing at least one selected colour'", "t('collection.mode_any')", 1),
    ("'Cards containing every selected colour (and possibly more)'", "t('collection.mode_all')", 1),
    ("'Cards whose colour identity is precisely the selection'", "t('collection.mode_exact')", 1),
    ("'Cards containing none of the selected colours'", "t('collection.mode_none')", 1),
    ("'Collection is empty. Sync your decks to populate it.'", "t('collection.empty')", 1),
])

add('src/pages/Duplicates.tsx', [
    ("{ value: '', label: 'All Colors' },", "{ value: '', label: t('color.all') },", 1),
    ("'MONO'", "t('duplicates.mono')", 1),
    ("{ value: 'extras_value_desc', label: 'Value desc' },",
     "{ value: 'extras_value_desc', label: t('sort.value_desc') },", 1),
    ("{ value: 'extras_desc', label: 'Extras desc' },",
     "{ value: 'extras_desc', label: t('sort.extras_desc') },", 1),
    ("{ value: 'copies_desc', label: 'Most copies' },",
     "{ value: 'copies_desc', label: t('sort.most_copies') },", 1),
    ("{ value: 'name_asc', label: 'Name asc' },",
     "{ value: 'name_asc', label: t('sort.name_asc') },", 1),
    ("{ value: 'set_asc', label: 'Set asc' },",
     "{ value: 'set_asc', label: t('sort.set_asc') },", 1),
    ("{ value: 'color_asc', label: 'Color asc' },",
     "{ value: 'color_asc', label: t('sort.color_asc') },", 1),
    ("'Creating...'", "t('duplicates.creating')", 1),
])

add('src/pages/DeckView.tsx', [
    ("'Lands'", "t('type.lands')", 1),
    ("'Creatures'", "t('type.creatures')", 1),
    ("'Artifacts'", "t('type.artifacts')", 1),
    ("'Enchantments'", "t('type.enchantments')", 1),
    ("'Inst/Sorc'", "t('type.instants_sorceries')", 1),
])

add('src/pages/Inbox.tsx', [
    ("'Triage'", "t('inbox.tab_triage')", 1),
    ("'History'", "t('inbox.tab_history')", 1),
    ("'Enriching…'", "t('inbox.enriching')", 1),
])

add('src/pages/Settings.tsx', [
    ("'Credentials set'", "t('settings.credentials_set')", 1),
    ("'Public only'", "t('settings.public_only')", 1),
    ("'Username set'", "t('settings.username_set')", 1),
    ("'Not configured'", "t('settings.not_configured')", 2),
    ("'Auto-sync'", "t('settings.autosync')", 1),
    ("'Disabled'", "t('settings.disabled')", 1),
    ("'Syncing...'", "t('settings.syncing')", 1),
    ("'Sync Now'", "t('settings.sync_now')", 1),
    ("'Resyncing...'", "t('settings.resyncing')", 1),
    ("'Full Resync'", "t('settings.full_resync')", 1),
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
