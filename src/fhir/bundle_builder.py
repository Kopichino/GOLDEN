import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

class FhirBundleBuilder:
    """Constructs standards-compliant HL7 FHIR R4 Bundles for Emergency Pre-Registration."""

    @staticmethod
    def create_pre_registration_bundle(
        patient_name: str,
        gender: str = "unknown",
        birth_date: Optional[str] = None,
        phone: Optional[str] = None,
        abha_id: Optional[str] = None,
        acuity_code: str = "RED",
        incident_description: str = "Road traffic accident trauma",
        location_name: str = "Chennai Trauma Center",
    ) -> Dict[str, Any]:
        """
        Creates a FHIR R4 Transaction Bundle with:
        1. Patient (Synthetic / Pre-hospital record)
        2. Encounter (Emergency / EMER class)
        3. Condition (Triage provisional finding)
        """
        patient_uuid = f"urn:uuid:{uuid.uuid4()}"
        encounter_uuid = f"urn:uuid:{uuid.uuid4()}"
        condition_uuid = f"urn:uuid:{uuid.uuid4()}"
        timestamp_str = datetime.now(timezone.utc).isoformat()

        # 1. Patient Resource
        patient_resource: Dict[str, Any] = {
            "resourceType": "Patient",
            "active": True,
            "name": [{
                "use": "official",
                "text": patient_name,
                "family": patient_name.split()[-1] if " " in patient_name else patient_name,
                "given": patient_name.split()[:-1] if " " in patient_name else [patient_name]
            }],
            "gender": gender if gender in ["male", "female", "other", "unknown"] else "unknown",
        }
        if birth_date:
            patient_resource["birthDate"] = birth_date
        if phone:
            patient_resource["telecom"] = [{
                "system": "phone",
                "value": phone,
                "use": "mobile"
            }]
        if abha_id:
            patient_resource["identifier"] = [{
                "system": "https://healthid.abdm.gov.in",
                "value": abha_id,
                "type": {
                    "coding": [{
                        "system": "http://terminology.hl7.org/CodeSystem/v2-0203",
                        "code": "MR",
                        "display": "Medical record number"
                    }]
                }
            }]

        # 2. Encounter Resource
        encounter_resource: Dict[str, Any] = {
            "resourceType": "Encounter",
            "status": "in-progress",
            "class": {
                "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
                "code": "EMER",
                "display": "emergency"
            },
            "priority": {
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/v3-ActPriority",
                    "code": "CR" if acuity_code == "RED" else "UR",
                    "display": "Callback results" if acuity_code == "RED" else "urgent"
                }],
                "text": f"Acuity {acuity_code}"
            },
            "subject": {
                "reference": patient_uuid,
                "display": patient_name
            },
            "period": {
                "start": timestamp_str
            },
            "reasonCode": [{
                "coding": [{
                    "system": "http://snomed.info/sct",
                    "code": "417746004",
                    "display": "Traumatic injury"
                }],
                "text": incident_description
            }]
        }

        # 3. Condition Resource
        condition_resource: Dict[str, Any] = {
            "resourceType": "Condition",
            "clinicalStatus": {
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                    "code": "active",
                    "display": "Active"
                }]
            },
            "verificationStatus": {
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/condition-ver-status",
                    "code": "provisional",
                    "display": "Provisional"
                }]
            },
            "category": [{
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/condition-category",
                    "code": "encounter-diagnosis",
                    "display": "Encounter Diagnosis"
                }]
            }],
            "severity": {
                "coding": [{
                    "system": "http://snomed.info/sct",
                    "code": "24484000" if acuity_code == "RED" else "6736007",
                    "display": "Severe" if acuity_code == "RED" else "Moderate"
                }]
            },
            "code": {
                "coding": [{
                    "system": "http://snomed.info/sct",
                    "code": "417746004",
                    "display": "Traumatic injury due to road traffic collision"
                }],
                "text": incident_description
            },
            "subject": {
                "reference": patient_uuid
            },
            "encounter": {
                "reference": encounter_uuid
            },
            "recordedDate": timestamp_str
        }

        # Build FHIR Transaction Bundle
        bundle: Dict[str, Any] = {
            "resourceType": "Bundle",
            "type": "transaction",
            "entry": [
                {
                    "fullUrl": patient_uuid,
                    "resource": patient_resource,
                    "request": {
                        "method": "POST",
                        "url": "Patient"
                    }
                },
                {
                    "fullUrl": encounter_uuid,
                    "resource": encounter_resource,
                    "request": {
                        "method": "POST",
                        "url": "Encounter"
                    }
                },
                {
                    "fullUrl": condition_uuid,
                    "resource": condition_resource,
                    "request": {
                        "method": "POST",
                        "url": "Condition"
                    }
                }
            ]
        }

        return bundle

    @staticmethod
    def create_family_history_bundle(
        patient_id: str,
        encounter_id: Optional[str] = None,
        allergies: Optional[List[str]] = None,
        medications: Optional[List[str]] = None,
        blood_group: Optional[str] = None,
        conditions: Optional[List[str]] = None,
        summary: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Creates a FHIR R4 Transaction Bundle with the family-reported history
        collected by the voice agent:
        1. AllergyIntolerance (one per reported allergy)
        2. MedicationStatement (one per reported current medication)
        3. Observation (ABO/Rh blood group, LOINC 882-1)
        4. Condition (one per reported pre-existing condition, family-reported)
        """
        patient_ref = f"Patient/{patient_id}"
        timestamp_str = datetime.now(timezone.utc).isoformat()
        entries: List[Dict[str, Any]] = []

        def add_entry(resource: Dict[str, Any]) -> None:
            entries.append({
                "fullUrl": f"urn:uuid:{uuid.uuid4()}",
                "resource": resource,
                "request": {
                    "method": "POST",
                    "url": resource["resourceType"]
                }
            })

        for allergy in (allergies or []):
            add_entry({
                "resourceType": "AllergyIntolerance",
                "clinicalStatus": {
                    "coding": [{
                        "system": "http://terminology.hl7.org/CodeSystem/allergyintolerance-clinical",
                        "code": "active",
                        "display": "Active"
                    }]
                },
                "code": {"text": str(allergy)},
                "patient": {"reference": patient_ref},
                "recordedDate": timestamp_str,
                "note": [{"text": "Family-reported via GOLDEN voice agent"}]
            })

        for medication in (medications or []):
            add_entry({
                "resourceType": "MedicationStatement",
                "status": "active",
                "medicationCodeableConcept": {"text": str(medication)},
                "subject": {"reference": patient_ref},
                "effectiveDateTime": timestamp_str,
                "informationSource": {"display": "Family report (GOLDEN voice agent)"},
                "note": [{"text": "Family-reported via GOLDEN voice agent"}]
            })

        if blood_group:
            add_entry({
                "resourceType": "Observation",
                "status": "final",
                "category": [{
                    "coding": [{
                        "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                        "code": "laboratory",
                        "display": "Laboratory"
                    }]
                }],
                "code": {
                    "coding": [{
                        "system": "http://loinc.org",
                        "code": "882-1",
                        "display": "ABO and Rh group [Type] in Blood"
                    }],
                    "text": "Blood group"
                },
                "subject": {"reference": patient_ref},
                "effectiveDateTime": timestamp_str,
                "valueString": str(blood_group),
                "note": [{"text": "Family-reported via GOLDEN voice agent"}]
            })

        for condition in (conditions or []):
            condition_resource: Dict[str, Any] = {
                "resourceType": "Condition",
                "clinicalStatus": {
                    "coding": [{
                        "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                        "code": "active",
                        "display": "Active"
                    }]
                },
                "verificationStatus": {
                    "coding": [{
                        "system": "http://terminology.hl7.org/CodeSystem/condition-ver-status",
                        "code": "unconfirmed",
                        "display": "Unconfirmed"
                    }]
                },
                "category": [{
                    "coding": [{
                        "system": "http://terminology.hl7.org/CodeSystem/condition-category",
                        "code": "problem-list-item",
                        "display": "Problem List Item"
                    }]
                }],
                "code": {"text": str(condition)},
                "subject": {"reference": patient_ref},
                "recordedDate": timestamp_str,
                "note": [{"text": "Family-reported pre-existing condition via GOLDEN voice agent"}]
            }
            if encounter_id:
                condition_resource["encounter"] = {"reference": f"Encounter/{encounter_id}"}
            add_entry(condition_resource)

        if summary:
            add_entry({
                "resourceType": "Observation",
                "status": "final",
                "category": [{
                    "coding": [{
                        "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                        "code": "social-history",
                        "display": "Social History"
                    }]
                }],
                "code": {
                    "coding": [{
                        "system": "http://snomed.info/sct",
                        "code": "417319006",
                        "display": "History of clinical finding in subject"
                    }],
                    "text": "Family-reported clinical summary"
                },
                "subject": {"reference": patient_ref},
                "effectiveDateTime": timestamp_str,
                "valueString": str(summary),
            })

        return {
            "resourceType": "Bundle",
            "type": "transaction",
            "entry": entries
        }
