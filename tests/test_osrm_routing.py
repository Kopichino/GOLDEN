"""Unit and Integration Tests for OSRM Road-Network Routing & ETA Engine (Phase B)."""

import pytest
from unittest.mock import patch
from src.agents.hospital import (
    haversine_distance,
    OsrmRouter,
    HospitalDiscovery,
    HospitalMatcher,
    HospitalAgent
)
from src.state.schema import HospitalCandidate


def test_haversine_distance():
    # Tambaram to Chromepet (~5 km)
    d = haversine_distance(12.9249, 80.1000, 12.9516, 80.1410)
    assert 4.0 <= d <= 6.5


def test_osrm_router_fallback_simulation():
    """Verify that when network fails, OsrmRouter provides resilient Chennai urban road estimates."""
    lat1, lon1 = 12.9249, 80.1000  # Tambaram
    lat2, lon2 = 12.9516, 80.1410  # Chromepet GH

    with patch("urllib.request.urlopen", side_effect=Exception("Network unreachable")):
        driving_km, eta_mins, source = OsrmRouter.get_driving_route(lat1, lon1, lat2, lon2)
        straight_km = haversine_distance(lat1, lon1, lat2, lon2)

        assert source == "HAVERSINE_ESTIMATED"
        # Tortuosity factor 1.35x
        assert driving_km >= straight_km
        assert eta_mins > 0.0


def test_osrm_router_live_or_fallback():
    """Verify OsrmRouter returns positive driving distance and realistic ETA."""
    # Guindy to RGGGH Central Chennai (~13 km straight-line)
    lat1, lon1 = 13.0067, 80.2022
    lat2, lon2 = 13.0827, 80.2707

    driving_km, eta_mins, source = OsrmRouter.get_driving_route(lat1, lon1, lat2, lon2, timeout_sec=2.5)

    assert driving_km > 5.0
    assert eta_mins > 5.0
    assert source in ["OSRM", "HAVERSINE_ESTIMATED"]


def test_hospital_candidate_schema_osrm_fields():
    """Verify HospitalCandidate model accepts and validates OSRM fields."""
    cand = HospitalCandidate(
        hospital_id="HOSP-TEST-01",
        name="Apollo Speciality Hospital OMR",
        distance_km=6.2,
        driving_distance_km=8.4,
        eta_minutes=14.5,
        routing_source="OSRM",
        trauma_level="LEVEL_1",
        specialties_available=["neurosurgery", "trauma"],
        available_icu_beds=5,
        available_er_beds=10,
        score=0.0
    )

    assert cand.driving_distance_km == 8.4
    assert cand.eta_minutes == 14.5
    assert cand.routing_source == "OSRM"


def test_hospital_discovery_populates_osrm_fields():
    """Verify Stage 1 discovery attaches driving distance and ETA to each candidate."""
    discovery = HospitalDiscovery()
    candidates = discovery.discover_candidates(incident_lat=12.9249, incident_lon=80.1000)

    assert len(candidates) >= 3
    for c in candidates:
        assert c.distance_km > 0.0
        assert c.driving_distance_km is not None
        assert c.driving_distance_km > 0.0
        assert c.eta_minutes is not None
        assert c.eta_minutes > 0.0
        assert c.routing_source in ["OSRM", "HAVERSINE_ESTIMATED"]


def test_hospital_matcher_scores_with_eta_penalty():
    """Verify Stage 2 multi-factor matching prioritizes lower transit ETA in emergency scoring."""
    matcher = HospitalMatcher()

    # Fast expressway hospital: further straight line (8 km) but fast ETA (10 mins)
    cand_expressway = HospitalCandidate(
        hospital_id="HOSP-EXPRESSWAY",
        name="Expressway Trauma Center",
        distance_km=8.0,
        driving_distance_km=9.0,
        eta_minutes=10.0,
        routing_source="OSRM",
        trauma_level="LEVEL_1",
        available_icu_beds=10,
        available_er_beds=15,
    )

    # Congested urban hospital: closer straight line (4 km) but high traffic ETA (30 mins)
    cand_congested = HospitalCandidate(
        hospital_id="HOSP-CONGESTED",
        name="Congested Urban Clinic",
        distance_km=4.0,
        driving_distance_km=7.5,
        eta_minutes=30.0,
        routing_source="OSRM",
        trauma_level="LEVEL_1",
        available_icu_beds=10,
        available_er_beds=15,
    )

    score_expressway = matcher.score_candidate(cand_expressway, "RED")
    score_congested = matcher.score_candidate(cand_congested, "RED")

    # The expressway hospital with 10m ETA should beat the congested hospital with 30m ETA!
    assert score_expressway > score_congested

    ranked, reason = matcher.match_and_rank([cand_congested, cand_expressway], "RED")
    assert ranked[0].hospital_id == "HOSP-EXPRESSWAY"
    assert "ETA" in reason
    assert "OSRM" in reason
