"""Backup and restore routes."""
import io
import logging
import shutil
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, UploadFile, File
from fastapi.responses import FileResponse

from ..config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/backup")
async def create_backup():
    """Download a backup of the SQLite database."""
    settings = get_settings()
    db_path = Path(settings.db_path)
    if not db_path.exists():
        return {"error": "Database file not found"}

    # Copy to temp backup file (avoid locking issues with WAL)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"mtg_backup_{timestamp}.db"
    backup_path = db_path.parent / backup_name
    shutil.copy2(db_path, backup_path)

    # Also copy WAL and SHM if they exist
    for suffix in ("-wal", "-shm"):
        wal = Path(str(db_path) + suffix)
        if wal.exists():
            shutil.copy2(wal, Path(str(backup_path) + suffix))

    return FileResponse(
        path=str(backup_path),
        filename=backup_name,
        media_type="application/x-sqlite3",
        background=None,
    )


@router.post("/restore")
async def restore_backup(file: UploadFile = File(...)):
    """Restore the database from an uploaded backup file."""
    settings = get_settings()
    db_path = Path(settings.db_path)

    content = await file.read()
    if len(content) < 100:
        return {"error": "File too small to be a valid database"}

    # Check SQLite magic header
    if content[:16] != b"SQLite format 3\x00":
        return {"error": "Not a valid SQLite database file"}

    # Backup current before overwriting
    if db_path.exists():
        pre_restore = db_path.parent / "mtg_pre_restore.db"
        shutil.copy2(db_path, pre_restore)
        logger.info("Pre-restore backup saved to %s", pre_restore)

    # Write the uploaded file
    db_path.write_bytes(content)

    # Remove WAL/SHM to force re-read
    for suffix in ("-wal", "-shm"):
        wal = Path(str(db_path) + suffix)
        if wal.exists():
            wal.unlink()

    logger.info("Database restored from upload (%d bytes)", len(content))
    return {"status": "restored", "size_bytes": len(content), "note": "Restart the add-on to apply changes"}
