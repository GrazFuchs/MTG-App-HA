# Backlog — bewusst ohne Sprint

Ideen aus dem Feature-Vergleich (R7/R8 in [review-befunde.md](review-befunde.md)) und
Aufräumkandidaten, die keinen der 11 Sprints rechtfertigen. Bei Interesse einzeln zum Sprint machen.

## Aus dem ManaBox-Vergleich

- **Binder-/Lagerort-Konzept** — ManaBox' Kernversprechen („in welchem Ordner liegt die Karte
  physisch?"): Binder vs. Liste vs. Deck als drei Aufenthaltsorte. Dem Add-on fehlt die Dimension
  komplett — es weiß, *dass* 10.214 Karten existieren, nicht *wo*. Größter konzeptioneller Zubau.
- **Vier-Zustands-Missing-Modell** für Completeness: *partially missing / completely missing /
  exact versions / other versions* (+ Schalter „exakte Printings erzwingen") statt der heutigen
  Ein-Zahl-Antwort. Passt zu den ungeprüften Completeness-Hinweisen (printing-exaktes Matching,
  Sideboard zählt mit, andere Decks binden Kopien).
- **Karten-Scan** — wenn je, dann OCR-/Collector-Number-basiert, nicht Artwork-Matching
  (ManaBox' Artwork-Ansatz erzwingt drei Kaschier-Features; die Lehre steht in R7).
- **Teilstapel-Geste** („3 von 7 Kopien verschieben") und **Preisband-Audiofeedback** — kleine,
  klaubare UX-Ideen.
- **Gespeicherte Suchen / Filter-Presets** in Collection und Inbox.

## Datenquellen

- **MTGJSON-Preishistorie je Karte** (90 Tage, Retail + Buylist, 26 Marktplatz-IDs, MIT) als
  zweite Preisquelle neben Cardmarket — und ab Tag 1 `AllPricesToday` täglich wegschreiben, wenn
  je mehr als 90 Tage Verlauf gewünscht sind (nachkaufen kann man Historie nicht).
- **EDHREC-Salt** (`json.edhrec.com/pages/top/salt.json`, paginierbar) als Zusatzsignal am Deck
  („Salt-Summe") — nur auf Duldung, hart cachen, weich degradieren.

## Cardmarket-Import-Härtung (ungeprüfte Audit-Hinweise, vor Umsetzung verifizieren)

- Neu-Format-CSV schreibt `set_code=''` → „LISTED"-Spalte dauerhaft 0, 🛒-Badge nie sichtbar.
- Foil geht beim Import/Export-Roundtrip verloren.
- `clear-listings`/Import löscht Bestand, bevor die erste Zeile geparst ist.
- Listing-Health vergleicht Foil-Listings gegen Non-Foil-Trend.

## Kleinkram

- Backup-Endpunkt: Vollkopien in `/data` aufräumen; Restore mit Bestätigung + DB-Reconnect.
- Settings: Sync-History-Zeiten (UTC-Offset), Erfolge nicht rot färben, Fehlerspalte lesbar.
- `items`-Kappung 10 → 25 auf den HA-Attribut-Listen (B15; in Sprint 07 als Option enthalten).
- Doku: `docs/ha-integration.md` Voice-REST-Beispiel (`localhost:8099`) korrigieren, wenn Voice
  bleibt (Sprint 11 entscheidet).
