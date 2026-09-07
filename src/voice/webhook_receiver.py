from datetime import datetime, timezone
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

class CallOutcomeWebhookPayload(BaseModel):
    thread_id: str = Field(..., description="LangGraph execution thread_id")
    case_id: str
    call_id: str
    call_status: str = Field(default="COMPLETED")
    consent_granted: bool = True
    allergies: List[str] = Field(default_factory=list)
    medications: List[str] = Field(default_factory=list)
    blood_group: Optional[str] = None
    pre_existing_conditions: List[str] = Field(default_factory=list)
    call_summary: Optional[str] = None
    call_duration_seconds: Optional[int] = None

app = FastAPI(title="GOLDEN Voice Webhook Receiver")

# Global reference to LangGraph coordinator app for state resumption
_active_coordinator = None

def set_active_coordinator(coordinator):
    global _active_coordinator
    _active_coordinator = coordinator

@app.post("/webhook/call-outcome")
def receive_call_outcome(payload: CallOutcomeWebhookPayload):
    if not _active_coordinator:
        raise HTTPException(status_code=503, detail="Coordinator orchestrator not registered.")

    success = _active_coordinator.resume_from_voice_webhook(
        thread_id=payload.thread_id,
        call_id=payload.call_id,
        call_status=payload.call_status,
        allergies=payload.allergies,
        medications=payload.medications,
        blood_group=payload.blood_group,
        conditions=payload.pre_existing_conditions,
        summary=payload.call_summary,
        duration_sec=payload.call_duration_seconds
    )

    if not success:
        raise HTTPException(status_code=404, detail=f"Thread {payload.thread_id} not found in checkpointer.")

    return {
        "status": "RESUMED",
        "thread_id": payload.thread_id,
        "resumed_at": datetime.now(timezone.utc).isoformat()
    }
