"""Safety, Guardrail, and Validation Layer for GOLDEN Emergency Decision Support.

Implements:
1. PIISanitizer: Indian national identifier & contact redaction (Aadhaar, Phone, PAN).
2. PromptInjectionDetector: Neutralizes instruction hijacking and jailbreak payloads in incident reports.
3. ClinicalSafetyValidator: Enforces protocol grounding, rationale depth, and prevents dangerous triage downgrades.
4. InterAgentContractGuard: Inter-agent schema contract enforcement with safe fail-open / fail-safe fallbacks.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple
from pydantic import ValidationError

from src.state.schema import TriageOutput, HospitalFhirOutput, HospitalCandidate


class SafetyViolationError(Exception):
    """Raised when an unrecoverable safety or security violation occurs."""
    pass


class PIISanitizer:
    """Sanitizes sensitive Personally Identifiable Information (PII) from text.

    Supports Indian identifier patterns:
    - Aadhaar (12 digits with optional spaces or hyphens)
    - Mobile numbers (10 digits with optional +91/91/0 prefix)
    - Permanent Account Number (PAN: 5 letters + 4 digits + 1 letter)
    """

    # Aadhaar pattern: 4 digits, separator, 4 digits, separator, 4 digits
    AADHAAR_PATTERN = re.compile(r"\b\d{4}[ -]\d{4}[ -]\d{4}\b|\b\d{12}\b")
    # Indian mobile numbers starting with 6, 7, 8, 9
    PHONE_PATTERN = re.compile(r"\b(?:\+91[\s-]?|91[\s-]?|0)?[6-9]\d{9}\b")
    # Indian PAN card pattern
    PAN_PATTERN = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]{1}\b")

    @classmethod
    def sanitize(cls, text: str) -> str:
        """Redact PII from narrative text with explicit replacement tokens."""
        if not text:
            return ""
        sanitized = cls.AADHAAR_PATTERN.sub("[AADHAAR-REDACTED]", text)
        sanitized = cls.PHONE_PATTERN.sub("[PHONE-REDACTED]", sanitized)
        sanitized = cls.PAN_PATTERN.sub("[PAN-REDACTED]", sanitized)
        return sanitized

    @classmethod
    def contains_pii(cls, text: str) -> bool:
        """Check if raw text contains any unredacted PII patterns."""
        if not text:
            return False
        return bool(
            cls.AADHAAR_PATTERN.search(text)
            or cls.PHONE_PATTERN.search(text)
            or cls.PAN_PATTERN.search(text)
        )


class PromptInjectionDetector:
    """Detects adversarial jailbreaks, system prompt overrides, and role confusion attempts."""

    INJECTION_PATTERNS = [
        re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions?", re.IGNORECASE),
        re.compile(r"disregard\s+(all\s+)?(guidelines|rules|prompts?)", re.IGNORECASE),
        re.compile(r"system\s+prompt\s+override", re.IGNORECASE),
        re.compile(r"you\s+are\s+now\s+(a\s+)?(doctor|physician|unrestricted|god)", re.IGNORECASE),
        re.compile(r"act\s+as\s+(an\s+)?unrestricted\s+ai", re.IGNORECASE),
        re.compile(r"forget\s+that\s+you\s+are", re.IGNORECASE),
        re.compile(r"jailbreak", re.IGNORECASE),
        re.compile(r"prescribe\s+(medicine|drugs?|narcotics?|dosage)", re.IGNORECASE),
    ]

    @classmethod
    def check_input(cls, raw_input: str) -> Tuple[bool, List[str]]:
        """Inspect raw incident text for adversarial injection attempts.

        Returns:
            (is_injection_detected, matched_patterns)
        """
        if not raw_input:
            return False, []

        matches = []
        for pattern in cls.INJECTION_PATTERNS:
            found = pattern.findall(raw_input)
            if found:
                matches.append(pattern.pattern)

        return len(matches) > 0, matches


class ClinicalSafetyValidator:
    """Validates clinical decisions against safety boundaries and established guidelines."""

    VALID_ACUITIES = {"RED", "YELLOW", "GREEN", "BLACK"}

    # High-risk symptoms that should NEVER be downgraded to GREEN without human sign-off
    HIGH_RISK_SYMPTOMS = [
        re.compile(r"\bunconscious\b", re.IGNORECASE),
        re.compile(r"\bunresponsive\b", re.IGNORECASE),
        re.compile(r"\bnot\s+breathing\b", re.IGNORECASE),
        re.compile(r"\bsevere\s+bleeding\b", re.IGNORECASE),
        re.compile(r"\bcardiac\s+arrest\b", re.IGNORECASE),
        re.compile(r"\bchest\s+pain\b", re.IGNORECASE),
        re.compile(r"\bcrushed\b", re.IGNORECASE),
        re.compile(r"\bhead\s+injury\b", re.IGNORECASE),
        re.compile(r"\bfemur\s+fracture\b", re.IGNORECASE),
        re.compile(r"\bamputation\b", re.IGNORECASE),
    ]

    @classmethod
    def validate_triage(
        cls,
        triage_output: TriageOutput,
        raw_narrative: str,
    ) -> Tuple[bool, List[str]]:
        """Validate clinical acuity, guideline citation, and safe downgrade boundaries.

        Returns:
            (is_valid, validation_warnings_or_errors)
        """
        issues: List[str] = []

        # 1. Acuity level validity
        if triage_output.acuity_level not in cls.VALID_ACUITIES:
            issues.append(f"Invalid acuity level: '{triage_output.acuity_level}'")

        # 2. Clinical rationale depth
        if not triage_output.rationale or len(triage_output.rationale.strip()) < 10:
            issues.append("Clinical rationale is missing or insufficient (<10 characters).")

        # 3. Guideline citation check
        guideline = (triage_output.guideline_reference or "").upper()
        if not any(k in guideline for k in ["AIIMS", "MORTH", "GOLDEN HOUR", "ATLS", "START"]):
            issues.append(
                f"Triage output references unrecognized guideline: '{triage_output.guideline_reference}'. "
                "Must reference AIIMS, MoRTH, ATLS, or START protocols."
            )

        # 4. Asymmetric Downgrade Prevention:
        # If narrative has high-risk trauma indicators, acuity must NOT be GREEN
        if triage_output.acuity_level == "GREEN":
            for pattern in cls.HIGH_RISK_SYMPTOMS:
                if pattern.search(raw_narrative):
                    issues.append(
                        f"CRITICAL SAFETY VIOLATION: Acuity downgraded to GREEN despite high-risk indicator "
                        f"matching pattern '{pattern.pattern}' in narrative."
                    )
                    break

        return len(issues) == 0, issues


class InterAgentContractGuard:
    """Guarantees schema integrity and fail-safe defaults across LangGraph node boundaries."""

    @classmethod
    def sanitize_triage_payload(
        cls,
        payload: Dict[str, Any],
        raw_narrative: str,
    ) -> TriageOutput:
        """Validate and sanitize TriageAgent output dictionary into a validated TriageOutput.

        If validation fails or a critical safety violation occurs, returns an emergency fail-safe RED state.
        """
        try:
            triage_obj = TriageOutput.model_validate(payload)
            is_valid, issues = ClinicalSafetyValidator.validate_triage(triage_obj, raw_narrative)
            if not is_valid:
                # Log issues and return an escalated safe default
                return TriageOutput(
                    acuity_level="RED",
                    hard_sos=True,
                    confidence=1.0,
                    rationale=f"SAFETY ESCALATION: Automatic fail-safe RED applied due to validation issues: {'; '.join(issues)}",
                    guideline_reference="MoRTH Golden Hour SOP 2025 (Safety Escalation)",
                    retry_count=triage_obj.retry_count + 1,
                )
            return triage_obj
        except ValidationError as ve:
            return TriageOutput(
                acuity_level="RED",
                hard_sos=True,
                confidence=1.0,
                rationale=f"SAFETY ESCALATION: Pydantic validation failure ({str(ve)[:100]}). Defaulted to immediate emergency RED.",
                guideline_reference="MoRTH Golden Hour SOP 2025 (Schema Guardrail Fallback)",
                retry_count=1,
            )

    @classmethod
    def sanitize_hospital_payload(cls, payload: Dict[str, Any]) -> HospitalFhirOutput:
        """Validate and sanitize HospitalAgent output dictionary into a validated HospitalFhirOutput.

        Guarantees that a valid hospital candidate is always present.
        """
        fallback_candidate = HospitalCandidate(
            hospital_id="HOSP-FALLBACK-01",
            name="District Headquarters Emergency Hospital (Fallback)",
            distance_km=10.0,
            trauma_level="DISTRICT_HOSPITAL",
            specialties_available=["Emergency Medicine", "General Surgery"],
            available_icu_beds=1,
            available_er_beds=2,
            score=10.0,
        )
        try:
            output = HospitalFhirOutput.model_validate(payload)
            # If candidate hospitals is empty or no hospital was selected, inject safe fallback
            if not output.candidate_hospitals or not output.selected_hospital_id:
                return HospitalFhirOutput(
                    candidate_hospitals=[fallback_candidate],
                    selected_hospital_id=fallback_candidate.hospital_id,
                    selected_hospital_name=fallback_candidate.name,
                    bed_status="REQUESTED",
                    fhir_submission_status="FAILED",
                )
            return output
        except (ValidationError, Exception):
            return HospitalFhirOutput(
                candidate_hospitals=[fallback_candidate],
                selected_hospital_id=fallback_candidate.hospital_id,
                selected_hospital_name=fallback_candidate.name,
                bed_status="REQUESTED",
                fhir_submission_status="FAILED",
            )
