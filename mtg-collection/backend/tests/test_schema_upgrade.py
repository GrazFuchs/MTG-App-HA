"""Startup must survive a database created before a column existed.

The bug this covers: 0.33.0 added `cards.cardmarket_id` and, in the same
change, an index on it inside SCHEMA_SQL. That script runs before the
migrations, and `CREATE TABLE IF NOT EXISTS` leaves an already existing `cards`
table untouched — so on every database created before 0.33.0 the index named a
column that was not there yet. `init_db()` died with
`sqlite3.OperationalError: no such column: cardmarket_id` before
`_migration_19` could add it. The add-on crash-looped, and its ingress panel
answered 502 behind Home Assistant.

Every other test starts from a fresh database, where `CREATE TABLE` does carry
the new column. That is exactly why the suite stayed green while every real
upgrade failed, and why this file builds an *old* database on purpose.
"""
import re
import sqlite3

import pytest

from app import config, database


def _write_legacy_database(path) -> None:
    """Write a database as 0.32.x left it: schema at version 18, no
    `cards.cardmarket_id`.

    The legacy schema is derived from the current one rather than pasted in, so
    it keeps up with unrelated schema changes on its own. Only the column under
    test is removed.
    """
    schema = database.SCHEMA_SQL.replace("    cardmarket_id INTEGER,\n", "", 1)

    conn = sqlite3.connect(path)
    try:
        conn.executescript(schema)
        columns = {row[1] for row in conn.execute("PRAGMA table_info(cards)")}
        assert "cardmarket_id" not in columns, (
            "legacy fixture still declares cards.cardmarket_id — the column "
            "declaration in SCHEMA_SQL was reformatted and no longer matches"
        )
        # 18 is the last migration that existed before cardmarket_id.
        conn.execute("INSERT OR REPLACE INTO schema_version (version) VALUES (18)")
        conn.commit()
    finally:
        conn.close()


@pytest.mark.anyio
async def test_startup_adds_cardmarket_id_to_an_existing_database(tmp_path, monkeypatch):
    """A 0.32.x database must come up, not raise OperationalError.

    This is the whole bug: it is the *upgrade* path that broke, and it broke at
    import of the schema, not in the migration that was written for it.
    """
    await database.close_db()  # release the fixture's fresh database

    data_dir = tmp_path / "legacy"
    data_dir.mkdir()
    _write_legacy_database(data_dir / "mtg.db")

    monkeypatch.setenv("DATA_DIR", str(data_dir))
    monkeypatch.setenv("OPTIONS_PATH", str(data_dir / "options.json"))
    config.get_settings.cache_clear()

    await database.init_db()  # used to raise: no such column: cardmarket_id

    db = await database.get_db()
    cursor = await db.execute("PRAGMA table_info(cards)")
    columns = {row[1] for row in await cursor.fetchall()}
    assert "cardmarket_id" in columns, "migration 19 did not add the column"

    cursor = await db.execute("PRAGMA index_list(cards)")
    indexes = {row[1] for row in await cursor.fetchall()}
    assert "idx_cards_cardmarket_id" in indexes, (
        "the index is gone from SCHEMA_SQL, so migration 19 has to create it"
    )


def _write_pre_enrichment_database(path) -> None:
    """Write a database as 0.35.0 left it: schema at version 20, none of the
    Scryfall-only columns, and a type line in Archidekt's comma form.
    """
    schema = re.sub(
        r"^\s*(game_changer|reserved|scryfall_enriched_at) .*\n",
        "",
        database.SCHEMA_SQL,
        flags=re.MULTILINE,
    )

    conn = sqlite3.connect(path)
    try:
        conn.executescript(schema)
        columns = {row[1] for row in conn.execute("PRAGMA table_info(cards)")}
        assert not columns & {"game_changer", "reserved", "scryfall_enriched_at"}, (
            "legacy fixture still declares the enrichment columns — the "
            "declarations in SCHEMA_SQL were reformatted and no longer match"
        )
        conn.execute(
            "INSERT INTO cards (scryfall_id, name, type_line) VALUES (?, ?, ?)",
            ("sf-legacy", "Ancient Copper Dragon", "Legendary, Creature — Dragon"),
        )
        # 20 is the last migration that existed before the enrichment columns.
        conn.execute("INSERT OR REPLACE INTO schema_version (version) VALUES (20)")
        conn.commit()
    finally:
        conn.close()


@pytest.mark.anyio
async def test_startup_adds_the_enrichment_columns_and_fixes_the_type_lines(
    tmp_path, monkeypatch
):
    """Migration 21 on a database that predates it.

    The columns are the easy half. The type line is the half worth a test: it
    rewrites existing rows, so it has to be right on data it did not create.
    """
    await database.close_db()

    data_dir = tmp_path / "pre21"
    data_dir.mkdir()
    _write_pre_enrichment_database(data_dir / "mtg.db")

    monkeypatch.setenv("DATA_DIR", str(data_dir))
    monkeypatch.setenv("OPTIONS_PATH", str(data_dir / "options.json"))
    config.get_settings.cache_clear()

    await database.init_db()

    db = await database.get_db()
    cursor = await db.execute("PRAGMA table_info(cards)")
    columns = {row[1] for row in await cursor.fetchall()}
    assert {"game_changer", "reserved", "scryfall_enriched_at"} <= columns

    cursor = await db.execute(
        "SELECT type_line, game_changer, scryfall_enriched_at FROM cards"
    )
    row = await cursor.fetchone()
    assert row[0] == "Legendary Creature — Dragon"
    # Nothing has asked Scryfall yet, and the migration must not pretend it has.
    assert row[1] is None and row[2] is None


@pytest.mark.anyio
async def test_schema_declares_no_index_on_a_column_it_may_not_have(tmp_path):
    """Guard the fix itself.

    Re-adding the index to SCHEMA_SQL would reintroduce the crash for every
    existing installation while every fresh-database test stayed green — so the
    absence is asserted here rather than left to review.
    """
    assert "idx_cards_cardmarket_id" not in database.SCHEMA_SQL, (
        "SCHEMA_SQL runs before the migrations; an index on cards(cardmarket_id) "
        "there breaks startup on any database predating 0.33.0. Migration 19 "
        "creates this index."
    )
