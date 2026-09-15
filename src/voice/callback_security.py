"""Authentication and replay protection for voice provider callbacks."""

from __future__ import annotations

import hashlib
import hmac
import time
from threading import Lock


class CallbackSecurity:
    """Validate signed callbacks while retaining a safe local-demo mode."""

    def __init__(self, secret: str | None, max_age_seconds: int = 300) -> None:
        self.secret = secret
        self.max_age_seconds = max_age_seconds
        self._seen_nonces: set[str] = set()
        self._lock = Lock()

    def validate(
        self,
        body: bytes,
        *,
        signature: str | None,
        timestamp: str | None,
        nonce: str | None,
        now: float | None = None,
    ) -> tuple[bool, str]:
        """Return whether callback headers authenticate the raw request body."""
        if not self.secret:
            return True, "callback signing is disabled for local development"
        if not signature or not timestamp or not nonce:
            return False, "signature, timestamp, and nonce headers are required"

        try:
            issued_at = int(timestamp)
        except ValueError:
            return False, "timestamp must be an integer"

        current_time = time.time() if now is None else now
        if abs(current_time - issued_at) > self.max_age_seconds:
            return False, "callback timestamp is outside the allowed window"

        signed_value = f"{timestamp}.{nonce}.".encode() + body
        expected = hmac.new(
            self.secret.encode(), signed_value, hashlib.sha256
        ).hexdigest()
        supplied = signature.removeprefix("sha256=")
        if not hmac.compare_digest(expected, supplied):
            return False, "callback signature is invalid"

        with self._lock:
            if nonce in self._seen_nonces:
                return False, "callback nonce has already been used"
            self._seen_nonces.add(nonce)
        return True, "callback authenticated"