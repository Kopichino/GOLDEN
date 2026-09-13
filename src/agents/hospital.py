import math
import time
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple

from src.fhir.client import FhirClient
from src.fhir.bundle_builder import FhirBundleBuilder
from src.state.schema import (
    GoldenCaseState,
    HospitalCandidate,
    HospitalFhirOutput
)

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0)**2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return round(r * c, 2)


class HospitalDiscovery:
    """Stage 1: Spatial and Capability Discovery Service.
    
    Queries FHIR Organization resources and hospital capability extensions
    independent of clinical acuity reasoning.
    """

    def __init__(self, fhir_client: Optional[FhirClient] = None):
        self.client = fhir_client or FhirClient()

    def query_candidate_hospitals(self) -> List[Dict[str, Any]]:
        # Turn 1: Retrieve organizations of type Healthcare Provider
        search_bundle = self.client.search("Organization", params={"type": "prov"})
        entries = search_bundle.get("entry", [])
        return [entry["resource"] for entry in entries if "resource" in entry]

    def get_hospital_capabilities(self, org_id: str) -> Dict[str, Any]:
        # Turn 2: Targeted query for specific hospital resource to read capability extensions
        hospital_res = self.client.get_resource("Organization", org_id)
        extensions = hospital_res.get("extension", [])
        caps = {
            "trauma_level": "LEVEL_2",
            "icu_beds": 5,
            "er_beds": 10,
            "latitude": 13.0827,
            "longitude": 80.2707
        }
        for ext in extensions:
            url = ext.get("url", "")
            if "trauma-level" in url:
                caps["trauma_level"] = ext.get("valueString", "LEVEL_2")
            elif "icu-beds" in url:
                caps["icu_beds"] = ext.get("valueInteger", 0)
            elif "er-beds" in url:
                caps["er_beds"] = ext.get("valueInteger", 0)
            elif "latitude" in url:
                caps["latitude"] = float(ext.get("valueDecimal", 13.0827))
            elif "longitude" in url:
                caps["longitude"] = float(ext.get("valueDecimal", 80.2707))
        return caps

    def discover_candidates(
        self,
        incident_lat: float,
        incident_lon: float
    ) -> List[HospitalCandidate]:
        """Discover nearby candidate facilities and their real-time capabilities via FHIR."""
        raw_orgs = self.query_candidate_hospitals()
        candidates: List[HospitalCandidate] = []

        for org in raw_orgs:
            org_id = org.get("id", "")
            org_name = org.get("name", "Unknown Hospital")
            caps = self.get_hospital_capabilities(org_id)

            dist_km = haversine_distance(incident_lat, incident_lon, caps["latitude"], caps["longitude"])
            trauma_level = caps["trauma_level"]
            icu_beds = caps["icu_beds"]
            er_beds = caps["er_beds"]

            candidates.append(
                HospitalCandidate(
                    hospital_id=org_id,
                    name=org_name,
                    distance_km=dist_km,
                    trauma_level=trauma_level,  # type: ignore
                    specialties_available=["trauma", "ortho", "icu"],
                    available_icu_beds=icu_beds,
                    available_er_beds=er_beds,
                    score=0.0
                )
            )

        candidates.sort(key=lambda x: x.distance_km)
        return candidates


class HospitalMatcher:
    """Stage 2: Deterministic Clinical Acuity Multi-Factor Matching Engine.
    
    Ranks discovered facilities using validated clinical triage acuity, trauma level,
    bed availability, and spatial distance.
    """

    def __init__(self):
        pass

    def score_candidate(self, c: HospitalCandidate, acuity_level: str) -> float:
        score = 0.0
        if acuity_level == "RED":
            if c.trauma_level == "LEVEL_1":
                score += 60.0
            elif c.trauma_level == "LEVEL_2":
                score += 30.0
            score += min(c.available_icu_beds * 4.0, 30.0)
        elif acuity_level == "YELLOW":
            if c.trauma_level in ["LEVEL_1", "LEVEL_2"]:
                score += 40.0
            score += min(c.available_er_beds * 3.0, 30.0)
        else:  # GREEN / BLACK / default
            score += min(c.available_er_beds * 2.0, 30.0)

        score -= (c.distance_km * 2.5)
        return round(score, 2)

    def match_and_rank(
        self,
        candidates: List[HospitalCandidate],
        acuity_level: str
    ) -> Tuple[List[HospitalCandidate], str]:
        """Deterministically match and rank candidate facilities using validated triage acuity."""
        scored_candidates: List[HospitalCandidate] = []

        for c in candidates:
            score = self.score_candidate(c, acuity_level)
            updated = c.model_copy()
            updated.score = score
            scored_candidates.append(updated)

        scored_candidates.sort(key=lambda x: x.score, reverse=True)

        top = scored_candidates[0] if scored_candidates else None
        if top:
            reason = (
                f"Selected {top.name} for {acuity_level} acuity: "
                f"Trauma {top.trauma_level}, {top.available_icu_beds} ICU beds, "
                f"{top.available_er_beds} ER beds, distance {top.distance_km:.1f}km (Score: {top.score})"
            )
        else:
            reason = "No hospital candidates available in the registry"

        return scored_candidates, reason


class FhirToolService:
    """Stage 3: FHIR Pre-Registration Tool Service.
    
    Submits structured FHIR transaction bundles (Patient, Encounter, Condition)
    to HAPI FHIR server.
    """

    def __init__(self, fhir_client: Optional[FhirClient] = None):
        self.client = fhir_client or FhirClient()

    def pre_register_patient(
        self,
        state: GoldenCaseState,
        selected_hospital: HospitalCandidate
    ) -> Tuple[str, str, str, str]:
        patient_name = f"Unidentified Trauma Victim ({state.input_data.case_id})"
        caller_phone = state.input_data.caller_phone
        acuity = state.triage.acuity_level or "RED"
        desc = state.input_data.raw_input

        bundle = FhirBundleBuilder.create_pre_registration_bundle(
            patient_name=patient_name,
            phone=caller_phone,
            acuity_code=acuity,
            incident_description=desc,
            location_name=selected_hospital.name
        )

        response = self.client.submit_bundle(bundle)
        bundle_id = response.get("id", str(time.time()))

        patient_id, encounter_id, condition_id = "", "", ""
        for entry in response.get("entry", []):
            location_hdr = entry.get("response", {}).get("location", "")
            if "Patient/" in location_hdr:
                patient_id = location_hdr.split("/_history")[0].replace("Patient/", "")
            elif "Encounter/" in location_hdr:
                encounter_id = location_hdr.split("/_history")[0].replace("Encounter/", "")
            elif "Condition/" in location_hdr:
                condition_id = location_hdr.split("/_history")[0].replace("Condition/", "")

        return bundle_id, patient_id, encounter_id, condition_id


class HospitalAgent:
    """Composing Facade for Hospital Discovery, Matching, and FHIR Pre-Registration.
    
    Provides 100% backward compatibility for all existing methods and tests.
    """

    def __init__(self, fhir_client: Optional[FhirClient] = None):
        self.client = fhir_client or FhirClient()
        self.discovery = HospitalDiscovery(self.client)
        self.matcher = HospitalMatcher()
        self.fhir_service = FhirToolService(self.client)

    def query_candidate_hospitals(self) -> List[Dict[str, Any]]:
        return self.discovery.query_candidate_hospitals()

    def get_hospital_capabilities(self, org_id: str) -> Dict[str, Any]:
        return self.discovery.get_hospital_capabilities(org_id)

    def discover_candidates(
        self,
        incident_lat: float,
        incident_lon: float
    ) -> List[HospitalCandidate]:
        return self.discovery.discover_candidates(incident_lat, incident_lon)

    def match_and_rank(
        self,
        candidates: List[HospitalCandidate],
        acuity_level: str
    ) -> Tuple[List[HospitalCandidate], str]:
        return self.matcher.match_and_rank(candidates, acuity_level)

    def rank_hospitals(
        self,
        incident_lat: float,
        incident_lon: float,
        acuity_level: str
    ) -> List[HospitalCandidate]:
        """Convenience method combining discovery and matching (for backward compatibility)."""
        raw = self.discover_candidates(incident_lat, incident_lon)
        ranked, _ = self.match_and_rank(raw, acuity_level)
        return ranked

    def pre_register_patient(
        self,
        state: GoldenCaseState,
        selected_hospital: HospitalCandidate
    ) -> Tuple[str, str, str, str]:
        return self.fhir_service.pre_register_patient(state, selected_hospital)

    def run(self, state: GoldenCaseState) -> GoldenCaseState:
        acuity = state.triage.acuity_level or ("RED" if state.triage.hard_sos else "YELLOW")
        raw = self.discover_candidates(
            incident_lat=state.input_data.location.latitude,
            incident_lon=state.input_data.location.longitude
        )
        candidates, reason = self.match_and_rank(raw, acuity)

        if not candidates:
            state.record_error("hospital_workflow", "NoHospitalsFound", "No candidate hospitals available in registry")
            return state

        selected = candidates[0]
        state.hospital_fhir.raw_candidates = raw
        state.hospital_fhir.candidate_hospitals = candidates
        state.hospital_fhir.selected_hospital_id = selected.hospital_id
        state.hospital_fhir.selected_hospital_name = selected.name
        state.hospital_fhir.ranking_reason = reason
        state.hospital_fhir.bed_status = "REQUESTED"

        # Pre-register patient on FHIR server
        try:
            bundle_id, p_id, enc_id, cond_id = self.pre_register_patient(state, selected)
            state.hospital_fhir.fhir_bundle_id = bundle_id
            state.hospital_fhir.fhir_patient_id = p_id
            state.hospital_fhir.fhir_encounter_id = enc_id
            state.hospital_fhir.fhir_condition_id = cond_id
            state.hospital_fhir.fhir_submission_status = "SUCCESS"
            state.hospital_fhir.fhir_submission_timestamp = datetime.now(timezone.utc)
            state.hospital_fhir.bed_status = "CONFIRMED"
            state.add_audit_entry(
                agent_name="hospital_workflow",
                action="fhir_pre_registration_completed",
                details={
                    "selected_hospital": selected.name,
                    "distance_km": selected.distance_km,
                    "score": selected.score,
                    "ranking_reason": reason,
                    "patient_id": p_id,
                    "encounter_id": enc_id,
                    "condition_id": cond_id
                }
            )
        except Exception as e:
            state.hospital_fhir.fhir_submission_status = "FAILED"
            state.record_error("hospital_workflow", "FhirSubmissionError", str(e))

        return state
