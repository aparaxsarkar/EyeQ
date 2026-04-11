from __future__ import annotations

import asyncio
import base64
import json
import time
from io import BytesIO
from typing import Any
from urllib.parse import urljoin
from urllib import error, request

import cv2
import numpy as np

from config import get_settings


DEFAULT_RESULT = {
    "flagged": False,
    "severity": "none",
    "reason": "error",
    "suggested_action": "none",
}

SYSTEM_PROMPT = (
    "You are an AI safety monitor for vulnerable care environments. Analyze the image or short ordered image sequence "
    "and return ONLY valid JSON, no other text. Format: {flagged: boolean, severity: "
    "none|low|medium|high, reason: one sentence, suggested_action: string}. Flag HIGH "
    "if: physical striking, person on floor with no caretaker, caretaker in aggressive "
    "posture over patient. Flag MEDIUM if: caretaker ignoring visible distress, rough "
    "handling during transfer, patient appears fearful. Flag LOW if: unusual patient "
    "stillness, caretaker absent, patient in uncomfortable position. Do NOT flag: "
    "bathing, feeding, physical therapy, normal transfers, playful interaction. When "
    "uncertain return flagged: false. Minimize false positives."
)


class SceneClassifier:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.last_invoked_at = 0.0
        self.last_result = DEFAULT_RESULT.copy()
        self.google_model = None
        if self.settings.gemini_api_key:
            import google.generativeai as genai

            genai.configure(api_key=self.settings.gemini_api_key)
            model_kwargs = {"model_name": self.settings.google_api_model}
            if not self.settings.google_api_model.startswith("gemma-"):
                model_kwargs["system_instruction"] = SYSTEM_PROMPT
            self.google_model = genai.GenerativeModel(**model_kwargs)

    async def classify_scene(
        self,
        frame: np.ndarray,
        ignore_cooldown: bool = False,
        context_hint: str = "",
        prefer_local: bool = False,
    ) -> dict[str, Any]:
        return await self.classify_burst(
            [frame],
            context_hint=context_hint,
            prefer_local=prefer_local,
            ignore_cooldown=ignore_cooldown,
        )

    async def classify_burst(
        self,
        frames: list[np.ndarray],
        context_hint: str = "",
        prefer_local: bool = False,
        ignore_cooldown: bool = False,
    ) -> dict[str, Any]:
        now = time.time()
        if not ignore_cooldown and now - self.last_invoked_at < self.settings.gemini_cooldown_seconds:
            return self.last_result

        self.last_invoked_at = now
        if not self.settings.ollama_model and not self.settings.openrouter_api_key and self.google_model is None:
            self.last_result = DEFAULT_RESULT.copy()
            return self.last_result

        try:
            frames_for_review = frames
            if prefer_local:
                frames_for_review = [
                    await asyncio.to_thread(
                        self._downscale_frame,
                        frame,
                        self.settings.live_review_max_side_px,
                    )
                    for frame in frames
                ]
            encoded_frames = [
                await asyncio.to_thread(self._frame_to_base64_jpeg, frame)
                for frame in frames_for_review
            ]
            raw_text = await self._classify_with_provider(
                encoded_frames,
                context_hint=context_hint,
                prefer_local=prefer_local,
            )
        except Exception:
            self.last_result = DEFAULT_RESULT.copy()
            return self.last_result

        try:
            parsed = self._normalize_result(json.loads(self._extract_json(raw_text)))
            self.last_result = parsed
            return parsed
        except Exception:
            self.last_result = DEFAULT_RESULT.copy()
            return self.last_result

    async def _classify_with_provider(
        self,
        encoded_frames: list[str],
        context_hint: str = "",
        prefer_local: bool = False,
    ) -> str:
        provider_errors: list[Exception] = []
        provider_chain = self._provider_chain(prefer_local=prefer_local)
        for provider_name in provider_chain:
            try:
                if provider_name == "ollama":
                    model_name = self.settings.live_ollama_model if prefer_local else self.settings.ollama_model
                    return await asyncio.wait_for(
                        asyncio.to_thread(self._call_ollama, encoded_frames, context_hint, model_name),
                        timeout=self.settings.provider_timeout_seconds,
                    )
                if provider_name == "google" and self.google_model is not None:
                    return await asyncio.wait_for(
                        asyncio.to_thread(self._call_google_api, encoded_frames, context_hint),
                        timeout=self.settings.provider_timeout_seconds,
                    )
                if provider_name == "openrouter" and self.settings.openrouter_api_key:
                    return await asyncio.wait_for(
                        asyncio.to_thread(self._call_openrouter, encoded_frames, context_hint),
                        timeout=self.settings.provider_timeout_seconds,
                    )
            except Exception as exc:
                provider_errors.append(exc)

        if provider_errors:
            raise provider_errors[-1]
        raise RuntimeError("No vision provider configured")

    def _provider_chain(self, prefer_local: bool = False) -> list[str]:
        if prefer_local:
            return ["ollama", "google", "openrouter"]
        return ["google", "ollama", "openrouter"]

    def _call_ollama(self, encoded_frames: list[str], context_hint: str = "", model_name: str = "") -> str:
        analysis_request = self._analysis_request(context_hint=context_hint, frame_count=len(encoded_frames))
        resolved_model = model_name or self.settings.ollama_model
        if not resolved_model:
            raise RuntimeError("No Ollama model configured")
        payload = {
            "model": resolved_model,
            "stream": False,
            "format": "json",
            "messages": [
                {
                    "role": "user",
                    "content": f"{SYSTEM_PROMPT}\n\n{analysis_request}",
                    "images": encoded_frames,
                }
            ],
            "options": {"temperature": 0},
        }
        req = request.Request(
            urljoin(self.settings.ollama_base_url, "/api/chat"),
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self.settings.ollama_timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"Ollama request failed: {exc.code} {detail}") from exc

        return str(payload.get("message", {}).get("content", "") or "{}")

    def _call_openrouter(self, encoded_frames: list[str], context_hint: str = "") -> str:
        analysis_request = self._analysis_request(context_hint=context_hint, frame_count=len(encoded_frames))
        content: list[dict[str, Any]] = [
            {
                "type": "text",
                "text": (
                    f"{SYSTEM_PROMPT}\n\n"
                    f"{analysis_request}"
                ),
            }
        ]
        content.extend(
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{encoded_frame}",
                    "detail": "low" if len(encoded_frames) > 1 else "auto",
                },
            }
            for encoded_frame in encoded_frames
        )
        payload = {
            "model": self.settings.openrouter_model,
            "messages": [
                {
                    "role": "user",
                    "content": content,
                },
            ],
            "temperature": 0,
            "max_tokens": 180,
            "response_format": {"type": "json_object"},
        }
        req = request.Request(
            "https://openrouter.ai/api/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.settings.openrouter_api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": self.settings.openrouter_site_url,
                "X-OpenRouter-Title": self.settings.openrouter_app_name,
            },
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"OpenRouter request failed: {exc.code} {detail}") from exc

        choices = payload.get("choices", [])
        if not choices:
            raise RuntimeError("OpenRouter response did not include choices")
        content = choices[0].get("message", {}).get("content", "")
        if isinstance(content, list):
            content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
        return str(content or "{}")

    def _call_google_api(self, encoded_frames: list[str], context_hint: str = "") -> str:
        assert self.google_model is not None
        analysis_request = self._analysis_request(context_hint=context_hint, frame_count=len(encoded_frames))
        is_gemma_model = self.settings.google_api_model.startswith("gemma-")
        if is_gemma_model:
            analysis_request = f"{SYSTEM_PROMPT}\n\n{analysis_request}"
        generation_config = {"temperature": 0.1}
        if not is_gemma_model:
            generation_config["response_mime_type"] = "application/json"
        parts: list[dict[str, Any]] = [{"text": analysis_request}]
        parts.extend(
            {
                "inline_data": {
                    "mime_type": "image/jpeg",
                    "data": encoded_frame,
                }
            }
            for encoded_frame in encoded_frames
        )
        response = self.google_model.generate_content(
            contents=[
                {
                    "role": "user",
                    "parts": parts,
                }
            ],
            generation_config=generation_config,
        )
        return getattr(response, "text", "") or "{}"

    @staticmethod
    def _frame_to_base64_jpeg(frame: np.ndarray) -> str:
        success, buffer = cv2.imencode(".jpg", frame)
        if not success:
            raise ValueError("Unable to encode frame to JPEG")
        return base64.b64encode(BytesIO(buffer.tobytes()).getvalue()).decode("utf-8")

    @staticmethod
    def _downscale_frame(frame: np.ndarray, max_side_px: int) -> np.ndarray:
        if max_side_px <= 0:
            return frame
        height, width = frame.shape[:2]
        longest_side = max(height, width)
        if longest_side <= max_side_px:
            return frame
        scale = max_side_px / longest_side
        resized_width = max(1, int(width * scale))
        resized_height = max(1, int(height * scale))
        return cv2.resize(frame, (resized_width, resized_height), interpolation=cv2.INTER_AREA)

    @staticmethod
    def _analysis_request(context_hint: str, frame_count: int) -> str:
        if frame_count <= 1:
            request_text = "Analyze this care environment scene and respond with JSON only."
        else:
            request_text = (
                "Analyze this short ordered image sequence from a recent live monitoring window. "
                "Treat the images as consecutive moments from the same incident and decide whether the sequence "
                "shows suspicious or abusive activity. Respond with JSON only."
            )
        if context_hint:
            request_text += f" Detection context: {context_hint}."
        return request_text

    @staticmethod
    def _extract_json(raw_text: str) -> str:
        text = raw_text.strip()
        if text.startswith("```"):
            text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end < start:
            raise ValueError("Model response did not contain JSON")
        return text[start : end + 1]

    @staticmethod
    def _normalize_result(payload: dict[str, Any]) -> dict[str, Any]:
        severity = str(payload.get("severity", "none")).lower()
        if severity not in {"none", "low", "medium", "high"}:
            severity = "none"
        return {
            "flagged": bool(payload.get("flagged", False)),
            "severity": severity,
            "reason": str(payload.get("reason", "") or "No issue detected."),
            "suggested_action": str(payload.get("suggested_action", "") or "none"),
        }

    @staticmethod
    def _severity_rank(severity: str) -> int:
        return {"none": 0, "low": 1, "medium": 2, "high": 3}.get(severity, 0)


_default_classifier: SceneClassifier | None = None


def get_default_classifier() -> SceneClassifier:
    global _default_classifier
    if _default_classifier is None:
        _default_classifier = SceneClassifier()
    return _default_classifier


async def classify_scene(
    frame: np.ndarray,
    ignore_cooldown: bool = False,
    context_hint: str = "",
) -> dict[str, Any]:
    return await get_default_classifier().classify_scene(
        frame,
        ignore_cooldown=ignore_cooldown,
        context_hint=context_hint,
    )
