"""Per-call transcript and voice-event logging."""

from __future__ import annotations

import logging
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class VoiceTranscriptLogger:
    """Write one readable transcript file for a single voice call."""

    def __init__(self, case_id: str, call_id: str, *, root: Path | None = None) -> None:
        log_dir = root or Path("logs") / "voice"
        log_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        filename = f"{self._safe(case_id)}_{self._safe(call_id)}_{timestamp}.log"
        self.path = log_dir / filename
        self._pending: dict[str, list[str]] = {"CALLER": [], "AGENT": []}
        self._write(f"VOICE CALL {case_id} / {call_id}\n")
        self._write("Raw audio is not stored; this file contains text and event metadata.\n\n")

    @staticmethod
    def _safe(value: str) -> str:
        return re.sub(r"[^A-Za-z0-9_.-]", "_", value)

    def _write(self, text: str) -> None:
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(text)

    def add_transcript(self, role: str, text: Any) -> None:
        """Buffer provider transcript fragments until a turn is complete."""
        cleaned = str(text or "").strip()
        if cleaned and role in self._pending:
            self._pending[role].append(cleaned)

    def finish_turn(self) -> dict[str, str]:
        """Write buffered caller and agent fragments as complete turns."""
        completed: dict[str, str] = {}
        for role in ("CALLER", "AGENT"):
            text = " ".join(self._pending[role]).strip()
            if text:
                self._write(f"{role}: {text}\n")
                completed[role] = text
            self._pending[role].clear()
        if completed:
            self._write("\n")
        return completed

    def event(self, name: str, details: Any = "") -> None:
        """Write a non-transcript event such as a tool call or provider error."""
        if details:
            encoded = json.dumps(details, ensure_ascii=False, default=str)
            suffix = f" | {encoded}"
        else:
            suffix = ""
        self._write(f"EVENT {name}{suffix}\n")

    def close(self) -> None:
        """Flush the final partial turn and close the logical call record."""
        self.finish_turn()
        self.event("CALL_LOG_CLOSED")
