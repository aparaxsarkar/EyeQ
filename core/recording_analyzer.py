from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2

from config import get_settings
from core.classifier import SceneClassifier
from core.clip_saver import ClipSaver
from core.detector import PoseDetector
from db import log_event


@dataclass(slots=True)
class RecordingFinding:
    timestamp_seconds: float
    severity: str
    reason: str
    suggested_action: str
    clip_path: str | None
    clip_start_seconds: float
    clip_end_seconds: float
    incident_offset_seconds: float


class RecordingAnalyzer:
    PRE_INCIDENT_SECONDS = 6.0
    POST_INCIDENT_SECONDS = 8.0
    SAMPLE_EVERY_SECONDS = 3.0
    MIN_SECONDS_BETWEEN_REVIEWS = 8.0
    MAX_CLASSIFICATION_CALLS = 12
    MAX_FINDINGS = 3

    def __init__(self) -> None:
        self.settings = get_settings()

    async def analyze(self, video_path: Path) -> dict[str, Any]:
        return await asyncio.to_thread(self._analyze_sync, video_path)

    def _analyze_sync(self, video_path: Path) -> dict[str, Any]:
        capture = cv2.VideoCapture(str(video_path))
        if not capture.isOpened():
            raise RuntimeError("Unable to open uploaded recording")

        fps = int(capture.get(cv2.CAP_PROP_FPS))
        if fps <= 0 or fps > 60:
            fps = 10

        detector = PoseDetector()
        classifier = SceneClassifier()
        clip_saver = ClipSaver(fps=fps)
        prev_persons: list[dict[str, Any]] = []
        findings: list[RecordingFinding] = []
        frame_index = 0
        last_saved_second = -15.0
        last_reviewed_second = -self.MIN_SECONDS_BETWEEN_REVIEWS
        classification_calls = 0
        sample_every_frames = max(int(round(fps * self.SAMPLE_EVERY_SECONDS)), 1)

        try:
            while True:
                ok, frame = capture.read()
                if not ok or frame is None:
                    break

                frame_index += 1
                clip_saver.add_frame(frame)
                if frame_index % sample_every_frames != 0:
                    continue

                persons = detector.detect(frame)
                heuristic_flag = detector.is_interaction_flagged(persons, prev_persons)
                prev_persons = persons
                current_second = frame_index / fps
                if not heuristic_flag:
                    continue
                if current_second - last_reviewed_second < self.MIN_SECONDS_BETWEEN_REVIEWS:
                    continue
                if classification_calls >= self.MAX_CLASSIFICATION_CALLS:
                    break

                classification_calls += 1
                last_reviewed_second = current_second
                classification = asyncio.run(classifier.classify_scene(frame, ignore_cooldown=True))
                if not classification["flagged"]:
                    continue
                if current_second - last_saved_second < 15:
                    continue

                clip_start_seconds, clip_end_seconds, clip_frames = self._extract_incident_clip(
                    video_path=video_path,
                    incident_second=current_second,
                    fps=fps,
                )
                clip_path = clip_saver.save_frames(clip_frames, classification["severity"])
                last_saved_second = current_second
                finding = RecordingFinding(
                    timestamp_seconds=current_second,
                    severity=classification["severity"],
                    reason=classification["reason"],
                    suggested_action=classification["suggested_action"],
                    clip_path=clip_path,
                    clip_start_seconds=clip_start_seconds,
                    clip_end_seconds=clip_end_seconds,
                    incident_offset_seconds=current_second - clip_start_seconds,
                )
                findings.append(finding)
                if len(findings) >= self.MAX_FINDINGS:
                    break
                asyncio.run(
                    log_event(
                        self.settings.db_path,
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        flagged=True,
                        severity=finding.severity,
                        reason=f"[Recording] {finding.reason}",
                        clip_path=finding.clip_path,
                        suggested_action=finding.suggested_action,
                    )
                )
        finally:
            capture.release()

        return {
            "filename": video_path.name,
            "flagged": bool(findings),
            "finding_count": len(findings),
            "classification_calls": classification_calls,
            "findings": [
                {
                    "timestamp_seconds": round(item.timestamp_seconds, 1),
                    "severity": item.severity,
                    "reason": item.reason,
                    "suggested_action": item.suggested_action,
                    "clip_path": item.clip_path,
                    "clip_start_seconds": round(item.clip_start_seconds, 1),
                    "clip_end_seconds": round(item.clip_end_seconds, 1),
                    "incident_offset_seconds": round(item.incident_offset_seconds, 1),
                }
                for item in findings
            ],
        }

    def _extract_incident_clip(
        self,
        video_path: Path,
        incident_second: float,
        fps: int,
    ) -> tuple[float, float, list]:
        source = cv2.VideoCapture(str(video_path))
        if not source.isOpened():
            raise RuntimeError("Unable to reopen uploaded recording for clip extraction")

        total_frames = int(source.get(cv2.CAP_PROP_FRAME_COUNT))
        total_duration = total_frames / max(fps, 1) if total_frames > 0 else incident_second
        clip_start_seconds = max(0.0, incident_second - self.PRE_INCIDENT_SECONDS)
        clip_end_seconds = min(total_duration, incident_second + self.POST_INCIDENT_SECONDS)
        source.set(cv2.CAP_PROP_POS_MSEC, clip_start_seconds * 1000)

        frames = []
        try:
            while True:
                ok, frame = source.read()
                if not ok or frame is None:
                    break
                current_seconds = source.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
                frames.append(frame)
                if current_seconds >= clip_end_seconds:
                    break
        finally:
            source.release()

        if not frames:
            raise RuntimeError("Unable to extract incident clip frames")

        return clip_start_seconds, clip_end_seconds, frames
