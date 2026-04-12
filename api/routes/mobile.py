from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from config import get_settings
from core.alert import get_default_alert_service
from db import (
    fetch_incident,
    fetch_incidents,
    fetch_device_tokens,
    fetch_latest_incident,
    register_device_token,
    remove_device_token,
    utc_now_iso,
)


router = APIRouter(prefix="/mobile/v1", tags=["mobile"])


class DeviceRegistrationRequest(BaseModel):
    platform: str = Field(default="ios")
    token: str
    device_name: str = Field(default="")
    app_version: str = Field(default="")
    notifications_enabled: bool = Field(default=True)


def _absolute_media_url(request: Request, path_value: str | None, media_type: str) -> str | None:
    if not path_value:
        return None
    safe_name = Path(path_value).name
    if media_type == "clip":
        return str(request.url_for("get_clip", filename=safe_name))
    return str(request.url_for("get_snapshot", filename=safe_name))


def _serialize_incident(request: Request, incident: dict[str, Any] | None) -> dict[str, Any] | None:
    if not incident:
        return None

    snapshot_url = _absolute_media_url(request, incident.get("snapshot_path"), "snapshot")
    clip_url = _absolute_media_url(request, incident.get("clip_path"), "clip")
    status = str(incident.get("status", "reviewing"))
    classifier_reason = str(incident.get("classifier_reason", "") or "")
    heuristic_reason = str(incident.get("heuristic_reason", "") or "")
    reason_short = classifier_reason or heuristic_reason or "Monitoring event"

    return {
        "id": incident["id"],
        "status": status,
        "severity": incident.get("severity", "none"),
        "source": incident.get("source", "live"),
        "monitor_name": incident.get("monitor_name", "Home Camera"),
        "started_at": incident.get("started_at"),
        "updated_at": incident.get("updated_at"),
        "heuristic_reason": heuristic_reason,
        "classifier_reason": classifier_reason,
        "reason_short": reason_short,
        "suggested_action": incident.get("suggested_action", ""),
        "review_latency_ms": incident.get("review_latency_ms", 0),
        "snapshot_url": snapshot_url,
        "clip_url": clip_url,
        "clip_ready": bool(clip_url),
        "notified_push": bool(incident.get("notified_push", 0)),
        "notified_sms": bool(incident.get("notified_sms", 0)),
    }


@router.get("/overview")
async def get_mobile_overview(request: Request) -> dict[str, Any]:
    settings = get_settings()
    pipeline = request.app.state.pipeline_manager
    status = pipeline.get_status()
    latest_incident = await fetch_latest_incident(settings.db_path)
    device_tokens = await fetch_device_tokens(settings.db_path, platform="ios")
    push_configured = bool(
        settings.apns_key_id
        and settings.apns_team_id
        and settings.apns_auth_key_path
        and settings.ios_bundle_id
    )

    return {
        "monitor": {
            "name": "Home Camera",
            "running": status["running"],
            "watch_state": "reviewing" if status["review_in_progress"] else ("watching" if status["running"] else "offline"),
            "uptime_seconds": status["uptime_seconds"],
            "people_count": status["people_count"],
            "last_heuristic_reason": status["last_heuristic_reason"],
            "last_classifier_reason": status["last_classifier_reason"],
            "last_classifier_severity": status["last_classifier_severity"],
            "last_review_latency_ms": status["last_review_latency_ms"],
            "latest_snapshot_url": _absolute_media_url(request, status["last_snapshot_url"], "snapshot"),
            "live_frame_url": str(request.url_for("get_live_frame")),
            "live_stream_url": str(request.url_for("get_live_mjpeg")),
        },
        "latest_incident": _serialize_incident(request, latest_incident),
        "notification_channels": {
            "push_configured": push_configured,
            "sms_configured": False,
            "registered_devices": len(device_tokens),
        },
    }


@router.get("/incidents")
async def get_mobile_incidents(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    status: str | None = Query(default=None),
) -> dict[str, Any]:
    settings = get_settings()
    incidents = await fetch_incidents(settings.db_path, limit=limit, status=status)
    return {
        "items": [_serialize_incident(request, incident) for incident in incidents],
    }


@router.get("/incidents/{incident_id}")
async def get_mobile_incident(incident_id: int, request: Request) -> dict[str, Any]:
    settings = get_settings()
    incident = await fetch_incident(settings.db_path, incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return _serialize_incident(request, incident) or {}


@router.post("/devices")
async def create_device_registration(payload: DeviceRegistrationRequest) -> dict[str, str]:
    settings = get_settings()
    await register_device_token(
        settings.db_path,
        platform=payload.platform,
        token=payload.token,
        device_name=payload.device_name,
        app_version=payload.app_version,
        notifications_enabled=payload.notifications_enabled,
    )
    return {"status": "registered"}


@router.delete("/devices/{token}")
async def delete_device_registration(token: str) -> dict[str, str]:
    settings = get_settings()
    await remove_device_token(settings.db_path, token)
    return {"status": "removed"}


@router.post("/notifications/test")
async def send_test_notification(request: Request) -> dict[str, Any]:
    settings = get_settings()
    latest_incident = await fetch_latest_incident(settings.db_path)
    alert_service = get_default_alert_service()

    incident_id = latest_incident.get("id") if latest_incident else None
    severity = str(latest_incident.get("severity") or "medium") if latest_incident else "medium"
    reason = (
        str(latest_incident.get("classifier_reason") or latest_incident.get("heuristic_reason") or "")
        if latest_incident
        else ""
    )
    reason = reason or "This is a CareWatch test alert from your phone."
    suggested_action = (
        str(latest_incident.get("suggested_action") or "Open the app and review the latest incident details.")
        if latest_incident
        else "Open the app and confirm notifications are reaching your phone."
    )
    clip_path = None
    snapshot_path = None
    if latest_incident:
        clip_path = str(latest_incident.get("clip_path") or "") or None
        snapshot_path = str(latest_incident.get("snapshot_path") or "") or None

    push_sent = await alert_service.send_alert(
        reason=reason,
        severity=severity,
        clip_path=clip_path,
        timestamp=utc_now_iso(),
        suggested_action=suggested_action,
        incident_id=incident_id,
        monitor_name="Home Camera",
        snapshot_path=snapshot_path,
        force_delivery=True,
    )

    return {
        "push_sent": push_sent,
        "sms_sent": False,
        "push_configured": alert_service.push_service.configured,
        "sms_configured": False,
        "incident_id": incident_id,
    }
