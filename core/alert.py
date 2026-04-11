from __future__ import annotations

from config import get_settings
from core.push import PushNotificationService
from db import log_alert, mark_incident_notifications, was_recent_alert_sent


class AlertService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.push_service = PushNotificationService()

    async def send_alert(
        self,
        reason: str,
        severity: str,
        clip_path: str | None,
        timestamp: str,
        suggested_action: str = "",
        incident_id: int | None = None,
        monitor_name: str = "Home Camera",
        snapshot_path: str | None = None,
        force_delivery: bool = False,
    ) -> bool:
        should_deduplicate = False
        if not force_delivery:
            should_deduplicate = await was_recent_alert_sent(
                self.settings.db_path,
                severity,
                within_seconds=300,
            )

        push_sent = False
        if not should_deduplicate:
            push_sent = await self.push_service.send_incident_notification(
                incident_id=incident_id,
                severity=severity,
                reason=reason,
                monitor_name=monitor_name,
                snapshot_path=snapshot_path,
            )

        await log_alert(
            self.settings.db_path,
            timestamp=timestamp,
            severity=severity,
            reason=reason,
            clip_path=clip_path,
            sms_sent=False,
            suggested_action=suggested_action,
            push_sent=push_sent,
            incident_id=incident_id,
        )
        if incident_id is not None:
            await mark_incident_notifications(
                self.settings.db_path,
                incident_id,
                push_sent=push_sent,
                sms_sent=False,
            )

        return push_sent


_default_alert_service: AlertService | None = None


def get_default_alert_service() -> AlertService:
    global _default_alert_service
    if _default_alert_service is None:
        _default_alert_service = AlertService()
    return _default_alert_service


async def send_alert(
    reason: str,
    severity: str,
    clip_path: str | None,
    timestamp: str,
    suggested_action: str = "",
    incident_id: int | None = None,
    monitor_name: str = "Home Camera",
    snapshot_path: str | None = None,
    force_delivery: bool = False,
) -> bool:
    return await get_default_alert_service().send_alert(
        reason=reason,
        severity=severity,
        clip_path=clip_path,
        timestamp=timestamp,
        suggested_action=suggested_action,
        incident_id=incident_id,
        monitor_name=monitor_name,
        snapshot_path=snapshot_path,
        force_delivery=force_delivery,
    )
