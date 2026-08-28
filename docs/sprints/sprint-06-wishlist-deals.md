# Sprint 06 — Wishlist: Deals & Bracket-Brücke

**Status: ✅ umgesetzt in 0.40.0, deployed + live gemessen am 2026-08-28.** Ist-Protokoll am Ende.

**Ziel (Auftraggeber-Schwerpunkt B8):** Zuverlässig erkennen und **melden**, wenn eine
Wunschlisten-Karte unter den Wunschpreis fällt — plus die Brücken zu Bracket (Sprint 04) und
Combos (Sprint 03).

**Warum (Befunde):** B8, B27, B16 in [review-befunde.md](review-befunde.md).

## Der Kern in einem Satz

`is_deal` gab es die ganze Zeit und es hat nie etwas gemeldet, **weil es ein Zustand ist** — wahr,
solange der Preis unter dem Ziel liegt. Nichts verglich heute mit gestern, also gab es keinen
Moment zu berichten: die Karte war einfach still billig, auf einer Liste von 74, bis jemand
zufällig hinsah. Der Umbau ist die Kante statt des Zustands.

## Umgesetzt

| # | Paket | Datei |
|---|---|---|
| 1 | **Migration 25**: `wishlist.last_price_eur` / `last_price_at` / `deal_notified_at` — der Vergleichspunkt für den nächsten Lauf | `database.py` |
| 2 | **`services/wishlist_deals.py`**: Kanten-Erkennung, Benachrichtigung über die bestehende `notifications`-Infrastruktur, Lauf nach dem täglichen Preis-Sync + `POST /api/wishlist/check-deals` | neu, `scheduler.py`, `routers/wishlist.py` |
| 3 | **Ziel 0 sichtbar machen**: „not set" statt Gedankenstrich, eigener Filter „No target price" | `WishlistItemRow.tsx`, `WishlistFilterBar.tsx`, `routers/wishlist.py` |
| 4 | **Drei Badges**: Game Changer · „Bracket a → b" · „vervollständigt ein Infinite in Deck Y" | `WishlistItemRow.tsx`, `routers/wishlist.py`, `services/bracket.py` |
| 5 | **HA-Langzeitstatistik** für die 74 Wunschlisten-Sensoren | `ha_publisher.py` |
| 6 | Version 0.40.0 + CHANGELOG | — |

### Drei Entscheidungen, die den Ausschlag geben

**(a) Der gemerkte Preis statt der Cardmarket-Historie.** Der Sprint schlug vor, im Preis-Sync
gegen die Vortageszeile in `cardmarket_price_history` zu vergleichen. Live gemessen hat aber
**ein Drittel der Liste gar kein Cardmarket-Produkt** (3 Einträge ganz ohne Preis, viele nur mit
Scryfall-Preis) — die wären damit nie beobachtet worden. Ein Preis je Eintrag deckt beide Quellen
und braucht keinen Join.

**(b) Eine Woche Ruhe nach einer Meldung.** Die Kante allein verhindert die tägliche Wiederholung,
aber ein Preis, der um das Ziel pendelt, überquert es jeden zweiten Tag. Sieben Tage sind die
billigste richtige Antwort; ein Preisband-Modell wäre mehr Erfindung als Nutzen.

**(c) ⚠️ Abweichung vom Sprint-Text bei `state_class`.** Der Sprint verlangte `device_class:
monetary` + `state_class: total`. Das ist genau die Fehldeutung, die **B14 anderswo aufräumen
will**: `total` ist eine laufende Summe, kein Bestandswert. Ohne *irgendeine* `state_class` führt HA
aber gar keine Statistik — der Preisverlauf einer Wunschkarte wäre nicht plottbar, also der ganze
Zweck der 74 Sensoren dahin. Gewählt: **`state_class: measurement` ohne `device_class`**. Das gibt
die ehrliche Aggregation (min/max/mean) und kostet nur die Währungsformatierung. Der bestehende Test
`test_wishlist_entity_shape_unchanged` hielt die alte Entscheidung fest und wurde mit Begründung
umgestellt.

## Akzeptanz

- [x] **Testeintrag über dem Ziel → genau eine Meldung, am Folgetag keine zweite** —
  `test_a_price_crossing_the_target_is_announced_once`, plus der Pendel-Fall.
- [x] **Eintrag mit Ziel 0 zeigt „not set"** statt eines stillen Nichts, und hat einen eigenen Filter.
- [x] **Rhystic Study trägt das Game-Changer-Badge** — live: 12 von 74 Einträgen, exakt die Zahl
  aus B27.
- [x] **HA-Langzeitstatistik** für die Wunschlisten-Sensoren (Discovery neu publiziert;
  Entity-IDs unangetastet).

## Verifikation

- [x] 13 Tests in `tests/test_wishlist_deals.py`: erster Lauf meldet nichts (kein Vergleichspunkt) ·
  Kante wird genau einmal gemeldet · dauerhaft unter dem Ziel ist keine neue Meldung · Preis genau
  auf dem Ziel zählt als erreicht · Pendeln wird gedeckelt · Ziel 0 wird gezählt statt gemeldet ·
  Karte ohne Preis wird als solche ausgewiesen · gekaufter Eintrag wird übergangen · die drei
  Badges · **ein ähnlicher Name darf die Combo nicht beanspruchen** („Anger" ≠ „Anger of the Gods").
- [x] Backend **308/310 grün** (die 2 sind der Altbestand `test_static_files.py`), Frontend-Build grün.

## Ist-Protokoll (2026-08-28, gegen den Pi 5 gemessen)

**Erster Deal-Lauf:** 71 Preise gemerkt, **0 Kanten** — richtig so, es gab noch nichts zu
vergleichen. Nebenbei gemessen: **3 Einträge haben gar keinen Preis**.

| Signal | live |
|---|---|
| Einträge | 74 |
| **Game Changers** | **12** — deckt sich exakt mit B27 |
| **ohne Preisziel** | **25** (B27 nannte nur die vier teuersten) |
| davon Game Changers ohne Ziel | **4**: Smothering Tithe · Orcish Bowmasters · Enlightened Tutor · Thassa's Oracle — **genau die vier aus B27** |
| Combo-Brücke | **7** Einträge |
| Bracket-Wirkung | **0** — und das ist korrekt, siehe unten |

**Die Combo-Brücke ist das überraschend nützliche Stück.** *Helm of the Host* fehlt zu einem
Infinite in **drei** Decks gleichzeitig (Sharknado, Forth Eorlingas, Emerald Hill Zone),
*Time Warp* in Allons-y!, *Underworld Breach* in Surf n Turf. Diese Information gab es vor
Sprint 03 nicht — `missing_cards` war auf allen 469 Teil-Combos leer.

**Warum die Bracket-Wirkung heute nichts anzeigt — nachgemessen, nicht vermutet:** nur **2** der 12
Game Changers sind überhaupt einem Deck zugeordnet, und beide ändern nachweislich nichts.
*Smothering Tithe* → Deck 5, das über zwei frühe Zwei-Karten-Combos **schon Bracket 4** ist (0 Game
Changers). *Field of the Dead* → Deck 20, das **einen** Game Changer hat und damit auf Bracket 3
steht; ein zweiter bleibt unter der Grenze von drei. Die Mechanik ist im Test mit dem 3→4-Fall
belegt; sie hat auf diesen Daten schlicht nichts zu sagen — und schweigt dann auch, statt ein
leeres Badge zu zeigen.

⚠️ **Nebenbefund:** *Smothering Tithe* liegt **im** Deck 20 und steht zugleich als Wunsch für
Deck 5 auf der Liste — ein zweites Exemplar. Die Zuordnung ist also gewollt, nicht verrutscht.

## Offen / bewusst nicht gemacht

- **Die Gegenrichtung der Combo-Brücke** („1 Karte bis zum Infinite — auf die Wunschliste?" mit
  Ein-Klick-Hinzufügen im Deck) ist **nicht** gebaut. Der Weg von der Wunschliste zum Deck ist der,
  den man beim Einkaufen geht; der umgekehrte gehört in die `DeckCombosSection` und ist ein eigenes
  Stück UI-Arbeit.
- **Der Zielpreis-Vorschlag „85 % vom Trend"** ist nicht gebaut — 25 Einträge ohne Ziel sind jetzt
  sichtbar und filterbar, aber sie müssen von Hand gesetzt werden. Ein Vorschlagsknopf wäre der
  nächste Schritt.
- **Die erste echte Deal-Meldung kann frühestens beim nächsten Preis-Sync entstehen**, weil dieser
  Lauf nur den Vergleichspunkt gesetzt hat. Das ist keine offene Arbeit, sondern die Bauart.
