"""Family Communication Specialist Workflow for GOLDEN.

Responsible for:
1. Consent-gated outbound family outreach (TRAI TCCCPR 2018 compliance).
2. Consent-gated Exotel transport coordination with local simulation fallback.
3. Structured collection and sanitization of reported medical disclosures
   (allergies, active medications, blood group, chronic conditions).
4. Emitting structured state updates for durable checkpoint resumption.

Explicit Non-Responsibilities:
- Does NOT make medical acuity decisions.
- Does NOT route or select hospitals.
- Does NOT replace clinical or emergency personnel.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
from src.voice.exotel_client import ExotelClient
from src.config import settings
from src.safety.guardrails import PIISanitizer
from src.state.schema import VoiceFamilyOutput

logger = logging.getLogger("golden.voice.family")

class FamilyCommunicationAgent:
    """Specialist agent / workflow for patient family outreach and medical disclosure gathering."""

    def __init__(self, exotel_client: Optional[ExotelClient] = None):
        self.client = exotel_client or ExotelClient()

    def execute_outreach(
        self,
        case_id: str,
        recipient_phone: Optional[str],
        callback_url: Optional[str] = None,
        thread_id: Optional[str] = None,
        consent_basis: Optional[str] = None,
        triggered_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Initiate consent-gated family outreach.

        `consent_basis` documents how consent to contact was established. When
        provided (e.g. the ambulance crew identified the family member on
        scene), the TEAM_CONSENT_PHONE_NUMBERS register is bypassed and the
        basis is written to the call log for the TRAI TCCCPR audit trail.

        Returns a structured dictionary with call status, call ID, and audit details.
        """
        if not recipient_phone:
            return {
                "status": "IDLE",
                "call_id": None,
                "recipient_phone": None,
                "consent_granted": None,
                "message": "No recipient phone number provided for family outreach."
            }

        sanitized_phone = PIISanitizer.sanitize(recipient_phone)

        # 1. Verify consent
        if consent_basis is None and not self.client.verify_consent(recipient_phone):
            from src.voice.call_log import record_call_trigger

            record_call_trigger(
                call_id=f"CALL-REFUSED-{case_id}",
                case_id=case_id,
                thread_id=thread_id,
                recipient_phone=recipient_phone,
                provider="blocked",
                status="CONSENT_REFUSED",
                triggered_by=triggered_by,
                message="Number not in consenting register (TRAI TCCCPR 2018 guardrail)",
            )
            return {
                "status": "CONSENT_REFUSED",
                "call_id": None,
                "recipient_phone": recipient_phone,
                "consent_granted": False,
                "message": f"Consent refused for {sanitized_phone}: not in consenting register (TRAI TCCCPR 2018 guardrail)."
            }

        # Exotel trial accounts refuse to dial unverified numbers, so the leg is
        # pinned to the account's verified number. This happens only after consent,
        # so an unregistered number can never be reached by dialling the pin instead.
        dial_phone = settings.VOICE_TEST_RECIPIENT_PHONE or recipient_phone
        if dial_phone != recipient_phone:
            logger.warning("Family outreach leg pinned to VOICE_TEST_RECIPIENT_PHONE")

        # 2. Trigger telephony
        result = self.client.trigger_outbound_call(
            recipient_phone=dial_phone,
            case_id=case_id,
            callback_url=callback_url or settings.EXOTEL_STATUS_CALLBACK_URL,
            thread_id=thread_id,
            consent_basis=consent_basis,
            triggered_by=triggered_by,
        )

        status = result.get("status", "TRIGGERED")
        call_id = result.get("call_id")

        return {
            "status": status,
            "call_id": call_id,
            "recipient_phone": recipient_phone,
            "consent_granted": True,
            "provider": result.get("provider", "local_simulation"),
            "message": result.get("message", f"Call dispatched to {sanitized_phone}")
        }

    def process_webhook_disclosure(
        self,
        call_id: str,
        call_status: str,
        allergies: Optional[List[str]] = None,
        medications: Optional[List[str]] = None,
        blood_group: Optional[str] = None,
        conditions: Optional[List[str]] = None,
        summary: Optional[str] = None,
        duration_sec: Optional[int] = None,
        consent_granted: bool = True,
    ) -> VoiceFamilyOutput:
        """Parse, sanitize, and structure incoming disclosures from telephony webhook."""
        clean_allergies = [PIISanitizer.sanitize(a.strip()) for a in (allergies or []) if a.strip()]
        clean_meds = [PIISanitizer.sanitize(m.strip()) for m in (medications or []) if m.strip()]
        clean_conditions = [PIISanitizer.sanitize(c.strip()) for c in (conditions or []) if c.strip()]
        clean_summary = PIISanitizer.sanitize(summary) if summary else None

        # Clean blood group string (e.g. "O+", "B-", "AB+")
        clean_bg = blood_group.strip().upper() if blood_group else None

        return VoiceFamilyOutput(
            call_status=call_status, # type: ignore
            call_id=call_id,
            consent_granted=consent_granted,
            allergies=clean_allergies,
            medications=clean_meds,
            blood_group=clean_bg,
            pre_existing_conditions=clean_conditions,
            call_summary=clean_summary,
            call_duration_seconds=duration_sec,
            resumed_at=datetime.now(timezone.utc)
        )


FamilyCommunicationWorkflow = FamilyCommunicationAgent
