# Sprint 06 — Wishlist: Deals & Bracket-Brücke

**Ziel (Auftraggeber-Schwerpunkt B8):** Zuverlässig erkennen und **melden**, wenn eine
Wunschlisten-Karte unter den Wunschpreis fällt — plus die Brücken zu Bracket (Sprint 04) und
Combos (Sprint 03).

**Warum:** B8 (97 % Priorität-Default, 4 Deals bei 74 Einträgen), B27 (ausgerechnet 4 der
teuersten Game Changers haben `target_price_eur = 0` → `is_deal` kann nie feuern), B16
(0/74 Sensoren mit `state_class` → kein Preisverlauf in HA).

## Teil 1 — „Unter Wunschpreis gefallen" melden (braucht nur Sprint 01)

1. **Deal-Erkennung als Ereignis, nicht nur als Flag:** Im Preis-Sync
   (`services/cardmarket_prices.py` nach dem Speichern der Tagespreise) je aktiven
   Wishlist-Eintrag prüfen: `current ≤ target` UND gestern `current > target` (Kante, nicht
   Zustand — sonst feuert es täglich). Dedup nach dem Muster `notification_log`
   (`wishlist_deal_<id>_<date>`).
2. **Benachrichtigung** über die bestehende `services/notifications.py`-Infrastruktur
   (persistent_notification + optional `notify_via_ha_service`): „🎯 Rhystic Study (J22) ist auf
   34,50 € gefallen — Ziel 35 €. [Wunschliste öffnen]" (Ingress-Deep-Link existiert).
3. **`target_price_eur = 0` behandeln:**
   - UI: 0 als „kein Ziel gesetzt" ausweisen (heute sieht es wie ein Preisziel von 0 € aus);
     Hinweis-Chip auf Einträgen ohne Ziel; optionaler Ein-Klick-Vorschlag „85 % vom Trend".
   - `is_deal` bleibt für Ziel 0 aus (korrekt) — aber die Karte darf nicht still unsichtbar
     bleiben: eigener Filter „ohne Preisziel" in der FilterBar.
4. **`state_class` für Wishlist-Sensoren** (`ha_publisher`, Wishlist-Discovery):
   `device_class: monetary` + `state_class: total` (HA erlaubt bei monetary nur `total` — siehe
   B14-Korrektur) → HA führt Langzeitstatistik je Karte, der Preisverlauf wird in HA plottbar.
   ⚠️ Discovery-Update genügt (retained Config neu publizieren); Entity-IDs nicht anfassen.

## Teil 2 — Bracket-Impact (braucht Sprint 04)

5. Je Wishlist-Eintrag: `game_changer`-Flag (aus `cards.game_changer`) als Badge.
6. Bei Deck-Zuordnung (`deck_id` gesetzt): „Hebt *Deck X* von Bracket a → b" berechnen
   (computed_bracket mit/ohne diese Karte — `services/bracket.py` auf hypothetischer Liste).
   Anzeige im `WishlistItemRow` + im Deck-Detail unter „geplante Käufe".

## Teil 3 — Combo-Brücke (braucht Sprint 03)

7. `missing_cards` aus `deck_combos` gegen die Wunschliste spiegeln: „Diese Karte vervollständigt
   ein Infinite in Deck Y" als Badge; umgekehrt im Deck: „1 Karte bis zum Infinite — auf die
   Wunschliste?" (Ein-Klick-Add über den bestehenden `POST /api/wishlist/`).

## Akzeptanz

- Testeintrag mit Ziel über aktuellem Marktpreis → beim nächsten Preis-Sync genau **eine**
  Meldung; am Folgetag ohne Preisänderung keine zweite.
- Eintrag mit Ziel 0 zeigt „kein Ziel gesetzt" statt eines stillen Nichts.
- Rhystic Study (auf der Liste, Game Changer) trägt das GC-Badge; mit Deck-Zuordnung erscheint
  der Bracket-Impact.
- HA: `sensor.mtg_wishlist_*` hat Langzeitstatistik (Verlaufsgraph im More-Info-Dialog).

## Verifikation

- Unit-Test für die Kanten-Erkennung (über/unter/gleich, kein Vortageswert, Ziel 0).
- HA-seitig: `statistics`-Tabelle enthält nach 2 Sync-Läufen Einträge für einen Wishlist-Sensor.
