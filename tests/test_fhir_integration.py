import pytest
import uuid
from src.fhir.client import FhirClient
from src.fhir.bundle_builder import FhirBundleBuilder

@pytest.fixture(scope="module")
def fhir_client():
    client = FhirClient()
    return client

def test_hapi_fhir_connection(fhir_client):
    assert fhir_client.ping() is True, "HAPI FHIR server is not answering /metadata with CapabilityStatement"

def test_create_and_retrieve_patient(fhir_client):
    unique_name = f"TestSubject-{uuid.uuid4().hex[:6]}"
    patient_payload = {
        "resourceType": "Patient",
        "name": [{
            "use": "official",
            "family": "Kumar",
            "given": [unique_name]
        }],
        "gender": "male",
        "birthDate": "1995-05-15",
        "identifier": [{
            "system": "https://healthid.abdm.gov.in",
            "value": f"91-9999-{uuid.uuid4().hex[:4]}"
        }]
    }

    created = fhir_client.create_resource("Patient", patient_payload)
    assert created.get("resourceType") == "Patient"
    patient_id = created.get("id")
    assert patient_id is not None

    retrieved = fhir_client.get_resource("Patient", patient_id)
    assert retrieved.get("id") == patient_id
    assert retrieved["name"][0]["given"][0] == unique_name

def test_submit_pre_registration_transaction_bundle(fhir_client):
    bundle = FhirBundleBuilder.create_pre_registration_bundle(
        patient_name="Santhosh RTA Victim",
        gender="male",
        birth_date="1998-04-12",
        phone="+919888776655",
        abha_id="91-1122-3344-5566",
        acuity_code="RED",
        incident_description="Severe head trauma from 2-wheeler crash on GST Road",
        location_name="RGGGH Trauma Center"
    )

    response = fhir_client.submit_bundle(bundle)
    assert response.get("resourceType") == "Bundle"
    assert response.get("type") in ["transaction-response", "batch-response"]
    assert len(response.get("entry", [])) == 3

    # All three resources (Patient, Encounter, Condition) must have 201 Created status
    for entry in response["entry"]:
        status = entry.get("response", {}).get("status", "")
        assert "201" in status or "200" in status, f"Bundle entry failed with status: {status}"
