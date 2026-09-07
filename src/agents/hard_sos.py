import re
import time
from typing import Tuple, List

HARD_SOS_PATTERNS = [
    (r"\b(unresponsive|unconscious|fainted|passed\s*out|comatose|not\s*waking\s*up)\b", "UNRESPONSIVE_PATIENT"),
    (r"\b(not\s*breathing|stopped\s*breathing|gasping\s*for\s*air|cannot\s*breathe|no\s*breath|asphyxiat\w*|choking)\b", "RESPIRATORY_ARREST"),
    (r"\b(no\s*pulse|heart\s*stopped|cardiac\s*arrest|cpr\s*needed|flatlin\w*)\b", "CARDIAC_ARREST"),
    (r"\b(severe\s*bleeding|bleeding\s*heavily|gushing\s*blood|blood\s*pooling|arterial\s*bleed\w*|soaked\s*in\s*blood)\b", "MASSIVE_HEMORRHAGE"),
    (r"\b(crush(ed)?\s*(injury|under)|trapped\s*under\s*(truck|bus|vehicle|debris)|severed\s*(limb|leg|arm|head)|amputat\w*)\b", "CATASTROPHIC_TRAUMA"),
    (r"\b(head\s*injury|skull\s*fracture|brain\s*exposed|seizure\s*continuous|convuls\w*)\b", "SEVERE_NEUROLOGICAL_CRISIS"),
]

COMPILED_PATTERNS = [(re.compile(pattern, re.IGNORECASE), code) for pattern, code in HARD_SOS_PATTERNS]

class HardSosEngine:
    @staticmethod
    def evaluate(text: str) -> Tuple[bool, List[str], str, float]:
        start_time = time.perf_counter()
        normalized = text.lower()
        matched_triggers: List[str] = []

        for regex, code in COMPILED_PATTERNS:
            match = regex.search(normalized)
            if match:
                matched_triggers.append(f"{code}:{match.group(0)}")

        latency_ms = (time.perf_counter() - start_time) * 1000.0

        if matched_triggers:
            rationale = f"Hard-SOS triggered by critical life-threat indicators: {', '.join(matched_triggers)}"
            return True, matched_triggers, rationale, latency_ms

        return False, [], "No deterministic hard-SOS indicators matched; proceeding to LLM triage", latency_ms
