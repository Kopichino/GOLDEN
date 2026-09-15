"""Low-overhead timing metrics for realtime voice calls."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger("golden.voice.latency")


@dataclass
class VoiceLatencyMetrics:
    """Capture first-frame and realtime milestone timings."""

    started_at: float = field(default_factory=time.perf_counter)
    media_frames_received: int = 0
    speech_frames_received: int = 0
    audio_frames_sent_to_gemini: int = 0
    audio_frames_received_from_gemini: int = 0
    audio_frames_sent_to_exotel: int = 0
    greeting_completed_at: float | None = None
    first_media_at: float | None = None
    first_speech_at: float | None = None
    first_gemini_input_at: float | None = None
    first_gemini_audio_at: float | None = None
    first_exotel_audio_at: float | None = None
    first_gemini_audio_after_caller_at: float | None = None
    first_exotel_audio_after_caller_at: float | None = None
    awaiting_caller_response: bool = False

    def mark_media(self, *, is_speech: bool) -> None:
        now = time.perf_counter()
        self.media_frames_received += 1
        self.first_media_at = self.first_media_at or now
        if is_speech:
            self.speech_frames_received += 1
            self.first_speech_at = self.first_speech_at or now

    def mark_gemini_input(self) -> None:
        now = time.perf_counter()
        self.audio_frames_sent_to_gemini += 1
        self.first_gemini_input_at = self.first_gemini_input_at or now
        self.awaiting_caller_response = True

    def mark_gemini_audio(self) -> None:
        now = time.perf_counter()
        self.audio_frames_received_from_gemini += 1
        self.first_gemini_audio_at = self.first_gemini_audio_at or now
        if self.awaiting_caller_response:
            self.first_gemini_audio_after_caller_at = now

    def mark_exotel_audio(self) -> None:
        now = time.perf_counter()
        self.audio_frames_sent_to_exotel += 1
        self.first_exotel_audio_at = self.first_exotel_audio_at or now
        if self.awaiting_caller_response:
            self.first_exotel_audio_after_caller_at = now
            self.awaiting_caller_response = False

    def mark_greeting_complete(self) -> None:
        self.greeting_completed_at = time.perf_counter()

    @staticmethod
    def _elapsed_ms(start: float | None, end: float | None) -> float | None:
        if start is None or end is None:
            return None
        return round((end - start) * 1000, 2)

    def snapshot(self) -> dict[str, object]:
        """Return serializable milestones and derived latency segments."""
        return {
            "media_frames_received": self.media_frames_received,
            "speech_frames_received": self.speech_frames_received,
            "audio_frames_sent_to_gemini": self.audio_frames_sent_to_gemini,
            "audio_frames_received_from_gemini": self.audio_frames_received_from_gemini,
            "audio_frames_sent_to_exotel": self.audio_frames_sent_to_exotel,
            "caller_audio_to_gemini_ms": self._elapsed_ms(
                self.first_speech_at, self.first_gemini_input_at
            ),
            "gemini_processing_to_audio_ms": self._elapsed_ms(
                self.first_gemini_input_at, self.first_gemini_audio_after_caller_at
            ),
            "gemini_audio_to_exotel_ms": self._elapsed_ms(
                self.first_gemini_audio_after_caller_at,
                self.first_exotel_audio_after_caller_at,
            ),
            "caller_audio_to_exotel_ms": self._elapsed_ms(
                self.first_speech_at, self.first_exotel_audio_after_caller_at
            ),
            "greeting_to_first_caller_audio_ms": self._elapsed_ms(
                self.greeting_completed_at, self.first_speech_at
            ),
        }

    def log_snapshot(self, *, call_id: str, stage: str) -> None:
        logger.info(
            "VOICE_LATENCY %s",
            json.dumps({"call_id": call_id, "stage": stage, **self.snapshot()}),
        )
