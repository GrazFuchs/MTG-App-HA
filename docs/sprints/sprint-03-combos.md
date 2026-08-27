# Sprint 03 — Combo-Abdeckung reparieren

**Ziel:** Der Combo-Cache (`deck_combos`) wird vollständig und ehrlich: alle Decks erfasst,
`missing_cards` befüllt, Fehler sichtbar. **Voraussetzung für Sprint 04 (Bracket) und die
Wishlist-Brücke in Sprint 06.**

**Warum (Befunde, alle gemessen):** B24 — 484 Combos gecacht, nur 15 vollständig; **14 von 19
Decks haben `[]`** (nur ab 2026-06-04 synchronisierte Decks haben Daten); **`missing_cards` ist
auf allen 469 Teil-Combos leer**; Deck 1 zeigt 27 Combos, von denen keine im Deck vollständig ist.
Spellbook `/estimate-bracket` bestätigt die vollständigen Zählungen exakt (B28) — die Datenquelle
stimmt, die Erfassung ist lückenhaft.

## Arbeitspakete

1. **Ursache der Lücke verifizieren** (`services/sync_service.py` `_do_full_sync` +
   `services/combo_sync.py`): Hypothese — der inkrementelle Sync überspringt unveränderte Decks
   und damit auch deren Combo-Sync; „best effort" schluckt Fehler still (Deck 20 wurde am
   2026-06-04 synchronisiert und hat trotzdem 0). Erst Befund festhalten, dann fixen.
2. **Fehler loggen statt schlucken** — ein gescheiterter Combo-Sync gehört mit Deck-ID und
   Ursache ins Log (`logger.warning`), nicht ins Nichts.
3. **Nachziehen des Bestands:** Einmal-Lauf über alle Decks (`POST /decks/{id}/combos/sync`
   existiert schon — Schleife im Startup-/Sync-Pfad oder Admin-Endpunkt `POST /combos/sync-all`).
   Combo-Sync auch für **unveränderte** Decks ausführen, wenn `deck_combos` für das Deck leer ist
   oder `cached_at` älter als N Tage.
4. **`missing_cards` befüllen** (`clients/spellbook.py`): der Client verwirft heute die
   `almostIncluded*`-Buckets der `/find-my-combos`-Antwort (ungeprüfter Audit-Hinweis — beim
   Umbau verifizieren). `almostIncluded` → `is_partial=1` + `missing_cards_json` mit den
   fehlenden Kartennamen. Buckets `almostIncludedByAddingColors` bewusst weglassen (andere
   Color Identity = kein realistischer Vorschlag).
5. **UI ehrlich machen** (`components/deck/DeckCombosSection.tsx`): „Im Deck vorhanden" (n) und
   „Eine Karte entfernt" (m) als getrennte, klar beschriftete Gruppen; vollständige zuerst.
   Teil-Combos zeigen die fehlende(n) Karte(n) als Chip.

## Akzeptanz

- Jedes Deck mit ≥60 Karten hat nach dem Nachzieh-Lauf einen `deck_combos`-Bestand (auch wenn 0
  vollständige — dann eben Teil-Combos) **oder** einen Log-Eintrag mit Fehlerursache.
- Deck 1: `Breath of Fury + Anger` erscheint als „1 Karte entfernt: Breath of Fury".
- Deck 5: 3 vollständige 2-Karten-Infinites klar getrennt von den Teil-Combos.

## Verifikation

- Vorher/Nachher-Zählung je Deck (`GET /decks/{id}/combos`) dokumentieren.
- Stichprobe gegen Spellbook `/find-my-combos` (POST, `{main, commanders}`) — `included` muss
  den `is_partial=0`-Einträgen entsprechen, `almostIncluded` den Teil-Combos mit `missing_cards`.
