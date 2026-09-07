import pytest
from src.agents.triage import TriageAgent
from src.state.schema import GoldenCaseState, CaseIdentityInput, IncidentLocation, ControlAudit

def test_triage_agent_classification():
    agent = TriageAgent()
    res = agent.triage_incident(
        incident_text="Pedestrian tripped on curb, minor superficial scratch on palm, walking normally, no dizziness.",
        location_text="T. Nagar, Chennai"
    )
    assert res.acuity_level in ["GREEN", "YELLOW"]
    assert res.confidence >= 0.7
    assert len(res.rationale) > 10
    assert "AIIMS" in res.guideline_reference or "MoRTH" in res.guideline_reference

def test_triage_agent_state_update():
    state = GoldenCaseState(
        input_data=CaseIdentityInput(
            case_id="CASE-TRIAGE-TEST-01",
            raw_input="Car collision at Kathipara junction. Driver conscious but reports severe chest wall tenderness from steering wheel impact.",
            location=IncidentLocation(
                latitude=13.0067,
                longitude=80.2030,
                address_or_landmark="Kathipara Junction"
            )
        ),
        control_audit=ControlAudit(
            current_node="triage_agent",
            execution_stage="PARALLEL_TRIAGE_HOSPITAL",
            thread_id="triage-test-thread"
        )
    )

    agent = TriageAgent()
    updated_state = agent.run(state)

    assert updated_state.triage.acuity_level in ["RED", "YELLOW"]
    assert len(updated_state.control_audit.audit_trail) >= 1
    assert updated_state.control_audit.audit_trail[-1].agent_name == "triage_agent"
