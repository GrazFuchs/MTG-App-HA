"""SQLite database initialization and access."""
import asyncio
from contextlib import asynccontextmanager
import logging
import aiosqlite
from pathlib import Path
from typing import AsyncIterator, Callable, Awaitable
from .config import get_settings

logger = logging.getLogger(__name__)

_pool: asyncio.Queue[aiosqlite.Connection] | None = None
_pool_connections: list[aiosqlite.Connection] = []
_primary: aiosqlite.Connection | None = None
_POOL_SIZE = 6  # extra connections beyond the primary

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

-- Sprint 13: indexes for sibling query (JOIN on cards.name) and listings JOIN (LOWER name)
CREATE INDEX IF NOT EXISTS idx_cards_name_lower ON cards(name COLLATE NOCASE);

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
    """Get the primary shared connection (backwards-compatible)."""
    if _primary is None:
        raise RuntimeError("Database not initialized")
    return _primary


@asynccontextmanager
async def borrow_db() -> AsyncIterator[aiosqlite.Connection]:
    """Borrow a connection from the pool for concurrent work."""
    if _pool is None:
        raise RuntimeError("Database not initialized")
    conn = await _pool.get()
    try:
        yield conn
    finally:
        await _pool.put(conn)


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


async def _migration_6(db: aiosqlite.Connection):
    """Add wishlist table."""
    await db.execute("""
        CREATE TABLE IF NOT EXISTS wishlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            card_name TEXT NOT NULL,
            max_price_eur REAL DEFAULT 0,
            notes TEXT DEFAULT '',
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(card_name)
        )
    """)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_wishlist_name ON wishlist(card_name)")


async def _migration_7(db: aiosqlite.Connection):
    """Add value_snapshots table for collection value tracking over time."""
    await db.execute("""
        CREATE TABLE IF NOT EXISTS value_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL UNIQUE,
            total_cards INTEGER DEFAULT 0,
            unique_cards INTEGER DEFAULT 0,
            value_eur REAL DEFAULT 0,
            value_usd REAL DEFAULT 0
        )
    """)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_date ON value_snapshots(date)")


async def _migration_8(db: aiosqlite.Connection):
    """Align wishlist schema: card_id FK, target_price_eur, removed_at soft-delete."""
    cursor = await db.execute("PRAGMA table_info(wishlist)")
    columns = {row[1] for row in await cursor.fetchall()}

    # Add new columns to existing table
    if "card_id" not in columns:
        await db.execute("ALTER TABLE wishlist ADD COLUMN card_id INTEGER REFERENCES cards(id)")
    if "target_price_eur" not in columns:
        await db.execute("ALTER TABLE wishlist ADD COLUMN target_price_eur REAL DEFAULT 0")
    if "removed_at" not in columns:
        await db.execute("ALTER TABLE wishlist ADD COLUMN removed_at TIMESTAMP")

    # Backfill card_id from card_name (best-effort match)
    await db.execute("""
        UPDATE wishlist SET card_id = (
            SELECT id FROM cards WHERE LOWER(cards.name) = LOWER(wishlist.card_name) LIMIT 1
        ) WHERE card_id IS NULL
    """)

    # Backfill target_price_eur from max_price_eur
    if "max_price_eur" in columns:
        await db.execute(
            "UPDATE wishlist SET target_price_eur = max_price_eur WHERE target_price_eur = 0 AND max_price_eur > 0"
        )

    # Recreate table without legacy columns (card_name, max_price_eur)
    # SQLite DROP COLUMN cannot drop columns with UNIQUE constraints, so we recreate.
    await db.execute("""
        CREATE TABLE IF NOT EXISTS wishlist_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            card_id INTEGER REFERENCES cards(id),
            target_price_eur REAL DEFAULT 0,
            notes TEXT DEFAULT '',
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            removed_at TIMESTAMP
        )
    """)
    await db.execute("""
        INSERT OR IGNORE INTO wishlist_new (id, card_id, target_price_eur, notes, added_at, removed_at)
        SELECT id, card_id, target_price_eur, notes, added_at, removed_at FROM wishlist
    """)
    await db.execute("DROP TABLE wishlist")
    await db.execute("ALTER TABLE wishlist_new RENAME TO wishlist")

    # Partial unique index: only one active entry per card
    await db.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_wishlist_card_active ON wishlist(card_id) WHERE removed_at IS NULL"
    )


async def _migration_9(db: aiosqlite.Connection):
    """Wishlist: add set_code, is_foil, quantity, priority, status, deck_id, tags, acquired_at."""
    cursor = await db.execute("PRAGMA table_info(wishlist)")
    columns = {row[1] for row in await cursor.fetchall()}

    additions = {
        "set_code": "ALTER TABLE wishlist ADD COLUMN set_code TEXT DEFAULT NULL",
        "is_foil": "ALTER TABLE wishlist ADD COLUMN is_foil INTEGER DEFAULT 0",
        "quantity": "ALTER TABLE wishlist ADD COLUMN quantity INTEGER DEFAULT 1",
        "priority": "ALTER TABLE wishlist ADD COLUMN priority INTEGER DEFAULT 3",
        "status": "ALTER TABLE wishlist ADD COLUMN status TEXT DEFAULT 'wanted'",
        "deck_id": "ALTER TABLE wishlist ADD COLUMN deck_id INTEGER REFERENCES decks(id) ON DELETE SET NULL",
        "tags": "ALTER TABLE wishlist ADD COLUMN tags TEXT DEFAULT ''",
        "acquired_at": "ALTER TABLE wishlist ADD COLUMN acquired_at TIMESTAMP DEFAULT NULL",
    }
    for col, stmt in additions.items():
        if col not in columns:
            await db.execute(stmt)

    # Replace UNIQUE index: from (card_id) to (card_id, set_code, is_foil) for active 'wanted' entries
    await db.execute("DROP INDEX IF EXISTS idx_wishlist_card_active")
    await db.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_wishlist_card_set_foil_active
        ON wishlist(card_id, COALESCE(set_code, ''), is_foil)
        WHERE removed_at IS NULL AND status = 'wanted'
    """)

    # Performance indexes
    await db.execute("""
        CREATE INDEX IF NOT EXISTS idx_wishlist_status
        ON wishlist(status) WHERE removed_at IS NULL
    """)
    await db.execute("""
        CREATE INDEX IF NOT EXISTS idx_wishlist_deck
        ON wishlist(deck_id) WHERE deck_id IS NOT NULL AND removed_at IS NULL
    """)


async def _migration_10(db: aiosqlite.Connection):
    """Decks: add user_bracket, gameplan, ai_assessment, ai_assessment_updated_at."""
    cursor = await db.execute("PRAGMA table_info(decks)")
    columns = {row[1] for row in await cursor.fetchall()}

    additions = {
        "user_bracket": "ALTER TABLE decks ADD COLUMN user_bracket INTEGER DEFAULT NULL",
        "gameplan": "ALTER TABLE decks ADD COLUMN gameplan TEXT DEFAULT ''",
        "ai_assessment": "ALTER TABLE decks ADD COLUMN ai_assessment TEXT DEFAULT ''",
        "ai_assessment_updated_at": "ALTER TABLE decks ADD COLUMN ai_assessment_updated_at TIMESTAMP DEFAULT NULL",
    }
    for col, stmt in additions.items():
        if col not in columns:
            await db.execute(stmt)


async def _migration_11(db: aiosqlite.Connection):
    """Wishlist: add acquisition tracking fields (paid_price_eur, expected_price_eur, source,
    is_ordered, ordered_at, not_received_at)."""
    cursor = await db.execute("PRAGMA table_info(wishlist)")
    columns = {row[1] for row in await cursor.fetchall()}

    additions = {
        "paid_price_eur": "ALTER TABLE wishlist ADD COLUMN paid_price_eur REAL DEFAULT NULL",
        "expected_price_eur": "ALTER TABLE wishlist ADD COLUMN expected_price_eur REAL DEFAULT NULL",
        "source": "ALTER TABLE wishlist ADD COLUMN source TEXT DEFAULT NULL",
        "is_ordered": "ALTER TABLE wishlist ADD COLUMN is_ordered INTEGER DEFAULT 0",
        "ordered_at": "ALTER TABLE wishlist ADD COLUMN ordered_at TIMESTAMP DEFAULT NULL",
        "not_received_at": "ALTER TABLE wishlist ADD COLUMN not_received_at TIMESTAMP DEFAULT NULL",
    }
    for col, stmt in additions.items():
        if col not in columns:
            await db.execute(stmt)

    # Performance index for acquisition stats queries
    await db.execute("""
        CREATE INDEX IF NOT EXISTS idx_wishlist_status_acquired
        ON wishlist(status, acquired_at)
        WHERE status = 'acquired'
    """)


async def _migration_12(db: aiosqlite.Connection):
    """Add deck_combos table for Spellbook combo cache."""
    await db.execute("""
        CREATE TABLE IF NOT EXISTS deck_combos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            deck_id INTEGER REFERENCES decks(id) ON DELETE CASCADE,
            combo_id TEXT NOT NULL,
            name TEXT DEFAULT '',
            color_identity TEXT DEFAULT '',
            cards_json TEXT NOT NULL,
            result_json TEXT DEFAULT '',
            prerequisites TEXT DEFAULT '',
            steps TEXT DEFAULT '',
            is_partial INTEGER DEFAULT 0,
            missing_cards_json TEXT DEFAULT '',
            cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(deck_id, combo_id)
        )
    """)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_deck_combos_deck ON deck_combos(deck_id)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_deck_combos_partial ON deck_combos(is_partial)")


async def _migration_13(db: aiosqlite.Connection):
    """Add acquisition_events table for inbox triage workflow."""
    await db.execute("""
        CREATE TABLE IF NOT EXISTS acquisition_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sync_log_id INTEGER REFERENCES sync_log(id) ON DELETE SET NULL,
            collection_id INTEGER REFERENCES collection(id) ON DELETE SET NULL,
            card_id INTEGER NOT NULL REFERENCES cards(id),
            condition TEXT NOT NULL DEFAULT 'NM',
            language TEXT NOT NULL DEFAULT 'en',
            is_foil INTEGER NOT NULL DEFAULT 0,
            qty_delta INTEGER NOT NULL,
            triage_state TEXT NOT NULL DEFAULT 'pending',
            triage_decision_at TIMESTAMP,
            source TEXT,
            linked_listing_id INTEGER REFERENCES cardmarket_listings(id) ON DELETE SET NULL,
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_acq_pending ON acquisition_events(triage_state, created_at DESC)"
    )
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_acq_card ON acquisition_events(card_id)"
    )


async def _migration_14(db: aiosqlite.Connection):
    """Performance indices for common JOIN and search paths."""
    await db.execute("CREATE INDEX IF NOT EXISTS idx_cards_name_nocase ON cards(name COLLATE NOCASE)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_cards_set_code ON cards(set_code)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_deck_cards_card_id ON deck_cards(card_id)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_collection_card_id ON collection(card_id)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_cardmarket_listings_card_name ON cardmarket_listings(card_name)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_cm_listings_name_set_foil ON cardmarket_listings(card_name, set_code, is_foil)")
    await db.execute("ANALYZE")


async def _migration_15(db: aiosqlite.Connection):
    """Add deck_games table for the Deck Performance Tracker."""
    await db.execute("""
        CREATE TABLE IF NOT EXISTS deck_games (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            deck_id INTEGER NOT NULL REFERENCES decks(id) ON DELETE CASCADE,
            played_at TEXT NOT NULL DEFAULT (date('now')),
            result TEXT NOT NULL DEFAULT 'win',
            opponents TEXT DEFAULT '',
            pod_size INTEGER DEFAULT 4,
            on_play INTEGER DEFAULT 0,
            mulligans INTEGER DEFAULT 0,
            missed_land_drops INTEGER DEFAULT 0,
            turns INTEGER DEFAULT 0,
            what_worked TEXT DEFAULT '',
            what_didnt TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_deck_games_deck ON deck_games(deck_id, played_at DESC)"
    )


MIGRATIONS: dict[int, Callable[[aiosqlite.Connection], Awaitable[None]]] = {
    2: _migration_2,
    3: _migration_3,
    4: _migration_4,
    5: _migration_5,
    6: _migration_6,
    7: _migration_7,
    8: _migration_8,
    9: _migration_9,
    10: _migration_10,
    11: _migration_11,
    12: _migration_12,
    13: _migration_13,
    14: _migration_14,
    15: _migration_15,
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


async def _create_connection() -> aiosqlite.Connection:
    """Create a single configured SQLite connection."""
    settings = get_settings()
    conn = await aiosqlite.connect(settings.db_path)
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA journal_mode=WAL")
    await conn.execute("PRAGMA synchronous=NORMAL")
    await conn.execute("PRAGMA cache_size=-20000")   # 20 MB
    await conn.execute("PRAGMA temp_store=MEMORY")
    await conn.execute("PRAGMA foreign_keys=ON")
    return conn


async def init_db():
    global _pool, _pool_connections, _primary
    settings = get_settings()
    Path(settings.data_dir).mkdir(parents=True, exist_ok=True)

    # Create primary connection and run schema + migrations
    _primary = await _create_connection()
    await _primary.executescript(SCHEMA_SQL)
    await _run_migrations(_primary)
    await _primary.commit()

    # Build pool of extra connections for concurrent reads
    _pool = asyncio.Queue(maxsize=_POOL_SIZE)
    _pool_connections = []
    for _ in range(_POOL_SIZE):
        conn = await _create_connection()
        _pool_connections.append(conn)
        await _pool.put(conn)
    logger.info("Database pool initialized: 1 primary + %d pool connections", _POOL_SIZE)


async def close_db():
    global _pool, _pool_connections, _primary
    if _primary:
        await _primary.close()
        _primary = None
    for conn in _pool_connections:
        await conn.close()
    _pool_connections = []
    _pool = None
