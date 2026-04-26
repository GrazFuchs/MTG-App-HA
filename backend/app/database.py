"""SQLite database initialization and access."""
import logging
import aiosqlite
from pathlib import Path
from typing import Callable, Awaitable
from .config import get_settings

logger = logging.getLogger(__name__)

_db: aiosqlite.Connection | None = None

COLLECTION_COLUMN_MIGRATIONS = {
    "archidekt_tags": "ALTER TABLE collection ADD COLUMN archidekt_tags TEXT DEFAULT ''",
}

DECK_COLUMN_MIGRATIONS = {
    "folder_name": "ALTER TABLE decks ADD COLUMN folder_name TEXT DEFAULT ''",
    "bracket": "ALTER TABLE decks ADD COLUMN bracket INTEGER DEFAULT 0",
}

CARDMARKET_COLUMN_MIGRATIONS = {
    "article_id": "ALTER TABLE cardmarket_listings ADD COLUMN article_id TEXT DEFAULT ''",
    "expansion_code": "ALTER TABLE cardmarket_listings ADD COLUMN expansion_code TEXT DEFAULT ''",
    "rarity": "ALTER TABLE cardmarket_listings ADD COLUMN rarity TEXT DEFAULT ''",
    "condition_full": "ALTER TABLE cardmarket_listings ADD COLUMN condition_full TEXT DEFAULT ''",
    "reverse_holo": "ALTER TABLE cardmarket_listings ADD COLUMN reverse_holo BOOLEAN DEFAULT FALSE",
    "comments": "ALTER TABLE cardmarket_listings ADD COLUMN comments TEXT DEFAULT ''",
    "product_url": "ALTER TABLE cardmarket_listings ADD COLUMN product_url TEXT DEFAULT ''",
    "source": "ALTER TABLE cardmarket_listings ADD COLUMN source TEXT DEFAULT 'import'",
}

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scryfall_id TEXT UNIQUE NOT NULL,
    oracle_id TEXT,
    name TEXT NOT NULL,
    mana_cost TEXT DEFAULT '',
    cmc REAL DEFAULT 0,
    type_line TEXT DEFAULT '',
    oracle_text TEXT DEFAULT '',
    colors TEXT DEFAULT '[]',
    color_identity TEXT DEFAULT '[]',
    set_code TEXT DEFAULT '',
    set_name TEXT DEFAULT '',
    collector_number TEXT DEFAULT '',
    rarity TEXT DEFAULT '',
    image_uri TEXT DEFAULT '',
    image_art_crop TEXT DEFAULT '',
    power TEXT DEFAULT '',
    toughness TEXT DEFAULT '',
    loyalty TEXT DEFAULT '',
    keywords TEXT DEFAULT '[]',
    legalities TEXT DEFAULT '{}',
    edhrec_rank INTEGER,
    price_usd TEXT DEFAULT '',
    price_eur TEXT DEFAULT '',
    price_usd_foil TEXT DEFAULT '',
    price_eur_foil TEXT DEFAULT '',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_cards_name ON cards(name);
CREATE INDEX IF NOT EXISTS idx_cards_oracle_id ON cards(oracle_id);
CREATE INDEX IF NOT EXISTS idx_cards_set ON cards(set_code);

CREATE TABLE IF NOT EXISTS decks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    archidekt_id INTEGER UNIQUE,
    name TEXT NOT NULL,
    format TEXT DEFAULT '',
    description TEXT DEFAULT '',
    featured_image TEXT DEFAULT '',
    commander_name TEXT DEFAULT '',
    commander_card_id INTEGER REFERENCES cards(id),
    owner_username TEXT DEFAULT '',
    view_count INTEGER DEFAULT 0,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    last_synced TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS deck_cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    deck_id INTEGER NOT NULL REFERENCES decks(id) ON DELETE CASCADE,
    card_id INTEGER NOT NULL REFERENCES cards(id),
    quantity INTEGER DEFAULT 1,
    category TEXT DEFAULT '',
    is_commander BOOLEAN DEFAULT FALSE,
    is_companion BOOLEAN DEFAULT FALSE,
    modifier TEXT DEFAULT 'Normal',
    UNIQUE(deck_id, card_id, modifier)
);

CREATE INDEX IF NOT EXISTS idx_deck_cards_deck ON deck_cards(deck_id);

CREATE TABLE IF NOT EXISTS collection (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id INTEGER NOT NULL REFERENCES cards(id),
    quantity INTEGER DEFAULT 1,
    foil_quantity INTEGER DEFAULT 0,
    condition TEXT DEFAULT 'NM',
    language TEXT DEFAULT 'en',
    archidekt_tags TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(card_id, condition, language)
);

CREATE INDEX IF NOT EXISTS idx_collection_card ON collection(card_id);

CREATE TABLE IF NOT EXISTS cardmarket_listings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_name TEXT NOT NULL,
    set_name TEXT DEFAULT '',
    set_code TEXT DEFAULT '',
    quantity INTEGER DEFAULT 1,
    price REAL DEFAULT 0,
    condition TEXT DEFAULT '',
    language TEXT DEFAULT '',
    is_foil BOOLEAN DEFAULT FALSE,
    card_id INTEGER REFERENCES cards(id),
    imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_cm_listings_name ON cardmarket_listings(card_name);

CREATE TABLE IF NOT EXISTS sync_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'running',
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP,
    items_synced INTEGER DEFAULT 0,
    error TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS cardmarket_products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cm_product_id INTEGER UNIQUE NOT NULL,
    card_name TEXT NOT NULL,
    expansion_name TEXT DEFAULT '',
    card_id INTEGER REFERENCES cards(id),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_cm_products_name ON cardmarket_products(card_name);
CREATE INDEX IF NOT EXISTS idx_cm_products_pid ON cardmarket_products(cm_product_id);

CREATE TABLE IF NOT EXISTS cardmarket_price_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cm_product_id INTEGER NOT NULL,
    date TEXT NOT NULL,
    avg REAL DEFAULT 0,
    low REAL DEFAULT 0,
    trend REAL DEFAULT 0,
    avg1 REAL DEFAULT 0,
    avg7 REAL DEFAULT 0,
    avg30 REAL DEFAULT 0,
    UNIQUE(cm_product_id, date)
);

CREATE INDEX IF NOT EXISTS idx_cm_price_product ON cardmarket_price_history(cm_product_id);

INSERT OR IGNORE INTO schema_version (version) VALUES (1);
"""


async def get_db() -> aiosqlite.Connection:
    global _db
    if _db is None:
        raise RuntimeError("Database not initialized")
    return _db


# --- Migrations ---
# Each migration is keyed by version number and applied in ascending order.
# Migrations must be idempotent (use IF NOT EXISTS / check PRAGMA table_info).

async def _migration_2(db: aiosqlite.Connection):
    """Add collection column migrations (archidekt_tags)."""
    cursor = await db.execute("PRAGMA table_info(collection)")
    columns = {row[1] for row in await cursor.fetchall()}
    for column_name, statement in COLLECTION_COLUMN_MIGRATIONS.items():
        if column_name not in columns:
            await db.execute(statement)


async def _migration_3(db: aiosqlite.Connection):
    """Add deck column migrations (folder_name, bracket)."""
    cursor = await db.execute("PRAGMA table_info(decks)")
    columns = {row[1] for row in await cursor.fetchall()}
    for column_name, statement in DECK_COLUMN_MIGRATIONS.items():
        if column_name not in columns:
            await db.execute(statement)


async def _migration_4(db: aiosqlite.Connection):
    """Add cardmarket column migrations (article_id, rarity, comments, source, etc.)."""
    cursor = await db.execute("PRAGMA table_info(cardmarket_listings)")
    columns = {row[1] for row in await cursor.fetchall()}
    for column_name, statement in CARDMARKET_COLUMN_MIGRATIONS.items():
        if column_name not in columns:
            await db.execute(statement)


async def _migration_5(db: aiosqlite.Connection):
    """Add notification_log table for anti-duplicate alert tracking."""
    await db.execute("""
        CREATE TABLE IF NOT EXISTS notification_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            card_name TEXT NOT NULL,
            alert_date TEXT NOT NULL,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(card_name, alert_date)
        )
    """)


MIGRATIONS: dict[int, Callable[[aiosqlite.Connection], Awaitable[None]]] = {
    2: _migration_2,
    3: _migration_3,
    4: _migration_4,
    5: _migration_5,
}


async def _run_migrations(db: aiosqlite.Connection):
    """Read current schema version and apply pending migrations."""
    cursor = await db.execute("SELECT MAX(version) FROM schema_version")
    row = await cursor.fetchone()
    current_version = row[0] if row and row[0] else 1

    for target_version in sorted(MIGRATIONS.keys()):
        if target_version > current_version:
            logger.info("Applying migration %d...", target_version)
            await MIGRATIONS[target_version](db)
            await db.execute(
                "INSERT OR REPLACE INTO schema_version (version) VALUES (?)",
                (target_version,),
            )
            await db.commit()
            logger.info("Migration %d applied", target_version)

    final_version = max(MIGRATIONS.keys()) if MIGRATIONS else 1
    if current_version < final_version:
        logger.info("Schema migrated from version %d to %d", current_version, final_version)
    else:
        logger.debug("Schema at version %d, no migrations needed", current_version)


async def init_db():
    global _db
    settings = get_settings()
    Path(settings.data_dir).mkdir(parents=True, exist_ok=True)
    _db = await aiosqlite.connect(settings.db_path)
    _db.row_factory = aiosqlite.Row
    await _db.execute("PRAGMA journal_mode=WAL")
    await _db.execute("PRAGMA foreign_keys=ON")
    await _db.executescript(SCHEMA_SQL)
    await _run_migrations(_db)
    await _db.commit()


async def close_db():
    global _db
    if _db:
        await _db.close()
        _db = None
