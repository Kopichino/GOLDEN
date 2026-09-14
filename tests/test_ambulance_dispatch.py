"""
Unit and Integration Tests for Option 2: Ambulance Fleet CAD Dispatch (ALS vs. BLS)
Verifies:
1. Fleet registry querying and capability profiles.
2. Acuity-driven matching: RED -> ALS, YELLOW/GREEN -> BLS.
3. OSRM-based transit calculation to scene.
4. Paramedic clinical handover note synthesis.
5. LangGraph orchestration pipeline integration.
6. API endpoint /api/cases/{case_id}/callout.
"""

import pytest
from starlette.testclient import TestClient
from src.agents.ambulance import AmbulanceFleetRegistry, AmbulanceAllocator
from src.agents.coordinator import GoldenCoordinator
from src.state.schema import (
    GoldenCaseState,
    CaseIdentityInput,
    IncidentLocation,
    ControlAudit,
    TriageOutput,
    HospitalFhirOutput,
    HospitalCandidate
)
from src.dashboard.server import app


def test_fleet_registry_inventory():
    """Verify registry has seeded Chennai South corridor ambulances with correct equipment."""
    fleet = AmbulanceFleetRegistry.get_fleet()
    assert len(fleet) == 5

    # Check AMB-108-01 (ALS at Tambaram)
    tambaram_unit = next(u for u in fleet if u["unit_id"] == "AMB-108-01")
    assert tambaram_unit["unit_type"] == "ALS"
    assert "Tambaram" in tambaram_unit["base_station"]
    assert any("ventilator" in eq.lower() for eq in tambaram_unit["equipment_manifest"])
    assert any("defibrillator" in eq.lower() for eq in tambaram_unit["equipment_manifest"])

    # Check AMB-108-02 (BLS at Chromepet)
    chromepet_unit = next(u for u in fleet if u["unit_id"] == "AMB-108-02")
    assert chromepet_unit["unit_type"] == "BLS"
    assert "Chromepet" in chromepet_unit["base_station"]
    assert any("aed" in eq.lower() for eq in chromepet_unit["equipment_manifest"])


def test_allocator_red_acuity_demands_als():
    """Verify RED acuity emergency always matches an ALS unit with ventilator & paramedic."""
    allocator = AmbulanceAllocator()
    state = GoldenCaseState(
        input_data=CaseIdentityInput(
            case_id="TEST-AMB-RED",
            raw_input="High-speed motorcycle collision at Tambaram flyover, unconscious and bleeding profusely.",
            location=IncidentLocation(latitude=12.9249, longitude=80.1472, address_or_landmark="Tambaram Signal, Chennai"),
            caller_phone="+91 94441 23456"
        ),
        control_audit=ControlAudit(
            current_node="ambulance_allocation",
            thread_id="test-amb-red"
        ),
        triage=TriageOutput(
            acuity_level="RED",
            confidence=0.98
        ),
        hospital_fhir=HospitalFhirOutput(
            selected_hospital_id="HOSP-SIMS",
            selected_hospital_name="SIMS Hospital",
            bed_status="CONFIRMED",
            candidate_hospitals=[
                HospitalCandidate(
                    hospital_id="HOSP-SIMS",
                    name="SIMS Hospital",
                    latitude=13.0180,
                    longitude=80.2070,
                    trauma_level="LEVEL_1",
                    available_icu_beds=5,
                    available_er_beds=8,
                    distance_km=12.4,
                    score=92.0
                )
            ]
        )
    )

    dispatch = allocator.allocate_ambulance(state)

    assert dispatch.dispatch_status == "DISPATCHED"
    assert dispatch.acuity_demanded in ["ALS", "RED"]
    assert dispatch.selected_unit is not None
    assert dispatch.selected_unit.unit_type == "ALS"
    assert "ALS" in dispatch.allocation_reason
    assert dispatch.callout_ticket_id.startswith("CALLOUT-108-")
    assert "SIMS Hospital" in dispatch.paramedic_handover_notes
    assert dispatch.selected_unit.eta_to_scene_minutes > 0
    assert dispatch.selected_unit.distance_to_scene_km > 0


def test_allocator_yellow_green_preserves_als_dispatches_bls():
    """Verify YELLOW and GREEN acuity emergencies dispatch BLS units to preserve ALS."""
    allocator = AmbulanceAllocator()
    state = GoldenCaseState(
        input_data=CaseIdentityInput(
            case_id="TEST-AMB-YELLOW",
            raw_input="Moderate ankle fracture after slip on pavement at Chromepet MIT gate.",
            location=IncidentLocation(latitude=12.9460, longitude=80.1400, address_or_landmark="Chromepet, Chennai"),
            caller_phone="+91 98840 55555"
        ),
        control_audit=ControlAudit(
            current_node="ambulance_allocation",
            thread_id="test-amb-yellow"
        ),
        triage=TriageOutput(
            acuity_level="YELLOW",
            confidence=0.92
        ),
        hospital_fhir=HospitalFhirOutput(
            selected_hospital_id="HOSP-CHROMEPET-GH",
            selected_hospital_name="Chromepet Government Hospital",
            bed_status="CONFIRMED"
        )
    )

    dispatch = allocator.allocate_ambulance(state)

    assert dispatch.dispatch_status == "DISPATCHED"
    assert dispatch.acuity_demanded in ["BLS", "YELLOW"]
    assert dispatch.selected_unit is not None
    assert dispatch.selected_unit.unit_type == "BLS"
    assert "BLS" in dispatch.allocation_reason
    assert "AMB-108-02" in dispatch.selected_unit.unit_id or "AMB-108-04" in dispatch.selected_unit.unit_id


def test_coordinator_pipeline_with_ambulance():
    """Verify GoldenCoordinator runs end-to-end with the new ambulance_allocation node."""
    coordinator = GoldenCoordinator()
    state = GoldenCaseState(
        input_data=CaseIdentityInput(
            case_id="TEST-PIPELINE-AMB",
            raw_input="Horrific motorcycle collision on GST road! Rider is unresponsive and bleeding heavily!",
            location=IncidentLocation(latitude=12.9249, longitude=80.1472, address_or_landmark="Tambaram Railway Station"),
            caller_phone="+91 94441 99999"
        ),
        control_audit=ControlAudit(
            current_node="entry",
            thread_id="test-pipeline-amb-thread"
        )
    )

    # Run full coordinator pipeline
    final_state = coordinator.dispatch_case(state)

    # Verify triage completed (Hard-SOS triggered for unresponsive rider)
    assert final_state.triage.acuity_level == "RED"

    # Verify hospital was matched
    assert final_state.hospital.selected_hospital_id is not None

    # Verify ambulance was allocated!
    assert final_state.ambulance.dispatch_status == "DISPATCHED"
    assert final_state.ambulance.selected_unit is not None
    assert final_state.ambulance.selected_unit.eta_to_scene_minutes > 0
    assert final_state.ambulance.callout_ticket_id.startswith("CALLOUT-108-")
    assert final_state.ambulance.selected_unit.unit_type == "ALS"


def test_dashboard_callout_ticket_api():
    """Verify GET /api/cases/{case_id}/callout returns full structured ticket."""
    client = TestClient(app)

    # Trigger a simulation to generate a case in dashboard memory
    sim_res = client.post(
        "/api/simulate",
        json={
            "custom_input": "Massive road traffic collision on GST Road Chromepet, two critically injured.",
            "landmark": "GST Road Chromepet, Chennai",
            "caller_phone": "+91 94441 12345",
            "latitude": 12.9516,
            "longitude": 80.1462
        }
    )
    assert sim_res.status_code == 200
    case_id = sim_res.json()["case_id"]

    # Now fetch the 108 CAD callout ticket
    callout_res = client.get(f"/api/cases/{case_id}/callout")
    assert callout_res.status_code == 200
    ticket = callout_res.json()

    assert ticket["case_id"] == case_id
    assert ticket["callout_ticket_id"].startswith("CALLOUT-108-")
    assert ticket["allocated_unit"] is not None
    assert ticket["allocated_unit"]["unit_type"] in ["ALS", "BLS"]
    assert ticket["crew_roster"]["lead_paramedic"] is not None
    assert ticket["destination_hospital"]["name"] is not None
    assert ticket["paramedic_handover_briefing"] is not None
