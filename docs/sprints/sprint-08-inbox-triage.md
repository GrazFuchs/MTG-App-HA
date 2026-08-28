# Sprint 08 — Inbox/Triage entlasten

**Status: ✅ umgesetzt in 0.43.0, deployed am 2026-08-28.**
⚠️ **Stufe 1 hat die Hypothese WIDERLEGT** — der Sprint macht deshalb etwas anderes als geplant.
Befund und Zahlen unten.

**Ziel (ursprünglich):** Die 964 Handentscheidungen/Monat (43 % davon „dismiss") reduzieren — erst
an der Ursache, dann an der Ergonomie.

**Warum (B5):** in [review-befunde.md](review-befunde.md).

## Stufe 1 — der Befund, und er fällt gegen die Hypothese aus

Der Sprint sagte: *„Wenn bestätigt: das ist der eigentliche Fix — bessere Buttons kurieren sonst nur
das Symptom."* Also zuerst gemessen. **Nichts davon hält.**

| Prüfung | Erwartet laut Hypothese | Gemessen |
|---|---|---|
| Abgebrochene Syncs vor Ereignis-Schüben | mehrere `partial`/`failed` | **141 Läufe, 140 `completed`.** Der eine Fehlschlag ist **Lauf #1** vom 2026-05-02 („No deck IDs configured") — ein Einrichtungsfehler, vor dem ersten Kollektions-Sync |
| Schlüsselwechsel (condition/language) bucht Besitz neu | Wechsel der Darstellung an einem Stichtag | `condition` = `"1"` auf 3152 von 3153 Ereignissen, `language` = `"1"`/`"3"` — **seit Mai unverändert**, kein Stichtag |
| ~32 Entscheidungen/Tag als Dauerlast | gleichmäßiger Strom | **Schübe an ~20 Tagen über vier Monate.** Die zwei jüngsten (je 140 am 13.08. und 22.08.) decken sich exakt mit den zwei Tagen, an denen `items_synced` sprang (+178, +298) — echtes Sammlungswachstum |
| „43 % dismiss" | Grundmuster | Über alle 3153 Ereignisse: **67 % keep, 20 % sold_new, 14 % dismiss.** Die 43 % sind das 30-Tage-Fenster, und in dem liegen genau die zwei Import-Tage |

**Und der Kern:** **alle 137 offenen Karten stammen von einem einzigen Tag (2026-08-22)**, davon
**127 unter 0,50 €** und 75 unter 0,10 €. Der gesamte Rückstand ist **72 €** wert.

> ⚠️ **Die Prüfung war anfangs nicht möglich.** `GET /api/sync/history` war im Code auf
> `LIMIT 20` verdrahtet — genug für die Einstellungsseite, nutzlos für die eine Frage, für die der
> Endpunkt hier gebraucht wurde. Mit 20 Zeilen sah es nach „keine Fehlschläge in drei Wochen" aus;
> erst mit allen 141 ist die Aussage belastbar. Der Endpunkt nimmt jetzt ein `limit`.

**Konsequenz:** an der Buchung wird **nichts** geändert. Der Schutz, den die Hypothese gefordert
hätte („Events nur aus vollständig durchgelaufenen Syncs"), **existiert bereits** —
`sync_collection` erzeugt Ereignisse nur unter `if sync_complete`. Ein Umbau auf eine Vermutung,
der die Daten widersprechen, wäre eine Lösung auf der Suche nach einem Problem gewesen.

**Die Warteschlange ist echt. Falsch war die Arbeitseinheit:** ein Bulk-Import landet am Stück, und
er wurde Karte für Karte abgearbeitet.

### Nebenbefund (Stufe 1, Punkt 2)

`acquisition_events.created_at` ist der Zeitpunkt der **Sync-Erkennung**, nicht des Erwerbs — daher
`age_days = 0` bei der Begutachtung (alle 137 waren am Messtag erkannt worden). Archidekts
`addedAt` wird aber **nicht verworfen**, wie im Sprint-Text vermutet: es landet in
`collection.added_at`. Es auf das Ereignis zu übernehmen, wäre ein Einzeiler und würde
`mtg_inbox_liegengeblieben` wieder sinnvoll machen — **bewusst nicht gemacht**, weil dann die
Erkennungszeit verloren ginge, die für „was ist seit dem letzten Sync passiert" die richtige ist.
Zwei Felder wären der saubere Weg; das gehört in einen eigenen Handgriff.

⚠️ Zweiter Nebenbefund: `condition` und `language` speichern die **numerischen Archidekt-IDs**
(`"1"`), nicht Namen wie `NM`/`en` — sie stehen so auch in der Inbox. Kosmetisch, aber unlesbar.
Nicht Teil dieses Sprints.

## Stufe 2 — umgesetzt

| # | Paket | Datei |
|---|---|---|
| 3 | **Fehlerpfad + kein Springen**: `handleDecide` hatte **kein einziges `catch`** — eine abgelehnte Entscheidung ging in die Konsole, die Karte blieb liegen. Und jede Entscheidung invalidierte die ganze Query, wodurch die Liste neu lud, die Farbgruppen zuklappten und die Scrollposition verlorenging. Entschiedene Karten werden jetzt aus der geladenen Seite entfernt | `pages/Inbox.tsx` |
| 4 | **Bulk-Triage**: Checkbox je Karte, „alle sichtbaren", keep/dismiss für die Auswahl; `POST /api/acquisitions/bulk-decide` | `routers/acquisitions.py`, `pages/Inbox.tsx`, `api.ts` |
| 5 | **Tastatur**: K = keep, D = dismiss auf der **Auswahl** | `pages/Inbox.tsx` |
| 6 | **Undo angebunden**: `POST /{id}/undo` existierte seit Monaten **ohne einen einzigen Aufrufer** | `pages/Inbox.tsx` |
| — | `GET /api/sync/history` nimmt ein `limit` (siehe oben) | `routers/sync.py` |
| — | Version 0.43.0 + CHANGELOG | — |

### Drei Entscheidungen beim Bauen

**(a) Verkaufen bleibt einzeln.** `sold_new` und `swap` verlangen Preis, Zustand und ein Listing je
Karte. Eine Sammelvariante müsste die erfinden oder die halbe Auswahl abweisen — der Endpunkt nimmt
nur `keep` und `dismiss` (422 sonst, mit Test).

**(b) Ein Ausfall stoppt den Stapel nicht.** Jede Karte läuft durch dasselbe `decide_triage` wie
eine Einzelentscheidung — kein zweiter Buchungspfad, also identischer Snapshot und identische
Sensor-Aktualisierung. Eine fehlgeschlagene Karte wird benannt, der Rest läuft weiter: 136 gute
Entscheidungen wegen einer veralteten Zeile zurückzurollen wäre der schlechtere Ausgang.

**(c) K/D wirken auf die Auswahl, nicht auf die „fokussierte" Karte.** Bei hundert Karten in einer
Gruppe ist das Arbeitsobjekt die Auswahl; ein Kürzel, das auf das wirkt, was der Browser gerade für
fokussiert hält, ist eines, das niemand vorhersagen kann. Eingabefelder sind ausgenommen.

## Akzeptanz

- [x] **Stufe-1-Befund dokumentiert (widerlegt, mit Zahlen)** — Tabelle oben.
- [x] **137 Karten in unter 5 Minuten triagierbar**: „alle sichtbaren" + ein Klick je Seite; mit
  dem bestehenden Filter „unter X €" trifft eine Auswahl die 127 Billigkarten in einem Zug.
  ⚠️ *Rechnerisch* erfüllt — nicht an den echten 137 Karten durchgespielt, siehe „Offen".
- [x] **Fehlgeschlagene Entscheidung zeigt eine Meldung**; Undo stellt den Zustand wieder her
  (Test `test_a_decision_can_be_undone`).

## Verifikation

- [x] 4 neue Backend-Tests (`test_acquisitions_smoke.py`): Sammelentscheidung · eine schlechte
  Karte kippt den Stapel nicht · Verkaufen wird abgewiesen · Undo-Roundtrip.
- [x] Backend **324/324 grün**, Frontend-Build grün, `tsc` sauber.
- [x] Live gegen 0.43.0: `bulk-decide` mit einer nicht existierenden ID →
  `{"decided":0,"failed":[{"event_id":999999,"error":"Event not found"}]}` in 3 ms;
  `action: "sold_new"` → 422; **`pending_count` unverändert 137** (die Probe hat keine echte Karte
  angefasst).

## Offen

- **Der Durchlauf an den echten 137 Karten** ist nicht erfolgt — das sind die Daten des
  Auftraggebers, und „alle auswählen und verwerfen" ist keine Entscheidung, die ich an seiner
  Stelle treffe. Der Weg dafür: Filter „unter 0,50 €" setzen, „alle sichtbaren" anhaken, *Dismiss* —
  und falls es zu weit ging, *Undo*.
- **Stufe 3 (regelbasierte Auto-Dismiss-Vorschläge)** ist nicht gebaut. Die Daten sprechen dafür
  (75 der 137 unter 0,10 €), aber sie sprechen genauso dafür, dass der Filter plus „alle
  sichtbaren" dasselbe in zwei Klicks tut. Erst benutzen, dann entscheiden, ob eine Regel den
  Aufwand wert ist.
- **Der Component-Test der Inbox-Entscheidung** (aus Sprint 09 hierher verschoben) fehlt weiterhin:
  er braucht einen gemockten API-Layer. Der Fehlerpfad und der Undo-Roundtrip sind backendseitig
  getestet, das Nicht-Springen der Liste ist es nicht.
- **`created_at` vs. `addedAt`** und die numerischen `condition`/`language`-Werte — siehe
  Nebenbefunde.
