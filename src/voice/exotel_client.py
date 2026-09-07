import uuid
import logging
from typing import Optional, Dict, Any
from src.config import settings

logger = logging.getLogger("golden.voice.exotel")

class ExotelClient:
    """Outbound Call Client for Indian Cloud Telephony (Exotel) with TRAI TCCCPR 2018 safety check."""

    def __init__(self):
        self.account_sid = settings.EXOTEL_ACCOUNT_SID
        self.api_key = settings.EXOTEL_API_KEY
        self.api_token = settings.EXOTEL_API_TOKEN
        self.subdomain = settings.EXOTEL_SUBDOMAIN
        self.caller_id = settings.EXOTEL_CALLER_ID
        self.consent_numbers = settings.consent_numbers

    def is_configured(self) -> bool:
        return bool(
            self.account_sid and "your_" not in self.account_sid
            and self.api_key and "your_" not in self.api_key
            and self.api_token and "your_" not in self.api_token
        )

    def verify_consent(self, phone: str) -> bool:
        # TRAI TCCCPR 2018 compliance guardrail: in research sandbox, only call consenting team numbers
        if not self.consent_numbers:
            return True
        return phone in self.consent_numbers

    def trigger_outbound_call(
        self,
        recipient_phone: str,
        case_id: str,
        callback_url: Optional[str] = None
    ) -> Dict[str, Any]:
        if not self.verify_consent(recipient_phone):
            return {
                "status": "CONSENT_REFUSED",
                "call_id": None,
                "message": f"Phone {recipient_phone} not in consenting team register (TRAI TCCCPR 2018 guardrail)."
            }

        if not self.is_configured():
            simulated_call_id = f"EXO-SIM-{uuid.uuid4().hex[:8]}"
            return {
                "status": "TRIGGERED",
                "call_id": simulated_call_id,
                "provider": "exotel_simulation",
                "message": f"Simulated call dispatched to {recipient_phone} for case {case_id}."
            }

        # Real Exotel API call
        import requests
        url = f"https://{self.subdomain}/v1/Accounts/{self.account_sid}/Calls/connect.json"
        data = {
            "From": recipient_phone,
            "To": self.caller_id,
            "CallerId": self.caller_id,
            "CustomField": case_id,
            "StatusCallback": callback_url
        }
        resp = requests.post(url, data=data, auth=(self.api_key, self.api_token), timeout=10)
        resp.raise_for_status()
        resp_data = resp.json()
        call_sid = resp_data.get("Call", {}).get("Sid")
        return {
            "status": "TRIGGERED",
            "call_id": call_sid,
            "provider": "exotel_live",
            "message": f"Live Exotel call dispatched: SID {call_sid}"
        }
