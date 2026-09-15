"""Tests for Option 1: Mobile Paramedic / Driver Companion View (/driver/{ticket_id})."""

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
)

client = TestClient(app)

@pytest.fixture
def seeded_case_with_ambulance():
    """Seed an active case with an allocated ambulance unit for driver companion tests."""
    case_id = "GOLDEN-TEST-DRIVER-01"
    ticket_id = "CALLOUT-108-DRIV01"
    
    unit = AmbulanceUnit(
        unit_id="AMB-108-01",
        vehicle_number="TN-07-G-1081",
        unit_type="ALS",
        base_station="Tambaram Sanatorium 108 Hub",
        latitude=12.9340,
        longitude=80.1280,
        status="DISPATCHED",
        crew_lead_paramedic="Rajesh Kumar (EMT-P)",
        pilot_driver="M. Venkatesh",
        pilot_contact="+91 94441 10801",
        equipment_manifest=["Transport Ventilator", "Biphasic Defibrillator"],
        distance_to_scene_km=4.8,
        eta_to_scene_minutes=6.5,
        routing_source="OSRM"
    )

    hosp = HospitalCandidate(
        hospital_id="HOSP-GLENEAGLES",
        name="Gleneagles HealthCity Chennai",
        trauma_level="LEVEL_1",
        latitude=12.9150,
        longitude=80.2000,
        distance_km=8.0,
        driving_distance_km=8.5,
        eta_minutes=9.2,
        available_icu_beds=24,
        available_er_beds=12,
        routing_source="OSRM",
        route_geometry=[[12.9249, 80.1472], [12.9150, 80.2000]]
    )

    state = GoldenCaseState(
        input_data=CaseIdentityInput(
            case_id=case_id,
            caller_phone="+91 94441 23456",
            raw_input="High-speed motorcycle collision on Tambaram Flyover, open femur fracture, heavy bleeding.",
            location=IncidentLocation(
                latitude=12.9249,
                longitude=80.1472,
                address_or_landmark="Tambaram Flyover, GST Road",
                district="Chennai"
            )
        ),
        triage=TriageOutput(
            acuity_level="RED",
            hard_sos=True,
            clinical_summary="Critical femur trauma with arterial threat"
        ),
        hospital_fhir=HospitalFhirOutput(
            selected_hospital_id="HOSP-GLENEAGLES",
            selected_hospital_name="Gleneagles HealthCity Chennai",
            candidate_hospitals=[hosp],
            bed_status="CONFIRMED"
        ),
        ambulance_dispatch=AmbulanceDispatchOutput(
            dispatch_status="DISPATCHED",
            mission_status="DISPATCHED",
            selected_unit=unit,
            candidate_units=[unit],
            callout_ticket_id=ticket_id,
            dispatch_timestamp=datetime.now(timezone.utc),
            acuity_demanded="ALS",
            turn_by_turn_instructions=["Depart Tambaram Hub", "Proceed to Tambaram Flyover"],
            paramedic_handover_notes="Critical RED airway stabilization protocol"
        ),
        control_audit=ControlAudit(
            thread_id=f"thread-{case_id}",
            active_provider="gemini",
            execution_stage="COMPLETED"
        )
    )

    active_cases[case_id] = state
    return case_id, ticket_id

def test_driver_companion_page_serves_html(seeded_case_with_ambulance):
    case_id, ticket_id = seeded_case_with_ambulance
    
    # Test access via ticket_id
    res1 = client.get(f"/driver/{ticket_id}")
    assert res1.status_code == 200
    assert "text/html" in res1.headers["content-type"]
    assert "108 CAD" in res1.text
    
    # Test access via CAD alias
    res2 = client.get(f"/cad/driver/{ticket_id}")
    assert res2.status_code == 200
    assert "text/html" in res2.headers["content-type"]

def test_driver_mission_api_payload(seeded_case_with_ambulance):
    case_id, ticket_id = seeded_case_with_ambulance
    
    # Can query by ticket_id or case_id
    res = client.get(f"/api/driver/{ticket_id}")
    assert res.status_code == 200
    data = res.json()
    
    assert data["ticket_id"] == ticket_id
    assert data["case_id"] == case_id
    assert data["mission_status"] == "DISPATCHED"
    assert data["acuity_level"] == "RED"
    assert data["unit"]["unit_id"] == "AMB-108-01"
    assert data["unit"]["unit_type"] == "ALS"
    assert data["crew"]["lead_paramedic"] == "Rajesh Kumar (EMT-P)"
    assert data["incident"]["address"] == "Tambaram Flyover, GST Road"
    assert data["hospital"]["name"] == "Gleneagles HealthCity Chennai"
    assert len(data["turn_by_turn_instructions"]) > 0

def test_driver_milestone_progression_lifecycle(seeded_case_with_ambulance):
    case_id, ticket_id = seeded_case_with_ambulance
    
    # 1. Acknowledge Mission
    res1 = client.post(f"/api/driver/{ticket_id}/status", json={"status": "ACKNOWLEDGED", "notes": "Pilot acknowledged"})
    assert res1.status_code == 200
    assert res1.json()["mission_status"] == "ACKNOWLEDGED"
    
    # 2. En route to Scene
    res2 = client.post(f"/api/driver/{ticket_id}/status", json={"status": "EN_ROUTE_SCENE"})
    assert res2.status_code == 200
    assert res2.json()["mission_status"] == "EN_ROUTE_SCENE"
    
    # 3. Arrived On Scene
    res3 = client.post(f"/api/driver/{ticket_id}/status", json={"status": "ON_SCENE"})
    assert res3.status_code == 200
    assert res3.json()["mission_status"] == "ON_SCENE"
    
    # 4. Patient Loaded
    res4 = client.post(f"/api/driver/{ticket_id}/status", json={"status": "PATIENT_LOADED"})
    assert res4.status_code == 200
    assert res4.json()["mission_status"] == "PATIENT_LOADED"
    
    # 5. Arrived at ED / Handover Complete
    res5 = client.post(f"/api/driver/{ticket_id}/status", json={"status": "HANDOVER_COMPLETE"})
    assert res5.status_code == 200
    assert res5.json()["mission_status"] == "HANDOVER_COMPLETE"
    assert res5.json()["events_count"] >= 5

def test_driver_invalid_status_rejected(seeded_case_with_ambulance):
    case_id, ticket_id = seeded_case_with_ambulance
    res = client.post(f"/api/driver/{ticket_id}/status", json={"status": "INVALID_MILESTONE_XYZ"})
    assert res.status_code == 400
    assert "Invalid status" in res.json()["detail"]

def test_driver_unknown_ticket_404():
    res = client.get("/api/driver/NON_EXISTENT_TICKET")
    assert res.status_code == 404

def test_driver_qr_code_generation(seeded_case_with_ambulance):
    case_id, ticket_id = seeded_case_with_ambulance
    res = client.get(f"/api/driver/{ticket_id}/qr")
    assert res.status_code == 200
    assert "image/svg+xml" in res.headers["content-type"]
    assert f"/driver/{ticket_id}" in res.headers.get("x-target-url", "")
    assert "<svg" in res.text

