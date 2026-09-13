"""Tests verifying the Target Architecture Refactoring for GOLDEN.

Covers:
1. Deterministic Hard-SOS immediate RED routing and immediate escalation.
2. Two-stage Hospital flow: Stage 1 Discovery (independent of acuity) -> Stage 2 Matching (dependent on triage acuity).
3. Separated HospitalDiscovery, HospitalMatcher, and FhirToolService classes and their HospitalAgent facade.
4. Acuity-driven deterministic ranking with explainable machine-readable reason.
5. Family Communication specialist workflow with TRAI consent enforcement.
6. Human Dispatcher review and auditable override persistence.
7. Node execution timings and parallelism tracking (is_parallel=True) in control_audit.
8. Backward compatibility aliases (GoldenCoordinator, FamilyCommunicationWorkflow).
"""

import pytest
from src.agents.coordinator import GoldenOrchestrator, GoldenCoordinator
from src.agents.hospital import (
    HospitalDiscovery,
    HospitalMatcher,
    FhirToolService,
    HospitalAgent,
)
from src.voice.family_communication import FamilyCommunicationAgent, FamilyCommunicationWorkflow
from src.state.schema import (
    GoldenCaseState,
    CaseIdentityInput,
    IncidentLocation,
    ControlAudit,
)


def test_hard_sos_immediate_red_escalation():
    """Verify Hard-SOS triggers sub-millisecond bypass, assigns RED, and records escalation."""
    orchestrator = GoldenOrchestrator()
    state = GoldenCaseState(
        input_data=CaseIdentityInput(
            case_id="TEST-SOS-ARCH-01",
            caller_phone="+919840112233",
            raw_input="Elderly man collapsed at Guindy station, unresponsive, not breathing, no pulse! CPR in progress!",
            location=IncidentLocation(
                latitude=13.0067,
                longitude=80.2026,
                address_or_landmark="Guindy Railway Station"
            )
        ),
        control_audit=ControlAudit(
            current_node="entry",
            thread_id="thread-test-sos-arch-01"
        )
    )

    final_state = orchestrator.dispatch_case(state)

    # 1. Hard-SOS flags
    assert final_state.triage.hard_sos is True
    assert final_state.triage.acuity_level == "RED"
    assert final_state.triage.confidence == 1.0

    # 2. Audit trail records immediate escalation
    actions = [entry.action for entry in final_state.control_audit.audit_trail]
    assert "immediate_red_escalation" in actions

    # 3. Hospital matching executed with RED acuity
    assert final_state.hospital_fhir.selected_hospital_id is not None
    assert final_state.hospital_fhir.ranking_reason is not None
    assert "RED" in final_state.hospital_fhir.ranking_reason

    # 4. Node timings recorded
    assert "hard_sos_check_node" in final_state.control_audit.node_timings
    assert final_state.control_audit.node_timings["hard_sos_check_node"].latency_ms is not None
    assert "immediate_escalation_node" in final_state.control_audit.node_timings


def test_separated_hospital_services():
    """Verify HospitalDiscovery, HospitalMatcher, and FhirToolService function as decoupled components."""
    discovery = HospitalDiscovery()
    matcher = HospitalMatcher()
    lat, lon = 12.9249, 80.1000  # Tambaram

    # Stage 1: Spatial & capability discovery (no acuity needed)
    raw_candidates = discovery.discover_candidates(lat, lon)
    assert len(raw_candidates) >= 3
    assert all(c.score == 0.0 for c in raw_candidates)

    # Stage 2: Acuity-based matching
    red_ranked, red_reason = matcher.match_and_rank(raw_candidates, acuity_level="RED")
    yellow_ranked, yellow_reason = matcher.match_and_rank(raw_candidates, acuity_level="YELLOW")

    assert len(red_ranked) == len(raw_candidates)
    assert len(yellow_ranked) == len(raw_candidates)
    assert "RED" in red_reason
    assert "YELLOW" in yellow_reason
    assert red_ranked[0].score > 0.0

    # Facade delegation check
    facade = HospitalAgent()
    assert facade.discovery is not None
    assert facade.matcher is not None
    assert facade.fhir_service is not None


def test_two_stage_hospital_discovery_and_matching():
    """Verify Stage 1 discovery does not require acuity, while Stage 2 matching is acuity-sensitive."""
    agent = HospitalAgent()
    lat, lon = 12.9249, 80.1000  # Tambaram

    # Stage 1: Discovery (raw capabilities & distances)
    raw_candidates = agent.discover_candidates(lat, lon)
    assert len(raw_candidates) >= 3
    # Distance sorted
    assert raw_candidates[0].distance_km <= raw_candidates[-1].distance_km
    for c in raw_candidates:
        assert c.score == 0.0

    # Stage 2: Acuity Matching
    red_ranked, red_reason = agent.match_and_rank(raw_candidates, acuity_level="RED")
    yellow_ranked, yellow_reason = agent.match_and_rank(raw_candidates, acuity_level="YELLOW")

    assert len(red_ranked) == len(raw_candidates)
    assert len(yellow_ranked) == len(raw_candidates)
    assert "RED" in red_reason
    assert "YELLOW" in yellow_reason

    # Top candidate scores should be non-zero
    assert red_ranked[0].score != 0.0
    assert yellow_ranked[0].score != 0.0


def test_dependency_aware_non_sos_workflow_and_timings():
    """Verify non-SOS flow executes parallel triage + discovery before matching and tracks is_parallel=True."""
    orchestrator = GoldenOrchestrator()
    thread_id = "thread-arch-dep-02"
    state = GoldenCaseState(
        input_data=CaseIdentityInput(
            case_id="TEST-DEP-002",
            caller_phone="+919840223344",
            raw_input="Passenger with minor superficial scratch on finger after auto stopped abruptly. Walking normally.",
            location=IncidentLocation(
                latitude=13.0400,
                longitude=80.2500,
                address_or_landmark="T. Nagar Signal"
            )
        ),
        control_audit=ControlAudit(
            current_node="entry",
            thread_id=thread_id
        )
    )

    final_state = orchestrator.dispatch_case(state)

    # 1. Triage classified as non-urgent
    assert final_state.triage.hard_sos is False
    assert final_state.triage.acuity_level in ["GREEN", "YELLOW"]

    # 2. Hospital selected based on the non-urgent acuity
    assert final_state.hospital_fhir.selected_hospital_name is not None
    assert final_state.hospital_fhir.ranking_reason is not None

    # 3. Node timings recorded including is_parallel=True on parallel branches
    timings = final_state.control_audit.node_timings
    assert "hard_sos_check_node" in timings
    assert "hospital_matching_node" in timings
    assert "fhir_service_node" in timings
    assert "family_communication_node" in timings
    assert "consolidation_node" in timings

    # Parallel branch timings recorded at Join Barrier
    assert "triage_agent_node" in timings
    assert timings["triage_agent_node"].is_parallel is True
    assert timings["triage_agent_node"].latency_ms is not None
    assert timings["triage_agent_node"].latency_ms > 0

    assert "hospital_discovery_node" in timings
    assert timings["hospital_discovery_node"].is_parallel is True
    assert timings["hospital_discovery_node"].latency_ms is not None
    assert timings["hospital_discovery_node"].latency_ms > 0


def test_family_communication_specialist_workflow():
    """Verify FamilyCommunicationAgent enforces consent and handles webhook disclosures."""
    family_agent = FamilyCommunicationAgent()

    # Unauthorized test number -> consent refused
    outreach = family_agent.execute_outreach(
        case_id="CASE-VOICE-001",
        recipient_phone="+910000000000"
    )
    assert outreach["status"] == "CONSENT_REFUSED"
    assert outreach["consent_granted"] is False

    # Empty phone -> IDLE
    idle_outreach = family_agent.execute_outreach(
        case_id="CASE-VOICE-002",
        recipient_phone=None
    )
    assert idle_outreach["status"] == "IDLE"

    # Webhook disclosure parsing
    disclosure = family_agent.process_webhook_disclosure(
        call_id="CALL-123",
        call_status="COMPLETED",
        allergies=["Aspirin", "Ibuprofen"],
        medications=["Amlodipine 5mg"],
        blood_group="O-",
        conditions=["Hypertension"],
        summary="Family member confirmed patient is allergic to NSAIDs.",
        duration_sec=65
    )
    assert disclosure.call_status == "COMPLETED"
    assert "Aspirin" in disclosure.allergies
    assert disclosure.blood_group == "O-"
    assert disclosure.call_duration_seconds == 65


def test_human_dispatcher_override_persistence():
    """Verify dispatcher can override acuity and target hospital with auditable notes."""
    orchestrator = GoldenOrchestrator()
    thread_id = "thread-override-003"
    state = GoldenCaseState(
        input_data=CaseIdentityInput(
            case_id="TEST-OVERRIDE-003",
            caller_phone="+919840112233",
            raw_input="Two-wheeler collision at Chromepet. Leg laceration with moderate pain.",
            location=IncidentLocation(
                latitude=12.9516,
                longitude=80.1410,
                address_or_landmark="Chromepet"
            )
        ),
        control_audit=ControlAudit(
            current_node="entry",
            thread_id=thread_id
        )
    )

    dispatched = orchestrator.dispatch_case(state)
    original_acuity = dispatched.triage.acuity_level

    # Apply override: elevate to RED with operational justification
    updated_state = orchestrator.apply_dispatcher_override(
        thread_id=thread_id,
        field="acuity_level",
        new_value="RED",
        dispatcher_notes="Caller reported secondary loss of consciousness while ambulance en route."
    )

    assert updated_state is not None
    assert updated_state.triage.acuity_level == "RED"

    # Check that override is recorded in human_overrides list
    assert len(updated_state.control_audit.human_overrides) >= 1
    rec = updated_state.control_audit.human_overrides[-1]
    assert rec.field_overridden == "acuity_level"
    assert rec.old_value == original_acuity
    assert rec.new_value == "RED"
    assert "loss of consciousness" in rec.dispatcher_notes

    # Check that override action is also in general audit trail
    actions = [a.action for a in updated_state.control_audit.audit_trail]
    assert "override_acuity_level" in actions


def test_backward_compatibility_aliases():
    """Verify GoldenCoordinator and FamilyCommunicationWorkflow work identically as aliases."""
    coord = GoldenCoordinator()
    assert isinstance(coord, GoldenOrchestrator)

    workflow = FamilyCommunicationWorkflow()
    assert isinstance(workflow, FamilyCommunicationAgent)
