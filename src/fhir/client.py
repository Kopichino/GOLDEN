import requests
from typing import Dict, Any, Optional, List
from src.config import settings

class FhirClient:
    """REST Client for interacting with HAPI FHIR R4 server."""

    def __init__(self, base_url: Optional[str] = None, timeout: Optional[int] = None):
        self.base_url = (base_url or settings.FHIR_BASE_URL).rstrip("/")
        self.timeout = timeout or settings.FHIR_TIMEOUT_SECONDS
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/fhir+json",
            "Accept": "application/fhir+json"
        })

    def ping(self) -> bool:
        """Verify HAPI FHIR server is reachable and reports FHIR R4 capability statement."""
        try:
            resp = self.session.get(f"{self.base_url}/metadata", timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("resourceType") == "CapabilityStatement"
            return False
        except Exception:
            return False

    def create_resource(self, resource_type: str, resource_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a single FHIR resource (e.g. Patient, Encounter, Condition)."""
        url = f"{self.base_url}/{resource_type}"
        resp = self.session.post(url, json=resource_data, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def submit_bundle(self, bundle: Dict[str, Any]) -> Dict[str, Any]:
        """Submit a FHIR transaction or batch bundle."""
        url = self.base_url
        resp = self.session.post(url, json=bundle, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def search(self, resource_type: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute a FHIR search query."""
        url = f"{self.base_url}/{resource_type}"
        resp = self.session.get(url, params=params or {}, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def get_resource(self, resource_type: str, resource_id: str) -> Dict[str, Any]:
        """Fetch a specific resource by ID."""
        url = f"{self.base_url}/{resource_type}/{resource_id}"
        resp = self.session.get(url, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()
