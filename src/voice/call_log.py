"""Durable Exotel voice-call log for GOLDEN.

One JSON store (logs/voice_call_logs.json) records every GOLDEN family call
across its full lifecycle so dashboards and audits can replay it later:

1. TRIGGERED  - outbound call placed (Exotel connect.json or local simulation).
2. IN_PROGRESS- Exotel WebSocket stream answered and the voice session started.
3. PROVIDER   - Exotel status callbacks (ringing, busy, no-answer, completed...).
4. OUTCOME    - structured callback from the voice server with the collected
                medical disclosures, transcript, and latency metrics.

The store is intentionally a flat JSON file: no database exists in this project
and the file survives restarts like logs/ and the active-call registry.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("golden.voice.call_log")

CALL_LOG_FILE = Path("logs") / "voice_call_logs.json"
MAX_ENTRIES = 500

_lock = threading.Lock()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load() -> Dict[str, Dict[str, Any]]:
    try:
        if CALL_LOG_FILE.exists():
            data = json.loads(CALL_LOG_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except Exception as exc:
        logger.warning("Failed to read call log store: %s", exc)
    return {}


def _save(data: Dict[str, Dict[str, Any]]) -> None:
    try:
        CALL_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        if len(data) > MAX_ENTRIES:
            ordered = sorted(
                (entry for entry in data.values() if isinstance(entry, dict)),
                key=lambda e: e.get("triggered_at") or "",
            )
            data = {entry["call_id"]: entry for entry in ordered[-MAX_ENTRIES:]}
        CALL_LOG_FILE.write_text(
            json.dumps(data, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
    except Exception as exc:
        logger.warning("Failed to persist call log store: %s", exc)


def _upsert(call_id: str, mutate) -> Optional[Dict[str, Any]]:
    """Apply one mutation to a call entry under the store lock."""
    if not call_id:
        return None
    with _lock:
        data = _load()
        entry = data.get(call_id) or {"call_id": call_id}
        mutate(entry)
        entry["updated_at"] = _now_iso()
        data[call_id] = entry
        _save(data)
        return dict(entry)


def record_call_trigger(
    call_id: str,
    case_id: str,
    thread_id: Optional[str],
    recipient_phone: Optional[str],
    provider: str,
    status: str,
    consent_basis: Optional[str] = None,
    triggered_by: Optional[str] = None,
    message: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Create the call entry the moment an outbound call is placed."""

    def mutate(entry: Dict[str, Any]) -> None:
        entry.update({
            "case_id": case_id,
            "thread_id": thread_id,
            "recipient_phone": recipient_phone,
            "provider": provider,
            "status": status,
            "consent_basis": consent_basis,
            "triggered_by": triggered_by,
            "message": message,
            "triggered_at": _now_iso(),
            "status_history": [{
                "status": status,
                "at": _now_iso(),
                "source": "trigger",
                "details": message,
            }],
        })

    return _upsert(call_id, mutate)


def record_call_status(
    call_id: str,
    status: str,
    source: str = "voice_server",
    details: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Append one status transition (IN_PROGRESS, FAILED, NO_ANSWER, ...)."""

    def mutate(entry: Dict[str, Any]) -> None:
        entry["status"] = status
        history = entry.setdefault("status_history", [])
        history.append({"status": status, "at": _now_iso(), "source": source, "details": details})
        if status == "IN_PROGRESS" and not entry.get("started_at"):
            entry["started_at"] = _now_iso()
        if status in {"COMPLETED", "FAILED", "NO_ANSWER", "CONSENT_REFUSED"} and not entry.get("ended_at"):
            entry["ended_at"] = _now_iso()

    return _upsert(call_id, mutate)


def attach_outcome(call_id: str, outcome: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Merge the structured end-of-call callback payload into the entry."""

    def mutate(entry: Dict[str, Any]) -> None:
        entry["outcome"] = outcome
        entry["status"] = outcome.get("call_status", entry.get("status"))
        if outcome.get("call_duration_seconds") is not None:
            entry["call_duration_seconds"] = outcome.get("call_duration_seconds")
        if outcome.get("transcript_path"):
            entry["transcript_path"] = outcome.get("transcript_path")
        if outcome.get("latency"):
            entry["latency"] = outcome.get("latency")
        history = entry.setdefault("status_history", [])
        history.append({
            "status": entry["status"],
            "at": outcome.get("completed_at") or _now_iso(),
            "source": "outcome_callback",
            "details": outcome.get("call_summary"),
        })

    return _upsert(call_id, mutate)


def attach_exotel_status(call_id: str, fields: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Record one Exotel telephony status callback (CallSid, Status, Duration...)."""

    def mutate(entry: Dict[str, Any]) -> None:
        provider = entry.setdefault("exotel_status_events", [])
        provider.append({"at": _now_iso(), "fields": fields})
        status = fields.get("Status") or fields.get("CallStatus") or fields.get("status")
        entry["exotel_last_status"] = status
        if status:
            history = entry.setdefault("status_history", [])
            history.append({"status": f"EXOTEL_{status}", "at": _now_iso(), "source": "exotel_status_callback"})
        if fields.get("Duration"):
            entry["exotel_duration_seconds"] = fields.get("Duration")
        if fields.get("RecordingUrl"):
            entry["recording_url"] = fields.get("RecordingUrl")

    return _upsert(call_id, mutate)


def get_calls(case_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    """Return newest-first call entries, optionally filtered by case."""
    with _lock:
        entries = list(_load().values())
    if case_id:
        entries = [e for e in entries if e.get("case_id") == case_id]
    entries.sort(key=lambda e: e.get("triggered_at") or e.get("updated_at") or "", reverse=True)
    return entries[: max(limit, 1)]


def find_call_for_case(case_id: str) -> Optional[Dict[str, Any]]:
    """Most recent call entry for a case, if any."""
    calls = get_calls(case_id=case_id, limit=1)
    return calls[0] if calls else None


def find_call_by_id(call_id: str) -> Optional[Dict[str, Any]]:
    """Exact call entry lookup by Exotel CallSid / GOLDEN call id."""
    with _lock:
        entry = _load().get(call_id)
    return dict(entry) if entry else None
