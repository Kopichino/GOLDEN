from datetime import datetime, timezone
from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

# =====================================================================
# SECTION 1: Case Identity & Input
# =====================================================================
class IncidentLocation(BaseModel):
    latitude: float = Field(..., description="Latitude of incident")
    longitude: float = Field(..., description="Longitude of incident")
    address_or_landmark: str = Field(..., description="Reported landmark / highway / junction")
    district: Optional[str] = Field(default="Chennai", description="Administrative district")

class CaseIdentityInput(BaseModel):
    case_id: str = Field(..., description="Unique case identifier (e.g. CASE-2026-XXXX)")
    caller_phone: Optional[str] = Field(default=None, description="Inbound caller number")
    raw_input: str = Field(..., description="Verbatim incident report (text or transcribed STT)")
    language: str = Field(default="en", description="Detected language code: en, ta, ta-en-codemix")
    modality: Literal["text", "voice_stt", "manual_dispatcher"] = Field(default="text")
    location: IncidentLocation = Field(..., description="Incident geo-coordinates and landmark")
    reported_at: datetime = Field(default_factory=utc_now)

# =====================================================================
# SECTION 2: Triage Output
# =====================================================================
class TriageOutput(BaseModel):
    acuity_level: Optional[Literal["RED", "YELLOW", "GREEN", "BLACK"]] = Field(
        default=None,
        description="RED: Immediate life threat; YELLOW: Urgent; GREEN: Non-urgent; BLACK: Deceased"
    )
    hard_sos: bool = Field(default=False, description="Deterministic safety override flag")
    hard_sos_triggers: List[str] = Field(default_factory=list, description="Keywords/patterns matched")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Confidence score from 0.0 to 1.0")
    rationale: Optional[str] = Field(default=None, description="Clinical justification for acuity")
    guideline_reference: Optional[str] = Field(
        default=None,
        description="Referenced clinical standard (e.g. AIIMS Triage Protocol / MoRTH 2025 SOP)"
    )
    retry_count: int = Field(default=0, ge=0, description="Schema retry count if validation failed")
    triage_completed_at: Optional[datetime] = None

# =====================================================================
# SECTION 3: Hospital / FHIR
# =====================================================================
class HospitalCandidate(BaseModel):
    hospital_id: str = Field(..., description="Unique hospital identifier")
    name: str = Field(..., description="Hospital facility name")
    distance_km: float = Field(..., ge=0.0, description="Distance from incident in kilometers")
    trauma_level: Literal["LEVEL_1", "LEVEL_2", "LEVEL_3", "DISTRICT_HOSPITAL"]
    specialties_available: List[str] = Field(default_factory=list, description="e.g. neurosurgery, ortho")
    available_icu_beds: int = Field(default=0, ge=0)
    available_er_beds: int = Field(default=0, ge=0)
    score: float = Field(default=0.0, description="Calculated recommendation score")

class HospitalFhirOutput(BaseModel):
    candidate_hospitals: List[HospitalCandidate] = Field(default_factory=list)
    selected_hospital_id: Optional[str] = None
    selected_hospital_name: Optional[str] = None
    bed_status: Literal["NONE", "REQUESTED", "CONFIRMED", "UNAVAILABLE"] = Field(default="NONE")
    fhir_bundle_id: Optional[str] = Field(default=None, description="ID of FHIR transaction bundle")
    fhir_patient_id: Optional[str] = Field(default=None, description="HAPI FHIR Patient resource ID")
    fhir_encounter_id: Optional[str] = Field(default=None, description="HAPI FHIR Encounter resource ID")
    fhir_condition_id: Optional[str] = Field(default=None, description="HAPI FHIR Condition resource ID")
    fhir_submission_status: Literal["PENDING", "SUCCESS", "FAILED"] = Field(default="PENDING")
    fhir_submission_timestamp: Optional[datetime] = None

# =====================================================================
# SECTION 4: Voice / Family
# =====================================================================
class VoiceFamilyOutput(BaseModel):
    call_status: Literal[
        "IDLE", "TRIGGERED", "IN_PROGRESS", "COMPLETED", "FAILED", "NO_ANSWER", "CONSENT_REFUSED"
    ] = Field(default="IDLE")
    call_id: Optional[str] = Field(default=None, description="Exotel call SID")
    recipient_phone: Optional[str] = Field(default=None, description="Consenting team test number")
    recipient_relationship: Optional[str] = Field(default=None, description="e.g. spouse, parent")
    consent_granted: Optional[bool] = Field(default=None, description="TRAI TCCCPR 2018 consent confirmation")
    allergies: List[str] = Field(default_factory=list, description="Reported patient drug/food allergies")
    medications: List[str] = Field(default_factory=list, description="Current medications")
    blood_group: Optional[str] = Field(default=None, description="Reported blood group (e.g. O+, A-)")
    pre_existing_conditions: List[str] = Field(default_factory=list)
    call_summary: Optional[str] = Field(default=None)
    call_duration_seconds: Optional[int] = Field(default=None, ge=0)
    resumed_at: Optional[datetime] = None

# =====================================================================
# SECTION 5: Control & Audit
# =====================================================================
class AuditError(BaseModel):
    node: str
    timestamp: datetime = Field(default_factory=utc_now)
    error_type: str
    message: str
    recovered: bool = False

class AuditLogEntry(BaseModel):
    timestamp: datetime = Field(default_factory=utc_now)
    agent_name: str
    action: str
    latency_ms: Optional[float] = None
    details: Dict[str, Any] = Field(default_factory=dict)

class ControlAudit(BaseModel):
    current_node: str = Field(default="entry", description="Current active node in LangGraph")
    execution_stage: Literal[
        "INGESTION",
        "HARD_SOS_CHECK",
        "PARALLEL_TRIAGE_HOSPITAL",
        "COORDINATOR_MERGE",
        "VOICE_DISPATCH",
        "AWAITING_WEBHOOK",
        "COMPLETED",
        "FAILED"
    ] = Field(default="INGESTION")
    active_provider: Literal["groq", "gemini", "openrouter", "ollama_local"] = Field(default="groq")
    fallback_active: bool = Field(default=False)
    thread_id: str = Field(..., description="LangGraph durable checkpoint thread_id")
    errors: List[AuditError] = Field(default_factory=list)
    audit_trail: List[AuditLogEntry] = Field(default_factory=list)
    started_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    completed_at: Optional[datetime] = None

# =====================================================================
# ROOT SHARED STATE: GoldenCaseState
# =====================================================================
class GoldenCaseState(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    input_data: CaseIdentityInput
    triage: TriageOutput = Field(default_factory=TriageOutput)
    hospital_fhir: HospitalFhirOutput = Field(default_factory=HospitalFhirOutput)
    voice_family: VoiceFamilyOutput = Field(default_factory=VoiceFamilyOutput)
    control_audit: ControlAudit

    def add_audit_entry(self, agent_name: str, action: str, latency_ms: Optional[float] = None, details: Optional[Dict[str, Any]] = None):
        self.control_audit.audit_trail.append(
            AuditLogEntry(
                agent_name=agent_name,
                action=action,
                latency_ms=latency_ms,
                details=details or {}
            )
        )
        self.control_audit.updated_at = utc_now()

    def record_error(self, node: str, error_type: str, message: str, recovered: bool = False):
        self.control_audit.errors.append(
            AuditError(
                node=node,
                error_type=error_type,
                message=message,
                recovered=recovered
            )
        )
        self.control_audit.updated_at = utc_now()
