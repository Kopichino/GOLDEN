"""Tests for On-Scene Victim Identity & Next-of-Kin Contact Discovery Pipeline."""

import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from src.dashboard.server import app, active_cases
from src.state.schema import (
    GoldenCaseState,
    CaseIdentityInput,
    IncidentLocation,
    ControlAudit,
    TriageOutput,
    HospitalFhirOutput,
    HospitalCandidate,
    AmbulanceDispatchOutput,
    AmbulanceUnit,
    VoiceFamilyOutput,
)

client = TestClient(app)

@pytest.fixture
def seeded_case_on_scene():
    """Seed an active case with an ambulance on scene."""
    case_id = "GOLDEN-TEST-ONSCENE-01"
    ticket_id = "CALLOUT-108-SCENE01"

    unit = AmbulanceUnit(
        unit_id="AMB-108-01",
        vehicle_number="TN-07-G-1081",
        unit_type="ALS",
        base_station="Tambaram Sanatorium 108 Hub",
        latitude=12.9340,
        longitude=80.1280,
        status="ON_SCENE",
        crew_lead_paramedic="Rajesh Kumar (EMT-P)",
        pilot_driver="M. Venkatesh",
        pilot_contact="+91 94441 10801",
        equipment_manifest=["Transport Ventilator", "Defibrillator"],
        distance_to_scene_km=4.8,
        eta_to_scene_minutes=6.5
    )

    state = GoldenCaseState(
        input_data=CaseIdentityInput(
            case_id=case_id,
            caller_phone="+91 94441 00000", # Bystander phone
            raw_input="Motorcycle collision on GST road, unconscious rider.",
            location=IncidentLocation(
                latitude=12.9249,
                longitude=80.1472,
                address_or_landmark="Tambaram Flyover",
                district="Chennai"
            )
        ),
        triage=TriageOutput(acuity_level="RED", hard_sos=True),
        hospital_fhir=HospitalFhirOutput(
            selected_hospital_name="Gleneagles HealthCity Chennai",
            bed_status="CONFIRMED"
        ),
        ambulance_dispatch=AmbulanceDispatchOutput(
            dispatch_status="DISPATCHED",
            mission_status="ON_SCENE",
            selected_unit=unit,
            callout_ticket_id=ticket_id
        ),
        voice_family=VoiceFamilyOutput(
            call_status="IDLE",
            next_of_kin_phone=None
        ),
        control_audit=ControlAudit(
            thread_id=f"thread-{case_id}",
            active_provider="groq",
            execution_stage="COMPLETED"
        )
    )

    active_cases[case_id] = state
    return case_id, ticket_id

def test_on_scene_identification_submission_success(seeded_case_on_scene):
    case_id, ticket_id = seeded_case_on_scene

    payload = {
        "patient_name": "Rajesh Kumar",
        "id_source": "Smartphone Lock-screen ICE",
        "relationship": "Parent (Father)",
        "next_of_kin_phone": "+91 98400 55555",
        "clinical_notes": "Father verified via emergency contact card on locked iPhone"
    }

    res = client.post(f"/api/driver/{ticket_id}/identification", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert data["success"] is True
    assert data["patient_name"] == "Rajesh Kumar"
    assert data["next_of_kin_phone"] == "+91 98400 55555"
    assert data["call_status"] == "TRIGGERED"

    # Verify state in memory
    updated_state = active_cases[case_id]
    assert updated_state.voice_family.next_of_kin_phone == "+91 98400 55555"
    assert updated_state.voice_family.call_status == "TRIGGERED"

    # Verify audit event in mission events
    events = updated_state.ambulance_dispatch.mission_events
    assert any(e.get("status") == "ON_SCENE_ID_DISCOVERED" for e in events)

def test_on_scene_identification_invalid_phone(seeded_case_on_scene):
    case_id, ticket_id = seeded_case_on_scene

    payload = {
        "patient_name": "Rajesh Kumar",
        "id_source": "Smartphone Lock-screen ICE",
        "relationship": "Parent",
        "next_of_kin_phone": "123" # Too short
    }

    res = client.post(f"/api/driver/{ticket_id}/identification", json=payload)
    assert res.status_code == 400
    assert "Invalid next-of-kin phone number" in res.json()["detail"]

def test_on_scene_identification_unknown_ticket():
    res = client.post("/api/driver/NON_EXISTENT_TICKET/identification", json={
        "patient_name": "Test",
        "id_source": "Wallet",
        "relationship": "Friend",
        "next_of_kin_phone": "+91 98400 11111"
    })
    assert res.status_code == 404
