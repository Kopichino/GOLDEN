"""Bidirectional Exotel/Gemini bridge for GOLDEN family calls."""

from __future__ import annotations

import asyncio
import json
import logging
import time
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

# Keep the watchdog cheap: it only observes scheduling delay, never audio bytes.
LOOP_LAG_WINDOW_SECONDS = 0.05

# After the agent asks to hang up, the leg stays open until outbound audio goes
# quiet, so the closing line is never clipped; the cap bounds a stalled provider.
END_CALL_DRAIN_SECONDS = 2.0
END_CALL_MAX_WAIT_SECONDS = 20.0


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
        transcript_logger: Any = None,
        metrics: VoiceLatencyMetrics | None = None,
    ) -> FamilyVoiceSession:
        """Relay one call until either provider closes or the call stops."""
        family_session = FamilyVoiceSession(metadata)
        stopped = asyncio.Event()
        greeting_complete = asyncio.Event()
        metrics = metrics or VoiceLatencyMetrics()
        metrics.mark_bridge_started()
        speech_threshold = 350.0
        # Live transcript fragments from Gemini; flushed as complete turns.
        pending_caller: list[str] = []
        pending_agent: list[str] = []
        transcript_messages: list[dict[str, str]] = []
        # Offloaded so transcript/log writes never sit between audio chunks.
        deferred_writes: asyncio.Queue = asyncio.Queue()
        dropped_pre_greeting_frames = 0
        end_call_task: asyncio.Task | None = None

        def write_transcript_turn(caller: list[str], agent: list[str]) -> None:
            if transcript_logger is not None:
                for text in caller:
                    transcript_logger.add_transcript("CALLER", text)
                for text in agent:
                    transcript_logger.add_transcript("AGENT", text)
                completed = transcript_logger.finish_turn()
                for role, text in completed.items():
                    transcript_messages.append({"role": role, "text": text})
            else:
                for role, buffer in (("CALLER", caller), ("AGENT", agent)):
                    text = " ".join(buffer).strip()
                    if text:
                        transcript_messages.append({"role": role, "text": text})

        def flush_transcript_turns(*, inline: bool = False) -> None:
            caller, agent = pending_caller.copy(), pending_agent.copy()
            pending_caller.clear()
            pending_agent.clear()
            if not caller and not agent:
                return
            if inline:
                write_transcript_turn(caller, agent)
                return
            # Deferring keeps transcript file I/O off the turn boundary, which is
            # exactly when the caller's next audio frames are arriving.
            defer(lambda: write_transcript_turn(caller, agent))

        def defer(work: Any) -> None:
            """Queue a non-realtime side effect; the audio path never waits on it."""
            deferred_writes.put_nowait(work)

        async def finish_after_closing() -> None:
            """Release the caller once the closing words have actually played out.

            The drain is level-triggered on outbound audio: the model may still be
            speaking its closing line (or a final safety note) when it asks to hang
            up, and a fixed delay would clip it. The cap keeps a stalled provider
            from leaving the caller on an open line forever.
            """
            deadline = time.perf_counter() + END_CALL_MAX_WAIT_SECONDS
            while time.perf_counter() < deadline:
                sent_before = metrics.audio_frames_sent_to_exotel
                await asyncio.sleep(END_CALL_DRAIN_SECONDS)
                if metrics.audio_frames_sent_to_exotel == sent_before:
                    break

            # Exotel Stream has no REST terminate and no stop message: the leg drops
            # when the application closes the WebSocket, so that is the hang-up.
            try:
                await websocket.close()
            except Exception as exc:
                logger.warning("Exotel websocket close failed for %s: %s", metadata.call_id, exc)
            stopped.set()
            media_task.cancel()
            response_task.cancel()

        async def drain_writes() -> None:
            while True:
                work = await deferred_writes.get()
                if work is None:
                    return
                try:
                    await asyncio.to_thread(work)
                except Exception as exc:  # a failed log line must not kill a call
                    logger.warning("Deferred voice write failed: %s", exc)

        async def exotel_to_gemini() -> None:
            from google.genai import types

            nonlocal dropped_pre_greeting_frames

            async for raw_message in websocket:
                if stopped.is_set():
                    return
                try:
                    event = parse_event(raw_message)
                except (ValueError, json.JSONDecodeError) as exc:
                    logger.warning("Discarding malformed Exotel event: %s", exc)
                    continue
                if event.get("event") == "stop":
                    logger.info("Exotel sent stop event for stream %s", metadata.stream_sid)
                    stopped.set()
                    return
                try:
                    frame = decode_media_frame(event)
                except ValueError as exc:
                    logger.warning("Discarding unreadable Exotel media frame: %s", exc)
                    continue
                if frame is None:
                    continue
                rms = AudioBridge.pcm16_rms(frame.pcm_8khz)
                is_speech = rms >= speech_threshold
                if metrics.media_frames_received == 0:
                    logger.info(
                        "First Exotel media frame: event_keys=%s media_keys=%s bytes=%d rms=%.1f",
                        sorted(event), sorted(event.get("media") or {}),
                        len(frame.pcm_8khz), rms,
                    )
                metrics.mark_media(
                    is_speech=is_speech, frame_bytes=len(frame.pcm_8khz), rms=rms
                )
                if not is_speech and not greeting_complete.is_set():
                    dropped_pre_greeting_frames += 1
                    continue
                if is_speech and not greeting_complete.is_set():
                    logger.info("Caller speech detected during greeting; forwarding immediately")
                audio = types.Blob(
                    data=self.gateway.to_realtime_audio(frame),
                    mime_type="audio/pcm;rate=16000",
                )
                send_started = time.perf_counter()
                await gemini_session.send_realtime_input(audio=audio)
                metrics.mark_gemini_input(send_ms=(time.perf_counter() - send_started) * 1000)
                if metrics.audio_frames_sent_to_gemini == 1:
                    metrics.log_snapshot(call_id=metadata.call_id, stage="first_caller_audio_to_gemini")

        async def gemini_to_exotel() -> None:
            """Forward every Gemini turn; greeting completion is not shutdown."""
            nonlocal end_call_task
            live_adapter = gemini_live_session or GeminiLiveFamilySession()
            while not stopped.is_set():
                saw_turn_complete = False
                async for response in gemini_session.receive():
                    if stopped.is_set():
                        return
                    server_content = getattr(response, "server_content", None)
                    if server_content is not None:
                        metrics.mark_gemini_response()
                        input_fragment = getattr(getattr(server_content, "input_transcription", None), "text", None)
                        if input_fragment:
                            pending_caller.append(input_fragment)
                        output_fragment = getattr(getattr(server_content, "output_transcription", None), "text", None)
                        if output_fragment:
                            pending_agent.append(output_fragment)
                        if getattr(server_content, "interrupted", False):
                            metrics.mark_interruption()
                            await websocket.send(self.gateway.to_clear_message(metadata.stream_sid))
                            continue
                        model_turn = getattr(server_content, "model_turn", None)
                        if model_turn:
                            for part in model_turn.parts:
                                inline_data = getattr(part, "inline_data", None)
                                if inline_data and getattr(inline_data, "data", None):
                                    metrics.mark_gemini_audio(chunk_bytes=len(inline_data.data))
                                    message = self.gateway.to_exotel_message(
                                        inline_data.data,
                                        stream_sid=metadata.stream_sid,
                                    )
                                    send_started = time.perf_counter()
                                    await websocket.send(message)
                                    metrics.mark_exotel_audio(
                                        send_ms=(time.perf_counter() - send_started) * 1000,
                                    )
                                    if metrics.audio_frames_sent_to_exotel == 1:
                                        metrics.log_snapshot(
                                            call_id=metadata.call_id,
                                            stage="first_gemini_audio_to_exotel",
                                        )
                        if getattr(server_content, "turn_complete", False):
                            saw_turn_complete = True
                            greeting_complete.set()
                            flush_transcript_turns()
                            metrics.mark_greeting_complete()
                            # Only the compact per-turn line is written here; the full
                            # snapshot is serialized once at call end. A json.dumps of
                            # the whole metric set on the turn boundary was measurably
                            # delaying the next caller frames.
                            record = metrics.close_turn("turn_complete")
                            if record:
                                metrics.log_turn(call_id=metadata.call_id, record=record)
                    tool_call = getattr(response, "tool_call", None)
                    if tool_call and transcript_logger is not None:
                        for function_call in getattr(tool_call, "function_calls", []) or []:
                            defer(lambda fc=function_call: transcript_logger.event("TOOL_CALL", {
                                "name": fc.name,
                                "args": dict(fc.args or {}),
                            }))
                    tool_started = time.perf_counter()
                    await live_adapter.handle_tool_response(
                        response, gemini_session, family_session
                    )
                    metrics.mark_tool_roundtrip((time.perf_counter() - tool_started) * 1000)
                    if family_session.end_call_requested and end_call_task is None:
                        end_call_task = asyncio.create_task(finish_after_closing())
                if stopped.is_set():
                    return
                if not saw_turn_complete:
                    metrics.mark_reconnect()
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

        async def loop_lag_watchdog() -> None:
            """Per-tick scheduling overshoot: p95 far above p50 means starvation.

            Measured from the tick's own start rather than an accumulating deadline,
            because the loop timer on Windows quantises downwards and a deadline
            comparison then reports zero even while the loop is blocked.
            """
            while not stopped.is_set():
                tick_started = time.perf_counter()
                await asyncio.sleep(LOOP_LAG_WINDOW_SECONDS)
                overshoot = time.perf_counter() - tick_started - LOOP_LAG_WINDOW_SECONDS
                metrics.mark_loop_lag(max(0.0, overshoot * 1000))

        media_task = asyncio.create_task(exotel_to_gemini())
        response_task = asyncio.create_task(gemini_to_exotel())
        keepalive_task = asyncio.create_task(keepalive())
        writes_task = asyncio.create_task(drain_writes())
        lag_task = asyncio.create_task(loop_lag_watchdog())
        tasks = {
            media_task,
            response_task,
        }
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        stopped.set()
        keepalive_task.cancel()
        if end_call_task is not None and not end_call_task.done():
            # The caller hung up before the agent asked to, so stop draining audio.
            end_call_task.cancel()
        for task in pending | {keepalive_task, lag_task}:
            task.cancel()
        await asyncio.gather(*done, *pending, return_exceptions=True)
        if end_call_task is not None:
            await asyncio.gather(end_call_task, return_exceptions=True)
        deferred_writes.put_nowait(None)
        await asyncio.gather(writes_task, return_exceptions=True)
        # A call usually ends mid-turn (the caller hangs up, or the leg closes); without
        # this the last turn the caller actually experienced would never be recorded.
        final_turn = metrics.close_turn("call_end")
        if final_turn:
            metrics.log_turn(call_id=metadata.call_id, record=final_turn)
        metrics.log_snapshot(call_id=metadata.call_id, stage="bridge_end")
        if dropped_pre_greeting_frames:
            logger.info(
                "Dropped %d pre-greeting silence frames for stream %s",
                dropped_pre_greeting_frames,
                metadata.stream_sid,
            )
        flush_transcript_turns(inline=True)
        if transcript_logger is not None:
            transcript_logger.event("LATENCY", metrics.snapshot())
        # Expose the call artifacts on the returned session for the completion payload.
        family_session.transcript_messages = transcript_messages
        family_session.latency_snapshot = metrics.snapshot()
        return family_session
