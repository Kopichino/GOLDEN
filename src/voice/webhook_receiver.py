from datetime import datetime, timezone
from typing import List, Literal, Optional
from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, Field
from src.config import settings
from src.state.schema import GoldenCaseState
from src.voice.callback_security import CallbackSecurity

class CallOutcomeWebhookPayload(BaseModel):
    thread_id: str = Field(..., description="LangGraph execution thread_id")
    case_id: str
    call_id: str
    call_status: Literal[
        "IDLE", "TRIGGERED", "IN_PROGRESS", "COMPLETED", "FAILED", "NO_ANSWER", "CONSENT_REFUSED"
    ] = Field(default="COMPLETED")
    consent_granted: bool = True
    allergies: List[str] = Field(default_factory=list)
    medications: List[str] = Field(default_factory=list)
    blood_group: Optional[str] = None
    pre_existing_conditions: List[str] = Field(default_factory=list)
    call_summary: Optional[str] = None
    call_duration_seconds: Optional[int] = None


callback_security = CallbackSecurity(
    settings.VOICE_CALLBACK_SECRET,
    settings.VOICE_CALLBACK_MAX_AGE_SECONDS,
)

app = FastAPI(title="GOLDEN Voice Webhook Receiver")

# Global reference to LangGraph coordinator app for state resumption
_active_coordinator = None

def set_active_coordinator(coordinator):
    global _active_coordinator
    _active_coordinator = coordinator

def handle_call_outcome(payload: CallOutcomeWebhookPayload, coordinator) -> dict:
    """Apply a validated payload to the coordinator checkpoint."""
    if not coordinator:
        raise HTTPException(status_code=503, detail="Coordinator orchestrator not registered.")

    checkpoint = coordinator.app.get_state({"configurable": {"thread_id": payload.thread_id}})
    if not checkpoint or not checkpoint.values:
        raise HTTPException(status_code=404, detail=f"Thread {payload.thread_id} not found in checkpointer.")
    checkpoint_state = GoldenCaseState.model_validate(checkpoint.values)
    if checkpoint_state.input_data.case_id != payload.case_id:
        raise HTTPException(status_code=409, detail="Callback case does not match the checkpoint.")

    success = coordinator.resume_from_voice_webhook(
        thread_id=payload.thread_id,
        call_id=payload.call_id,
        call_status=payload.call_status,
        allergies=payload.allergies,
        medications=payload.medications,
        blood_group=payload.blood_group,
        conditions=payload.pre_existing_conditions,
        summary=payload.call_summary,
        duration_sec=payload.call_duration_seconds,
        consent_granted=payload.consent_granted,
    )

    if not success:
        raise HTTPException(status_code=404, detail=f"Thread {payload.thread_id} not found in checkpointer.")

    return {
        "status": "RESUMED",
        "thread_id": payload.thread_id,
        "resumed_at": datetime.now(timezone.utc).isoformat()
    }


@app.post("/webhook/call-outcome")
async def receive_call_outcome(
    request: Request,
    payload: CallOutcomeWebhookPayload,
    x_golden_signature: Optional[str] = Header(default=None),
    x_golden_timestamp: Optional[str] = Header(default=None),
    x_golden_nonce: Optional[str] = Header(default=None),
):
    body = await request.body()
    valid, reason = callback_security.validate(
        body,
        signature=x_golden_signature,
        timestamp=x_golden_timestamp,
        nonce=x_golden_nonce,
    )
    if not valid:
        raise HTTPException(status_code=401, detail=reason)
    return handle_call_outcome(payload, _active_coordinator)
