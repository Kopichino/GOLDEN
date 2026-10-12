"""Repeatable voice-latency probe for the GOLDEN Exotel↔Gemini bridge.

Modes:

* ``stub`` (default, offline, deterministic) — a fake Exotel media WebSocket feeds
  paced 8 kHz frames and a fake Gemini Live session emits audio with a *known,
  fixed* model latency. Anything measured on top of that constant is our own
  pipeline cost: JSON/base64 decode, RMS gate, resampling, event-loop scheduling
  and WebSocket forwarding. Run it against any checkout to compare before/after.

* ``live-bridge`` — the real ``LiveVoiceBridge`` with a real Gemini Live session
  and a scripted fake telephony socket. Nothing is dialled; only the model side is
  live. This is the only mode that measures true turn-taking latency (provider VAD
  + model + our forwarding) end to end.

* ``live`` — bare Gemini Live session timings (connect, first audio, chunk pacing).

* ``resample`` — micro-benchmark of the audio maths at realistic chunk sizes.

Usage:
    python scripts/voice_latency_harness.py --mode stub --trials 20
    python scripts/voice_latency_harness.py --mode live-bridge --repeats 3
    python scripts/voice_latency_harness.py --mode live --repeats 3
    python scripts/voice_latency_harness.py --mode resample
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import ctypes
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any, AsyncIterator

import numpy as np

from src.voice.exotel_media_gateway import ExotelCallMetadata
from src.voice.live_bridge import LiveVoiceBridge

FRAME_MS = 20
SAMPLE_RATE = 8000
SAMPLES_PER_FRAME = SAMPLE_RATE * FRAME_MS // 1000
FRAME_BYTES_8K = SAMPLES_PER_FRAME * 2
FRAME_BYTES_16K = FRAME_BYTES_8K * 2
KEEPALIVE_BYTES = 16_000 * 2 // 5          # the bridge's greeting keepalive blob
OUTBOUND_SAMPLE_RATE = 24_000
FIXTURE_8K = Path("data") / "caller_utterance_8k.pcm"


def sharpen_windows_timer() -> None:
    """Windows sleeps quantize to ~15.6 ms, which would swallow every real number."""
    if sys.platform == "win32":
        ctypes.windll.winmm.timeBeginPeriod(1)


def percentile(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((pct / 100.0) * (len(ordered) - 1)))))
    return round(ordered[index], 2)


def report(label: str, values: list[float]) -> dict[str, Any]:
    if not values:
        return {"label": label, "count": 0}
    return {
        "label": label,
        "count": len(values),
        "p50_ms": percentile(values, 50),
        "p95_ms": percentile(values, 95),
        "max_ms": round(max(values), 2),
        "mean_ms": round(statistics.fmean(values), 2),
    }


def voiced_frame() -> bytes:
    t = np.arange(SAMPLES_PER_FRAME) / SAMPLE_RATE
    return (np.sin(2 * np.pi * 220 * t) * 6000).astype(np.int16).tobytes()


SILENT_FRAME = bytes(FRAME_BYTES_8K)


class FakeExotelSocket:
    """Exotel media stream: deadline-paced inbound frames, timestamped outbound."""

    def __init__(self, *, scripted_frames: list[tuple[float, bytes]] | None = None,
                 voiced_frames: int = 25, pace_seconds: float = 0.02) -> None:
        self.pace = pace_seconds
        self.scripted = scripted_frames
        self.voiced_frames = voiced_frames
        self.outbound: list[tuple[float, int]] = []
        self.yields: list[tuple[float, bytes]] = []
        self._stop = False

    def stop(self) -> None:
        self._stop = True

    def __aiter__(self) -> AsyncIterator[str]:
        return self._drive()

    async def _drive(self) -> AsyncIterator[str]:
        if self.scripted is not None:
            for payload, voiced in self.scripted:
                if self._stop:
                    break
                now = time.perf_counter()
                self.yields.append((now, voiced))
                yield json.dumps({"event": "media", "media": {"payload": payload}})
                delay = self.pace - (time.perf_counter() - now)
                if delay > 0:
                    await asyncio.sleep(delay)
        else:
            deadline = time.perf_counter()
            index = 0
            while not self._stop:
                index += 1
                payload = voiced_frame() if index <= self.voiced_frames else SILENT_FRAME
                now = time.perf_counter()
                self.yields.append((now, payload))
                yield json.dumps({
                    "event": "media",
                    "media": {"payload": base64.b64encode(payload).decode()},
                })
                deadline += self.pace
                delay = deadline - time.perf_counter()
                if delay > 0:
                    await asyncio.sleep(delay)
        yield json.dumps({"event": "stop"})

    async def send(self, message: str) -> None:
        self.outbound.append((time.perf_counter(), len(message)))


class StubGeminiSession:
    """Gemini Live stand-in with a *known* latency, so deltas are ours."""

    def __init__(self, *, first_token_ms: float, chunk_interval_ms: float, chunks: int) -> None:
        self.first_token_ms = first_token_ms
        self.chunk_interval_ms = chunk_interval_ms
        self.chunks = chunks
        self.media_arrivals: list[float] = []
        self.keepalive_arrivals: list[float] = []
        self.chunk_generated: list[float] = []
        self.turn_started_at: float | None = None
        self._queue: asyncio.Queue = asyncio.Queue()
        self._generating = False

    async def send_realtime_input(self, *, audio: Any) -> None:
        arrived_at = time.perf_counter()
        size = len(audio.data)
        if size == KEEPALIVE_BYTES:
            self.keepalive_arrivals.append(arrived_at)
            return
        self.media_arrivals.append(arrived_at)
        if self._generating or size < FRAME_BYTES_16K:
            return
        self._generating = True
        self.turn_started_at = arrived_at
        asyncio.get_running_loop().create_task(self._generate())

    async def _generate(self) -> None:
        await asyncio.sleep(self.first_token_ms / 1000)
        chunk = bytes(OUTBOUND_SAMPLE_RATE * 2 * self.chunk_interval_ms // 1000)
        for _ in range(self.chunks):
            self.chunk_generated.append(time.perf_counter())
            await self._queue.put(_audio_message(chunk))
            await asyncio.sleep(self.chunk_interval_ms / 1000)
        await self._queue.put(_turn_complete_message())
        self._generating = False

    async def receive(self) -> AsyncIterator[Any]:
        while True:
            yield await self._queue.get()


def _audio_message(data: bytes) -> Any:
    part = type("Part", (), {"inline_data": type("Inline", (), {"data": data})()})()
    turn = type("Turn", (), {"parts": [part]})()
    content = type("Content", (), {
        "model_turn": turn,
        "input_transcription": None,
        "output_transcription": None,
        "interrupted": False,
        "turn_complete": False,
    })()
    return type("Response", (), {"server_content": content, "tool_call": None})()


def _turn_complete_message() -> Any:
    content = type("Content", (), {
        "model_turn": None,
        "input_transcription": None,
        "output_transcription": None,
        "interrupted": False,
        "turn_complete": True,
    })()
    return type("Response", (), {"server_content": content, "tool_call": None})()


async def measure_loop_lag(samples: list[float], window: float = 0.005) -> None:
    """Per-tick event-loop scheduling delay; the deadline re-bases when starved."""
    deadline = time.perf_counter() + window
    while True:
        await asyncio.sleep(window)
        now = time.perf_counter()
        samples.append(max(0.0, (now - deadline) * 1000))
        if now - deadline > 5 * window:
            deadline = now
        deadline += window


async def run_stub_trial(*, first_token_ms: float, chunk_interval_ms: float,
                         chunks: int, voiced_frames: int, pace: float,
                         transcript: bool) -> dict[str, Any]:
    socket = FakeExotelSocket(voiced_frames=voiced_frames, pace_seconds=pace)
    gemini = StubGeminiSession(
        first_token_ms=first_token_ms,
        chunk_interval_ms=chunk_interval_ms,
        chunks=chunks,
    )
    metadata = ExotelCallMetadata("case-harness", "thread-harness", "call-harness")
    transcript_logger = _TempTranscriptLogger() if transcript else None

    lag: list[float] = []
    lag_task = asyncio.create_task(measure_loop_lag(lag))
    call_task = asyncio.create_task(LiveVoiceBridge().run(
        socket, metadata, gemini, transcript_logger=transcript_logger,
    ))

    async def stop_when_answered() -> None:
        while not call_task.done():
            if len(socket.outbound) >= chunks:
                socket.stop()
                return
            await asyncio.sleep(0.005)

    waiter = asyncio.create_task(stop_when_answered())
    started = time.perf_counter()
    family_session = None
    try:
        family_session = await asyncio.wait_for(asyncio.shield(call_task), timeout=30)
    finally:
        socket.stop()
        waiter.cancel()
        lag_task.cancel()
        await asyncio.gather(waiter, lag_task, return_exceptions=True)
    elapsed = time.perf_counter() - started

    voiced = [t for t, payload in socket.yields if payload != SILENT_FRAME]
    inbound = [(recv - sent) * 1000 for sent, recv in zip(voiced, gemini.media_arrivals)]
    outbound = [(sent - generated) * 1000
                for generated, (sent, _) in zip(gemini.chunk_generated, socket.outbound)]
    caller_end_to_playout = None
    if gemini.turn_started_at is not None and socket.outbound:
        caller_end_to_playout = (socket.outbound[0][0] - gemini.turn_started_at) * 1000

    return {
        "elapsed_seconds": round(elapsed, 2),
        "media_frames_forwarded": len(gemini.media_arrivals),
        "keepalive_frames": len(gemini.keepalive_arrivals),
        "outbound_frames": len(socket.outbound),
        "inbound_stage": report("inbound stage", inbound),
        "outbound_stage": report("outbound stage", outbound),
        "caller_end_to_playout_ms": round(caller_end_to_playout, 2) if caller_end_to_playout else None,
        "event_loop_lag": report("event loop lag", lag[2:]),
        "bridge_metrics": getattr(family_session, "latency_snapshot", None),
        "outbound_message_bytes": round(statistics.fmean([n for _, n in socket.outbound]), 1)
        if socket.outbound else None,
    }


class _TempTranscriptLogger:
    """Mimics VoiceTranscriptLogger's synchronous per-write file I/O."""

    def __init__(self) -> None:
        import tempfile
        self.path = f"{tempfile.gettempdir()}/harness_transcript.log"
        self._pending: dict[str, list[str]] = {"CALLER": [], "AGENT": []}

    def add_transcript(self, role: str, text: Any) -> None:
        self._pending.setdefault(role, []).append(str(text))

    def finish_turn(self) -> dict[str, str]:
        done = {r: " ".join(v) for r, v in self._pending.items() if v}
        with open(self.path, "a", encoding="utf-8") as stream:
            for role, text in done.items():
                stream.write(f"{role}: {text}\n")
            stream.write("\n")
        for buffer in self._pending.values():
            buffer.clear()
        return done

    def event(self, name: str, details: Any = "") -> None:
        with open(self.path, "a", encoding="utf-8") as stream:
            stream.write(f"EVENT {name} {json.dumps(details, default=str)}\n")

    def close(self) -> None:
        self.finish_turn()


# ── Caller speech fixture ───────────────────────────────────────────────────

CALLER_UTTERANCE = "Yes that is okay. He is allergic to coconut and he takes blood pressure medicine."


async def ensure_caller_fixture(force: bool = False) -> Path:
    """Generate (once) a real spoken caller utterance at 8 kHz PCM 16-bit mono."""
    if FIXTURE_8K.exists() and not force:
        return FIXTURE_8K
    from google import genai
    from google.genai import types
    from src.config import settings
    from src.voice.audio_bridge import AudioBridge

    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    response = await client.aio.models.generate_content(
        model="gemini-2.5-flash-preview-tts",
        contents=CALLER_UTTERANCE,
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Kore"))),
        ),
    )
    pcm_24k = response.candidates[0].content.parts[0].inline_data.data
    FIXTURE_8K.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE_8K.write_bytes(AudioBridge.resample_to_8k(pcm_24k, source_rate=24000))
    return FIXTURE_8K


def fixture_frames(pcm_8k: bytes) -> list[bytes]:
    return [pcm_8k[i:i + FRAME_BYTES_8K] for i in range(0, len(pcm_8k), FRAME_BYTES_8K)]


class ObservingSession:
    """Transparent proxy around a real Gemini Live session.

    Wrapping (rather than editing) the session means the same probe runs against
    unmodified baseline code and against changed code, so the numbers compare.
    """

    def __init__(self, inner: Any) -> None:
        self.inner = inner
        self.input_sent: list[tuple[float, int, bool]] = []
        self.audio_chunks: list[tuple[float, int]] = []
        self.turn_completes: list[float] = []
        self.interrupts: list[float] = []
        self.responses: list[float] = []
        self.text_fragments = 0

    async def send_realtime_input(self, *, audio: Any) -> None:
        self.input_sent.append((time.perf_counter(), len(audio.data), any(audio.data)))
        await self.inner.send_realtime_input(audio=audio)

    async def send_tool_response(self, **kwargs: Any) -> Any:
        return await self.inner.send_tool_response(**kwargs)

    def _observe(self, response: Any) -> None:
        content = getattr(response, "server_content", None)
        if content is None:
            return
        if getattr(content, "interrupted", False):
            self.interrupts.append(time.perf_counter())
        self.responses.append(time.perf_counter())
        for attribute in ("input_transcription", "output_transcription"):
            if getattr(getattr(content, attribute, None), "text", None):
                self.text_fragments += 1
        turn = getattr(content, "model_turn", None)
        for part in getattr(turn, "parts", None) or []:
            data = getattr(getattr(part, "inline_data", None), "data", None)
            if data:
                self.audio_chunks.append((time.perf_counter(), len(data)))
        if getattr(content, "turn_complete", False):
            self.turn_completes.append(time.perf_counter())

    async def receive(self) -> AsyncIterator[Any]:
        async for response in self.inner.receive():
            self._observe(response)
            yield response


class ScriptedTelephony:
    """Greeting window -> caller utterance -> silence until the agent replies."""

    def __init__(self, utterance_frames: list[bytes], *, pace: float,
                 greeting_cap_seconds: float = 40, silence_cap: int = 700) -> None:
        self.utterance_frames = utterance_frames
        self.pace = pace
        self.greeting_cap = greeting_cap_seconds
        self.silence_cap = silence_cap
        self.outbound: list[tuple[float, int]] = []
        self.yields: list[tuple[float, bytes]] = []
        self.clears: list[float] = []
        self.greeting_frames = 0
        self.observer: ObservingSession | None = None
        self._stop = False

    def stop(self) -> None:
        self._stop = True

    def __aiter__(self) -> AsyncIterator[str]:
        return self._drive(self.observer)

    async def _emit(self, payload_b64: str, raw: bytes, started: float) -> AsyncIterator[str]:
        self.yields.append((time.perf_counter(), raw))
        yield json.dumps({"event": "media", "media": {"payload": payload_b64}})
        remaining = self.pace - (time.perf_counter() - started)
        if remaining > 0:
            await asyncio.sleep(remaining)

    async def _drive(self, observer: ObservingSession | None = None) -> AsyncIterator[str]:
        started = time.perf_counter()
        silent_b64 = base64.b64encode(SILENT_FRAME).decode()

        def greeting_done() -> bool:
            if observer is not None:
                return bool(observer.turn_completes)
            return len(self.outbound) >= 10

        # Phase 1: stay quiet while the agent plays its greeting.
        while not greeting_done() and time.perf_counter() - started < self.greeting_cap:
            if self._stop:
                break
            self.greeting_frames += 1
            async for message in self._emit(silent_b64, SILENT_FRAME, time.perf_counter()):
                yield message

        # Phase 2: the caller speaks.
        for payload in self.utterance_frames:
            if self._stop:
                break
            async for message in self._emit(base64.b64encode(payload).decode(), payload, time.perf_counter()):
                yield message
        self.spoken_until = time.perf_counter()

        # Phase 3: caller stops; wait for the agent's reply to start playing.
        for _ in range(self.silence_cap):
            if self._stop or any(t > self.spoken_until for t, _ in self.outbound):
                break
            async for message in self._emit(silent_b64, SILENT_FRAME, time.perf_counter()):
                yield message
        yield json.dumps({"event": "stop"})

    async def send(self, message: str) -> None:
        if '"clear"' in message:
            self.clears.append(time.perf_counter())
            return
        self.outbound.append((time.perf_counter(), len(message)))


async def run_live_bridge_trial(index: int, *, pace: float) -> dict[str, Any]:
    from src.voice.gemini_live_session import GeminiLiveFamilySession

    pcm_8k = (await ensure_caller_fixture()).read_bytes()
    utterance = fixture_frames(pcm_8k)
    socket = ScriptedTelephony(utterance, pace=pace)
    metadata = ExotelCallMetadata("case-harness", "thread-harness", f"call-harness-{index}")
    adapter = GeminiLiveFamilySession()

    lag: list[float] = []
    lag_task = asyncio.create_task(measure_loop_lag(lag))
    started = time.perf_counter()
    connect_at: float | None = None
    observer: ObservingSession | None = None
    family_session = None
    try:
        async with adapter.connect() as gemini_session:
            connect_at = time.perf_counter()
            observer = ObservingSession(gemini_session)
            socket.observer = observer
            family_session = await asyncio.wait_for(
                LiveVoiceBridge().run(socket, metadata, observer, adapter),
                timeout=90,
            )
    finally:
        socket.stop()
        lag_task.cancel()
        await asyncio.gather(lag_task, return_exceptions=True)

    voiced = [t for t, payload in socket.yields if payload != SILENT_FRAME]
    forwarded = socket.outbound
    reply_after = [t for t, _ in forwarded if voiced and t > voiced[-1]]
    greeting_end = observer.turn_completes[0] if observer and observer.turn_completes else None

    # Inbound stage: telephony frame handed over -> bytes actually on the Gemini wire.
    # Pairing is by content, not by index: every all-zero blob the bridge forwards is
    # either a pre-greeting keepalive blob or the caller's silence after the utterance,
    # and neither corresponds to one of the scripted voiced frames.
    forwarded_inputs = [t for t, _size, carried_speech in (observer.input_sent if observer else [])
                        if carried_speech]
    # Index pairing is only meaningful when the bridge forwarded exactly the frames we
    # scripted; a caller that barges into the greeting drops frames and shifts the pair.
    inbound = ([(recv - sent) * 1000 for sent, recv in zip(voiced, forwarded_inputs)]
               if len(voiced) == len(forwarded_inputs) else [])
    inbound_pairing = (len(voiced), len(forwarded_inputs))
    # Outbound stage: chunk arrives from Gemini -> media message handed to Exotel.
    generated = [t for t, _ in (observer.audio_chunks if observer else [])]
    outbound = [(sent - got) * 1000 for got, (sent, _) in zip(generated, forwarded)]

    reply_generated = [t for t in generated if t > socket.spoken_until]
    return {
        "trial": index,
        "elapsed_seconds": round(time.perf_counter() - started, 2),
        "gemini_connect_ms": round((connect_at - started) * 1000, 2) if connect_at else None,
        "greeting_ms": round((greeting_end - connect_at) * 1000, 2) if greeting_end and connect_at else None,
        "greeting_chunks": sum(1 for t, _ in forwarded if voiced and t <= voiced[0]),
        "caller_speech_seconds": round(len(voiced) * pace, 2),
        "turn_latency_to_gemini_audio_ms": round((reply_generated[0] - voiced[-1]) * 1000, 2)
        if reply_generated and voiced else None,
        "turn_latency_to_playout_ms": round((reply_after[0] - voiced[-1]) * 1000, 2) if reply_after and voiced else None,
        "inbound_stage": report("inbound stage", inbound),
        "inbound_pairing": inbound_pairing,
        "outbound_stage": report("outbound stage", outbound),
        "interrupt_clears": len(socket.clears),
        "gemini_interrupts": len(observer.interrupts) if observer else None,
        "outbound_message_bytes": round(statistics.fmean([n for _, n in forwarded]), 1) if forwarded else None,
        "event_loop_lag": report("event loop lag", lag[2:]),
        "bridge_metrics": getattr(family_session, "latency_snapshot", None),
    }


async def run_live_repeats(repeats: int) -> list[dict[str, Any]]:
    """Real Gemini Live timings; no telephony, no call is placed."""
    from google import genai
    from google.genai import types
    from src.config import settings

    results = []
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    for index in range(repeats):
        connect_started = time.perf_counter()
        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            system_instruction="Say exactly: Hello, this is GOLDEN emergency support.",
            input_audio_transcription=types.AudioTranscriptionConfig(),
            output_audio_transcription=types.AudioTranscriptionConfig(),
        )
        async with client.aio.live.connect(model=settings.GEMINI_LIVE_MODEL, config=config) as session:
            connect_ms = (time.perf_counter() - connect_started) * 1000
            await session.send_client_content(
                turns=[types.Content(role="user", parts=[types.Part.from_text(text="CALL_START")])],
                turn_complete=True,
            )
            asked_at = time.perf_counter()
            first_audio = None
            gaps: list[float] = []
            sizes: list[int] = []
            last: float | None = None
            async for response in session.receive():
                content = getattr(response, "server_content", None)
                if not content:
                    continue
                turn = getattr(content, "model_turn", None)
                for part in getattr(turn, "parts", []) or []:
                    data = getattr(getattr(part, "inline_data", None), "data", None)
                    if data:
                        now = time.perf_counter()
                        if first_audio is None:
                            first_audio = now
                        if last is not None:
                            gaps.append((now - last) * 1000)
                        last = now
                        sizes.append(len(data))
                if getattr(content, "turn_complete", False):
                    break
            results.append({
                "trial": index,
                "connect_ms": round(connect_ms, 2),
                "first_audio_ms": round((first_audio - asked_at) * 1000, 2) if first_audio else None,
                "chunk_count": len(sizes),
                "chunk_bytes_mean": round(statistics.fmean(sizes), 1) if sizes else None,
                "chunk_audio_ms": round(statistics.fmean(sizes) / (OUTBOUND_SAMPLE_RATE * 2) * 1000, 1)
                if sizes else None,
                "chunk_gap": report("gemini chunk gap", gaps),
                "turn_total_ms": round(((last or asked_at) - asked_at) * 1000, 2),
            })
    return results


def aggregate_stub(trials: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, Any]:
    def pooled(key: str, sub: str) -> dict[str, Any]:
        values = [t[key][sub] for t in trials if t[key]["count"]]
        return report(key, values)

    return {
        "configuration": config,
        "trials": len(trials),
        "per_trial_pooled": {
            "inbound_stage": pooled("inbound_stage", "p50_ms"),
            "inbound_stage_p95": pooled("inbound_stage", "p95_ms"),
            "outbound_stage": pooled("outbound_stage", "p50_ms"),
            "outbound_stage_p95": pooled("outbound_stage", "p95_ms"),
            "event_loop_lag_max": pooled("event_loop_lag", "max_ms"),
            "event_loop_lag_p50": pooled("event_loop_lag", "p50_ms"),
        },
        "caller_end_to_playout": report("caller end -> first playout (includes known model latency)", [
            t["caller_end_to_playout_ms"] for t in trials if t["caller_end_to_playout_ms"] is not None
        ]),
        "notes": {
            "known_model_first_token_ms": config["known_model_first_token_ms"],
            "interpretation": "caller_end_to_playout minus first_token_ms is everything we control",
            "outbound_message_bytes_mean": round(statistics.fmean([
                t["outbound_message_bytes"] for t in trials if t["outbound_message_bytes"]
            ]), 1) if any(t["outbound_message_bytes"] for t in trials) else None,
            "keepalive_frames_per_trial": [t["keepalive_frames"] for t in trials],
        },
    }


def aggregate_live(trials: list[dict[str, Any]]) -> dict[str, Any]:
    def pull(key: str) -> list[float]:
        return [t[key] for t in trials if t.get(key) is not None]

    def pooled(key: str, sub: str) -> dict[str, Any]:
        values = [t[key][sub] for t in trials if t[key]["count"]]
        return report(key, values)

    return {
        "trials": len(trials),
        "gemini_connect_ms": report("gemini connect", pull("gemini_connect_ms")),
        "greeting_ms": report("connect -> greeting turn_complete", pull("greeting_ms")),
        "turn_latency_to_gemini_audio": report("caller end -> first Gemini audio", pull("turn_latency_to_gemini_audio_ms")),
        "turn_latency_to_playout": report("caller end -> first playout at Exotel", pull("turn_latency_to_playout_ms")),
        "inbound_stage": pooled("inbound_stage", "p50_ms"),
        "inbound_stage_p95": pooled("inbound_stage", "p95_ms"),
        "outbound_stage": pooled("outbound_stage", "p50_ms"),
        "outbound_stage_p95": pooled("outbound_stage", "p95_ms"),
        "event_loop_lag_p95": pooled("event_loop_lag", "p95_ms"),
        "event_loop_lag_max": pooled("event_loop_lag", "max_ms"),
        "interrupts": {"socket_clears": sum(t["interrupt_clears"] or 0 for t in trials),
                       "gemini_interrupted": sum(t["gemini_interrupts"] or 0 for t in trials)},
        "outbound_message_bytes": pull("outbound_message_bytes"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="GOLDEN voice latency probe")
    parser.add_argument("--mode", choices=("stub", "live", "live-bridge", "resample"), default="stub")
    parser.add_argument("--trials", type=int, default=20)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--first-token-ms", type=float, default=250)
    parser.add_argument("--chunk-interval-ms", type=float, default=200)
    parser.add_argument("--chunks", type=int, default=6)
    parser.add_argument("--voiced-frames", type=int, default=25)
    parser.add_argument("--pace", type=float, default=0.02, help="seconds between inbound frames")
    parser.add_argument("--with-transcript-io", action="store_true",
                        help="attach a file-writing transcript logger (production behaviour)")
    parser.add_argument("--refresh-fixture", action="store_true")
    parser.add_argument("--out", default=None, help="write JSON results to this file")
    args = parser.parse_args()

    sharpen_windows_timer()

    if args.mode == "live":
        payload = json.dumps(asyncio.run(run_live_repeats(args.repeats)), indent=2)
    elif args.mode == "live-bridge":
        trials = [asyncio.run(run_live_bridge_trial(i, pace=args.pace)) for i in range(args.repeats)]
        payload = json.dumps({"aggregate": aggregate_live(trials), "trials": trials}, indent=2)
    elif args.mode == "resample":
        from src.voice.audio_bridge import AudioBridge
        from src.voice.exotel_media_gateway import ExotelMediaGateway

        frame = voiced_frame()
        outbound = bytes(4800 * 2)

        def bench(label, fn, n=400):
            samples = []
            for _ in range(n):
                t = time.perf_counter()
                fn()
                samples.append((time.perf_counter() - t) * 1000)
            return report(label, samples)

        payload = json.dumps([
            bench("pcm16_rms(20ms@8k)", lambda: AudioBridge.pcm16_rms(frame)),
            bench("fast_resample_8k_to_16k", lambda: AudioBridge.fast_resample_8k_to_16k(frame)),
            bench("resample_poly_8k_to_16k", lambda: AudioBridge.resample_8k_to_16k(frame)),
            bench("to_exotel_message(200ms@24k)",
                  lambda: ExotelMediaGateway.to_exotel_message(outbound, source_rate=24000, stream_sid="S")),
        ], indent=2)
    else:
        config = {
            "trials": args.trials,
            "known_model_first_token_ms": args.first_token_ms,
            "known_model_chunk_interval_ms": args.chunk_interval_ms,
            "model_chunks_per_turn": args.chunks,
            "inbound_frame_ms": FRAME_MS,
            "pace_seconds": args.pace,
            "voiced_frames": args.voiced_frames,
            "transcript_io": args.with_transcript_io,
        }
        trials = [asyncio.run(run_stub_trial(
            first_token_ms=args.first_token_ms,
            chunk_interval_ms=args.chunk_interval_ms,
            chunks=args.chunks,
            voiced_frames=args.voiced_frames,
            pace=args.pace,
            transcript=args.with_transcript_io,
        )) for _ in range(args.trials)]
        payload = json.dumps({"aggregate": aggregate_stub(trials, config), "trials": trials}, indent=2)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as stream:
            stream.write(payload)
        print(f"wrote {args.out}")
    else:
        print(payload)


if __name__ == "__main__":
    main()
