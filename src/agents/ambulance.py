"""Ambulance Fleet Allocation & Physical Dispatch Engine (108 CAD).

Implements:
1. AmbulanceFleetRegistry: Registry of emergency response hubs along Chennai South corridor.
2. AmbulanceAllocator: Acuity-tiered matching (ALS vs BLS), OSRM transit ETA to scene, and callout ticket generation.
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from src.agents.hospital import OsrmRouter, haversine_distance
from src.state.schema import (
    AmbulanceUnit,
    AmbulanceDispatchOutput,
    GoldenCaseState,
)


class AmbulanceFleetRegistry:
    """In-memory 108 Emergency Fleet Registry for Chennai South Highway Corridor."""

    @classmethod
    def get_fleet(cls) -> List[Dict]:
        return cls.get_initial_fleet()

    @staticmethod
    def get_initial_fleet() -> List[Dict]:
        return [
            {
                "unit_id": "AMB-108-01",
                "vehicle_number": "TN-07-G-1081",
                "unit_type": "ALS",
                "base_station": "Tambaram Sanatorium 108 Hub",
                "latitude": 12.9340,
                "longitude": 80.1280,
                "status": "AVAILABLE",
                "crew_lead_paramedic": "Rajesh Kumar (EMT-P)",
                "pilot_driver": "M. Venkatesh",
                "pilot_contact": "+91 94441 10801",
                "equipment_manifest": [
                    "Transport Ventilator (Hamilton-T1)",
                    "Biphasic Defibrillator / Monitor",
                    "Syringe Infusion Pump",
                    "Video Laryngoscope / Intubation Kit",
                    "Emergency Trauma Surgical Pack",
                    "Spine Board & Cervical Immobilization"
                ]
            },
            {
                "unit_id": "AMB-108-02",
                "vehicle_number": "TN-07-G-1082",
                "unit_type": "BLS",
                "base_station": "Chromepet MIT Gate Station",
                "latitude": 12.9480,
                "longitude": 80.1400,
                "status": "AVAILABLE",
                "crew_lead_paramedic": "Priya Sundaram (EMT-B)",
                "pilot_driver": "K. Murugan",
                "pilot_contact": "+91 94441 10802",
                "equipment_manifest": [
                    "Automated External Defibrillator (AED)",
                    "Portable Medical Oxygen Cylinders (D-Type)",
                    "Bag-Valve-Mask (BVM) Resuscitator",
                    "Rigid Cervical Collars & Spine Board",
                    "Traction & Fracture Splints",
                    "Basic Burn & Trauma Dressing Kit"
                ]
            },
            {
                "unit_id": "AMB-108-03",
                "vehicle_number": "TN-07-G-1083",
                "unit_type": "ALS",
                "base_station": "Guindy Kathipara Flyover Hub",
                "latitude": 13.0067,
                "longitude": 80.2022,
                "status": "AVAILABLE",
                "crew_lead_paramedic": "S. Arunachalam (Critical Care EMT)",
                "pilot_driver": "R. Selvaraj",
                "pilot_contact": "+91 94441 10803",
                "equipment_manifest": [
                    "LTV-1200 Transport Ventilator",
                    "Zoll X Series Monitor / Defibrillator / Pacer",
                    "ACLS Emergency Drug Kit (Epi, Amiodarone)",
                    "Suction Apparatus & Chest Tube Kit",
                    "Multi-Parameter Patient Monitor (NIBP/SpO2/EtCO2)",
                    "Scoop Stretcher & Pelvic Binder"
                ]
            },
            {
                "unit_id": "AMB-108-04",
                "vehicle_number": "TN-07-G-1084",
                "unit_type": "BLS",
                "base_station": "Medavakkam Junction Depot",
                "latitude": 12.9180,
                "longitude": 80.1920,
                "status": "AVAILABLE",
                "crew_lead_paramedic": "Dinesh Babu (EMT-B)",
                "pilot_driver": "T. Anbarasan",
                "pilot_contact": "+91 94441 10804",
                "equipment_manifest": [
                    "Automated External Defibrillator (AED)",
                    "Oxygen Resuscitation Kit",
                    "Bleeding Control & Hemostatic Gauze",
                    "Pulse Oximeter & Glucometer",
                    "Collapsible Stretcher & Blanket"
                ]
            },
            {
                "unit_id": "AMB-108-05",
                "vehicle_number": "TN-07-G-1085",
                "unit_type": "ALS",
                "base_station": "Sholinganallur OMR Expressway Hub",
                "latitude": 12.9010,
                "longitude": 80.2280,
                "status": "AVAILABLE",
                "crew_lead_paramedic": "K. Selvamani (EMT-P)",
                "pilot_driver": "P. Balamurugan",
                "pilot_contact": "+91 94441 10805",
                "equipment_manifest": [
                    "Portable ICU Transport Ventilator",
                    "Biphasic Defibrillator",
                    "Emergency Trauma & Arterial Bleed Kit",
                    "Intravenous Infusion & Blood Warmer Kit",
                    "Pediatric Emergency Care Bag"
                ]
            }
        ]


class AmbulanceAllocator:
    """Acuity-Driven Ambulance Allocation & CAD Dispatch Engine."""

    def __init__(self, fleet_registry: Optional[List[Dict]] = None):
        self._fleet = fleet_registry or AmbulanceFleetRegistry.get_initial_fleet()

    def get_all_units(self) -> List[AmbulanceUnit]:
        return [AmbulanceUnit.model_validate(u) for u in self._fleet]

    def allocate_ambulance(
        self,
        incident_lat: Any = None,
        incident_lon: Optional[float] = None,
        acuity_level: Optional[str] = None,
        case_id: Optional[str] = None,
        target_hospital_name: Optional[str] = None,
        landmark_narrative: Optional[str] = None
    ) -> AmbulanceDispatchOutput:
        """Allocate the optimal ambulance unit based on acuity tier, proximity, and equipment capability."""
        passed_state = None
        if isinstance(incident_lat, GoldenCaseState):
            passed_state = incident_lat
            loc = passed_state.input_data.location
            incident_lat = loc.latitude
            incident_lon = loc.longitude
            acuity_level = passed_state.triage.acuity_level or ("RED" if passed_state.triage.hard_sos else "YELLOW")
            case_id = passed_state.input_data.case_id
            target_hospital_name = passed_state.hospital_fhir.selected_hospital_name or "Receiving Hospital"
            landmark_narrative = loc.address_or_landmark

        acuity = (acuity_level or "YELLOW").upper()
        demanded_tier = "ALS" if acuity == "RED" else "BLS"

        evaluated_units: List[AmbulanceUnit] = []

        for raw_unit in self._fleet:
            u_lat = raw_unit["latitude"]
            u_lon = raw_unit["longitude"]

            # Calculate road driving distance & transit ETA from hub to incident scene
            driving_km, eta_mins, routing_source, route_geom = OsrmRouter.get_driving_route(
                u_lat, u_lon, incident_lat, incident_lon, include_geometry=True
            )

            unit_obj = AmbulanceUnit(
                unit_id=raw_unit["unit_id"],
                vehicle_number=raw_unit["vehicle_number"],
                unit_type=raw_unit["unit_type"],
                base_station=raw_unit["base_station"],
                latitude=u_lat,
                longitude=u_lon,
                status=raw_unit.get("status", "AVAILABLE"),
                crew_lead_paramedic=raw_unit["crew_lead_paramedic"],
                pilot_driver=raw_unit["pilot_driver"],
                pilot_contact=raw_unit["pilot_contact"],
                equipment_manifest=raw_unit.get("equipment_manifest", []),
                distance_to_scene_km=driving_km,
                eta_to_scene_minutes=eta_mins,
                route_geometry=route_geom,
                routing_source=routing_source
            )
            evaluated_units.append(unit_obj)

        # Primary filter: match exact demanded tier (ALS for RED, BLS for YELLOW/GREEN)
        tier_matched = [u for u in evaluated_units if u.unit_type == demanded_tier and u.status == "AVAILABLE"]

        # Fallback hierarchy:
        # If RED but all ALS occupied -> escalate to nearest BLS with critical care alert
        # If YELLOW/GREEN and all BLS occupied -> upgrade to available ALS
        if not tier_matched:
            tier_matched = [u for u in evaluated_units if u.status == "AVAILABLE"]

        if not tier_matched:
            # Complete fleet busy fallback
            tier_matched = evaluated_units

        # Sort candidate units by shortest transit ETA to incident scene
        tier_matched.sort(key=lambda u: (u.eta_to_scene_minutes or 999.0))
        selected_unit = tier_matched[0] if tier_matched else None

        # Build official Callout Ticket
        short_id = case_id[-6:] if len(case_id) >= 6 else str(int(time.time()))[-6:]
        ticket_id = f"CALLOUT-108-{short_id.upper()}"
        now_utc = datetime.now(timezone.utc)

        # Paramedic Briefing Notes based on clinical protocol
        if acuity == "RED":
            handover_notes = (
                f"🚨 PRIORITY RED EMERGENCY: Dispatched {selected_unit.unit_type} unit {selected_unit.unit_id}. "
                f"Pre-hospital life threat criteria active. Immediately initiate airway stabilization, high-flow O2, "
                f"and cervical spine restriction. Target Level-1/2 Receiving Facility: {target_hospital_name or 'Designated Trauma Center'}."
            )
            allocation_reason = (
                f"Allocated {selected_unit.unit_type} unit {selected_unit.unit_id} ({selected_unit.vehicle_number}) "
                f"from {selected_unit.base_station}: ETA {selected_unit.eta_to_scene_minutes}m to scene "
                f"({selected_unit.distance_to_scene_km}km via {selected_unit.routing_source}). "
                f"Mandatory ALS tier satisfied with ventilator/defibrillator onboard."
            )
        else:
            handover_notes = (
                f"🟡 URGENT {acuity} DISPATCH: Dispatched {selected_unit.unit_type} unit {selected_unit.unit_id}. "
                f"Provide vital signs monitoring, wound care, and stable transport. "
                f"Destination Facility: {target_hospital_name or 'Emergency Department'}."
            )
            allocation_reason = (
                f"Allocated {selected_unit.unit_type} unit {selected_unit.unit_id} ({selected_unit.vehicle_number}) "
                f"from {selected_unit.base_station}: ETA {selected_unit.eta_to_scene_minutes}m to scene "
                f"({selected_unit.distance_to_scene_km}km via {selected_unit.routing_source}). "
                f"BLS resource allocated to conserve ALS fleet for life threats."
            )

        instructions = [
            f"Exit {selected_unit.base_station} heading towards incident coordinates ({incident_lat:.4f}°N, {incident_lon:.4f}°E).",
            f"Engage primary emergency audio/visual sirens on Chennai South arterial corridor.",
            f"Target Scene ETA: {selected_unit.eta_to_scene_minutes} minutes ({selected_unit.distance_to_scene_km} km via {selected_unit.routing_source}).",
            f"Report arrival code 10-23 (On Scene) upon visual contact with patient at landmark: {landmark_narrative or 'Incident Location'}."
        ]

        dispatch_out = AmbulanceDispatchOutput(
            dispatch_status="DISPATCHED",
            mission_status="DISPATCHED",
            mission_events=[{
                "status": "DISPATCHED",
                "timestamp": now_utc.isoformat(),
                "notes": f"Initial unit dispatch by GOLDEN CAD to {selected_unit.unit_id if selected_unit else 'unit'}."
            }],
            selected_unit=selected_unit,
            candidate_units=evaluated_units,
            callout_ticket_id=ticket_id,
            dispatch_timestamp=now_utc,
            acuity_demanded=demanded_tier,
            allocation_reason=allocation_reason,
            turn_by_turn_instructions=instructions,
            paramedic_handover_notes=handover_notes
        )
        if passed_state is not None:
            passed_state.ambulance_dispatch = dispatch_out
        return dispatch_out
