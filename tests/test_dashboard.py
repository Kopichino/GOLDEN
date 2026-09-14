"""Tests for Phase 2 Live Emergency Dispatcher Dashboard server."""

import pytest
from fastapi.testclient import TestClient
from src.dashboard.server import app, active_cases
from src.state.schema import GoldenCaseState, CaseIdentityInput, IncidentLocation, ControlAudit

client = TestClient(app)

def test_dashboard_index_serves_html():
    response = client.get("/")
    assert response.status_code == 200
    assert "GOLDEN" in response.text
    assert "text/html" in response.headers["content-type"]

def test_dashboard_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ONLINE"
    assert "active_cases_count" in data

def test_dashboard_presets():
    response = client.get("/api/presets")
    assert response.status_code == 200
    presets = response.json()["presets"]
    assert "tambaram_femur_crash" in presets
    assert "guindy_cardiac_arrest" in presets

def test_dashboard_case_lifecycle_and_override():
    # 1. Create a dummy case in active_cases
    case_id = "GOLDEN-TEST-999"
    thread_id = f"thread-{case_id}"
    state = GoldenCaseState(
        input_data=CaseIdentityInput(
            case_id=case_id,
            raw_input="Test high impact road crash.",
            location=IncidentLocation(
                latitude=12.92,
                longitude=80.14,
                address_or_landmark="Tambaram Signal"
            )
        ),
        control_audit=ControlAudit(
            thread_id=thread_id
        )
    )
    active_cases[case_id] = state

    # 2. Query case via API
    res_get = client.get(f"/api/cases/{case_id}")
    assert res_get.status_code == 200
    assert res_get.json()["input_data"]["case_id"] == case_id

    # 3. Apply human dispatcher override
    res_override = client.post(
        f"/api/cases/{case_id}/override",
        json={
            "acuity_level": "RED",
            "selected_hospital_id": "HOSP-01",
            "selected_hospital_name": "Government Hospital Chromepet",
            "dispatcher_notes": "Immediate resuscitation needed per supervisor order."
        }
    )
    assert res_override.status_code == 200
    assert res_override.json()["status"] == "OVERRIDDEN"

    # Verify state was updated
    updated_state = active_cases[case_id]
    assert updated_state.triage.acuity_level == "RED"
    assert updated_state.hospital_fhir.selected_hospital_name == "Government Hospital Chromepet"
    # Verify audit log entry was added
    assert len(updated_state.control_audit.audit_trail) >= 1
    assert updated_state.control_audit.audit_trail[-1].agent_name == "human_dispatcher"

def test_dashboard_analytics_endpoint():
    res = client.get("/api/analytics")
    assert res.status_code == 200
    data = res.json()
    assert "total_cases" in data
    assert "acuity_distribution" in data
    assert "RED" in data["acuity_distribution"]
    assert "YELLOW" in data["acuity_distribution"]
    assert "GREEN" in data["acuity_distribution"]
    assert "metrics" in data
    assert "avg_latency_ms" in data["metrics"]
    assert "under_triage_rate_pct" in data["metrics"]

def test_dashboard_case_handover_slip_and_export():
    case_id = "GOLDEN-TEST-HANDOVER-01"
    state = GoldenCaseState(
        input_data=CaseIdentityInput(
            case_id=case_id,
            raw_input="Motorcycle crash on GST road with right thigh arterial bleed.",
            caller_phone="+919840112233",
            location=IncidentLocation(
                latitude=12.9516,
                longitude=80.1410,
                address_or_landmark="Chromepet GST Road"
            )
        ),
        control_audit=ControlAudit(
            thread_id=f"thread-{case_id}"
        )
    )
    state.triage.acuity_level = "RED"
    state.triage.rationale = "Arterial hemorrhage requires immediate Level-1 trauma care."
    state.hospital_fhir.selected_hospital_name = "Government Hospital Chromepet"
    state.hospital_fhir.bed_status = "CONFIRMED"
    active_cases[case_id] = state

    # Test Handover slip
    res_slip = client.get(f"/api/cases/{case_id}/handover")
    assert res_slip.status_code == 200
    slip = res_slip.json()
    assert slip["case_id"] == case_id
    assert slip["document_type"] == "MoRTH_AIIMS_PREHOSPITAL_HANDOVER_SLIP"
    assert slip["clinical_triage"]["acuity_level"] == "RED"
    assert slip["receiving_facility"]["hospital_name"] == "Government Hospital Chromepet"

    # Test Full Audit Export
    res_export = client.get("/api/audit/export")
    assert res_export.status_code == 200
    export_data = res_export.json()
    assert "cases" in export_data
    assert any(c["input_data"]["case_id"] == case_id for c in export_data["cases"])

