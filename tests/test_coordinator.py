import pytest
from src.agents.coordinator import GoldenCoordinator
from src.state.schema import GoldenCaseState, CaseIdentityInput, IncidentLocation, ControlAudit

def test_coordinator_hard_sos_bypass_flow():
    coordinator = GoldenCoordinator()
    state = GoldenCaseState(
        input_data=CaseIdentityInput(
            case_id="CASE-COORD-SOS-001",
            caller_phone="+919840112233",
            raw_input="Horrific motorcycle collision on GST road! Rider is unresponsive and bleeding heavily!",
            location=IncidentLocation(
                latitude=12.9516,
                longitude=80.1410,
                address_or_landmark="Chromepet, GST Road"
            )
        ),
        control_audit=ControlAudit(
            current_node="entry",
            thread_id="test-thread-sos-001"
        )
    )

    final_state = coordinator.dispatch_case(state)

    # 1. Hard-SOS check verified
    assert final_state.triage.hard_sos is True
    assert final_state.triage.acuity_level == "RED"
    assert final_state.triage.confidence == 1.0

    # 2. Hospital & FHIR write verified
    assert final_state.hospital_fhir.selected_hospital_id is not None
    assert final_state.hospital_fhir.bed_status == "CONFIRMED"
    assert final_state.hospital_fhir.fhir_submission_status == "SUCCESS"
    assert final_state.hospital_fhir.fhir_bundle_id is not None

    # 3. Voice safety contract verified
    assert final_state.voice_family.call_status in [
        "TRIGGERED", "IDLE", "CONSENT_REFUSED"
    ]
    if final_state.voice_family.call_status == "TRIGGERED":
        assert final_state.voice_family.call_id is not None
    else:
        assert final_state.voice_family.call_id is None

def test_coordinator_parallel_fanout_and_webhook_resumption():
    coordinator = GoldenCoordinator()
    thread_id = "test-thread-fanout-002"
    state = GoldenCaseState(
        input_data=CaseIdentityInput(
            case_id="CASE-COORD-FANOUT-002",
            caller_phone="+919840223344",
            raw_input="Car bumper collision at Anna Nagar. Driver has mild wrist pain and ankle sprain, conscious and alert.",
            location=IncidentLocation(
                latitude=13.0850,
                longitude=80.2100,
                address_or_landmark="Anna Nagar Roundtana, Chennai"
            )
        ),
        control_audit=ControlAudit(
            current_node="entry",
            thread_id=thread_id
        )
    )

    dispatched_state = coordinator.dispatch_case(state)

    # 1. Not Hard-SOS -> Guideline LLM triage ran
    assert dispatched_state.triage.hard_sos is False
    assert dispatched_state.triage.acuity_level in ["GREEN", "YELLOW"]
    assert dispatched_state.hospital_fhir.fhir_submission_status == "SUCCESS"

    # 2. State paused awaiting webhook
    assert dispatched_state.control_audit.execution_stage == "AWAITING_WEBHOOK"

    # 3. Webhook arrives with next-of-kin information
    resumed = coordinator.resume_from_voice_webhook(
        thread_id=thread_id,
        call_id=dispatched_state.voice_family.call_id or "EXO-SIM-001",
        call_status="COMPLETED",
        allergies=["Penicillin", "Peanuts"],
        medications=["Metformin 500mg"],
        blood_group="O+",
        summary="Spouse confirmed patient identity, noted severe penicillin allergy, requested admission at nearest facility.",
        duration_sec=75
    )
    assert resumed is True

    # 4. Check resumed state in checkpointer
    checkpoint = coordinator.app.get_state({"configurable": {"thread_id": thread_id}})
    resumed_state = GoldenCaseState.model_validate(checkpoint.values)
    assert resumed_state.control_audit.execution_stage == "COMPLETED"
    assert "Penicillin" in resumed_state.voice_family.allergies
    assert resumed_state.voice_family.blood_group == "O+"
    assert resumed_state.voice_family.call_duration_seconds == 75
