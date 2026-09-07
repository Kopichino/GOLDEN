from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Callable
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from src.state.schema import GoldenCaseState, HospitalFhirOutput
from src.agents.hard_sos import HardSosEngine
from src.agents.triage import TriageAgent
from src.agents.hospital import HospitalAgent
from src.voice.exotel_client import ExotelClient
from src.safety.guardrails import (
    PIISanitizer,
    PromptInjectionDetector,
    InterAgentContractGuard,
)

class GoldenCoordinator:
    def __init__(
        self,
        triage_agent: Optional[TriageAgent] = None,
        hospital_agent: Optional[HospitalAgent] = None,
        exotel_client: Optional[ExotelClient] = None,
        event_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ):
        self.triage_agent = triage_agent or TriageAgent()
        self.hospital_agent = hospital_agent or HospitalAgent()
        self.exotel_client = exotel_client or ExotelClient()
        self.event_callback = event_callback
        self.checkpointer = MemorySaver()
        self.app = self._build_graph()

    def emit_event(self, stage: str, case_id: str, payload: Dict[str, Any]) -> None:
        """Broadcast live graph progress event to subscribers/dashboard."""
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

        # 1. Entry & Hard-SOS Node
        def hard_sos_node(state: GoldenCaseState) -> Dict[str, Any]:
            # Prompt injection check
            has_injection, patterns = PromptInjectionDetector.check_input(state.input_data.raw_input)
            
            is_sos, triggers, rationale, latency_ms = HardSosEngine.evaluate(state.input_data.raw_input)
            updates: Dict[str, Any] = {}

            triage_copy = state.triage.model_copy()
            if is_sos:
                triage_copy.hard_sos = True
                triage_copy.hard_sos_triggers = triggers
                triage_copy.acuity_level = "RED"
                triage_copy.confidence = 1.0
                triage_copy.rationale = rationale
                triage_copy.guideline_reference = "MoRTH Road Accident Golden Hour Deterministic Protocol 2025"
                triage_copy.triage_completed_at = datetime.now(timezone.utc)
            updates["triage"] = triage_copy

            control_copy = state.control_audit.model_copy()
            control_copy.current_node = "hard_sos_node"
            control_copy.execution_stage = "HARD_SOS_CHECK"
            if has_injection:
                control_copy.errors.append({
                    "node": "hard_sos_node",
                    "error_type": "PROMPT_INJECTION_FLAGGED",
                    "message": f"Potential prompt injection flagged: {patterns}",
                    "recovered": True
                })
            updates["control_audit"] = control_copy
            
            self.emit_event("HARD_SOS_CHECK", state.input_data.case_id, {
                "hard_sos": is_sos,
                "triggers": triggers,
                "latency_ms": latency_ms,
                "injection_flagged": has_injection
            })
            return updates

        # 2. Triage Node (LLM based) with Guardrail Validation
        def triage_node(state: GoldenCaseState) -> Dict[str, Any]:
            triage_res = self.triage_agent.triage_incident(
                incident_text=state.input_data.raw_input,
                location_text=state.input_data.location.address_or_landmark
            )
            # Guardrail Contract Enforcement
            validated_triage = InterAgentContractGuard.sanitize_triage_payload(
                triage_res.model_dump(),
                state.input_data.raw_input
            )
            self.emit_event("TRIAGE_COMPLETE", state.input_data.case_id, {
                "acuity_level": validated_triage.acuity_level,
                "confidence": validated_triage.confidence,
                "guideline": validated_triage.guideline_reference,
                "rationale": validated_triage.rationale
            })
            return {"triage": validated_triage}

        # 3. Hospital & Bed Agent Node - Updates ONLY 'hospital_fhir'
        def hospital_node(state: GoldenCaseState) -> Dict[str, Any]:
            acuity = state.triage.acuity_level or ("RED" if state.triage.hard_sos else "YELLOW")
            candidates = self.hospital_agent.rank_hospitals(
                incident_lat=state.input_data.location.latitude,
                incident_lon=state.input_data.location.longitude,
                acuity_level=acuity
            )
            if not candidates:
                fallback_hosp = InterAgentContractGuard.sanitize_hospital_payload({})
                self.emit_event("HOSPITAL_ROUTED", state.input_data.case_id, {
                    "hospital_id": fallback_hosp.selected_hospital_id,
                    "name": fallback_hosp.selected_hospital_name,
                    "status": "FALLBACK"
                })
                return {"hospital_fhir": fallback_hosp}

            selected = candidates[0]
            try:
                bundle_id, p_id, enc_id, cond_id = self.hospital_agent.pre_register_patient(state, selected)
                hosp_out = HospitalFhirOutput(
                    candidate_hospitals=candidates,
                    selected_hospital_id=selected.hospital_id,
                    selected_hospital_name=selected.name,
                    bed_status="CONFIRMED",
                    fhir_bundle_id=bundle_id,
                    fhir_patient_id=p_id,
                    fhir_encounter_id=enc_id,
                    fhir_condition_id=cond_id,
                    fhir_submission_status="SUCCESS",
                    fhir_submission_timestamp=datetime.now(timezone.utc)
                )
            except Exception as e:
                hosp_out = HospitalFhirOutput(
                    candidate_hospitals=candidates,
                    selected_hospital_id=selected.hospital_id,
                    selected_hospital_name=selected.name,
                    bed_status="REQUESTED",
                    fhir_submission_status="FAILED"
                )

            validated_hosp = InterAgentContractGuard.sanitize_hospital_payload(hosp_out.model_dump())
            self.emit_event("HOSPITAL_ROUTED", state.input_data.case_id, {
                "hospital_id": validated_hosp.selected_hospital_id,
                "name": validated_hosp.selected_hospital_name,
                "distance_km": selected.distance_km,
                "bed_status": validated_hosp.bed_status,
                "fhir_patient_id": validated_hosp.fhir_patient_id,
                "fhir_bundle_id": validated_hosp.fhir_bundle_id,
                "fhir_submission_status": validated_hosp.fhir_submission_status
            })
            return {"hospital_fhir": validated_hosp}

        # 4. Dispatcher Fan-Out Bridge Node
        def fan_out_node(state: GoldenCaseState) -> Dict[str, Any]:
            control_copy = state.control_audit.model_copy()
            control_copy.current_node = "fan_out_node"
            control_copy.execution_stage = "PARALLEL_TRIAGE_HOSPITAL"
            return {"control_audit": control_copy}

        # 5. Coordinator Merge Node
        def coordinator_merge_node(state: GoldenCaseState) -> Dict[str, Any]:
            control_copy = state.control_audit.model_copy()
            control_copy.current_node = "coordinator_merge_node"
            control_copy.execution_stage = "COORDINATOR_MERGE"
            return {"control_audit": control_copy}

        # 6. Voice Dispatch Trigger Node
        def voice_trigger_node(state: GoldenCaseState) -> Dict[str, Any]:
            voice_copy = state.voice_family.model_copy()
            control_copy = state.control_audit.model_copy()
            control_copy.current_node = "voice_trigger_node"

            phone_to_call = state.voice_family.recipient_phone or state.input_data.caller_phone
            if phone_to_call:
                res = self.exotel_client.trigger_outbound_call(
                    recipient_phone=phone_to_call,
                    case_id=state.input_data.case_id,
                    callback_url="http://localhost:8000/webhook/call-outcome"
                )
                voice_copy.call_status = res.get("status", "TRIGGERED")
                voice_copy.call_id = res.get("call_id")
                voice_copy.recipient_phone = phone_to_call
                control_copy.execution_stage = "AWAITING_WEBHOOK"
                self.emit_event("VOICE_TRIGGERED", state.input_data.case_id, {
                    "call_id": voice_copy.call_id,
                    "recipient_phone": PIISanitizer.sanitize(phone_to_call),
                    "status": voice_copy.call_status
                })
            else:
                voice_copy.call_status = "IDLE"
                control_copy.execution_stage = "COMPLETED"
                control_copy.completed_at = datetime.now(timezone.utc)
                self.emit_event("CASE_COMPLETED", state.input_data.case_id, {
                    "status": "COMPLETED_WITHOUT_VOICE"
                })

            return {"voice_family": voice_copy, "control_audit": control_copy}

        # Add Nodes to Graph
        graph.add_node("hard_sos_node", hard_sos_node)
        graph.add_node("fan_out_node", fan_out_node)
        graph.add_node("triage_node", triage_node)
        graph.add_node("hospital_node", hospital_node)
        graph.add_node("coordinator_merge_node", coordinator_merge_node)
        graph.add_node("voice_trigger_node", voice_trigger_node)

        # Edges & Conditional Routing
        graph.add_edge(START, "hard_sos_node")

        def route_after_hard_sos(state: GoldenCaseState) -> str:
            if state.triage.hard_sos:
                return "hospital_direct"
            return "fan_out"

        graph.add_conditional_edges(
            "hard_sos_node",
            route_after_hard_sos,
            {
                "hospital_direct": "hospital_node",
                "fan_out": "fan_out_node"
            }
        )

        # Parallel fan-out when not Hard-SOS
        graph.add_edge("fan_out_node", "triage_node")
        graph.add_edge("fan_out_node", "hospital_node")

        # Merge parallel paths
        graph.add_edge("triage_node", "coordinator_merge_node")
        graph.add_edge("hospital_node", "coordinator_merge_node")

        # Proceed to Voice trigger
        graph.add_edge("coordinator_merge_node", "voice_trigger_node")
        graph.add_edge("voice_trigger_node", END)

        return graph.compile(checkpointer=self.checkpointer)

    def dispatch_case(self, initial_state: GoldenCaseState) -> GoldenCaseState:
        thread_id = initial_state.control_audit.thread_id
        config = {"configurable": {"thread_id": thread_id}}

        final_state_dict = self.app.invoke(initial_state, config=config)
        return GoldenCaseState.model_validate(final_state_dict)

    def resume_from_voice_webhook(
        self,
        thread_id: str,
        call_id: str,
        call_status: str,
        allergies: List[str],
        medications: List[str],
        blood_group: Optional[str] = None,
        conditions: Optional[List[str]] = None,
        summary: Optional[str] = None,
        duration_sec: Optional[int] = None
    ) -> bool:
        config = {"configurable": {"thread_id": thread_id}}
        current_checkpoint = self.app.get_state(config)
        if not current_checkpoint or not current_checkpoint.values:
            return False

        current_state = GoldenCaseState.model_validate(current_checkpoint.values)
        current_state.voice_family.call_id = call_id
        current_state.voice_family.call_status = call_status # type: ignore
        current_state.voice_family.allergies = allergies
        current_state.voice_family.medications = medications
        current_state.voice_family.blood_group = blood_group
        current_state.voice_family.pre_existing_conditions = conditions or []
        current_state.voice_family.call_summary = summary
        current_state.voice_family.call_duration_seconds = duration_sec
        current_state.voice_family.resumed_at = datetime.now(timezone.utc)
        current_state.control_audit.execution_stage = "COMPLETED"
        current_state.control_audit.completed_at = datetime.now(timezone.utc)
        current_state.add_audit_entry(
            agent_name="voice_agent",
            action="resumed_from_webhook",
            details={
                "call_id": call_id,
                "allergies": allergies,
                "medications": medications,
                "blood_group": blood_group
            }
        )

        self.app.update_state(config, current_state)
        self.emit_event("CASE_COMPLETED", current_state.input_data.case_id, {
            "status": "COMPLETED_VIA_WEBHOOK",
            "allergies": allergies,
            "medications": medications,
            "blood_group": blood_group
        })
        return True
