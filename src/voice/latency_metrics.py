"""Low-overhead timing metrics for realtime voice calls.

Two views are captured:

* call milestones (connection, first inbound audio, first playout, completion)
* per-turn segments, because the number a caller actually experiences is
  "I stopped talking -> I heard the agent", measured on every turn.

Existing field and method names are preserved so the bridge, tests and the
completion payload keep working.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("golden.voice.latency")

MAX_TURNS = 200
MAX_SAMPLES = 400


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((pct / 100.0) * (len(ordered) - 1)))))
    return round(ordered[index], 2)


@dataclass
class SampleStats:
    """Bounded p50/p95 accumulator for one measured quantity."""

    values: list[float] = field(default_factory=list)

    def add(self, value: float | None) -> None:
        if value is None:
            return
        self.values.append(round(value, 2))
        if len(self.values) > MAX_SAMPLES:
            del self.values[: len(self.values) - MAX_SAMPLES]

    def summary(self) -> dict[str, Any]:
        return {
            "count": len(self.values),
            "p50_ms": _percentile(self.values, 50),
            "p95_ms": _percentile(self.values, 95),
            "max_ms": round(max(self.values), 2) if self.values else None,
        }


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
    first_speech_after_greeting_at: float | None = None
    first_gemini_input_at: float | None = None
    first_gemini_audio_at: float | None = None
    first_exotel_audio_at: float | None = None
    first_gemini_audio_after_caller_at: float | None = None
    first_exotel_audio_after_caller_at: float | None = None
    awaiting_caller_response: bool = False
    # ── Call lifecycle milestones ───────────────────────────────────────────
    call_connected_at: float | None = None
    gemini_connected_at: float | None = None
    call_completed_at: float | None = None
    # ── Current (in-flight) turn ────────────────────────────────────────────
    last_inbound_audio_at: float | None = None
    turn_start_at: float | None = None
    turn_caller_end_at: float | None = None
    turn_gemini_input_at: float | None = None
    turn_gemini_response_at: float | None = None
    turn_gemini_audio_at: float | None = None
    turn_exotel_audio_at: float | None = None
    # ── History / aggregates ────────────────────────────────────────────────
    turns: list[dict[str, Any]] = field(default_factory=list)
    turn_durations: dict[str, SampleStats] = field(default_factory=dict)
    inbound_frame_gaps: SampleStats = field(default_factory=SampleStats)
    outbound_chunk_gaps: SampleStats = field(default_factory=SampleStats)
    gemini_send_latency: SampleStats = field(default_factory=SampleStats)
    exotel_send_latency: SampleStats = field(default_factory=SampleStats)
    tool_roundtrip: SampleStats = field(default_factory=SampleStats)
    event_loop_lag: SampleStats = field(default_factory=SampleStats)
    inbound_frame_bytes: SampleStats = field(default_factory=SampleStats)
    outbound_chunk_bytes: SampleStats = field(default_factory=SampleStats)
    inbound_rms: SampleStats = field(default_factory=SampleStats)
    reconnects: int = 0
    interruptions: int = 0
    # Whole-call peak: SampleStats only keeps the most recent window, so a caller who
    # spoke early in a long call would otherwise leave no trace of their level.
    inbound_rms_peak: float = 0.0
    last_media_gap_anchor: float | None = None
    last_gemini_audio_anchor: float | None = None

    # ── Milestone markers ───────────────────────────────────────────────────

    def mark_call_connected(self) -> None:
        self.call_connected_at = time.perf_counter()

    def mark_gemini_connected(self) -> None:
        self.gemini_connected_at = time.perf_counter()

    def mark_bridge_started(self) -> None:
        """Both realtime directions are running; used when the server owns setup."""
        self.gemini_connected_at = self.gemini_connected_at or time.perf_counter()

    def mark_call_completed(self) -> None:
        self.call_completed_at = time.perf_counter()
        self.close_turn("abandoned")

    def mark_reconnect(self) -> None:
        self.reconnects += 1

    def mark_loop_lag(self, lag_ms: float) -> None:
        self.event_loop_lag.add(lag_ms)

    def mark_interruption(self) -> None:
        self.interruptions += 1
        self.close_turn("interrupted")
        self.awaiting_caller_response = False

    def mark_media(
        self,
        *,
        is_speech: bool = False,
        frame_bytes: int = 0,
        rms: float = 0.0,
    ) -> None:
        now = time.perf_counter()
        self.media_frames_received += 1
        self.first_media_at = self.first_media_at or now
        self.inbound_frame_bytes.add(float(frame_bytes))
        # Inbound level is the only way to tell "the caller was silent" apart from
        # "their voice arrived but below our speech gate".
        self.inbound_rms.add(rms)
        self.inbound_rms_peak = max(self.inbound_rms_peak, rms)
        if self.last_media_gap_anchor is not None:
            self.inbound_frame_gaps.add((now - self.last_media_gap_anchor) * 1000)
        self.last_media_gap_anchor = now
        self.last_inbound_audio_at = now
        if is_speech:
            self.speech_frames_received += 1
            self.first_speech_at = self.first_speech_at or now
            # "Caller spoke after the greeting" is only meaningful once the greeting has
            # actually ended; speech that barged into the greeting would otherwise make
            # the reported interval negative.
            if self.greeting_completed_at is not None and self.first_speech_after_greeting_at is None:
                self.first_speech_after_greeting_at = now
            if self.turn_start_at is not None and self.turn_gemini_audio_at is None:
                # The caller's turn ends at their last *audible* frame. The telephony leg
                # keeps delivering silence frames afterwards, so anchoring on any inbound
                # frame would report an end-of-speech that is really just "reply arrived".
                self.turn_caller_end_at = now

    def mark_gemini_input(self, *, send_ms: float | None = None) -> None:
        now = time.perf_counter()
        self.audio_frames_sent_to_gemini += 1
        self.first_gemini_input_at = self.first_gemini_input_at or now
        # A forwarded frame is by definition caller audio we received, so the handover
        # can never predate it. Without this backfill a quiet first frame (breath, room
        # tone) makes caller_audio_to_gemini_ms report a negative interval.
        self.first_speech_at = self.first_speech_at or now
        self.gemini_send_latency.add(send_ms)
        if self.turn_start_at is None:
            self.turn_start_at = now
            self.turn_gemini_input_at = now
            self.turn_caller_end_at = self.turn_caller_end_at or self.last_inbound_audio_at
        self.awaiting_caller_response = True

    def mark_gemini_response(self) -> None:
        if self.turn_start_at is not None and self.turn_gemini_response_at is None:
            self.turn_gemini_response_at = time.perf_counter()

    def mark_gemini_audio(self, *, chunk_bytes: int = 0) -> None:
        now = time.perf_counter()
        self.audio_frames_received_from_gemini += 1
        self.first_gemini_audio_at = self.first_gemini_audio_at or now
        self.outbound_chunk_bytes.add(float(chunk_bytes))
        if self.last_gemini_audio_anchor is not None:
            self.outbound_chunk_gaps.add((now - self.last_gemini_audio_anchor) * 1000)
        self.last_gemini_audio_anchor = now
        if self.awaiting_caller_response:
            self.first_gemini_audio_after_caller_at = now
        if self.turn_start_at is not None and self.turn_gemini_audio_at is None:
            self.turn_gemini_audio_at = now

    def mark_tool_roundtrip(self, ms: float | None) -> None:
        """A tool call pauses the model turn; this is the cost we add there."""
        self.tool_roundtrip.add(ms)

    def mark_exotel_audio(self, *, send_ms: float | None = None) -> None:
        now = time.perf_counter()
        self.audio_frames_sent_to_exotel += 1
        self.first_exotel_audio_at = self.first_exotel_audio_at or now
        self.exotel_send_latency.add(send_ms)
        if self.awaiting_caller_response:
            self.first_exotel_audio_after_caller_at = now
            self.awaiting_caller_response = False
        if self.turn_start_at is not None and self.turn_exotel_audio_at is None:
            self.turn_exotel_audio_at = now

    def mark_greeting_complete(self) -> None:
        self.greeting_completed_at = time.perf_counter()

    # ── Turn accounting ─────────────────────────────────────────────────────

    def close_turn(self, outcome: str) -> dict[str, Any] | None:
        """Freeze the in-flight turn into a record and add it to the aggregates."""
        if self.turn_start_at is None:
            return None
        record = {
            "turn": len(self.turns) + 1,
            "outcome": outcome,
            "caller_end_to_playout_ms": self._elapsed_ms(
                self.turn_caller_end_at, self.turn_exotel_audio_at
            ),
            "caller_end_to_gemini_audio_ms": self._elapsed_ms(
                self.turn_caller_end_at, self.turn_gemini_audio_at
            ),
            "input_to_gemini_response_ms": self._elapsed_ms(
                self.turn_gemini_input_at, self.turn_gemini_response_at
            ),
            "gemini_response_to_audio_ms": self._elapsed_ms(
                self.turn_gemini_response_at, self.turn_gemini_audio_at
            ),
            "gemini_audio_to_playout_ms": self._elapsed_ms(
                self.turn_gemini_audio_at, self.turn_exotel_audio_at
            ),
        }
        for name, value in record.items():
            if name.endswith("_ms") and value is not None:
                self.turn_durations.setdefault(name, SampleStats()).add(value)
        self.turns.append(record)
        if len(self.turns) > MAX_TURNS:
            del self.turns[: len(self.turns) - MAX_TURNS]
        self.turn_start_at = None
        self.turn_caller_end_at = None
        self.turn_gemini_input_at = None
        self.turn_gemini_response_at = None
        self.turn_gemini_audio_at = None
        self.turn_exotel_audio_at = None
        return record

    @staticmethod
    def _elapsed_ms(start: float | None, end: float | None) -> float | None:
        if start is None or end is None:
            return None
        return round((end - start) * 1000, 2)

    def snapshot(self) -> dict[str, object]:
        """Return serializable milestones and derived latency segments."""
        return {
            "media_frames_received": self.media_frames_received,
            "inbound_rms_peak": round(self.inbound_rms_peak, 1),
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
                self.greeting_completed_at, self.first_speech_after_greeting_at
            ),
            "lifecycle_ms": {
                "gemini_connect": self._elapsed_ms(
                    self.call_connected_at, self.gemini_connected_at
                ),
                "connect_to_first_inbound_audio": self._elapsed_ms(
                    self.call_connected_at, self.first_media_at
                ),
                "connect_to_first_gemini_audio": self._elapsed_ms(
                    self.call_connected_at, self.first_gemini_audio_at
                ),
                "connect_to_first_playout": self._elapsed_ms(
                    self.call_connected_at, self.first_exotel_audio_at
                ),
                "call_duration": self._elapsed_ms(
                    self.call_connected_at, self.call_completed_at
                ),
            },
            "counters": {
                "reconnects": self.reconnects,
                "interruptions": self.interruptions,
                "turns_recorded": len(self.turns),
            },
            "transport": {
                "inbound_frame_gap": self.inbound_frame_gaps.summary(),
                "inbound_frame_bytes": self.inbound_frame_bytes.summary(),
                "inbound_rms": self.inbound_rms.summary(),
                "gemini_send": self.gemini_send_latency.summary(),
                "outbound_chunk_gap": self.outbound_chunk_gaps.summary(),
                "outbound_chunk_bytes": self.outbound_chunk_bytes.summary(),
                "exotel_send": self.exotel_send_latency.summary(),
                "tool_roundtrip": self.tool_roundtrip.summary(),
                "event_loop_lag": self.event_loop_lag.summary(),
            },
            "turn_latency": {name: stats.summary() for name, stats in self.turn_durations.items()},
            "turns": self.turns[-20:],
        }

    def log_snapshot(self, *, call_id: str, stage: str) -> None:
        logger.info(
            "VOICE_LATENCY %s",
            json.dumps({"call_id": call_id, "stage": stage, "metrics": self.snapshot()}),
        )

    def log_turn(self, *, call_id: str, record: dict[str, Any]) -> None:
        logger.info("VOICE_TURN %s", json.dumps({"call_id": call_id, **record}))
