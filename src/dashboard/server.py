"""FastAPI Server for GOLDEN Live Emergency Dispatcher Dashboard.

Provides:
- REST API for listing cases, simulating emergency scenarios, and manual dispatcher overrides.
- Real-time Server-Sent Events (SSE) streaming live multi-agent pipeline events.
- FHIR resource proxy to inspect live Patient, Encounter, and Condition resources from local HAPI FHIR.
- Serves the modern, responsive dispatcher interface.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.config import settings
from src.state.schema import (
    GoldenCaseState,
    CaseIdentityInput,
    IncidentLocation,
    ControlAudit,
)
from src.agents.coordinator import GoldenCoordinator
from src.safety.guardrails import PIISanitizer, PromptInjectionDetector

app = FastAPI(title="GOLDEN Emergency Dispatcher Console", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)

# In-memory storage for active cases and SSE subscribers
active_cases: Dict[str, GoldenCaseState] = {}
sse_subscribers: List[asyncio.Queue] = []
event_history: List[Dict[str, Any]] = []

def broadcast_event(event_dict: Dict[str, Any]) -> None:
    """Send an event to all connected SSE clients."""
    event_history.append(event_dict)
    if len(event_history) > 100:
        event_history.pop(0)

    for queue in list(sse_subscribers):
        try:
            queue.put_nowait(event_dict)
        except Exception:
            if queue in sse_subscribers:
                sse_subscribers.remove(queue)

coordinator = GoldenCoordinator(event_callback=broadcast_event)

# Pre-defined emergency simulation scenarios
PRESET_SCENARIOS = {
    "tambaram_femur_crash": {
        "title": "Tambaram Flyover High-Speed Collision (Polytrauma)",
        "raw_input": "Two-wheeler collided with median at 60 km/h on Tambaram Flyover. Rider thrown 10 meters, conscious but moaning, severe deformity and arterial bleeding in right thigh, probable femur fracture. Pulse weak, rapid.",
        "latitude": 12.9249,
        "longitude": 80.1472,
        "address": "Tambaram Flyover, GST Road, Chennai",
        "district": "Chennai",
        "caller_phone": "+91 94441 23456",
        "language": "en",
    },
    "guindy_cardiac_arrest": {
        "title": "Guindy Industrial Estate Unresponsive Male (Hard-SOS)",
        "raw_input": "55-year-old male collapsed on factory floor in Guindy Industrial Estate. Unresponsive and not breathing, chest compressions started by bystander. Possible cardiac arrest.",
        "latitude": 13.0067,
        "longitude": 80.2026,
        "address": "Guindy Industrial Estate, Chennai",
        "district": "Chennai",
        "caller_phone": "+91 98400 98765",
        "language": "en",
    },
    "omr_concussion": {
        "title": "OMR Thoraipakkam Two-Wheeler Skid (Urgent)",
        "raw_input": "Motorcyclist skidded on wet road near Thoraipakkam signal. Deep forehead laceration, bleeding controlled with cloth, complaining of nausea and dizziness, ambulatory.",
        "latitude": 12.9385,
        "longitude": 80.2327,
        "address": "OMR Thoraipakkam Signal, Chennai",
        "district": "Chennai",
        "caller_phone": "+91 98840 55443",
        "language": "en",
    },
}

class SimulateRequest(BaseModel):
    preset_key: Optional[str] = None
    custom_input: Optional[str] = None
    landmark: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    caller_phone: Optional[str] = None

class OverrideRequest(BaseModel):
    acuity_level: Optional[str] = None
    selected_hospital_id: Optional[str] = None
    selected_hospital_name: Optional[str] = None
    dispatcher_notes: str

class WebhookInjectRequest(BaseModel):
    allergies: List[str] = []
    medications: List[str] = []
    blood_group: Optional[str] = None
    conditions: List[str] = []
    summary: Optional[str] = None

@app.get("/api/events")
async def sse_events(request: Request):
    """Server-Sent Events endpoint streaming live multi-agent updates."""
    queue: asyncio.Queue = asyncio.Queue()
    sse_subscribers.append(queue)

    async def event_generator():
        # Yield recent backlog
        for past_event in event_history[-10:]:
            yield f"data: {json.dumps(past_event)}\n\n"

        try:
            while True:
                if await request.is_disconnected():
                    break
                event = await queue.get()
                yield f"data: {json.dumps(event)}\n\n"
        finally:
            if queue in sse_subscribers:
                sse_subscribers.remove(queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.get("/api/cases")
def list_cases():
    """List all tracked emergency cases with summarized statuses."""
    items = []
    for c_id, state in active_cases.items():
        items.append({
            "case_id": c_id,
            "reported_at": state.input_data.reported_at.isoformat(),
            "landmark": state.input_data.location.address_or_landmark,
            "raw_input_snippet": state.input_data.raw_input[:100] + "...",
            "acuity_level": state.triage.acuity_level,
            "hard_sos": state.triage.hard_sos,
            "selected_hospital": state.hospital_fhir.selected_hospital_name,
            "distance_km": state.hospital_fhir.candidate_hospitals[0].distance_km if state.hospital_fhir.candidate_hospitals else None,
            "call_status": state.voice_family.call_status,
            "execution_stage": state.control_audit.execution_stage,
            "fhir_bundle_id": state.hospital_fhir.fhir_bundle_id,
        })
    return {"cases": items}

@app.get("/api/cases/{case_id}")
def get_case_details(case_id: str):
    """Return full state JSON for a specific emergency case."""
    if case_id not in active_cases:
        raise HTTPException(status_code=404, detail="Case not found")
    return active_cases[case_id].model_dump()

@app.get("/api/presets")
def get_presets():
    """Return available scenario simulation presets."""
    return {"presets": PRESET_SCENARIOS}

async def _run_simulation_task(initial_state: GoldenCaseState):
    """Background task executing LangGraph and updating the case registry."""
    case_id = initial_state.input_data.case_id
    broadcast_event({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "case_id": case_id,
        "stage": "INGESTED",
        "data": {
            "landmark": initial_state.input_data.location.address_or_landmark,
            "raw_input": initial_state.input_data.raw_input
        }
    })
    
    # Run through coordinator
    final_state = coordinator.dispatch_case(initial_state)
    active_cases[case_id] = final_state

    broadcast_event({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "case_id": case_id,
        "stage": "DISPATCH_CYCLE_COMPLETE",
        "data": {
            "acuity": final_state.triage.acuity_level,
            "hospital": final_state.hospital_fhir.selected_hospital_name,
            "bed_status": final_state.hospital_fhir.bed_status,
            "stage": final_state.control_audit.execution_stage,
            "fhir_bundle_id": final_state.hospital_fhir.fhir_bundle_id
        }
    })

@app.post("/api/simulate")
def trigger_simulation(req: SimulateRequest, background_tasks: BackgroundTasks):
    """Trigger an emergency simulation from preset or custom input."""
    if req.preset_key and req.preset_key in PRESET_SCENARIOS:
        preset = PRESET_SCENARIOS[req.preset_key]
        raw_text = preset["raw_input"]
        lat = preset["latitude"]
        lon = preset["longitude"]
        landmark = preset["address"]
        phone = preset["caller_phone"]
        lang = preset["language"]
    else:
        raw_text = req.custom_input or "Emergency road accident reported near Tambaram."
        lat = req.latitude or 12.9249
        lon = req.longitude or 80.1472
        landmark = req.landmark or "Tambaram Flyover, Chennai"
        phone = req.caller_phone or "+91 94441 23456"
        lang = "en"

    case_id = f"GOLDEN-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    thread_id = f"thread-{case_id}"

    initial_state = GoldenCaseState(
        input_data=CaseIdentityInput(
            case_id=case_id,
            caller_phone=phone,
            raw_input=raw_text,
            language=lang,
            location=IncidentLocation(
                latitude=lat,
                longitude=lon,
                address_or_landmark=landmark,
                district="Chennai"
            )
        ),
        control_audit=ControlAudit(
            thread_id=thread_id,
            active_provider="gemini",
            execution_stage="INGESTION"
        )
    )

    active_cases[case_id] = initial_state
    background_tasks.add_task(_run_simulation_task, initial_state)

    return {"status": "QUEUED", "case_id": case_id, "thread_id": thread_id}

@app.post("/api/cases/{case_id}/webhook")
def inject_webhook(case_id: str, req: WebhookInjectRequest):
    """Simulate next-of-kin voice callback and resume LangGraph execution."""
    if case_id not in active_cases:
        raise HTTPException(status_code=404, detail="Case not found")

    state = active_cases[case_id]
    thread_id = state.control_audit.thread_id

    resumed = coordinator.resume_from_voice_webhook(
        thread_id=thread_id,
        call_id=state.voice_family.call_id or f"EXO-SIM-{uuid.uuid4().hex[:8]}",
        call_status="COMPLETED",
        allergies=req.allergies,
        medications=req.medications,
        blood_group=req.blood_group,
        conditions=req.conditions,
        summary=req.summary or "Next-of-kin confirmed patient details and verified medical history.",
        duration_sec=42
    )

    if resumed:
        # Refresh state from coordinator checkpointer
        checkpoint = coordinator.app.get_state({"configurable": {"thread_id": thread_id}})
        if checkpoint and checkpoint.values:
            active_cases[case_id] = GoldenCaseState.model_validate(checkpoint.values)
        return {"status": "SUCCESS", "resumed": True}
    raise HTTPException(status_code=500, detail="Failed to resume checkpoint")

@app.post("/api/cases/{case_id}/override")
def human_override(case_id: str, req: OverrideRequest):
    """Human dispatcher in-the-loop override endpoint."""
    if case_id not in active_cases:
        raise HTTPException(status_code=404, detail="Case not found")

    state = active_cases[case_id]

    if req.acuity_level:
        old_acuity = state.triage.acuity_level
        state.triage.acuity_level = req.acuity_level # type: ignore
        state.add_audit_entry(
            agent_name="human_dispatcher",
            action="acuity_override",
            details={"old": old_acuity, "new": req.acuity_level, "notes": req.dispatcher_notes}
        )

    if req.selected_hospital_id and req.selected_hospital_name:
        old_hosp = state.hospital_fhir.selected_hospital_name
        state.hospital_fhir.selected_hospital_id = req.selected_hospital_id
        state.hospital_fhir.selected_hospital_name = req.selected_hospital_name
        state.add_audit_entry(
            agent_name="human_dispatcher",
            action="hospital_override",
            details={"old": old_hosp, "new": req.selected_hospital_name, "notes": req.dispatcher_notes}
        )

    broadcast_event({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "case_id": case_id,
        "stage": "DISPATCHER_OVERRIDE",
        "data": {
            "acuity_override": req.acuity_level,
            "hospital_override": req.selected_hospital_name,
            "notes": req.dispatcher_notes
        }
    })

    return {"status": "OVERRIDDEN", "case": state.model_dump()}

@app.get("/api/fhir/{resource_type}/{resource_id}")
def proxy_fhir_resource(resource_type: str, resource_id: str):
    """Proxy view to query local HAPI FHIR server without CORS limitations."""
    fhir_url = f"{settings.FHIR_BASE_URL.rstrip('/')}/{resource_type}/{resource_id}"
    try:
        resp = requests.get(fhir_url, timeout=5)
        if resp.status_code == 200:
            return resp.json()
        return {"error": f"FHIR Server returned HTTP {resp.status_code}", "url": fhir_url}
    except Exception as e:
        return {"error": str(e), "url": fhir_url}

@app.get("/api/health")
def health_check():
    """System health check including FHIR and agent provider status."""
    fhir_ok = False
    try:
        r = requests.get(f"{settings.FHIR_BASE_URL.rstrip('/')}/metadata", timeout=2)
        fhir_ok = (r.status_code == 200)
    except Exception:
        pass

    return {
        "status": "ONLINE",
        "fhir_connected": fhir_ok,
        "fhir_url": settings.FHIR_BASE_URL,
        "primary_llm": settings.DEFAULT_LLM_PROVIDER,
        "active_cases_count": len(active_cases),
        "sse_subscribers_count": len(sse_subscribers)
    }

# Mount static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/", response_class=HTMLResponse)
def serve_index():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return HTMLResponse(content=index_file.read_text(encoding="utf-8"))
    return HTMLResponse("<h2>Dispatcher UI files generating... Refresh in 5 seconds.</h2>")
