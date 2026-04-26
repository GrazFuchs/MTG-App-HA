"""Backup and restore routes."""
import asyncio
import logging
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse

from ..config import get_settings
from ..database import get_db

logger = logging.getLogger(__name__)
router = APIRouter()

REQUIRED_TABLES = {"cards", "decks", "deck_cards", "collection", "schema_version"}


@router.get("/backup")
async def create_backup():
    """Download a backup of the SQLite database via VACUUM INTO (atomic, safe during writes)."""
    settings = get_settings()
    db_path = Path(settings.db_path)
    if not db_path.exists():
        raise HTTPException(status_code=404, detail="Database file not found")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"mtg_backup_{timestamp}.db"
    backup_path = db_path.parent / backup_name

    db = await get_db()
    await db.execute(f"VACUUM INTO '{backup_path}'")

    return FileResponse(
        path=str(backup_path),
        filename=backup_name,
        media_type="application/x-sqlite3",
        background=None,
    )


def _validate_uploaded_db(file_path: Path) -> None:
    """Validate an uploaded SQLite file (runs in thread, sync sqlite3)."""
    conn = sqlite3.connect(str(file_path))
    try:
        # PRAGMA integrity_check
        result = conn.execute("PRAGMA integrity_check").fetchone()
        if result is None or result[0] != "ok":
            detail = result[0] if result else "unknown error"
            raise HTTPException(
                status_code=400,
                detail=f"Integrity check failed: {detail}",
            )

        # Schema plausibility: required tables must exist
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        existing = {r[0] for r in rows}
        missing = REQUIRED_TABLES - existing
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"Schema mismatch: missing tables: {sorted(missing)}",
            )
    finally:
        conn.close()


@router.post("/restore")
async def restore_backup(file: UploadFile = File(...)):
    """Restore the database from an uploaded backup file."""
    settings = get_settings()
    db_path = Path(settings.db_path)

    content = await file.read()
    if len(content) < 100:
        raise HTTPException(status_code=400, detail="File too small to be a valid database")

    # Check SQLite magic header
    if content[:16] != b"SQLite format 3\x00":
        raise HTTPException(status_code=400, detail="Not a valid SQLite database file")

    # Write to temp file for validation
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        # Validate integrity and schema in a thread
        await asyncio.to_thread(_validate_uploaded_db, tmp_path)

        # Pre-restore backup of current DB
        if db_path.exists():
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            pre_restore = db_path.parent / f"mtg.db.pre-restore-{timestamp}"
            db = await get_db()
            await db.execute(f"VACUUM INTO '{pre_restore}'")
            logger.info("Pre-restore backup saved to %s", pre_restore)

        # Atomic replace: rename validated file onto db_path
        tmp_path.replace(db_path)

        # Remove WAL/SHM to force fresh open
        for suffix in ("-wal", "-shm"):
            wal = Path(str(db_path) + suffix)
            if wal.exists():
                wal.unlink()

        logger.info("Database restored from upload (%d bytes)", len(content))
        return {
            "status": "restored",
            "size_bytes": len(content),
            "note": "Restart the add-on to apply changes",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Restore failed")
        raise HTTPException(status_code=500, detail=f"Restore failed: {e}")
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
