#!/usr/bin/env python3
"""
One-shot codemod for the Sprint-10 i18n sweep.

Kept in the repo rather than thrown away because it is the record of *which*
literal became *which* key — a diff of 300 replacements does not tell you that,
and the next person adding a language will want the mapping, not the diff.

Two things it does that a blind search-and-replace must not:

1. `EXPECT` is the number of occurrences each replacement must find. A count
   that does not match aborts the whole run. Half the literals in this app are
   words like "Cancel" or "Set" that appear in several places with different
   meanings; without the count, a stray hit is silent.

2. Value-less `<option>` elements are rewritten to carry an explicit `value=`
   **before** their text is translated. In `<option>English</option>` the
   displayed text *is* the submitted value, so translating it alone would post
   the German word to Cardmarket. Duplicates.tsx had ten of them.

Usage:  python scripts/i18n-sweep.py --check    (dry run, prints every miss)
        python scripts/i18n-sweep.py --apply
"""
from __future__ import annotations

import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# --------------------------------------------------------------------------
# New keys. Existing ones (including the 76 that were defined but never wired
# up) are reused rather than duplicated — see REUSED below for the ones that
# carried the sweep.
# --------------------------------------------------------------------------
NEW_KEYS: dict[str, tuple[str, str]] = {
    # -- generic ----------------------------------------------------------
    'common.search': ('Search', 'Suchen'),
    'common.search_placeholder': ('Search...', 'Suchen...'),
    'common.all_sets': ('All Sets', 'Alle Sets'),
    'common.all_decks': ('All Decks', 'Alle Decks'),
    'common.all_tags': ('All Tags', 'Alle Tags'),
    'common.all_sources': ('All Sources', 'Alle Quellen'),
    'common.all': ('All', 'Alle'),
    'common.clear': ('clear', 'leeren'),
    'common.reset_all': ('reset all', 'alles zurücksetzen'),
    'common.reset': ('Reset', 'Zurücksetzen'),
    'common.refresh': ('Refresh', 'Aktualisieren'),
    'common.hide': ('Hide', 'Ausblenden'),
    'common.sell': ('Sell', 'Verkaufen'),
    'common.undo': ('Undo', 'Rückgängig'),
    'common.delete': ('Delete', 'Löschen'),
    'common.actions': ('Actions', 'Aktionen'),
    'common.source': ('Source', 'Quelle'),
    'common.date': ('Date', 'Datum'),
    'common.result': ('Result', 'Ergebnis'),
    'common.quantity': ('Quantity', 'Menge'),
    'common.price_eur': ('Price (EUR)', 'Preis (EUR)'),
    'common.condition': ('Condition', 'Zustand'),
    'common.language': ('Language', 'Sprache'),
    'common.set_version': ('Set / Version', 'Set / Edition'),
    'common.any_printing': ('Any printing', 'Beliebiger Druck'),
    'common.card': ('Card', 'Karte'),
    'common.back_to_top': ('Back to top', 'Nach oben'),
    'common.open_cardmarket': ('Open on Cardmarket', 'Auf Cardmarket öffnen'),
    'common.why': ('why?', 'warum?'),
    'common.select_printing': ('Select printing', 'Druck wählen'),
    'common.loading_printings': ('Loading printings...', 'Drucke werden geladen...'),
    'common.example_price': ('e.g. 12.50', 'z. B. 12,50'),
    # -- table column headers --------------------------------------------
    'col.card': ('CARD', 'KARTE'),
    'col.set': ('SET', 'SET'),
    'col.owned': ('OWNED', 'BESTAND'),
    'col.decks': ('DECKS', 'DECKS'),
    'col.extra': ('EXTRA', 'ÜBERSCHUSS'),
    'col.eur': ('EUR', 'EUR'),
    'col.value': ('VALUE', 'WERT'),
    'col.printing': ('PRINTING', 'DRUCK'),
    'col.copies': ('COPIES', 'KOPIEN'),
    'col.listed': ('LISTED', 'GELISTET'),
    'col.qty': ('QTY', 'ANZ'),
    'col.price_eur': ('PRICE €', 'PREIS €'),
    'col.name': ('NAME', 'NAME'),
    'col.in_decks': ('IN DECKS', 'IN DECKS'),
    'col.finish': ('FINISH', 'AUSFÜHRUNG'),
    'col.edition': ('EDITION', 'EDITION'),
    'col.lang': ('LANG', 'SPR'),
    'col.cond': ('COND', 'ZUST'),
    'col.source': ('SOURCE', 'QUELLE'),
    'col.rarity': ('RARITY', 'SELTENHEIT'),
    'col.started': ('STARTED', 'GESTARTET'),
    'col.status': ('STATUS', 'STATUS'),
    'col.items': ('ITEMS', 'EINTRÄGE'),
    'col.finished': ('FINISHED', 'BEENDET'),
    'col.error': ('ERROR', 'FEHLER'),
    'col.my_price': ('My Price', 'Mein Preis'),
    'col.trend': ('Trend', 'Trend'),
    'col.suggested': ('Suggested', 'Vorschlag'),
    # -- card condition (Cardmarket grades) -------------------------------
    'condition.MT': ('Mint', 'Mint'),
    'condition.NM': ('Near Mint', 'Near Mint'),
    'condition.EX': ('Excellent', 'Excellent'),
    'condition.GD': ('Good', 'Good'),
    'condition.LP': ('Light Played', 'Light Played'),
    'condition.PL': ('Played', 'Played'),
    'condition.PO': ('Poor', 'Poor'),
    # -- card language ----------------------------------------------------
    'lang.English': ('English', 'Englisch'),
    'lang.German': ('German', 'Deutsch'),
    'lang.French': ('French', 'Französisch'),
    'lang.Spanish': ('Spanish', 'Spanisch'),
    'lang.Italian': ('Italian', 'Italienisch'),
    'lang.Japanese': ('Japanese', 'Japanisch'),
    'lang.Chinese': ('Chinese', 'Chinesisch'),
    'lang.Korean': ('Korean', 'Koreanisch'),
    'lang.Portuguese': ('Portuguese', 'Portugiesisch'),
    'lang.Russian': ('Russian', 'Russisch'),
    # -- app shell --------------------------------------------------------
    'app.subtitle': ('Collection Manager', 'Sammlungsverwaltung'),
    'app.render_failed': ('This page could not be rendered', 'Diese Seite konnte nicht dargestellt werden'),
    'app.loading': ('Loading…', 'Wird geladen…'),
    'notfound.title': ('No such page', 'Seite gibt es nicht'),
    'notfound.body': ('is not a route of this add-on.', 'ist keine Route dieses Add-ons.'),
    'notfound.back': ('Back to the dashboard', 'Zurück zur Übersicht'),
    # -- dashboard --------------------------------------------------------
    'dashboard.last_sync': ('LAST SYNC', 'LETZTER SYNC'),
    'dashboard.aggregate': ('AGGREGATE HOLDINGS · EUR', 'GESAMTBESTAND · EUR'),
    'dashboard.usd_mirror': ('USD MIRROR', 'USD-SPIEGEL'),
    'dashboard.listings_value': ('LISTINGS VALUE', 'ANGEBOTSWERT'),
    'dashboard.buy': ('BUY', 'KAUFEN'),
    'dashboard.sell': ('SELL', 'VERKAUFEN'),
    'dashboard.vault': ('The Vault', 'Der Tresor'),
    'dashboard.backend_unreachable': ('Backend unreachable', 'Backend nicht erreichbar'),
    'dashboard.open_collection': ('Open the collection', 'Sammlung öffnen'),
    'dashboard.anomalies': ('Market Anomalies', 'Marktauffälligkeiten'),
    'dashboard.movers': ('Collection Movers', 'Größte Bewegungen'),
    'dashboard.signals': ('Trade Signals', 'Handelssignale'),
    # -- collection -------------------------------------------------------
    'collection.sort_added': ('Date Added', 'Hinzugefügt am'),
    'collection.sort_price': ('Price', 'Preis'),
    'collection.sort_set': ('Set', 'Set'),
    'collection.sort_tag': ('Collection Tag', 'Sammlungs-Tag'),
    'collection.sort_name': ('Name', 'Name'),
    'collection.asc': ('Ascending', 'Aufsteigend'),
    'collection.desc': ('Descending', 'Absteigend'),
    'collection.colour': ('Colour', 'Farbe'),
    'collection.type': ('Type', 'Typ'),
    'collection.tag_filter': ('Collection tag filter', 'Filter nach Sammlungs-Tag'),
    'collection.colour_mode_hint': ('How to combine the selected colours', 'Wie die gewählten Farben verknüpft werden'),
    'collection.loading': ('Loading collection...', 'Sammlung wird geladen...'),
    # -- duplicates -------------------------------------------------------
    'duplicates.title': ('Duplicates', 'Duplikate'),
    'duplicates.search': ('Search duplicates...', 'Duplikate suchen...'),
    'duplicates.show_listed': ('Show fully listed', 'Vollständig gelistete zeigen'),
    'duplicates.loading': ('Loading duplicates...', 'Duplikate werden geladen...'),
    'duplicates.urgency': ('Urgency', 'Dringlichkeit'),
    'duplicates.not_listed': ('Not yet listed', 'Noch nicht gelistet'),
    'duplicates.empty': ('No duplicate cards found.', 'Keine doppelten Karten gefunden.'),
    # -- inbox ------------------------------------------------------------
    'inbox.min_value': ('Min value', 'Mindestwert'),
    'inbox.search': ('Search by name...', 'Nach Namen suchen...'),
    'inbox.color_filter': ('Color filter', 'Farbfilter'),
    'inbox.sort_by': ('Sort by', 'Sortieren nach'),
    'inbox.refetch_colors': ('Re-fetch missing colour data from Scryfall so the colour groups/filter work',
                             'Fehlende Farbdaten von Scryfall nachladen, damit Farbgruppen und -filter greifen'),
    'inbox.loading': ('Loading inbox...', 'Eingang wird geladen...'),
    'inbox.render_failed': ('The inbox list could not be rendered', 'Die Eingangsliste konnte nicht dargestellt werden'),
    'inbox.decision_failed': ('Decision failed', 'Entscheidung fehlgeschlagen'),
    'inbox.shortcut_hint': ('K = keep · D = dismiss', 'K = behalten · D = verwerfen'),
    'inbox.already_own': ('You already own:', 'Bereits im Bestand:'),
    'inbox.history.suggestion_shown': ('Suggestion shown at confirmation', 'Vorschlag bei der Bestätigung'),
    'inbox.history.state_then': ('State at that time', 'Zustand damals'),
    'inbox.history.copies_then': ('Other copies owned then', 'Andere Kopien damals'),
    'inbox.history.filter': ('Decision filter', 'Entscheidungsfilter'),
    'inbox.history.loading': ('Loading history...', 'Verlauf wird geladen...'),
    'triage.copy_to_sell': ('Copy to sell', 'Zu verkaufende Kopie'),
    'triage.create_listing': ('Create Listing', 'Angebot anlegen'),
    # -- cardmarket -------------------------------------------------------
    'cardmarket.title': ('Cardmarket', 'Cardmarket'),
    'cardmarket.listings_total': ('LISTINGS · TOTAL VALUE', 'ANGEBOTE · GESAMTWERT'),
    'cardmarket.manual_draft': ('Manual (Draft)', 'Manuell (Entwurf)'),
    'cardmarket.imported': ('Imported', 'Importiert'),
    'cardmarket.empty': ('No listings. Import a CSV or list duplicates from the Duplicates tab.',
                         'Keine Angebote. Importiere eine CSV oder liste Duplikate im Reiter Duplikate.'),
    'cardmarket.trend_30d': ('30-day trend', '30-Tage-Trend'),
    'cardmarket.price_alerts': ('Price Spike Alerts', 'Preis-Spike-Alarme'),
    'cardmarket.active_listings': ('Active Listings', 'Aktive Angebote'),
    'cardmarket.listing_health': ('Listing Health', 'Angebotsqualität'),
    'cardmarket.health_empty': ('No listings in this category.', 'Keine Angebote in dieser Kategorie.'),
    'cardmarket.health_loading': ('Analyzing listings...', 'Angebote werden ausgewertet...'),
    'cardmarket.workflow_intro': ('Cardmarket has no official sync API for stocks — updates work via CSV roundtrips:',
                                  'Cardmarket hat keine offizielle Sync-API für Bestände — Aktualisierungen laufen über CSV:'),
    'cardmarket.workflow_step1': ('On cardmarket.com → Stock → "Export to CSV"',
                                  'Auf cardmarket.com → Stock → „Export to CSV"'),
    'cardmarket.workflow_step1_hint': ('Downloads your current stock list', 'Lädt deine aktuelle Bestandsliste herunter'),
    'cardmarket.workflow_step2_hint': ('Updates your listings in this add-on', 'Aktualisiert die Angebote in diesem Add-on'),
    'cardmarket.workflow_step3': ('Edit here (adjust prices, mark cards for sale)',
                                  'Hier bearbeiten (Preise anpassen, Karten zum Verkauf markieren)'),
    'cardmarket.workflow_step4_hint': ('CSV with your changes, ready for re-import on Cardmarket',
                                       'CSV mit deinen Änderungen, bereit zum Reimport auf Cardmarket'),
    'cardmarket.workflow_step5': ('On Cardmarket: use browser extension or MKM API for bulk updates (power users)',
                                  'Auf Cardmarket: Browser-Erweiterung oder MKM-API für Massenänderungen (für Fortgeschrittene)'),
    # -- decks ------------------------------------------------------------
    'decks.title': ('Decks', 'Decks'),
    'decks.loading': ('Loading decks...', 'Decks werden geladen...'),
    'decks.empty': ('No decks synced yet. Go to Settings to trigger a sync from Archidekt.',
                    'Noch keine Decks synchronisiert. Starte in den Einstellungen einen Archidekt-Sync.'),
    'decks.all_brackets': ('All Brackets', 'Alle Brackets'),
    'deck.loading': ('Loading deck...', 'Deck wird geladen...'),
    'deck.no_id': ('No deck ID provided.', 'Keine Deck-ID übergeben.'),
    'deck.not_found': ('Deck not found.', 'Deck nicht gefunden.'),
    'deck.mana_curve': ('MANA CURVE', 'MANAKURVE'),
    'deck.color_pips': ('COLOR PIPS', 'FARBSYMBOLE'),
    'deck.composition': ('COMPOSITION', 'ZUSAMMENSETZUNG'),
    'deck.compare_loading': ('Comparing decks...', 'Decks werden verglichen...'),
    'deck.compare_none': ('No cards in common', 'Keine gemeinsamen Karten'),
    'deck.union_label': ('UNION:', 'VEREINIGUNG:'),
    'deck.intersection_label': ('INTERSECTION:', 'SCHNITTMENGE:'),
    'combo.partial': ('PARTIAL', 'TEILWEISE'),
    'combo.cards_involved': ('CARDS INVOLVED', 'BETEILIGTE KARTEN'),
    'combo.missing_cards': ('MISSING CARDS', 'FEHLENDE KARTEN'),
    'combo.result': ('RESULT', 'ERGEBNIS'),
    'combo.prerequisites': ('PREREQUISITES', 'VORAUSSETZUNGEN'),
    'combo.steps': ('STEPS', 'SCHRITTE'),
    'combo.spellbook_link': ('View on Commander Spellbook ↗', 'Auf Commander Spellbook ansehen ↗'),
    'combo.none_complete': ('No complete combo in this deck', 'Keine vollständige Combo in diesem Deck'),
    'combo.none_partial': ('No partial combos detected', 'Keine Teil-Combos erkannt'),
    'gameplan.title': ('Gameplan', 'Spielplan'),
    'gameplan.empty': ('No gameplan set', 'Kein Spielplan hinterlegt'),
    'ai.empty': ('No AI assessment yet. Ask the MCP assistant to analyze this deck.',
                 'Noch keine KI-Einschätzung. Bitte den MCP-Assistenten, dieses Deck zu analysieren.'),
    'ai.stale': ('Assessment predates the last deck change', 'Einschätzung ist älter als die letzte Deckänderung'),
    # -- deck performance --------------------------------------------------
    'perf.title': ('Deck Performance', 'Deck-Leistung'),
    'perf.log_game': ('Log game', 'Partie erfassen'),
    'perf.log_a_game': ('Log a game', 'Partie erfassen'),
    'perf.empty': ('No games logged yet. Track how your deck performs after each game.',
                   'Noch keine Partien erfasst. Halte nach jeder Partie fest, wie das Deck läuft.'),
    'perf.win': ('Win', 'Sieg'),
    'perf.loss': ('Loss', 'Niederlage'),
    'perf.draw': ('Draw', 'Unentschieden'),
    'perf.win_rate': ('Win rate', 'Siegquote'),
    'perf.wld': ('W / L / D', 'S / N / U'),
    'perf.recent_form': ('Recent form', 'Letzte Form'),
    'perf.on_play_win': ('On-play win%', 'Siege am Zug'),
    'perf.avg_mulligans': ('Avg mulligans', 'Ø Mulligans'),
    'perf.avg_missed_lands': ('Avg missed lands', 'Ø fehlende Länder'),
    'perf.avg_turns': ('Avg turns', 'Ø Züge'),
    'perf.delete_game': ('Delete game', 'Partie löschen'),
    'perf.on_the_play': ('On the play', 'Am Zug'),
    'perf.pod_size': ('Pod size', 'Podgröße'),
    'perf.mulligans': ('Mulligans', 'Mulligans'),
    'perf.missed_lands': ('Missed lands', 'Fehlende Länder'),
    'perf.turns': ('Turns', 'Züge'),
    'perf.opponents': ('Opponents / commanders', 'Gegner / Commander'),
    'perf.opponents_hint': ('e.g. Atraxa, Krenko', 'z. B. Atraxa, Krenko'),
    'perf.what_worked': ('What worked', 'Was lief gut'),
    'perf.what_didnt': ("What didn't", 'Was lief schlecht'),
    # -- power / bracket ---------------------------------------------------
    'power.title': ('Power', 'Power'),
    'power.not_scored': ('Not scored yet.', 'Noch nicht bewertet.'),
    'power.score': ('Score', 'Punkte'),
    'power.level': ('Power level', 'Power-Level'),
    'power.efficiency': ('Efficiency', 'Effizienz'),
    'power.tipping_point': ('Tipping point', 'Kipppunkt'),
    'power.avg_cost': ('Avg. cost', 'Ø Kosten'),
    'power.by_mana_value': ('Impact by mana value', 'Wirkung nach Manawert'),
    'power.carrying': ('Carrying the score', 'Treiber der Wertung'),
    'power.reference': ('Check against edhpowerlevel.com ↗', 'Gegen edhpowerlevel.com prüfen ↗'),
    'bracket.your_bracket': ('YOUR BRACKET · overrides the computed one',
                             'DEIN BRACKET · überstimmt das berechnete'),
    'bracket.computed_from': ('Computed from the decklist:', 'Aus der Deckliste berechnet:'),
    'bracket.nothing_found': ('No game changers, no complete two-card combo, no mass land denial, no extra-turn plan.',
                              'Keine Game Changer, keine vollständige Zwei-Karten-Combo, keine Mass Land Denial, kein Extra-Turn-Plan.'),
    'bracket.clear': ('Clear — fall back to the computed bracket',
                      'Zurücksetzen — wieder das berechnete Bracket verwenden'),
    'bracket.explain': ('What put this deck in that bracket', 'Warum dieses Deck in diesem Bracket steht'),
    # -- settings ---------------------------------------------------------
    'settings.schedule': ('SYNC SCHEDULE', 'SYNC-ZEITPLAN'),
    'settings.sync_config': ('Sync Configuration', 'Sync-Konfiguration'),
    'settings.sync_config_hint': ('Configure these options in the Home Assistant Add-on settings.',
                                  'Diese Optionen werden in den Home-Assistant-Add-on-Einstellungen gesetzt.'),
    'settings.connections': ('CONNECTIONS', 'VERBINDUNGEN'),
    'settings.cardmarket_data': ('Cardmarket Data', 'Cardmarket-Daten'),
    'settings.clear_hint': ('Delete all Cardmarket listings (both imported and manually created).',
                            'Löscht alle Cardmarket-Angebote (importierte wie von Hand angelegte).'),
    'settings.clear_all': ('Clear All Listings', 'Alle Angebote löschen'),
    'settings.history_empty': ('No sync history yet.', 'Noch keine Sync-Historie.'),
    'settings.history': ('Sync History', 'Sync-Historie'),
    # -- MCP wizard --------------------------------------------------------
    'mcp.title': ('MCP Setup for Claude Desktop', 'MCP-Einrichtung für Claude Desktop'),
    'mcp.reachable': ('Add-on reachable', 'Add-on erreichbar'),
    'mcp.token_required': ('Auth token required', 'Auth-Token erforderlich'),
    'mcp.step': ('Step {n}:', 'Schritt {n}:'),
    'mcp.step1': ('Download proxy file', 'Proxy-Datei herunterladen'),
    'mcp.step2': ('Create a Long-Lived Access Token', 'Long-Lived Access Token anlegen'),
    'mcp.step2_hint': ('In Home Assistant: Profile → Security → Long-Lived Access Tokens → Create Token',
                       'In Home Assistant: Profil → Sicherheit → Langlebige Zugriffstokens → Token erstellen'),
    'mcp.step3': ('Paste config into Claude Desktop', 'Konfiguration in Claude Desktop einfügen'),
    'mcp.step4': ('Config file location', 'Ort der Konfigurationsdatei'),
    'mcp.show_paths': ('Show paths per OS', 'Pfade je Betriebssystem zeigen'),
    'mcp.step5': ('Replace placeholders in the config', 'Platzhalter in der Konfiguration ersetzen'),
    'mcp.step6': ('Restart Claude Desktop', 'Claude Desktop neu starten'),
    'mcp.step6_hint': ('After saving the config, fully quit and reopen Claude Desktop.',
                       'Nach dem Speichern Claude Desktop vollständig beenden und neu öffnen.'),
    # -- wishlist ----------------------------------------------------------
    'wishlist.group_by_name': ('Group by name', 'Nach Namen gruppieren'),
    'wishlist.no_target_short': ('not set', 'nicht gesetzt'),
    'wishlist.no_target_hint': ('No target price set — this card can never show up as a deal',
                                'Kein Zielpreis gesetzt — diese Karte kann nie als Deal erscheinen'),
    'wishlist.game_changer': ('Game Changer', 'Game Changer'),
    'wishlist.game_changer_hint': ('On the official WotC Game Changers list',
                                   'Steht auf der offiziellen WotC-Game-Changers-Liste'),
    'wishlist.no_target_filter': ('No target price', 'Ohne Zielpreis'),
    'wishlist.filter_ordered': ('Ordered', 'Bestellt'),
    'wishlist.card_name_placeholder': ('Card name...', 'Kartenname...'),
    'wishlist.no_alert': ('0 = no alert', '0 = kein Alarm'),
    'wishlist.tags_placeholder': ('modern, priority-upgrade', 'modern, priority-upgrade'),
    'wishlist.notes_placeholder': ('Optional notes...', 'Notizen (optional)...'),
    'wishlist.paid_price': ('Paid Price (EUR)', 'Bezahlter Preis (EUR)'),
    'wishlist.expected_price': ('Expected Price (EUR)', 'Erwarteter Preis (EUR)'),
    'wishlist.select_source': ('Select source (optional)', 'Quelle wählen (optional)'),
    'wishlist.printings_failed': ('Could not load printings. Proceed without set.',
                                  'Drucke konnten nicht geladen werden. Ohne Set fortfahren.'),
    # -- misc --------------------------------------------------------------
    'price.no_history': ('No price history', 'Keine Preishistorie'),
    'price.mtgstocks': ('MTGStocks · 1y (USD)', 'MTGStocks · 1 J. (USD)'),
}

# Existing keys the sweep wires up for the first time — the sprint's "many fit
# exactly" turned out to be true for 41 of the 76 dead ones.
REUSED = [
    'collection.title', 'collection.search', 'collection.no_results', 'collection.empty',
    'dashboard.title', 'dashboard.total_cards', 'dashboard.unique_cards', 'dashboard.value_eur',
    'dashboard.value_usd', 'dashboard.decks', 'dashboard.cardmarket_listings',
    'dashboard.price_alerts', 'dashboard.value_history',
    'decks.compare_title', 'decks.compare_select', 'decks.compare_common', 'decks.compare_unique',
    'decks.compare_overlap', 'decks.combos_empty', 'decks.completeness',
    'duplicates.group_by', 'duplicates.group.none', 'duplicates.group.color', 'duplicates.group.set',
    'wishlist.tab_active', 'wishlist.tab_history', 'wishlist.tab_lost', 'wishlist.tab_dropped',
    'wishlist.no_deck', 'wishlist.notes_label', 'wishlist.tags_label', 'wishlist.priority_label',
    'wishlist.deck_label', 'wishlist.no_data',
    'cards.foil', 'cards.owned', 'common.cancel', 'common.save', 'common.loading', 'common.retry',
    'settings.backup', 'inbox.action.dismiss',
]

# --------------------------------------------------------------------------
# The replacements. (file, old, new, expected occurrences)
# --------------------------------------------------------------------------
E: list[tuple[str, str, str, int]] = []


def add(path: str, pairs: list[tuple[str, str, int]]) -> None:
    for old, new, n in pairs:
        E.append((path, old, new, n))


# --- value-less options get a value BEFORE their text is translated -------
for _l in ('English', 'German', 'French', 'Spanish', 'Italian',
           'Japanese', 'Chinese', 'Korean', 'Portuguese', 'Russian'):
    add('src/pages/Duplicates.tsx', [
        (f'<option>{_l}</option>',
         f'<option value="{_l}">{{t(\'lang.{_l}\')}}</option>', 1),
    ])

add('src/App.tsx', [
    ('>Collection Manager<', ">{t('app.subtitle')}<", 1),
    ('>Try again<', ">{t('common.retry')}<", 1),
    ('title="This page could not be rendered"', "title={t('app.render_failed')}", 1),
    ('label="Loading…"', "label={t('app.loading')}", 1),
])

add('src/pages/NotFound.tsx', [
    ('>No such page<', ">{t('notfound.title')}<", 1),
    ('>is not a route of this add-on.<', ">{t('notfound.body')}<", 1),
    ('>Back to the dashboard<', ">{t('notfound.back')}<", 1),
])

add('src/pages/Dashboard.tsx', [
    ('>LAST SYNC<', ">{t('dashboard.last_sync')}<", 1),
    ('>AGGREGATE HOLDINGS · EUR<', ">{t('dashboard.aggregate')}<", 1),
    ('>USD MIRROR<', ">{t('dashboard.usd_mirror')}<", 1),
    ('>LISTINGS VALUE<', ">{t('dashboard.listings_value')}<", 1),
    ('>BUY<', ">{t('dashboard.buy')}<", 1),
    ('>SELL<', ">{t('dashboard.sell')}<", 1),
    ('label="Loading..."', "label={t('common.loading')}", 1),
    ('title="The Vault"', "title={t('dashboard.vault')}", 1),
    ('title="Backend unreachable"', "title={t('dashboard.backend_unreachable')}", 1),
    ('title="Open the collection"', "title={t('dashboard.open_collection')}", 1),
    ('title="Market Anomalies"', "title={t('dashboard.anomalies')}", 1),
    ('title="Collection Movers"', "title={t('dashboard.movers')}", 1),
    ('title="Trade Signals"', "title={t('dashboard.signals')}", 1),
])

add('src/pages/Collection.tsx', [
    ('>Search<', ">{t('common.search')}<", 1),
    ('>All Sets<', ">{t('common.all_sets')}<", 1),
    ('>All Decks<', ">{t('common.all_decks')}<", 1),
    ('>All Tags<', ">{t('common.all_tags')}<", 1),
    ('>Date Added<', ">{t('collection.sort_added')}<", 1),
    ('>Price<', ">{t('collection.sort_price')}<", 1),
    ('>Set<', ">{t('collection.sort_set')}<", 1),
    ('>Collection Tag<', ">{t('collection.sort_tag')}<", 1),
    ('>Name<', ">{t('collection.sort_name')}<", 1),
    ('>Ascending<', ">{t('collection.asc')}<", 1),
    ('>Descending<', ">{t('collection.desc')}<", 1),
    ('>Colour<', ">{t('collection.colour')}<", 1),
    ('>Type<', ">{t('collection.type')}<", 1),
    ('>clear<', ">{t('common.clear')}<", 2),
    ('>reset all<', ">{t('common.reset_all')}<", 2),
    ('>NAME<', ">{t('col.name')}<", 1),
    ('>COPIES<', ">{t('col.copies')}<", 1),
    ('>IN DECKS<', ">{t('col.in_decks')}<", 1),
    ('>FINISH<', ">{t('col.finish')}<", 1),
    ('>EDITION<', ">{t('col.edition')}<", 1),
    ('>LANG<', ">{t('col.lang')}<", 1),
    ('>EUR<', ">{t('col.eur')}<", 1),
    ('title="Collection"', "title={t('collection.title')}", 1),
    ('placeholder="Search cards..."', "placeholder={t('collection.search')}", 1),
    ('aria-label="Collection tag filter"', "aria-label={t('collection.tag_filter')}", 1),
    ('aria-label="How to combine the selected colours"', "aria-label={t('collection.colour_mode_hint')}", 1),
    ('label="Loading collection..."', "label={t('collection.loading')}", 1),
])

add('src/pages/Duplicates.tsx', [
    ('>Sell<', ">{t('common.sell')}<", 1),
    ('>CARD<', ">{t('col.card')}<", 1),
    ('>SET<', ">{t('col.set')}<", 1),
    ('>OWNED<', ">{t('col.owned')}<", 1),
    ('>DECKS<', ">{t('col.decks')}<", 1),
    ('>EXTRA<', ">{t('col.extra')}<", 1),
    ('>EUR<', ">{t('col.eur')}<", 1),
    ('>VALUE<', ">{t('col.value')}<", 1),
    ('>Search<', ">{t('common.search')}<", 1),
    ('>All Sets<', ">{t('common.all_sets')}<", 1),
    ('>Urgency<', ">{t('duplicates.urgency')}<", 1),
    ('>Not yet listed<', ">{t('duplicates.not_listed')}<", 1),
    ('>No duplicate cards found.<', ">{t('duplicates.empty')}<", 1),
    ('>PRINTING<', ">{t('col.printing')}<", 1),
    ('>COPIES<', ">{t('col.copies')}<", 1),
    ('>LISTED<', ">{t('col.listed')}<", 1),
    ('>QTY<', ">{t('col.qty')}<", 1),
    ('>PRICE €<', ">{t('col.price_eur')}<", 1),
    ('>Condition<', ">{t('common.condition')}<", 1),
    ('>Language<', ">{t('common.language')}<", 1),
    ('<option value="MT">Mint</option>', '<option value="MT">{t(\'condition.MT\')}</option>', 1),
    ('<option value="NM">Near Mint</option>', '<option value="NM">{t(\'condition.NM\')}</option>', 1),
    ('<option value="EX">Excellent</option>', '<option value="EX">{t(\'condition.EX\')}</option>', 1),
    ('<option value="GD">Good</option>', '<option value="GD">{t(\'condition.GD\')}</option>', 1),
    ('<option value="LP">Light Played</option>', '<option value="LP">{t(\'condition.LP\')}</option>', 1),
    ('<option value="PL">Played</option>', '<option value="PL">{t(\'condition.PL\')}</option>', 1),
    ('<option value="PO">Poor</option>', '<option value="PO">{t(\'condition.PO\')}</option>', 1),
    ('>Cancel<', ">{t('common.cancel')}<", 1),
    ('title="Duplicates"', "title={t('duplicates.title')}", 1),
    ('placeholder="Search duplicates..."', "placeholder={t('duplicates.search')}", 1),
    ('label="Show fully listed"', "label={t('duplicates.show_listed')}", 1),
    ('label="Loading duplicates..."', "label={t('duplicates.loading')}", 1),
    ('label="Loading printings..."', "label={t('common.loading_printings')}", 1),
])

add('src/pages/Inbox.tsx', [
    ('>Min value<', ">{t('inbox.min_value')}<", 1),
    ('>All<', ">{t('common.all')}<", 1),
    ('>Dismiss<', ">{t('inbox.action.dismiss')}<", 1),
    ('>Undo<', ">{t('common.undo')}<", 1),
    ('>K = keep · D = dismiss<', ">{t('inbox.shortcut_hint')}<", 1),
    ('placeholder="Search by name..."', "placeholder={t('inbox.search')}", 1),
    ('aria-label="Color filter"', "aria-label={t('inbox.color_filter')}", 1),
    ('aria-label="Sort by"', "aria-label={t('inbox.sort_by')}", 1),
    ('title="Re-fetch missing colour data from Scryfall so the colour groups/filter work"',
     "title={t('inbox.refetch_colors')}", 1),
    ('label="Loading inbox..."', "label={t('inbox.loading')}", 1),
    ('title="Inbox-Liste konnte nicht gerendert werden"', "title={t('inbox.render_failed')}", 1),
    ('title="Decision failed"', "title={t('inbox.decision_failed')}", 1),
])

add('src/pages/Cardmarket.tsx', [
    ('>LISTINGS · TOTAL VALUE<', ">{t('cardmarket.listings_total')}<", 1),
    ('>All Sets<', ">{t('common.all_sets')}<", 1),
    ('>All Sources<', ">{t('common.all_sources')}<", 1),
    ('>Manual (Draft)<', ">{t('cardmarket.manual_draft')}<", 1),
    ('>Imported<', ">{t('cardmarket.imported')}<", 1),
    ('>No listings. Import a CSV or list duplicates from the Duplicates tab.<',
     ">{t('cardmarket.empty')}<", 1),
    ('>NAME<', ">{t('col.name')}<", 1),
    ('>SET<', ">{t('col.set')}<", 1),
    ('>QTY<', ">{t('col.qty')}<", 1),
    ('>COND<', ">{t('col.cond')}<", 1),
    ('>LANG<', ">{t('col.lang')}<", 1),
    ('>SOURCE<', ">{t('col.source')}<", 1),
    ('>EUR<', ">{t('col.eur')}<", 1),
    ('>RARITY<', ">{t('col.rarity')}<", 1),
    ('label="30-day trend"', "label={t('cardmarket.trend_30d')}", 1),
    ('title="Cardmarket"', "title={t('cardmarket.title')}", 1),
    ('placeholder="Search..."', "placeholder={t('common.search_placeholder')}", 1),
    ('title="Price Spike Alerts"', "title={t('cardmarket.price_alerts')}", 1),
    ('title="Active Listings"', "title={t('cardmarket.active_listings')}", 1),
    ('label="Loading..."', "label={t('common.loading')}", 1),
    ('title="Listing Health"', "title={t('cardmarket.listing_health')}", 1),
])

add('src/pages/Settings.tsx', [
    ('>SYNC SCHEDULE<', ">{t('settings.schedule')}<", 1),
    ('>Sync Configuration<', ">{t('settings.sync_config')}<", 1),
    ('>Configure these options in the Home Assistant Add-on settings.<',
     ">{t('settings.sync_config_hint')}<", 1),
    ('>CONNECTIONS<', ">{t('settings.connections')}<", 1),
    ('>Cardmarket Data<', ">{t('settings.cardmarket_data')}<", 1),
    ('>Delete all Cardmarket listings (both imported and manually created).<',
     ">{t('settings.clear_hint')}<", 1),
    ('>Clear All Listings<', ">{t('settings.clear_all')}<", 1),
    ('>No sync history yet.<', ">{t('settings.history_empty')}<", 1),
    ('>STARTED<', ">{t('col.started')}<", 1),
    ('>SOURCE<', ">{t('col.source')}<", 1),
    ('>STATUS<', ">{t('col.status')}<", 1),
    ('>ITEMS<', ">{t('col.items')}<", 1),
    ('>FINISHED<', ">{t('col.finished')}<", 1),
    ('>ERROR<', ">{t('col.error')}<", 1),
    ('label="Loading..."', "label={t('common.loading')}", 1),
    ('title="Sync History"', "title={t('settings.history')}", 1),
    ('title="Backup & Restore"', "title={t('settings.backup')}", 1),
])

add('src/pages/Decks.tsx', [
    ('>No decks synced yet. Go to Settings to trigger a sync from Archidekt.<',
     ">{t('decks.empty')}<", 1),
    ('>All Brackets<', ">{t('decks.all_brackets')}<", 1),
    ('label="Loading decks..."', "label={t('decks.loading')}", 1),
    ('title="Decks"', "title={t('decks.title')}", 2),
])

add('src/pages/DeckView.tsx', [
    ('>No deck ID provided.<', ">{t('deck.no_id')}<", 1),
    ('>Deck not found.<', ">{t('deck.not_found')}<", 1),
    ('>MANA CURVE<', ">{t('deck.mana_curve')}<", 1),
    ('>COLOR PIPS<', ">{t('deck.color_pips')}<", 1),
    ('>COMPOSITION<', ">{t('deck.composition')}<", 1),
    ('label="Loading deck..."', "label={t('deck.loading')}", 1),
])

add('src/pages/DeckCompare.tsx', [
    ('>Reset<', ">{t('common.reset')}<", 1),
    ('>UNION:<', ">{t('deck.union_label')}<", 1),
    ('>INTERSECTION:<', ">{t('deck.intersection_label')}<", 1),
    ('>No cards in common<', ">{t('deck.compare_none')}<", 1),
    ('>Select at least 2 decks to compare.<', ">{t('decks.compare_select')}<", 1),
    ('title="Compare Decks"', "title={t('decks.compare_title')}", 1),
    ('label="Comparing decks..."', "label={t('deck.compare_loading')}", 1),
    ('title="Overlap Matrix"', "title={t('decks.compare_overlap')}", 1),
    ('title="Common Cards"', "title={t('decks.compare_common')}", 1),
    ('title="Unique Cards"', "title={t('decks.compare_unique')}", 1),
])

add('src/components/BackToTop.tsx', [
    ('aria-label="Back to top"', "aria-label={t('common.back_to_top')}", 1),
    ('title="Back to top"', "title={t('common.back_to_top')}", 1),
])
add('src/components/CardmarketButton.tsx', [
    ('content="Open on Cardmarket"', "content={t('common.open_cardmarket')}", 1),
])
add('src/components/PriceTrendHover.tsx', [
    ('>No price history<', ">{t('price.no_history')}<", 1),
    ('>MTGStocks · 1y (USD)<', ">{t('price.mtgstocks')}<", 1),
])
add('src/components/cardmarket/CardmarketWorkflowBanner.tsx', [
    ('>Hide<', ">{t('common.hide')}<", 1),
    ('>Cardmarket has no official sync API for stocks — updates work via CSV roundtrips:<',
     ">{t('cardmarket.workflow_intro')}<", 1),
    ('>Downloads your current stock list<', ">{t('cardmarket.workflow_step1_hint')}<", 1),
    ('>Updates your listings in this add-on<', ">{t('cardmarket.workflow_step2_hint')}<", 1),
    ('>Edit here (adjust prices, mark cards for sale)<', ">{t('cardmarket.workflow_step3')}<", 1),
    ('>CSV with your changes, ready for re-import on Cardmarket<',
     ">{t('cardmarket.workflow_step4_hint')}<", 1),
    ('>On Cardmarket: use browser extension or MKM API for bulk updates (power users)<',
     ">{t('cardmarket.workflow_step5')}<", 1),
])
add('src/components/cardmarket/ListingHealthPanel.tsx', [
    ('>Refresh<', ">{t('common.refresh')}<", 1),
    ('>No listings in this category.<', ">{t('cardmarket.health_empty')}<", 1),
    ('>Card<', ">{t('common.card')}<", 1),
    ('>My Price<', ">{t('col.my_price')}<", 1),
    ('>Trend<', ">{t('col.trend')}<", 1),
    ('>Suggested<', ">{t('col.suggested')}<", 1),
    ('label="Analyzing listings..."', "label={t('cardmarket.health_loading')}", 1),
])
add('src/components/deck/AIAssessmentBox.tsx', [
    ('>No AI assessment yet. Ask the MCP assistant to analyze this deck.<', ">{t('ai.empty')}<", 1),
])
add('src/components/deck/ComboDetailDialog.tsx', [
    ('>PARTIAL<', ">{t('combo.partial')}<", 1),
    ('>CARDS INVOLVED<', ">{t('combo.cards_involved')}<", 1),
    ('>MISSING CARDS<', ">{t('combo.missing_cards')}<", 1),
    ('>RESULT<', ">{t('combo.result')}<", 1),
    ('>PREREQUISITES<', ">{t('combo.prerequisites')}<", 1),
    ('>STEPS<', ">{t('combo.steps')}<", 1),
    ('>View on Commander Spellbook ↗<', ">{t('combo.spellbook_link')}<", 1),
])
add('src/components/deck/DeckCombosSection.tsx', [
    ('>No combos cached yet.<', ">{t('decks.combos_empty')}<", 1),
    ('>No complete combo in this deck<', ">{t('combo.none_complete')}<", 1),
    ('>No partial combos detected<', ">{t('combo.none_partial')}<", 1),
])
add('src/components/deck/DeckCompletenessSection.tsx', [
    ('title="Deck Completeness"', "title={t('decks.completeness')}", 1),
])
add('src/components/deck/GameplanBox.tsx', [
    ('>No gameplan set<', ">{t('gameplan.empty')}<", 1),
    ('>Gameplan<', ">{t('gameplan.title')}<", 1),
    ('>Cancel<', ">{t('common.cancel')}<", 1),
    ('>Save<', ">{t('common.save')}<", 1),
])
add('src/components/deck/DeckPerformanceSection.tsx', [
    ('>Log game<', ">{t('perf.log_game')}<", 1),
    ('>No games logged yet. Track how your deck performs after each game.<', ">{t('perf.empty')}<", 1),
    ('>Log a game<', ">{t('perf.log_a_game')}<", 1),
    ('>Win<', ">{t('perf.win')}<", 1),
    ('>Loss<', ">{t('perf.loss')}<", 1),
    ('>Draw<', ">{t('perf.draw')}<", 1),
    ('>Cancel<', ">{t('common.cancel')}<", 1),
    ('title="Deck Performance"', "title={t('perf.title')}", 1),
    ('label="Win rate"', "label={t('perf.win_rate')}", 1),
    ('label="W / L / D"', "label={t('perf.wld')}", 1),
    ('label="Recent form"', "label={t('perf.recent_form')}", 1),
    ('label="On-play win%"', "label={t('perf.on_play_win')}", 1),
    ('label="Avg mulligans"', "label={t('perf.avg_mulligans')}", 1),
    ('label="Avg missed lands"', "label={t('perf.avg_missed_lands')}", 1),
    ('label="Avg turns"', "label={t('perf.avg_turns')}", 1),
    ('aria-label="Delete game"', "aria-label={t('perf.delete_game')}", 1),
    ('label="Result"', "label={t('common.result')}", 1),
    ('label="Date"', "label={t('common.date')}", 1),
    ('label="On the play"', "label={t('perf.on_the_play')}", 1),
    ('label="Pod size"', "label={t('perf.pod_size')}", 1),
    ('label="Mulligans"', "label={t('perf.mulligans')}", 1),
    ('label="Missed lands"', "label={t('perf.missed_lands')}", 1),
    ('label="Turns"', "label={t('perf.turns')}", 1),
    ('label="Opponents / commanders"', "label={t('perf.opponents')}", 1),
    ('placeholder="e.g. Atraxa, Krenko"', "placeholder={t('perf.opponents_hint')}", 1),
    ('label="What worked"', "label={t('perf.what_worked')}", 1),
    ('label="What didn\'t"', "label={t('perf.what_didnt')}", 1),
    ('label="Notes"', "label={t('wishlist.notes_label')}", 1),
])
add('src/components/deck/DeckPowerSection.tsx', [
    ('>Not scored yet.<', ">{t('power.not_scored')}<", 1),
    ('>Impact by mana value<', ">{t('power.by_mana_value')}<", 1),
    ('>Carrying the score<', ">{t('power.carrying')}<", 1),
    ('>Check against edhpowerlevel.com ↗<', ">{t('power.reference')}<", 1),
    ('title="Power"', "title={t('power.title')}", 2),
    ('label="Score"', "label={t('power.score')}", 1),
    ('label="Power level"', "label={t('power.level')}", 1),
    ('label="Efficiency"', "label={t('power.efficiency')}", 1),
    ('label="Tipping point"', "label={t('power.tipping_point')}", 1),
    ('label="Avg. cost"', "label={t('power.avg_cost')}", 1),
])
add('src/components/deck/UserBracketBadge.tsx', [
    ('>YOUR BRACKET · overrides the computed one<', ">{t('bracket.your_bracket')}<", 1),
    ('>Computed from the decklist:<', ">{t('bracket.computed_from')}<", 1),
    ('>why?<', ">{t('common.why')}<", 1),
    ('>No game changers, no complete two-card combo, no mass land denial, no extra-turn plan.<',
     ">{t('bracket.nothing_found')}<", 1),
    ('title="Clear — fall back to the computed bracket"', "title={t('bracket.clear')}", 1),
    ('title="What put this deck in that bracket"', "title={t('bracket.explain')}", 1),
])
add('src/components/inbox/AcquisitionCard.tsx', [
    ('>You already own:<', ">{t('inbox.already_own')}<", 1),
])
add('src/components/inbox/InboxHistory.tsx', [
    ('>Suggestion shown at confirmation<', ">{t('inbox.history.suggestion_shown')}<", 1),
    ('>State at that time<', ">{t('inbox.history.state_then')}<", 1),
    ('>Other copies owned then<', ">{t('inbox.history.copies_then')}<", 1),
    ('aria-label="Decision filter"', "aria-label={t('inbox.history.filter')}", 1),
    ('label="Loading history..."', "label={t('inbox.history.loading')}", 1),
])
add('src/components/inbox/TriageDecisionDialog.tsx', [
    ('>Price (EUR)<', ">{t('common.price_eur')}<", 1),
    ('>Condition<', ">{t('common.condition')}<", 1),
    ('>Language<', ">{t('common.language')}<", 1),
    ('<option value="English">English</option>', '<option value="English">{t(\'lang.English\')}</option>', 1),
    ('<option value="German">German</option>', '<option value="German">{t(\'lang.German\')}</option>', 1),
    ('<option value="French">French</option>', '<option value="French">{t(\'lang.French\')}</option>', 1),
    ('<option value="Italian">Italian</option>', '<option value="Italian">{t(\'lang.Italian\')}</option>', 1),
    ('<option value="Spanish">Spanish</option>', '<option value="Spanish">{t(\'lang.Spanish\')}</option>', 1),
    ('<option value="Japanese">Japanese</option>', '<option value="Japanese">{t(\'lang.Japanese\')}</option>', 1),
    ('>Copy to sell<', ">{t('triage.copy_to_sell')}<", 1),
    ('>Create Listing<', ">{t('triage.create_listing')}<", 1),
])
add('src/components/settings/MCPSetupSection.tsx', [
    ('>MCP Setup for Claude Desktop<', ">{t('mcp.title')}<", 2),
    ('>Add-on reachable<', ">{t('mcp.reachable')}<", 1),
    ('>Auth-Token erforderlich<', ">{t('mcp.token_required')}<", 1),
    ('>Step 1:<', ">{t('mcp.step', { n: 1 })}<", 1),
    ('>Step 2:<', ">{t('mcp.step', { n: 2 })}<", 1),
    ('>Step 3:<', ">{t('mcp.step', { n: 3 })}<", 1),
    ('>Step 4:<', ">{t('mcp.step', { n: 4 })}<", 1),
    ('>Step 5:<', ">{t('mcp.step', { n: 5 })}<", 1),
    ('>Step 6:<', ">{t('mcp.step', { n: 6 })}<", 1),
    ('>Download proxy file<', ">{t('mcp.step1')}<", 1),
    ('>Create a Long-Lived Access Token<', ">{t('mcp.step2')}<", 1),
    ('>In Home Assistant: Profile → Security → Long-Lived Access Tokens → Create Token<',
     ">{t('mcp.step2_hint')}<", 1),
    ('>Paste config into Claude Desktop<', ">{t('mcp.step3')}<", 1),
    ('>Config file location<', ">{t('mcp.step4')}<", 1),
    ('>Show paths per OS<', ">{t('mcp.show_paths')}<", 1),
    ('>Replace placeholders in the config<', ">{t('mcp.step5')}<", 1),
    ('>Restart Claude Desktop<', ">{t('mcp.step6')}<", 1),
    ('>After saving the config, fully quit and reopen Claude Desktop.<', ">{t('mcp.step6_hint')}<", 1),
])
add('src/components/wishlist/CardNameAutocomplete.tsx', [
    ('placeholder="Card name..."', "placeholder={t('wishlist.card_name_placeholder')}", 1),
])
add('src/components/wishlist/PrioritySelector.tsx', [
    ('label="Priority"', "label={t('wishlist.priority_label')}", 1),
])
add('src/components/wishlist/SetSelector.tsx', [
    ('>Could not load printings. Proceed without set.<', ">{t('wishlist.printings_failed')}<", 1),
    ('>Any printing<', ">{t('common.any_printing')}<", 1),
    ('label="Loading printings..."', "label={t('common.loading_printings')}", 1),
    ('placeholder="Any printing"', "placeholder={t('common.any_printing')}", 1),
    (": 'Any printing'}", ": t('common.any_printing')}", 1),
    ('label="Foil"', "label={t('cards.foil')}", 1),
])
add('src/components/wishlist/WishlistAcquireDialog.tsx', [
    ('>Any printing<', ">{t('common.any_printing')}<", 1),
    ('>Cancel<', ">{t('common.cancel')}<", 1),
    ('label="Paid Price (EUR)"', "label={t('wishlist.paid_price')}", 1),
    ('placeholder="e.g. 12.50"', "placeholder={t('common.example_price')}", 1),
    ('label="Source"', "label={t('common.source')}", 1),
    ('placeholder="Select source (optional)"', "placeholder={t('wishlist.select_source')}", 1),
    ('label="Set / Version"', "label={t('common.set_version')}", 1),
    ('placeholder="Select printing"', "placeholder={t('common.select_printing')}", 1),
    ('label="Foil"', "label={t('cards.foil')}", 1),
])
add('src/components/wishlist/WishlistAddForm.tsx', [
    ('>No deck<', ">{t('wishlist.no_deck')}<", 1),
    ('label="Card"', "label={t('common.card')}", 1),
    ('label="Quantity"', "label={t('common.quantity')}", 1),
    ('label="Target Price (EUR)"', "label={t('wishlist.target_price')}", 1),
    ('placeholder="0 = no alert"', "placeholder={t('wishlist.no_alert')}", 1),
    ('label="Priority"', "label={t('wishlist.priority_label')}", 1),
    ('label="Deck"', "label={t('wishlist.deck_label')}", 1),
    ('placeholder="No deck"', "placeholder={t('wishlist.no_deck')}", 1),
    ('label="Tags"', "label={t('wishlist.tags_label')}", 1),
    ('placeholder="modern, priority-upgrade"', "placeholder={t('wishlist.tags_placeholder')}", 1),
    ('label="Notes"', "label={t('wishlist.notes_label')}", 1),
    ('placeholder="Optional notes..."', "placeholder={t('wishlist.notes_placeholder')}", 1),
])
add('src/components/wishlist/WishlistEditDialog.tsx', [
    ('>Any printing<', ">{t('common.any_printing')}<", 1),
    ('label="Set / Version"', "label={t('common.set_version')}", 1),
    ('placeholder="Any printing"', "placeholder={t('common.any_printing')}", 1),
    ('label="Foil"', "label={t('cards.foil')}", 1),
    ('placeholder="modern, priority-upgrade"', "placeholder={t('wishlist.tags_placeholder')}", 1),
])
add('src/components/wishlist/WishlistFilterBar.tsx', [
    ('placeholder="Color"', "placeholder={t('collection.colour')}", 1),
    ('placeholder="Ordered"', "placeholder={t('wishlist.filter_ordered')}", 1),
    ('label="No target price"', "label={t('wishlist.no_target_filter')}", 1),
])
add('src/components/wishlist/WishlistItemRow.tsx', [
    ('>not set<', ">{t('wishlist.no_target_short')}<", 1),
    ('>Game Changer<', ">{t('wishlist.game_changer')}<", 1),
    ('title="No target price set — this card can never show up as a deal"',
     "title={t('wishlist.no_target_hint')}", 1),
    ('title="On the official WotC Game Changers list"', "title={t('wishlist.game_changer_hint')}", 1),
    ('aria-label="Actions"', "aria-label={t('common.actions')}", 1),
])
add('src/components/wishlist/WishlistList.tsx', [
    ('label="Group by name"', "label={t('wishlist.group_by_name')}", 1),
])
add('src/components/wishlist/WishlistOrderDialog.tsx', [
    ('>Any printing<', ">{t('common.any_printing')}<", 1),
    ('>Cancel<', ">{t('common.cancel')}<", 1),
    ('label="Expected Price (EUR)"', "label={t('wishlist.expected_price')}", 1),
    ('placeholder="e.g. 12.50"', "placeholder={t('common.example_price')}", 1),
    ('label="Set / Version"', "label={t('common.set_version')}", 1),
    ('placeholder="Select printing"', "placeholder={t('common.select_printing')}", 1),
    ('label="Foil"', "label={t('cards.foil')}", 1),
])


def substitute(text: str, old: str, new: str) -> tuple[str, int]:
    """
    Replace `old` with `new`, tolerating the line breaks JSX puts around text.

    A literal written as `>Cancel<` in the table also has to match

        >
          Cancel
        </Button>

    which is how the formatter leaves anything longer than the print width.
    The surrounding whitespace is preserved, so the diff stays readable and
    the JSX keeps its indentation.
    """
    if old.startswith('>') and old.endswith('<'):
        body = re.escape(old[1:-1])
        pat = re.compile(r'>(\s*)' + body + r'(\s*)<')
        n = len(pat.findall(text))
        if n:
            text = pat.sub(lambda m: '>' + m.group(1) + new[1:-1] + m.group(2) + '<', text)
        return text, n
    n = text.count(old)
    return (text.replace(old, new) if n else text), n


def main() -> int:
    apply = '--apply' in sys.argv
    misses: list[str] = []
    per_file: dict[str, list[tuple[str, str, int]]] = {}
    for path, old, new, n in E:
        per_file.setdefault(path, []).append((old, new, n))

    changed = 0
    done = 0
    for path, pairs in per_file.items():
        full = os.path.join(ROOT, path)
        if not os.path.exists(full):
            misses.append(f'{path}: file missing')
            continue
        text = original = io.open(full, encoding='utf-8').read()
        for old, new, want in pairs:
            candidate, got = substitute(text, old, new)
            if got != want:
                misses.append(f'{path}: {got}x (want {want}x)  {old[:70]}')
                continue
            text = candidate
            done += 1
        if text != original:
            changed += 1
            if apply:
                io.open(full, 'w', encoding='utf-8', newline='\n').write(text)

    print(f'Dateien mit Ersetzungen: {changed}   Ersetzungen: {done}/{len(E)}')
    if misses:
        print(f'\n{len(misses)} NICHT ERSETZT:')
        for m in misses:
            print('  ' + m)
    print('\n(dry run — mit --apply schreiben)' if not apply else '\ngeschrieben.')
    return 1 if misses else 0


if __name__ == '__main__':
    sys.exit(main())
