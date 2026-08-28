# Sprint 07 — HA-Brücke begradigen

**Status: ✅ umgesetzt und deployed am 2026-08-28** (Add-on 0.41.0 + HA-Seite live).
Ist-Protokoll am Ende.

**Ziel:** Die HA-Seite (Repo `ha-infrastructure`) und die MQTT-Publikation auf denselben
Wahrheitsstand bringen wie das Add-on.

**Warum (Befunde):** B9, B29–B31, W9, W10, B10 in [review-befunde.md](review-befunde.md).

## Umgesetzt — Add-on (0.41.0)

| # | Paket | Datei |
|---|---|---|
| 1 | **W10:** Attribute werden **vor** dem State publiziert. HA-Automationen triggern auf den State und lesen dann die Attribute — der Inbox-Push zog die oberste Karte aus `items`, sobald der pending-Zähler sprang, und konnte in dem Fenster eine veraltete `event_id` einbacken. Ein Test hält die Reihenfolge fest, **gegengeprüft: er fällt auf der alten** | `services/ha_publisher.py`, `tests/test_ha_discovery.py` |
| 2 | **B15:** `TOP_N` 10 → 25. Die Kappung war nie gemessen: alle 128 MTG-Entities zusammen 40,8 KiB Attribute, schwerste Einzel-Payload 2,2 von ~16 KiB | `services/ha_metrics.py` |

## Umgesetzt — Repo `ha-infrastructure`

| # | Paket | Datei |
|---|---|---|
| 3 | **B30:** `DASHBOARDS` um das Hauptdashboard erweitert. Es trug denselben MTG-Block wie `home_desktop`, wurde aber von keinem Werkzeug gepflegt — der nächste `--apply` hätte die beiden auseinanderlaufen lassen | `tools/patch-mtg-gameroom.py` |
| 4 | **B31:** die veraltete „nicht belastbar / Stand 2026-07-22"-Warnkarte durch **Definitionen** der drei Verkaufszahlen ersetzt; `mtg_verkauf_wochenreport` zurück auf `sell_potential_eur`, „ABWEICHUNG VOM SPRINT" raus | `tools/patch-mtg-gameroom.py`, `pi-ha/config/automations.yaml` |
| 5 | **W9:** „Tauschen" fällt nicht mehr in den `default`-Zweig, sondern teilt sich den Preis-Zweig mit „Verkaufen" | `pi-ha/config/scripts.yaml` |
| 6 | **0.35.0-Nacharbeit:** die `last_sync_at`-Warnung aus allen drei Dashboards entfernt — der Sensor liefert seit 0.35.0 `2026-08-28T07:08:15+00:00` | `tools/patch-mtg-gameroom.py` |
| 7 | **B9:** `rename-mtg-entities.py` benennt jetzt **musterbasiert über die `unique_id`** um; 75 Entities gezogen, auto-entities-Wildcards auf **ein** Muster je Gruppe vereinfacht | `tools/rename-mtg-entities.py`, `tools/patch-mtg-gameroom.py` |
| 8 | **B10:** CLAUDE.md nachgezogen (Version, alle vier Add-on-Fehler zu, die drei Verkaufszahlen erklärt, Entity-IDs, `items`-Kappung, Verweis auf diesen Sprint-Ordner) | `CLAUDE.md` |

### Die Gegenprobe, die der Sprint verlangt hat (B31)

Die drei Zahlen sind **nicht drei Versuche derselben Messung**, sondern drei Messungen:

| Sensor | live | was es misst |
|---|---:|---|
| `sell_potential_eur` | 1.817 € | Empfehlung des Verkaufsberaters, gewichtet nach Preisanstieg. Zählt **ungenutzte** Exemplare (Besitz − Deckverwendung) |
| `duplicates_surplus_value_eur` | 1.063 € | Wert aller Exemplare über den Deckbedarf hinaus |
| `unlisted_value_eur` | 915 € | der Teil davon, der noch nicht bei Cardmarket steht — immer ≤ Überschuss |

Damit ist die Rangfolge erklärt und die Warnkarte hinfällig. **Und der Rückschalter ist besser
begründet als im Sprint-Text:** dort hieß es „der Quadrier-Fehler ist mit 0.33.0 behoben, also
zurück". Richtig — aber der eigentliche Grund ist, dass `duplicates_surplus` und `unlisted_value`
laut W5 **derzeit zu hoch** stehen (deckgebundene Exemplare zählen mit, Fix in Sprint 09), während
`sell_potential` davon nicht betroffen ist. Der Wochenreport hängt jetzt an der belastbareren Zahl
und nennt den Rückstand nur noch als **Obergrenze**.

### Was beim Umsetzen dazukam

**🐞 `patch-mtg-gameroom.py` war auf Windows unbenutzbar.** Es las die Dashboard-JSONs mit
`open(local)` ohne `encoding` — auf Windows ist der Default cp1252, und die Dateien sind UTF-8. Der
Lauf brach beim ersten Emoji ab. Schlimmer wäre der Schreibpfad gewesen: `open(out, "w")` hätte die
gepatchte Config in cp1252 geschrieben. Beide Stellen sind jetzt explizit.

**🐞 Eine Automation lag nur live vor, nicht im Repo.** Der Pflicht-Vergleich vor dem `scp` (58 live
gegen 57 im Repo) förderte `automation.tag_gassi_gehen_is_scanned` zutage — den in CLAUDE.md
geführten UI-Stub am gelöschten Vorgänger-Tag, der als Testaktion das Wohnzimmerlicht toggelte. Alle
57 gemeinsamen Automationen waren inhaltlich identisch. Der Deploy hat den Stub entfernt; der
Registry-Waise ist gleich mit weg.

**Die `unique_id` ist die Wahrheit für die Ziel-ID.** Der Sprint schlug vor, `…_wishlist_<slug>` auf
`…_wishlist_<id>` zu ziehen — also den Slug zu parsen. Die Registry gibt aber die `unique_id` aus,
und das Add-on setzt dort exakt die Ziel-ID (`mtg_wishlist_131` → `sensor.mtg_wishlist_131`). Kein
Raten, kein Sonderfall für Karten mit Komma im Namen.
⚠️ Die `unique_id` wird dabei **nur gelesen** — sie zu ändern hieße, die Entity zu verlieren
(Falle 4 des Hausbuchs).

## Akzeptanz / Verifikation

- [x] **`--apply` ändert alle drei Dashboards**, und die MTG-Blöcke von `dashboard` und
  `home_desktop` sind byteidentisch (13.599 Zeichen). Gegenprobe vor dem Push: **alle anderen
  Views byteidentisch zum Live-Stand** — geprüft je Dashboard.
- [x] **75 Entities umbenannt**, zweiter Lauf meldet 0 (idempotent). Danach live: **74 Wishlist- und
  1 Deck-Sensor unter den neuen IDs, 0 unter den alten**; der `is_deal`-Filter findet weiter
  5 Einträge.
- [x] **„Tauschen"** schickt jetzt `listing_preis_eur` mit. Am Add-on gegengeprüft, dass genau das
  gefehlt hat: `routers/acquisitions.py:320` verlangt es für `sold_new` **und** `swap`; `source`
  setzt der MQTT-Handler selbst (`_service_triage`), das war **nicht** die Ursache.
- [x] **Attribut-Reihenfolge** durch einen Test gesichert, der auf der alten Reihenfolge fällt.
- [x] Add-on **309/311 Tests grün** (die 2 sind der Altbestand `test_static_files.py`).
- [ ] **Der actionable Push mit der richtigen `event_id`** ist nicht end-to-end nachgestellt — dafür
  müsste eine echte Triage-Entscheidung auf der Live-Inbox getroffen werden. Die Ursache ist
  behoben und getestet, der Nachweis am lebenden System steht aus.

## Ist-Protokoll (2026-08-28)

| Schritt | Ergebnis |
|---|---|
| Add-on 0.41.0 | `healthz` ok; `items` live auf **25** (vorher 10) — an `sensor.mtg_sell_candidates` und `sensor.mtg_unlisted_value_eur` nachgesehen |
| Dashboards | 3 × deployt (5/5/4 Sektionen — deckt sich mit dem Control-Inventar B29); live 0 alte Wildcards, 0 alte Warnkarten |
| Rename | 75 Entities, zweiter Lauf 0 |
| `sensor.mtg_last_sync_at` | `2026-08-28T07:08:15+00:00` — Sprint 01 hält |
| Snapshots | alle drei `pi-ha/dashboards/*.json` neu gezogen, Diff auf **5 Zeilen ±** statt Volldiff (Formatierung aus dem Bestand abgeleitet statt geraten) |

## Offen

- **Der Nachweis des actionable Push** (siehe Akzeptanz) — braucht eine echte Triage-Entscheidung.
- **Die Anzeigenamen** der 75 umbenannten Entities tragen weiter „MTG Collection Manager MTG
  Wishlist …". Umbenannt wurden nur die IDs; ein Namens-Sweep wäre ein eigener, kosmetischer Lauf.
- **B29s eigentliche Empfehlung ist nicht umgesetzt:** `docs/dashboard-strategie.md` schlägt vor,
  den MTG-Teil „auf eine Sektion einzudampfen, Rest hinter Deep-Link" — von 28 Controls tun 5 etwas,
  10 davon sind Formularfelder des Game-Loggers mit einer erfassten Partie. Das ist eine
  Produktentscheidung, kein Bugfix, und gehört dem Auftraggeber vorgelegt.
