from __future__ import annotations

from pydantic import BaseModel, Field, model_validator
from fastapi import APIRouter, HTTPException, Request
import asyncio

from fastapi.responses import Response, StreamingResponse

from core.pipeline import PipelineManager


router = APIRouter(tags=["stream"])


class StreamStartRequest(BaseModel):
    camera_index: int | None = Field(default=0)
    rtsp_url: str | None = Field(default=None)

    @model_validator(mode="after")
    def validate_source(self) -> "StreamStartRequest":
        if self.rtsp_url:
            return self
        if self.camera_index is None:
            raise ValueError("camera_index is required when rtsp_url is not provided")
        return self


def _manager(request: Request) -> PipelineManager:
    return request.app.state.pipeline_manager


@router.post("/stream/start")
async def start_stream(payload: StreamStartRequest, request: Request) -> dict:
    manager = _manager(request)
    source = payload.rtsp_url if payload.rtsp_url else int(payload.camera_index or 0)
    try:
        return await manager.start(source)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/stream/stop")
async def stop_stream(request: Request) -> dict:
    return await _manager(request).stop()


@router.get("/status")
async def get_status(request: Request) -> dict:
    return _manager(request).get_status()


@router.get("/stream/frame")
async def get_live_frame(request: Request) -> Response:
    frame = _manager(request).get_latest_frame()
    if frame is None:
        raise HTTPException(status_code=404, detail="No live frame available")
    return Response(content=frame, media_type="image/jpeg")


@router.get("/stream/mjpeg")
async def get_live_mjpeg(request: Request) -> StreamingResponse:
    manager = _manager(request)

    async def stream():
        previous_frame: bytes | None = None
        while True:
            if await request.is_disconnected():
                break
            frame = manager.get_latest_frame()
            if frame and frame != previous_frame:
                previous_frame = frame
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
            await asyncio.sleep(0.08)

    return StreamingResponse(
        stream(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )
