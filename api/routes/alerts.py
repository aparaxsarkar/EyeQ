from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Query

from config import get_settings
from db import fetch_alerts


router = APIRouter(tags=["alerts"])


@router.get("/alerts")
async def get_alerts(limit: int = Query(default=50, ge=1, le=200)) -> list[dict]:
    settings = get_settings()
    alerts = await fetch_alerts(settings.db_path, limit=limit)
    for alert in alerts:
        clip_path = alert.get("clip_path")
        alert["clip_url"] = f"/clips/{Path(clip_path).name}" if clip_path else None
    return alerts
