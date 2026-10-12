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

def test_coordinator_parallel_fanout_and_webhook_resumption(monkeypatch):
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

    # 2. Family call is deferred: no call yet, workflow waits for the
    #    ambulance crew to trigger outreach from the driver dashboard.
    assert dispatched_state.control_audit.execution_stage == "AWAITING_FAMILY_CONTACT"
    assert dispatched_state.voice_family.call_status == "IDLE"
    assert dispatched_state.voice_family.call_id is None

    # 3. Driver dashboard triggers the family voice call on scene
    monkeypatch.setattr("src.config.settings.VOICE_SIMULATION_ONLY", True)
    triggered = coordinator.trigger_family_outreach(
        case_id=dispatched_state.input_data.case_id,
        recipient_phone="+919840223344",
        thread_id=thread_id,
        relationship="Spouse",
        consent_basis="On-scene identification by ambulance crew",
        triggered_by="driver_on_scene",
    )
    assert triggered["success"] is True
    assert triggered["status"] == "TRIGGERED"
    assert triggered["call_id"] is not None
    checkpoint_mid = coordinator.app.get_state({"configurable": {"thread_id": thread_id}})
    mid_state = GoldenCaseState.model_validate(checkpoint_mid.values)
    assert mid_state.voice_family.call_status == "TRIGGERED"
    assert mid_state.voice_family.call_triggered_by == "driver_on_scene"
    assert mid_state.control_audit.execution_stage == "AWAITING_WEBHOOK"

    # 4. Webhook arrives with next-of-kin information
    resumed = coordinator.resume_from_voice_webhook(
        thread_id=thread_id,
        call_id=triggered["call_id"],
        call_status="COMPLETED",
        allergies=["Penicillin", "Peanuts"],
        medications=["Metformin 500mg"],
        blood_group="O+",
        summary="Spouse confirmed patient identity, noted severe penicillin allergy, requested admission at nearest facility.",
        duration_sec=75
    )
    assert resumed is True

    # 5. Check resumed state in checkpointer
    checkpoint = coordinator.app.get_state({"configurable": {"thread_id": thread_id}})
    resumed_state = GoldenCaseState.model_validate(checkpoint.values)
    assert resumed_state.control_audit.execution_stage == "COMPLETED"
    assert "Penicillin" in resumed_state.voice_family.allergies
    assert resumed_state.voice_family.blood_group == "O+"
    assert resumed_state.voice_family.call_duration_seconds == 75
    # Attribution recorded at driver-trigger time survives the webhook merge
    assert resumed_state.voice_family.call_triggered_by == "driver_on_scene"
    # ...and so does the contact the crew identified, which the dashboard displays
    assert resumed_state.voice_family.recipient_relationship == "Spouse"
    assert "+919840223344" in (
        resumed_state.voice_family.next_of_kin_phone or "",
        resumed_state.voice_family.recipient_phone or "",
    )
    # Family history is pushed to FHIR (or failed gracefully when HAPI is down)
    assert resumed_state.voice_family.fhir_update_status in ["SUCCESS", "FAILED"]
