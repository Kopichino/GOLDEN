import pytest
from src.agents.hospital import HospitalAgent, haversine_distance
from src.state.schema import GoldenCaseState, CaseIdentityInput, IncidentLocation, ControlAudit, TriageOutput

def test_haversine_distance():
    # Chennai Central (13.0827, 80.2707) to Guindy (13.0067, 80.2030) is ~11-12 km
    dist = haversine_distance(13.0827, 80.2707, 13.0067, 80.2030)
    assert 10.0 <= dist <= 13.0

def test_hospital_agent_ranking_and_pre_registration():
    state = GoldenCaseState(
        input_data=CaseIdentityInput(
            case_id="CASE-HOSP-TEST-01",
            raw_input="High-speed head-on collision near Chromepet GST Road.",
            caller_phone="+919840112233",
            location=IncidentLocation(
                latitude=12.9516,
                longitude=80.1410,
                address_or_landmark="Chromepet GST Road",
                district="Chengalpattu"
            )
        ),
        triage=TriageOutput(
            acuity_level="RED",
            hard_sos=True,
            confidence=1.0,
            rationale="Immediate life threat"
        ),
        control_audit=ControlAudit(
            current_node="hospital_agent",
            execution_stage="PARALLEL_TRIAGE_HOSPITAL",
            thread_id="test-hospital-thread"
        )
    )

    agent = HospitalAgent()
    updated_state = agent.run(state)

    assert len(updated_state.hospital_fhir.candidate_hospitals) >= 1
    assert updated_state.hospital_fhir.selected_hospital_id is not None
    assert updated_state.hospital_fhir.bed_status == "CONFIRMED"
    assert updated_state.hospital_fhir.fhir_submission_status == "SUCCESS"
    assert updated_state.hospital_fhir.fhir_patient_id is not None
    assert updated_state.hospital_fhir.fhir_encounter_id is not None
    assert updated_state.hospital_fhir.fhir_condition_id is not None
