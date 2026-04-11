from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from pathlib import Path
import shutil
import subprocess

import cv2
import numpy as np

from config import get_settings


class ClipSaver:
    def __init__(self, fps: int) -> None:
        self.settings = get_settings()
        self.fps = max(int(fps), 1)
        self.buffer: deque[np.ndarray] = deque(maxlen=30 * self.fps)

    def add_frame(self, frame: np.ndarray) -> None:
        self.buffer.append(frame.copy())

    def sample_recent_frames(self, frame_count: int = 3, spacing_frames: int | None = None) -> list[np.ndarray]:
        frames = list(self.buffer)
        if not frames:
            return []

        spacing = spacing_frames or max(self.fps // 3, 1)
        indices: list[int] = []
        cursor = len(frames) - 1
        while cursor >= 0 and len(indices) < frame_count:
            indices.append(cursor)
            cursor -= spacing
        indices.reverse()
        return [frames[index].copy() for index in indices]

    def sample_recent_window(self, window_seconds: int, frame_count: int) -> list[np.ndarray]:
        frames = list(self.buffer)
        if not frames:
            return []

        if window_seconds <= 0:
            return self.sample_recent_frames(frame_count=frame_count)

        window_frame_count = max(int(window_seconds * self.fps), 1)
        selected_frames = frames[-window_frame_count:]
        if len(selected_frames) <= frame_count:
            return [frame.copy() for frame in selected_frames]

        if frame_count <= 1:
            return [selected_frames[-1].copy()]

        last_index = len(selected_frames) - 1
        indices = sorted(
            {
                min(last_index, int(round(position * last_index / (frame_count - 1))))
                for position in range(frame_count)
            }
        )
        return [selected_frames[index].copy() for index in indices]

    def get_buffer_snapshot(self) -> list[np.ndarray]:
        return [frame.copy() for frame in self.buffer]

    def save_clip(self, reason: str, severity: str) -> str:
        if not self.buffer:
            raise ValueError("Clip buffer is empty")
        return self.save_frames([frame.copy() for frame in self.buffer], severity)

    def save_frames(self, frames: list[np.ndarray], severity: str) -> str:
        if not frames:
            raise ValueError("Clip frame set is empty")
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        relative_path = Path("clips") / f"{timestamp}_{severity}.mp4"
        absolute_path = self.settings.clips_dir / relative_path.name
        temp_path = absolute_path.with_suffix(".raw.mp4")

        first_frame = frames[0]
        height, width = first_frame.shape[:2]
        writer = cv2.VideoWriter(
            str(temp_path),
            cv2.VideoWriter_fourcc(*"mp4v"),
            self.fps,
            (width, height),
        )
        if not writer.isOpened():
            raise ValueError("Unable to open MP4 writer")

        try:
            for frame in frames:
                writer.write(frame)
        finally:
            writer.release()

        self._ensure_browser_compatible(temp_path, absolute_path)
        return str(relative_path)

    def _ensure_browser_compatible(self, source_path: Path, target_path: Path) -> None:
        ffmpeg_path = shutil.which("ffmpeg")
        if not ffmpeg_path:
            source_path.replace(target_path)
            return

        command = [
            ffmpeg_path,
            "-y",
            "-i",
            str(source_path),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(target_path),
        ]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode == 0 and target_path.exists():
            source_path.unlink(missing_ok=True)
            return

        source_path.replace(target_path)

    @staticmethod
    def ensure_playable_clip(path: Path) -> Path:
        ffprobe_path = shutil.which("ffprobe")
        ffmpeg_path = shutil.which("ffmpeg")
        if not ffprobe_path or not ffmpeg_path or not path.exists():
            return path

        probe = subprocess.run(
            [
                ffprobe_path,
                "-v",
                "error",
                "-show_entries",
                "stream=codec_name",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True,
            text=True,
        )
        codec = probe.stdout.strip().splitlines()[0] if probe.returncode == 0 and probe.stdout.strip() else ""
        if codec == "h264":
            return path

        compatible_path = path.with_name(f"{path.stem}.browser.mp4")
        if compatible_path.exists():
            return compatible_path

        result = subprocess.run(
            [
                ffmpeg_path,
                "-y",
                "-i",
                str(path),
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                str(compatible_path),
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 and compatible_path.exists():
            return compatible_path
        return path
