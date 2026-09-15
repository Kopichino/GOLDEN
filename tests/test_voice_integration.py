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