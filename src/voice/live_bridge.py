"""Bidirectional Exotel/Gemini bridge for GOLDEN family calls."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from src.voice.audio_bridge import AudioBridge
from src.voice.exotel_media_gateway import (
    ExotelCallMetadata,
    ExotelMediaGateway,
    decode_media_frame,
    parse_event,
)
from src.voice.family_voice_session import FamilyVoiceSession
from src.voice.gemini_live_session import GeminiLiveFamilySession
from src.voice.latency_metrics import VoiceLatencyMetrics

logger = logging.getLogger("golden.voice.bridge")


class LiveVoiceBridge:
    """Supervise the two realtime directions for one authenticated call."""

    def __init__(self, gateway: ExotelMediaGateway | None = None) -> None:
        self.gateway = gateway or ExotelMediaGateway()

    async def run(
        self,
        websocket: Any,
        metadata: ExotelCallMetadata,
        gemini_session: Any,
        gemini_live_session: Any = None,
    ) -> FamilyVoiceSession:
        """Relay one call until either provider closes or the call stops."""
        family_session = FamilyVoiceSession(metadata)
        stopped = asyncio.Event()
        greeting_complete = asyncio.Event()
        metrics = VoiceLatencyMetrics()
        speech_threshold = 350.0

        async def exotel_to_gemini() -> None:
            from google.genai import types

            async for raw_message in websocket:
                if stopped.is_set():
                    return
                event = parse_event(raw_message)
                if event.get("event") == "stop":
                    logger.info("Exotel sent stop event for stream %s", metadata.stream_sid)
                    stopped.set()
                    return
                frame = decode_media_frame(event)
                if frame is None:
                    continue
                is_speech = AudioBridge.pcm16_rms(frame.pcm_8khz) >= speech_threshold
                metrics.mark_media(is_speech=is_speech)
                if not is_speech and not greeting_complete.is_set():
                    continue
                if is_speech and not greeting_complete.is_set():
                    logger.info("Caller speech detected during greeting; forwarding immediately")
                await gemini_session.send_realtime_input(
                    audio=types.Blob(
                        data=self.gateway.to_realtime_audio(frame),
                        mime_type="audio/pcm;rate=16000",
                    )
                )
                metrics.mark_gemini_input()
                if metrics.audio_frames_sent_to_gemini == 1:
                    metrics.log_snapshot(call_id=metadata.call_id, stage="first_caller_audio_to_gemini")

        async def gemini_to_exotel() -> None:
            """Forward every Gemini turn; greeting completion is not shutdown."""
            live_adapter = gemini_live_session or GeminiLiveFamilySession()
            while not stopped.is_set():
                saw_turn_complete = False
                async for response in gemini_session.receive():
                    if stopped.is_set():
                        return
                    server_content = getattr(response, "server_content", None)
                    if server_content is not None:
                        if getattr(server_content, "interrupted", False):
                            await websocket.send(json.dumps({"event": "clear"}))
                            continue
                        model_turn = getattr(server_content, "model_turn", None)
                        if model_turn:
                            for part in model_turn.parts:
                                inline_data = getattr(part, "inline_data", None)
                                if inline_data and getattr(inline_data, "data", None):
                                    metrics.mark_gemini_audio()
                                    await websocket.send(
                                        self.gateway.to_exotel_message(
                                            inline_data.data,
                                            stream_sid=metadata.stream_sid,
                                        )
                                    )
                                    metrics.mark_exotel_audio()
                                    if metrics.audio_frames_sent_to_exotel == 1:
                                        metrics.log_snapshot(
                                            call_id=metadata.call_id,
                                            stage="first_gemini_audio_to_exotel",
                                        )
                        if getattr(server_content, "turn_complete", False):
                            saw_turn_complete = True
                            greeting_complete.set()
                            metrics.mark_greeting_complete()
                            metrics.log_snapshot(
                                call_id=metadata.call_id,
                                stage="turn_complete",
                            )
                    await live_adapter.handle_tool_response(
                        response, gemini_session, family_session
                    )
                if stopped.is_set():
                    return
                if not saw_turn_complete:
                    await asyncio.sleep(0.05)

        async def keepalive() -> None:
            """Prevent Gemini session idle timeout while the greeting plays."""
            from google.genai import types

            silence = bytes(16_000 * 2 // 5)
            while not stopped.is_set() and not greeting_complete.is_set():
                await asyncio.sleep(0.2)
                if stopped.is_set() or greeting_complete.is_set():
                    return
                await gemini_session.send_realtime_input(
                    audio=types.Blob(data=silence, mime_type="audio/pcm;rate=16000")
                )

        media_task = asyncio.create_task(exotel_to_gemini())
        response_task = asyncio.create_task(gemini_to_exotel())
        keepalive_task = asyncio.create_task(keepalive())
        tasks = {
            media_task,
            response_task,
        }
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        stopped.set()
        keepalive_task.cancel()
        for task in pending | {keepalive_task}:
            task.cancel()
        await asyncio.gather(*done, *pending, return_exceptions=True)
        metrics.log_snapshot(call_id=metadata.call_id, stage="bridge_end")
        return family_session