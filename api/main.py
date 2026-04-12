from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes.alerts import router as alerts_router
from api.routes.clips import router as clips_router
from api.routes.recordings import router as recordings_router
from api.routes.snapshots import router as snapshots_router
from api.routes.stream import router as stream_router
from config import get_settings
from core.pipeline import PipelineManager
from db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    await init_db(settings.db_path)
    settings.clips_dir.mkdir(parents=True, exist_ok=True)
    settings.snapshots_dir.mkdir(parents=True, exist_ok=True)
    app.state.pipeline_manager = PipelineManager()
    yield
    manager: PipelineManager = app.state.pipeline_manager
    await manager.stop()


settings = get_settings()
app = FastAPI(title="CareWatch API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.cors_origin,
        "http://127.0.0.1:3000",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(stream_router)
app.include_router(alerts_router)
app.include_router(clips_router)
app.include_router(snapshots_router)
app.include_router(recordings_router)
