from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile
import asyncio

from config import get_settings
from core.recording_analyzer import RecordingAnalyzer


router = APIRouter(tags=["recordings"])
ANALYSIS_TIMEOUT_SECONDS = 90


@router.post("/recordings/analyze")
async def analyze_recording(file: UploadFile = File(...)) -> dict:
    settings = get_settings()
    suffix = Path(file.filename or "upload.mp4").suffix or ".mp4"
    upload_path = settings.uploads_dir / f"{uuid4().hex}{suffix}"
    try:
        with upload_path.open("wb") as output:
            while chunk := await file.read(1024 * 1024):
                output.write(chunk)
        analyzer = RecordingAnalyzer()
        result = await asyncio.wait_for(
            analyzer.analyze(upload_path),
            timeout=ANALYSIS_TIMEOUT_SECONDS,
        )
    except TimeoutError as exc:
        raise HTTPException(
            status_code=408,
            detail=(
                f"Recording analysis exceeded {ANALYSIS_TIMEOUT_SECONDS}s. "
                "Try a shorter clip or rerun after the current analysis load clears."
            ),
        ) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        await file.close()
        if upload_path.exists():
            upload_path.unlink()

    result["filename"] = file.filename or result["filename"]
    for finding in result["findings"]:
        clip_path = finding.get("clip_path")
        finding["clip_url"] = f"/clips/{Path(clip_path).name}" if clip_path else None
    return result
