# Sprint 05 — Power-Level (edhpowerlevel-Port)

**Ziel:** Ein kontinuierlicher Power-Score je Deck (0–1000) + Power-Level (0–10) nach dem
vollständig extrahierten edhpowerlevel-Algorithmus (R2) — offline aus der eigenen `cards`-Tabelle
gerechnet, **getrennt vom Bracket** (R3). **Braucht Sprint 02** (edhrec_rank auffrischen,
type_line-Norm, reserved).

## Arbeitspakete

1. **Migration:** `decks.power_score REAL`, `decks.power_level REAL`, `decks.power_detail TEXT
   (JSON: Impact je Karte, Tipping Point, Efficiency, avgCost)`.
2. **`services/power_level.py`** — Port exakt nach R2 (review-befunde.md):
   - `de()`-Interpolator: Dezil-Index × Gewicht + **ungewichteter** linearer Bruchteil (Falle 1).
   - `factors`-Tabelle wörtlich übernehmen; `popCurve`-Deckel 27.000 → aktuellen Wert von
     Scryfall (`legal:commander`, `total_cards`) ziehen und **danach neu kalibrieren** (Falle:
     verschiebt alle Popularitätswerte).
   - ~90 Karten-Overrides (price/impact/commanderImpact/cmc/producer) als Datentabelle.
   - Länder × 0.6; **Basics NACH dem Faktor pauschal `2 × qty`**; MDFC (`layout='modal_dfc'`)
     zählt als Land und fällt aus avgCost; Reserved-Preis × 0.2 vor der Kurve.
   - Tipping Point (65 % kumulierte Nicht-Land-Impact), `Ce` **ungeklemmt**,
     `X = 0.65 + 0.45·Ce`, `Score = ΣImpact × X`, `PowerLevel = de(Score, powerCurve)`.
   - Eingaben je Karte: `price_usd` (niedrigster), `edhrec_rank`, `cmc`, `type_line`/`layout`,
     `reserved` — alles nach Sprint 02 lokal vorhanden.
3. **Kalibrierung:** 20–30 eigene Decks per Deep-Link (`edhpowerlevel.com?d=<encoded>~Z~`,
   Encoder in R2) durchschicken, Referenzwerte notieren, gegen den Port diffen (±0,1 Toleranz).
   Die 7 Nachbau-Fallen aus R2 sind genau die Stellen, an denen ein Diff auffällt.
4. **Recompute** nach Sync + `POST /decks/{id}/power/recompute` (gemeinsam mit Bracket-Hook).
5. **UI:** Power-Panel in DeckView (Score, Level, Efficiency ×10, Tipping Point,
   Impact-Verteilung je CMC als kleines Chart); Badge in der Decks-Liste. Für Vergleiche den
   **Score** prominent zeigen (Empfehlung des Original-Autors), Level als Übersetzung.
6. **HA:** `power_score`/`power_level` als Attribute an den Deck-Sensoren.

## Bewusste Grenzen (in der UI benennen)

Der Score misst Nachfrage (Preis + Popularität) × Kurveneffizienz — **nicht** Synergie, Combos
oder Konsistenz. Er ist als Vergleichsmaß zwischen echten Decks gebaut und manipulierbar
(Autor-Zitat in R2). Combos/GC/MLD fließen **nur** in den Bracket (Sprint 04), nie in den Score.

## Akzeptanz

- 5 Referenzdecks weichen ≤0,1 Power-Level von edhpowerlevel.com ab (nach popCurve-Angleich).
- Precon (Deck 13) landet spürbar unter den getunten Maxi-Decks.

## Verifikation

- Unit-Tests: `de()` gegen handgerechnete Stützstellen; Basics-Sockel; MDFC-Behandlung;
  Reserved-Dämpfung; ein komplettes Mini-Deck mit bekanntem Referenzwert.
- Kalibrier-Diff-Tabelle in dieses Dokument eintragen (Deck · Referenz · Port · Δ).
