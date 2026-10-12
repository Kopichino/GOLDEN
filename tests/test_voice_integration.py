import asyncio
import base64
import hashlib
import hmac
import json

import pytest

from src.voice.callback_security import CallbackSecurity
from src.voice.exotel_client import ExotelClient
from src.voice.exotel_media_gateway import (
    ExotelCallMetadata,
    ExotelMediaGateway,
    decode_media_frame,
    parse_event,
)
from src.voice.family_voice_session import FamilyVoiceSession
from src.voice.gemini_live_session import GeminiLiveFamilySession
from src.voice.latency_metrics import VoiceLatencyMetrics
from src.voice.live_bridge import LiveVoiceBridge


@pytest.fixture(autouse=True)
def isolated_call_log(tmp_path, monkeypatch):
    """Keep voice tests from writing entries into the real call-log store."""
    from src.voice import call_log

    monkeypatch.setattr(call_log, "CALL_LOG_FILE", tmp_path / "voice_call_logs.json")
    yield


def test_exotel_media_protocol_decodes_and_resamples_audio():
    pcm_8khz = b"\x01\x00" * 80
    event = {
        "event": "media",
        "media": {"payload": base64.b64encode(pcm_8khz).decode("ascii")},
    }

    parsed = parse_event(json.dumps(event))
    frame = decode_media_frame(parsed)

    assert frame is not None
    assert frame.pcm_8khz == pcm_8khz
    assert len(ExotelMediaGateway.to_realtime_audio(frame)) == len(pcm_8khz) * 2


def test_exotel_metadata_requires_all_durable_identifiers():
    metadata = ExotelCallMetadata.from_start_event({
        "stream_sid": "stream-1",
        "start": {
            "call_id": "call-1",
            "customParameters": {"case_id": "case-1", "thread_id": "thread-1"},
        }
    })

    metadata.validate()
    assert metadata.case_id == "case-1"
    assert metadata.thread_id == "thread-1"
    assert metadata.stream_sid == "stream-1"

    with pytest.raises(ValueError):
        ExotelCallMetadata("", "thread-1", "call-1").validate()


def test_exotel_outbound_audio_preserves_stream_id():
    message = json.loads(
        ExotelMediaGateway.to_exotel_message(b"\x00\x00", stream_sid="stream-1")
    )

    assert message["event"] == "media"
    assert message["stream_sid"] == "stream-1"


def test_exotel_metadata_recovers_missing_ids_from_active_registry():
    from src.voice.active_calls import register_active_call

    register_active_call(
        call_id="call-exotel-999",
        case_id="case-recovered-999",
        thread_id="thread-recovered-999",
        recipient_phone="+919876543210",
    )

    # Simulate Exotel connecting with only callSid and NO customParameters or query string
    metadata = ExotelCallMetadata.from_start_event(
        event={"start": {"callSid": "call-exotel-999"}},
        stream_path="/ws",
    )
    metadata.validate()
    assert metadata.case_id == "case-recovered-999"
    assert metadata.thread_id == "thread-recovered-999"
    assert metadata.call_id == "call-exotel-999"
    assert metadata.recipient_phone == "+919876543210"


def test_family_session_requires_consent_before_collecting_history():
    session = FamilyVoiceSession(ExotelCallMetadata("case-1", "thread-1", "call-1"))

    refused = session.handle_tool_call("record_allergies", {"value": ["Penicillin"]})
    assert refused["status"] == "rejected"

    accepted = session.handle_tool_call("record_consent", {"consent_granted": True})
    assert accepted["status"] == "accepted"
    recorded = session.handle_tool_call("record_allergies", {"value": ["Penicillin"]})
    assert recorded["status"] == "recorded"
    assert session.callback_fields("COMPLETED", 30)["allergies"] == ["Penicillin"]


def test_gemini_array_tools_declare_string_items():
    declarations = GeminiLiveFamilySession.build_tools()[0].function_declarations
    array_tools = {
        "record_allergies",
        "record_medications",
        "record_conditions",
    }

    for declaration in declarations:
        if declaration.name in array_tools:
            value_schema = declaration.parameters.properties["value"]
            assert value_schema.items.type == "STRING"


def test_family_outreach_pins_recipient_for_trial_accounts(monkeypatch):
    from src.voice.family_communication import FamilyCommunicationAgent

    monkeypatch.setattr(
        "src.voice.family_communication.settings.VOICE_TEST_RECIPIENT_PHONE", "+919566017658"
    )
    captured = {}

    class FakeExotel:
        def trigger_outbound_call(self, **kwargs):
            captured.update(kwargs)
            return {"status": "TRIGGERED", "call_id": "call-1", "provider": "exotel", "message": "ok"}

    result = FamilyCommunicationAgent(exotel_client=FakeExotel()).execute_outreach(
        case_id="case-1",
        recipient_phone="+919999900000",
        consent_basis="Crew identified the family member on scene",
    )

    assert captured["recipient_phone"] == "+919566017658"
    # The audit trail keeps the relative the crew actually found, not the trial leg.
    assert result["recipient_phone"] == "+919999900000"


def test_trial_pin_never_dials_in_place_of_consent(monkeypatch):
    """Substituting the leg must not turn an unregistered number into a call.

    The pin exists because Exotel trial accounts can only dial verified numbers; if
    it were applied before the consent check, every refused number would silently
    become a call to the developer's own phone.
    """
    from src.voice.family_communication import FamilyCommunicationAgent

    monkeypatch.setattr(
        "src.voice.family_communication.settings.VOICE_TEST_RECIPIENT_PHONE", "+919566017658"
    )
    monkeypatch.setattr("src.voice.call_log.record_call_trigger", lambda **kwargs: None)
    dialled = []

    class FakeExotel:
        def verify_consent(self, phone):
            return False

        def trigger_outbound_call(self, **kwargs):
            dialled.append(kwargs["recipient_phone"])
            return {"status": "TRIGGERED", "call_id": "call-1"}

    result = FamilyCommunicationAgent(exotel_client=FakeExotel()).execute_outreach(
        case_id="case-1",
        recipient_phone="+910000000000",
    )

    assert result["status"] == "CONSENT_REFUSED"
    assert dialled == []


def test_callback_security_authenticates_once_and_rejects_replay():
    security = CallbackSecurity("test-secret", max_age_seconds=300)
    body = b'{"case_id":"case-1"}'
    timestamp = "1700000000"
    nonce = "nonce-1"
    signed = f"{timestamp}.{nonce}.".encode() + body
    signature = hmac.new(b"test-secret", signed, hashlib.sha256).hexdigest()

    valid, _ = security.validate(
        body,
        signature=f"sha256={signature}",
        timestamp=timestamp,
        nonce=nonce,
        now=1700000000,
    )
    assert valid is True

    replayed, reason = security.validate(
        body,
        signature=signature,
        timestamp=timestamp,
        nonce=nonce,
        now=1700000000,
    )
    assert replayed is False
    assert "already" in reason


def test_exotel_client_builds_request_from_new_environment(monkeypatch):
    monkeypatch.setattr("src.voice.exotel_client.settings.VOICE_SIMULATION_ONLY", False)
    monkeypatch.setattr("src.voice.exotel_client.settings.EXOTEL_ACCOUNT_SID", "new-account")
    monkeypatch.setattr("src.voice.exotel_client.settings.EXOTEL_API_KEY", "new-key")
    monkeypatch.setattr("src.voice.exotel_client.settings.EXOTEL_API_TOKEN", "new-token")
    monkeypatch.setattr("src.voice.exotel_client.settings.EXOTEL_SUBDOMAIN", "new.exotel.example")
    monkeypatch.setattr("src.voice.exotel_client.settings.EXOTEL_CALLER_ID", "new-caller")
    monkeypatch.setattr("src.voice.exotel_client.settings.EXOTEL_STREAM_URL", "wss://new.example/ws")
    monkeypatch.setattr("src.voice.exotel_client.settings.EXOTEL_STATUS_CALLBACK_URL", "https://new.example/status")
    monkeypatch.setattr("src.voice.exotel_client.settings.TEAM_CONSENT_PHONE_NUMBERS", "+919999999999")
    monkeypatch.setattr("src.voice.exotel_client.settings.EXOTEL_RECORD_CALLS", False)

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"Call": {"Sid": "new-call-id"}}

    captured = {}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured["kwargs"] = kwargs
        return FakeResponse()

    monkeypatch.setattr("src.voice.exotel_client.requests.post", fake_post)
    client = ExotelClient()
    result = client.trigger_outbound_call(
        recipient_phone="+91 99999 99999",
        case_id="case-1",
        thread_id="thread-1",
    )

    assert result["call_id"] == "new-call-id"
    assert captured["url"] == "https://new.exotel.example/v1/Accounts/new-account/Calls/connect.json"
    assert captured["kwargs"]["auth"] == ("new-key", "new-token")
    assert captured["kwargs"]["data"]["CallerId"] == "new-caller"
    assert "case_id=case-1" in captured["kwargs"]["data"]["StreamUrl"]


def test_exotel_client_fails_closed_without_new_account_configuration(monkeypatch):
    monkeypatch.setattr("src.voice.exotel_client.settings.VOICE_SIMULATION_ONLY", False)
    monkeypatch.setattr("src.voice.exotel_client.settings.TEAM_CONSENT_PHONE_NUMBERS", "+919999999999")
    monkeypatch.setattr("src.voice.exotel_client.settings.EXOTEL_ACCOUNT_SID", None)

    client = ExotelClient()
    with pytest.raises(RuntimeError, match="not configured"):
        client.trigger_outbound_call(
            recipient_phone="+919999999999",
            case_id="case-1",
        )


def test_live_bridge_waits_for_caller_after_greeting_turn():
    class FakeWebSocket:
        def __init__(self):
            self.greeting_sent = asyncio.Event()

        def __aiter__(self):
            return self._events()

        async def _events(self):
            await self.greeting_sent.wait()
            yield json.dumps({
                "event": "media",
                "media": {"payload": base64.b64encode(b"\x01\x00" * 80).decode()},
            })
            yield json.dumps({"event": "stop"})

        async def send(self, message):
            self.sent = getattr(self, "sent", []) + [message]
            self.greeting_sent.set()

    class FakeResponse:
        def __init__(self, turn_complete=False, audio=False):
            self.server_content = type("Content", (), {
                "turn_complete": turn_complete,
                "interrupted": False,
                "model_turn": type("Turn", (), {
                    "parts": [type("Part", (), {
                        "inline_data": type("Audio", (), {"data": b"\x00\x00"})() if audio else None,
                    })()]
                })() if audio else None,
            })
            self.tool_call = None

    class FakeGemini:
        def __init__(self):
            self.received_audio = []
            self.receive_count = 0

        async def send_realtime_input(self, audio):
            self.received_audio.append(audio.data)

        async def receive(self):
            self.receive_count += 1
            if self.receive_count == 1:
                yield FakeResponse(turn_complete=True, audio=True)
            else:
                await asyncio.sleep(0.2)

    websocket = FakeWebSocket()
    gemini = FakeGemini()
    metadata = ExotelCallMetadata("case-1", "thread-1", "call-1")
    session = asyncio.run(LiveVoiceBridge().run(websocket, metadata, gemini))

    assert session.metadata.call_id == "call-1"
    assert gemini.receive_count >= 2
    assert gemini.received_audio


def test_latency_metrics_report_required_voice_segments():
    metrics = VoiceLatencyMetrics()
    metrics.mark_media(is_speech=True)
    metrics.mark_gemini_input()
    metrics.mark_gemini_audio()
    metrics.mark_exotel_audio()

    snapshot = metrics.snapshot()
    assert snapshot["caller_audio_to_gemini_ms"] is not None
    assert snapshot["gemini_processing_to_audio_ms"] is not None
    assert snapshot["gemini_audio_to_exotel_ms"] is not None
    assert snapshot["caller_audio_to_exotel_ms"] is not None


def test_live_bridge_hangs_up_after_the_closing_line(monkeypatch):
    """`end_call` must release the caller, but only once the audio has drained.

    Exotel Stream has no REST terminate: the leg drops when we close the
    WebSocket, so that close is the hang-up. Doing it the moment the tool arrives
    would clip the closing sentence, so the drain watches outbound audio first.
    """
    from src.voice import live_bridge

    monkeypatch.setattr(live_bridge, "END_CALL_DRAIN_SECONDS", 0.05)

    class EndCallAdapter:
        async def handle_tool_response(self, response, gemini_session, family_session):
            for call in getattr(getattr(response, "tool_call", None), "function_calls", []) or []:
                family_session.handle_tool_call(call.name, dict(call.args or {}))

    websocket = _RecordingSocket()  # stays open: only the bridge can end this call
    gemini = _MutedGemini([
        type("Response", (), {
            "server_content": _server_content(turn_complete=True, audio=True),
            "tool_call": None,
        })(),
        type("Response", (), {
            "server_content": None,
            "tool_call": type("Calls", (), {"function_calls": [
                type("Call", (), {"name": "end_call", "id": "fc-1", "args": {}})(),
            ]})(),
        })(),
    ])

    session = asyncio.run(LiveVoiceBridge().run(
        websocket,
        ExotelCallMetadata("case-1", "thread-1", "call-1"),
        gemini,
        gemini_live_session=EndCallAdapter(),
    ))

    assert websocket.closed is True
    assert session.end_call_requested is True
    assert session.latency_snapshot["audio_frames_sent_to_exotel"] >= 1


def test_end_call_is_not_gated_on_consent():
    """A caller who refuses consent still has to be released from the leg."""
    from src.voice.family_voice_session import FamilyDisclosureAccumulator

    disclosures = FamilyDisclosureAccumulator()
    assert disclosures.apply_tool_call("end_call", {}) == {"status": "accepted"}
    assert disclosures.end_call_requested is True
    # …while the disclosure fields stay locked behind consent.
    assert disclosures.apply_tool_call("record_allergies", {"value": ["Penicillin"]})["status"] == "rejected"


def test_end_call_is_declared_for_the_live_session():
    from src.voice.gemini_live_session import GeminiLiveFamilySession

    declarations = GeminiLiveFamilySession.build_tools()[0].function_declarations
    end_call = next(item for item in declarations if item.name == "end_call")
    assert end_call.parameters.properties == {}


def _loud_frame(samples: int = 400) -> bytes:
    # Constant 512 LSB amplitude: RMS well above the bridge's speech threshold.
    return (512).to_bytes(2, "little") * samples


def _media_message(payload: bytes) -> str:
    return json.dumps({"event": "media", "media": {"payload": base64.b64encode(payload).decode()}})


def _server_content(*, interrupted=False, turn_complete=False, audio=False, caller_text=None):
    return type("Content", (), {
        "turn_complete": turn_complete,
        "interrupted": interrupted,
        "input_transcription": type("T", (), {"text": caller_text})() if caller_text else None,
        "output_transcription": None,
        "model_turn": type("Turn", (), {"parts": [type("Part", (), {
            "inline_data": type("Audio", (), {"data": b"\x00\x00" * 1600})()})()]})() if audio else None,
    })()


class _RecordingSocket:
    """Exotel leg: replays given messages, records everything the bridge sends."""

    def __init__(self, messages=(), stop_after=None):
        self.messages = list(messages)
        self.sent = []
        self.stop_after = stop_after
        self.closed = False

    def __aiter__(self):
        async def drive():
            for message in self.messages:
                yield message
            if self.stop_after is None:
                await asyncio.Event().wait()
            else:
                await self.stop_after.wait()
            yield json.dumps({"event": "stop"})
        return drive()

    async def send(self, message):
        self.sent.append(json.loads(message))

    async def close(self):
        self.closed = True


class _MutedGemini:
    """Gemini leg: replays given responses, then stays open like a live session."""

    def __init__(self, responses=(), delivered=None):
        self.responses = list(responses)
        self.delivered = delivered
        self.received = []

    async def send_realtime_input(self, audio):
        self.received.append(audio.data)

    async def receive(self):
        for response in self.responses:
            yield response
        if self.delivered is not None:
            self.delivered.set()
        await asyncio.Event().wait()


def test_live_bridge_skips_malformed_frames_without_dropping_the_call():
    websocket = _RecordingSocket([
        json.dumps({"event": "media", "media": {"payload": "not!base64"}}),
        _media_message(_loud_frame()),
        json.dumps({"event": "stop"}),
    ])
    gemini = _MutedGemini()

    session = asyncio.run(LiveVoiceBridge().run(
        websocket, ExotelCallMetadata("case-1", "thread-1", "call-1"), gemini
    ))

    assert session.metadata.call_id == "call-1"
    assert len(gemini.received) == 1
    assert len(gemini.received[0]) == len(_loud_frame()) * 2


def test_live_bridge_reports_inbound_audio_level_for_quiet_callers():
    """Peak inbound level separates a silent telephony leg from a quiet caller.

    Both look identical in the counters ("no speech frames") but need opposite
    fixes, so the bridge has to report the level it actually received.
    """
    quiet = (200).to_bytes(2, "little") * 400  # below the 350 speech gate
    websocket = _RecordingSocket([
        _media_message(quiet),
        _media_message(quiet),
        _media_message(_loud_frame()),
        json.dumps({"event": "stop"}),
    ])
    gemini = _MutedGemini()

    session = asyncio.run(LiveVoiceBridge().run(
        websocket, ExotelCallMetadata("case-1", "thread-1", "call-1"), gemini
    ))

    snapshot = session.latency_snapshot
    assert snapshot["inbound_rms_peak"] == 512.0
    assert snapshot["transport"]["inbound_rms"]["count"] == 3
    assert snapshot["speech_frames_received"] == 1


def test_live_bridge_clears_queued_exotel_audio_on_barge_in():
    delivered = asyncio.Event()
    websocket = _RecordingSocket(stop_after=delivered)
    gemini = _MutedGemini([
        type("Response", (), {"server_content": _server_content(interrupted=True), "tool_call": None})(),
        type("Response", (), {"server_content": _server_content(turn_complete=True), "tool_call": None})(),
    ], delivered=delivered)

    asyncio.run(LiveVoiceBridge().run(
        websocket,
        ExotelCallMetadata("case-1", "thread-1", "call-1", stream_sid="stream-1"),
        gemini,
    ))

    clears = [message for message in websocket.sent if message["event"] == "clear"]
    assert clears == [{"event": "clear", "stream_sid": "stream-1"}]


def test_live_bridge_defers_transcript_writes_and_flushes_them_by_call_end():
    class RecordingTranscriptLogger:
        def __init__(self):
            self.fragments = []
            self.turns_finished = 0

        def add_transcript(self, role, text):
            self.fragments.append((role, text))

        def finish_turn(self):
            self.turns_finished += 1
            return {"CALLER": "he is allergic to coconut"}

        def event(self, name, details=""):
            return None

    delivered = asyncio.Event()
    transcript_logger = RecordingTranscriptLogger()
    gemini = _MutedGemini([
        type("Response", (), {
            "server_content": _server_content(turn_complete=True, caller_text="allergic"),
            "tool_call": None,
        })(),
    ], delivered=delivered)

    session = asyncio.run(LiveVoiceBridge().run(
        _RecordingSocket(stop_after=delivered),
        ExotelCallMetadata("case-1", "thread-1", "call-1"),
        gemini,
        transcript_logger=transcript_logger,
    ))

    assert transcript_logger.fragments == [("CALLER", "allergic")]
    assert transcript_logger.turns_finished == 1
    assert {"role": "CALLER", "text": "he is allergic to coconut"} in session.transcript_messages


def test_latency_metrics_record_per_turn_playout_latency():
    metrics = VoiceLatencyMetrics()
    metrics.mark_media(is_speech=True)
    metrics.mark_gemini_input()
    metrics.mark_media(is_speech=True)
    metrics.mark_gemini_response()
    metrics.mark_gemini_audio(chunk_bytes=9600)
    metrics.mark_exotel_audio()

    record = metrics.close_turn("turn_complete")

    assert record["outcome"] == "turn_complete"
    assert record["caller_end_to_playout_ms"] is not None
    assert record["gemini_audio_to_playout_ms"] is not None
    snapshot = metrics.snapshot()
    assert snapshot["counters"]["turns_recorded"] == 1
    assert snapshot["turn_latency"]["caller_end_to_playout_ms"]["count"] == 1
    assert snapshot["transport"]["outbound_chunk_bytes"]["max_ms"] == 9600.0
    assert metrics.close_turn("turn_complete") is None


def test_voice_metrics_ignore_speech_that_barged_into_the_greeting():
    """`greeting_to_first_caller_audio_ms` measured against pre-greeting speech
    reported -73 s on a live call."""
    metrics = VoiceLatencyMetrics()
    metrics.mark_media(is_speech=True, frame_bytes=320, rms=900.0)
    metrics.mark_greeting_complete()
    assert metrics.snapshot()["greeting_to_first_caller_audio_ms"] is None

    metrics.mark_media(is_speech=True, frame_bytes=320, rms=900.0)
    assert metrics.snapshot()["greeting_to_first_caller_audio_ms"] >= 0