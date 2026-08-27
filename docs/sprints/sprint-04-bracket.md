# Sprint 04 — Bracket: pflegbar + berechnet

**Ziel (Entscheidung Auftraggeber):** Das WotC-Bracket-System bleibt und wird **in der App
pflegbar** — plus eine lokal **berechnete** Einstufung nach den offiziellen Regeln, mit
Begründung. **Braucht Sprint 02 (game_changer/legalities) und Sprint 03 (Combo-Abdeckung).**

**Warum:** B1 (alle 22 Decks Bracket 0), B26 (Archidekt-Quelle doppelt leer), B24/B28 (der
schwierigste Input — 2-Karten-Infinites — liegt gepflegt in `deck_combos` und wird von keiner
Zeile für eine Einstufung benutzt), B27 (24 % der Wunschliste sind Game Changers — die
Bracket-Frage ist real, nicht akademisch), R5 (offizielle Regeln).

## Feld-Semantik — drei Werte, klar getrennt

| Feld | Quelle | Rolle |
|---|---|---|
| `bracket` | Archidekt-Import (`edhBracket`, seit 0.35.0 korrekt gelesen) | reiner Spiegel; heute überall leer |
| `user_bracket` | Hand (existiert: `PUT /decks/{id}/user-fields`, 1–5) | **der gepflegte Wert** — gewinnt immer |
| `computed_bracket` (neu) | lokale Berechnung | Vorschlag mit Begründung |

Anzeige-Vorrang: `user_bracket` → `computed_bracket` → `bracket`. Ein von Hand gesetzter Wert
übersteht jeden Sync (Import schreibt nur `bracket`, nie `user_bracket` — heute schon so).

## Arbeitspakete

1. **Migration:** `decks.computed_bracket INTEGER`, `decks.computed_bracket_detail TEXT (JSON)`.
2. **`services/bracket.py`** — WotC-Regeln (R5), Eingaben komplett lokal:
   - **Game Changers:** `cards.game_changer` (Sprint 02). Anzahl 0 → kompatibel bis B2;
     1–3 → mind. B3; >3 → mind. B4.
   - **2-Karten-Infinites:** `deck_combos` mit `is_partial = 0` und `len(cards) ≤ 2`.
     Early/Late-Trennung: `manaValueNeeded` + Summe der CMCs ≤ 7 = early (early → mind. B4,
     late → mind. B3; Vorbild edhpowerlevel §R2).
   - **Mass Land Denial:** Kartenliste (33 Namen aus R2) + Regex auf `oracle_text` → mind. B4.
   - **Extra Turns:** chainable-Liste (12 Namen) → mind. B4; einzelne Extra-Turn-Karten in
     Menge > 2 → mind. B3.
   - **Tutoren bewusst NICHT** — WotC hat die Limits 10/2025 gestrichen (R2/R5).
   - Ergebnis = max(Untergrenzen); `detail`-JSON nennt **welche Karten/Combos** jede Grenze
     ausgelöst haben (die Begründung ist das Feature, nicht die Zahl).
3. **Recompute-Hook** nach Deck-Sync + Combo-Sync; manuell `POST /decks/{id}/bracket/recompute`.
4. **Gegenprobe je Deck:** Spellbook `POST /estimate-bracket` (B28 — Combo-Zahlen validieren
   exakt). ⚠️ Zuerst das `bracketTag`-Mapping über `backend.commanderspellbook.com/schema/`
   klären (`E`, `R`, … sind nicht dokumentiert — nicht raten). ⚠️ `gameChanger` NICHT von dort
   nehmen (bewertet nur Karten aus der Spellbook-DB, 34/87 bei Deck 5) — lokales Feld benutzen.
5. **UI:**
   - `UserBracketBadge` ausbauen: effektiver Bracket (Vorrangkette) + Klick-Picker 1–5 zum
     **Pflegen** — prominent in DeckView **und** Decks-Liste (heute nur DeckView).
   - Begründungs-Popup: „mind. Bracket 4: 2-Karten-Combo Kiki-Jiki + Deceiver Exarch" etc.
   - Decks-Filter „All Brackets" auf den effektiven Bracket umstellen.
   - „Compare Decks"-Einstieg vom Archidekt-Bracket entkoppeln (ungeprüfter Hinweis: der einzige
     Einstieg ist heute unsichtbar, weil kein Deck einen Archidekt-Bracket hat — verifizieren).
6. **HA:** `computed_bracket` + effektiver Bracket als Attribute an den Deck-Sensoren
   (`ha_publisher.publish_deck_sensors`).

## Akzeptanz

- Deck 5 „Emerald Hill Zone, Fast!" → mind. Bracket 4 (Kiki-Combo), Begründung nennt die Combo.
- Deck 13 „Turtle Power!" (Precon, 0 Combos, 0 GC) → Bracket ≤ 2.
- Deck 2 → Begründung nennt Death Cloud (MLD) und die 12 vollständigen Combos.
- Von Hand gesetzter `user_bracket` = 3 bleibt nach einem Voll-Sync stehen und gewinnt die Anzeige.

## Verifikation

- Alle 22 Decks: `computed_bracket` + Spellbook-`bracketTag` nebeneinander dokumentieren;
  Abweichungen erklären (lokal hat vollständige Kartensicht, Spellbook nicht).
- Unit-Tests für `services/bracket.py` mit konstruierten Decklisten (GC-Grenzen 0/3/4, early
  vs. late Combo, MLD).
