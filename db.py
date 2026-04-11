from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import aiosqlite


CREATE_ALERTS_TABLE = """
CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    severity TEXT NOT NULL,
    reason TEXT NOT NULL,
    suggested_action TEXT NOT NULL DEFAULT '',
    clip_path TEXT,
    sms_sent INTEGER NOT NULL DEFAULT 0,
    push_sent INTEGER NOT NULL DEFAULT 0,
    incident_id INTEGER
)
"""

CREATE_EVENTS_TABLE = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    flagged INTEGER NOT NULL,
    severity TEXT NOT NULL,
    reason TEXT NOT NULL,
    suggested_action TEXT NOT NULL DEFAULT '',
    clip_path TEXT
)
"""

CREATE_INCIDENTS_TABLE = """
CREATE TABLE IF NOT EXISTS incidents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'live',
    monitor_name TEXT NOT NULL DEFAULT 'Home Camera',
    status TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'none',
    heuristic_reason TEXT NOT NULL DEFAULT '',
    classifier_reason TEXT NOT NULL DEFAULT '',
    suggested_action TEXT NOT NULL DEFAULT '',
    snapshot_path TEXT,
    clip_path TEXT,
    review_latency_ms INTEGER NOT NULL DEFAULT 0,
    notified_push INTEGER NOT NULL DEFAULT 0,
    notified_sms INTEGER NOT NULL DEFAULT 0
)
"""

CREATE_DEVICE_REGISTRATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS device_registrations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT NOT NULL,
    token TEXT NOT NULL UNIQUE,
    device_name TEXT NOT NULL DEFAULT '',
    app_version TEXT NOT NULL DEFAULT '',
    notifications_enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""


async def init_db(db_path: Path) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(CREATE_ALERTS_TABLE)
        await db.execute(CREATE_EVENTS_TABLE)
        await db.execute(CREATE_INCIDENTS_TABLE)
        await db.execute(CREATE_DEVICE_REGISTRATIONS_TABLE)
        await db.commit()

        await _ensure_column(db, "alerts", "suggested_action", "TEXT NOT NULL DEFAULT ''")
        await _ensure_column(db, "alerts", "push_sent", "INTEGER NOT NULL DEFAULT 0")
        await _ensure_column(db, "alerts", "incident_id", "INTEGER")
        await _ensure_column(db, "events", "suggested_action", "TEXT NOT NULL DEFAULT ''")
        await _ensure_column(db, "incidents", "source", "TEXT NOT NULL DEFAULT 'live'")
        await _ensure_column(db, "incidents", "monitor_name", "TEXT NOT NULL DEFAULT 'Home Camera'")
        await _ensure_column(db, "incidents", "status", "TEXT NOT NULL DEFAULT 'reviewing'")
        await _ensure_column(db, "incidents", "severity", "TEXT NOT NULL DEFAULT 'none'")
        await _ensure_column(db, "incidents", "heuristic_reason", "TEXT NOT NULL DEFAULT ''")
        await _ensure_column(db, "incidents", "classifier_reason", "TEXT NOT NULL DEFAULT ''")
        await _ensure_column(db, "incidents", "suggested_action", "TEXT NOT NULL DEFAULT ''")
        await _ensure_column(db, "incidents", "snapshot_path", "TEXT")
        await _ensure_column(db, "incidents", "clip_path", "TEXT")
        await _ensure_column(db, "incidents", "review_latency_ms", "INTEGER NOT NULL DEFAULT 0")
        await _ensure_column(db, "incidents", "notified_push", "INTEGER NOT NULL DEFAULT 0")
        await _ensure_column(db, "incidents", "notified_sms", "INTEGER NOT NULL DEFAULT 0")
        await _ensure_column(db, "device_registrations", "device_name", "TEXT NOT NULL DEFAULT ''")
        await _ensure_column(db, "device_registrations", "app_version", "TEXT NOT NULL DEFAULT ''")
        await _ensure_column(db, "device_registrations", "notifications_enabled", "INTEGER NOT NULL DEFAULT 1")
        await _ensure_column(db, "device_registrations", "created_at", "TEXT NOT NULL DEFAULT ''")
        await _ensure_column(db, "device_registrations", "updated_at", "TEXT NOT NULL DEFAULT ''")
        await db.commit()


async def _ensure_column(
    db: aiosqlite.Connection,
    table_name: str,
    column_name: str,
    column_definition: str,
) -> None:
    cursor = await db.execute(f"PRAGMA table_info({table_name})")
    columns = await cursor.fetchall()
    names = {row[1] for row in columns}
    if column_name not in names:
        await db.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def log_alert(
    db_path: Path,
    timestamp: str,
    severity: str,
    reason: str,
    clip_path: str | None,
    sms_sent: bool,
    suggested_action: str = "",
    push_sent: bool = False,
    incident_id: int | None = None,
) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT INTO alerts (timestamp, severity, reason, suggested_action, clip_path, sms_sent, push_sent, incident_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (timestamp, severity, reason, suggested_action, clip_path, int(sms_sent), int(push_sent), incident_id),
        )
        await db.commit()


async def log_event(
    db_path: Path,
    timestamp: str,
    flagged: bool,
    severity: str,
    reason: str,
    clip_path: str | None,
    suggested_action: str = "",
) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT INTO events (timestamp, flagged, severity, reason, suggested_action, clip_path)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (timestamp, int(flagged), severity, reason, suggested_action, clip_path),
        )
        await db.commit()


async def create_incident(
    db_path: Path,
    started_at: str,
    status: str,
    severity: str,
    heuristic_reason: str,
    classifier_reason: str,
    suggested_action: str,
    snapshot_path: str | None,
    clip_path: str | None = None,
    source: str = "live",
    monitor_name: str = "Home Camera",
    review_latency_ms: int = 0,
) -> int:
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            """
            INSERT INTO incidents (
                started_at,
                updated_at,
                source,
                monitor_name,
                status,
                severity,
                heuristic_reason,
                classifier_reason,
                suggested_action,
                snapshot_path,
                clip_path,
                review_latency_ms
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                started_at,
                started_at,
                source,
                monitor_name,
                status,
                severity,
                heuristic_reason,
                classifier_reason,
                suggested_action,
                snapshot_path,
                clip_path,
                review_latency_ms,
            ),
        )
        await db.commit()
        return int(cursor.lastrowid)


async def update_incident(
    db_path: Path,
    incident_id: int,
    *,
    status: str,
    severity: str,
    classifier_reason: str,
    suggested_action: str,
    clip_path: str | None = None,
    review_latency_ms: int = 0,
    notified_push: bool | None = None,
    notified_sms: bool | None = None,
) -> None:
    update_fields: list[str] = [
        "updated_at = ?",
        "status = ?",
        "severity = ?",
        "classifier_reason = ?",
        "suggested_action = ?",
        "review_latency_ms = ?",
    ]
    params: list[Any] = [
        utc_now_iso(),
        status,
        severity,
        classifier_reason,
        suggested_action,
        review_latency_ms,
    ]
    if clip_path is not None:
        update_fields.append("clip_path = ?")
        params.append(clip_path)
    if notified_push is not None:
        update_fields.append("notified_push = ?")
        params.append(int(notified_push))
    if notified_sms is not None:
        update_fields.append("notified_sms = ?")
        params.append(int(notified_sms))

    params.append(incident_id)
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            f"""
            UPDATE incidents
            SET {", ".join(update_fields)}
            WHERE id = ?
            """,
            params,
        )
        await db.commit()


async def mark_incident_notifications(
    db_path: Path,
    incident_id: int,
    *,
    push_sent: bool | None = None,
    sms_sent: bool | None = None,
) -> None:
    update_fields = ["updated_at = ?"]
    params: list[Any] = [utc_now_iso()]
    if push_sent is not None:
        update_fields.append("notified_push = ?")
        params.append(int(push_sent))
    if sms_sent is not None:
        update_fields.append("notified_sms = ?")
        params.append(int(sms_sent))
    params.append(incident_id)
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            f"""
            UPDATE incidents
            SET {", ".join(update_fields)}
            WHERE id = ?
            """,
            params,
        )
        await db.commit()


async def fetch_alerts(db_path: Path, limit: int = 50) -> list[dict]:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT id, timestamp, severity, reason, suggested_action, clip_path, sms_sent, push_sent, incident_id
            FROM alerts
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def fetch_incidents(
    db_path: Path,
    limit: int = 50,
    status: str | None = None,
) -> list[dict]:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        if status:
            cursor = await db.execute(
                """
                SELECT *
                FROM incidents
                WHERE status = ?
                ORDER BY started_at DESC
                LIMIT ?
                """,
                (status, limit),
            )
        else:
            cursor = await db.execute(
                """
                SELECT *
                FROM incidents
                ORDER BY started_at DESC
                LIMIT ?
                """,
                (limit,),
            )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def fetch_incident(db_path: Path, incident_id: int) -> dict[str, Any] | None:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM incidents WHERE id = ? LIMIT 1",
            (incident_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def fetch_latest_incident(db_path: Path) -> dict[str, Any] | None:
    incidents = await fetch_incidents(db_path, limit=1)
    return incidents[0] if incidents else None


async def count_alerts(db_path: Path) -> int:
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM alerts")
        row = await cursor.fetchone()
        return int(row[0]) if row else 0


async def count_incidents(db_path: Path) -> int:
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM incidents")
        row = await cursor.fetchone()
        return int(row[0]) if row else 0


async def was_recent_alert_sent(db_path: Path, severity: str, within_seconds: int) -> bool:
    cutoff = (datetime.now(timezone.utc) - timedelta(seconds=within_seconds)).isoformat()
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            """
            SELECT 1
            FROM alerts
            WHERE severity = ? AND push_sent = 1 AND timestamp >= ?
            ORDER BY timestamp DESC
            LIMIT 1
            """,
            (severity, cutoff),
        )
        return await cursor.fetchone() is not None


async def register_device_token(
    db_path: Path,
    *,
    platform: str,
    token: str,
    device_name: str = "",
    app_version: str = "",
    notifications_enabled: bool = True,
) -> None:
    now = utc_now_iso()
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT INTO device_registrations (
                platform,
                token,
                device_name,
                app_version,
                notifications_enabled,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(token) DO UPDATE SET
                platform = excluded.platform,
                device_name = excluded.device_name,
                app_version = excluded.app_version,
                notifications_enabled = excluded.notifications_enabled,
                updated_at = excluded.updated_at
            """,
            (
                platform,
                token,
                device_name,
                app_version,
                int(notifications_enabled),
                now,
                now,
            ),
        )
        await db.commit()


async def remove_device_token(db_path: Path, token: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute("DELETE FROM device_registrations WHERE token = ?", (token,))
        await db.commit()


async def fetch_device_tokens(db_path: Path, platform: str = "ios") -> list[str]:
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            """
            SELECT token
            FROM device_registrations
            WHERE platform = ? AND notifications_enabled = 1
            ORDER BY updated_at DESC
            """,
            (platform,),
        )
        rows = await cursor.fetchall()
        return [str(row[0]) for row in rows if row and row[0]]
