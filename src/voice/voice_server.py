"""Standalone Exotel WebSocket server for GOLDEN family calls."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any

import httpx
import websockets

from src.config import settings
from src.voice.exotel_media_gateway import ExotelCallMetadata, parse_event
from src.voice.family_voice_session import FamilyVoiceSession
from src.voice.gemini_live_session import GeminiLiveFamilySession
from src.voice.live_bridge import LiveVoiceBridge

logger = logging.getLogger("golden.voice.server")


def _callback_headers(body: bytes) -> dict[str, str]:
    """Sign a callback when GOLDEN callback authentication is configured."""
    if not settings.VOICE_CALLBACK_SECRET:
        return {}
    timestamp = str(int(time.time()))
    nonce = hashlib.sha256(f"{timestamp}:{time.monotonic_ns()}".encode()).hexdigest()
    signed = f"{timestamp}.{nonce}.".encode() + body
    signature = hmac.new(
        settings.VOICE_CALLBACK_SECRET.encode(), signed, hashlib.sha256
    ).hexdigest()
    return {
        "X-Golden-Signature": f"sha256={signature}",
        "X-Golden-Timestamp": timestamp,
        "X-Golden-Nonce": nonce,
    }


async def _post_completion(payload: dict[str, Any]) -> None:
    """Post completion with bounded retries and exponential backoff."""
    body = json.dumps(payload).encode()
    headers = {"Content-Type": "application/json", **_callback_headers(body)}
    attempts = max(settings.CALLBACK_RETRY_ATTEMPTS, 1)
    for attempt in range(attempts):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    settings.VOICE_CALLBACK_URL,
                    content=body,
                    headers=headers,
                    timeout=15,
                )
                response.raise_for_status()
                return
        except (httpx.HTTPError, OSError) as exc:
            if attempt == attempts - 1:
                logger.error("Voice completion callback failed: %s", exc)
                return
            await asyncio.sleep(settings.CALLBACK_RETRY_BACKOFF_SECONDS * (attempt + 1))


async def _read_start_event(websocket: Any, stream_path: str = "") -> ExotelCallMetadata:
    """Read and validate the Exotel start event before opening Gemini."""
    if not stream_path:
        request = getattr(websocket, "request", None)
        stream_path = str(getattr(request, "path", "") or getattr(websocket, "path", ""))
    
    from urllib.parse import unquote
    cleaned_stream_path = unquote(stream_path).replace("\\?", "?").replace("\\", "")

    async for raw_message in websocket:
        event = parse_event(raw_message)
        if event.get("event") == "connected":
            continue
        if event.get("event") != "start":
            raise ValueError("voice stream must begin with an Exotel start event")
        metadata = ExotelCallMetadata.from_start_event(event, cleaned_stream_path)
        logger.info("Received Exotel start event for stream path: %s", cleaned_stream_path)
        logger.info("Exotel raw start event: %s", event)
        logger.info("Parsed call metadata: case_id=%s, thread_id=%s, call_id=%s", metadata.case_id, metadata.thread_id, metadata.call_id)
        metadata.validate()
        return metadata
    raise ValueError("voice stream closed before the Exotel start event")


async def handle_connection(websocket: Any) -> None:
    """Handle one Exotel stream and send its structured result to GOLDEN."""
    started_at = time.monotonic()
    metadata: ExotelCallMetadata | None = None
    family_session: FamilyVoiceSession | None = None
    call_status = "FAILED"
    try:
        request = getattr(websocket, "request", None)
        request_path = str(getattr(request, "path", "") or getattr(websocket, "path", ""))
        
        # Tolerate URL-encoded backslashes (%5C) or trailing slashes from Exotel
        from urllib.parse import unquote
        unquoted = unquote(request_path)
        base_path = unquoted.split("?", 1)[0].replace("\\", "").rstrip("/") or "/"
        expected_path = settings.VOICE_SERVER_PATH.strip().rstrip("/\\").rstrip("/") or "/"
        if base_path not in (expected_path, "/ws", "/"):
            raise ValueError(f"unexpected voice WebSocket path: {request_path}")
        
        cleaned_stream_path = unquoted.replace("\\?", "?").replace("\\", "")
        metadata = await _read_start_event(websocket, cleaned_stream_path)
        voice_session = GeminiLiveFamilySession(settings.GEMINI_LIVE_MODEL)
        async with voice_session.connect() as gemini_session:
            bridge = LiveVoiceBridge()
            family_session = await asyncio.wait_for(
                bridge.run(websocket, metadata, gemini_session, voice_session),
                timeout=settings.VOICE_CALL_TIMEOUT_SECONDS,
            )
        call_status = "COMPLETED"
    except (asyncio.TimeoutError, ValueError, RuntimeError, websockets.exceptions.ConnectionClosed) as exc:
        logger.warning("Voice stream ended: %s", exc, exc_info=True)
    finally:
        if metadata:
            session = family_session or FamilyVoiceSession(metadata)
            payload = session.callback_fields(
                call_status,
                round(time.monotonic() - started_at),
            )
            payload["completed_at"] = datetime.now(timezone.utc).isoformat()
            await _post_completion(payload)


async def serve() -> None:
    """Run the configured GOLDEN voice WebSocket server."""
    async with websockets.serve(
        handle_connection,
        settings.VOICE_SERVER_HOST,
        settings.VOICE_SERVER_PORT,
    ):
        logger.info(
            "GOLDEN voice server listening on ws://%s:%s%s",
            settings.VOICE_SERVER_HOST,
            settings.VOICE_SERVER_PORT,
            settings.VOICE_SERVER_PATH,
        )
        await asyncio.Future()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(serve())


if __name__ == "__main__":
    main()