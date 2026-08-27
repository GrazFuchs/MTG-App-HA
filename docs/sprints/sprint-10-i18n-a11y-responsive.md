# Sprint 10 — i18n, A11y, Responsive

**Ziel:** Die Oberfläche konsequent zweisprachig, tastatur-/touch-bedienbar und auf schmalen
Viewports brauchbar machen. Unabhängig; profitiert von Sprint 09 (Render-Tests fangen Regressionen).

**Warum:** B22 (~27 % i18n-Abdeckung, ~222 Literale, 76 tote Keys — strukturell gemischtsprachige
UI im deutschen Browser), B20, plus die A11y-/Responsive-Hinweise des Audits (ungeprüft, beim
Umsetzen verifizieren).

## Arbeitspakete

1. **i18n-Sweep:** die ~222 hartcodierten Literale in 34 Dateien auf `t()`-Keys ziehen
   (Reihenfolge nach Nutzungsgewicht: Inbox → Duplicates → Collection → Settings → Cardmarket →
   Deck-Bereich → Wishlist-Dialoge); die 76 definierten-aber-unbenutzten Keys entweder anschließen
   (viele passen exakt, z. B. 20 Deck-Keys) oder löschen. Serverseitige Nutzertexte
   vereinheitlichen: `sell_advisor` liefert Deutsch („nicht in Decks"),
   `cardmarket_prices`-Suggestions Englisch — eine Sprache bzw. Key-basiert.
2. **B20 — Fonts bundeln:** Space Grotesk / Inter / JetBrains Mono als Assets ins Bundle
   (woff2 + `@font-face`), `fonts.googleapis.com`-Links aus `index.html` entfernen.
   Local-First, AdGuard-fest, kein Layout-Shift bei Offline-Start.
3. **A11y-Grundpfad:** Primärnavigation als echte `<a>`/`<button>` (heute `<div onClick>` —
   komplett tastatur-unerreichbar); Tabellen-Header mit `aria-sort` + Enter/Space;
   Karten-Hover-Preview bekommt eine Touch-/Tastatur-Alternative (Tap/Enter öffnet das Bild —
   es ist das primäre Identifikationsmittel im Triage-Fluss); Dialoge: Escape + Fokus-Falle
   (Fluent-Dialog kann das, die handgebauten Overlays nicht).
4. **Responsive-Pass** (Audit-Hinweise beim Umsetzen einzeln verifizieren):
   Collection 601–768 px (Header verschwindet, Grid schon kollabiert); Duplicates ohne
   Mobil-Layout (9-Spalten-Grid ≥524 px → Karten-Layout oder Scroll-Container);
   Settings-Grids (hart `1fr 1fr`); PageHeader-Kollision bei 320–375 px; generell: breite
   Tabellen in `overflow-x: auto`-Container statt Seiten-Scroll.

## Akzeptanz

- Deutsche UI ohne englische Restinseln auf den fünf Hauptseiten; `en` vollständig (kein roher Key).
- Panel lädt ohne Internetzugang mit korrekten Schriften.
- Komplette Bedienung der Inbox nur mit Tastatur möglich; Kartenbild auf dem iPhone erreichbar.
- 375-px-Durchgang: keine horizontale Seiten-Scrollbar auf Collection/Duplicates/Settings.

## Verifikation

- i18n-Lint: kleiner Test, der `frontend/src` auf JSX-Text-Literale > N Zeichen scannt
  (Ausnahmenliste) — hält den Sweep dauerhaft.
- Render-Tests aus Sprint 09 um einen Sprach-Smoke ergänzen (de + en Rendering eines Screens).
