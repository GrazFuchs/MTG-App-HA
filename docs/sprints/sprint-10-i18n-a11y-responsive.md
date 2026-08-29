# Sprint 10 — i18n, A11y, Responsive

**Status: ✅ umgesetzt in 0.44.0, deployed + live geprüft am 2026-08-29.** Ist-Protokoll am Ende.

**Ziel:** Die Oberfläche konsequent zweisprachig, tastatur-/touch-bedienbar und auf schmalen
Viewports brauchbar machen.

**Warum:** B22, B20, plus die A11y-/Responsive-Hinweise des Audits (ungeprüft — beim Umsetzen
verifiziert, siehe unten).

## Umgesetzt

| # | Paket | Datei |
|---|---|---|
| 1 | **i18n-Sweep in drei Durchgängen, 433 Strings.** Werkzeuge und Zuordnungstabelle bleiben im Repo | `scripts/i18n-sweep.py`, `-2.py`, `-3.py`, `src/i18n.ts`, 44 Komponenten |
| 2 | **B20 — Schriften gebündelt**, `fonts.googleapis.com` raus | `scripts/fetch-fonts.py`, `src/fonts.css`, `src/assets/fonts/`, `index.html` |
| 3 | **A11y**: Navigation als `<Link>`, Akzentwähler als Buttons, Skip-Link, `<main>`, `aria-sort` auf den Sortierköpfen, Kartenbild per Tap/Tastatur, Fokusfalle im handgebauten Dialog | `App.tsx`, `Duplicates.tsx`, `CardHoverPreview.tsx`, **neu:** `useDialogA11y.ts` |
| 4 | **Responsive**: Collection-Breakpoint, Scroll-Container für die breiten Tabellen, PageHeader-Umbruch, Settings-Grid | `Collection.tsx`, `Duplicates.tsx`, `Settings.tsx`, `PageHeader.tsx` |
| 5 | **i18n-Lint** + Sprach-Smoke in der Testsuite | `scripts/i18n-lint.py`, **neu:** `src/__tests__/i18n.test.ts` |
| — | Der aus Sprint 08/09 zweimal verschobene Inbox-Render-Test | **neu:** `src/pages/inboxList.ts`, `src/__tests__/inboxList.test.ts` |
| — | woff2 bekommt `font/woff2` statt `application/octet-stream` | `static_files.py` + Test |
| — | Version 0.44.0 + CHANGELOG | — |

### Die Zahl war 433, nicht 222 — und gefunden hat sie nicht der Scanner

Ein Scanner über JSX-Textknoten und String-Props fand 324. Übrig blieben **45 Keys, die als
„definiert, aber nie benutzt" dastanden** — und jeder einzelne benannte UI, die es offensichtlich
gibt. Also musste der Text hartcodiert an einer Stelle stehen, die der Scanner nicht sieht. Er
stand dort, in vier Formen: Objektliterale für ein `.map()`, Options-Arrays, Ternaries in JSX, und
Template-Literale mit einem Wert mitten im Satz. **Die Liste der toten Keys war der bessere
Scanner.** Zwei weitere Durchgänge haben die 109 abgeräumt.

### Drei Funde, die auf keiner Liste standen

**(a) Zehn `<option>` ohne `value`.** Bei `<option>English</option>` *ist* der Anzeigetext der
gesendete Wert. Ein blindes Übersetzen hätte „Englisch" als Kartensprache an Cardmarket
geschickt. Sie haben jetzt explizite Werte — gesetzt **bevor** das Label angefasst wurde.

**(b) Die Farbliste gab es viermal** — `utils/colors.ts`, Inbox, Cardmarket, Wunschlisten-Filter —
und sie war schon auseinandergelaufen: „All Colors" gegen „All colors", der Mehrfarbig-Bucket
`M` an der einen und `Multi` an der anderen Stelle. Keine Kopie war für sich falsch, deshalb ist es
niemandem aufgefallen. Jetzt eine Liste; die Emoji bleiben bewusst außerhalb der
Übersetzungswerte.

**(c) Eine lokale Variable `t`** in der Deck-Ansicht verdeckte die Übersetzungsfunktion in dem
Moment, in dem die Typ-Labels Keys wurden. Der Compiler hat es gefangen; beim Lesen wäre es
durchgegangen.

### Die Lint-Prüfung, die am meisten wert ist

Nicht die nach hartcodierten Literalen, sondern die nach **Keys, die der Code aufruft und niemand
definiert**. Die werfen nämlich nicht: `t()` fällt auf den Key selbst zurück, die Seite zeigt dann
`inbox.sort_set`, wo ein Wort stehen sollte. **Genau dieser Key ist mir im Sweep durchgerutscht
und genau diese Prüfung hat ihn gefunden.**

⚠️ Sie muss die **Indirektion mitzählen**: dieses Projekt legt Keys als Strings in Options-Arrays
ab (`{ value: 'color', label: 'inbox.sort_color' }`) und übersetzt erst am Render-Ort mit
`t(o.label)`. Die erste Fassung suchte nur nach `t('…')`, fand nichts — und das Sortiermenü druckte
derweil den rohen Key auf den Bildschirm.

### Schriften: eine Datei je Familie, nicht je Gewicht

Alle drei sind **Variable Fonts**. Die woff2 hinter Space Grotesk 500, 600 und 700 ist byteweise
dieselbe Datei (per SHA-256 geprüft). Der naheliegende Weg — je Gewicht laden — lädt sie dreimal und
liefert 100 kB Dubletten aus. Stattdessen ein `@font-face` je Familie mit **Gewichtsbereich**.
102 kB statt 226.

⚠️ Sie liegen unter `src/assets/`, **nicht** `public/`: das Panel läuft hinter einem
Ingress-Präfix, ein absolutes `/fonts/…` wäre ein 404. Über den Import erzeugt Vite eine URL
relativ zum Stylesheet (`url(./Inter-*.woff2)`), die unter jedem Präfix aufgeht — live gegengeprüft.

## Akzeptanz

- [x] **Deutsche UI ohne englische Restinseln** — 0 hartcodierte Literale über alle 44 Komponenten,
  nicht nur die fünf Hauptseiten.
- [x] **`en` vollständig, kein roher Key** — beide Wörterbücher definieren dieselben 504 Keys, und
  der Sprach-Smoke prüft zusätzlich, dass kein Wert leer ist und **beide Seiten dieselben
  Platzhalter tragen** (ein fehlendes `{count}` rendert einen Satz mit Loch, ein erfundenes die
  Klammern — beides wirft nicht).
- [x] **Panel lädt ohne Internet mit den richtigen Schriften** — kein CDN-Element mehr in der
  ausgelieferten `index.html` (live geprüft: 0 Treffer), Font liefert 200.
- [x] **Inbox komplett mit der Tastatur bedienbar** — Skip-Link → Navigation (`<Link>`) →
  Filter/Suche → Karten-Checkboxen → K/D aus Sprint 08. Die Karte selbst ist per Enter erreichbar.
- [x] **Kartenbild auf dem iPhone erreichbar** — Tap öffnet, Escape schließt.
- [x] **375 px ohne horizontale Seiten-Scrollbar** auf Collection/Duplicates/Settings — die breiten
  Tabellen scrollen in ihrem eigenen Container. ⚠️ Am Code hergeleitet, nicht im Browser gemessen
  — siehe „Offen".

## Verifikation

- [x] Backend **325/325** (der neue woff2-MIME-Test dabei), Frontend **45/45**, `tsc` sauber,
  Build grün (Einstieg 421 kB).
- [x] **Der i18n-Wächter ist gegengeprüft**: ein wieder hartcodiertes `aria-label` lässt den Test
  fallen (`src/components/BackToTop.tsx: prop= Scroll to the top`), danach wieder grün.
- [x] Live gegen 0.44.0 auf Pi 5: `healthz` meldet 0.44.0, ausgelieferte Seite ohne CDN-Links,
  `assets/Inter-*.woff2` liefert 200, und der Ingress-`<base href>` aus Sprint 09 steht weiter.
- [x] Jeder der vier Responsive-Audit-Hinweise wurde **am Code bestätigt**, bevor er behoben wurde:
  Collection 601–768 px (Header `display: none` ab 768, Kartenlayout erst ab 600 — Lücke belegt) ·
  Duplicates 9 Spalten ohne jede Media-Query · PageHeader ohne `flexWrap` · Settings hart `1fr 1fr`.

## Offen

- **Der Sicht-Durchgang im Browser bei 375 px und 768 px** fehlt weiterhin — dafür braucht es einen
  Browser, und die Fixes oben sind aus dem Stylesheet hergeleitet, nicht gesehen. Was zu prüfen
  wäre: ob die Duplicates-Tabelle im Scroll-Container tatsächlich innen scrollt (Griffel setzt
  `overflow-x` auf einem Grid-Elternteil gelegentlich anders um als erwartet) und ob der
  Collection-Kartenmodus bei 700 px gut aussieht — er war bisher nur bis 600 px im Einsatz.
- **Die Sprachumschaltung selbst** ist unverändert: `currentLang` wird einmal beim Import
  bestimmt (LocalStorage → HA → Browser). Ein Umschalter in der UI wäre eine eigene Sache und
  stand nicht im Sprint.
- **Serverseitige Nutzertexte** sind noch gemischt (`sell_advisor` liefert Deutsch,
  `cardmarket_prices`-Suggestions Englisch). Das war Teil von Arbeitspaket 1 und ist **nicht
  gemacht** — es ist eine andere Baustelle als der Frontend-Sweep: die Strings kommen aus der API
  und müssten dort key-basiert werden, sonst übersetzt man sie an zwei Stellen.
