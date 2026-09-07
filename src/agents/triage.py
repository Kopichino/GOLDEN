import json
import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, ValidationError

from src.config import settings
from src.state.schema import TriageOutput, GoldenCaseState

TRIAGE_SYSTEM_PROMPT = """You are GOLDEN's Guideline-Grounded Pre-Hospital Triage Agent for Indian Emergency Medical Services (108/112).
Your role is to classify patient acuity based on clinical guidelines (AIIMS Emergency Department Triage Protocol / MoRTH Road Accident Golden Hour SOP 2025).

Acuity Levels:
- RED: Immediate life threat (compromised airway, respiratory distress, shock, altered consciousness, uncontrolled hemorrhage). Time to physician: Immediate (0 min).
- YELLOW: Urgent (severe pain, potential fractures with intact circulation, moderate blood loss, stable vital signs with high-energy trauma). Time to physician: <= 15 min.
- GREEN: Non-urgent / Delayed (minor abrasions, isolated superficial lacerations, normal ambulation, sprains). Time to physician: <= 60 min.
- BLACK: Clinically deceased / catastrophic non-survivable injuries with absent vital signs.

CRITICAL INSTRUCTION:
You must output ONLY a valid, raw JSON object matching this exact schema:
{
  "acuity_level": "RED" | "YELLOW" | "GREEN" | "BLACK",
  "confidence": 0.0 to 1.0,
  "rationale": "Clinical rationale referencing reported signs, symptoms, and mechanism of injury",
  "guideline_reference": "AIIMS Emergency Triage Protocol 2024 / MoRTH Golden Hour Care Standard"
}
Do not include any conversational filler, markdown codeblocks (no ```json), or explanation outside the JSON object.
"""

class TriageLLMResponse(BaseModel):
    acuity_level: str = Field(..., pattern="^(RED|YELLOW|GREEN|BLACK)$")
    confidence: float = Field(..., ge=0.0, le=1.0)
    rationale: str = Field(..., min_length=5)
    guideline_reference: str = Field(default="AIIMS Emergency Triage Protocol 2024")

class TriageAgent:
    def __init__(self, provider: Optional[str] = None):
        self.provider = provider or settings.DEFAULT_LLM_PROVIDER
        self.max_retries = settings.SCHEMA_MAX_RETRIES

    def _call_llm(self, prompt: str, system_prompt: str) -> str:
        # Prioritize Gemini for ultra-low latency direct JSON, fallback to Groq
        providers = [self.provider]
        if "gemini" not in providers:
            providers.insert(0, "gemini")
        if "groq" not in providers:
            providers.append("groq")

        last_exc = None
        for p in providers:
            try:
                if p == "gemini" and settings.GEMINI_API_KEY:
                    return self._call_gemini(prompt, system_prompt)
                elif p == "groq" and settings.GROQ_API_KEY:
                    return self._call_groq(prompt, system_prompt)
            except Exception as e:
                last_exc = e
                continue

        raise RuntimeError(f"All triage LLM providers failed. Last error: {last_exc}")

    def _call_groq(self, prompt: str, system_prompt: str) -> str:
        from groq import Groq
        client = Groq(api_key=settings.GROQ_API_KEY)
        completion = client.chat.completions.create(
            model="qwen/qwen3.6-27b",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=350,
        )
        return completion.choices[0].message.content.strip()

    def _call_gemini(self, prompt: str, system_prompt: str) -> str:
        from google import genai
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        full_content = f"{system_prompt}\n\nUser Report:\n{prompt}"
        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=full_content,
        )
        return response.text.strip()

    def _clean_json_str(self, raw_text: str) -> str:
        import re
        # Strip <think> tags from reasoning models like Qwen / DeepSeek
        text = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.DOTALL).strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        # Find opening and closing JSON braces if surrounding text exists
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if match:
            return match.group(0).strip()
        return text

    def triage_incident(self, incident_text: str, location_text: str = "") -> TriageOutput:
        start_time = time.perf_counter()
        user_prompt = f"Incident Report: {incident_text}\nLocation Context: {location_text}"
        system_prompt = TRIAGE_SYSTEM_PROMPT
        last_error = ""

        for attempt in range(self.max_retries + 1):
            if attempt > 0:
                retry_prompt = (
                    f"{user_prompt}\n\n"
                    f"PREVIOUS OUTPUT FAILED VALIDATION: {last_error}\n"
                    f"Fix the error and return ONLY valid JSON matching the schema."
                )
            else:
                retry_prompt = user_prompt

            raw_response = self._call_llm(retry_prompt, system_prompt)
            cleaned = self._clean_json_str(raw_response)

            try:
                data = json.loads(cleaned)
                parsed = TriageLLMResponse.model_validate(data)
                latency_ms = (time.perf_counter() - start_time) * 1000.0

                return TriageOutput(
                    acuity_level=parsed.acuity_level, # type: ignore
                    hard_sos=False,
                    confidence=parsed.confidence,
                    rationale=parsed.rationale,
                    guideline_reference=parsed.guideline_reference,
                    retry_count=attempt,
                    triage_completed_at=datetime.now(timezone.utc)
                )
            except (json.JSONDecodeError, ValidationError) as e:
                last_error = str(e)

        return TriageOutput(
            acuity_level="YELLOW",
            hard_sos=False,
            confidence=0.5,
            rationale=f"Triage fallback after {self.max_retries} schema validation retries. Error: {last_error}",
            guideline_reference="MoRTH Default Pre-Hospital Safety Protocol",
            retry_count=self.max_retries,
            triage_completed_at=datetime.now(timezone.utc)
        )

    def run(self, state: GoldenCaseState) -> GoldenCaseState:
        triage_res = self.triage_incident(
            incident_text=state.input_data.raw_input,
            location_text=state.input_data.location.address_or_landmark
        )
        state.triage = triage_res
        state.add_audit_entry(
            agent_name="triage_agent",
            action="acuity_classified",
            details={
                "acuity": triage_res.acuity_level,
                "confidence": triage_res.confidence,
                "retries": triage_res.retry_count
            }
        )
        return state
