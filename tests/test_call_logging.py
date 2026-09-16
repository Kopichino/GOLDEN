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
