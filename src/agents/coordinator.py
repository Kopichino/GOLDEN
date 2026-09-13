"""GOLDEN Orchestrator: Dependency-Aware Emergency Coordination Workflow.

Implements the central state machine in LangGraph.
Architectural Principles:
1. The Orchestrator is a workflow state machine, NOT an AI agent.
2. Hard-SOS is a deterministic sub-millisecond safety engine, NOT an AI agent.
3. In Normal (non-SOS) flow: Triage Agent (clinical LLM) and Hospital Discovery (FHIR retrieval)
   run in parallel because discovery does not require triage reasoning.
4. Hospital Matching executes AFTER triage completes, using validated clinical acuity.
5. FHIR Pre-Registration is a tool service executed on the selected hospital.
6. Family Communication is a specialist workflow enforcing TRAI consent guardrails.
7. Human Dispatcher retains final review and override authority.
"""

from datetime import datetime, timezone
import time
from typing import Dict, Any, Optional, List, Callable, Tuple
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from src.state.schema import (
    GoldenCaseState,
    HospitalFhirOutput,
    VoiceFamilyOutput,
    ControlAudit,
    NodeExecutionTiming,
)
from src.agents.hard_sos import HardSosEngine
from src.agents.triage import TriageAgent
from src.agents.hospital import (
    HospitalDiscovery,
    HospitalMatcher,
    FhirToolService,
    HospitalAgent,
)
from src.voice.family_communication import FamilyCommunicationAgent, FamilyCommunicationWorkflow
from src.voice.exotel_client import ExotelClient
from src.safety.guardrails import (
    PIISanitizer,
    PromptInjectionDetector,
    InterAgentContractGuard,
)


class GoldenOrchestrator:
    """State machine controller coordinating specialized emergency dispatch workflows."""

    def __init__(
        self,
        triage_agent: Optional[TriageAgent] = None,
        hospital_agent: Optional[HospitalAgent] = None,
        hospital_discovery: Optional[HospitalDiscovery] = None,
        hospital_matcher: Optional[HospitalMatcher] = None,
        fhir_service: Optional[FhirToolService] = None,
        family_agent: Optional[FamilyCommunicationAgent] = None,
        exotel_client: Optional[ExotelClient] = None,
        event_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ):
        self.triage_agent = triage_agent or TriageAgent()
        self.hospital_agent = hospital_agent or HospitalAgent()
        self.hospital_discovery = hospital_discovery or getattr(self.hospital_agent, "discovery", HospitalDiscovery())
        self.hospital_matcher = hospital_matcher or getattr(self.hospital_agent, "matcher", HospitalMatcher())
        self.fhir_service = fhir_service or getattr(self.hospital_agent, "fhir_service", FhirToolService())
        self.exotel_client = exotel_client or ExotelClient()
        self.family_agent = family_agent or FamilyCommunicationAgent(exotel_client=self.exotel_client)
        self.event_callback = event_callback
        self.checkpointer = MemorySaver()
        self.app = self._build_graph()

    def emit_event(self, stage: str, case_id: str, payload: Dict[str, Any]) -> None:
        """Broadcast live workflow events to subscribers/dashboard."""
        if self.event_callback:
            try:
                self.event_callback({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "case_id": case_id,
                    "stage": stage,
                    "data": payload
                })
            except Exception:
                pass

    def _build_graph(self):
        graph = StateGraph(GoldenCaseState)

        # -------------------------------------------------------------
        # 1. Hard-SOS Safety Check Node
        # -------------------------------------------------------------
        def hard_sos_check_node(state: GoldenCaseState) -> Dict[str, Any]:
            start_time = time.perf_counter()
            has_injection, patterns = PromptInjectionDetector.check_input(state.input_data.raw_input)
            is_sos, triggers, rationale, engine_latency = HardSosEngine.evaluate(state.input_data.raw_input)

            elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
            triage_copy = state.triage.model_copy()
            control_copy = state.control_audit.model_copy()
            control_copy.current_node = "hard_sos_check_node"
            control_copy.execution_stage = "HARD_SOS_CHECK"

            control_copy.node_timings["hard_sos_check_node"] = NodeExecutionTiming(
                node_name="hard_sos_check_node",
                started_at=datetime.now(timezone.utc),
                ended_at=datetime.now(timezone.utc),
                latency_ms=elapsed_ms,
                is_parallel=False
            )

            if has_injection:
                control_copy.errors.append({
                    "node": "hard_sos_check_node",
                    "error_type": "PROMPT_INJECTION_FLAGGED",
                    "message": f"Potential prompt injection flagged: {patterns}",
                    "recovered": True
                })

            if is_sos:
                triage_copy.hard_sos = True
                triage_copy.hard_sos_triggers = triggers
                triage_copy.acuity_level = "RED"
                triage_copy.confidence = 1.0
                triage_copy.rationale = rationale
                triage_copy.guideline_reference = "MoRTH Road Accident Golden Hour Deterministic Protocol 2025"
                triage_copy.triage_completed_at = datetime.now(timezone.utc)

            self.emit_event("HARD_SOS_CHECK", state.input_data.case_id, {
                "hard_sos": is_sos,
                "triggers": triggers,
                "latency_ms": elapsed_ms,
                "injection_flagged": has_injection
            })

            return {"triage": triage_copy, "control_audit": control_copy}

        # -------------------------------------------------------------
        # 2. Immediate Escalation Node (Hard-SOS critical bypass path)
        # -------------------------------------------------------------
        def immediate_escalation_node(state: GoldenCaseState) -> Dict[str, Any]:
            esc_start = time.perf_counter()
            control_copy = state.control_audit.model_copy()
            control_copy.current_node = "immediate_escalation_node"
            control_copy.execution_stage = "HARD_SOS_CHECK"
            control_copy.add_audit_entry(
                agent_name="hard_sos_safety_engine",
                action="immediate_red_escalation",
                details={
                    "rationale": state.triage.rationale,
                    "triggers": state.triage.hard_sos_triggers,
                    "action_required": "Immediate dispatcher priority & zero-delay routing"
                }
            )
            esc_elapsed = round((time.perf_counter() - esc_start) * 1000.0, 2)
            control_copy.node_timings["immediate_escalation_node"] = NodeExecutionTiming(
                node_name="immediate_escalation_node",
                started_at=datetime.now(timezone.utc),
                ended_at=datetime.now(timezone.utc),
                latency_ms=esc_elapsed,
                is_parallel=False
            )
            self.emit_event("IMMEDIATE_ESCALATION", state.input_data.case_id, {
                "acuity": "RED",
                "reason": state.triage.rationale
            })
            return {"control_audit": control_copy}

        # -------------------------------------------------------------
        # 3. Fan-Out Bridge Node (Normal path)
        # -------------------------------------------------------------
        def fan_out_node(state: GoldenCaseState) -> Dict[str, Any]:
            fo_start = time.perf_counter()
            control_copy = state.control_audit.model_copy()
            control_copy.current_node = "fan_out_node"
            control_copy.execution_stage = "PARALLEL_TRIAGE_DISCOVERY"
            fo_elapsed = round((time.perf_counter() - fo_start) * 1000.0, 2)
            control_copy.node_timings["fan_out_node"] = NodeExecutionTiming(
                node_name="fan_out_node",
                started_at=datetime.now(timezone.utc),
                ended_at=datetime.now(timezone.utc),
                latency_ms=fo_elapsed,
                is_parallel=False
            )
            return {"control_audit": control_copy}

        # -------------------------------------------------------------
        # 4. Triage Agent Node (Clinical Reasoning) - Parallel Branch A
        # -------------------------------------------------------------
        def triage_agent_node(state: GoldenCaseState) -> Dict[str, Any]:
            t_start = time.perf_counter()
            triage_res = self.triage_agent.triage_incident(
                incident_text=state.input_data.raw_input,
                location_text=state.input_data.location.address_or_landmark
            )
            validated_triage = InterAgentContractGuard.sanitize_triage_payload(
                triage_res.model_dump(),
                state.input_data.raw_input
            )
            t_elapsed = round((time.perf_counter() - t_start) * 1000.0, 2)
            validated_triage.latency_ms = t_elapsed

            self.emit_event("TRIAGE_COMPLETE", state.input_data.case_id, {
                "acuity_level": validated_triage.acuity_level,
                "confidence": validated_triage.confidence,
                "guideline": validated_triage.guideline_reference,
                "latency_ms": t_elapsed
            })

            # Note: Returns ONLY 'triage' to prevent LangGraph concurrent write collision on control_audit
            return {"triage": validated_triage}

        # -------------------------------------------------------------
        # 5. Hospital Discovery Node - Parallel Branch B
        # -------------------------------------------------------------
        def hospital_discovery_node(state: GoldenCaseState) -> Dict[str, Any]:
            d_start = time.perf_counter()
            raw_candidates = self.hospital_discovery.discover_candidates(
                incident_lat=state.input_data.location.latitude,
                incident_lon=state.input_data.location.longitude
            )
            d_elapsed = round((time.perf_counter() - d_start) * 1000.0, 2)

            hosp_copy = state.hospital_fhir.model_copy()
            hosp_copy.raw_candidates = raw_candidates
            hosp_copy.discovery_latency_ms = d_elapsed

            self.emit_event("HOSPITAL_DISCOVERY_COMPLETE", state.input_data.case_id, {
                "discovered_count": len(raw_candidates),
                "nearest_hospital": raw_candidates[0].name if raw_candidates else None,
                "nearest_distance_km": raw_candidates[0].distance_km if raw_candidates else None,
                "latency_ms": d_elapsed
            })

            # Note: Returns ONLY 'hospital_fhir' to prevent LangGraph concurrent write collision on control_audit
            return {"hospital_fhir": hosp_copy}

        # -------------------------------------------------------------
        # 6. Hospital Matching Node (Join Barrier)
        # -------------------------------------------------------------
        def hospital_matching_node(state: GoldenCaseState) -> Dict[str, Any]:
            m_start = time.perf_counter()
            control_copy = state.control_audit.model_copy()
            control_copy.current_node = "hospital_matching_node"
            control_copy.execution_stage = "HOSPITAL_MATCHING"

            # Populate parallel branch timings from state schemas into control_audit
            if state.triage.latency_ms is not None:
                control_copy.node_timings["triage_agent_node"] = NodeExecutionTiming(
                    node_name="triage_agent_node",
                    started_at=datetime.now(timezone.utc),
                    ended_at=datetime.now(timezone.utc),
                    latency_ms=state.triage.latency_ms,
                    is_parallel=True
                )
            if state.hospital_fhir.discovery_latency_ms is not None:
                control_copy.node_timings["hospital_discovery_node"] = NodeExecutionTiming(
                    node_name="hospital_discovery_node",
                    started_at=datetime.now(timezone.utc),
                    ended_at=datetime.now(timezone.utc),
                    latency_ms=state.hospital_fhir.discovery_latency_ms,
                    is_parallel=True
                )

            # Use validated clinical acuity (from Triage Agent or Hard-SOS)
            acuity = state.triage.acuity_level or ("RED" if state.triage.hard_sos else "YELLOW")

            raw = state.hospital_fhir.raw_candidates
            if not raw:
                raw = self.hospital_discovery.discover_candidates(
                    incident_lat=state.input_data.location.latitude,
                    incident_lon=state.input_data.location.longitude
                )

            candidates, reason = self.hospital_matcher.match_and_rank(raw, acuity)

            hosp_copy = state.hospital_fhir.model_copy()
            hosp_copy.raw_candidates = raw
            hosp_copy.candidate_hospitals = candidates

            if not candidates:
                fallback = InterAgentContractGuard.sanitize_hospital_payload({})
                hosp_copy.selected_hospital_id = fallback.selected_hospital_id
                hosp_copy.selected_hospital_name = fallback.selected_hospital_name
                hosp_copy.ranking_reason = "Fallback hospital selected due to empty registry"
                hosp_copy.bed_status = "REQUESTED"
            else:
                top = candidates[0]
                hosp_copy.selected_hospital_id = top.hospital_id
                hosp_copy.selected_hospital_name = top.name
                hosp_copy.ranking_reason = reason
                hosp_copy.bed_status = "REQUESTED"

            m_elapsed = round((time.perf_counter() - m_start) * 1000.0, 2)
            control_copy.node_timings["hospital_matching_node"] = NodeExecutionTiming(
                node_name="hospital_matching_node",
                started_at=datetime.now(timezone.utc),
                ended_at=datetime.now(timezone.utc),
                latency_ms=m_elapsed,
                is_parallel=False
            )

            self.emit_event("HOSPITAL_MATCHED", state.input_data.case_id, {
                "hospital_id": hosp_copy.selected_hospital_id,
                "name": hosp_copy.selected_hospital_name,
                "ranking_reason": hosp_copy.ranking_reason,
                "latency_ms": m_elapsed
            })

            return {"hospital_fhir": hosp_copy, "control_audit": control_copy}

        # -------------------------------------------------------------
        # 7. FHIR Service Node (Pre-Registration Tool Layer)
        # -------------------------------------------------------------
        def fhir_service_node(state: GoldenCaseState) -> Dict[str, Any]:
            f_start = time.perf_counter()
            control_copy = state.control_audit.model_copy()
            control_copy.current_node = "fhir_service_node"
            control_copy.execution_stage = "FHIR_REGISTRATION"

            hosp_copy = state.hospital_fhir.model_copy()
            candidates = hosp_copy.candidate_hospitals

            if candidates:
                selected = candidates[0]
                try:
                    bundle_id, p_id, enc_id, cond_id = self.fhir_service.pre_register_patient(state, selected)
                    hosp_copy.fhir_bundle_id = bundle_id
                    hosp_copy.fhir_patient_id = p_id
                    hosp_copy.fhir_encounter_id = enc_id
                    hosp_copy.fhir_condition_id = cond_id
                    hosp_copy.fhir_submission_status = "SUCCESS"
                    hosp_copy.fhir_submission_timestamp = datetime.now(timezone.utc)
                    hosp_copy.bed_status = "CONFIRMED"
                except Exception as e:
                    hosp_copy.fhir_submission_status = "FAILED"
                    control_copy.errors.append({
                        "node": "fhir_service_node",
                        "error_type": "FHIR_SUBMISSION_FAILED",
                        "message": str(e),
                        "recovered": True
                    })
            else:
                hosp_copy.fhir_submission_status = "FAILED"

            f_elapsed = round((time.perf_counter() - f_start) * 1000.0, 2)
            control_copy.node_timings["fhir_service_node"] = NodeExecutionTiming(
                node_name="fhir_service_node",
                started_at=datetime.now(timezone.utc),
                ended_at=datetime.now(timezone.utc),
                latency_ms=f_elapsed,
                is_parallel=False
            )

            self.emit_event("FHIR_REGISTRATION_COMPLETE", state.input_data.case_id, {
                "bundle_id": hosp_copy.fhir_bundle_id,
                "patient_id": hosp_copy.fhir_patient_id,
                "encounter_id": hosp_copy.fhir_encounter_id,
                "status": hosp_copy.fhir_submission_status
            })

            return {"hospital_fhir": hosp_copy, "control_audit": control_copy}

        # -------------------------------------------------------------
        # 8. Family Communication Specialist Node
        # -------------------------------------------------------------
        def family_communication_node(state: GoldenCaseState) -> Dict[str, Any]:
            v_start = time.perf_counter()
            control_copy = state.control_audit.model_copy()
            control_copy.current_node = "family_communication_node"
            control_copy.execution_stage = "VOICE_DISPATCH"

            phone_to_call = state.voice_family.recipient_phone or state.input_data.caller_phone
            outreach = self.family_agent.execute_outreach(
                case_id=state.input_data.case_id,
                recipient_phone=phone_to_call,
                callback_url="http://localhost:8000/webhook/call-outcome"
            )

            voice_copy = state.voice_family.model_copy()
            voice_copy.call_status = outreach["status"]
            voice_copy.call_id = outreach.get("call_id")
            voice_copy.recipient_phone = outreach.get("recipient_phone")
            voice_copy.consent_granted = outreach.get("consent_granted")

            v_elapsed = round((time.perf_counter() - v_start) * 1000.0, 2)
            control_copy.node_timings["family_communication_node"] = NodeExecutionTiming(
                node_name="family_communication_node",
                started_at=datetime.now(timezone.utc),
                ended_at=datetime.now(timezone.utc),
                latency_ms=v_elapsed,
                is_parallel=False
            )

            self.emit_event("FAMILY_OUTREACH_TRIGGERED", state.input_data.case_id, {
                "call_id": voice_copy.call_id,
                "recipient": PIISanitizer.sanitize(phone_to_call or ""),
                "status": voice_copy.call_status,
                "message": outreach.get("message")
            })

            return {"voice_family": voice_copy, "control_audit": control_copy}

        # -------------------------------------------------------------
        # 9. Consolidation Node
        # -------------------------------------------------------------
        def consolidation_node(state: GoldenCaseState) -> Dict[str, Any]:
            c_start = time.perf_counter()
            control_copy = state.control_audit.model_copy()
            control_copy.current_node = "consolidation_node"

            phone_to_call = state.voice_family.recipient_phone or state.input_data.caller_phone
            if phone_to_call:
                control_copy.execution_stage = "AWAITING_WEBHOOK"
            else:
                control_copy.execution_stage = "DISPATCHER_REVIEW"
                control_copy.completed_at = datetime.now(timezone.utc)

            c_elapsed = round((time.perf_counter() - c_start) * 1000.0, 2)
            control_copy.node_timings["consolidation_node"] = NodeExecutionTiming(
                node_name="consolidation_node",
                started_at=datetime.now(timezone.utc),
                ended_at=datetime.now(timezone.utc),
                latency_ms=c_elapsed,
                is_parallel=False
            )

            self.emit_event("CASE_CONSOLIDATED", state.input_data.case_id, {
                "stage": control_copy.execution_stage,
                "acuity": state.triage.acuity_level,
                "hospital": state.hospital_fhir.selected_hospital_name,
                "call_status": state.voice_family.call_status
            })

            return {"control_audit": control_copy}

        # -------------------------------------------------------------
        # Graph Construction & Edges
        # -------------------------------------------------------------
        graph.add_node("hard_sos_check_node", hard_sos_check_node)
        graph.add_node("immediate_escalation_node", immediate_escalation_node)
        graph.add_node("fan_out_node", fan_out_node)
        graph.add_node("triage_agent_node", triage_agent_node)
        graph.add_node("hospital_discovery_node", hospital_discovery_node)
        graph.add_node("hospital_matching_node", hospital_matching_node)
        graph.add_node("fhir_service_node", fhir_service_node)
        graph.add_node("family_communication_node", family_communication_node)
        graph.add_node("consolidation_node", consolidation_node)

        # Ingestion -> Hard-SOS Check
        graph.add_edge(START, "hard_sos_check_node")

        def route_after_sos(state: GoldenCaseState) -> str:
            if state.triage.hard_sos:
                return "sos_path"
            return "normal_path"

        graph.add_conditional_edges(
            "hard_sos_check_node",
            route_after_sos,
            {
                "sos_path": "immediate_escalation_node",
                "normal_path": "fan_out_node"
            }
        )

        # SOS Path: Immediate Escalation -> Discovery -> Matching
        graph.add_edge("immediate_escalation_node", "hospital_discovery_node")

        # Normal Path: Parallel Fan-Out to Triage & Hospital Discovery
        graph.add_edge("fan_out_node", "triage_agent_node")
        graph.add_edge("fan_out_node", "hospital_discovery_node")

        # Join Barrier: Both Triage and Discovery join into Hospital Matching
        graph.add_edge("triage_agent_node", "hospital_matching_node")
        graph.add_edge("hospital_discovery_node", "hospital_matching_node")

        # Downstream operational flow: Matching -> FHIR -> Family -> Consolidation -> END
        graph.add_edge("hospital_matching_node", "fhir_service_node")
        graph.add_edge("fhir_service_node", "family_communication_node")
        graph.add_edge("family_communication_node", "consolidation_node")
        graph.add_edge("consolidation_node", END)

        return graph.compile(checkpointer=self.checkpointer)

    def dispatch_case(self, initial_state: GoldenCaseState) -> GoldenCaseState:
        """Run the initial dispatch cycle up to webhook wait or completion."""
        thread_id = initial_state.control_audit.thread_id
        config = {"configurable": {"thread_id": thread_id}}
        final_state_dict = self.app.invoke(initial_state, config=config)
        return GoldenCaseState.model_validate(final_state_dict)

    def resume_from_voice_webhook(
        self,
        thread_id: str,
        call_id: str,
        call_status: str,
        allergies: Optional[List[str]] = None,
        medications: Optional[List[str]] = None,
        blood_group: Optional[str] = None,
        conditions: Optional[List[str]] = None,
        summary: Optional[str] = None,
        duration_sec: Optional[int] = None
    ) -> bool:
        """Resume paused workflow checkpoint upon arrival of telephony webhook."""
        config = {"configurable": {"thread_id": thread_id}}
        current_checkpoint = self.app.get_state(config)
        if not current_checkpoint or not current_checkpoint.values:
            return False

        current_state = GoldenCaseState.model_validate(current_checkpoint.values)

        # Process disclosure via specialist agent
        disclosure = self.family_agent.process_webhook_disclosure(
            call_id=call_id,
            call_status=call_status,
            allergies=allergies,
            medications=medications,
            blood_group=blood_group,
            conditions=conditions,
            summary=summary,
            duration_sec=duration_sec
        )

        current_state.voice_family = disclosure
        current_state.control_audit.execution_stage = "COMPLETED"
        current_state.control_audit.completed_at = datetime.now(timezone.utc)
        current_state.add_audit_entry(
            agent_name="family_communication_agent",
            action="resumed_from_webhook",
            details={
                "call_id": call_id,
                "allergies": disclosure.allergies,
                "medications": disclosure.medications,
                "blood_group": disclosure.blood_group,
                "call_duration_seconds": disclosure.call_duration_seconds
            }
        )

        self.app.update_state(config, current_state)
        self.emit_event("CASE_COMPLETED", current_state.input_data.case_id, {
            "status": "COMPLETED_VIA_WEBHOOK",
            "allergies": disclosure.allergies,
            "medications": disclosure.medications,
            "blood_group": disclosure.blood_group
        })
        return True

    def apply_dispatcher_override(
        self,
        thread_id: str,
        field: str,
        new_value: str,
        dispatcher_notes: str
    ) -> Optional[GoldenCaseState]:
        """Apply human-in-the-loop override and record it into the audit trail."""
        config = {"configurable": {"thread_id": thread_id}}
        current_checkpoint = self.app.get_state(config)
        if not current_checkpoint or not current_checkpoint.values:
            return None

        current_state = GoldenCaseState.model_validate(current_checkpoint.values)
        old_val = None

        if field == "acuity_level":
            old_val = current_state.triage.acuity_level
            current_state.triage.acuity_level = new_value  # type: ignore
        elif field == "selected_hospital_id":
            old_val = current_state.hospital_fhir.selected_hospital_id
            current_state.hospital_fhir.selected_hospital_id = new_value
            # Match name if in candidates
            for c in current_state.hospital_fhir.candidate_hospitals:
                if c.hospital_id == new_value:
                    current_state.hospital_fhir.selected_hospital_name = c.name
                    break

        current_state.record_human_override(field, old_val, new_value, dispatcher_notes)
        self.app.update_state(config, current_state)

        self.emit_event("DISPATCHER_OVERRIDE", current_state.input_data.case_id, {
            "field": field,
            "old_value": old_val,
            "new_value": new_value,
            "notes": dispatcher_notes
        })
        return current_state


# Backward-compatible alias for existing imports
GoldenCoordinator = GoldenOrchestrator
