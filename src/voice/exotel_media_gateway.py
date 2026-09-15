"""Provider transport primitives for Exotel bidirectional media streams."""

from __future__ import annotations

import base64
import binascii
import json
import logging
import uuid
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlparse

from src.voice.audio_bridge import AudioBridge

logger = logging.getLogger("golden.voice.gateway")


@dataclass(frozen=True)
class ExotelCallMetadata:
    """Identifiers carried from GOLDEN through Exotel and back to the callback."""

    case_id: str
    thread_id: str
    call_id: str
    recipient_phone: str | None = None
    stream_sid: str | None = None

    @classmethod
    def from_start_event(
        cls,
        event: dict[str, Any],
        stream_path: str = "",
    ) -> "ExotelCallMetadata":
        # ── Log the complete raw event so we can see exactly what Exotel sends ──
        logger.info("[EXOTEL RAW] stream_path=%r  event=%s", stream_path, json.dumps(event))

        start = event.get("start", {})
        stream_sid = str(
            event.get("stream_sid")
            or event.get("streamSid")
            or start.get("stream_sid")
            or start.get("streamSid")
            or ""
        ) or None

        # Exotel may put custom params under either key
        parameters: dict = (
            start.get("customParameters")
            or start.get("custom_parameters")
            or event.get("customParameters")
            or event.get("custom_parameters")
            or {}
        )

        # Parse query string from the WebSocket URL path
        parsed_url = urlparse(stream_path)
        # Handle full wss:// URLs or bare paths alike
        query = parse_qs(parsed_url.query)
        logger.info("[EXOTEL] parsed query params: %s", dict(query))
        logger.info("[EXOTEL] customParameters: %s", parameters)

        def first_value(name: str) -> str:
            values = query.get(name, [])
            return values[0] if values else ""

        # ── Extract call_id (Exotel CallSid / StreamSid) ──────────────────────
        # NOTE: Exotel uses snake_case (call_sid, stream_sid, custom_parameters)
        call_id = str(
            start.get("call_sid")      # Exotel snake_case (confirmed from live event)
            or start.get("callSid")    # camelCase variants
            or start.get("CallSid")
            or start.get("call_id")
            or start.get("sid")
            or start.get("stream_sid") # Exotel snake_case stream id
            or start.get("streamSid")
            or event.get("call_sid")   # also check top-level event
            or event.get("callSid")
            or event.get("CallSid")
            or event.get("stream_sid") # Exotel sends stream_sid at top level too
            or event.get("streamSid")
            or parameters.get("call_id")
            or first_value("call_id")
            or ""
        )

        # ── Extract case_id and thread_id ────────────────────────────────────
        case_id = str(
            parameters.get("case_id")
            or first_value("case_id")
            or ""
        )
        thread_id = str(
            parameters.get("thread_id")
            or first_value("thread_id")
            or ""
        )
        recipient_phone = parameters.get("recipient_phone") or first_value("recipient_phone") or None

        # ── Fallback 1: active call registry by call_id ──────────────────────
        if not case_id or not thread_id:
            from src.voice.active_calls import lookup_active_call
            active_info = lookup_active_call(call_id) if call_id else None
            if not active_info:
                # Try the most-recently registered call (latest entry)
                active_info = lookup_active_call(None)
            if active_info:
                logger.info("[EXOTEL] recovering identifiers from active_calls: %s", active_info)
                case_id = case_id or active_info.get("case_id", "")
                thread_id = thread_id or active_info.get("thread_id", "")
                call_id = call_id or active_info.get("call_id", "")
                recipient_phone = recipient_phone or active_info.get("recipient_phone")

        # ── Fallback 2: synthesize missing identifiers rather than hard-fail ─
        if case_id and not thread_id:
            thread_id = f"thread-{case_id}"
        if not call_id:
            # Synthesize a traceable ID so the session can continue
            call_id = f"SYNTH-{uuid.uuid4().hex[:12]}"
            logger.warning(
                "[EXOTEL] call_id not found in start event — synthesized: %s", call_id
            )
        if not case_id:
            short_id = call_id.replace("-", "")[:8]
            case_id = f"CASE-{short_id}"
            thread_id = thread_id or f"thread-{case_id}"

        logger.info(
            "[EXOTEL] resolved metadata: case_id=%s  thread_id=%s  call_id=%s",
            case_id, thread_id, call_id,
        )
        return cls(
            case_id=case_id,
            thread_id=thread_id,
            call_id=call_id,
            recipient_phone=recipient_phone,
            stream_sid=stream_sid,
        )

    def validate(self) -> None:
        """Reject streams that are completely unresolvable to a GOLDEN case."""
        # call_id may be synthesized; we only hard-fail if case_id and thread_id
        # are both missing (means we have absolutely no context to work with).
        if not self.case_id or not self.thread_id:
            raise ValueError(
                f"Exotel stream could not be bound to a GOLDEN case "
                f"(case_id={self.case_id!r}, thread_id={self.thread_id!r}). "
                "Check EXOTEL_STREAM_URL query params and the active_calls registry."
            )


@dataclass(frozen=True)
class ExotelMediaFrame:
    """Decoded 8 kHz PCM media from Exotel."""

    pcm_8khz: bytes


def parse_event(raw_message: str | bytes) -> dict[str, Any]:
    """Decode one JSON Exotel WebSocket event."""
    if isinstance(raw_message, bytes):
        raw_message = raw_message.decode("utf-8")
    event = json.loads(raw_message)
    if not isinstance(event, dict):
        raise ValueError("Exotel WebSocket event must be a JSON object")
    return event


def decode_media_frame(event: dict[str, Any]) -> ExotelMediaFrame | None:
    """Decode a media event and ignore non-media events."""
    if event.get("event") != "media":
        return None
    payload = event.get("media", {}).get("payload")
    if not payload:
        return None
    try:
        return ExotelMediaFrame(base64.b64decode(payload, validate=True))
    except (binascii.Error, ValueError) as exc:
        raise ValueError("Exotel media payload is not valid base64") from exc


class ExotelMediaGateway:
    """Translate Exotel 8 kHz PCM frames to and from realtime sessions."""

    @staticmethod
    def to_realtime_audio(frame: ExotelMediaFrame, *, low_latency: bool = True) -> bytes:
        if low_latency:
            return AudioBridge.fast_resample_8k_to_16k(frame.pcm_8khz)
        return AudioBridge.resample_8k_to_16k(frame.pcm_8khz)

    @staticmethod
    def to_exotel_message(
        pcm_audio: bytes,
        source_rate: int = 24000,
        stream_sid: str | None = None,
    ) -> str:
        pcm_8khz = AudioBridge.resample_to_8k(pcm_audio, source_rate=source_rate)
        message: dict[str, Any] = {
            "event": "media",
            "media": {"payload": base64.b64encode(pcm_8khz).decode("ascii")},
        }
        if stream_sid:
            message["stream_sid"] = stream_sid
        return json.dumps(message)