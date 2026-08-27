# Sprint 08 — Inbox/Triage entlasten

**Ziel:** Die 964 Handentscheidungen/Monat (43 % davon „dismiss") drastisch reduzieren — erst an
der Ursache, dann an der Ergonomie. Unabhängig von anderen Sprints.

**Warum (B5):** 137 offen, alle mit `age_days = 0`; ~32 Entscheidungen/Tag; die vier
HA-Dashboard-Knöpfe entscheiden immer nur die oberste Karte (B29); kein `catch` auf dem
Entscheidungspfad; `POST /undo` fertig implementiert und **nirgends angebunden**.

## Stufe 1 — Ursache prüfen (zuerst!)

1. **Phantom-Event-Hypothese verifizieren** (ungeprüfter Audit-Hinweis, `sync_service.py:322` +
   `:287-291`): ein abgebrochener Sync hinterlässt halb-aggregierte Mengen in `collection`; der
   nächste erfolgreiche Sync bucht die Differenz als frische Acquisition. Zusätzlich soll ein
   Condition-/Language-Schlüsselwechsel eine besessene Karte neu einbuchen. Prüfweg:
   `sync_log` auf `partial`/`failed`-Läufe vor Event-Schüben; `acquisition_events` je
   `sync_log_id` clustern; Stichproben gegen Archidekt-`addedAt`.
   **Wenn bestätigt: das ist der eigentliche Fix** — Events nur aus vollständig
   durchgelaufenen Syncs, Schlüsselwechsel als Move statt als Zugang buchen. Bessere Buttons
   kurieren sonst nur das Symptom.
2. Nebenbefund festhalten: `acquisition_events.created_at` = Zeitpunkt der Sync-Erkennung, nicht
   des Erwerbs (Archidekts `addedAt` wird gelesen und verworfen) — erklärt `age_days = 0`.
   Entscheiden, ob `addedAt` übernommen wird (macht `mtg_inbox_liegengeblieben` wieder sinnvoll).

## Stufe 2 — Ergonomie in der Add-on-UI

3. **Fehlerbehandlung auf dem Entscheidungspfad:** `handleDecide` (Inbox.tsx) bekommt
   try/catch + sichtbare Fehlermeldung; die Liste darf nach einer Entscheidung nicht springen
   (Query-Invalidierung ersetzt heute die ganze Seite — optimistisches Entfernen der einen Karte).
4. **Bulk-Triage:** Mehrfachauswahl (Checkbox je Karte + „alle sichtbaren"), Sammelaktion
   dismiss/keep; Filter „unter X €" existiert schon (`min_value_eur`) und wird damit erst nützlich.
   Backend: `POST /acquisitions/bulk-decide` (Liste von event_ids + action) — Schleife über die
   bestehende `decide_triage`-Logik, ein Commit.
5. **Tastatur:** K = keep, D = dismiss, S = sell-Dialog auf der fokussierten Karte.
6. **Undo anbinden:** Nach jeder Entscheidung ein Toast „Entschieden: <Karte> — Rückgängig"
   (8 s), der `POST /acquisitions/{id}/undo` ruft. Macht Bulk + Tastatur risikofrei.

## Stufe 3 — optional, nach Stufe 1

7. Regelbasierte Auto-Dismiss-**Vorschläge** („unter 0,10 € + kein Deck-Bezug + kein Foil") als
   vorausgewählte Bulk-Selektion — nie stumm ausführen.

## Akzeptanz

- Stufe-1-Befund ist im Sprint-Log dokumentiert (bestätigt/widerlegt, mit Zahlen).
- 137 offene Karten lassen sich in < 5 Minuten triagieren (Bulk + Tastatur).
- Eine fehlgeschlagene Entscheidung zeigt eine Meldung; Undo stellt Zustand + ggf. Listing wieder her.

## Verifikation

- Component-Test (nach Sprint 09-Infrastruktur) für: Entscheidung → Karte verschwindet ohne
  Scroll-Sprung; Fehlerpfad zeigt Banner; Undo-Roundtrip.
