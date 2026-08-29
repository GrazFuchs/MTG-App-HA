## 0.44.0 — Sprint 10: the interface was half in English, and unreachable without a mouse

### The i18n sweep, in three passes and 433 strings

The review counted "~222 hardcoded literals, 27 % coverage". The real number was 433, and finding the other 211 was the interesting part.

A scanner over JSX text and string props found 324 and moved them. That left 45 keys marked "defined but never used" — and every one of them named a piece of interface that plainly exists, which meant the text had to be hardcoded somewhere the scanner could not see. It was: in object literals feeding a `.map()`, in options arrays, in ternaries, and in template literals with a value spliced into the middle of the sentence. **The dead-key list turned out to be the better scanner.** Two further passes cleared those.

Three things fell out of it that were not on anyone's list:

- **Ten `<option>` elements had no `value`.** In `<option>English</option>` the displayed text *is* the submitted value, so translating those alone would have posted "Englisch" to Cardmarket as a card's language. They got explicit values before their labels were touched.
- **The colour list existed four times** — in `utils/colors.ts`, in the inbox, in Cardmarket, in the wishlist filter — and had already drifted: "All Colors" against "All colors", and the multicolour bucket keyed `M` in one place and `Multi` in another. Now one list.
- **A local variable named `t`** in the deck view shadowed the translation function the moment those labels became keys. The compiler caught it; a reviewer would not have.

35 keys really were obsolete and are deleted. What remains: **502 keys, 502 used, 0 hardcoded literals**, and English and German define exactly the same set.

`npm run lint:i18n` checks all of that, and the test suite runs it — including the check that matters most, keys the code *calls* that nobody defined. Those do not throw; `t()` falls back to printing the key, so the page shows `inbox.sort_set` where a word belongs. That exact key slipped in during the sweep and this is what found it.

### Fonts are in the bundle now

The three UI fonts loaded from fonts.googleapis.com at runtime. Two problems at once here: the panel is opened on a LAN that is regularly without internet, and this household filters DNS on both resolvers — a blocklist entry for fonts.gstatic.com would have swapped the whole interface to a fallback face with nothing anywhere to say why.

They are vendored as woff2, latin subset, **one file per family rather than one per weight**: all three are variable fonts, so the file behind Space Grotesk 500, 600 and 700 is the same bytes. Fetching per weight the obvious way ships 100 kB of duplicates. 102 kB total.

### Keyboard and touch

- **The main navigation was `<div onClick>`** — no tab stop, no Enter, nothing for a screen reader, and middle-click did nothing because there was no href. It is `<Link>` now, with `aria-current` on the active item. The accent picker was the same shape and is now real buttons.
- **A skip link**, because eight navigation items sit between the top of the document and the content on every page.
- **The sortable column headers** in Duplicates were also `<div onClick>`: the only way to reorder that table was a mouse. Buttons now, with `aria-sort`.
- **The card image was hover-only.** It is the primary way to tell one printing from another during triage, and on a phone there is no hover — so on the device where the inbox is most often worked through, the image was simply unreachable. Tap or Enter now pins it; Escape closes it.
- **The hand-built triage dialog** had no Escape, no focus trap and no focus restore: Tab walked out of the modal into the page behind it, where the user would have been typing into a form they could not see.

### Narrow screens

Each audit hint was checked against the code before being fixed; all four held.

- **Collection had a dead zone between 601 and 768 px:** the column header hid at 768 and the row grid collapsed at 768, but the card layout only started at 600 — so in between you got unlabelled columns with no header to explain them. One breakpoint now.
- **Duplicates' nine-column grid and the sync history's six** get a scroll container of their own, so the table scrolls and the *page* does not.
- **PageHeader** could not wrap, so the title and whatever sat beside it overlapped at 320–375 px.
- The settings grid was a hard `1fr 1fr`.

### Carried over from Sprint 08

The third render test — what happens to the loaded list when a card is decided — was deferred twice for wanting "a mocked API layer". It did not: the behaviour worth pinning is a pure transform of the cached page, and extracting it from the component left nothing to mock.

## 0.43.0 — Sprint 08: the inbox was the wrong unit, not the wrong interface

The plan for this release was to hunt a bug: the suspicion was that aborted syncs were booking phantom acquisitions, and that the 964 decisions a month were largely fabricated. Measuring first said otherwise, so the release does something else.

### What the measurement said
Every one of the last twenty sync runs completed; none was partial or failed. Condition and language have been recorded the same way since May, so no key change ever re-booked an owned card. And the events do not trickle in at 32 a day — they arrive in bursts on about twenty days across four months, the two most recent lining up exactly with the two days the collection actually grew.

**All 137 open cards were detected on one day, and 127 of them are worth under 50 cents.** The whole backlog is €72. The queue is real; it is just one bulk import, and deciding it one card at a time was the wrong unit of work.

### Added
- **Bulk triage.** A checkbox per card, "select all shown", and keep/dismiss for the whole selection — `POST /api/acquisitions/bulk-decide`. Every card still goes through the same decision path as a single one, so the booking snapshot, the sensor refresh and the error handling are identical; a card that fails is reported by name and the rest carry on, because rolling back 136 good decisions over one stale row is the worse outcome. Selling stays per card: it needs a price, a condition and a listing, and a bulk version would have to invent them.
- **Undo.** `POST /{id}/undo` had been implemented for months **without a single caller**. Every decision — single or bulk — now leaves an undo bar that puts the cards back.
- **K and D** decide the current selection. Deliberately not "the focused card": with a hundred cards in one bucket the thing you are working on is the selection, and a shortcut that acts on whatever the browser considers focused is one nobody can predict.

### Fixed
- **A failed decision was invisible.** The decision path had no `catch` at all: a rejected request went to the console while the card sat there looking undecided. Failures now show a banner.
- **The list jumped after every decision.** Deciding invalidated the whole query, so the page reloaded, the colour groups re-collapsed and the scroll position was lost. Decided cards are now removed from the loaded page instead — with 137 cards in one bucket that is the difference between triaging and finding your place again.
- **`GET /api/sync/history` was capped at 20 rows in code.** Fine for the settings page, useless for the one question it was needed for here — whether any sync had ever aborted. It takes a `limit` now.

### Not done, and why
The suspected phantom-event mechanism was **not** confirmed, so nothing was changed about how events are booked. The guard it would have needed is already there: events are only generated when the sync walked every page. Rebuilding that on a hypothesis the data contradicts would have been a fix in search of a bug.

## 0.42.0 — Sprint 09: the display bugs had three causes, not twelve

A dialog you could not reach, a popup drawn over by the cards below it, duplicated listing rows, a white page after a reload. Four releases fixed four symptoms. This one goes after what they share.

### Fixed
- **Every floating overlay now leaves the panel it is written in.** The Sothera `Panel` carries `backdrop-filter`, which makes it *both* a containing block for `position: fixed` descendants and a stacking context — so an overlay inside it competes for z-index only within that panel, and every card painted later draws on top. `z-index: 10000` looks like the fix and is not one. 0.34.1 solved this for the sell dialog by portalling it; the price-trend popup carried the identical defect until now. All three overlays go through one `OverlayPortal`, and the rule is written down where the next one will be added.
- **The sell dialog can be reached in a short window.** The second half of the same complaint: a centred dialog taller than the viewport pushed its confirm button past both edges of an ingress iframe, where nothing could scroll to it. It now caps at 90 % of the viewport and scrolls inside.
- **Reloading a nested route no longer shows a white page.** The build references its bundles relatively, so after a reload on `/decks/5` the browser asked for `/decks/assets/index-*.js` — correctly a 404, and a blank screen. The served shell now carries a `<base href>` pointing at the add-on root, taken from the `X-Ingress-Path` header the Supervisor sets (falling back to the startup value). Route depth stops mattering.
- **Two tests had been failing for weeks — on Windows only, and for a real reason.** Starlette hands the static-file handler an *OS-normalised* path, so `assets/index-abc.js` arrives with a backslash there; every prefix check in the module is written with forward slashes. The asset cache header and the API passthrough both silently did the wrong thing. Separators are normalised once, and the suite is green for the first time.
- **A card sitting in a deck is no longer counted as a spare copy.** The duplicates query computed the surplus correctly and then ignored it: `extras` was the printing's own copy count, so a playset entirely in play read as four cards to sell — and the sell dialog would offer them.

  Handing every row the card's surplus instead would have traded that for the opposite error, since deck usage is counted per *card* while the rows are per *printing*: a card with two printings would be counted twice in any sum. The card's surplus is therefore handed out across its printings in a stable order, capped by what is owned of each, so the rows add up to it exactly once. Listings now count against the printing they belong to rather than every card of that name — the same name-versus-printing confusion the price join was fixed for in 0.33.0. ⚠️ 42 of 1223 listings never got linked to a printing by the import; those no longer cancel anything, so the backlog reads slightly high for them. The MCP tool shares the corrected query and a test asserts the two agree.
- **A failing page shows the failure.** An error boundary wraps every route, and an unknown path gets a real "no such page" instead of an empty content area that reads exactly like a page with no data.

### Added
- **Component tests — the first this project has had.** The suite ran under `environment: 'node'`, so nothing was ever rendered; the existing "Inbox test" says in its own comment that it tests a utility module instead, because importing `api.ts` touched `window` at module load. That coupling is gone (the base path resolves on first use), the suite runs under jsdom with Testing Library, and the overlay and error-boundary behaviours above are pinned by tests that were each verified to fail on the old code.
- **Per-page code splitting.** The bundle was a single 1.15 MB file, so opening the dashboard also downloaded the deck comparison, the Cardmarket import and the markdown renderer. Routes load lazily: the entry chunk is **392 kB (120 kB gzipped) instead of 1179 kB (336 kB)** — a third of what it was, which is felt over the tunnel.

### Upgrading
No migration, but the duplicate figures move, and **not all in the same direction** — measured on the real collection:

| | before | after |
|---|---:|---:|
| surplus cards | 2526 | **2763** |
| surplus value | €1062.70 | **€1041.33** |
| unlisted value | €915.17 | **€942.23** |

Two corrections pull against each other, and the listing one turned out to be the larger. Deck-bound copies leaving the count pushes it down; listings no longer cancelling *other printings* of the same card pushes it up. Concretely: three copies of printing A and two of printing B, with four of A listed — the old name match cancelled all five and reported nothing spare, when two copies of B were sitting there unlisted. The count rising is the correction, not a regression.

## 0.41.0 — Sprint 07 (add-on half): what Home Assistant reads, and when

### Fixed
- **An actionable push could name one card and act on another.** Every sensor was published state first, attributes second. Home Assistant automations trigger on the *state* and then read the attributes — the inbox push takes the top card out of `items` the moment the pending count changes — so there was a window, short but real, in which the automation read the previous `items` and baked a stale `event_id` into a notification whose Keep/Sell buttons then decided a different card than the one it described. Attributes are now published first, and a test pins the order (verified to fail on the old one).

### Changed
- **Attribute lists carry 25 entries instead of 10.** The cap was set cautiously and never measured; across all 128 MTG entities the attributes come to 40.8 KiB in total, with the heaviest single payload at 2.2 KiB of the roughly 16 KiB Home Assistant allows. The dashboard tables said "showing 10 of 137" for no reason anybody could point at; at 25 the worst payload is still about a third of the limit.

## 0.40.0 — Sprint 06: the wishlist says something when a card gets cheap

`is_deal` had been there all along and never announced anything, because it is a *state*: true for as long as the price stays under the target. Nothing compared today against yesterday, so there was no moment to report — the card was simply quietly cheap, on a list of 74, until somebody happened to look.

### Added
- **A deal is now the crossing, not the condition.** Each entry remembers what it cost at the last check (migration 25), and a card that was above its target and no longer is gets a notification naming the old price, the new one and the target. It runs after the daily price sync, or on demand via `POST /api/wishlist/check-deals`. The price is recorded whether or not anything happened — that record *is* the comparison for the next run, which is why the very first run reports nothing and should.

  Two quiet rules that matter more than they look. The stored price is used rather than the Cardmarket history, because a third of this list has no Cardmarket product and would otherwise never be watched at all. And an entry stays quiet for a week after it has been announced: edge detection stops a daily repeat, but a price wobbling around the target would cross every second day.
- **A target of 0 is shown as "not set", not as a dash.** It means *no target*, never *free*, and such an entry can never register as a deal — so four of the most expensive cards on this list were invisible in exactly the view meant to find bargains. There is now a "No target price" filter beside the deals one.
- **Three badges that say why a card is worth more than its price.** Whether it is on the official Game Changers list; what adding it would do to the bracket of the deck it is assigned to ("Bracket 3 → 4", with the reason in the tooltip); and whether it is the one card missing from an infinite combo in a deck, naming that deck — the bridge that only became possible once partial combos started naming what they lack.

  The bracket comparison runs the deck through the same rules twice rather than reasoning about the card alone, because a fourth game changer only matters in the company of the three already there. It is computed only where it could say anything — the card has to be assigned to a deck and be something the rules count.
- **Wishlist sensors now keep a history in Home Assistant.** ⚠️ As `state_class: measurement` with **no device class**: without a state class HA keeps no long-term statistics at all, so the price of a wanted card could not be plotted — the whole point of those 74 sensors. But `device_class: monetary` accepts only `total`, and `total` means a running sum, which is the wrong reading for a price and the very misuse the aggregate sensors still have to be cleaned up for. A plain measurement in EUR aggregates honestly (min, max, mean) at the cost of the currency formatting.

## 0.39.0 — Sprint 05: a power score, kept apart from the bracket

A port of edhpowerlevel.com's scoring, computed offline from the fields the Scryfall enrichment already stores. It answers a different question from the bracket and is deliberately not allowed to touch it: the bracket asks what a deck is *capable of*, this asks what its cards are *worth and wanted*, scaled by how cheaply the deck deploys them. Combos, game changers and land denial feed the bracket only — the same separation the original makes.

### Added
- **`services/power_level.py`** — the full chain: a price and a popularity rating per card, weighted 1.25 and 0.75, the land factor, the flat floor for basics, the tipping point at 65% of non-land impact, and the efficiency scaling that turns the sum into a score out of 1000 and a level out of 10. Roughly ninety card overrides come with it (Sol Ring's price counted eightfold, free spells at zero mana, four commanders worth three to four times their own impact when they are actually the commander).

  Five things in it look like bugs and are faithful: the interpolator weights the decile boundary but not the fraction inside it; efficiency is not clamped, so a very cheap deck scores above ten and a very expensive one goes negative; a modal double-faced card counts as a land and drops out of the average mana cost entirely; basic lands get their flat value *after* the land factor; and the commander multiplier applies only in the command zone. Each has a test that would fail if someone tidied it up.
- **`decks.power_score` / `power_level` / `power_detail`** (migration 24), a power panel in the deck view — score first, since the original's author recommends comparing that rather than the level — with the efficiency, the tipping point, the impact spread by mana value, the five cards carrying the score, and the caveat that none of it measures synergy or consistency. `POST /api/decks/{id}/power/recompute` and `/api/decks/power/recompute-all`; the sync does it after every run.
- **`GET /api/decks/{id}/power/reference-url`** and a button beside the panel: the original runs client-side in a browser, so the only way to check the port is to open the same list there. The link is built the way the site's own encoder does — `~` between lines, `+` for spaces, `~Z~` to close it, and `[Commander]` kept, because the commander multiplier depends on it.
- `cards.layout`, needed for exactly one rule (recognising a modal double-faced card). Migration 24 clears the enrichment stamp so the next pass fills it.
- The per-deck HA sensor carries `power_score` and `power_level` alongside the bracket.

### Notes
**The popularity curve is from September 2024 and is left that way on purpose.** It scores a card by `27000 − edhrec_rank`, where 27,000 was the Commander-legal card count then. Raising only that last number is not an update: the other ten stops are decile boundaries of the same 2024 distribution, so moving the top alone yields a curve that is neither the original nor a correct recalibration — while silently shifting every deck's popularity. A real refresh means re-deriving all eleven stops. Until then the 2024 curve stands, because it is the only version a result can be checked against.

**Our USD price comes from Archidekt where the original reads Scryfall.** They track each other but are not the same number, so a small divergence from the reference is expected and is not a porting error.

## 0.38.3

### Fixed
- **The bracket tag on a deck card was unreadable in the light theme.** The tag carries its own fixed dark background but took its text colour from the theme, and in light mode that is `#0E1024` — near-black letters on a near-black scrim, over artwork. It now uses a fixed light colour, the way the deck hero already did, plus a larger weight and a stronger backdrop. The `?` that marked a computed value is gone: the border is dashed for a computed bracket and solid for one you set, which needs no decoding, and the tooltip says which it is.

## 0.38.2

### Fixed
- **A four-piece Food engine was reading as an upgraded deck.** 0.38.1 let any complete infinite combo set the floor at bracket 3, which was right for a three-card infinite and wrong for "Squirreled Away", whose only loop needs four cards and produces infinite Food tokens — it wins nothing on its own, and Commander Spellbook files that deck as Exhibition. The generic rule is now bounded at three pieces (`GENERIC_INFINITE_MAX_CARDS`). Both that bound and the eight-mana early-combo ceiling are judgements calibrated against real decks rather than quotations, and both are named constants for exactly that reason.

## 0.38.1

### Fixed
- **A deck that wins on the spot was filed as Core.** The bracket rules count *two-card* infinite combos, because that is the distinction the guidance draws between brackets 3 and 4 — so a deck whose only infinite needs three pieces triggered nothing at all and came out at the base bracket. "Surf n Turf" holds two complete three-card infinites and was reported as a bracket 2 deck, while Commander Spellbook independently called the same list Ruthless. Having an infinite at all now sets the floor at 3; needing only two cards for it still sets it at 4. Found by running the computation over all 22 real decks rather than by reading the rules again.

## 0.38.0 — Sprint 04: a bracket the deck can actually be given

Every deck in this collection reported bracket 0. The only source was an Archidekt field that is null on all of them, so the filter, the badge and the deck comparison were all built on a number that never arrived. The bracket is now worked out from what the deck contains — and can be overruled by hand, which is the point.

### Added
- **A computed WotC bracket, with the evidence attached** (`services/bracket.py`, migration 23). Four criteria, all answerable from data the previous two sprints put in place: game changers (`cards.game_changer`, from Scryfall), complete two-card infinite combos (`deck_combos`), mass land denial and chained extra turns. Each rule that raises the floor records *which cards or combos raised it*, and the deck's badge has a "why?" that shows them. A number without that is not reviewable.

  **The computation only ever answers 2, 3 or 4, and says so.** Bracket 1 (Exhibition) and bracket 5 (cEDH) describe intent — a deck built around a bit, a deck taken to a tournament — and nothing in a decklist separates either from its neighbour. Claiming them would be inventing a result. That is what the hand-set bracket is for.
- **The bracket is editable and the hand-set value wins.** `user_bracket` already existed and was already sync-proof; it now sits in a badge that shows the *effective* bracket — hand-set, else computed, else the (empty) import — and the same value drives the deck list, its filter and the tile on each deck. `POST /api/decks/{id}/bracket/recompute` and `POST /api/decks/bracket/recompute-all` recompute on demand; the sync does it after every run, since it is local SQL and costs nothing.
- **Mass land denial and extra turns are cached per card from Commander Spellbook** (`cards.mass_land_denial`, `cards.extra_turn`, filled during the combo sync). Those two are judgements about what a card does rather than a published list, and a hand-written list in this repository is the part that would go stale first. What Spellbook cannot classify stays NULL — *unclassified*, not *clean* — and the bracket detail reports how many cards are in that state, so a thin answer is visible rather than implied. A deliberately narrow oracle-text fallback catches the plainest wordings ("Destroy all lands").
- **Spellbook's own verdict is kept beside ours** (`decks.spellbook_bracket_tag`). ⚠️ It is **not** the WotC 1–5 scale: the schema documents the values as Exhibition, Core, Oddball, Powerful, Spicy, Ruthless and Banned, and no mapping between the two scales is published. It is shown as a label, never as a number.
- The per-deck HA sensor carries `bracket` and `bracket_source` as attributes. ⚠️ That sensor only exists for decks played in the last 90 days, so in practice the bracket is an in-app feature.

### Fixed
- **The "Compare Decks" button was invisible.** It sat inside a block rendered only when some deck had a bracket — and no deck did, so the only entry point to the deck comparison could not be reached at all. It now stands on its own, and the bracket filter next to it works off the effective bracket instead of the empty Archidekt one.

### Notes on the rules
The bracket guidance is written in prose, so two thresholds are judgements rather than quotations, and both are single named constants:
- **Three game changers are allowed at bracket 3**; a fourth makes it 4. That one is stated outright.
- **A two-card infinite counts as "early" — and so bracket 4 — at eight mana or less**, counting the pieces plus whatever the combo still owes. Kiki-Jiki (5) + Deceiver Exarch (3) is eight and is treated as an early combo everywhere; Mikaeus (6) + Triskelion (6) is twelve and is not. A group that reads "before turn seven" differently changes `EARLY_COMBO_MANA_CEILING`.
- **Tutors are deliberately not counted.** Wizards removed the tutor limits from brackets 1–3 in October 2025.

### Upgrading
Migration 23 adds the columns. Brackets appear after the next sync, or immediately via `POST /api/decks/bracket/recompute-all` — no network needed for the computation itself, though the card classification arrives with the combo sync.

## 0.37.0 — Sprint 03: combos for every deck, and what they are short of

The combo cache held 433 combos spread over 4 of 21 decks, and not one of the 418 partial ones named the card it was missing. Two unrelated causes, both fixed here.

### Fixed
- **17 of 21 decks had never been asked about combos at all.** The combo lookup sat inside the branch that runs after a deck is re-fetched from Archidekt — and the sync is incremental, so a deck that had not changed since the feature arrived hit `continue` several lines earlier and was never asked. It looked exactly like a deck without combos.

  Asking every deck every night is the other extreme, and the obvious cheap test for "does this deck need asking" does not work: a deck Spellbook found nothing for and a deck that was never asked both hold zero rows in `deck_combos`. So the answer is stamped on the deck (`decks.combos_synced_at`, migration 22), and a top-up pass after each sync asks about every deck that is due — after a normal sync, only the ones that were skipped. A deck is re-asked after 14 days, because Spellbook keeps adding variants to a decklist that has not changed. Migration 22 stamps the decks that already carry combos with the date of their newest cached row, so the first run after the upgrade goes to the decks that actually need it.
- **No partial combo said which card it was missing** — the extractor read `combo["missingCards"]`, and **the Spellbook response has no such field** (checked against the live API). A combo carries `uses`, the cards it needs, and nothing about what you lack. The missing cards are now derived: the combo's cards minus the deck's, matching a double-faced card under either face and counting the commander as present. Where nothing *named* is missing, the deck is short one of the combo's templates ("any creature with flying") and that is named instead — an empty list would have claimed the combo was complete.

  Deck 1 has 27 such combos, every one of them exactly one card short. *Breath of Fury* — with *Anger* already in the deck — is now readable as what it is: one card away from an infinite.
- **A Spellbook outage was reported as "this deck has no combos".** `sync_combos_for_deck` caught the error and returned `0`, which the sync then logged only if it was non-zero. Failures now propagate: the top-up names the deck and the reason and carries on with the rest, `POST /{deck_id}/combos/sync` answers **502** instead of `{"count": 0}`, and the per-deck result is logged whether it is 0 or 200.
- **The combos panel counted cards that are not in the deck.** The header read "Combos in this Deck — 27 PARTIAL"; the two columns are now "Complete — every card in the deck" and "One card away — not in the deck yet", and the missing card is named in the row rather than hinted at.

### Added
- **`POST /api/decks/combos/sync-all`** (`max_decks`, `force`) catches the whole shelf up in one go instead of waiting for the nightly sync, and reports per deck what it found or why it failed. It is declared before the `/{deck_id}` routes so `combos` is never read as a deck id.
- The Spellbook client logs the buckets it deliberately ignores — combos that would need other colours or another commander — so leaving them out stays a visible decision rather than an invisible one.

### Upgrading
Migration 22 adds the stamp. The first sync afterwards asks Spellbook about every deck that has none (about a second per deck), or `POST /api/decks/combos/sync-all` does it immediately.

## 0.36.0 — Sprint 02: the card facts only Scryfall has

Nearly every card row in this database was assembled from an Archidekt payload, because that is where the decks and the collection come from. Archidekt is a good source for what is *owned* and *played*, and a partial one for what a card *is*. Everything here follows from that, and it is the groundwork the bracket (Sprint 04) and power-level (Sprint 05) work needs: a bracket cannot be computed from data that has no Game Changers, no Reserved List and no format legality.

### Added
- **`cards.game_changer` and `cards.reserved`** — Scryfall publishes the official WotC Game Changers list as a field on the card object (53 cards as of 2026-02-09), and the Reserved List likewise. That is worth stating plainly: it means the bracket calculation needs no hardcoded card list of its own, which is the one part of a home-grown bracket calculator that is guaranteed to go stale.

  Both are `NULL` until asked, and `NULL` means *never asked* rather than *no*. A printing Scryfall cannot resolve keeps its NULLs and is not given a fabricated `0` — `game_changer = 1` is about to decide a deck's bracket, so "unknown" has to stay visible as unknown.
- **`cards.scryfall_enriched_at` and the enrichment pass behind it** (`services/card_enrichment.py`). `POST /cards/collection`, 75 printings per request, keyed by `scryfall_id` so it is printing-exact. It fills `legalities` (which was `{}` on every Archidekt-sourced card — the parser sends the literal string), refreshes `edhrec_rank`, writes `keywords` from Scryfall rather than Archidekt's thinner reading, tops up `cardmarket_id` for the printings the Cardmarket-specific backfill never reached, and fills `oracle_text`, `cmc` and `mana_cost` only where they were empty. A field Scryfall does not answer for leaves the stored value alone — a double-faced card, whose rules text lives in `card_faces` rather than at the top level, keeps the text it has instead of being blanked.

  The stamp is what makes this affordable. Without it a nightly run would re-crawl all ten thousand cards; with it a card is asked once and then left alone for a week. The week is not idle patience: WotC edits the Game Changers list, EDHREC ranks drift, and an Archidekt sync of the same card writes its own keywords back, so the weekly refresh is what keeps those self-correcting rather than frozen at first contact. In steady state that is a tenth of the collection per night.
- **`POST /api/cards/backfill-scryfall`** runs the pass now instead of waiting for a sync (`max_cards`, `force`). The pass inside a sync is capped at 3000 printings so a first run cannot stretch a nightly sync unpredictably; this endpoint is uncapped — a full collection is ~137 requests, a few minutes at the rate Scryfall asks for on `/cards/collection` (2 requests/second there, not the general 10, which is why the loop paces itself rather than relying on the shared client's 100 ms).
- **`GET /api/cards/enrichment`** reports how far along it is, and reports *asked* separately from *flagged* for the reason above.

### Fixed
- **A sync overwrote what the enrichment had just learned.** `upsert_card` is the single card write path and the nightly sync drives it with Archidekt payloads, so `legalities=excluded.legalities` meant every night's sync wrote `{}` back over any legality the app had. The same for a thin Archidekt entry (one with no `oracleCard`), which carries neither rank nor rules text and set both to nothing, and for keywords — only 45 of 98 cards in the sampled deck carried any at all, so an empty list would have blanked the majority of them until the following week's refresh. The fields Archidekt cannot speak to are now protected at that write path, the way `cardmarket_id` already was: an empty payload never overwrites a known value. Without this the enrichment would have survived until 03:00.
- **The type line was stored in two different shapes, and one of them broke every filter that spells two type words.** Archidekt hands the type line out as three lists (`superTypes`, `types`, `subTypes`) and the parser comma-joined them: `Legendary, Creature — Pirate, Shark` where Scryfall writes `Legendary Creature — Pirate Shark`. The card-type filter added in 0.34.0 matches a substring of the part before the em dash, so both forms answered it correctly and the difference stayed invisible.

  What it did break is `type_line NOT LIKE '%Basic Land%'`, which never matched a single Archidekt-sourced basic land, because the row reads `Basic, Land — Plains`. In the price-alert query a second, name-based exclusion carried it; in the MTGStocks near-ATH query there is no second half, so basic lands were eligible for "consider selling" (inert only because MTGStocks is disabled). The parser now assembles Scryfall's spelling, `upsert_card` canonicalises whatever it is handed — the same arrangement colours got in 0.34.0 — and **migration 21** rewrites the existing rows. A comma never occurs in a Scryfall type line, so `LIKE '%,%'` selects exactly the affected rows and dropping the commas is a canonicalisation rather than a guess about the source.

### Upgrading
Migration 21 adds the three columns and rewrites the comma-form type lines in place; no sync is needed for that part. The Scryfall data itself arrives over the following nights (3000 printings per sync) — or in one pass via `POST /api/cards/backfill-scryfall`, which is the faster way to get Sprint 04 something to work with. `GET /api/cards/enrichment` shows the state of it.

## 0.35.0 — Sprint 01: the UI tells the truth again

### Fixed
- **`sensor.mtg_last_sync_at` was permanently `unknown`** — the one open bug in the HA bridge. SQLite's `CURRENT_TIMESTAMP` is UTC but *naive* (`2026-08-23 01:15:13`, no offset), and Home Assistant rejects a timezone-less state on a `device_class: timestamp` sensor. The publisher now normalises through `utc_iso()` (space→`T`, `+00:00` appended); a database that has never synced publishes nothing instead of inventing the current time as a "last sync".
- **The Dashboard header fabricated its two headline judgements.** "LAST SYNC" printed the *browser clock* next to a hardcoded green "SYNCED" badge, and the hero's "+7.70% vs. 90d" delta was a string literal. The header now reads `/api/sync/status` (real timestamp, dot and label follow the actual status — SYNCED / SYNCING… / FAILED / NEVER SYNCED), and the delta is computed from the 90-day value snapshots that were already being fetched three lines below the fake badge. A failed `/api/stats` now shows an error banner and an em-dash instead of presenting €0.00 as a fact.
- **The Archidekt bracket import read a key that does not exist.** The deck payload carries `edhBracket`; the code read `bracket`/`deckBracket` and the comment asserted that was correct — so every deck fell back to 0 regardless of what Archidekt held. (The field is also `null` on all currently synced decks, so no visible change until someone sets a bracket on Archidekt — the groundwork for computing brackets locally is Sprint 04.)
- **Deck completeness counted basic lands as missing cards.** "Forest ×3" appeared in `missing_cards` — and in `most_expensive_missing` — and skewed the percentage. The endpoint now applies the same name-based basic-land exclusion the Duplicates and Inbox queries already use.
- **The wishlist "Deals only" checkbox was a silent no-op** — the frontend sent `deals_only`, the backend reads `is_deal_only`; FastAPI never saw the parameter. Enabling it exposed a second latent bug: the deal filter ran *after* `LIMIT`/`OFFSET`, so deals beyond the first page were silently invisible. Deal filtering now fetches unpaged, filters, then paginates.
- **Changing a wishlist item's status back to "Wanted" always failed** with `400 "Item is not deleted"` — the edit dialog called `POST /restore`, which un-soft-deletes rather than re-opens. An item in "Not received" was permanently stuck (`/order` rejects that state too). The dialog now PATCHes `status: wanted`, and the PATCH clears the terminal-state bookkeeping (`acquired_at`, `not_received_at`, `is_ordered`, `ordered_at`). A collision with an existing active entry for the same printing answers 409 instead of a raw UNIQUE error.
- **The MCP setup wizard generated a config that could not work.** It emitted `MTG_BASE_URL`/`MTG_TOKEN`/`MTG_SSE_ENDPOINT` environment variables that `mcp-proxy.mjs` never reads (the proxy takes positional arguments), and pointed at `/mcp/sse`, a route that does not exist (the MCP mount is streamable HTTP at `/mcp`). The wizard now emits the real invocation — `node mcp-proxy.mjs <ha_url> <ha_token> <ingress_path>/mcp [mcp_auth_token]` — resolves the actual ingress path, mentions the `npm install ws` prerequisite, and appends the auth-token argument when `mcp_auth_token` is configured. The settings card no longer shows a hardcoded green "MCP Server running" badge next to the nonexistent SSE URL.
- **English UI showed the literal string `common.loading`** — the key existed only in the German dictionary.
- **`<html lang>` was hardcoded to `en`** while the UI renders German for German browsers; the language attribute now follows the detected UI language.

### Upgrading
No migration. `sensor.mtg_last_sync_at` shows a value after the next sync completes (or immediately after the add-on restart re-publishes stats, if a sync has ever completed).

## 0.34.1

### Fixed
- **The Inbox sell dialog was buried under the cards that follow it** — its confirm button often unreachable. The dialog is a `position: fixed` overlay with `z-index: 1000`, but it was mounted inside the acquisition card's `Panel`, whose `backdrop-filter: blur(14px)` makes the panel both a containing block for fixed-position descendants and a stacking context. The overlay's z-index therefore only competed *within* its own card, and every later inbox card — each its own stacking context, painted later in DOM order — drew on top of it. The dialog now portals into `document.body` (the same escape `CardHoverPreview` already uses), where its z-index means what it says.

## 0.34.0 — Colours, and a dashboard you can click

Archidekt reports a card's colours by name where Scryfall reports them by letter. Everything else here is downstream of the add-on having stored whichever arrived.

### Fixed
- **Every card in the Inbox was filed under "Colorless"** — `cards.color_identity` held Archidekt's `["Green"]` on 6625 of 7540 cards, where the rest of the app expected Scryfall's `["G"]`. The frontend classifier matched tokens against the set `{W,U,B,R,G}`, a full name matched nothing, and a card with no recognised colour is colourless. Pressing "Fix colors" could not help: it only re-fetched cards whose colour identity was *empty*, and these were not empty, just unreadable.
- **Mono-coloured cards were reported as multicolour, and their colour filter returned nothing** — the SQL tested a bare `LIKE '%G%'`. "Green" satisfies that twice: the 'G', and the 'r', because SQLite's LIKE is case-insensitive. A green card therefore counted as two colours and read as multicolour, while the mono-green filter — "has G and not R" — excluded it by its own 'r' and matched nothing at all. "Blue" broke identically through its 'B' and 'u'. White, Black and Red each contain exactly one colour letter and so worked by accident, which is why this survived unnoticed. Reported against *Beorn the Fierce*, mono-green, shown as Multicolor and missing from the green filter.

  Colours are now normalised to WUBRG letters at the single write path (`upsert_card`), so both ingest sources converge, and **migration 20** rewrites the existing rows. The SQL matches a comma-delimited token rather than a bare letter, so a name that somehow slips through reads as colourless — wrong by omission rather than by invention. The same normalisation also repairs the deck colour-identity strip, which had been asking Scryfall for a nonexistent `Green.svg`.
- **"No results" was reported as a backend failure** — filtering the Inbox to a colour that matched nothing produced *"Could not load inbox — the backend reported 140 pending cards but they could not be fetched. Check the add-on logs."* The page inferred an error from an empty list whenever the pending count was non-zero, so a working filter looked like a broken add-on. An empty result is now an empty state naming the filters and offering to clear them; the error banner is reserved for a request that actually failed.
- **`card.id` in the Inbox payload was the acquisition event's id** — `SELECT ae.*, c.*` puts two `id` columns in the row and `sqlite3.Row` returns the first. Latent, since nothing on the page read it yet.
- **`version.py`, `config.yaml` and `package.json` reported three different versions** (0.33.0, 0.33.1, 0.32.3). Realigned; `/healthz` had been a release behind since 0.33.1.

### Added
- **The Dashboard tiles are links.** Every stat card opens the page it summarises — Inbox, Collection, Decks, Cardmarket, Wishlist — and the hero value panel opens the collection sorted by price. Price-spike, mover and buy/sell rows open the collection filtered to that card. All keyboard-reachable.
- **An Inbox tile on the Dashboard**, showing the pending count and highlighted in the accent colour while anything is waiting. The Inbox was the one section with no presence there at all.
- **The Wishlist tile shows real numbers** instead of the placeholder `—`: item count and outstanding value.
- **Search and a decision filter in the Inbox history.** The archive is 2873 entries deep and could previously only be paged through 50 at a time. `GET /api/acquisitions/history` takes `search` and `state`; filtering happens in SQL, so it covers the whole archive rather than the loaded page.
- **Card-type filter on the Collection page** — Creature, Instant, Sorcery, Enchantment, Artifact, Planeswalker, Land, Battle, Kindred; several types OR together. Matching is restricted to the part of the type line before the em dash, so a "Creature — Human Artificer" does not answer an Artifact filter and a planeswalker with the Bear subtype does not answer a Creature one.
- **Multi-colour selection on the Collection page, with an explicit mode.** Several colours are ambiguous on their own, so the reading is chosen rather than assumed: *has any of*, *has all of*, *is exactly*, *has none of*. Colourless is selectable alongside the five colours. `GET /api/collection/` takes `color` (CSV) and `color_mode`.
- The Collection page reads `search`, `sort_by` and `sort_dir` from the URL, which is what makes the Dashboard deep links land on a filtered view.

### Upgrading
Migration 20 runs at startup and rewrites the colour columns of every affected card — 6629 of 7540 rows in about a third of a second on a Pi 5. No sync is required afterwards; the colours are corrected in place.

## 0.33.1

### Fixed
- **0.33.0 would not start on an existing installation** — the add-on crash-looped, and its ingress panel answered 502 behind Home Assistant. `init_db()` runs `SCHEMA_SQL` first and the migrations after it, and 0.33.0 added `CREATE INDEX … ON cards(cardmarket_id)` to that script alongside the new column. `CREATE TABLE IF NOT EXISTS` leaves an existing `cards` table untouched, so on every database created before 0.33.0 the index named a column that was not there yet: `sqlite3.OperationalError: no such column: cardmarket_id`, raised before `_migration_19` — which adds the column properly — was ever reached. A fresh database was unaffected, since there `CREATE TABLE` does carry the column; that is why the test suite stayed green while every real upgrade failed.

  The index is now created only by migration 19, for upgrades and fresh databases alike (a fresh one starts at schema version 1, so every migration runs). `tests/test_schema_upgrade.py` builds a pre-0.33.0 database and starts against it, and asserts the index is absent from `SCHEMA_SQL` so it cannot be reintroduced.

## 0.33.0 — Cardmarket prices per printing

Cardmarket prices a *product*, and a product is one printing. Everything here follows from the add-on having matched those products to cards by name alone.

### Fixed
- **Price-spike notifications described two different cards at once** — Cardmarket products were matched to the collection by card name, with no set, printing or expansion involved. All 31 "Terror" products — from the €0.08 reprint to the €1177.41 original — therefore collapsed onto whichever `cards` row `SELECT … WHERE LOWER(name) = ? LIMIT 1` happened to return. The morning notification read *"3 unused copies of Terror, +356%, €258.23 → €1177.41"*: the price of a printing that was never in the collection, beside the count of one that was. 1987 alerts were produced, 107 of them above the €5 notification threshold, so up to 107 persistent notifications could arrive after a single 03:00 sync.

  Printings are now joined on `cards.cardmarket_id`, the Cardmarket product id Scryfall publishes per printing. Every figure in an alert describes the same printing, and the message names its set.
- **`sensor.mtg_sell_potential_eur` reported €361,607 against a €6,772 collection** — the sell advisor joined `cardmarket_products` directly, so each collection row was multiplied by the number of products matching its name and `SUM(quantity)` counted a 3-copy playset as 93. Price and product now come from correlated subqueries; the aggregate counts each copy once. `sensor.mtg_active_price_alerts` showed the same inflated 1987 and is corrected by the same change.
- **Nine other price lookups took a random printing's price** — wishlist valuation, the inbox and spending sensors, the voice endpoint, the triage advisor's suggested sell price and the listing-health comparison all resolved a Cardmarket trend through `LOWER(cp.card_name) = LOWER(c.name)`, i.e. whichever printing the query planner returned first. Listing health additionally emitted one row per matching product, so a listing could appear several times in the buckets. All of them now join on the linked card, and fall back to the printing's own Scryfall price when Cardmarket has none.
- **Three games were downloaded on every sync** — `price_guide_{n}.json` numbers Cardmarket's *games*, not pages; the fetch loop read `{n}` as a page counter and merged Magic, World of Warcraft and Yu-Gi-Oh! into one list before stopping at the 403 from game 4 (games 5–8 exist and were reached only by accident of that error). The sync now fetches the Magic guide alone and keeps category 1, "Magic Single" — the guide carries twelve product categories, the rest being sealed product. The 20 MB product catalogue download is gone entirely: name, set and card link all come from our own `cards` row.

### Added
- **`cards.cardmarket_id`** — the Cardmarket product id of each printing, from Scryfall. Populated on card ingest, and backfilled for existing cards in batches of 75 via `POST /cards/collection`. Printings Cardmarket does not carry (tokens, some promos) are marked `0`, so the backfill asks about them once rather than on every run.
- **`POST /api/cardmarket/backfill-links`** — runs that backfill on demand instead of waiting for the nightly sync. The price sync calls it itself.

### Changed
- Deck usage behind an alert is counted across all printings sharing an oracle id, while ownership stays per printing: any printing fills a deck slot, so counting deck usage per printing would advertise a card as spare while a deck plays another copy of it. The asymmetry is deliberate and errs towards staying quiet.
- Migration 19 drops every existing product→card link; the next sync rebuilds them, and each sync now clears the links first so a printing sold out of the collection releases its product instead of keeping a stale claim. Price history is keyed by Cardmarket product and stays valid, so it is kept. Rows left unlinked are leftovers of the old name matching and are filtered out of `/api/cardmarket/products` and the MCP price-history lookup.

### Upgrading
`notify_min_alert_value_eur` was raised to `999999` to silence the broken notifications. Set it back to `5.0` in the add-on options and restart — `get_settings()` is `@lru_cache`d, so a restart is required. The first sync after the update runs the full backfill and takes noticeably longer.

## 0.32.3

### Fixed
- **Repository links pointed at a repository that does not exist** — `config.yaml`, `repository.yaml` and the install instructions in the README all named `HerrFuchs/mtg-collection-ha`, while the add-on actually lives at `GrazFuchs/MTG-App-HA`. The documentation link in the HA add-on panel therefore went nowhere, and anyone following the README added a repository URL that cannot be resolved. Historical CHANGELOG entries keep the old URL — they describe what was true at the time.

## 0.32.2

### Fixed
- **White page and a 404 after every add-on update** — `index.html` keeps its name while the asset filenames carry a content hash that changes with every build, so a browser-cached copy kept requesting bundles the new container no longer had. The HTML (and every other unhashed file) is now served with `Cache-Control: no-cache, must-revalidate`; only the content-hashed files under `/assets/` are cached long-term, where it is safe. No more clearing the browser cache by hand after an update.
- **Reloading a sub-page 404'd** — `/inbox`, `/settings`, `/decks/42` and friends are client-side routes with no file behind them, so a reload or a bookmark hit a 404. Unknown paths now fall back to the app shell. Requests that name a file (`.js`, `.css`, …) and anything under `/api` or `/mcp` keep returning a real 404, so a missing asset stays a clear error instead of becoming a confusing MIME-type failure, and API errors are not swallowed by the shell.

New `app/static_files.py` (`SpaStaticFiles`) replaces the plain `StaticFiles` mount.

## 0.32.1

### Fixed
- **Price-spike notifications never arrived** — Creating a persistent notification calls the Core API proxy at `http://supervisor/core/api/...`, which the Supervisor only allows when the add-on declares `homeassistant_api: true`. That key was missing from `config.yaml`, so every attempt came back `401 Unauthorized` — 76 of them in a single night's log. Added the permission.
- **Log noise on a rejected notification** — A rejected proxy call is a configuration problem, not a runtime fault; it now logs one line per alert (including the hint about the missing permission for 401/403) instead of an identical traceback each time.

## 0.32.0 — Sprint 32 (deep links)

### Added
- **`sensor.mtg_ingress_url`** — The add-on publishes its own ingress path, with one ready-made link per UI route as attributes (`dashboard`, `decks`, `collection`, `inbox`, `duplicates`, `cardmarket`, `wishlist`, `settings`). Dashboard cards can link into the add-on without a hardcoded slug — which also survives a reinstall, since the ingress token changes with it. Stays *unknown* outside a Supervisor environment, where no absolute link exists.
- New `services/ingress.py` resolves every link into the add-on UI in one place.

### Fixed
- **Deep links in persistent notifications never worked** — The "Open in MTG Collection" link resolved the ingress slug from an `INGRESS_TOKEN` environment variable that nothing sets (`run.sh` exports `INGRESS_ENTRY`), so the link always fell back to a bare path such as `/cardmarket`, which resolves against Home Assistant itself and 404s. Links are now built from the path the Supervisor hands the add-on, and are omitted entirely when it is unknown rather than pointing somewhere wrong.

## 0.31.0 — Sprint 31 (game-logger form in HA)

### Added
- **Game-logger form** — The add-on publishes its own input entities under a separate **MTG Game Logger** device, so logging a game from a dashboard needs no HA helpers and no templating: `select.mtg_log_deck`, `select.mtg_log_result`, `number.mtg_log_pod_size` / `_mulligans` / `_missed_land_drops` / `_turns`, `switch.mtg_log_on_play`, `text.mtg_log_opponents` / `_notes`, `button.mtg_log_submit` and `sensor.mtg_log_status`. Pressing the button writes the game, clears the form, refreshes the deck performance sensors and reports the outcome on the status sensor. Ready-made dashboard card in [docs/ha-integration.md](../docs/ha-integration.md).
- **Deck selector follows the database** — The options of `select.mtg_log_deck` are rebuilt on startup and after every sync (scheduled or manual). Decks that share a name get their id appended so every option resolves to exactly one deck.
- **Form state survives a restart** — Field values live in the new `ha_form_state` table (migration 18) instead of memory, so a half-filled form is still there after an add-on restart.
- Numbers outside their range are clamped, texts are cut to HA's 255-character limit, and a select value that is no longer a valid option is rejected with a note on the status sensor rather than being stored. The form's number bounds are checked against the game model in the tests, so the form cannot offer a value the API would reject.
- Deleting or renaming a deck while it sits selected in the form is caught at submit time (and reset on the next publish) instead of logging the game against the wrong deck.

### Fixed
- `discovery_payload` no longer puts a `state_topic` on stateless entities; HA rejects a `button` config that carries one.

## 0.30.0 — Sprint 30 (log games from HA)

### Added
- **`log_game` MQTT service** — Log a played game from an automation, script or voice command: `{"deck": "Atraxa", "result": "win", "turns": 9, …}`. The deck is matched by id or by name (case-insensitive, exact match first, then a unique substring); an ambiguous or unknown name is never guessed at — the response lists the candidates instead. Field validation reuses the same model as the REST endpoint, so bounds like `pod_size` 1–8 hold everywhere. New `services/game_log.py`.
- **`triage` MQTT service** — Decide one inbox item (`{"event_id": 42, "action": "keep"}`), so the inbox notifications from 0.29.0 can carry "Keep" / "Sell" buttons. Delegates to the API handler, so listing creation and the decision snapshot behave exactly as in the UI; `source` defaults to `other` for decisions made from HA.
- **`create_listing` MQTT service** — Create a Cardmarket listing straight from a duplicates alert.
- **Deck performance sensors** — `mtg_games_30d`, `mtg_winrate_30d` (with W/L/D attributes), `mtg_last_game_at`, `mtg_last_game_result`, plus one `mtg_deck_<deck_id>_winrate` per deck played in the last 90 days, carrying games/W/L/D/last_played as attributes. Keyed by deck id, so renaming a deck in Archidekt keeps the sensor and its history; a deck that goes quiet for 90 days is removed from HA and reappears when it is played again. Refreshed on every game change (UI or MQTT) and with the daily publish.
- **Voice sentences** — `HassMTGLogWin` / `HassMTGLogLoss` with a `{deck}` slot ("trag einen Sieg mit Atraxa ein"), plus `HassMTGGetInbox`. Wiring example in [docs/ha-integration.md](../docs/ha-integration.md), together with an actionable-notification automation for triage.

### Changed
- A metric whose value is `None` is no longer published, so a sensor without a value (e.g. `mtg_last_game_at` before the first logged game) stays *unknown* in HA instead of receiving an empty payload that `device_class: timestamp` cannot parse.

## 0.29.0 — Sprint 29 (inbox & sell sensors)

### Added
- **Inbox sensors** — `mtg_inbox_pending`, `mtg_inbox_needs_sell`, `mtg_inbox_needs_keep`, `mtg_inbox_pending_value_eur`, `mtg_inbox_oldest_age_days`, `mtg_inbox_decided_30d` and a `binary_sensor.mtg_inbox_has_pending`. The pending sensor carries the 10 newest cards (name, set, quantity, triage suggestion, reason, price, age) as attributes; the decided sensor carries a per-state breakdown. Basic lands are excluded, matching the Inbox UI.
- **Selling sensors** — `mtg_sell_candidates` and `mtg_sell_potential_eur` from the sell advisor, plus `mtg_duplicates_surplus_cards`, `mtg_duplicates_surplus_value_eur` and `mtg_unlisted_value_eur` (the surplus not yet listed on Cardmarket). Candidates and unlisted rows carry their top 10 entries as attributes.
- **MTGStocks signal sensors** — `mtg_signals_buy` / `mtg_signals_sell`, published only while `mtgstocks_enabled` is on; turning the option off clears them from HA.
- **Refresh on triage** — Confirming or undoing an inbox decision refreshes the inbox sensors, debounced by 5 s so working through the inbox does not trigger one full recompute per click. Everything else refreshes with the existing daily stats publish.
- **Predictable entity ids** — Discovery now pins `object_id`, so a fresh install gets exactly the entity ids listed in the docs (`sensor.mtg_inbox_pending`, …) instead of ids derived from the device and entity name. Existing entities keep the id they already have.
- Example automations for the new sensors in [docs/ha-integration.md](../docs/ha-integration.md): inbox push notification, weekly selling report, "inbox left unattended" reminder.

### Fixed
- **Sell advisor skipped cards that are in no deck** — In `HAVING total_owned > in_decks`, SQLite resolved the bare `in_decks` to the joined `deck_use.in_decks` column (NULL for a card in no deck) rather than to the `COALESCE(…, 0)` output alias, so the comparison evaluated to NULL and the row was dropped. Cards not used in any deck — the most obvious sell candidates — never showed up in `suggest_sells`, and its "nicht in Decks" reason was unreachable. Affects the Dashboard sell suggestions and the `suggest_sells` MCP tool.
- **`suggest_sells` with no target** — The advisor can now be called with `target_amount_eur=None` to rank every candidate and offer all unused copies, instead of stopping at the first €50.

### Changed
- The duplicates CTE moved from `routers/collection.py` to `services/queries.py` so the Duplicates API and the surplus sensors share one definition of "surplus".

## 0.28.0 — Sprint 28 (MQTT foundation)

Groundwork for the HA dashboard integration planned in [docs/ha-dashboard-sprints.md](../docs/ha-dashboard-sprints.md). No new entities — the existing ones get more reliable instead.

### Added
- **Availability / online state** — The add-on now holds a single long-lived MQTT connection (`services/ha_mqtt.py`) that publishes a retained `online` on `mtg-collection/status` and registers `offline` as its Last Will; a graceful stop publishes `offline` explicitly. Every discovery config references that topic, so all MTG entities go *unavailable* in HA while the add-on is down instead of showing stale values.
- **Entity abstraction** — `services/ha_entities.py` builds the discovery payloads for all component types (`sensor` today, `select`/`number`/`switch`/`text`/`button` for the upcoming game-logger form).
- **Discovery snapshot tests** (`tests/test_ha_discovery.py`) pinning every `unique_id`, plus end-to-end tests of the publish/subscribe paths against a fake broker.

### Changed
- **One MQTT connection instead of one per publish** — Publishers and the service subscriber share the manager's connection; calls made before the manager is up (e.g. from a request handler during startup) fall back to a single short-lived connection per batch. Behaviour of all existing topics, entity names and `unique_id`s is unchanged.
- **Long-term statistics for the count sensors** — `total_cards`, `unique_cards`, `total_decks`, `active_price_alerts`, `acquired_count_30d` and the three `listings_*` sensors now declare `state_class: measurement`, so HA records history and can chart them. They previously had none.

### Fixed
- **"Impossible state class" on the monetary sensors** — `total_value_eur/usd`, `spending_30d` and `spending_30d_value` combined `device_class: monetary` with `state_class: measurement`, which HA rejects (monetary only accepts `total`); they were logged as invalid and got no statistics. Now `total`.

## 0.27.0 — Sprint 27 (MTGStocks integration)

### Added
- **MTGStocks.com integration** — Optional new data source (off by default; enable via the `mtgstocks_enabled` add-on option). Uses MTGStocks' (unofficial) API with a browser-like header set and a polite ~1 req/s rate limit, degrading gracefully if the source is blocked/unavailable. Synced daily after the Cardmarket job.
  - **Market Movers** — Daily MTGStocks "interests" (market & average boards, regular + foil) filtered to cards you own, surfaced as a **Collection Movers** section on the Dashboard. Exact per-printing matching (set abbreviation + collector number) via each print's `sets[]`.
  - **Buy/Sell signals** — All-time-high/low tracking per print drives a **Trade Signals** Dashboard section: wishlist cards trading near their all-time low (buy) and owned, unused copies near their all-time high (sell).
  - **Long-term price history** — Multi-year TCGplayer (USD) trend with all-time high/low, shown as an extra sparkline in the price-trend hover (wishlist rows).
  - New tables (`mtgstocks_prints`, `mtgstocks_price_history`, `mtgstocks_interests`, migration 17), client `clients/mtgstocks.py`, service `services/mtgstocks_prices.py`, and routes under `/api/mtgstocks` (`/status`, `/movers`, `/signals`, `/price-history/{card_id}`, `/sync`).

## 0.26.0 — Sprint 26 (MCP server enhancements)

### Added
- **Batch card lookup (`get_cards`)** — New MCP tool that resolves several cards in one call. Names are matched against the local DB first (no rate limit), and any misses are fetched from Scryfall in a single `POST /cards/collection` request (chunked at 75/req via the new `ScryfallClient.get_cards_collection`). Returns details + prices per card and a `not_found` list.
- **Batch collection lookup (`find_cards_in_collection`)** — Batched version of `find_card_in_collection`: owned/foil counts, deck usage and price for many cards in a single SQL pass.
- **`bulk_add_to_wishlist`** — Add many cards to the wishlist at once (e.g. paste a decklist) with shared priority/tags/deck; reports added vs skipped.
- **Structured `analyze_deck`** — MCP tool returning mana curve, colour-pip distribution, card-type breakdown and average mana value (previously only a prompt template).
- **`get_acquisition_history`** — Exposes the Inbox booking archive (see 0.24.0) over MCP.

### Fixed
- **MCP `get_duplicates` colour filter** — Now uses the same format-robust colour matching as the REST API (see 0.24.0), so single-colour filters behave identically in both.
- **`mcp-proxy.mjs` "Unexpected end of JSON input" warning** — The stdio proxy forwarded the empty HTTP 202 body of MCP notifications (e.g. `notifications/initialized`) as a blank stdout line, which the MCP client tried to `JSON.parse`. Empty responses are now skipped.

## 0.25.0 — Sprint 25 (cross-cutting UI)

### Added
- **"Lands" filter option** — A 🟤 Lands choice was added to the colour filters on the Wishlist and Inbox tabs (Duplicates and Cardmarket already had it), filtering to land-type cards. Backed by the shared, format-robust colour-filter helper.
- **Open on Cardmarket** — Every card row in the Duplicates, Inbox and Collection tabs now has an icon button that opens the card's Cardmarket page in a new tab (shared `CardmarketButton`).
- **Back to Top** — A floating button appears after scrolling and smoothly returns to the top of the page (`components/BackToTop.tsx`, attached to the main scroll container).

### Changed
- **Deck "Combos in this Deck"** — The section is now collapsible and **collapsed by default** (state persisted). Cards listed in a combo's detail dialog are now clickable links that open the card's Scryfall page in a new tab.

## 0.24.0 — Sprint 24 (intake & duplicates reliability)

### Fixed
- **Single-colour pip filters returned nothing** — Filtering by Red/Blue/etc. in the Inbox and Duplicates (and Collection/Wishlist) tabs missed cards whose `color_identity` was stored in a non-JSON form, because the SQL required literal JSON quotes (`LIKE '%"R"%'`). Colour matching is now format-robust (matches the bare colour letter and counts distinct WUBRG letters for mono/multi/colourless), applied consistently across all routers and the MCP `get_duplicates` tool. A defensive `parse_color_identity` helper also prevents the API from crashing on non-JSON values.
- **Intake duplicate check missed owned copies** — The triage advisor matched other printings case-sensitively (inconsistent with the rest of the app) and, when a new copy merged into an existing collection row, excluded that whole row — hiding a genuine pre-existing duplicate. Matching is now case-insensitive and subtracts only the freshly-arrived quantity from its own row.

### Added
- **Inbox booking history / archive** — Confirming a triage decision now records a snapshot of the decision, the suggestion shown and the card's state at that moment (new `decision_snapshot` column, migration 16). A new **History** view in the Inbox (`GET /api/acquisitions/history`) shows how each item was booked and how it was presented at confirmation.
- **Duplicates urgency tools** — A "Most copies" sort plus quick-filter pills ("≥ 3 / ≥ 5 surplus", "≥ €5 / ≥ €20 value", "Not yet listed") to surface the most pressing duplicates (`min_extras` / `min_value_eur` / `unlisted_only` query params).

## 0.23.0 — Sprint 23 (wishlist enhancements)

### Added
- **Ordered-cards filter** — The Wishlist (wanted tab) now has an "Ordered / Not ordered / All" filter over the existing `is_ordered` flag.
- **Interactive price chart on hover** — Hovering a wishlist card name shows an interactive sparkline of the last 2 weeks of Cardmarket trend prices; the popup is hoverable and a crosshair tracks the cursor to read the price/date at each point. The reusable `PriceTrendHover` now also powers the Cardmarket page's price hover, and `Sparkline` gained an `interactive` mode.

### Fixed
- **Wishlist image didn't follow the chosen edition** — Editing a wishlist item's set/version only updated the displayed image/price when that printing already existed locally; the chosen printing is now imported from Scryfall when missing, so the thumbnail and price always match the selected edition.

## 0.22.0

### Added
- **Deck Performance Tracker** — Log how each game went and see aggregate stats per deck. Each game records result (win/loss/draw), date, on-the-play, pod size, mulligans, missed land drops, turns, opponents/commanders, and free-text "what worked / what didn't / notes". A new section on the deck page shows win rate, W/L/D, recent form, on-play win rate, and averages, plus a list of recent games. Backed by a new `deck_games` table (migration 15) and `GET/POST/PATCH/DELETE /api/decks/{id}/games` + `GET /api/decks/{id}/performance`.

### Fixed
- **Deck view hover/category overlap** — The card hover-preview is now scoped to the card name only, so it no longer overlaps the adjacent "+N" extra-category tooltip when both were triggered.

## 0.21.0

### Fixed
- **Cardmarket Active Listings showed nothing** — The v0.17.3 listings query used a correlated subquery inside a `LEFT JOIN ... ON` that raised `sqlite3.OperationalError: no such column: l.set_code`, so `/api/cardmarket/listings` 500'd and the table rendered "No listings". The card match is now resolved in Python: listings are fetched plainly and each is paired with exactly one best-match card (preferring the matching set, then most recent), which also keeps the v0.17.3 fix against row multiplication.
- **Misleading empty state** — The "Sync from profile" hint (no such feature exists) is now "Import a CSV or list duplicates from the Duplicates tab."

## 0.20.0

### Added
- **Collection Tag filter** — A real filter dropdown for collection (Archidekt) tags, backed by a new `GET /api/collection/tags` endpoint that returns the distinct individual tags. (The tag badge was already shown; previously only a *sort* existed.)
- **Wishlist set/version editing anytime** — The Edit dialog now has a Set/Version picker and a Foil toggle, editable for any status (wanted/ordered/acquired). `WishlistItemUpdate` (PATCH) accepts `set_code` + `is_foil`, and choosing a set now repoints the item to that printing so the displayed set name, image and price follow the choice (also applied on Order/Acquire).

### Changed
- **Wishlist order badge** — The "Ordered" badge now uses a cleaner soft (tint) rounded style.

## 0.19.0

### Added
- **Inbox name search** — Search pending acquisitions by card name.
- **Inbox sort** — Sort the inbox by Newest, Color, Set, or Name.
- **Inbox color filter** — Dropdown to show only one colour bucket (W/U/B/R/G/Multicolor/Colorless) across all pages, complementing the existing colour headers.
- **"Fix colors" backfill** — `POST /api/acquisitions/backfill-colors` re-fetches colour data from Scryfall for pending cards whose `color_identity` is empty (Archidekt sometimes returns a thin card), so the colour groups/filter stop classifying everything as Colorless. Exposed as a button in the Inbox.

### Fixed
- **Basic lands in Inbox** — Inbox now excludes basic lands by name (shared with Duplicates), covering snow-covered basics and cards with an empty `type_line`.

## 0.18.0

### Fixed
- **Basic lands shown in Duplicates** — Filtering relied on `type_line NOT LIKE '%Basic Land%'`, which let through Snow-Covered basics (`Basic Snow Land — …`) and any card with an empty `type_line` (e.g. Cardmarket-imported cards). Replaced with a deterministic **name-based** exclusion (`Plains/Island/Swamp/Mountain/Forest/Wastes` + Snow-Covered variants), shared via `services/queries.basic_land_exclusion_sql()` and reused by the MCP `get_duplicates` tool.
- **Duplicates color filter (monocolor)** — Selecting a single color now matches every card whose colour identity **includes** that colour (mono **and** multicolor), and a new **Monocolor** option lists all single-colour cards.

### Changed
- **Test harness** — Tests now initialise an isolated, file-backed SQLite database per test (lifespan isn't run under `ASGITransport`), fixing the previously-failing acquisitions smoke tests and enabling seeded API tests.

## 0.17.3

### Fixed
- **Cardmarket listings duplicated rows** — The LEFT JOIN to the `cards` table matched ALL printings of a card name, multiplying listing rows. Replaced with a scalar subquery that picks exactly one card per listing (preferring matching set_code, then most recent).
- **Cardmarket SET column empty** — Frontend now displays `set_name` (expansion) from the listing instead of the always-empty `set_code`.

## 0.17.2

### Fixed
- **Deck sync card loss (foil/non-foil)** — Changed `INSERT OR REPLACE` to `ON CONFLICT DO UPDATE SET quantity += excluded.quantity` so duplicate keys (same card_id + modifier) sum quantities instead of silently discarding the first entry. Fixes 5-card loss when same basic land exists as both Normal and Foil.
- **DeckView hero text in light mode** — Hero title and meta text now always use light colors (`#EDEDF5`) since the overlay is always dark, regardless of theme mode.

## 0.17.1

### Fixed
- **Cardmarket CSV import** — Added diagnostic logging and empty-file guard; header detection now strips whitespace for resilience against format changes; frontend shows `error_details` on failed imports.
- **Deck card count** — Card count now uses `SUM(quantity)` instead of `COUNT(rows)`, correctly reflecting total cards including multiples.

## 0.17.0

### Added
- **Cross-set selling** — Sell dialog shows per-printing breakdown (set + foil) with individual sell actions and quantity caps.
- **Bulk-Sell** — Multi-select printings of the same card and create Cardmarket listings in one step.
- **Column sort (Duplicates)** — Clickable table headers for name, extras, price, and set.
- **include_listed toggle (Duplicates)** — Checkbox to show/hide rows where all extras are already listed.
- **Multi-category deduplication (Deck View)** — Cards appear under first category only; secondary categories shown via hover badge.
- **AI Assessment collapsible** — AIAssessmentBox is now collapsible with localStorage persistence.
- **Color filter (Wishlist)** — W/U/B/R/G/M/C filter bar replaces accordion grouping.
- **Group-by-Card-Name toggle (Wishlist)** — Expandable rows grouping same card across sets/conditions.
- **Set/Version selection (Wishlist)** — Set picker when marking items as Ordered or Acquired.

### Fixed
- **Monocolor filter** — Duplicates color filter now excludes multicolor cards (cards with commas in color_identity).
- **Extras calculation** — Subtracts Cardmarket-listed quantity aggregated by card_name (not per-printing).
- **Combo Detection** — Fixed Spellbook API payload format (list of dicts) and response parsing (`results.included`).
- **Wishlist all Colorless** — Added `c.color_identity` to wishlist SELECT query.
- **Order tag styling** — Cleaned up "Bestell Tag" visual appearance.
- **Collection tag display** — Tag badge rendered on collection entries.
- **Branding** — Header renamed from "STELLAR·VAULT" to "MTG·Collection Manager".
- **Cardmarket listing count** — Section header shows "LISTINGS" instead of misleading "ROWS".
- **Inbox basic lands** — Pending acquisitions queries exclude Basic Lands via `type_line NOT LIKE '%Basic Land%'`.

## 0.16.0

### Changed
- **Duplicates page: printing-level aggregation** — one row per (card + set + foil) instead of card-name grouping.
- **Listing-aware extras** — `extras_after_listings` subtracts already-listed Cardmarket quantities; default hides fully-listed rows.
- **Basic Land filter** — Basic Lands excluded from duplicates.
- **Color filter (CSV)** — supports W,U,B,R,G,M,C,L with AND logic for multi-color.
- **Scoped set filter** — new `GET /api/collection/duplicates/sets` returns only sets with actual duplicates.
- **Foil indicator** — ◆ badge on foil printings in table and sell dialog.
- **Sell dialog respects foil & listing cap** — quantity capped to `extras_after_listings`, `is_foil` passed to listing.
- **MCP `get_duplicates` updated** — mirrors printing-level logic with color param.

### Fixed
- **Group dropdown crash** — removed crashing Group-by dropdown (caused black screen).
- **CSS spacing** — added padding between Value column and Sell button.

### Performance
- **Composite index** on `cardmarket_listings(card_name, set_code, is_foil)` for JOIN performance.

## 0.15.0

### Performance
- **SQLite WAL + PRAGMA tuning**: `journal_mode=WAL`, `synchronous=NORMAL`, `cache_size=-20000` (20 MB page cache), `temp_store=MEMORY` applied to every connection.
- **Connection pool** raised from 2 → 6 concurrent DB connections.
- **Migration 14**: 5 new indices (`idx_cards_name_nocase`, `idx_cards_set_code`, `idx_deck_cards_card_id`, `idx_collection_card_id`, `idx_cardmarket_listings_card_name`) + `ANALYZE`.
- **GZip middleware** (`minimum_size=1000`) compresses API payloads by ~60–80%.
- **Cache-Control headers** on hot read endpoints: `/collection/sets` (60 s), `/decks/`, `/stats/`, `/cardmarket/stats` (30 s each).
- **React Query migration**: All 8 pages (Collection, DeckView, Decks, Cardmarket, Duplicates, Settings, Dashboard, Inbox) fully migrated to `useQuery`/`useMutation`. Zero legacy `useEffect` data-fetchers remaining. QueryClient defaults: `staleTime=30s`, `gcTime=5min`, `retry=1`, `refetchOnWindowFocus=false`, `keepPreviousData`.
- **Deck prefetch on hover**: `Decks.tsx` prefetches deck detail on mouse-enter via `queryClient.prefetchQuery`.

### Fixed
- **Cardmarket stats**: `/api/cardmarket/stats` now correctly distinguishes `unique_cards` (`COUNT(DISTINCT card_name)`) from `total_rows` (raw listing count). Header shows "X CARDS · Y LISTINGS · Z COPIES". `unique_listings` retained as deprecated backward-compat field.
- **Cardmarket search regression**: Each keystroke no longer fires an API request — search is committed on Enter only (`searchInput` / `committedSearch` split).

## 0.14.1

### Fixed
- **Inbox White-Screen Crash** (`TypeError: undefined is not an object`): `getColorBucket` now handles null/undefined cards, null/empty/JSON-array-string/concatenated-letter (`WU`) color identities without throwing. Root cause was `Map.get(undefined).push()` when a card had a malformed or missing `color_identity`.
- **`groupByColorBucket`** pre-initialises all 8 `BucketKey` slots so `.get()` can never return `undefined`.
- **`Duplicates.tsx`** migrated to `getColorBucketLegacy` — no type regression.

### Added
- **`ErrorBoundary` component** (`frontend/src/components/ErrorBoundary.tsx`): Class component with `getDerivedStateFromError`, `componentDidCatch`, and a `retry()` callback; wraps the Inbox list as defense-in-depth so a single render error cannot white-screen the whole page.
- **`BucketKey` type + `BUCKET_KEYS` + `groupByColorBucket`** exported from `utils/colors.ts`.
- **Vitest** added to frontend devDependencies (`npm test`) with 16 regression tests covering all `color_identity` edge cases — all green.

## 0.14.0

### Fixed
- **Schema-Drift Fix** (`triage_advisor.py`): Column names corrected — `cph.trend_eur` → `cph.trend`, `cph.snapshot_at` → `cph.date`. Resolves `/api/acquisitions/pending` returning HTTP 500 and Inbox showing empty despite 190+ pending cards.

### Added
- **Graceful Triage Fallback**: `get_suggestion()` wrapped in `try/except` — `sqlite3.OperationalError` and unexpected exceptions are caught, logged via `logger.error/exception`, and a safe `DEFAULT_SUGGESTION` (action: `keep`) is returned. Schema drift in future sprints can no longer crash the entire `/pending` route.
- **Inbox ErrorBanner**: Inbox page now distinguishes three states: (1) truly empty (celebration 🎉), (2) `loadError` or items/stats mismatch → `ErrorBanner` with pending count and Retry button, (3) normal items list. Prevents misleading "Inbox zero" when the backend fails.
- **ErrorBanner Component** (`frontend/src/components/ErrorBanner.tsx`): Reusable Fluent UI `MessageBar`-based error display with title, message, and optional action slot.
- **Acquisition Smoke Tests** (`backend/tests/test_acquisitions_smoke.py`): Two `pytest-asyncio` tests asserting `/api/acquisitions/pending` and `/api/acquisitions/stats` return HTTP 200 with correct response shapes against an in-memory SQLite DB.
- **`requirements-dev.txt`**: New file — `pytest>=8`, `pytest-asyncio>=0.23`, `httpx>=0.27` for backend test runs.
- **i18n**: 4 new keys per language — `inbox.empty_celebration`, `inbox.error.title`, `inbox.error.api_failed`, `common.retry` (EN + DE).

## 0.13.0

### Added
- **Sprint 13 — Triage Polish, Categorization & Hover-Fix**
- **CardHoverPreview Refactor**: Portal-based hover preview (`createPortal` → `document.body`), z-index 2147483000 — survives all Fluent UI dialogs; auto-hides on scroll/resize; 200 ms show delay; bounds-checked with oracle-text height
- **Sibling-Aware Triage**: Advisor detects earlier pending events for the same card (`ae.id < current`) and factors them into sell/keep logic — prevents double-keep on batch imports
- **Sell Price Pre-Fill**: Triage dialog pre-fills price from Cardmarket trend price (falls back to Scryfall EUR); hint text shown below field; uses `triage.sell_price_hint` i18n key
- **Multi-Copy Sell Qty**: `sold_new` triage exposes quantity selector (1…qty_delta) when more than one copy arrived; `sell_qty` validated server-side (422 if > qty_delta)
- **Inbox Filter Bar**: Three filter pills — All / Suggested: Sell / Suggested: Keep — URL-persistent via `useSearchParams`
- **Inbox Color-Grouping**: Events grouped by MTG color bucket (W/U/B/R/G/M/C/L), collapsible sections, collapse state persisted in localStorage
- **Duplicates Page Filter+Group+Sort**: Search, color dropdown, set dropdown, group-by (None/Color/Set), sort (value/extras/name/set/color) — all URL-persistent
- **Cardmarket Listings Filter**: Color, set, source (Draft/Imported), sort dropdowns; Pending-first split renders Draft and Live sections separately; card name wrapped in `CardHoverPreview`
- **`secret_lair` Source**: Added to `SOURCE_VALUES`, `WishlistSource`, `SourcePicker`, and `WishlistAcquireDialog`
- **`utils/colors.ts`**: New shared `getColorBucket` utility + `BUCKET_ORDER/LABELS/EMOJI` constants
- **i18n**: 20 new keys in EN + DE (inbox filters, color labels, triage hints, source, duplicates group-by, cardmarket sections)

### Fixed
- `TriageDecisionDialog` price hint now uses `t('triage.sell_price_hint')` instead of hardcoded English string
- Added `CREATE INDEX idx_cards_name_lower ON cards(name COLLATE NOCASE)` for sibling query and listings JOIN performance

## 0.12.0

### Added
- **Inbox & Triage Workflow** (Sprint 12): Triage newly acquired cards detected during Archidekt sync — keep, sell, swap, or dismiss with one click
- **Delta Detection**: Collection sync now snapshots quantities before sync and generates acquisition events for positive deltas (skipped on first sync and full resync)
- **Triage Advisor**: Automated keep-score engine comparing printings by price and foil status — suggests keep/swap/sell with reasoning
- **Acquisition Events API**: 4 REST endpoints — `GET /api/acquisitions/pending` (paginated), `GET /api/acquisitions/stats`, `POST /api/acquisitions/{id}/decide`, `POST /api/acquisitions/{id}/undo`
- **Inbox Page**: Full triage UI with value filter, pagination, source picker (sessionStorage-persistent), skip functionality, and empty state
- **AcquisitionCard Component**: Card detail with existing printings, deck usage, suggestion display, and action buttons
- **TriageDecisionDialog**: Modal for editing listing price/condition/language before creating Cardmarket listing
- **Collection CM-Badge**: 🛒 badge on collection entries with active Cardmarket listings (LEFT JOIN on `cardmarket_listings`)
- **Nav Badge**: Pending triage count in navigation with 60s polling + `visibilitychange` refresh
- **2 new MCP Tools**: `get_pending_triage`, `decide_triage`

### Changed
- `sync_collection()` accepts `is_resync` parameter to suppress event generation during full resyncs
- `run_full_resync()` passes `is_resync=True` through to `sync_collection()`
- Collection API enriched with `cardmarket_listing_count` and `cardmarket_listed_qty` per entry

### Technical
- Schema Migration #13: `acquisition_events` table with 13 columns, 2 indexes (`idx_acq_pending`, `idx_acq_card`)
- `backend/app/services/triage_advisor.py` — isolated suggestion engine (no router dependencies)
- `backend/app/routers/acquisitions.py` — triage REST API with cross-field validation
- `frontend/src/pages/Inbox.tsx`, `frontend/src/components/inbox/AcquisitionCard.tsx`, `TriageDecisionDialog.tsx`, `SourcePicker.tsx` — new components
- i18n: 14 new keys per language (EN + DE) for inbox/triage and collection CM-badge

## 0.11.0

### Added
- **Deck Combo Detection** (Sprint 11): Automatic combo discovery via Commander Spellbook integration — combos synced on every deck sync + manual refresh
- **Deck Compare**: Compare 2–4 decks side-by-side — overlap matrix, common cards, unique-per-deck, color identity intersection (`GET /api/decks/compare?ids=…`)
- **Deck Completeness**: Per-deck ownership progress bar with missing card list and estimated cost (`GET /api/decks/{id}/completeness`)
- **Owned-Indicator on Card Search**: Scryfall search results now show `owned_quantity`, `owned_foil_quantity`, and `in_decks` fields (batch query, no N+1)
- **Combo Detail Dialog**: Click any combo to see cards involved, results, prerequisites, steps, and Spellbook link
- **DeckCompare Page**: Full deck comparison UI with multi-select dropdowns, overlap matrix grid, URL-param-based state
- **OwnedBadge Component**: Reusable badge showing "✓ Owned (N×)" with foil indicator and deck tooltip
- **3 new MCP Tools**: `get_deck_combos`, `compare_decks`, `find_card_in_collection`

### Changed
- `sync_deck()` now triggers best-effort combo sync after successful Archidekt import (1s rate-limit between decks)
- Card search endpoints (`/api/cards/search`, `/api/cards/by-name`) enriched with collection ownership data
- Decks page adds "⌬ Compare Decks" navigation button
- DeckView page shows Combos section and Completeness section below AI Assessment

### Fixed
- FastAPI route ordering: `/compare` now correctly defined before `/{deck_id}` to prevent path-parameter matching
- `GET /api/decks/compare` returns HTTP 400 for non-numeric deck IDs (was unhandled ValueError → 500)
- React Fragment key warning in DeckCompare overlap matrix

### Technical
- Schema Migration #12: `deck_combos` table with `deck_id` FK CASCADE, UNIQUE constraint, 2 indexes
- `backend/app/clients/spellbook.py` — Commander Spellbook API client (singleton)
- `backend/app/services/combo_sync.py` — combo fetch/cache service with DELETE-before-INSERT strategy
- `frontend/src/pages/DeckCompare.tsx`, `frontend/src/components/deck/DeckCombosSection.tsx`, `DeckCompletenessSection.tsx`, `ComboDetailDialog.tsx`, `OwnedBadge.tsx` — new components
- i18n: ~20 new keys per language (EN + DE) for combos, compare, completeness, owned indicators

## 0.10.0

### Added
- **Acquisition Tracking** (Sprint 9): Wishlist items now track the full buy-lifecycle via new fields `paid_price_eur`, `expected_price_eur`, `source`, `is_ordered`, `ordered_at`, `not_received_at` (Schema Migration #11)
- **Order Flow**: `POST /api/wishlist/{id}/order` marks an item as ordered with optional expected price; `POST /api/wishlist/{id}/unorder` cancels it. Ordered items show a 📦 badge with expected price in the Active-Tab
- **Acquire Dialog**: "Mark as Received" opens a dialog pre-filled with `expected_price_eur`; user can adjust to actual paid price and select source (`cardmarket | whatnot | booster | trade | gift | shop | other`)
- **Not-Received Flow**: `POST /api/wishlist/{id}/mark-not-received` sets `status=not_received` + timestamp — for lost packages and failed deliveries
- **Acquisition Stats**: `GET /api/wishlist/acquisitions/stats?days=N` returns total acquired count, total spent, current market value, breakdown by source and by month (last 12)
- **Wishlist Tabs**: Four tabs on the Wishlist page — Active (wanted) · History (acquired) · Lost (not_received) · Dropped — each with live item count badge; tab selection persisted to URL (`?tab=…`)
- **History Δ-Column**: Acquired items show paid price vs current market price with color-coded Δ (green = cheaper than market, red = paid more)
- **Listing Health**: `GET /api/cardmarket/listings/health?threshold_pct=15` compares each listing against the latest Cardmarket trend price; returns buckets: `underpriced`, `overpriced`, `fair`, `no_match`. Listings with `price=0` or no trend data go to `no_match`
- **ListingHealthPanel**: New UI panel on the Cardmarket page with threshold slider, bucket filter chips, and suggested-price table
- **5 new MCP Tools**: `mark_wishlist_ordered`, `mark_wishlist_acquired`, `mark_wishlist_not_received`, `get_acquisition_stats`, `analyze_my_listings`

### Changed
- `POST /api/wishlist/{id}/acquire` now accepts optional body `{paid_price_eur, source}`; falls back to `expected_price_eur` when item was previously ordered and no paid price is given
- `GET /api/wishlist/` supports new query params `is_ordered: bool` and convenience alias `status=ordered`
- `WishlistItemRow` actions menu extended with Order / Undo Order / Not Received items (context-sensitive)
- Pydantic `WishlistItemCreate` / `WishlistItemUpdate` status Literal extended with `not_received`
- i18n (EN + DE): `action_order`, `action_unorder`, `action_not_received`, `status_ordered`, `status_not_received`, tab labels

### Fixed
- `POST /api/wishlist/{id}/order` now returns 400 for already-acquired or not-received items (was silently succeeding)
- `POST /api/wishlist/{id}/unorder` now returns 400 "Item is not ordered" if `is_ordered=0` (was missing validation)
- Listing Health: listings with `price=0` no longer misclassified as underpriced — moved to `no_match`

### Technical
- `backend/app/services/listing_health.py` — new service (extracted from cardmarket router)
- `idx_wishlist_status_acquired` partial index on `wishlist(status, acquired_at) WHERE status='acquired'` for stats query performance
- `WishlistAcquireDialog.tsx`, `WishlistOrderDialog.tsx` — new frontend components
- `ListingHealthPanel.tsx` — new cardmarket component with threshold slider

## 0.9.0

### Added
- **Light Theme**: "Daylight Orbital Station" variant — cool near-white (`#F4F5FA`) base, frosted-glass surfaces (`rgba(255,255,255,0.72)`), AA-compliant darker oklch accents for all 6 accent families (sothera / nebula / endstone / stellar / drift / ember)
- **Auto/Dark/Light Toggle**: 3-state theme control in the topbar (◎ AUTO · ◑ DARK · ○ LITE). Auto mode reads `prefers-color-scheme` and updates live on macOS appearance change
- **CSS Custom Property Token System** (`--sv-*`): all design tokens are CSS custom properties that switch atomically under `:root[data-sv-theme="light"]` — zero page-level code changes required
- **`SotheraThemeProvider`** + **`useSotheraTheme()`** hook (`src/theme/index.ts`): returns `{mode, setMode, isDark, fluentTheme}`. Theme choice persisted to `localStorage` under key `sothera.theme`
- **`ACCENTS_LIGHT`**: Light-mode accent map (darkened for AA contrast on white surfaces) exposed alongside `ACCENTS` (dark)

### Changed
- **BackdropFX**: Light branch — nebula masked to upper 35% of viewport (no full-bleed), no star dust, softer glow. Dark branch unchanged
- **Sparkline galaxy-foil**: Fill gradient stops use `var(--sv-foil-sN)` + `var(--sv-foil-top-opacity)` — switches automatically between dark (high-chroma) and light (−30% chroma) variants
- **Topbar accent picker**: Swatches reflect the active theme's accent variant (dark vs light)
- **`FluentProvider`**: Now picks `sotheraTheme` (dark) or `sotheraLightTheme` (light, built with `createLightTheme`) at runtime — no static import
- **220ms crossfade**: `transition: background-color 220ms, color 220ms, border-color 220ms` applied globally via `index.css` — no hard cutover flash on theme switch
- **Scrollbar**: Uses `var(--sv-border-strong)` / `var(--sv-fg-faint)` — inverts cleanly on light
- **Bundle size**: 1,010 KB → 1,024 KB (+14 KB raw / ~4 KB gzip) — delta from `createLightTheme` import

### Technical
- No `isDark` ternaries in any page or component — token layer is the single source of truth
- `tsc --noEmit`: 0 errors; `npm run build`: clean
- No new runtime dependencies

## 0.8.0

### Added
- **Sothera Vault Redesign**: Complete frontend redesign with space-opera aesthetic
- **Theme System**: `src/theme/sothera.ts` — oklch accent ramp (6 named accents: sothera/nebula/endstone/stellar/drift/ember), glass surface tokens, dark Fluent UI theme override
- **Shared Primitives**: `src/components/sothera/` — Panel, PageHeader, SectionHeader, DeltaBadge, CornerTicks, Sigil, BackdropFX
- **Accent Picker**: Swappable accent colors persisted to localStorage, accessible from the topbar
- **Galaxy-Foil Sparkline**: Rewritten Sparkline component with gradient fill, grid pattern, and glowing accent dot with concentric rings
- **BackdropFX**: Animated starfield + nebula glow + horizon haze background layer

### Changed
- **Typography**: Space Grotesk (display, 600-700), Inter (body, 400-500), JetBrains Mono (mono/data, 500-600) via Google Fonts CDN
- **All 8 pages rewritten**: Dashboard, Decks, DeckView, Collection, Cardmarket, Duplicates, Wishlist, Settings — from Fluent UI defaults to Sothera glass-panel layout with custom CSS grid tables
- **Topbar**: New branded topbar with sigil, glyph navigation, status line, and accent picker — replaces Fluent UI TabList
- **Background**: #04040A base with layered radial nebula gradients, replacing default Fluent dark/light mode
- **Surfaces**: Glass panels (rgba(20,20,32,0.55), 1px hairline border, ≤2px radius, backdrop blur) replace Fluent UI Card components
- **Bundle size**: Reduced by ~42 KB (1,052 KB → 1,010 KB) by dropping unused Fluent UI Table/Card imports

### Technical
- Styles use Griffel `makeStyles` throughout — no Tailwind, styled-components, or raw style tags
- No new runtime dependencies added (fonts loaded via `<link>` in index.html)
- `api.ts`, routing structure, data shapes, and backend unchanged
- `tsc --noEmit` passes with zero errors

## 0.7.0

### Added
- **Wishlist**: Full wishlist management — Add-Form, priorities (1-5), status tracking, filters, CSV export
- **Deck Header Features**: User-Bracket (editable 1-5), Gameplan field (500 chars), AI-Assessment (Markdown rendered, MCP-only write)
- **MCP Setup UX**: Settings section with proxy download, config snippet (copy-to-clipboard), OS-specific paths
- **Cardmarket Workflow Banner**: 5-step CSV roundtrip guide on Cardmarket page (dismissible via localStorage)
- **AI-Assessment Markdown**: react-markdown + remark-gfm for safe rendering (no rehype-raw)
- **MCP Tool**: `set_deck_ai_assessment` — AI can write deck assessments (max 5000 chars)
- **API Endpoints**: `GET /api/mcp/proxy.mjs`, `GET /api/mcp/setup-instructions`, `PUT /api/decks/{id}/user-fields`
- **Documentation**: MCP Setup Guide, Cardmarket Workflow Guide

### Changed
- Deck detail header shows Archidekt bracket + editable user bracket side-by-side
- Dockerfile copies mcp-proxy.mjs into container for download endpoint
- Schema migration #10: 4 new columns on `decks` table (user_bracket, gameplan, ai_assessment, ai_assessment_updated_at)

## 0.6.0

### Changed
- **Repository structure**: Add-on files moved into `mtg-collection/` subdirectory — required for Home Assistant custom repositories
- Installation is now via the HA Add-on Store: Settings → Add-ons → Add-on Store → ⋮ → Repositories → `https://github.com/HerrFuchs/mtg-collection-ha`

### Migration
If you previously installed the add-on manually via SCP:
1. Back up the DB: `cp /data/mtg.db /backup/mtg.db.$(date +%Y%m%d)`
2. Uninstall the old add-on in HA
3. Delete the local add-on folder: `rm -rf /addons/mtg-collection`
4. Add the repository URL in HA and reinstall the add-on
5. Restore the DB: `cp /backup/mtg.db.YYYYMMDD /data/mtg.db`

## 0.5.1

### Removed
- Cardmarket profile scraping removed entirely (FlareSolverr-based, unreliable due to Cloudflare)
- FlareSolverr integration and configuration (`flaresolverr_url`)
- "Sync from Profile" button in the Cardmarket UI
- Dependency: selectolax

### Changed
- Cardmarket listings now only via CSV import or manual entry
- Price data sync via official Cardmarket JSON feeds is unchanged

## 0.5.0

### Added
- Duplicates tab: shows cards with excess copies, with sell dialog for Cardmarket listings
- Dashboard price alerts: price-spike alerts on the dashboard with tier grouping
- Collection deck filter: dropdown to filter by deck
- EDHREC link in deck detail view for the Commander
- Cardmarket source tracking: distinguishes imported vs. manually created listings
- Clear Listings button on the Settings page
- MCP Server: `get_duplicates`, `add_cardmarket_listing`, `clear_cardmarket_listings` tools

### Changed
- Dashboard no longer shows a sync-status card
- CSV import preserves manual entries and merges them on name match

## 0.4.2

### Added
- Collection server-side pagination (100 per page)
- Price alert tier grouping with collapsible groups

## 0.4.1

### Fixed
- Collection performance: CTE instead of a correlated O(n²) subquery
- Cardmarket price sync: HTTP 403 treated as end of page list

## 0.3.0

### Added
- Archidekt authentication (login with username/password for private decks and collection)
- Collection sync directly via Archidekt Collection API
- Cardmarket CSV import for listings
- New config fields: `archidekt_password`, `archidekt_user_id`, `cardmarket_username`
- Settings page shows authentication status for Archidekt and Cardmarket

### Changed
- Collection is now read directly from Archidekt (no longer built from deck cards)
- Deck sync no longer automatically adds cards to the collection

### Fixed
- API base URL correctly extracted from the ingress path (fixes "Deck not found" on navigation)
- CHANGELOG format made compatible with Home Assistant

## 0.2.0

### Fixed
- Dockerfile: `ARG BUILD_FROM` placed before first `FROM` for correct HA build args
- Dockerfile: replaced `npm ci` with `npm install` (no `package-lock.json` required)
- Icon: replaced `CardMultiple24Regular` with `Stack24Regular` (exists in @fluentui/react-icons)
- Docker: replaced HA base image with `python:3.12-alpine` — fixes s6-overlay PID 1 crash
- `run.sh`: removed bashio dependency, uses plain `sh` with Supervisor API for ingress info
- Frontend: API base URL derived dynamically from ingress path — fixes 404 errors
- Frontend: `BrowserRouter basename` set for HA ingress routing
- Backend: `root_path` from `INGRESS_ENTRY` for correct FastAPI redirects
- MCP server import/mount made fault-tolerant (try/except)

### Added
- `CHANGELOG.md` for Home Assistant add-on updates
- Centralized version constant in `backend/app/version.py`

## 0.1.0

### Added
- Initial release
- Archidekt deck sync with configurable schedule
- Scryfall card search and price lookup
- EDHREC Commander recommendations and combos
- Collection management with SQLite
- Cardmarket CSV import
- MCP server (Streamable HTTP) for AI assistants
- Fluent UI React frontend with Dashboard, Decks, Collection, Cardmarket, Settings
- Home Assistant Ingress integration
