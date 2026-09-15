import uuid
import logging
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import requests
from src.config import settings

logger = logging.getLogger("golden.voice.exotel")

class ExotelClient:
    """Consent-gated Exotel client with local simulation fallback."""

    def __init__(self):
        self.consent_numbers = settings.consent_numbers
        self.account_sid = settings.EXOTEL_ACCOUNT_SID
        self.api_key = settings.EXOTEL_API_KEY
        self.api_token = settings.EXOTEL_API_TOKEN
        self.subdomain = settings.EXOTEL_SUBDOMAIN
        self.caller_id = settings.EXOTEL_CALLER_ID

    def is_configured(self) -> bool:
        required = (
            self.account_sid,
            self.api_key,
            self.api_token,
            self.subdomain,
            self.caller_id,
            settings.EXOTEL_STREAM_URL,
        )
        return not settings.VOICE_SIMULATION_ONLY and all(required)

    def verify_consent(self, phone: str) -> bool:
        # Fail closed: no configured consent register means no outbound call.
        if not self.consent_numbers:
            return False
        normalized_phone = "".join(character for character in phone if character.isdigit())
        return any(
            normalized_phone == "".join(character for character in allowed if character.isdigit())
            for allowed in self.consent_numbers
        )

    def trigger_outbound_call(
        self,
        recipient_phone: str,
        case_id: str,
        callback_url: Optional[str] = None,
        thread_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not self.verify_consent(recipient_phone):
            return {
                "status": "CONSENT_REFUSED",
                "call_id": None,
                "message": f"Phone {recipient_phone} not in consenting team register (TRAI TCCCPR 2018 guardrail)."
            }

        if settings.VOICE_SIMULATION_ONLY:
            simulated_call_id = f"CALL-SIM-{uuid.uuid4().hex[:8]}"
            return {
                "status": "TRIGGERED",
                "call_id": simulated_call_id,
                "provider": "local_simulation",
                "case_id": case_id,
                "thread_id": thread_id,
                "message": f"Simulated call dispatched to {recipient_phone} for case {case_id}."
            }

        if not self.is_configured():
            raise RuntimeError(
                "Exotel is not configured; set the new account environment variables "
                "or enable VOICE_SIMULATION_ONLY"
            )

        endpoint = (
            f"https://{self.subdomain}/v1/Accounts/"
            f"{self.account_sid}/Calls/connect.json"
        )
        stream_url = self._build_stream_url(case_id, thread_id)
        form_data = {
            "From": recipient_phone,
            "CallerId": self.caller_id,
            "StreamUrl": stream_url,
            "StreamType": "bidirectional",
            "StatusCallback": callback_url or settings.EXOTEL_STATUS_CALLBACK_URL,
            "Record": str(settings.EXOTEL_RECORD_CALLS).lower(),
        }
        # NOTE: Do NOT add 'Url' (ExoML app) here — combining Url + StreamUrl causes
        # Exotel to follow the ExoML flow and discard the bidirectional stream, which
        # results in an immediate 1-second call drop.
        try:
            response = requests.post(
                endpoint,
                data={key: value for key, value in form_data.items() if value},
                auth=(self.api_key, self.api_token),
                timeout=settings.EXOTEL_TIMEOUT_SECONDS,
            )
        except Exception as exc:
            logger.error("Network error connecting to Exotel: %s", exc)
            return {
                "status": "FAILED",
                "call_id": None,
                "provider": "exotel",
                "message": f"Network error connecting to Exotel: {exc}",
            }

        status_code = getattr(response, "status_code", 200)
        if status_code != 200:
            error_msg = getattr(response, "text", "")
            try:
                err_json = response.json()
                error_msg = err_json.get("RestException", {}).get("Message") or err_json.get("message") or error_msg
            except Exception:
                pass
            logger.error("Exotel call rejected (%s): %s", status_code, error_msg)
            return {
                "status": "FAILED",
                "call_id": None,
                "provider": "exotel",
                "message": f"Exotel error ({status_code}): {error_msg}",
            }

        response_data = response.json()
        call_data = response_data.get("Call", {})
        call_id = call_data.get("Sid") or call_data.get("sid")
        if not call_id:
            logger.error("Exotel response did not include a call identifier: %s", response_data)
            return {
                "status": "FAILED",
                "call_id": None,
                "provider": "exotel",
                "message": "Exotel response did not include a call identifier",
            }

        from src.voice.active_calls import register_active_call
        register_active_call(
            call_id=call_id,
            case_id=case_id,
            thread_id=thread_id or f"thread_{case_id}",
            recipient_phone=recipient_phone,
        )

        return {
            "status": "TRIGGERED",
            "call_id": call_id,
            "provider": "exotel",
            "message": f"Outbound voice call dispatched for case {case_id}",
        }

    @staticmethod
    def _build_stream_url(case_id: str, thread_id: Optional[str]) -> str:
        """Attach only GOLDEN identifiers to the configured public stream URL."""
        stream_url = (settings.EXOTEL_STREAM_URL or "").strip().rstrip("/\\")
        if not stream_url:
            raise RuntimeError("EXOTEL_STREAM_URL is required for live voice calls")
        query = urlencode({
            "case_id": case_id,
            "thread_id": thread_id or "",
            "app_id": settings.EXOTEL_APP_ID or "",
            "result_callback_url": settings.VOICE_CALLBACK_URL,
        })
        separator = "&" if "?" in stream_url else "?"
        return f"{stream_url}{separator}{query}"
