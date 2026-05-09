"""Archidekt → Local sync service."""
import asyncio
import json
import logging
from datetime import datetime, timezone

from ..database import get_db
from ..config import get_settings
from ..clients.archidekt import archidekt, parse_archidekt_deck, parse_archidekt_card

logger = logging.getLogger(__name__)

_sync_lock = asyncio.Lock()


def is_sync_running() -> bool:
    """Check if a sync is currently in progress."""
    return _sync_lock.locked()


async def upsert_card(db, card_data: dict) -> int:
    """Insert or update a card, return its DB id."""
    colors = card_data.get("colors", [])
    color_identity = card_data.get("color_identity", [])
    keywords = card_data.get("keywords", [])

    if isinstance(colors, list):
        colors = json.dumps(colors)
    if isinstance(color_identity, list):
        color_identity = json.dumps(color_identity)
    if isinstance(keywords, list):
        keywords = json.dumps(keywords)

    legalities = card_data.get("legalities", "{}")

    params = (
        card_data["scryfall_id"],
        card_data.get("oracle_id", ""),
        card_data.get("name", ""),
        card_data.get("mana_cost", ""),
        card_data.get("cmc", 0),
        card_data.get("type_line", ""),
        card_data.get("oracle_text", ""),
        colors, color_identity,
        card_data.get("set_code", ""),
        card_data.get("set_name", ""),
        card_data.get("collector_number", ""),
        card_data.get("rarity", ""),
        card_data.get("image_uri", ""),
        card_data.get("image_art_crop", ""),
        card_data.get("power", ""),
        card_data.get("toughness", ""),
        card_data.get("loyalty", ""),
        keywords,
        legalities,
        card_data.get("edhrec_rank"),
        card_data.get("price_usd", ""),
        card_data.get("price_eur", ""),
        card_data.get("price_usd_foil", ""),
        card_data.get("price_eur_foil", ""),
    )

    cursor = await db.execute(
        """INSERT INTO cards (
            scryfall_id, oracle_id, name, mana_cost, cmc, type_line, oracle_text,
            colors, color_identity, set_code, set_name, collector_number,
            rarity, image_uri, image_art_crop, power, toughness, loyalty,
            keywords, legalities, edhrec_rank, price_usd, price_eur,
            price_usd_foil, price_eur_foil
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(scryfall_id) DO UPDATE SET
            oracle_id=excluded.oracle_id, name=excluded.name,
            mana_cost=excluded.mana_cost, cmc=excluded.cmc,
            type_line=excluded.type_line, oracle_text=excluded.oracle_text,
            colors=excluded.colors, color_identity=excluded.color_identity,
            set_code=excluded.set_code, set_name=excluded.set_name,
            collector_number=excluded.collector_number, rarity=excluded.rarity,
            image_uri=excluded.image_uri, image_art_crop=excluded.image_art_crop,
            power=excluded.power, toughness=excluded.toughness, loyalty=excluded.loyalty,
            keywords=excluded.keywords, legalities=excluded.legalities,
            edhrec_rank=excluded.edhrec_rank, price_usd=excluded.price_usd,
            price_eur=excluded.price_eur, price_usd_foil=excluded.price_usd_foil,
            price_eur_foil=excluded.price_eur_foil, updated_at=CURRENT_TIMESTAMP
        RETURNING id""",
        params,
    )
    row = await cursor.fetchone()
    return row[0]


async def sync_deck(deck_id: int, folder_cache: dict[int, str] | None = None) -> dict:
    """Sync a single deck from Archidekt."""
    db = await get_db()
    raw = await archidekt.get_deck(deck_id)
    deck_data = parse_archidekt_deck(raw)

    # Resolve folder name
    folder_name = ""
    parent_folder_id = raw.get("parentFolder")
    if parent_folder_id:
        if folder_cache is not None and parent_folder_id in folder_cache:
            folder_name = folder_cache[parent_folder_id]
        else:
            try:
                folder_data = await archidekt.get_folder(parent_folder_id)
                folder_name = folder_data.get("name", "")
                if folder_cache is not None:
                    folder_cache[parent_folder_id] = folder_name
            except Exception as e:
                logger.warning("Could not resolve folder %d: %s", parent_folder_id, e)

    # Upsert deck
    await db.execute(
        """INSERT INTO decks (archidekt_id, name, format, description, featured_image,
            commander_name, owner_username, view_count, created_at, updated_at, folder_name, bracket, last_synced)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)
        ON CONFLICT(archidekt_id) DO UPDATE SET
            name=excluded.name, format=excluded.format, description=excluded.description,
            featured_image=excluded.featured_image, commander_name=excluded.commander_name,
            owner_username=excluded.owner_username, view_count=excluded.view_count,
            updated_at=excluded.updated_at, folder_name=excluded.folder_name,
            bracket=excluded.bracket,
            last_synced=CURRENT_TIMESTAMP""",
        (
            deck_data["archidekt_id"],
            deck_data["name"],
            deck_data["format"],
            deck_data["description"],
            deck_data["featured_image"],
            deck_data["commander_name"],
            deck_data["owner_username"],
            deck_data["view_count"],
            deck_data["created_at"],
            deck_data["updated_at"],
            folder_name,
            deck_data.get("bracket", 0),
        ),
    )

    # Get local deck id
    cursor = await db.execute(
        "SELECT id FROM decks WHERE archidekt_id=?", (deck_data["archidekt_id"],)
    )
    deck_row = await cursor.fetchone()
    local_deck_id = deck_row[0]

    # Clear old deck cards
    await db.execute("DELETE FROM deck_cards WHERE deck_id=?", (local_deck_id,))

    # Insert cards
    cards_synced = 0
    for card_entry in raw.get("cards", []):
        try:
            parsed = parse_archidekt_card(card_entry)
            card_id = await upsert_card(db, parsed["card"])

            await db.execute(
                """INSERT OR REPLACE INTO deck_cards
                (deck_id, card_id, quantity, category, is_commander, is_companion, modifier)
                VALUES (?,?,?,?,?,?,?)""",
                (
                    local_deck_id,
                    card_id,
                    parsed["quantity"],
                    parsed["category"],
                    parsed["is_commander"],
                    parsed["is_companion"],
                    parsed["modifier"],
                ),
            )

            cards_synced += 1
        except Exception as e:
            logger.warning("Failed to sync card in deck %d: %s", deck_id, e)

    # Update commander card ref
    if deck_data["commander_name"]:
        cursor = await db.execute(
            """SELECT c.id FROM cards c
            JOIN deck_cards dc ON dc.card_id = c.id
            WHERE dc.deck_id=? AND dc.is_commander=1 LIMIT 1""",
            (local_deck_id,),
        )
        cmd_row = await cursor.fetchone()
        if cmd_row:
            await db.execute(
                "UPDATE decks SET commander_card_id=? WHERE id=?",
                (cmd_row[0], local_deck_id),
            )

    await db.commit()
    return {"deck_id": local_deck_id, "cards_synced": cards_synced, "name": deck_data["name"]}


async def sync_collection(user_id: int) -> int:
    """Sync the user's Archidekt collection to the local database.

    Saves incrementally per page so partial progress is preserved on failure.
    """
    db = await get_db()
    synced = 0
    page = 1
    sync_complete = False
    aggregated_entries: dict[tuple[int, str, str], dict[str, str | int | None]] = {}

    # Fix legacy type mismatches: SQLite UNIQUE treats int 1 and text "1" as different.
    # Delete rows where condition/language are stored as non-text (they'll be re-synced).
    await db.execute(
        "DELETE FROM collection WHERE typeof(condition) != 'text' OR typeof(language) != 'text'"
    )
    await db.commit()

    def merge_tags(existing_tags: str, new_tags: str) -> str:
        ordered_tags: list[str] = []
        for raw_tags in (existing_tags, new_tags):
            for tag in raw_tags.split(","):
                cleaned = tag.strip()
                if cleaned and cleaned not in ordered_tags:
                    ordered_tags.append(cleaned)
        return ", ".join(ordered_tags)

    while True:
        try:
            data = await archidekt.get_collection(user_id, page=page)
        except Exception as e:
            logger.warning("Collection page %d failed: %s — saving %d items synced so far", page, e, synced)
            break

        results = data.get("results", data.get("cards", []))
        if not results:
            break

        for entry in results:
            try:
                parsed = parse_archidekt_card(entry)
                card_id = await upsert_card(db, parsed["card"])

                quantity = parsed["quantity"]
                is_foil = parsed.get("modifier", "Normal") == "Foil"
                archidekt_tags = parsed.get("category", "")
                condition = str(entry.get("condition") or entry.get("quality") or "NM")
                language = str(entry.get("language") or entry.get("languageOfCard") or "en")
                added_at = entry.get("addedAt") or entry.get("createdAt") or entry.get("updatedAt")
                entry_key = (card_id, condition, language)
                aggregated = aggregated_entries.setdefault(
                    entry_key,
                    {
                        "quantity": 0,
                        "foil_quantity": 0,
                        "archidekt_tags": "",
                        "added_at": None,
                    },
                )

                if is_foil:
                    aggregated["foil_quantity"] = int(aggregated["foil_quantity"]) + quantity
                else:
                    aggregated["quantity"] = int(aggregated["quantity"]) + quantity

                aggregated["archidekt_tags"] = merge_tags(
                    str(aggregated["archidekt_tags"]),
                    archidekt_tags,
                )
                if added_at and (
                    aggregated["added_at"] is None or str(added_at) < str(aggregated["added_at"])
                ):
                    aggregated["added_at"] = added_at

                await db.execute(
                    """INSERT INTO collection (
                    card_id, quantity, foil_quantity, condition, language, archidekt_tags, added_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, COALESCE(?, CURRENT_TIMESTAMP))
                    ON CONFLICT(card_id, condition, language) DO UPDATE SET
                        quantity = excluded.quantity,
                        foil_quantity = excluded.foil_quantity,
                        archidekt_tags = excluded.archidekt_tags,
                        added_at = COALESCE(excluded.added_at, collection.added_at)""",
                    (
                        card_id,
                        aggregated["quantity"],
                        aggregated["foil_quantity"],
                        condition,
                        language,
                        aggregated["archidekt_tags"],
                        aggregated["added_at"],
                    ),
                )
                synced += 1
            except Exception as e:
                logger.warning("Failed to sync collection card: %s", e)

        # Commit after each page so progress is saved
        await db.commit()
        logger.info("Collection page %d saved (%d cards this page, %d total)", page, len(results), synced)

        if not data.get("next"):
            sync_complete = True
            break
        page += 1

    logger.info("Synced %d collection entries from Archidekt (complete=%s), %d unique keys in aggregated_entries",
                synced, sync_complete, len(aggregated_entries))
    if aggregated_entries:
        sample_key = next(iter(aggregated_entries))
        logger.info("Sample aggregated key: %s (types: %s)", repr(sample_key),
                     tuple(type(x).__name__ for x in sample_key))

    # Remove stale collection entries that no longer exist in Archidekt
    # ONLY if the sync completed all pages — partial syncs must not delete data
    if sync_complete and aggregated_entries:
        seen_keys = set(aggregated_entries.keys())
        cursor = await db.execute("SELECT id, card_id, condition, language FROM collection")
        all_rows = await cursor.fetchall()
        logger.info("Stale check: %d seen_keys, %d DB rows", len(seen_keys), len(all_rows))
        stale_ids = [
            row["id"] for row in all_rows
            if (row["card_id"], str(row["condition"]), str(row["language"])) not in seen_keys
        ]
        if stale_ids:
            logger.info("Removing %d stale entries (first 5 DB keys not in seen: %s)",
                        len(stale_ids),
                        [(r["card_id"], repr(r["condition"]), repr(r["language"]))
                         for r in all_rows
                         if (r["card_id"], str(r["condition"]), str(r["language"])) not in seen_keys][:5])
            placeholders = ",".join(["?"] * len(stale_ids))
            await db.execute(f"DELETE FROM collection WHERE id IN ({placeholders})", stale_ids)
            await db.commit()
            logger.info("Removed %d stale collection entries no longer in Archidekt", len(stale_ids))
        else:
            logger.info("No stale collection entries found")

    return synced


async def run_full_sync() -> dict:
    """Run a full sync for all configured decks and collection.

    Returns immediately if a sync is already running.
    Uses incremental deck sync: only re-fetches decks that changed since last sync.
    """
    if _sync_lock.locked():
        logger.info("Sync already in progress, skipping")
        return {"status": "already_running", "message": "A sync is already in progress"}

    async with _sync_lock:
        return await _do_full_sync()


async def run_full_resync() -> dict:
    """Wipe all synced data and re-sync everything from scratch.

    Returns immediately if a sync is already running.
    """
    if _sync_lock.locked():
        logger.info("Sync already in progress, skipping resync")
        return {"status": "already_running", "message": "A sync is already in progress"}

    async with _sync_lock:
        db = await get_db()
        logger.info("Full resync: wiping all synced data...")
        await db.execute("DELETE FROM deck_cards")
        await db.execute("DELETE FROM collection")
        await db.execute("DELETE FROM decks")
        await db.commit()
        logger.info("Full resync: all synced data cleared, starting fresh sync")
        return await _do_full_sync()


async def _do_full_sync() -> dict:
    """Internal sync implementation (must be called under _sync_lock)."""
    db = await get_db()
    settings = get_settings()

    # Log sync start
    cursor = await db.execute(
        "INSERT INTO sync_log (source, status) VALUES ('archidekt', 'running')"
    )
    log_id = cursor.lastrowid
    await db.commit()

    total_synced = 0
    errors = []

    try:
        # Authenticate if credentials are provided
        if settings.archidekt_username and settings.archidekt_password:
            logged_in = await archidekt.login(settings.archidekt_username, settings.archidekt_password)
            if not logged_in:
                errors.append("Archidekt login failed — continuing with public access only")
                logger.warning("Archidekt login failed for %s", settings.archidekt_username)

        # Sync collection if authenticated and user_id is set
        if archidekt.is_authenticated and settings.archidekt_user_id:
            try:
                collection_count = await sync_collection(settings.archidekt_user_id)
                total_synced += collection_count
                logger.info("Synced %d collection entries", collection_count)
            except PermissionError:
                errors.append("Collection sync requires authentication — check credentials")
            except Exception as e:
                errors.append(f"Collection sync failed: {e}")
                logger.error("Collection sync failed: %s", e)

        # Discover and sync decks
        deck_ids = list(settings.archidekt_deck_ids)

        # Auto-discover decks by username if no specific IDs are configured
        if not deck_ids and settings.archidekt_username:
            logger.info("Discovering all decks for user: %s", settings.archidekt_username)
            deck_ids = await archidekt.get_user_deck_ids(settings.archidekt_username)
            logger.info("Discovered %d decks for user %s", len(deck_ids), settings.archidekt_username)
        elif settings.archidekt_username and deck_ids:
            # If both are set, also discover and merge (user decks + explicit IDs)
            logger.info("Discovering decks for user %s and merging with configured IDs", settings.archidekt_username)
            discovered = await archidekt.get_user_deck_ids(settings.archidekt_username)
            # Merge: configured IDs first, then discovered ones
            all_ids = list(deck_ids)
            for did in discovered:
                if did not in all_ids:
                    all_ids.append(did)
            deck_ids = all_ids
            logger.info("Total decks to sync: %d (%d configured + %d discovered)",
                        len(deck_ids), len(settings.archidekt_deck_ids), len(discovered))

        if not deck_ids:
            raise ValueError(
                "No deck IDs configured and auto-discovery failed. "
                "Please add deck IDs in the add-on configuration."
            )

        skipped_decks = 0
        folder_cache: dict[int, str] = {}
        for i, did in enumerate(deck_ids):
            try:
                if i > 0:
                    await asyncio.sleep(1.5)  # Rate limit between deck syncs

                # Incremental: check if deck has changed since last sync
                cursor = await db.execute(
                    "SELECT updated_at FROM decks WHERE archidekt_id=?", (did,)
                )
                local = await cursor.fetchone()
                if local and local["updated_at"]:
                    try:
                        small = await archidekt.get_deck_small(did)
                        remote_updated = small.get("updatedAt", "")
                        if remote_updated:
                            try:
                                remote_dt = datetime.fromisoformat(str(remote_updated))
                                local_dt = datetime.fromisoformat(str(local["updated_at"]))
                                # Normalize: make both aware (UTC) or both naive
                                if remote_dt.tzinfo is not None and local_dt.tzinfo is None:
                                    local_dt = local_dt.replace(tzinfo=timezone.utc)
                                elif remote_dt.tzinfo is None and local_dt.tzinfo is not None:
                                    remote_dt = remote_dt.replace(tzinfo=timezone.utc)
                                if remote_dt <= local_dt:
                                    logger.info("Deck %d unchanged since last sync, skipping", did)
                                    skipped_decks += 1
                                    continue
                            except (ValueError, TypeError):
                                logger.debug("Could not parse dates for deck %d, will re-sync", did)
                    except Exception as e:
                        logger.debug("Could not check deck %d for changes, will do full sync: %s", did, e)

                result = await sync_deck(did, folder_cache=folder_cache)
                total_synced += result["cards_synced"]
                logger.info("Synced deck '%s' (%d cards)", result["name"], result["cards_synced"])

                # Best-effort combo sync after successful deck sync
                try:
                    from .combo_sync import sync_combos_for_deck
                    await asyncio.sleep(1)  # Rate limit for Spellbook API
                    combo_count = await sync_combos_for_deck(result["deck_id"])
                    if combo_count:
                        logger.info("Synced %d combos for deck '%s'", combo_count, result["name"])
                except Exception as combo_err:
                    logger.warning("Combo sync failed for deck '%s': %s", result["name"], combo_err)

            except Exception as e:
                error_msg = f"Deck {did}: {e}"
                errors.append(error_msg)
                logger.error("Failed to sync deck %d: %s", did, e)

        status = "completed" if not errors else "partial"
        await db.execute(
            """UPDATE sync_log SET status=?, finished_at=CURRENT_TIMESTAMP,
            items_synced=?, error=? WHERE id=?""",
            (status, total_synced, "; ".join(errors), log_id),
        )
        await db.commit()

        return {
            "status": status,
            "decks_synced": len(deck_ids) - len(errors) - skipped_decks,
            "decks_skipped": skipped_decks,
            "cards_synced": total_synced,
            "errors": errors,
        }

    except Exception as e:
        await db.execute(
            """UPDATE sync_log SET status='failed', finished_at=CURRENT_TIMESTAMP,
            error=? WHERE id=?""",
            (str(e), log_id),
        )
        await db.commit()
        raise
