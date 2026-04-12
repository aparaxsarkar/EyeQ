from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from config import get_settings
from core.clip_saver import ClipSaver


router = APIRouter(tags=["clips"])


@router.get("/clips/{filename}")
async def get_clip(filename: str) -> FileResponse:
    settings = get_settings()
    safe_name = Path(filename).name
    clip_path = settings.clips_dir / safe_name
    if not clip_path.exists():
        raise HTTPException(status_code=404, detail="Clip not found")
    playable_path = ClipSaver.ensure_playable_clip(clip_path)
    return FileResponse(path=playable_path, media_type="video/mp4", filename=playable_path.name)
