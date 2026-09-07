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

class HospitalAgent:
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

    def rank_hospitals(
        self,
        incident_lat: float,
        incident_lon: float,
        acuity_level: str
    ) -> List[HospitalCandidate]:
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

            # Multi-factorial scoring: Acuity suitability + bed availability - distance penalty
            score = 0.0
            if acuity_level == "RED":
                if trauma_level == "LEVEL_1":
                    score += 60.0
                elif trauma_level == "LEVEL_2":
                    score += 30.0
                score += min(icu_beds * 4.0, 30.0)
            elif acuity_level == "YELLOW":
                if trauma_level in ["LEVEL_1", "LEVEL_2"]:
                    score += 40.0
                score += min(er_beds * 3.0, 30.0)
            else: # GREEN / default
                score += min(er_beds * 2.0, 30.0)

            score -= (dist_km * 2.5)

            candidates.append(
                HospitalCandidate(
                    hospital_id=org_id,
                    name=org_name,
                    distance_km=dist_km,
                    trauma_level=trauma_level, # type: ignore
                    specialties_available=["trauma", "ortho", "icu"],
                    available_icu_beds=icu_beds,
                    available_er_beds=er_beds,
                    score=round(score, 2)
                )
            )

        candidates.sort(key=lambda x: x.score, reverse=True)
        return candidates

    def pre_register_patient(
        self,
        state: GoldenCaseState,
        selected_hospital: HospitalCandidate
    ) -> Tuple[str, str, str, str]:
        # Turn 3: Submit FHIR Transaction Bundle
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

    def run(self, state: GoldenCaseState) -> GoldenCaseState:
        acuity = state.triage.acuity_level or ("RED" if state.triage.hard_sos else "YELLOW")
        candidates = self.rank_hospitals(
            incident_lat=state.input_data.location.latitude,
            incident_lon=state.input_data.location.longitude,
            acuity_level=acuity
        )

        if not candidates:
            state.record_error("hospital_agent", "NoHospitalsFound", "No candidate hospitals available in registry")
            return state

        selected = candidates[0]
        state.hospital_fhir.candidate_hospitals = candidates
        state.hospital_fhir.selected_hospital_id = selected.hospital_id
        state.hospital_fhir.selected_hospital_name = selected.name
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
                agent_name="hospital_agent",
                action="fhir_pre_registration_completed",
                details={
                    "selected_hospital": selected.name,
                    "distance_km": selected.distance_km,
                    "score": selected.score,
                    "patient_id": p_id,
                    "encounter_id": enc_id,
                    "condition_id": cond_id
                }
            )
        except Exception as e:
            state.hospital_fhir.fhir_submission_status = "FAILED"
            state.record_error("hospital_agent", "FhirSubmissionError", str(e))

        return state
