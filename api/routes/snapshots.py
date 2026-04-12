from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from config import get_settings


router = APIRouter(tags=["snapshots"])


@router.get("/snapshots/{filename}")
async def get_snapshot(filename: str) -> FileResponse:
    settings = get_settings()
    snapshot_path = settings.snapshots_dir / filename
    if not snapshot_path.exists() or not snapshot_path.is_file():
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return FileResponse(snapshot_path, media_type="image/jpeg", filename=Path(filename).name)
