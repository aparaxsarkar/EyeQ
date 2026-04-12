from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _env_int(name: str, default: int) -> int:
    raw_value = os.getenv(name, "").strip()
    return int(raw_value) if raw_value else default


def _env_float(name: str, default: float) -> float:
    raw_value = os.getenv(name, "").strip()
    return float(raw_value) if raw_value else default


@dataclass(slots=True)
class Settings:
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    google_api_model: str = os.getenv("GOOGLE_API_MODEL", "") or "gemma-3-27b-it"
    openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", "")
    openrouter_model: str = os.getenv("OPENROUTER_MODEL", "") or "google/gemma-3-12b-it:free"
    openrouter_site_url: str = os.getenv("OPENROUTER_SITE_URL", "http://localhost:8000")
    openrouter_app_name: str = os.getenv("OPENROUTER_APP_NAME", "EyeQ")
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "")
    live_ollama_model: str = os.getenv("LIVE_OLLAMA_MODEL", "") or os.getenv("OLLAMA_MODEL", "")
    live_review_provider: str = os.getenv("LIVE_REVIEW_PROVIDER", "api").strip().lower() or "api"
    twilio_account_sid: str = os.getenv("TWILIO_ACCOUNT_SID", "")
    twilio_auth_token: str = os.getenv("TWILIO_AUTH_TOKEN", "")
    twilio_phone: str = os.getenv("TWILIO_PHONE", "")
    guardian_phone: str = os.getenv("GUARDIAN_PHONE", "")
    public_api_base_url: str = os.getenv("PUBLIC_API_BASE_URL", "http://localhost:8000")
    ios_bundle_id: str = os.getenv("IOS_BUNDLE_ID", "Hades.EyeQ-IOS")
    apns_key_id: str = os.getenv("APNS_KEY_ID", "")
    apns_team_id: str = os.getenv("APNS_TEAM_ID", "")
    apns_auth_key_path: str = os.getenv("APNS_AUTH_KEY_PATH", "")
    apns_use_sandbox: bool = os.getenv("APNS_USE_SANDBOX", "true").strip().lower() != "false"
    proximity_threshold_px: int = _env_int("PROXIMITY_THRESHOLD_PX", 150)
    keypoint_velocity_threshold: int = _env_int("KEYPOINT_VELOCITY_THRESHOLD", 25)
    neglect_timeout_seconds: int = _env_int("NEGLECT_TIMEOUT_SECONDS", 1800)
    gemini_cooldown_seconds: int = _env_int("GEMINI_COOLDOWN_SECONDS", 10)
    live_detection_stride: int = _env_int("LIVE_DETECTION_STRIDE", 2)
    live_capture_width: int = _env_int("LIVE_CAPTURE_WIDTH", 960)
    live_capture_height: int = _env_int("LIVE_CAPTURE_HEIGHT", 540)
    review_burst_frames: int = _env_int("REVIEW_BURST_FRAMES", 2)
    review_burst_spacing_frames: int = _env_int("REVIEW_BURST_SPACING_FRAMES", 4)
    live_review_window_seconds: int = _env_int("LIVE_REVIEW_WINDOW_SECONDS", 5)
    live_review_sequence_frames: int = _env_int("LIVE_REVIEW_SEQUENCE_FRAMES", 4)
    live_review_max_side_px: int = _env_int("LIVE_REVIEW_MAX_SIDE_PX", 640)
    detection_confidence_threshold: float = _env_float("DETECTION_CONFIDENCE_THRESHOLD", 0.45)
    strike_contact_threshold_px: int = _env_int("STRIKE_CONTACT_THRESHOLD_PX", 120)
    strike_velocity_threshold: int = _env_int("STRIKE_VELOCITY_THRESHOLD", 35)
    strike_approach_delta_px: int = _env_int("STRIKE_APPROACH_DELTA_PX", 18)
    rapid_motion_joint_count_threshold: int = _env_int("RAPID_MOTION_JOINT_COUNT_THRESHOLD", 2)
    interaction_min_bbox_height_px: int = _env_int("INTERACTION_MIN_BBOX_HEIGHT_PX", 110)
    interaction_min_bbox_area_px: int = _env_int("INTERACTION_MIN_BBOX_AREA_PX", 6500)
    interaction_max_area_ratio: int = _env_int("INTERACTION_MAX_AREA_RATIO", 5)
    interaction_min_vertical_overlap_px: int = _env_int("INTERACTION_MIN_VERTICAL_OVERLAP_PX", 60)
    interaction_min_relative_area_percent: int = _env_int("INTERACTION_MIN_RELATIVE_AREA_PERCENT", 35)
    interaction_top_person_count: int = _env_int("INTERACTION_TOP_PERSON_COUNT", 2)
    max_people_for_strike_force_flag: int = _env_int("MAX_PEOPLE_FOR_STRIKE_FORCE_FLAG", 2)
    live_event_memory_seconds: int = _env_int("LIVE_EVENT_MEMORY_SECONDS", 2)
    strike_review_hit_count: int = _env_int("STRIKE_REVIEW_HIT_COUNT", 2)
    strike_force_flag_hit_count: int = _env_int("STRIKE_FORCE_FLAG_HIT_COUNT", 3)
    rapid_motion_review_hit_count: int = _env_int("RAPID_MOTION_REVIEW_HIT_COUNT", 2)
    camera_motion_shift_threshold_px: int = _env_int("CAMERA_MOTION_SHIFT_THRESHOLD_PX", 4)
    motion_intrusion_area_px: int = _env_int("MOTION_INTRUSION_AREA_PX", 1800)
    motion_intrusion_padding_px: int = _env_int("MOTION_INTRUSION_PADDING_PX", 36)
    motion_intrusion_threshold: int = _env_int("MOTION_INTRUSION_THRESHOLD", 32)
    ollama_timeout_seconds: int = _env_int("OLLAMA_TIMEOUT_SECONDS", 6)
    provider_timeout_seconds: int = _env_int("PROVIDER_TIMEOUT_SECONDS", 8)
    review_timeout_seconds: int = _env_int("REVIEW_TIMEOUT_SECONDS", 10)
    db_path: Path = BASE_DIR / "eyeq.db"
    clips_dir: Path = BASE_DIR / "clips"
    snapshots_dir: Path = BASE_DIR / "snapshots"
    uploads_dir: Path = BASE_DIR / "uploads"
    cors_origin: str = os.getenv("CORS_ORIGIN", "http://localhost:3000")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.clips_dir.mkdir(parents=True, exist_ok=True)
    settings.snapshots_dir.mkdir(parents=True, exist_ok=True)
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    return settings
