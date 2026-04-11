from __future__ import annotations

import asyncio
from pathlib import Path

from config import get_settings
from db import fetch_device_tokens


class PushNotificationService:
    def __init__(self) -> None:
        self.settings = get_settings()

    @property
    def configured(self) -> bool:
        return bool(
            self.settings.apns_key_id
            and self.settings.apns_team_id
            and self.settings.apns_auth_key_path
            and self.settings.ios_bundle_id
        )

    async def send_incident_notification(
        self,
        *,
        incident_id: int | None,
        severity: str,
        reason: str,
        monitor_name: str,
        snapshot_path: str | None,
    ) -> bool:
        if not self.configured:
            return False

        tokens = await fetch_device_tokens(self.settings.db_path, platform="ios")
        if not tokens:
            return False

        return await asyncio.to_thread(
            self._send_sync,
            tokens=tokens,
            incident_id=incident_id,
            severity=severity,
            reason=reason,
            monitor_name=monitor_name,
            snapshot_path=snapshot_path,
        )

    def _send_sync(
        self,
        *,
        tokens: list[str],
        incident_id: int | None,
        severity: str,
        reason: str,
        monitor_name: str,
        snapshot_path: str | None,
    ) -> bool:
        try:
            from apns2.client import APNsClient
            from apns2.credentials import TokenCredentials
            from apns2.payload import Payload
        except ImportError:
            return False

        auth_key_path = Path(self.settings.apns_auth_key_path)
        if not auth_key_path.exists():
            return False

        credentials = TokenCredentials(
            auth_key_path=str(auth_key_path),
            auth_key_id=self.settings.apns_key_id,
            team_id=self.settings.apns_team_id,
        )
        client = APNsClient(
            credentials=credentials,
            use_sandbox=self.settings.apns_use_sandbox,
        )

        snapshot_url = None
        if snapshot_path:
            snapshot_url = f"{self.settings.public_api_base_url}/snapshots/{Path(snapshot_path).name}"

        custom_payload: dict[str, object] = {
            "severity": severity,
            "snapshot_url": snapshot_url,
            "monitor_name": monitor_name,
        }
        if incident_id is not None:
            custom_payload["incident_id"] = incident_id

        payload = Payload(
            alert={
                "title": f"{monitor_name}: {severity.upper()} alert",
                "body": reason,
            },
            sound="default",
            badge=1,
            mutable_content=True,
            custom=custom_payload,
        )

        sent = False
        for token in tokens:
            try:
                client.send_notification(
                    token,
                    payload,
                    topic=self.settings.ios_bundle_id,
                    push_type="alert",
                )
                sent = True
            except Exception:
                continue

        return sent


_default_push_service: PushNotificationService | None = None


def get_default_push_service() -> PushNotificationService:
    global _default_push_service
    if _default_push_service is None:
        _default_push_service = PushNotificationService()
    return _default_push_service
