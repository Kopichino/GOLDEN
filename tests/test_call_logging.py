"""Tests for Exotel call logging, family-history FHIR update, and status webhooks."""

import pytest
from fastapi.testclient import TestClient

from src.voice import call_log
from src.voice.exotel_client import ExotelClient
from src.fhir.bundle_builder import FhirBundleBuilder
from src.agents.hospital import FhirToolService
from src.dashboard.server import app


@pytest.fixture(autouse=True)
def isolated_call_log(tmp_path, monkeypatch):
    """Point the durable call-log store at a temp file for every test."""
    monkeypatch.setattr(call_log, "CALL_LOG_FILE", tmp_path / "voice_call_logs.json")
    yield


def test_call_log_records_full_lifecycle():
    call_log.record_call_trigger(
        call_id="call-log-1",
        case_id="GOLDEN-TEST-LOG-1",
        thread_id="thread-GOLDEN-TEST-LOG-1",
        recipient_phone="+919840012345",
        provider="exotel",
        status="TRIGGERED",
        consent_basis="On-scene identification",
        triggered_by="driver_on_scene",
    )
    call_log.record_call_status("call-log-1", "IN_PROGRESS", source="voice_server")
    call_log.attach_exotel_status("call-log-1", {"CallSid": "call-log-1", "Status": "in-progress"})
    call_log.attach_outcome("call-log-1", {
        "call_status": "COMPLETED",
        "call_duration_seconds": 64,
        "transcript_path": "logs/voice/x.log",
        "latency": {"caller_audio_to_exotel_ms": 900},
        "allergies": ["Penicillin"],
    })

    entry = call_log.find_call_by_id("call-log-1")
    assert entry is not None
    assert entry["case_id"] == "GOLDEN-TEST-LOG-1"
    assert entry["status"] == "COMPLETED"
    assert entry["call_duration_seconds"] == 64
    assert entry["transcript_path"].endswith(".log")
    assert entry["latency"]["caller_audio_to_exotel_ms"] == 900
    assert any(e["status"] == "EXOTEL_in-progress" for e in entry["status_history"])
    assert entry["outcome"]["allergies"] == ["Penicillin"]

    assert call_log.get_calls(case_id="GOLDEN-TEST-LOG-1")[0]["call_id"] == "call-log-1"
    assert call_log.get_calls(case_id="UNKNOWN") == []


def test_exotel_client_logs_simulated_trigger(monkeypatch):
    monkeypatch.setattr("src.config.settings.VOICE_SIMULATION_ONLY", True)

    client = ExotelClient()
    result = client.trigger_outbound_call(
        recipient_phone="+919840099999",
        case_id="GOLDEN-TEST-LOG-2",
        thread_id="thread-GOLDEN-TEST-LOG-2",
        consent_basis="On-scene identification by ambulance crew",
        triggered_by="driver_on_scene",
    )

    assert result["status"] == "TRIGGERED"
    entry = call_log.find_call_by_id(result["call_id"])
    assert entry is not None
    assert entry["provider"] == "local_simulation"
    assert entry["triggered_by"] == "driver_on_scene"
    assert entry["consent_basis"] == "On-scene identification by ambulance crew"


def test_family_history_bundle_builds_expected_resources():
    bundle = FhirBundleBuilder.create_family_history_bundle(
        patient_id="patient-1",
        encounter_id="encounter-1",
        allergies=["Penicillin"],
        medications=["Metformin 500mg"],
        blood_group="O+",
        conditions=["Diabetes"],
        summary="Stable on medication",
    )

    types = [entry["resource"]["resourceType"] for entry in bundle["entry"]]
    assert types.count("AllergyIntolerance") == 1
    assert types.count("MedicationStatement") == 1
    assert types.count("Observation") == 2  # blood group + summary
    assert types.count("Condition") == 1

    condition = next(e["resource"] for e in bundle["entry"] if e["resource"]["resourceType"] == "Condition")
    assert condition["encounter"]["reference"] == "Encounter/encounter-1"
    assert condition["verificationStatus"]["coding"][0]["code"] == "unconfirmed"

    blood = next(e["resource"] for e in bundle["entry"] if e["resource"]["resourceType"] == "Observation" and "valueString" in e["resource"] and e["resource"]["code"]["text"] == "Blood group")
    assert blood["valueString"] == "O+"


def test_family_history_submission_skips_and_fails_gracefully():
    service = FhirToolService()

    skipped = service.submit_family_history_update(None, None, [], [], None, [], None)
    assert skipped["status"] == "SKIPPED"

    class ExplodingClient:
        def submit_bundle(self, bundle):
            raise RuntimeError("HAPI down")

    failing = FhirToolService(fhir_client=ExplodingClient())
    failed = failing.submit_family_history_update(
        "patient-1", "encounter-1", ["Penicillin"], [], "O+", [], None
    )
    assert failed["status"] == "FAILED"


def test_exotel_status_webhook_logs_unknown_call():
    client = TestClient(app)
    res = client.post(
        "/webhook/exotel-status",
        data={"CallSid": "call-status-webhook-1", "Status": "no-answer", "Duration": "0"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "LOGGED"

    entry = call_log.find_call_by_id("call-status-webhook-1")
    assert entry is not None
    assert entry["exotel_last_status"] == "no-answer"


def test_call_outcome_webhook_refreshes_dashboard_case(monkeypatch):
    """Collected family history has to reach the in-memory case the pages render.

    The resume writes the LangGraph checkpoint, but every dashboard view reads
    ``active_cases``, so a checkpoint-only update leaves the UI frozen on the
    pre-call state forever.
    """
    from types import SimpleNamespace

    from src.dashboard import server
    from src.state.schema import (
        CaseIdentityInput,
        ControlAudit,
        GoldenCaseState,
        IncidentLocation,
    )

    case_id = "GOLDEN-TEST-SYNC-1"
    thread_id = f"thread-{case_id}"
    before = GoldenCaseState(
        input_data=CaseIdentityInput(
            case_id=case_id,
            caller_phone="+919840012345",
            raw_input="Two-wheeler skidded on wet asphalt.",
            location=IncidentLocation(
                latitude=12.9, longitude=80.1, address_or_landmark="Test Junction"
            ),
        ),
        control_audit=ControlAudit(thread_id=thread_id, execution_stage="AWAITING_WEBHOOK"),
    )
    after = before.model_copy(deep=True)
    after.voice_family.call_status = "COMPLETED"
    after.voice_family.allergies = ["Penicillin"]
    after.voice_family.blood_group = "O+"

    monkeypatch.setattr(server, "active_cases", {case_id: before})
    monkeypatch.setattr(server, "event_history", [])
    monkeypatch.setattr(server, "coordinator", SimpleNamespace(
        app=SimpleNamespace(get_state=lambda config: SimpleNamespace(values=after.model_dump()))
    ))
    monkeypatch.setattr(server, "handle_call_outcome", lambda payload, coord: {"status": "RESUMED"})
    monkeypatch.setattr(server.callback_security, "validate", lambda *a, **k: (True, None))

    response = TestClient(app).post(
        "/webhook/call-outcome",
        json={
            "thread_id": thread_id,
            "case_id": case_id,
            "call_id": "call-sync-1",
            "call_status": "COMPLETED",
            "allergies": ["Penicillin"],
            "blood_group": "O+",
        },
    )

    assert response.status_code == 200
    assert response.json() == {"status": "RESUMED"}
    rendered = server.active_cases[case_id].voice_family
    assert rendered.allergies == ["Penicillin"]
    assert rendered.blood_group == "O+"
    broadcast = server.event_history[-1]
    assert broadcast["event_type"] == "FAMILY_CALL_OUTCOME"
    assert broadcast["voice_family"]["allergies"] == ["Penicillin"]


def test_call_outcome_webhook_ignores_cases_the_dashboard_does_not_hold(monkeypatch):
    """A callback for an unknown case must not invent dashboard state."""
    from types import SimpleNamespace

    from src.dashboard import server

    monkeypatch.setattr(server, "active_cases", {})
    monkeypatch.setattr(server, "event_history", [])
    monkeypatch.setattr(server, "coordinator", SimpleNamespace(
        app=SimpleNamespace(get_state=lambda config: SimpleNamespace(values=None))
    ))
    monkeypatch.setattr(server, "handle_call_outcome", lambda payload, coord: {"status": "RESUMED"})
    monkeypatch.setattr(server.callback_security, "validate", lambda *a, **k: (True, None))

    response = TestClient(app).post(
        "/webhook/call-outcome",
        json={"thread_id": "thread-ghost", "case_id": "GHOST-CASE", "call_id": "call-ghost"},
    )

    assert response.status_code == 200
    assert server.event_history == []
