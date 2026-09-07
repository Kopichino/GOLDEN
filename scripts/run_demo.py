import os
import sys
import uuid
import argparse
from pathlib import Path
from datetime import datetime, timezone

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.agents.coordinator import GoldenCoordinator
from src.state.schema import GoldenCaseState, CaseIdentityInput, IncidentLocation, ControlAudit

DEFAULT_SAMPLE_REPORT = (
    "Two-wheeler collision with auto-rickshaw near Tambaram flyover, GST Road. "
    "Rider thrown 10 meters, conscious but in severe agony with suspected right femur fracture "
    "and active bleeding from thigh wound. Passenger sitting on sidewalk with minor contusions."
)

def run_happy_path_demo(
    report_text: str = DEFAULT_SAMPLE_REPORT,
    landmark: str = "Tambaram Flyover, GST Road, Chennai",
    latitude: float = 12.9249,
    longitude: float = 80.1000,
    caller_phone: str = "+919840112233"
):
    case_id = f"GOLDEN-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    thread_id = f"thread-{case_id}"

    print("=" * 80)
    print("   GOLDEN: Emergency Dispatch Decision-Support Pipeline (Phase 1 Demo)")
    print("   Guideline-Grounded Orchestrated LLM Dispatch for Emergency Networks")
    print("=" * 80)
    print(f"\n[1] CASE INGESTION")
    print(f"  * Case ID:     {case_id}")
    print(f"  * Caller:      {caller_phone}")
    print(f"  * Location:    {landmark} ({latitude}, {longitude})")
    print(f"  * Incident:    \"{report_text}\"")

    initial_state = GoldenCaseState(
        input_data=CaseIdentityInput(
            case_id=case_id,
            caller_phone=caller_phone,
            raw_input=report_text,
            location=IncidentLocation(
                latitude=latitude,
                longitude=longitude,
                address_or_landmark=landmark
            )
        ),
        control_audit=ControlAudit(
            current_node="entry",
            thread_id=thread_id
        )
    )

    coordinator = GoldenCoordinator()

    print("\n[2] ORCHESTRATION & AGENT EXECUTION")
    print("  * Starting LangGraph workflow with durable MemorySaver checkpointer...")
    dispatched_state = coordinator.dispatch_case(initial_state)

    # 1. Hard-SOS
    print("\n--- Hard-SOS Rule Engine ---")
    if dispatched_state.triage.hard_sos:
        print("  [CRITICAL BYPASS] Hard-SOS Pattern Triggered!")
        print(f"  * Triggers:    {dispatched_state.triage.hard_sos_triggers}")
        print(f"  * Routing:     Direct bypass to Hospital Agent (< 1ms)")
    else:
        print("  [CLEAR] No deterministic life-threat pattern matched.")
        print("  * Routing:     Fanned out in parallel to Triage Agent + Hospital Agent")

    # 2. Triage Output
    print("\n--- Guideline-Grounded Triage Agent ---")
    print(f"  * Acuity Level:   [{dispatched_state.triage.acuity_level}]")
    print(f"  * Confidence:     {dispatched_state.triage.confidence * 100:.1f}%")
    print(f"  * Clinical Logic: {dispatched_state.triage.rationale}")
    print(f"  * Protocol Cited: {dispatched_state.triage.guideline_reference}")
    print(f"  * Schema Retries: {dispatched_state.triage.retry_count}")

    # 3. Hospital & Bed Agent
    print("\n--- Hospital & Bed Agent (FHIR R4) ---")
    print(f"  * Selected Facility: {dispatched_state.hospital_fhir.selected_hospital_name}")
    print(f"  * Bed Reservation:   {dispatched_state.hospital_fhir.bed_status}")
    print("  * Candidate Ranking:")
    for i, c in enumerate(dispatched_state.hospital_fhir.candidate_hospitals[:3], 1):
        print(f"     {i}. {c.name:45} | Dist: {c.distance_km:5.1f}km | Trauma: {c.trauma_level:10} | Score: {c.score}")

    print("\n--- HL7 FHIR R4 Pre-Registration Bundle ---")
    print(f"  * Submission Status: {dispatched_state.hospital_fhir.fhir_submission_status}")
    print(f"  * Bundle ID:         {dispatched_state.hospital_fhir.fhir_bundle_id}")
    print(f"  * Patient Resource:  http://localhost:8080/fhir/Patient/{dispatched_state.hospital_fhir.fhir_patient_id}")
    print(f"  * Encounter Resource:http://localhost:8080/fhir/Encounter/{dispatched_state.hospital_fhir.fhir_encounter_id}")
    print(f"  * Condition Resource:http://localhost:8080/fhir/Condition/{dispatched_state.hospital_fhir.fhir_condition_id}")

    # 4. Voice Agent Trigger
    print("\n--- Family Notification Voice Agent ---")
    print(f"  * Call Status:       {dispatched_state.voice_family.call_status}")
    print(f"  * Dispatch SID:      {dispatched_state.voice_family.call_id}")
    print(f"  * Contact Target:    {dispatched_state.voice_family.recipient_phone}")
    print(f"  * Graph State:       {dispatched_state.control_audit.execution_stage} (Checkpoint Saved)")

    # 5. Simulate Incoming Webhook
    print("\n[3] SIMULATING ASYNC WEBHOOK CALLBACK (Family Call Concluded)")
    print("  * Simulating incoming payload from voice bridge to /webhook/call-outcome...")
    coordinator.resume_from_voice_webhook(
        thread_id=thread_id,
        call_id=dispatched_state.voice_family.call_id or "EXO-SIM-001",
        call_status="COMPLETED",
        allergies=["Ciprofloxacin", "Shellfish"],
        medications=["Telmisartan 40mg (Hypertension)"],
        blood_group="B+",
        conditions=["Hypertension", "Type 2 Diabetes"],
        summary="Spouse answered call. Consented to treatment. Verified blood group B+, cautioned about Ciprofloxacin allergy.",
        duration_sec=88
    )

    resumed_checkpoint = coordinator.app.get_state({"configurable": {"thread_id": thread_id}})
    resumed_state = GoldenCaseState.model_validate(resumed_checkpoint.values)

    print("\n--- Checkpoint Resumption Succeeded ---")
    print(f"  * Final Pipeline Stage: {resumed_state.control_audit.execution_stage}")
    print(f"  * Retrieved Allergies:  {resumed_state.voice_family.allergies}")
    print(f"  * Current Medications:  {resumed_state.voice_family.medications}")
    print(f"  * Verified Blood Group: {resumed_state.voice_family.blood_group}")
    print(f"  * Call Duration:        {resumed_state.voice_family.call_duration_seconds} seconds")
    print(f"  * Call Summary:         \"{resumed_state.voice_family.call_summary}\"")

    print("\n" + "=" * 80)
    print("   END-TO-END DEMO SUCCESS: ALL 4 AGENTS COORDINATED & STATE PERSISTED")
    print("=" * 80)
    return resumed_state

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GOLDEN Pre-Hospital Emergency Dispatch Demo")
    parser.add_argument("--report", type=str, default=DEFAULT_SAMPLE_REPORT, help="Incident report text")
    parser.add_argument("--location", type=str, default="Tambaram Flyover, GST Road, Chennai", help="Landmark")
    args = parser.parse_args()

    run_happy_path_demo(report_text=args.report, landmark=args.location)
