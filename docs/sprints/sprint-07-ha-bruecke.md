# Sprint 07 — HA-Brücke begradigen

**Ziel:** Die HA-Seite (Repo `ha-infrastructure`) und die MQTT-Publikation auf denselben
Wahrheitsstand bringen wie das Add-on. Unabhängig von anderen Sprints; enthält die aus Sprint 01
verschobenen HA-Pakete.

**Warum:** B9, B29–B31, W9, W10, B10 in [review-befunde.md](review-befunde.md).

## Arbeitspakete — Add-on-Seite

1. **W10:** Publikationsreihenfolge in `_publish_metrics` (`ha_publisher.py:250-257`) drehen —
   **Attribute vor State** publizieren. Der HA-State-Trigger feuert dann erst, wenn die
   `items`-Attribute schon aktuell sind; der actionable Push kann keine veraltete `event_id`
   mehr einbacken.
2. **B15 (optional, billig):** `items`-Kappung der Inbox-/Sell-Sensoren von 10 auf 25 erhöhen —
   gemessene Attributlast erlaubt es locker (max 2,2 KiB von 16 KiB); die Dashboard-Tabellen
   zeigen dann „25 von 137" statt „10 von 137".

## Arbeitspakete — Repo `ha-infrastructure`

3. **B30:** `tools/patch-mtg-gameroom.py` → `DASHBOARDS` um das Haupt-Dashboard (`dashboard`,
   Storage-Key `lovelace.dashboard`) erweitern. Der MTG-Block dort ist heute byteidentisch zu
   `home_desktop` — nach dieser Änderung bleibt er es auch.
4. **B31:** Gegenprobe der drei Verkaufszahlen (Code hinter `sell_potential_eur` = 1817 € /
   `unlisted_value_eur` = 937 € / `duplicates_surplus_value_eur` = 1073 € lesen und die
   Differenzen erklären — Achtung: W5 sagt, die Duplicates-Zahl ist überhöht, Fix in Sprint 09).
   Dann: veraltete „nicht belastbar / Stand 2026-07-22"-Warnkarte durch neutrale
   Definitions-Zeilen ersetzen; `mtg_verkauf_wochenreport`-Trigger von `unlisted_value_eur`
   zurück auf `sell_potential_eur` stellen (der dokumentierte Rückkehrgrund ist erfüllt),
   „ABWEICHUNG VOM SPRINT"-Kommentar entfernen.
5. **W9:** „Tauschen"-Knopf in `script.mtg_triage_oberste`: swap-Zweig wie den sold_new-Zweig
   bauen (Preis aus dem Eintrag mitgeben, bei Preis 0 abbrechen) — `swap` verlangt
   `listing_price_eur`, sonst 422 ins Leere. Alternativ den Knopf entfernen (Entscheidung beim
   Umsetzen; der Vorschlag der App ist ohnehin selten `swap`).
6. **0.35.0-Nacharbeit:** `last_sync_at`-Warnkarte („liefert nichts, obwohl completed") aus
   allen drei Dashboards entfernen, sobald der Sensor verifiziert Werte zeigt; die
   Sync-Status-Markdown auf den Normalfall reduzieren.
7. **B9:** `tools/rename-mtg-entities.py` um musterbasierte Behandlung erweitern:
   `sensor.mtg_collection_manager_mtg_wishlist_<slug>` → `sensor.mtg_wishlist_<id>` und
   `sensor.mtg_collection_mtg_deck_*_win_rate` → `sensor.mtg_deck_<id>_winrate`.
   ⚠️ Registry gewinnt über Discovery-`object_id`; nur `new_entity_id` setzen, nie `unique_id`
   (Falle 4 des Hausbuchs). Die alten namensbasierten IDs stammen aus einer Vor-Version — nach
   dem Rename die auto-entities-Wildcards in den Dashboards auf **ein** Muster vereinfachen.
8. **B10:** CLAUDE.md (ha-infrastructure) nachziehen: Add-on-Version, `notify_min_alert_value_eur`
   ist zurückgestellt (5.0 — der „offene Punkt" ist erledigt), `last_sync_at` behoben,
   Alert-/Sell-Zahlen neu bewertet, MTG-Abschnitt auf diesen Sprint-Ordner verweisen.

## Deploy-Reihenfolge

Add-on zuerst (1–2, neue Version), dann HA-Seite (3–7: Live-Dateien holen → semantisch
vergleichen → patchen → `ha_ws.py`-Push bzw. `scp` + `automation.reload`/`script.reload` →
Snapshots neu ziehen → committen). CLAUDE.md zuletzt (8).

## Akzeptanz / Verifikation

- Actionable Push nach einer Test-Triage trägt die `event_id` der tatsächlich obersten Karte.
- `--apply` von patch-mtg-gameroom.py ändert alle **drei** Dashboards; Gegenprobe: MTG-Blöcke
  byteidentisch.
- „Tauschen" auf der obersten Karte erzeugt eine Listing-Zeile (oder der Knopf ist weg).
- `rename`-Lauf: 75 Entities umbenannt, auto-entities-Karten zeigen weiter alle Einträge.
