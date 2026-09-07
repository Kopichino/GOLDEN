import pytest
from datetime import datetime, timezone
from src.state.schema import (
    GoldenCaseState,
    CaseIdentityInput,
    IncidentLocation,
    TriageOutput,
    HospitalCandidate,
    HospitalFhirOutput,
    VoiceFamilyOutput,
    ControlAudit,
)

def test_golden_case_state_instantiation():
    case_input = CaseIdentityInput(
        case_id="CASE-2026-TEST-001",
        caller_phone="+919876543210",
        raw_input="Two vehicle collision on GST Road near Tambaram flyover. Rider unconscious, bleeding heavily.",
        language="en",
        modality="text",
        location=IncidentLocation(
            latitude=12.9249,
            longitude=80.1000,
            address_or_landmark="Tambaram Flyover, GST Road, Chennai",
            district="Chennai"
        )
    )

    control = ControlAudit(
        current_node="entry",
        execution_stage="INGESTION",
        thread_id="thread-test-001"
    )

    state = GoldenCaseState(
        input_data=case_input,
        control_audit=control
    )

    assert state.input_data.case_id == "CASE-2026-TEST-001"
    assert state.triage.acuity_level is None
    assert state.triage.hard_sos is False
    assert state.hospital_fhir.bed_status == "NONE"
    assert state.voice_family.call_status == "IDLE"
    assert state.control_audit.current_node == "entry"

def test_json_roundtrip_serialization():
    case_input = CaseIdentityInput(
        case_id="CASE-2026-TEST-002",
        raw_input="Auto rickshaw overturned near Guindy Kathipara.",
        location=IncidentLocation(
            latitude=13.0067,
            longitude=80.2030,
            address_or_landmark="Kathipara Junction, Chennai"
        )
    )
    control = ControlAudit(
        current_node="coordinator",
        execution_stage="INGESTION",
        thread_id="thread-test-002"
    )
    state = GoldenCaseState(input_data=case_input, control_audit=control)

    # Test audit helpers
    state.add_audit_entry("hard_sos_rule_engine", "evaluated_incident", latency_ms=12.5, details={"matched": False})
    state.record_error("triage_agent", "ValidationError", "Missing acuity rationale", recovered=True)

    json_str = state.model_dump_json()
    assert "CASE-2026-TEST-002" in json_str
    assert "hard_sos_rule_engine" in json_str

    restored = GoldenCaseState.model_validate_json(json_str)
    assert restored.input_data.case_id == state.input_data.case_id
    assert len(restored.control_audit.audit_trail) == 1
    assert len(restored.control_audit.errors) == 1
    assert restored.control_audit.errors[0].recovered is True

def test_validation_bounds():
    # Confidence must be between 0.0 and 1.0
    with pytest.raises(Exception):
        TriageOutput(confidence=1.5)

    with pytest.raises(Exception):
        TriageOutput(confidence=-0.1)

    # Acuity must match Literal
    with pytest.raises(Exception):
        TriageOutput(acuity_level="PURPLE")
