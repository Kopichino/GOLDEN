import os
import sys
import json
import uuid
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.fhir.client import FhirClient
from src.fhir.bundle_builder import FhirBundleBuilder

SAMPLE_SYNTHEA_PATIENTS = [
    {
        "id": "synthea-patient-001",
        "name": "Karthik Subramanian",
        "gender": "male",
        "birthDate": "1994-08-14",
        "phone": "+919840123456",
        "abha_id": "91-4589-2314-7856",
        "blood_group": "O+",
        "allergies": ["Penicillin"],
        "medications": ["Metformin 500mg"],
        "city": "Chennai",
        "district": "Chengalpattu"
    },
    {
        "id": "synthea-patient-002",
        "name": "Ananya Venkatesh",
        "gender": "female",
        "birthDate": "1988-11-22",
        "phone": "+919841234567",
        "abha_id": "91-8890-5621-3412",
        "blood_group": "B+",
        "allergies": ["Sulfa drugs", "Aspirin"],
        "medications": ["Thyroxine 50mcg"],
        "city": "Chennai",
        "district": "Chennai"
    },
    {
        "id": "synthea-patient-003",
        "name": "Mohammed Imran",
        "gender": "male",
        "birthDate": "2001-03-05",
        "phone": "+919842345678",
        "abha_id": "91-1234-9876-4321",
        "blood_group": "AB+",
        "allergies": [],
        "medications": [],
        "city": "Tambaram",
        "district": "Kanchipuram"
    },
    {
        "id": "synthea-patient-004",
        "name": "Priya Rajesh",
        "gender": "female",
        "birthDate": "1975-06-18",
        "phone": "+919843456789",
        "abha_id": "91-7744-1122-9900",
        "blood_group": "A-",
        "allergies": ["Latex"],
        "medications": ["Amlodipine 5mg", "Atorvastatin 10mg"],
        "city": "Guindy",
        "district": "Chennai"
    }
]

from src.data.hospitals_catalog import CHENNAI_EMERGENCY_HOSPITALS

# Scaled Emergency Hospitals Catalog across Chennai & Tamil Nadu Corridors (32 facilities)
EMERGENCY_HOSPITALS = CHENNAI_EMERGENCY_HOSPITALS


def seed_synthea_data(client: FhirClient):
    print("Connecting to HAPI FHIR server at", client.base_url)
    if not client.ping():
        print("ERROR: HAPI FHIR server is not responding to /metadata.")
        return False

    print("\n[1/2] Seeding Emergency Hospitals / Organizations...")
    for hosp in EMERGENCY_HOSPITALS:
        try:
            res = client.create_resource("Organization", hosp)
            print(f"  + Seeded Hospital: {hosp['name']} (ID: {res.get('id')})")
        except Exception as e:
            print(f"  ! Warning seeding {hosp['name']}: {e}")

    print("\n[2/2] Seeding Synthea Synthetic Patient Records...")
    for p in SAMPLE_SYNTHEA_PATIENTS:
        patient_resource = {
            "resourceType": "Patient",
            "id": p["id"],
            "name": [{
                "use": "official",
                "family": p["name"].split()[-1],
                "given": p["name"].split()[:-1]
            }],
            "gender": p["gender"],
            "birthDate": p["birthDate"],
            "telecom": [{"system": "phone", "value": p["phone"], "use": "mobile"}],
            "identifier": [{
                "system": "https://healthid.abdm.gov.in",
                "value": p["abha_id"]
            }],
            "address": [{
                "city": p["city"],
                "district": p["district"],
                "state": "Tamil Nadu",
                "country": "India"
            }]
        }
        try:
            res = client.create_resource("Patient", patient_resource)
            print(f"  + Seeded Patient: {p['name']} | ABHA: {p['abha_id']} (ID: {res.get('id')})")
        except Exception as e:
            print(f"  ! Warning seeding patient {p['name']}: {e}")

    print("\nSeeding complete! Verifying patient search...")
    try:
        search_res = client.search("Patient")
        total = search_res.get("total", len(search_res.get("entry", [])))
        print(f"  Total Patients currently in HAPI FHIR store: {total}")
        return True
    except Exception as e:
        print(f"  Search error: {e}")
        return False

if __name__ == "__main__":
    client = FhirClient()
    success = seed_synthea_data(client)
    if success:
        print("\nHAPI FHIR server seeded successfully with Synthea patients & hospitals!")
    else:
        sys.exit(1)
