from __future__ import annotations

import asyncio
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from config import get_settings
from core.alert import AlertService
from core.classifier import SceneClassifier
from core.clip_saver import ClipSaver
from core.detector import PoseDetector
from db import (
    count_alerts,
    create_incident,
    log_event,
    update_incident,
    utc_now_iso,
)


@dataclass(slots=True)
class ReviewRequest:
    incident_id: int
    timestamp: str
    heuristic_reason: str
    snapshot_path: str | None
    burst_frames: list[np.ndarray]
    clip_frames: list[np.ndarray]


@dataclass(slots=True)
class SuspicionSummary:
    reason: str
    strike_count: int
    rapid_motion_count: int
    latest_timestamp: float


class CareWatchPipeline:
    def __init__(self, camera_index: int | str) -> None:
        self.settings = get_settings()
        self.source = camera_index
        self.capture: cv2.VideoCapture | None = None
        self.detector = PoseDetector()
        self.classifier = SceneClassifier()
        self.alert_service = AlertService()
        self.clip_saver: ClipSaver | None = None
        self.running = False
        self.started_at: float | None = None
        self.alert_count = 0
        self.prev_persons: list[dict[str, Any]] = []
        self.latest_frame_jpeg: bytes | None = None
        self.last_detected_persons: list[dict[str, Any]] = []
        self.last_interaction_flagged = False
        self.last_people_count = 0
        self.last_heuristic_reason = "monitoring"
        self.last_classifier_reason = "No concern detected."
        self.last_classifier_severity = "none"
        self.last_review_latency_ms = 0
        self.estimated_detection_fps = 0.0
        self.review_in_progress = False
        self.last_snapshot_url: str | None = None
        self.last_snapshot_reason: str | None = None
        self.last_snapshot_timestamp: str | None = None
        self._last_force_flag_at = 0.0
        self._review_task: asyncio.Task | None = None
        self._review_started_at: float | None = None
        self._review_token = 0
        self._active_review_token: int | None = None
        self._active_incident_id: int | None = None
        self._next_review_allowed_at = 0.0
        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()
        self._frame_counter = 0
        self._detection_counter = 0
        self._fps_window_started_at = time.time()
        self._previous_gray_small: np.ndarray | None = None
        self._previous_motion_gray: np.ndarray | None = None
        self._recent_events: deque[tuple[float, str]] = deque()
        self._last_event_preview: bytes | None = None
        self._last_event_timestamp: str | None = None
        self._last_event_reason: str | None = None

    async def start(self) -> None:
        if self.running:
            return
        self.capture = await asyncio.to_thread(cv2.VideoCapture, self.source)
        if not self.capture or not self.capture.isOpened():
            raise RuntimeError(f"Unable to open video source: {self.source}")
        self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.settings.live_capture_width)
        self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.settings.live_capture_height)

        fps = int(self.capture.get(cv2.CAP_PROP_FPS))
        if fps <= 0 or fps > 60:
            fps = 10

        self.clip_saver = ClipSaver(fps=fps)
        self.alert_count = await count_alerts(self.settings.db_path)
        self.running = True
        self.started_at = time.time()
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run_loop(), name="carewatch-pipeline")

    async def stop(self) -> None:
        self.running = False
        self._stop_event.set()
        if self._task:
            await self._task
            self._task = None
        if self._review_task:
            await self._review_task
            self._review_task = None
        if self.capture:
            await asyncio.to_thread(self.capture.release)
            self.capture = None

    def get_status(self) -> dict[str, Any]:
        uptime_seconds = int(time.time() - self.started_at) if self.running and self.started_at else 0
        return {
            "running": self.running,
            "uptime_seconds": uptime_seconds,
            "alert_count": self.alert_count,
            "source": self.source,
            "people_count": self.last_people_count,
            "last_heuristic_reason": self.last_heuristic_reason,
            "last_classifier_reason": self.last_classifier_reason,
            "last_classifier_severity": self.last_classifier_severity,
            "last_review_latency_ms": self.last_review_latency_ms,
            "estimated_detection_fps": round(self.estimated_detection_fps, 1),
            "review_in_progress": self.review_in_progress,
            "last_snapshot_url": self.last_snapshot_url,
            "last_snapshot_reason": self.last_snapshot_reason,
            "last_snapshot_timestamp": self.last_snapshot_timestamp,
        }

    def get_latest_frame(self) -> bytes | None:
        return self.latest_frame_jpeg

    async def _run_loop(self) -> None:
        assert self.capture is not None
        assert self.clip_saver is not None

        try:
            while self.running and not self._stop_event.is_set():
                self._expire_stale_review()
                ok, frame = await asyncio.to_thread(self.capture.read)
                if not ok or frame is None:
                    await asyncio.sleep(0.2)
                    continue

                self._frame_counter += 1
                self.clip_saver.add_frame(frame)
                global_motion_vector = self._estimate_global_motion(frame)
                should_run_detection = self._frame_counter % max(self.settings.live_detection_stride, 1) == 0
                if should_run_detection:
                    persons = await asyncio.to_thread(self.detector.detect, frame)
                    interaction_flagged = self.detector.is_interaction_flagged(
                        persons,
                        self.prev_persons,
                        global_motion_vector=global_motion_vector,
                    )
                    motion_intrusion_reason = self._detect_motion_intrusion(
                        frame,
                        persons,
                        global_motion_vector=global_motion_vector,
                    )
                    if motion_intrusion_reason and not interaction_flagged:
                        interaction_flagged = True
                        self.detector.last_flag_reason = motion_intrusion_reason
                    self.prev_persons = persons
                    self.last_detected_persons = persons
                    self.last_interaction_flagged = interaction_flagged
                    self.last_people_count = len(persons)
                    self.last_heuristic_reason = self.detector.last_flag_reason
                    self._detection_counter += 1
                    self._update_detection_fps()
                else:
                    persons = self.last_detected_persons
                    interaction_flagged = self.last_interaction_flagged

                self.latest_frame_jpeg = await asyncio.to_thread(
                    self._encode_preview_frame,
                    frame,
                    persons,
                    interaction_flagged,
                )
                timestamp = utc_now_iso()
                clip_path: str | None = None
                reason = "Monitoring normal activity."
                severity = "none"
                suggested_action = "Continue monitoring."
                flagged = False
                incident_id: int | None = None
                now = time.time()

                if interaction_flagged:
                    self._record_suspicion_event(
                        timestamp=timestamp,
                        event_time=now,
                        heuristic_reason=self.detector.last_flag_reason,
                    )

                summary = self._recent_suspicion_summary()
                if summary and not self.review_in_progress:
                    self.last_heuristic_reason = summary.reason

                if summary:
                    if self._should_force_flag_live_hit(summary):
                        snapshot_path = self._record_snapshot(
                            timestamp=self._last_event_timestamp or timestamp,
                            heuristic_reason=summary.reason,
                            preview_frame=self._last_event_preview or self.latest_frame_jpeg,
                        )
                        clip_path = await asyncio.to_thread(
                            self.clip_saver.save_frames,
                            self.clip_saver.get_buffer_snapshot(),
                            "high",
                        )
                        reason = "Repeated strike-contact motion detected live; escalating as probable physical abuse."
                        severity = "high"
                        suggested_action = "Immediately check on the dependent, remove the aggressor, and review the saved clip."
                        flagged = True
                        self.last_classifier_reason = reason
                        self.last_classifier_severity = severity
                        self._last_force_flag_at = time.time()
                        self._next_review_allowed_at = max(
                            self._next_review_allowed_at,
                            time.time() + self.settings.gemini_cooldown_seconds,
                        )
                        incident_id = await create_incident(
                            self.settings.db_path,
                            started_at=timestamp,
                            status="flagged",
                            severity=severity,
                            heuristic_reason=summary.reason,
                            classifier_reason=reason,
                            suggested_action=suggested_action,
                            snapshot_path=snapshot_path,
                            clip_path=clip_path,
                        )
                        await self.alert_service.send_alert(
                            reason=reason,
                            severity=severity,
                            clip_path=clip_path,
                            timestamp=timestamp,
                            suggested_action=suggested_action,
                            incident_id=incident_id,
                            snapshot_path=snapshot_path,
                        )
                        self.alert_count += 1
                        await log_event(
                            self.settings.db_path,
                            timestamp=timestamp,
                            flagged=flagged,
                            severity=severity,
                            reason=reason,
                            clip_path=clip_path,
                            suggested_action=suggested_action,
                        )
                        self._recent_events.clear()
                        await asyncio.sleep(0)
                        continue

                    can_schedule_review = (
                        not self.review_in_progress
                        and time.time() >= self._next_review_allowed_at
                    )
                    if can_schedule_review and self._should_schedule_review(summary):
                        snapshot_path = self._record_snapshot(
                            timestamp=self._last_event_timestamp or timestamp,
                            heuristic_reason=summary.reason,
                            preview_frame=self._last_event_preview or self.latest_frame_jpeg,
                        )
                        incident_id = await create_incident(
                            self.settings.db_path,
                            started_at=timestamp,
                            status="reviewing",
                            severity="reviewing",
                            heuristic_reason=summary.reason,
                            classifier_reason=f"Reviewing possible anomaly: {summary.reason}.",
                            suggested_action="Waiting for vision review.",
                            snapshot_path=snapshot_path,
                        )
                        self._schedule_review(
                            ReviewRequest(
                                incident_id=incident_id,
                                timestamp=timestamp,
                                heuristic_reason=summary.reason,
                                snapshot_path=snapshot_path,
                                burst_frames=self.clip_saver.sample_recent_window(
                                    window_seconds=self.settings.live_review_window_seconds,
                                    frame_count=self.settings.live_review_sequence_frames,
                                )
                                or [frame.copy()],
                                clip_frames=self.clip_saver.get_buffer_snapshot(),
                            )
                        )
                        reason = f"Reviewing possible anomaly: {summary.reason}."
                        suggested_action = "Waiting for vision review."
                        self.last_classifier_reason = reason
                        self.last_classifier_severity = "reviewing"
                    elif self.review_in_progress:
                        reason = f"Reviewing possible anomaly: {summary.reason}."
                        suggested_action = "Waiting for vision review."
                    elif interaction_flagged:
                        reason = self.last_classifier_reason
                        severity = self.last_classifier_severity
                        suggested_action = "Waiting for cooldown before another review."
                elif not self.review_in_progress:
                    self.last_heuristic_reason = "monitoring"
                    self.last_classifier_reason = reason
                    self.last_classifier_severity = severity

                await log_event(
                    self.settings.db_path,
                    timestamp=timestamp,
                    flagged=flagged,
                    severity=severity,
                    reason=reason,
                    clip_path=clip_path,
                    suggested_action=suggested_action,
                )
                await asyncio.sleep(0)
        finally:
            self.running = False
            self.latest_frame_jpeg = None
            if self.capture:
                await asyncio.to_thread(self.capture.release)
                self.capture = None

    def _schedule_review(self, request: ReviewRequest) -> None:
        self._review_token += 1
        review_token = self._review_token
        self.review_in_progress = True
        self._review_started_at = time.time()
        self._active_review_token = review_token
        self._active_incident_id = request.incident_id
        self._next_review_allowed_at = self._review_started_at + self.settings.gemini_cooldown_seconds
        self._review_task = asyncio.create_task(
            self._process_review(request, review_token),
            name="carewatch-review",
        )

    async def _process_review(self, request: ReviewRequest, review_token: int) -> None:
        review_started_at = time.time()
        try:
            classification = await asyncio.wait_for(
                self.classifier.classify_burst(
                    request.burst_frames,
                    context_hint=(
                        "Pose tracker saw suspicious live motion over a short recent window. "
                        f"Heuristic reason: {request.heuristic_reason}"
                    ),
                    prefer_local=self.settings.live_review_provider == "local",
                ),
                timeout=self.settings.review_timeout_seconds,
            )

            reason = classification["reason"]
            severity = classification["severity"]
            suggested_action = classification["suggested_action"]
            flagged = bool(classification["flagged"])
            clip_path: str | None = None

            if flagged:
                clip_path = await asyncio.to_thread(
                    self.clip_saver.save_frames,
                    request.clip_frames,
                    severity,
                )
                await self.alert_service.send_alert(
                    reason=reason,
                    severity=severity,
                    clip_path=clip_path,
                    timestamp=request.timestamp,
                    suggested_action=suggested_action,
                    incident_id=request.incident_id,
                    snapshot_path=request.snapshot_path,
                )
                self.alert_count += 1
            else:
                reason = f"Heuristic triggered but the vision model cleared the scene: {request.heuristic_reason}."
                severity = "none"
                suggested_action = "Continue monitoring."

            if not self._is_current_review(review_token):
                return
            self.last_classifier_reason = reason
            self.last_classifier_severity = severity
            await update_incident(
                self.settings.db_path,
                request.incident_id,
                status="flagged" if flagged else "cleared",
                severity=severity,
                classifier_reason=reason,
                suggested_action=suggested_action,
                clip_path=clip_path,
                review_latency_ms=int((time.time() - review_started_at) * 1000),
            )
            await log_event(
                self.settings.db_path,
                timestamp=request.timestamp,
                flagged=flagged,
                severity=severity,
                reason=reason,
                clip_path=clip_path,
                suggested_action=suggested_action,
            )
        except TimeoutError:
            if not self._is_current_review(review_token):
                return
            self.last_classifier_reason = (
                f"Vision review timed out after {self.settings.review_timeout_seconds}s; "
                f"continuing monitoring after {request.heuristic_reason}."
            )
            self.last_classifier_severity = "timeout"
            await update_incident(
                self.settings.db_path,
                request.incident_id,
                status="timed_out",
                severity="none",
                classifier_reason=self.last_classifier_reason,
                suggested_action="Continue monitoring.",
                review_latency_ms=int((time.time() - review_started_at) * 1000),
            )
            await log_event(
                self.settings.db_path,
                timestamp=request.timestamp,
                flagged=False,
                severity="none",
                reason=self.last_classifier_reason,
                clip_path=None,
                suggested_action="Continue monitoring.",
            )
        except Exception as exc:
            if not self._is_current_review(review_token):
                return
            self.last_classifier_reason = f"Vision review failed: {exc}"
            self.last_classifier_severity = "error"
            await update_incident(
                self.settings.db_path,
                request.incident_id,
                status="error",
                severity="none",
                classifier_reason=self.last_classifier_reason,
                suggested_action="Retry review or continue monitoring.",
                review_latency_ms=int((time.time() - review_started_at) * 1000),
            )
        finally:
            if self._is_current_review(review_token):
                self.last_review_latency_ms = int((time.time() - review_started_at) * 1000)
                self.review_in_progress = False
                self._review_started_at = None
                self._active_review_token = None
                self._active_incident_id = None
                self._next_review_allowed_at = max(
                    self._next_review_allowed_at,
                    time.time() + self.settings.gemini_cooldown_seconds,
                )
            if self._review_task is asyncio.current_task():
                self._review_task = None

    def _is_current_review(self, review_token: int) -> bool:
        return self._active_review_token == review_token

    def _expire_stale_review(self) -> None:
        if not self.review_in_progress or self._review_started_at is None:
            return
        elapsed = time.time() - self._review_started_at
        timeout_seconds = self.settings.review_timeout_seconds + 1
        if elapsed <= timeout_seconds:
            return

        self.last_classifier_reason = (
            f"Vision review timed out after {self.settings.review_timeout_seconds}s; "
            "continuing monitoring."
        )
        self.last_classifier_severity = "timeout"
        self.last_review_latency_ms = int(elapsed * 1000)
        incident_id = self._active_incident_id
        self.review_in_progress = False
        self._review_started_at = None
        self._active_review_token = None
        self._active_incident_id = None
        self._next_review_allowed_at = max(
            self._next_review_allowed_at,
            time.time() + self.settings.gemini_cooldown_seconds,
        )
        if self._review_task and not self._review_task.done():
            self._review_task.cancel()
        self._review_task = None
        if incident_id is not None:
            asyncio.create_task(
                update_incident(
                    self.settings.db_path,
                    incident_id,
                    status="timed_out",
                    severity="none",
                    classifier_reason=self.last_classifier_reason,
                    suggested_action="Continue monitoring.",
                    review_latency_ms=self.last_review_latency_ms,
                ),
                name="carewatch-review-timeout",
            )

    def _update_detection_fps(self) -> None:
        now = time.time()
        elapsed = now - self._fps_window_started_at
        if elapsed >= 1.0:
            self.estimated_detection_fps = self._detection_counter / elapsed
            self._detection_counter = 0
            self._fps_window_started_at = now

    def _record_snapshot(self, timestamp: str, heuristic_reason: str, preview_frame: bytes | None) -> str | None:
        if not preview_frame:
            return None
        snapshot_name = (
            f"{timestamp.replace(':', '').replace('-', '').replace('+00:00', 'Z').replace('.', '')}_"
            f"{heuristic_reason}.jpg"
        )
        snapshot_path = self.settings.snapshots_dir / snapshot_name
        snapshot_path.write_bytes(preview_frame)
        self.last_snapshot_url = f"/snapshots/{Path(snapshot_name).name}"
        self.last_snapshot_reason = heuristic_reason
        self.last_snapshot_timestamp = timestamp
        return f"snapshots/{Path(snapshot_name).name}"

    def _estimate_global_motion(self, frame: np.ndarray) -> tuple[float, float]:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray_small = cv2.resize(gray, (160, 90), interpolation=cv2.INTER_AREA).astype(np.float32)
        if self._previous_gray_small is None:
            self._previous_gray_small = gray_small
            return (0.0, 0.0)

        shift, _ = cv2.phaseCorrelate(self._previous_gray_small, gray_small)
        self._previous_gray_small = gray_small
        scale_x = frame.shape[1] / 160.0
        scale_y = frame.shape[0] / 90.0
        motion_vector = (float(shift[0] * scale_x), float(shift[1] * scale_y))
        if float(np.linalg.norm(np.asarray(motion_vector, dtype=float))) < self.settings.camera_motion_shift_threshold_px:
            return (0.0, 0.0)
        return motion_vector

    def _detect_motion_intrusion(
        self,
        frame: np.ndarray,
        persons: list[dict[str, Any]],
        *,
        global_motion_vector: tuple[float, float],
    ) -> str | None:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)
        previous_gray = self._previous_motion_gray
        self._previous_motion_gray = gray
        if previous_gray is None or not persons:
            return None

        max_area = max(
            (self.detector._bbox_area(person["bbox"]) for person in persons),  # noqa: SLF001
            default=0.0,
        )
        viable_persons = [
            person
            for person in persons
            if self.detector._person_is_viable_interaction_target(person, max_area=max_area)  # noqa: SLF001
        ]
        if not viable_persons:
            return None

        primary_person = next(
            (person for person in viable_persons if person.get("role") == "subject"),
            None,
        )
        if primary_person is None:
            primary_person = self.detector._select_primary_person(  # noqa: SLF001
                viable_persons,
                frame_width=frame.shape[1],
                frame_height=frame.shape[0],
            )
        if primary_person is None:
            return None
        x1, y1, x2, y2 = [int(value) for value in primary_person["bbox"]]
        if x2 <= x1 or y2 <= y1:
            return None

        transform = np.float32(
            [[1, 0, global_motion_vector[0]], [0, 1, global_motion_vector[1]]]
        )
        stabilized_previous = cv2.warpAffine(
            previous_gray,
            transform,
            (gray.shape[1], gray.shape[0]),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REPLICATE,
        )
        diff = cv2.absdiff(gray, stabilized_previous)
        _, thresholded = cv2.threshold(
            diff,
            self.settings.motion_intrusion_threshold,
            255,
            cv2.THRESH_BINARY,
        )
        thresholded = cv2.dilate(thresholded, None, iterations=2)
        contours, _ = cv2.findContours(thresholded, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        padding = self.settings.motion_intrusion_padding_px
        target_left = max(x1 - padding, 0)
        target_right = min(x2 + padding, gray.shape[1] - 1)
        target_top = max(y1, 0)
        target_bottom = min(int(y1 + (y2 - y1) * 0.62), gray.shape[0] - 1)
        if target_bottom <= target_top:
            return None

        for contour in contours:
            area = cv2.contourArea(contour)
            if area < self.settings.motion_intrusion_area_px:
                continue

            contour_x, contour_y, contour_w, contour_h = cv2.boundingRect(contour)
            contour_right = contour_x + contour_w
            contour_bottom = contour_y + contour_h

            overlap_left = max(contour_x, target_left)
            overlap_right = min(contour_right, target_right)
            overlap_top = max(contour_y, target_top)
            overlap_bottom = min(contour_bottom, target_bottom)
            if overlap_right <= overlap_left or overlap_bottom <= overlap_top:
                continue

            crosses_from_left = contour_x < x1 and contour_right > x1 + 8
            crosses_from_right = contour_right > x2 and contour_x < x2 - 8
            if not (crosses_from_left or crosses_from_right):
                continue

            contour_center_x = contour_x + contour_w / 2
            subject_center_x = (x1 + x2) / 2
            if abs(contour_center_x - subject_center_x) < (x2 - x1) * 0.18:
                continue

            return "possible_strike_contact"

        return None

    def _record_suspicion_event(self, *, timestamp: str, event_time: float, heuristic_reason: str) -> None:
        self._recent_events.append((event_time, heuristic_reason))
        self._last_event_preview = self.latest_frame_jpeg
        self._last_event_timestamp = timestamp
        self._last_event_reason = heuristic_reason
        self._prune_recent_events(event_time)

    def _prune_recent_events(self, now: float | None = None) -> None:
        now = now or time.time()
        while self._recent_events and now - self._recent_events[0][0] > self.settings.live_event_memory_seconds:
            self._recent_events.popleft()

    def _recent_suspicion_summary(self) -> SuspicionSummary | None:
        now = time.time()
        self._prune_recent_events(now)
        if not self._recent_events:
            return None
        strike_count = sum(1 for _, reason in self._recent_events if reason == "possible_strike_contact")
        rapid_motion_count = sum(1 for _, reason in self._recent_events if reason == "rapid_motion_near_dependent")
        latest_timestamp, latest_reason = self._recent_events[-1]
        reason = "possible_strike_contact" if strike_count else latest_reason
        return SuspicionSummary(
            reason=reason,
            strike_count=strike_count,
            rapid_motion_count=rapid_motion_count,
            latest_timestamp=latest_timestamp,
        )

    def _should_schedule_review(self, summary: SuspicionSummary) -> bool:
        if summary.strike_count >= self.settings.strike_review_hit_count:
            return True
        if summary.reason == "possible_strike_contact" and summary.strike_count >= 1:
            return True
        return summary.rapid_motion_count >= self.settings.rapid_motion_review_hit_count

    def _should_force_flag_live_hit(self, summary: SuspicionSummary) -> bool:
        if summary.reason != "possible_strike_contact":
            return False
        if self.last_people_count > self.settings.max_people_for_strike_force_flag:
            return False
        if summary.strike_count < self.settings.strike_force_flag_hit_count:
            return False
        if time.time() - self._last_force_flag_at < 15:
            return False
        return True

    @staticmethod
    def _encode_preview_frame(
        frame: np.ndarray,
        persons: list[dict[str, Any]],
        interaction_flagged: bool,
    ) -> bytes | None:
        preview = frame.copy()
        flagged_accent = (32, 181, 255)
        safe_accent = (122, 240, 189)
        bystander_accent = (110, 120, 125)
        for person in persons:
            x1, y1, x2, y2 = [int(value) for value in person["bbox"]]
            role = str(person.get("role", "bystander"))
            if role == "subject":
                accent = flagged_accent if interaction_flagged else safe_accent
                thickness = 3
                label = f"SUBJECT {person['id']}"
            elif role == "candidate":
                accent = flagged_accent
                thickness = 3 if interaction_flagged else 2
                label = f"CANDIDATE {person['id']}"
            else:
                accent = bystander_accent
                thickness = 1
                label = f"BG {person['id']}"

            cv2.rectangle(preview, (x1, y1), (x2, y2), accent, thickness)
            cv2.putText(
                preview,
                label,
                (x1, max(20, y1 - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                accent,
                1,
                cv2.LINE_AA,
            )
            for point in person["keypoints"]:
                x, y = [int(value) for value in point]
                dot_color = (255, 255, 255) if role != "bystander" else (175, 175, 175)
                cv2.circle(preview, (x, y), 2 if role == "bystander" else 3, dot_color, -1)

        label = "Potential anomaly" if interaction_flagged else "Monitoring"
        cv2.putText(
            preview,
            label,
            (18, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            flagged_accent if interaction_flagged else safe_accent,
            2,
            cv2.LINE_AA,
        )
        success, encoded = cv2.imencode(".jpg", preview)
        return encoded.tobytes() if success else None


class PipelineManager:
    def __init__(self) -> None:
        self.pipeline: CareWatchPipeline | None = None

    async def start(self, source: int | str) -> dict[str, Any]:
        if self.pipeline and self.pipeline.running:
            raise RuntimeError("Pipeline already running")
        self.pipeline = CareWatchPipeline(camera_index=source)
        await self.pipeline.start()
        return self.pipeline.get_status()

    async def stop(self) -> dict[str, Any]:
        if self.pipeline:
            await self.pipeline.stop()
        return self.get_status()

    def get_status(self) -> dict[str, Any]:
        if not self.pipeline:
            return {
                "running": False,
                "uptime_seconds": 0,
                "alert_count": 0,
                "source": None,
                "people_count": 0,
                "last_heuristic_reason": "monitoring",
                "last_classifier_reason": "No concern detected.",
                "last_classifier_severity": "none",
                "last_review_latency_ms": 0,
                "estimated_detection_fps": 0.0,
                "review_in_progress": False,
                "last_snapshot_url": None,
                "last_snapshot_reason": None,
                "last_snapshot_timestamp": None,
            }
        return self.pipeline.get_status()

    def get_latest_frame(self) -> bytes | None:
        if not self.pipeline:
            return None
        return self.pipeline.get_latest_frame()
