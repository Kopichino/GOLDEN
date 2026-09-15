"""Shared active call registry across GOLDEN processes.

Maps Exotel Call Sids to GOLDEN case and thread identifiers so WebSocket
streams can recover case state even when telephony providers do not forward
custom query parameters or applet metadata.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("golden.voice.active_calls")

REGISTRY_FILE = Path(__file__).resolve().parent / ".active_calls.json"


def register_active_call(
    call_id: str,
    case_id: str,
    thread_id: str,
    recipient_phone: Optional[str] = None,
) -> None:
    """Register an outbound call immediately upon receipt of Exotel CallSid."""
    try:
        data: dict[str, Any] = {}
        if REGISTRY_FILE.exists():
            try:
                data = json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
            except Exception:
                data = {}

        entry = {
            "case_id": case_id,
            "thread_id": thread_id,
            "call_id": call_id,
            "recipient_phone": recipient_phone,
            "registered_at": time.time(),
        }

        # Keep by call_id and also as latest
        data[call_id] = entry
        data["latest"] = entry

        # Prune entries older than 30 minutes
        cutoff = time.time() - 1800
        data = {
            k: v for k, v in data.items()
            if k == "latest" or (isinstance(v, dict) and v.get("registered_at", 0) > cutoff)
        }

        REGISTRY_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
        logger.info("Registered active call %s for case %s (thread %s)", call_id, case_id, thread_id)
    except Exception as exc:
        logger.warning("Failed to record active call registry: %s", exc)


def lookup_active_call(call_id: Optional[str] = None) -> Optional[dict[str, Any]]:
    """Look up call identifiers by call_id, or return the most recently registered call."""
    try:
        if not REGISTRY_FILE.exists():
            return None
        data = json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))

        # Exact match by call_id
        if call_id and call_id in data and isinstance(data[call_id], dict):
            entry = data[call_id]
            # Only accept if registered within the last 15 minutes
            if time.time() - entry.get("registered_at", 0) < 900:
                return entry

        # No call_id supplied (or no match): return the most recently registered call
        # by comparing registered_at timestamps across all real entries.
        # Exclude the "latest" sentinel key and entries older than 15 minutes.
        cutoff = time.time() - 900
        candidates = [
            v for k, v in data.items()
            if k != "latest"
            and isinstance(v, dict)
            and v.get("registered_at", 0) > cutoff
            # Only treat as a real GOLDEN call if it has proper identifiers
            and v.get("case_id", "").startswith(("GOLDEN-", "CASE-"))
        ]
        if candidates:
            return max(candidates, key=lambda e: e.get("registered_at", 0))
    except Exception as exc:
        logger.warning("Failed to read active call registry: %s", exc)
    return None
