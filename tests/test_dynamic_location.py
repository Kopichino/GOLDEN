import pytest
from fastapi.testclient import TestClient
from src.dashboard.server import app, active_cases
from src.data.hospitals_catalog import CHENNAI_EMERGENCY_HOSPITALS
from src.agents.hospital import HospitalDiscovery, HospitalMatcher

client = TestClient(app)

def test_hospitals_catalog_size_and_schema():
    """Verify that the expanded hospital catalog contains at least 30 valid facilities."""
    assert len(CHENNAI_EMERGENCY_HOSPITALS) >= 30
    
    required_keys = {"resourceType", "id", "name", "telecom", "address", "extension"}
    for hosp in CHENNAI_EMERGENCY_HOSPITALS:
        assert required_keys.issubset(hosp.keys()), f"Missing keys in {hosp.get('name')}"
        assert hosp["resourceType"] == "Organization"
        
        ext_urls = {ext["url"]: ext for ext in hosp["extension"]}
        assert "http://golden.org/fhir/trauma-level" in ext_urls
        assert "http://golden.org/fhir/icu-beds" in ext_urls
        assert "http://golden.org/fhir/er-beds" in ext_urls
        assert "http://golden.org/fhir/latitude" in ext_urls
        assert "http://golden.org/fhir/longitude" in ext_urls
        
        # Verify valid coordinates within Tamil Nadu / Chennai region
        lat = ext_urls["http://golden.org/fhir/latitude"]["valueDecimal"]
        lon = ext_urls["http://golden.org/fhir/longitude"]["valueDecimal"]
        assert 12.5 <= lat <= 13.5
        assert 79.5 <= lon <= 80.5

def test_dynamic_location_discovery_north_chennai():
    """Verify that an accident in North Chennai (Royapuram/Tondiarpet) discovers Stanley as nearest."""
    discovery = HospitalDiscovery()
    # Royapuram harbor area
    candidates = discovery.discover_candidates(13.1100, 80.2900)
    assert len(candidates) > 0
    
    # Stanley or Tondiarpet should be within 3 km
    nearest = candidates[0]
    assert nearest.distance_km < 4.0
    assert "Stanley" in nearest.name or "Tondiarpet" in nearest.name

def test_dynamic_location_discovery_west_chennai():
    """Verify that an accident in Porur/Ramachandra discovers SRMC or MIOT as nearest."""
    discovery = HospitalDiscovery()
    # Porur junction
    candidates = discovery.discover_candidates(13.0382, 80.1415)
    assert len(candidates) > 0
    
    nearest = candidates[0]
    assert nearest.distance_km < 3.0
    assert "Ramachandra" in nearest.name or "SRMC" in nearest.name or "MIOT" in nearest.name

def test_dynamic_location_discovery_chengalpattu():
    """Verify that an accident in Chengalpattu discovers Chengalpattu GMCH as nearest."""
    discovery = HospitalDiscovery()
    # Chengalpattu Toll plaza
    candidates = discovery.discover_candidates(12.6900, 79.9800)
    assert len(candidates) > 0
    
    nearest = candidates[0]
    assert nearest.distance_km < 5.0
    assert "Chengalpattu" in nearest.name

def test_api_simulate_custom_arbitrary_location():
    """Verify triggering an emergency simulation from arbitrary custom coordinates."""
    payload = {
        "custom_input": "Severe high-speed truck overturn near Koyambedu Market roundtana. Multiple victims with crush injuries.",
        "landmark": "Koyambedu Roundtana, Chennai",
        "latitude": 13.0690,
        "longitude": 80.1948,
        "district": "Chennai",
        "caller_phone": "+91 98840 99887"
    }
    
    resp = client.post("/api/simulate", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "QUEUED"
    case_id = data["case_id"]
    assert case_id in active_cases
    
    case_state = active_cases[case_id]
    assert case_state.input_data.location.latitude == 13.0690
    assert case_state.input_data.location.longitude == 80.1948
    assert "Koyambedu" in case_state.input_data.location.address_or_landmark
