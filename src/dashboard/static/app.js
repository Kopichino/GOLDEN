/**
 * GOLDEN Emergency Dispatcher Console — Client-Side Application
 * Handles real-time SSE updates, incident queue rendering, interactive inspection,
 * simulation triggers, dispatcher overrides, and live HAPI FHIR JSON viewer.
 */

// Global State
let activeCases = [];
let selectedCaseId = null;
let selectedPresetKey = "tambaram_femur_crash";
let eventSource = null;

// DOM Elements
const incidentListContainer = document.getElementById("incident-list-container");
const emptyQueueMessage = document.getElementById("empty-queue-message");
const activeCasesCount = document.getElementById("active-cases-count");
const fhirStatusText = document.getElementById("fhir-status-text");
const fhirDot = document.getElementById("fhir-dot");

// Inspector Elements
const heroCaseId = document.getElementById("hero-case-id");
const heroAcuityBadge = document.getElementById("hero-acuity-badge");
const heroHardSosBadge = document.getElementById("hero-hard-sos-badge");
const heroLandmark = document.getElementById("hero-landmark");
const heroReportedTime = document.getElementById("hero-reported-time");
const btnOpenOverrideModal = document.getElementById("btn-open-override-modal");

// Card 1: Narrative
const callerNarrativeText = document.getElementById("caller-narrative-text");
const callerContactValue = document.getElementById("caller-contact-value");
const callerGpsValue = document.getElementById("caller-gps-value");
const safetyTag = document.getElementById("safety-tag");

// Card 2: Triage
const triageConfidenceBadge = document.getElementById("triage-confidence-badge");
const triageGuidelineText = document.getElementById("triage-guideline-text");
const triageRationaleText = document.getElementById("triage-rationale-text");

// Card 3: Hospital
const hospitalBedBadge = document.getElementById("hospital-bed-badge");
const selectedHospitalName = document.getElementById("selected-hospital-name");
const hospDistanceVal = document.getElementById("hosp-distance-val");
const hospTraumaVal = document.getElementById("hosp-trauma-val");
const hospBedsVal = document.getElementById("hosp-beds-val");
const candidatesTableBody = document.getElementById("candidates-table-body");

// Card 4: FHIR & Voice
const fhirBadgeStatus = document.getElementById("fhir-badge-status");
const btnInspectPatient = document.getElementById("btn-inspect-patient");
const btnInspectEncounter = document.getElementById("btn-inspect-encounter");
const btnInspectCondition = document.getElementById("btn-inspect-condition");
const voiceCallStatus = document.getElementById("voice-call-status");
const medicalTagsContainer = document.getElementById("medical-tags-container");
const btnSimulateWebhook = document.getElementById("btn-simulate-webhook");

// Modals
const modalSimulate = document.getElementById("modal-simulate");
const btnOpenSimulateModal = document.getElementById("btn-open-simulate-modal");
const btnCloseSimulateModal = document.getElementById("btn-close-simulate-modal");
const btnCancelSimulate = document.getElementById("btn-cancel-simulate");
const btnSubmitSimulation = document.getElementById("btn-submit-simulation");

const modalOverride = document.getElementById("modal-override");
const btnCloseOverrideModal = document.getElementById("btn-close-override-modal");
const btnCancelOverride = document.getElementById("btn-cancel-override");
const btnSubmitOverride = document.getElementById("btn-submit-override");
const selectOverrideAcuity = document.getElementById("select-override-acuity");
const selectOverrideHospital = document.getElementById("select-override-hospital");
const inputOverrideNotes = document.getElementById("input-override-notes");

const modalFhirInspector = document.getElementById("modal-fhir-inspector");
const btnCloseFhirModal = document.getElementById("btn-close-fhir-modal");
const btnCloseFhirViewer = document.getElementById("btn-close-fhir-viewer");
const fhirModalTitle = document.getElementById("fhir-modal-title");
const fhirModalUrl = document.getElementById("fhir-modal-url");
const fhirModalJson = document.getElementById("fhir-modal-json");

// Card 5: Ambulance Fleet Dispatch
const ambulanceTierBadge = document.getElementById("ambulance-tier-badge");
const ambulanceCallsign = document.getElementById("ambulance-callsign");
const ambulanceVehicleNo = document.getElementById("ambulance-vehicle-no");
const ambulanceAcuityTag = document.getElementById("ambulance-acuity-tag");
const ambulanceBaseStation = document.getElementById("ambulance-base-station");
const ambulanceEtaToScene = document.getElementById("ambulance-eta-to-scene");
const ambulanceDistToScene = document.getElementById("ambulance-dist-to-scene");
const ambulanceParamedicName = document.getElementById("ambulance-paramedic-name");
const ambulancePilotName = document.getElementById("ambulance-pilot-name");
const ambulancePilotPhone = document.getElementById("ambulance-pilot-phone");
const ambulanceEquipmentPills = document.getElementById("ambulance-equipment-pills");
const ambulanceParamedicNotes = document.getElementById("ambulance-paramedic-notes");
const btnViewCalloutTicket = document.getElementById("btn-view-callout-ticket");
const ambulanceTicketRef = document.getElementById("ambulance-ticket-ref");

// Modal: 108 Callout Ticket
const modalCalloutTicket = document.getElementById("modal-callout-ticket");
const btnCloseCalloutModal = document.getElementById("btn-close-callout-modal");
const btnCloseCalloutTicket = document.getElementById("btn-close-callout-ticket");
const btnPrintCalloutTicket = document.getElementById("btn-print-callout-ticket");
const ticketModalId = document.getElementById("ticket-modal-id");
const ticketModalTime = document.getElementById("ticket-modal-time");
const ticketCaseId = document.getElementById("ticket-case-id");
const ticketAcuity = document.getElementById("ticket-acuity");
const ticketLocation = document.getElementById("ticket-location");
const ticketGps = document.getElementById("ticket-gps");
const ticketCallerPhone = document.getElementById("ticket-caller-phone");
const ticketUnitCallsign = document.getElementById("ticket-unit-callsign");
const ticketVehNo = document.getElementById("ticket-veh-no");
const ticketTier = document.getElementById("ticket-tier");
const ticketDepot = document.getElementById("ticket-depot");
const ticketEta = document.getElementById("ticket-eta");
const ticketDestHospital = document.getElementById("ticket-dest-hospital");
const ticketParamedic = document.getElementById("ticket-paramedic");
const ticketPilot = document.getElementById("ticket-pilot");
const ticketPilotPhone = document.getElementById("ticket-pilot-phone");
const ticketEquipManifest = document.getElementById("ticket-equip-manifest");
const ticketDrivingDirections = document.getElementById("ticket-driving-directions");
const ticketHandoverBrief = document.getElementById("ticket-handover-brief");

// Pipeline Steps
const stepMap = {
  "INGESTION": "step-ingest",
  "INGESTED": "step-ingest",
  "HARD_SOS_CHECK": "step-sos",
  "PARALLEL_TRIAGE_DISCOVERY": "step-fanout",
  "PARALLEL_TRIAGE_HOSPITAL": "step-fanout",
  "HOSPITAL_MATCHING": "step-merge",
  "COORDINATOR_MERGE": "step-merge",
  "AMBULANCE_ALLOCATION": "step-ambulance",
  "FHIR_REGISTRATION": "step-voice",
  "VOICE_DISPATCH": "step-voice",
  "AWAITING_WEBHOOK": "step-voice",
  "DISPATCHER_REVIEW": "step-complete",
  "CONSOLIDATION": "step-complete",
  "COMPLETED": "step-complete"
};

// Tactical Corridor Map state
let corridorMap = null;
let incidentMarker = null;
let incidentPerimeter = null;
let hospitalMarkers = [];
let ambulanceMarker = null;
let ambulanceRouteLine = null;
let routePolyline = null;
let lastIncidentLatLng = null;
let lastBoundsPoints = [];

// =====================================================================
// Initialization
// =====================================================================
document.addEventListener("DOMContentLoaded", () => {
  setupEventListeners();
  setupAnalyticsTab();
  initCorridorMap();
  checkHealth();
  fetchCases();
  fetchAnalytics();
  initSSE();
});

function setupEventListeners() {
  // Simulate Modal
  btnOpenSimulateModal.addEventListener("click", () => {
    modalSimulate.classList.remove("hidden");
    setTimeout(() => initOrRefreshPickerMap(), 80);
  });
  btnCloseSimulateModal.addEventListener("click", () => modalSimulate.classList.add("hidden"));
  btnCancelSimulate.addEventListener("click", () => modalSimulate.classList.add("hidden"));

  // Preset Selection in Modal
  const PRESET_COORDS = {
    "tambaram_femur_crash": { lat: 12.9249, lon: 80.1472, landmark: "Tambaram Flyover, GST Road, Chennai", district: "Chennai" },
    "guindy_cardiac_arrest": { lat: 13.0067, lon: 80.2026, landmark: "Guindy Industrial Estate, Chennai", district: "Chennai" },
    "omr_concussion": { lat: 12.9385, lon: 80.2327, landmark: "OMR Thoraipakkam Signal, Chennai", district: "Chennai" }
  };

  document.querySelectorAll(".preset-btn").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      document.querySelectorAll(".preset-btn").forEach((b) => b.classList.remove("selected"));
      btn.classList.add("selected");
      selectedPresetKey = btn.dataset.preset;
      isCustomLocationSelected = false;

      const pInfo = PRESET_COORDS[selectedPresetKey];
      if (pInfo) {
        const latInput = document.getElementById("input-custom-lat");
        const lonInput = document.getElementById("input-custom-lon");
        const landmarkInput = document.getElementById("input-custom-landmark");
        const statusPill = document.getElementById("picker-status-pill");

        if (latInput) latInput.value = pInfo.lat;
        if (lonInput) lonInput.value = pInfo.lon;
        if (landmarkInput) landmarkInput.value = pInfo.landmark;
        if (statusPill) {
          statusPill.textContent = `📍 Loaded Preset: ${pInfo.landmark}`;
          statusPill.className = "picker-hint-badge";
        }
        if (pickerMap && pickerMarker) {
          pickerMarker.setLatLng([pInfo.lat, pInfo.lon]);
          pickerMap.setView([pInfo.lat, pInfo.lon], 13);
        }
      }
      // Clear custom fields
      document.getElementById("input-custom-narrative").value = "";
    });
  });

  // Locate Search in Modal
  const btnMapSearch = document.getElementById("btn-map-search");
  if (btnMapSearch) {
    btnMapSearch.addEventListener("click", handlePlaceSearch);
  }
  const inputMapSearch = document.getElementById("input-map-search");
  if (inputMapSearch) {
    inputMapSearch.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        handlePlaceSearch();
      }
    });
  }

  // Manual Lat/Lon input listeners
  const latInput = document.getElementById("input-custom-lat");
  const lonInput = document.getElementById("input-custom-lon");
  const onManualCoordChange = () => {
    const lat = parseFloat(latInput?.value);
    const lon = parseFloat(lonInput?.value);
    if (!isNaN(lat) && !isNaN(lon)) {
      if (pickerMap && pickerMarker) {
        pickerMarker.setLatLng([lat, lon]);
        pickerMap.setView([lat, lon], 13);
      }
      updateLocationFromPicker(lat, lon, true);
    }
  };
  if (latInput) latInput.addEventListener("change", onManualCoordChange);
  if (lonInput) lonInput.addEventListener("change", onManualCoordChange);

  btnSubmitSimulation.addEventListener("click", handleDispatchSimulation);


  // Override Modal
  btnOpenOverrideModal.addEventListener("click", populateAndOpenOverrideModal);
  btnCloseOverrideModal.addEventListener("click", () => modalOverride.classList.add("hidden"));
  btnCancelOverride.addEventListener("click", () => modalOverride.classList.add("hidden"));
  btnSubmitOverride.addEventListener("click", handleSubmitOverride);

  // FHIR Inspector Modal
  btnCloseFhirModal.addEventListener("click", () => modalFhirInspector.classList.add("hidden"));
  btnCloseFhirViewer.addEventListener("click", () => modalFhirInspector.classList.add("hidden"));

  btnInspectPatient.addEventListener("click", () => openFhirInspector("Patient", btnInspectPatient.dataset.resId));
  btnInspectEncounter.addEventListener("click", () => openFhirInspector("Encounter", btnInspectEncounter.dataset.resId));
  btnInspectCondition.addEventListener("click", () => openFhirInspector("Condition", btnInspectCondition.dataset.resId));

  // Webhook Injection
  btnSimulateWebhook.addEventListener("click", handleSimulateWebhook);

  // Ambulance CAD Callout Ticket Modal
  if (btnViewCalloutTicket) {
    btnViewCalloutTicket.addEventListener("click", () => openCalloutTicketModal(selectedCaseId));
  }
  if (btnCloseCalloutModal) {
    btnCloseCalloutModal.addEventListener("click", () => modalCalloutTicket.classList.add("hidden"));
  }
  if (btnCloseCalloutTicket) {
    btnCloseCalloutTicket.addEventListener("click", () => modalCalloutTicket.classList.add("hidden"));
  }
  if (btnPrintCalloutTicket) {
    btnPrintCalloutTicket.addEventListener("click", () => window.print());
  }

  // Filter Pills
  document.querySelectorAll(".pill").forEach((pill) => {
    pill.addEventListener("click", () => {
      document.querySelectorAll(".pill").forEach((p) => p.classList.remove("active"));
      pill.classList.add("active");
      renderIncidentList(pill.dataset.filter);
    });
  });
}

// =====================================================================
// Real-Time Server-Sent Events (SSE)
// =====================================================================
function initSSE() {
  if (eventSource) {
    eventSource.close();
  }

  eventSource = new EventSource("/api/events");

  eventSource.onmessage = (e) => {
    try {
      const event = JSON.parse(e.data);
      handleLiveEvent(event);
    } catch (err) {
      console.warn("Error parsing SSE event:", err);
    }
  };

  eventSource.onerror = () => {
    console.warn("SSE connection lost. Reconnecting in 3s...");
    eventSource.close();
    setTimeout(initSSE, 3000);
  };
}

function handleLiveEvent(event) {
  // Fetch latest cases to keep list fresh
  fetchCases(false);

  // If the event corresponds to currently inspected case, reload details
  if (selectedCaseId && event.case_id === selectedCaseId) {
    fetchCaseDetails(selectedCaseId, false);
  }
}

// =====================================================================
// Data Fetching
// =====================================================================
async function checkHealth() {
  try {
    const res = await fetch("/api/health");
    if (!res.ok) throw new Error("Health check failed");
    const data = await res.json();
    if (data.fhir_connected) {
      fhirStatusText.textContent = "Online (Port 8080)";
      fhirDot.className = "dot-indicator dot-connected";
    } else {
      fhirStatusText.textContent = "Offline / Error";
      fhirDot.className = "dot-indicator dot-alert";
    }
  } catch (err) {
    fhirStatusText.textContent = "Unreachable";
    fhirDot.className = "dot-indicator dot-alert";
  }
}

async function fetchCases(autoSelectFirst = true) {
  try {
    const res = await fetch("/api/cases");
    if (!res.ok) return;
    const data = await res.json();
    activeCases = data.cases || [];
    activeCasesCount.textContent = activeCases.length;

    renderIncidentList();

    if (autoSelectFirst && activeCases.length > 0 && !selectedCaseId) {
      selectCase(activeCases[0].case_id);
    }
  } catch (err) {
    console.error("Failed to fetch cases:", err);
  }
}

async function fetchCaseDetails(caseId, highlightItem = true) {
  try {
    const res = await fetch(`/api/cases/${caseId}`);
    if (!res.ok) return;
    const fullState = await res.json();
    renderCaseDetails(fullState);

    if (highlightItem) {
      document.querySelectorAll(".incident-item").forEach((el) => {
        el.classList.toggle("selected", el.dataset.caseId === caseId);
      });
    }
  } catch (err) {
    console.error(`Failed to load details for case ${caseId}:`, err);
  }
}

// =====================================================================
// UI Rendering
// =====================================================================
function renderIncidentList(filter = "ALL") {
  incidentListContainer.innerHTML = "";

  const filtered = activeCases.filter((c) => {
    if (filter === "ALL") return true;
    return c.acuity_level === filter;
  });

  if (filtered.length === 0) {
    emptyQueueMessage.classList.remove("hidden");
    incidentListContainer.appendChild(emptyQueueMessage);
    return;
  }

  emptyQueueMessage.classList.add("hidden");

  filtered.forEach((c) => {
    const card = document.createElement("div");
    const acuityClass = c.acuity_level ? `acuity-${c.acuity_level.toLowerCase()}` : "acuity-none";
    card.className = `incident-item ${acuityClass} ${c.case_id === selectedCaseId ? "selected" : ""}`;
    card.dataset.caseId = c.case_id;

    const timeStr = new Date(c.reported_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    card.innerHTML = `
      <div class="item-top">
        <span class="item-case-id">${c.case_id}</span>
        <span class="item-time">${timeStr}</span>
      </div>
      <div class="item-landmark">${escapeHtml(c.landmark)}</div>
      <div class="item-snippet">${escapeHtml(c.raw_input_snippet)}</div>
      <div class="item-bottom">
        <span class="badge badge-acuity-${c.acuity_level || 'none'}">${c.acuity_level || 'PENDING'}</span>
        <span class="meta-item font-mono" style="font-size:0.7rem; color:var(--text-dim);">${c.selected_hospital || 'Routing...'}</span>
      </div>
    `;

    card.addEventListener("click", () => selectCase(c.case_id));
    incidentListContainer.appendChild(card);
  });
}

function selectCase(caseId) {
  selectedCaseId = caseId;
  btnOpenOverrideModal.disabled = false;
  fetchCaseDetails(caseId, true);
}

function renderCaseDetails(state) {
  const input = state.input_data;
  const triage = state.triage || {};
  const hosp = state.hospital_fhir || {};
  const voice = state.voice_family || {};
  const audit = state.control_audit || {};

  // Hero Card
  heroCaseId.textContent = input.case_id;
  heroLandmark.textContent = input.location.address_or_landmark;
  const reportedTime = new Date(input.reported_at).toLocaleString();
  heroReportedTime.textContent = `Reported: ${reportedTime} | Channel: ${input.modality.toUpperCase()} (${input.language})`;

  // Acuity Badge
  heroAcuityBadge.className = `badge badge-acuity-${triage.acuity_level || 'none'}`;
  heroAcuityBadge.textContent = triage.acuity_level ? `${triage.acuity_level} ACUITY` : "PENDING TRIAGE";

  // Hard-SOS
  if (triage.hard_sos) {
    heroHardSosBadge.classList.remove("hidden");
  } else {
    heroHardSosBadge.classList.add("hidden");
  }

  // Card 1: Narrative & Caller
  callerNarrativeText.textContent = input.raw_input;
  callerContactValue.textContent = input.caller_phone || "Unknown";
  callerGpsValue.textContent = `${input.location.latitude.toFixed(4)}° N, ${input.location.longitude.toFixed(4)}° E`;

  // Card 2: Triage Agent
  const confidencePct = Math.round((triage.confidence || 0) * 100);
  triageConfidenceBadge.textContent = `${confidencePct}% CONFIDENCE`;
  triageGuidelineText.textContent = triage.guideline_reference || "Standard Triage Operating Procedure";
  triageRationaleText.textContent = triage.rationale || "Synthesizing clinical assessment...";

  // Card 3: Hospital Matching
  if (hosp.selected_hospital_name) {
    selectedHospitalName.textContent = hosp.selected_hospital_name;
    const topCand = hosp.candidate_hospitals?.[0];
    const distance = topCand?.distance_km || 0;
    const drivingKm = topCand?.driving_distance_km;
    const etaMins = topCand?.eta_minutes;
    const routeSrc = topCand?.routing_source || "OSRM";

    if (drivingKm && etaMins) {
      hospDistanceVal.innerHTML = `<span style="color:var(--accent-cyan); font-weight:bold;">🚗 ${etaMins}m ETA</span> (${drivingKm} km via ${routeSrc} | ${distance.toFixed(1)} km straight-line)`;
    } else {
      hospDistanceVal.textContent = `${distance.toFixed(1)} km away`;
    }
    hospTraumaVal.textContent = `Trauma Level: ${topCand?.trauma_level || 'LEVEL_2'}`;
    hospBedsVal.textContent = `Available ICU: ${topCand?.available_icu_beds || 0}`;
    hospitalBedBadge.textContent = hosp.bed_status;
    hospitalBedBadge.className = `bed-status-badge ${hosp.bed_status === 'CONFIRMED' ? 'highlight' : ''}`;
  } else {
    selectedHospitalName.textContent = "Evaluating nearest corridor facilities...";
    hospDistanceVal.textContent = "-";
    hospTraumaVal.textContent = "-";
    hospBedsVal.textContent = "-";
  }

  // Candidate Table
  candidatesTableBody.innerHTML = "";
  if (hosp.candidate_hospitals && hosp.candidate_hospitals.length > 0) {
    hosp.candidate_hospitals.forEach((c) => {
      const tr = document.createElement("tr");
      const isSelected = c.hospital_id === hosp.selected_hospital_id;
      const distInfo = c.eta_minutes
        ? `<span style="color:var(--accent-cyan); font-weight:600;">🚗 ${c.eta_minutes}m</span> <span style="font-size:0.75rem; color:var(--text-dim);">(${c.driving_distance_km || c.distance_km}km ${c.routing_source || 'OSRM'})</span>`
        : `${c.distance_km.toFixed(1)} km`;
      tr.innerHTML = `
        <td><strong>${escapeHtml(c.name)}</strong> ${isSelected ? '<span style="color:var(--accent-cyan)">(Selected)</span>' : ''}</td>
        <td class="font-mono">${distInfo}</td>
        <td>${c.available_icu_beds} ICU / ${c.available_er_beds} ER</td>
        <td class="font-mono">${c.score.toFixed(1)}</td>
      `;
      candidatesTableBody.appendChild(tr);
    });
  } else {
    candidatesTableBody.innerHTML = `<tr><td colspan="4" class="text-muted">No candidates queried yet.</td></tr>`;
  }

  // Card 4: FHIR R4
  fhirBadgeStatus.textContent = hosp.fhir_submission_status || "PENDING";
  if (hosp.fhir_patient_id) {
    btnInspectPatient.disabled = false;
    btnInspectPatient.textContent = `Patient/${hosp.fhir_patient_id}`;
    btnInspectPatient.dataset.resId = hosp.fhir_patient_id;
  } else {
    btnInspectPatient.disabled = true;
    btnInspectPatient.textContent = "None";
  }

  if (hosp.fhir_encounter_id) {
    btnInspectEncounter.disabled = false;
    btnInspectEncounter.textContent = `Encounter/${hosp.fhir_encounter_id}`;
    btnInspectEncounter.dataset.resId = hosp.fhir_encounter_id;
  } else {
    btnInspectEncounter.disabled = true;
    btnInspectEncounter.textContent = "None";
  }

  if (hosp.fhir_condition_id) {
    btnInspectCondition.disabled = false;
    btnInspectCondition.textContent = `Condition/${hosp.fhir_condition_id}`;
    btnInspectCondition.dataset.resId = hosp.fhir_condition_id;
  } else {
    btnInspectCondition.disabled = true;
    btnInspectCondition.textContent = "None";
  }

  // Voice Sub-card
  voiceCallStatus.textContent = voice.call_status;
  voiceCallStatus.className = `badge ${voice.call_status === 'COMPLETED' ? 'badge-acuity-GREEN' : 'badge-case'}`;

  // Medical Tags
  medicalTagsContainer.innerHTML = "";
  const hasHistory = (voice.allergies && voice.allergies.length > 0) || (voice.medications && voice.medications.length > 0) || voice.blood_group;

  if (hasHistory) {
    if (voice.blood_group) {
      const bTag = document.createElement("span");
      bTag.className = "tag-blood";
      bTag.textContent = `Blood: ${voice.blood_group}`;
      medicalTagsContainer.appendChild(bTag);
    }
    (voice.allergies || []).forEach((a) => {
      const tag = document.createElement("span");
      tag.className = "tag-allergy";
      tag.textContent = `Allergy: ${a}`;
      medicalTagsContainer.appendChild(tag);
    });
    (voice.medications || []).forEach((m) => {
      const tag = document.createElement("span");
      tag.className = "tag-med";
      tag.textContent = `Med: ${m}`;
      medicalTagsContainer.appendChild(tag);
    });
  } else {
    medicalTagsContainer.innerHTML = `<span class="tag-empty">Awaiting next-of-kin allergy/history check</span>`;
  }

  // Enable simulate webhook button if call triggered or awaiting webhook
  btnSimulateWebhook.disabled = !(voice.call_status === "TRIGGERED" || audit.execution_stage === "AWAITING_WEBHOOK");

  // Card 5: Ambulance Fleet Dispatch (108 CAD)
  const amb = state.ambulance_dispatch || {};
  const unit = amb.selected_unit;

  if (unit && ambulanceTierBadge) {
    const isAls = unit.unit_type === "ALS";
    const missionStatus = (amb.mission_status || "DISPATCHED").toUpperCase();
    let statusLabel = `${unit.unit_type} ALLOCATED`;
    if (missionStatus === "ACKNOWLEDGED") statusLabel = "🚨 ACKNOWLEDGED BY CREW";
    else if (missionStatus === "EN_ROUTE_SCENE") statusLabel = "🚑 EN ROUTE TO SCENE";
    else if (missionStatus === "ON_SCENE") statusLabel = "📍 ON SCENE (10-23)";
    else if (missionStatus === "PATIENT_LOADED") statusLabel = "🩺 PATIENT LOADED / EN ROUTE ED";
    else if (missionStatus === "ARRIVED_ED") statusLabel = "🏥 ARRIVED AT ED TRAUMA BAY";
    else if (missionStatus === "HANDOVER_COMPLETE") statusLabel = "✅ HANDOVER COMPLETE / READY";

    ambulanceTierBadge.textContent = statusLabel;
    ambulanceTierBadge.className = `ambulance-tier-badge ${isAls ? "tier-als" : "tier-bls"} status-${missionStatus.toLowerCase().replace(/_/g, '-')}`;

    ambulanceCallsign.textContent = unit.unit_id;
    ambulanceVehicleNo.textContent = unit.vehicle_number;
    ambulanceAcuityTag.textContent = unit.unit_type;
    ambulanceAcuityTag.className = `unit-acuity-tag ${isAls ? "als" : "bls"}`;

    ambulanceBaseStation.textContent = unit.base_station;
    ambulanceEtaToScene.textContent = `${unit.eta_to_scene_minutes} mins`;
    ambulanceDistToScene.textContent = `(${unit.distance_to_scene_km} km via ${unit.routing_source || 'OSRM'})`;

    ambulanceParamedicName.textContent = unit.crew_lead_paramedic;
    ambulancePilotName.textContent = unit.pilot_driver;
    ambulancePilotPhone.textContent = unit.pilot_contact;

    // Equipment pills
    ambulanceEquipmentPills.innerHTML = "";
    (unit.equipment_manifest || []).forEach((eq) => {
      const pill = document.createElement("span");
      const isCritical = isAls && (eq.toLowerCase().includes("ventilator") || eq.toLowerCase().includes("defibrillator"));
      pill.className = `equip-pill ${isCritical ? "equip-als" : ""}`;
      pill.textContent = eq;
      ambulanceEquipmentPills.appendChild(pill);
    });

    ambulanceParamedicNotes.textContent = amb.paramedic_handover_notes || "En route to incident scene.";
    ambulanceTicketRef.textContent = `TICKET: ${amb.callout_ticket_id || 'PENDING'}`;
    if (btnViewCalloutTicket) btnViewCalloutTicket.disabled = false;

    // Driver companion button
    const btnOpenDriver = document.getElementById("btn-open-driver-companion");
    if (btnOpenDriver && amb.callout_ticket_id) {
      btnOpenDriver.href = `/driver/${encodeURIComponent(amb.callout_ticket_id)}`;
      btnOpenDriver.style.display = "inline-flex";
    }
  } else if (ambulanceTierBadge) {
    ambulanceTierBadge.textContent = "AWAITING ALLOCATION";
    ambulanceTierBadge.className = "ambulance-tier-badge";
    ambulanceCallsign.textContent = "AMB-108-XX";
    ambulanceVehicleNo.textContent = "TN-XX-XX-XXXX";
    ambulanceAcuityTag.textContent = "PENDING";
    ambulanceAcuityTag.className = "unit-acuity-tag";
    ambulanceBaseStation.textContent = "Awaiting dispatch";
    ambulanceEtaToScene.textContent = "-- mins";
    ambulanceDistToScene.textContent = "(-- km)";
    ambulanceParamedicName.textContent = "-";
    ambulancePilotName.textContent = "-";
    ambulancePilotPhone.textContent = "-";
    ambulanceEquipmentPills.innerHTML = `<span class="tag-empty">Awaiting fleet dispatch...</span>`;
    ambulanceParamedicNotes.textContent = "Awaiting incident dispatch and routing calculation...";
    ambulanceTicketRef.textContent = "TICKET: PENDING";
    if (btnViewCalloutTicket) btnViewCalloutTicket.disabled = true;

    const btnOpenDriver = document.getElementById("btn-open-driver-companion");
    if (btnOpenDriver) btnOpenDriver.style.display = "none";
  }

  // Update Pipeline Tracker
  updatePipelineTracker(audit.execution_stage);

  // Update Tactical Corridor Map & Highway Route
  updateCorridorMap(state);
}

function initCorridorMap() {
  const mapElem = document.getElementById("corridor-map-container");
  if (!mapElem || typeof L === "undefined") return;

  try {
    // Default center: Chennai South / Tambaram Corridor (12.96, 80.18)
    corridorMap = L.map("corridor-map-container", {
      center: [12.96, 80.18],
      zoom: 11,
      zoomControl: true,
      attributionControl: false
    });

    // Standard OpenStreetMap tiles with dark tactical CSS filter (no API key required)
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "© OpenStreetMap contributors"
    }).addTo(corridorMap);

    // Click anywhere on tactical corridor map to drop incident spot & open simulation
    corridorMap.on("click", (e) => {
      const lat = e.latlng.lat;
      const lon = e.latlng.lng;
      const popupHtml = `
        <div style="font-family:var(--font-sans); font-size:0.78rem; padding:4px 2px; color:#e2e8f0; min-width:180px;">
          <div style="font-weight:700; color:#38bdf8; margin-bottom:4px;">📍 Incident Pin Drop</div>
          <div style="font-family:var(--font-mono); font-size:0.75rem; color:#94a3b8; margin-bottom:8px;">
            ${lat.toFixed(4)}° N, ${lon.toFixed(4)}° E
          </div>
          <button id="btn-quick-dispatch-spot" style="width:100%; background:linear-gradient(135deg,#ef4444,#b91c1c); color:#fff; border:none; border-radius:4px; padding:6px 10px; font-weight:700; font-size:0.75rem; cursor:pointer; display:flex; align-items:center; justify-content:center; gap:4px; box-shadow:0 0 10px rgba(239,68,68,0.5);">
            <span>🚨 Dispatch Incident Here</span>
          </button>
        </div>
      `;
      L.popup({ className: "dark-map-popup" })
        .setLatLng([lat, lon])
        .setContent(popupHtml)
        .openOn(corridorMap);

      setTimeout(() => {
        const btn = document.getElementById("btn-quick-dispatch-spot");
        if (btn) {
          btn.onclick = () => {
            corridorMap.closePopup();
            modalSimulate.classList.remove("hidden");
            initOrRefreshPickerMap();
            if (pickerMarker && pickerMap) {
              pickerMarker.setLatLng([lat, lon]);
              pickerMap.setView([lat, lon], 14);
            }
            updateLocationFromPicker(lat, lon, true);
          };
        }
      }, 80);
    });


    // Quick-action map header controls
    const btnFocus = document.getElementById("btn-focus-accident");
    if (btnFocus) {
      btnFocus.addEventListener("click", () => {
        if (lastIncidentLatLng && corridorMap) {
          corridorMap.flyTo(lastIncidentLatLng, 14, { duration: 0.8 });
        }
      });
    }

    const btnFit = document.getElementById("btn-fit-corridor");
    if (btnFit) {
      btnFit.addEventListener("click", () => {
        if (lastBoundsPoints.length > 0 && corridorMap) {
          const bounds = L.latLngBounds(lastBoundsPoints);
          corridorMap.fitBounds(bounds, { padding: [45, 45], maxZoom: 14 });
        }
      });
    }
  } catch (err) {
    console.warn("Leaflet map initialization notice:", err);
  }
}

function getCleanHospitalName(fullName) {
  if (!fullName) return "Trauma Center";
  let name = fullName.trim();
  name = name.replace(/^Government Hospital\s+/i, "GH ")
             .replace(/^Government\s+/i, "Govt ")
             .replace(/Speciality Hospital/i, "Hospital")
             .replace(/Medical College & Hospital/i, "MCH")
             .replace(/Memorial Hospital/i, "Hospital");
  if (name.length > 18) {
    return name.substring(0, 16) + "...";
  }
  return name;
}

window.promptRerouteHospital = function(hospId, hospName) {
  if (!selectedCaseId) return;
  populateAndOpenOverrideModal();
  const selectHosp = document.getElementById("select-override-hospital");
  if (selectHosp) {
    selectHosp.value = hospId;
  }
  const notesField = document.getElementById("input-override-notes");
  if (notesField) {
    notesField.value = `Dispatcher tactical re-route to ${hospName || hospId} via Live Corridor Map selection.`;
  }
};

function updateCorridorMap(state) {
  if (!corridorMap || !state || !state.input_data) return;

  const loc = state.input_data.location;
  if (!loc || !loc.latitude || !loc.longitude) return;

  const incidentLat = loc.latitude;
  const incidentLon = loc.longitude;
  const hospState = state.hospital_fhir || {};
  const selectedId = hospState.selected_hospital_id;
  const acuity = (state.triage?.acuity_level || "RED").toUpperCase();

  lastIncidentLatLng = [incidentLat, incidentLon];

  // 1. Clear previous layers
  if (incidentMarker) {
    corridorMap.removeLayer(incidentMarker);
    incidentMarker = null;
  }
  if (incidentPerimeter) {
    corridorMap.removeLayer(incidentPerimeter);
    incidentPerimeter = null;
  }
  hospitalMarkers.forEach((m) => corridorMap.removeLayer(m));
  hospitalMarkers = [];
  if (ambulanceMarker) {
    corridorMap.removeLayer(ambulanceMarker);
    ambulanceMarker = null;
  }
  if (ambulanceRouteLine) {
    corridorMap.removeLayer(ambulanceRouteLine);
    ambulanceRouteLine = null;
  }
  if (routePolyline) {
    corridorMap.removeLayer(routePolyline);
    routePolyline = null;
  }

  // 2. Incident Beacon: Urgent Pulsing Radar Marker
  const isRed = acuity === "RED";
  const isYellow = acuity === "YELLOW";
  const hazardIcon = isRed ? "🚨" : (isYellow ? "⚠️" : "ℹ️");
  const waveClass = isYellow ? "yellow-acuity" : "";

  const incidentIcon = L.divIcon({
    className: "custom-incident-wrapper",
    html: `
      <div class="urgent-incident-marker">
        <div class="urgent-wave ring-1 ${waveClass}"></div>
        <div class="urgent-wave ring-2 ${waveClass}"></div>
        <div class="urgent-shield ${waveClass}">
          <span class="urgent-icon">${hazardIcon}</span>
        </div>
        <div class="incident-tag-label acuity-${acuity}">
          ${hazardIcon} ${escapeHtml(acuity)} ACCIDENT
        </div>
      </div>
    `,
    iconSize: [40, 40],
    iconAnchor: [20, 20]
  });

  incidentMarker = L.marker([incidentLat, incidentLon], { icon: incidentIcon, zIndexOffset: 1200 })
    .addTo(corridorMap)
    .bindPopup(`
      <div style="font-size:0.82rem; font-family:var(--font-sans); line-height:1.45; min-width:210px;">
        <div style="display:flex; align-items:center; gap:6px; margin-bottom:4px;">
          <span style="background:#ff3b30; color:#fff; font-weight:800; font-size:0.68rem; padding:2px 6px; border-radius:4px;">URGENT ACCIDENT SCENE</span>
          <span class="badge ${isRed ? 'badge-acuity-red' : (isYellow ? 'badge-acuity-yellow' : 'badge-acuity-green')}">${escapeHtml(acuity)}</span>
        </div>
        <strong style="color:#ffffff; font-size:0.9rem;">${escapeHtml(loc.address_or_landmark)}</strong><br/>
        <span style="color:var(--text-secondary); font-size:0.75rem;">Case: <code>${escapeHtml(state.input_data.case_id)}</code></span><br/>
        <div style="margin-top:6px; padding-top:6px; border-top:1px solid rgba(255,255,255,0.1); font-size:0.75rem; color:var(--text-secondary);">
          <strong>GPS Coordinates:</strong> ${incidentLat.toFixed(4)}° N, ${incidentLon.toFixed(4)}° E<br/>
          <strong>Hard-SOS Flag:</strong> ${state.triage?.hard_sos ? '⚡ Active' : 'Normal Protocol'}
        </div>
      </div>
    `);

  // 2.5 Golden Hour 5km Catchment Perimeter Ring
  const ringColor = isRed ? "#ef4444" : (isYellow ? "#f59e0b" : "#10b981");
  incidentPerimeter = L.circle([incidentLat, incidentLon], {
    radius: 5000,
    color: ringColor,
    fillColor: ringColor,
    fillOpacity: 0.06,
    weight: 1.5,
    dashArray: "6, 6"
  }).addTo(corridorMap);

  const boundsPoints = [[incidentLat, incidentLon]];

  // 3. Merge All Nearby Candidate Hospitals (Top Candidates + Raw Discovered)
  const hospMap = new Map();
  (hospState.candidate_hospitals || []).forEach((h) => {
    if (h.latitude && h.longitude) hospMap.set(h.hospital_id, h);
  });
  (hospState.raw_candidates || []).forEach((h) => {
    if (h.latitude && h.longitude && !hospMap.has(h.hospital_id)) {
      hospMap.set(h.hospital_id, h);
    }
  });
  const allHospitals = Array.from(hospMap.values());

  let targetCandidate = null;

  allHospitals.forEach((c) => {
    if (!c.latitude || !c.longitude) return;

    const isSelected = c.hospital_id === selectedId;
    const cleanName = getCleanHospitalName(c.name);
    const traumaCls = c.trauma_level === "LEVEL_1" ? "l1" : "l2";
    const traumaLabel = c.trauma_level === "LEVEL_1" ? "L1 Trauma" : "L2 Trauma";
    const icuBeds = c.available_icu_beds != null ? c.available_icu_beds : 0;
    const distKm = c.driving_distance_km || (c.distance_km ? c.distance_km.toFixed(1) : "--");

    if (isSelected) {
      targetCandidate = c;
      const etaText = c.eta_minutes ? `🚗 ${c.eta_minutes}m` : `${distKm}km`;

      const destPinHtml = `
        <div class="hospital-map-pin dest-pin">
          <div class="pin-title-row">
            <span class="pin-icon">🎯</span>
            <span class="pin-name">${escapeHtml(cleanName)}</span>
            <span class="pin-badge ${traumaCls}">${traumaLabel}</span>
          </div>
          <div class="pin-meta-row">
            <span class="eta-pill">${etaText} ETA</span>
            <span class="bed-pill">${icuBeds} ICU free</span>
          </div>
        </div>
      `;

      const destIcon = L.divIcon({
        className: "custom-hospital-icon-wrapper dest-wrapper",
        html: destPinHtml,
        iconSize: [180, 56],
        iconAnchor: [90, 28]
      });

      const marker = L.marker([c.latitude, c.longitude], { icon: destIcon, zIndexOffset: 1000 })
        .addTo(corridorMap)
        .bindPopup(`
          <div class="hosp-map-popup">
            <div class="hosp-popup-header">
              <span class="badge badge-acuity-red" style="font-size:0.68rem; font-weight:800;">TARGET DESTINATION</span>
              <span class="badge ${traumaCls === 'l1' ? 'badge-hard-sos' : 'badge-acuity-yellow'}">${traumaLabel}</span>
            </div>
            <strong style="color:var(--accent-cyan); font-size:0.92rem; display:block; margin:2px 0 6px;">${escapeHtml(c.name)}</strong>
            <div class="hosp-popup-metrics">
              <div><strong>Transit ETA:</strong> <span style="color:#00f0ff; font-weight:700;">${c.eta_minutes ? `${c.eta_minutes} mins` : '--'}</span> (${distKm} km via ${c.routing_source || 'OSRM'})</div>
              <div><strong>ICU Capacity:</strong> <span style="color:#10b981; font-weight:700;">${icuBeds} Free</span> / ${c.total_icu_beds || 15} Total</div>
              <div><strong>ER Trauma Bays:</strong> ${c.available_er_beds != null ? c.available_er_beds : '--'} Available</div>
              <div><strong>Specialties:</strong> ${(c.specialties || ['Trauma', 'Neurosurgery']).slice(0, 3).join(', ')}</div>
            </div>
          </div>
        `);

      hospitalMarkers.push(marker);
      boundsPoints.push([c.latitude, c.longitude]);

    } else {
      // Nearby Alternate Facility Pin
      const nearbyPinHtml = `
        <div class="hospital-map-pin nearby-pin">
          <div class="pin-title-row">
            <span class="pin-icon">🏥</span>
            <span class="pin-name">${escapeHtml(cleanName)}</span>
            <span class="pin-badge ${traumaCls}">${c.trauma_level === "LEVEL_1" ? "L1" : "L2"}</span>
          </div>
          <div class="pin-meta-row">
            <span>📍 ${distKm}km</span>
            <span class="bed-pill">${icuBeds} ICU</span>
          </div>
        </div>
      `;

      const nearbyIcon = L.divIcon({
        className: "custom-hospital-icon-wrapper nearby-wrapper",
        html: nearbyPinHtml,
        iconSize: [155, 48],
        iconAnchor: [77, 24]
      });

      const marker = L.marker([c.latitude, c.longitude], { icon: nearbyIcon, zIndexOffset: 500 })
        .addTo(corridorMap)
        .bindPopup(`
          <div class="hosp-map-popup">
            <div class="hosp-popup-header">
              <span style="color:var(--text-secondary); font-size:0.72rem; font-weight:700;">NEARBY BACKUP FACILITY</span>
              <span class="badge ${traumaCls === 'l1' ? 'badge-hard-sos' : 'badge-acuity-yellow'}">${traumaLabel}</span>
            </div>
            <strong style="color:#ffffff; font-size:0.88rem; display:block; margin:2px 0 6px;">${escapeHtml(c.name)}</strong>
            <div class="hosp-popup-metrics">
              <div><strong>Distance:</strong> ${distKm} km (${c.eta_minutes ? `🚗 ${c.eta_minutes}m ETA` : 'via OSRM'})</div>
              <div><strong>Beds Available:</strong> ${icuBeds} ICU / ${c.available_er_beds || '--'} ER</div>
            </div>
            <button class="btn-reroute-hosp" onclick="promptRerouteHospital('${escapeHtml(c.hospital_id)}', '${escapeHtml(c.name)}')">
              🔄 Re-route Dispatch to this Hospital
            </button>
          </div>
        `);

      hospitalMarkers.push(marker);
      boundsPoints.push([c.latitude, c.longitude]);
    }
  });

  // 3.5 Allocated Ambulance Unit Marker & Route Connection
  const ambDispatch = state.ambulance_dispatch || {};
  const ambUnit = ambDispatch.selected_unit;

  if (ambUnit && ambUnit.latitude && ambUnit.longitude) {
    const isAls = ambUnit.unit_type === "ALS";
    const ambPinHtml = `
      <div class="ambulance-map-pin">
        <span>🚑</span>
        <span>${escapeHtml(ambUnit.unit_id)}</span>
        <span class="pin-badge ${isAls ? 'l1' : 'l2'}">${escapeHtml(ambUnit.unit_type)}</span>
      </div>
    `;

    const ambIcon = L.divIcon({
      className: "custom-ambulance-icon-wrapper",
      html: ambPinHtml,
      iconSize: [110, 26],
      iconAnchor: [55, 13]
    });

    ambulanceMarker = L.marker([ambUnit.latitude, ambUnit.longitude], { icon: ambIcon, zIndexOffset: 900 })
      .addTo(corridorMap)
      .bindPopup(`
        <div style="font-size:0.8rem; font-family:var(--font-sans); line-height:1.45;">
          <div style="display:flex; align-items:center; gap:6px; margin-bottom:4px;">
            <span style="color:#00f0ff; font-weight:bold;">🚑 108 CAD AMBULANCE ALLOCATED</span>
            <span class="badge ${isAls ? 'badge-hard-sos' : 'badge-acuity-green'}">${escapeHtml(ambUnit.unit_type)}</span>
          </div>
          <strong>Unit:</strong> ${escapeHtml(ambUnit.unit_id)} (${escapeHtml(ambUnit.vehicle_number)})<br/>
          <strong>Base Depot:</strong> ${escapeHtml(ambUnit.base_station)}<br/>
          <strong>Scene ETA:</strong> <span style="color:var(--accent-cyan); font-weight:bold;">${ambUnit.eta_to_scene_minutes} mins</span> (${ambUnit.distance_to_scene_km} km via ${ambUnit.routing_source || 'OSRM'})<br/>
          <strong>Paramedic:</strong> ${escapeHtml(ambUnit.crew_lead_paramedic)}<br/>
          <strong>Pilot:</strong> ${escapeHtml(ambUnit.pilot_driver)} (${escapeHtml(ambUnit.pilot_contact)})
        </div>
      `);

    // Draw dashed amber dispatch route line from ambulance depot to incident scene
    ambulanceRouteLine = L.polyline([[ambUnit.latitude, ambUnit.longitude], [incidentLat, incidentLon]], {
      color: "#f59e0b",
      weight: 3,
      opacity: 0.85,
      dashArray: "8, 8"
    }).addTo(corridorMap);

    boundsPoints.push([ambUnit.latitude, ambUnit.longitude]);
  }

  // 4. Draw OSRM Highway Route Polyline
  const hudTarget = document.getElementById("hud-target-hospital");
  const hudEta = document.getElementById("hud-transit-eta");
  const hudDist = document.getElementById("hud-driving-distance");

  if (targetCandidate && targetCandidate.route_geometry && targetCandidate.route_geometry.length >= 2) {
    const polylineCoords = targetCandidate.route_geometry;

    // Glowing emergency highway corridor route
    routePolyline = L.polyline(polylineCoords, {
      color: "#00f0ff",
      weight: 5,
      opacity: 0.95,
      lineCap: "round",
      lineJoin: "round",
      dashArray: "10, 8"
    }).addTo(corridorMap);

    // Update Floating Map HUD
    if (hudTarget) hudTarget.textContent = targetCandidate.name;
    if (hudEta) hudEta.textContent = targetCandidate.eta_minutes ? `🚗 ${targetCandidate.eta_minutes} mins` : "--";
    if (hudDist) {
      hudDist.textContent = `${targetCandidate.driving_distance_km || targetCandidate.distance_km} km (${targetCandidate.routing_source || 'OSRM'})`;
    }
  } else {
    if (hudTarget) hudTarget.textContent = hospState.selected_hospital_name || "Nearest Trauma Facility";
    if (hudEta) hudEta.textContent = "--";
    if (hudDist) hudDist.textContent = "--";
  }

  // 5. Fit bounds with padding so dispatcher sees incident, hospital, and ambulance
  lastBoundsPoints = boundsPoints;
  if (boundsPoints.length > 0) {
    try {
      const bounds = L.latLngBounds(boundsPoints);
      corridorMap.fitBounds(bounds, { padding: [55, 55], maxZoom: 13 });
    } catch (err) {
      console.warn("Could not fit map bounds:", err);
    }
  }
}


function updatePipelineTracker(currentStage) {
  const stepOrder = [
    "step-ingest",
    "step-sos",
    "step-fanout",
    "step-merge",
    "step-ambulance",
    "step-voice",
    "step-complete"
  ];

  const activeStepId = stepMap[currentStage] || "step-ingest";
  const activeIdx = stepOrder.indexOf(activeStepId);

  stepOrder.forEach((stepId, idx) => {
    const el = document.getElementById(stepId);
    if (!el) return;
    el.classList.remove("active", "completed");
    if (idx < activeIdx) {
      el.classList.add("completed");
    } else if (idx === activeIdx) {
      el.classList.add("active");
    }
  });
}

// =====================================================================
// Dynamic Incident Location Picker (OSM & Nominatim Geocoding)
// =====================================================================
let pickerMap = null;
let pickerMarker = null;
let isCustomLocationSelected = false;
let reverseGeocodeTimeout = null;

function initOrRefreshPickerMap() {
  const container = document.getElementById("incident-picker-map");
  if (!container) return;

  const latVal = parseFloat(document.getElementById("input-custom-lat")?.value) || 12.9249;
  const lonVal = parseFloat(document.getElementById("input-custom-lon")?.value) || 80.1472;

  if (!pickerMap) {
    pickerMap = L.map("incident-picker-map", {
      center: [latVal, lonVal],
      zoom: 12,
      zoomControl: true,
      attributionControl: false
    });

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 18,
      attribution: "© OpenStreetMap contributors"
    }).addTo(pickerMap);

    const hazardIcon = L.divIcon({
      className: "picker-hazard-icon",
      html: `<div class="picker-marker-dot">📍</div>`,
      iconSize: [32, 32],
      iconAnchor: [16, 28]
    });

    pickerMarker = L.marker([latVal, lonVal], {
      draggable: true,
      icon: hazardIcon
    }).addTo(pickerMap);

    pickerMarker.on("dragend", (e) => {
      const pos = e.target.getLatLng();
      updateLocationFromPicker(pos.lat, pos.lng, true);
    });

    pickerMap.on("click", (e) => {
      const lat = e.latlng.lat;
      const lon = e.latlng.lng;
      pickerMarker.setLatLng([lat, lon]);
      updateLocationFromPicker(lat, lon, true);
    });
  } else {
    pickerMap.invalidateSize();
    pickerMarker.setLatLng([latVal, lonVal]);
    pickerMap.setView([latVal, lonVal], 13);
  }
}

async function updateLocationFromPicker(lat, lon, fetchAddress = true) {
  isCustomLocationSelected = true;
  document.querySelectorAll(".preset-btn").forEach((b) => b.classList.remove("selected"));

  const latInput = document.getElementById("input-custom-lat");
  const lonInput = document.getElementById("input-custom-lon");
  const landmarkInput = document.getElementById("input-custom-landmark");
  const statusPill = document.getElementById("picker-status-pill");

  if (latInput) latInput.value = lat.toFixed(5);
  if (lonInput) lonInput.value = lon.toFixed(5);

  if (statusPill) {
    statusPill.textContent = `📍 Selected: ${lat.toFixed(4)}° N, ${lon.toFixed(4)}° E`;
    statusPill.className = "picker-hint-badge resolving";
  }

  if (fetchAddress) {
    if (reverseGeocodeTimeout) clearTimeout(reverseGeocodeTimeout);
    reverseGeocodeTimeout = setTimeout(async () => {
      try {
        const url = `https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lon}&zoom=16&addressdetails=1`;
        const res = await fetch(url, {
          headers: { "Accept-Language": "en" }
        });
        if (res.ok) {
          const data = await res.json();
          const addr = data.address || {};
          const mainPart = addr.road || addr.suburb || addr.neighbourhood || addr.amenity || data.name || "Incident Spot";
          const cityPart = addr.city || addr.town || addr.county || addr.state_district || "Chennai";
          const resolvedLandmark = `${mainPart}, ${cityPart}`;

          if (landmarkInput) landmarkInput.value = resolvedLandmark;
          if (statusPill) {
            statusPill.textContent = `📍 ${resolvedLandmark}`;
            statusPill.className = "picker-hint-badge";
          }
        }
      } catch (err) {
        if (statusPill) {
          statusPill.textContent = `📍 GPS Pin: ${lat.toFixed(4)}° N, ${lon.toFixed(4)}° E`;
          statusPill.className = "picker-hint-badge";
        }
      }
    }, 350);
  }
}

async function handlePlaceSearch() {
  const searchInput = document.getElementById("input-map-search");
  const statusPill = document.getElementById("picker-status-pill");
  const landmarkInput = document.getElementById("input-custom-landmark");
  const query = searchInput ? searchInput.value.trim() : "";
  if (!query) return;

  if (statusPill) {
    statusPill.textContent = `🔍 Searching "${query}"...`;
    statusPill.className = "picker-hint-badge resolving";
  }

  try {
    const qWithRegion = query.toLowerCase().includes("chennai") || query.toLowerCase().includes("tamil nadu") ? query : `${query}, Chennai`;
    const url = `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(qWithRegion)}&countrycodes=in&limit=1`;
    const res = await fetch(url, {
      headers: { "Accept-Language": "en" }
    });
    if (res.ok) {
      const results = await res.json();
      if (results.length > 0) {
        const r = results[0];
        const lat = parseFloat(r.lat);
        const lon = parseFloat(r.lon);

        if (pickerMap && pickerMarker) {
          pickerMarker.setLatLng([lat, lon]);
          pickerMap.setView([lat, lon], 14);
        }

        const cleanName = r.display_name.split(",").slice(0, 3).join(",");
        if (landmarkInput) landmarkInput.value = cleanName;

        updateLocationFromPicker(lat, lon, false);
        if (statusPill) {
          statusPill.textContent = `📍 Located: ${cleanName}`;
          statusPill.className = "picker-hint-badge";
        }
      } else {
        alert(`Location "${query}" not found. You can click directly anywhere on the map.`);
        if (statusPill) {
          statusPill.textContent = `📍 Click map to drop beacon`;
          statusPill.className = "picker-hint-badge";
        }
      }
    }
  } catch (err) {
    console.warn("Place search failed:", err);
  }
}

// =====================================================================
// Actions & Handlers
// =====================================================================
async function handleDispatchSimulation() {
  const customNarrative = document.getElementById("input-custom-narrative").value.trim();
  const customLandmark = document.getElementById("input-custom-landmark").value.trim();
  const customPhone = document.getElementById("input-custom-phone").value.trim();
  const customDistrict = document.getElementById("input-custom-district")?.value || "Chennai";
  const customLat = parseFloat(document.getElementById("input-custom-lat")?.value);
  const customLon = parseFloat(document.getElementById("input-custom-lon")?.value);

  let payload = {};
  if (isCustomLocationSelected || customNarrative) {
    payload = {
      custom_input: customNarrative || `Emergency road accident reported at ${customLandmark || 'Scene'}. Urgent medical trauma team dispatched.`,
      landmark: customLandmark || "Chennai Metro Corridor",
      caller_phone: customPhone || "+91 94441 23456",
      district: customDistrict,
      latitude: !isNaN(customLat) ? customLat : 12.9249,
      longitude: !isNaN(customLon) ? customLon : 80.1472
    };
  } else {
    payload = { preset_key: selectedPresetKey };
  }

  btnSubmitSimulation.disabled = true;
  btnSubmitSimulation.textContent = "Ingesting...";

  try {
    const res = await fetch("/api/simulate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (res.ok) {
      const data = await res.json();
      modalSimulate.classList.add("hidden");
      selectedCaseId = data.case_id;
      setTimeout(() => fetchCases(true), 500);
    }
  } catch (err) {
    alert("Simulation dispatch failed: " + err.message);
  } finally {
    btnSubmitSimulation.disabled = false;
    btnSubmitSimulation.textContent = "🚨 Ingest & Dispatch CAD Incident";
  }
}


async function handleSimulateWebhook() {
  if (!selectedCaseId) return;

  btnSimulateWebhook.disabled = true;
  btnSimulateWebhook.textContent = "Receiving Callback...";

  try {
    const res = await fetch(`/api/cases/${selectedCaseId}/webhook`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        allergies: ["Ciprofloxacin", "Shellfish"],
        medications: ["Metformin 500mg daily"],
        blood_group: "O+",
        conditions: ["Type 2 Diabetes"],
        summary: "Spouse answered call. Confirmed severe allergy to Ciprofloxacin and regular Metformin."
      })
    });

    if (res.ok) {
      await fetchCaseDetails(selectedCaseId, false);
    }
  } catch (err) {
    alert("Failed to inject webhook: " + err.message);
  } finally {
    btnSimulateWebhook.disabled = false;
    btnSimulateWebhook.textContent = "Simulate Caller Webhook Callback";
  }
}

function populateAndOpenOverrideModal() {
  if (!selectedCaseId) return;
  const currentCase = activeCases.find((c) => c.case_id === selectedCaseId);

  // Populate Hospital dropdown
  selectOverrideHospital.innerHTML = `<option value="">-- Retain Recommended Destination --</option>`;
  fetch(`/api/cases/${selectedCaseId}`)
    .then((r) => r.json())
    .then((state) => {
      const candidates = state.hospital_fhir?.candidate_hospitals || [];
      candidates.forEach((c) => {
        const opt = document.createElement("option");
        opt.value = c.hospital_id;
        opt.textContent = `${c.name} (${c.distance_km.toFixed(1)} km - ${c.available_icu_beds} ICU Beds)`;
        selectOverrideHospital.appendChild(opt);
      });
      modalOverride.classList.remove("hidden");
    });
}

async function handleSubmitOverride() {
  const newAcuity = selectOverrideAcuity.value;
  const newHospId = selectOverrideHospital.value;
  const notes = inputOverrideNotes.value.trim();

  if (!notes) {
    alert("Human dispatchers MUST document an audit note justifying the override.");
    return;
  }

  let selectedHospName = null;
  if (newHospId) {
    const opt = selectOverrideHospital.querySelector(`option[value="${newHospId}"]`);
    if (opt) selectedHospName = opt.textContent.split(" (")[0];
  }

  btnSubmitOverride.disabled = true;

  try {
    const res = await fetch(`/api/cases/${selectedCaseId}/override`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        acuity_level: newAcuity || null,
        selected_hospital_id: newHospId || null,
        selected_hospital_name: selectedHospName || null,
        dispatcher_notes: notes
      })
    });

    if (res.ok) {
      modalOverride.classList.add("hidden");
      inputOverrideNotes.value = "";
      fetchCaseDetails(selectedCaseId, false);
    }
  } catch (err) {
    alert("Override failed: " + err.message);
  } finally {
    btnSubmitOverride.disabled = false;
  }
}

async function openFhirInspector(resourceType, resourceId) {
  if (!resourceId) return;

  fhirModalTitle.textContent = `HL7 FHIR R4: ${resourceType}/${resourceId}`;
  fhirModalUrl.textContent = `http://localhost:8080/fhir/${resourceType}/${resourceId}`;
  fhirModalJson.textContent = "Loading live FHIR resource from local HAPI FHIR server...";
  modalFhirInspector.classList.remove("hidden");

  try {
    const res = await fetch(`/api/fhir/${resourceType}/${resourceId}`);
    const data = await res.json();
    fhirModalJson.textContent = JSON.stringify(data, null, 2);
  } catch (err) {
    fhirModalJson.textContent = "Error fetching FHIR resource: " + err.message;
  }
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

// =====================================================================
// Phase D: Dispatcher Analytics Tab & Hospital Handover Engine
// =====================================================================
let currentHandoverCaseId = null;
let currentHandoverData = null;
let cachedAnalyticsCases = [];

function setupAnalyticsTab() {
  const tabLive = document.getElementById("tab-live-console");
  const tabAnalytics = document.getElementById("tab-analytics");
  const viewConsole = document.getElementById("view-console");
  const viewAnalytics = document.getElementById("view-analytics");

  if (tabLive && tabAnalytics) {
    tabLive.addEventListener("click", () => {
      tabLive.classList.add("active");
      tabAnalytics.classList.remove("active");
      viewConsole.classList.remove("hidden");
      viewAnalytics.classList.add("hidden");
      if (corridorMap) {
        setTimeout(() => corridorMap.invalidateSize(), 150);
      }
    });

    tabAnalytics.addEventListener("click", () => {
      tabAnalytics.classList.add("active");
      tabLive.classList.remove("active");
      viewConsole.classList.add("hidden");
      viewAnalytics.classList.remove("hidden");
      fetchAnalytics();
    });
  }

  // Quick export buttons
  const btnExportQuick = document.getElementById("btn-export-audit-json-quick");
  if (btnExportQuick) {
    btnExportQuick.addEventListener("click", handleExportAuditJson);
  }

  const btnExportFull = document.getElementById("btn-export-full-audit-json");
  if (btnExportFull) {
    btnExportFull.addEventListener("click", handleExportAuditJson);
  }

  // Refresh analytics
  const btnRefresh = document.getElementById("btn-refresh-analytics");
  if (btnRefresh) {
    btnRefresh.addEventListener("click", () => {
      btnRefresh.classList.add("spinning");
      fetchAnalytics().finally(() => {
        setTimeout(() => btnRefresh.classList.remove("spinning"), 500);
      });
    });
  }

  // Handover selection dropdown
  const selectHandover = document.getElementById("select-handover-case");
  if (selectHandover) {
    selectHandover.addEventListener("change", (e) => {
      const cId = e.target.value;
      if (cId) {
        currentHandoverCaseId = cId;
        loadHandoverPreview(cId);
      } else {
        resetHandoverPreview();
      }
    });
  }

  // Generate / Print Handover Slip
  const btnGenSlip = document.getElementById("btn-generate-handover-slip");
  if (btnGenSlip) {
    btnGenSlip.addEventListener("click", () => {
      if (currentHandoverCaseId) {
        openHandoverSlipModal(currentHandoverCaseId);
      }
    });
  }

  const modalHandover = document.getElementById("modal-handover-slip");
  const btnCloseHandover = document.getElementById("btn-close-handover-modal");
  if (btnCloseHandover && modalHandover) {
    btnCloseHandover.addEventListener("click", () => modalHandover.classList.add("hidden"));
  }

  const btnPrintSlip = document.getElementById("btn-print-slip");
  const btnPrintSlipFooter = document.getElementById("btn-print-slip-footer");
  if (btnPrintSlip) {
    btnPrintSlip.addEventListener("click", () => window.print());
  }
  if (btnPrintSlipFooter) {
    btnPrintSlipFooter.addEventListener("click", () => window.print());
  }

  const btnDownloadSlipJson = document.getElementById("btn-download-slip-json");
  if (btnDownloadSlipJson) {
    btnDownloadSlipJson.addEventListener("click", handleDownloadSingleSlipJson);
  }

  // Search filter on audit table
  const auditSearch = document.getElementById("audit-table-search");
  if (auditSearch) {
    auditSearch.addEventListener("input", (e) => {
      const query = e.target.value.toLowerCase().trim();
      filterAuditTable(query);
    });
  }
}

async function fetchAnalytics() {
  try {
    const res = await fetch("/api/analytics");
    if (!res.ok) throw new Error("Failed to fetch analytics");
    const data = await res.json();

    // 1. Update KPI ribbon
    const statTotal = document.getElementById("stat-total-incidents");
    const statSubtext = document.getElementById("stat-incidents-subtext");
    const statLatency = document.getElementById("stat-avg-latency");
    const statUnderTriage = document.getElementById("stat-under-triage");
    const statFhir = document.getElementById("stat-fhir-registrations");
    const tabBadge = document.getElementById("tab-badge-active-count");

    if (statTotal) statTotal.textContent = data.total_cases;
    if (tabBadge) tabBadge.textContent = data.total_cases;
    if (statSubtext) {
      statSubtext.textContent = data.is_simulated_corpus 
        ? "50 Calibrated AIIMS/MoRTH Incidents" 
        : `${data.total_cases} Active CAD Dispatches`;
    }
    if (statLatency) {
      statLatency.textContent = `${data.metrics.avg_latency_ms} ms`;
    }
    if (statUnderTriage) {
      statUnderTriage.textContent = `${data.metrics.under_triage_rate_pct.toFixed(1)}%`;
    }
    if (statFhir) {
      statFhir.textContent = `${data.metrics.fhir_registered_count} Synced`;
    }

    // 2. Render SVG Donut Chart
    renderTriageDonutChart(data.acuity_distribution, data.total_cases);

    // 3. Update Handover dropdown and table
    await refreshAuditCasesTable();

  } catch (err) {
    console.error("Analytics fetch failed:", err);
  }
}

function renderTriageDonutChart(distribution, total) {
  const svg = document.getElementById("triage-donut-svg");
  const totalDisplay = document.getElementById("donut-total-count");
  if (!svg || !totalDisplay) return;

  totalDisplay.textContent = total || 0;

  // Clear previous segments except center hole
  const oldSegments = svg.querySelectorAll(".donut-segment");
  oldSegments.forEach((el) => el.remove());

  const radius = 80;
  const circumference = 2 * Math.PI * radius; // ~502.65
  const cx = 120;
  const cy = 120;

  const red = distribution["RED"] || 0;
  const yellow = distribution["YELLOW"] || 0;
  const green = distribution["GREEN"] || 0;
  const black = distribution["BLACK"] || 0;

  // Update Legend numbers
  const countRed = document.getElementById("legend-count-red");
  const pctRed = document.getElementById("legend-pct-red");
  const countYellow = document.getElementById("legend-count-yellow");
  const pctYellow = document.getElementById("legend-pct-yellow");
  const countGreen = document.getElementById("legend-count-green");
  const pctGreen = document.getElementById("legend-pct-green");
  const countBlack = document.getElementById("legend-count-black");
  const pctBlack = document.getElementById("legend-pct-black");

  if (countRed) countRed.textContent = red;
  if (pctRed) pctRed.textContent = total ? `(${Math.round((red / total) * 100)}%)` : "(0%)";
  if (countYellow) countYellow.textContent = yellow;
  if (pctYellow) pctYellow.textContent = total ? `(${Math.round((yellow / total) * 100)}%)` : "(0%)";
  if (countGreen) countGreen.textContent = green;
  if (pctGreen) pctGreen.textContent = total ? `(${Math.round((green / total) * 100)}%)` : "(0%)";
  if (countBlack) countBlack.textContent = black;
  if (pctBlack) pctBlack.textContent = total ? `(${Math.round((black / total) * 100)}%)` : "(0%)";

  if (!total) return;

  const slices = [
    { name: "RED", count: red, color: "var(--red-critical, #f43f5e)", strokeColor: "#f43f5e" },
    { name: "YELLOW", count: yellow, color: "var(--yellow-urgent, #f59e0b)", strokeColor: "#f59e0b" },
    { name: "GREEN", count: green, color: "var(--green-stable, #10b981)", strokeColor: "#10b981" },
    { name: "BLACK", count: black, color: "var(--black-deceased, #475569)", strokeColor: "#475569" }
  ];

  let accumulatedOffset = 0;

  slices.forEach((slice) => {
    if (slice.count <= 0) return;

    const sliceFraction = slice.count / total;
    const strokeDash = sliceFraction * circumference;
    const strokeGap = circumference - strokeDash;

    const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    circle.setAttribute("class", `donut-segment segment-${slice.name.toLowerCase()}`);
    circle.setAttribute("cx", String(cx));
    circle.setAttribute("cy", String(cy));
    circle.setAttribute("r", String(radius));
    circle.setAttribute("fill", "transparent");
    circle.setAttribute("stroke", slice.strokeColor);
    circle.setAttribute("stroke-width", "26");
    circle.setAttribute("stroke-dasharray", `${strokeDash} ${strokeGap}`);
    circle.setAttribute("stroke-dashoffset", String(-accumulatedOffset));

    const title = document.createElementNS("http://www.w3.org/2000/svg", "title");
    title.textContent = `${slice.name}: ${slice.count} cases (${Math.round(sliceFraction * 100)}%)`;
    circle.appendChild(title);

    svg.appendChild(circle);
    accumulatedOffset += strokeDash;
  });
}

async function refreshAuditCasesTable() {
  try {
    const res = await fetch("/api/cases");
    if (!res.ok) return;
    const data = await res.json();
    cachedAnalyticsCases = data.cases || [];

    // 1. Populate Handover select dropdown
    const select = document.getElementById("select-handover-case");
    if (select) {
      const prevVal = select.value;
      select.innerHTML = '<option value="">-- Choose a Dispatched Incident --</option>';

      cachedAnalyticsCases.forEach((c) => {
        const opt = document.createElement("option");
        opt.value = c.case_id;
        opt.textContent = `${c.case_id} — [${c.acuity_level || "PENDING"}] ${c.landmark || "Chennai Corridor"}`;
        select.appendChild(opt);
      });

      if (prevVal && cachedAnalyticsCases.some((c) => c.case_id === prevVal)) {
        select.value = prevVal;
      } else if (cachedAnalyticsCases.length > 0 && !currentHandoverCaseId) {
        // Auto-select first case
        select.value = cachedAnalyticsCases[0].case_id;
        currentHandoverCaseId = cachedAnalyticsCases[0].case_id;
        loadHandoverPreview(currentHandoverCaseId);
      }
    }

    // 2. Render Audit Table
    renderAuditTableRows(cachedAnalyticsCases);

  } catch (err) {
    console.error("Failed to refresh audit cases:", err);
  }
}

function renderAuditTableRows(cases) {
  const tbody = document.getElementById("audit-table-body");
  if (!tbody) return;

  if (!cases || cases.length === 0) {
    tbody.innerHTML = `<tr><td colspan="8" class="text-center text-muted py-4">No active cases registered. Click "Simulate Incident" to ingest live emergency calls.</td></tr>`;
    return;
  }

  tbody.innerHTML = "";
  cases.forEach((c) => {
    const tr = document.createElement("tr");

    const acuity = c.acuity_level || "PENDING";
    let badgeClass = "badge-acuity-none";
    if (acuity === "RED") badgeClass = "badge-acuity-red";
    else if (acuity === "YELLOW") badgeClass = "badge-acuity-yellow";
    else if (acuity === "GREEN") badgeClass = "badge-acuity-green";

    const reportedDate = c.reported_at ? new Date(c.reported_at).toLocaleTimeString() : "--:--";

    tr.innerHTML = `
      <td><span class="font-mono text-cyan">${escapeHtml(c.case_id)}</span></td>
      <td class="text-muted">${escapeHtml(reportedDate)}</td>
      <td><strong>${escapeHtml(c.landmark || "Chennai South")}</strong></td>
      <td><span class="badge ${badgeClass}">${acuity}</span></td>
      <td>${c.hard_sos ? '<span class="badge badge-hard-sos">⚡ HARD-SOS</span>' : '<span class="text-muted text-dim">No</span>'}</td>
      <td>${escapeHtml(c.selected_hospital || "Evaluating...")}</td>
      <td><span class="text-green font-mono">${escapeHtml(c.bed_status || "CONFIRMED")}</span></td>
      <td class="audit-actions-cell">
        <button class="btn-small-action btn-sm-handover" data-case="${c.case_id}">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 6 2 18 2 18 9"></polyline><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"></path><rect x="6" y="14" width="12" height="8"></rect></svg>
          Handover Slip
        </button>
      </td>
    `;
    tbody.appendChild(tr);
  });

  // Attach button listeners
  tbody.querySelectorAll(".btn-sm-handover").forEach((btn) => {
    btn.addEventListener("click", () => {
      const cId = btn.dataset.case;
      if (cId) openHandoverSlipModal(cId);
    });
  });
}

function filterAuditTable(query) {
  if (!query) {
    renderAuditTableRows(cachedAnalyticsCases);
    return;
  }
  const filtered = cachedAnalyticsCases.filter((c) => {
    const idMatch = c.case_id && c.case_id.toLowerCase().includes(query);
    const landmarkMatch = c.landmark && c.landmark.toLowerCase().includes(query);
    const hospMatch = c.selected_hospital && c.selected_hospital.toLowerCase().includes(query);
    const acuityMatch = c.acuity_level && c.acuity_level.toLowerCase().includes(query);
    return idMatch || landmarkMatch || hospMatch || acuityMatch;
  });
  renderAuditTableRows(filtered);
}

async function loadHandoverPreview(caseId) {
  try {
    const res = await fetch(`/api/cases/${caseId}/handover`);
    if (!res.ok) return;
    const data = await res.json();
    currentHandoverData = data;

    const previewId = document.getElementById("preview-case-id");
    const previewAcuity = document.getElementById("preview-acuity-badge");
    const previewLoc = document.getElementById("preview-location");
    const previewHosp = document.getElementById("preview-hospital");
    const previewBed = document.getElementById("preview-bed-status");
    const previewFhir = document.getElementById("preview-fhir-id");
    const btnGen = document.getElementById("btn-generate-handover-slip");

    if (previewId) previewId.textContent = data.case_id;
    if (previewAcuity) {
      previewAcuity.textContent = data.clinical_triage.acuity_level || "PENDING";
      previewAcuity.className = `badge badge-acuity-${(data.clinical_triage.acuity_level || "").toLowerCase()}`;
    }
    if (previewLoc) previewLoc.textContent = data.incident_location.address || "Chennai South";
    if (previewHosp) previewHosp.textContent = data.receiving_facility.hospital_name || "Assigned";
    if (previewBed) previewBed.textContent = data.receiving_facility.bed_reservation_status || "CONFIRMED";
    if (previewFhir) previewFhir.textContent = data.fhir_pre_registration.bundle_id || "sim-bundle-pending";
    if (btnGen) btnGen.disabled = false;

  } catch (err) {
    console.error("Failed to load handover preview:", err);
  }
}

function resetHandoverPreview() {
  const previewId = document.getElementById("preview-case-id");
  const previewAcuity = document.getElementById("preview-acuity-badge");
  const previewLoc = document.getElementById("preview-location");
  const previewHosp = document.getElementById("preview-hospital");
  const previewBed = document.getElementById("preview-bed-status");
  const previewFhir = document.getElementById("preview-fhir-id");
  const btnGen = document.getElementById("btn-generate-handover-slip");

  if (previewId) previewId.textContent = "SELECT AN INCIDENT ABOVE";
  if (previewAcuity) {
    previewAcuity.textContent = "PENDING";
    previewAcuity.className = "badge badge-acuity-none";
  }
  if (previewLoc) previewLoc.textContent = "--";
  if (previewHosp) previewHosp.textContent = "--";
  if (previewBed) previewBed.textContent = "--";
  if (previewFhir) previewFhir.textContent = "--";
  if (btnGen) btnGen.disabled = true;
}

async function openHandoverSlipModal(caseId) {
  try {
    const res = await fetch(`/api/cases/${caseId}/handover`);
    if (!res.ok) throw new Error("Could not retrieve handover record");
    const data = await res.json();
    currentHandoverData = data;

    // Populate Handover Slip Document fields
    document.getElementById("slip-stamp-acuity").textContent = data.clinical_triage.acuity_level || "RED";
    document.getElementById("slip-case-id").textContent = data.case_id;
    document.getElementById("slip-time").textContent = new Date(data.reported_at).toLocaleString();
    document.getElementById("slip-caller").textContent = data.caller_contact || "Emergency Bystander";
    document.getElementById("slip-location").textContent = data.incident_location.address || "Chennai South";
    document.getElementById("slip-narrative").textContent = data.patient_narrative || "Emergency call logged.";

    document.getElementById("slip-acuity-name").textContent = `${data.clinical_triage.acuity_level} (Priority Emergency)`;
    document.getElementById("slip-hard-sos").textContent = data.clinical_triage.hard_sos_triggered ? "YES (Sub-Millisecond Bypass)" : "NO";
    document.getElementById("slip-confidence").textContent = `${Math.round((data.clinical_triage.confidence || 0.95) * 100)}%`;
    document.getElementById("slip-guideline").textContent = data.clinical_triage.guideline_citation || "AIIMS Emergency Protocol 2025";
    document.getElementById("slip-rationale").textContent = data.clinical_triage.rationale || "Life threat criteria met.";

    document.getElementById("slip-hospital-name").textContent = data.receiving_facility.hospital_name || "Emergency Department";
    document.getElementById("slip-trauma-level").textContent = data.receiving_facility.trauma_level || "LEVEL_1";
    const recFac = data.receiving_facility;
    const slipDistStr = recFac.eta_minutes
      ? `🚗 ${recFac.eta_minutes}m ETA (${recFac.driving_distance_km} km via ${recFac.routing_source || 'OSRM'}) [Straight: ${recFac.distance_km?.toFixed(1) || '-'} km]`
      : (recFac.distance_km ? `${recFac.distance_km.toFixed(1)} km` : "In Corridor");
    document.getElementById("slip-distance").textContent = slipDistStr;
    document.getElementById("slip-bed-status").textContent = data.receiving_facility.bed_reservation_status || "CONFIRMED";
    document.getElementById("slip-fhir-enc").textContent = data.fhir_pre_registration.encounter_id || "Enc/SIM-2025";
    document.getElementById("slip-fhir-cond").textContent = data.fhir_pre_registration.condition_id || "Cond/TRAUMA-01";
    document.getElementById("slip-hospital-reason").textContent = data.receiving_facility.ranking_reason || "Direct Level 1 trauma routing.";

    document.getElementById("slip-call-status").textContent = data.next_of_kin_telephony.call_status || "NOT_TRIGGERED";
    const allergies = data.next_of_kin_telephony.allergies || [];
    document.getElementById("slip-allergies").textContent = allergies.length > 0 ? allergies.join(", ") : "NKDA (No Known Drug Allergies)";
    const meds = data.next_of_kin_telephony.medications || [];
    document.getElementById("slip-medications").textContent = meds.length > 0 ? meds.join(", ") : "None verified";

    // Show modal
    document.getElementById("modal-handover-slip").classList.remove("hidden");

  } catch (err) {
    alert("Error preparing handover slip: " + err.message);
  }
}

async function handleExportAuditJson() {
  try {
    const res = await fetch("/api/audit/export");
    if (!res.ok) throw new Error("Failed to export audit report");
    const data = await res.json();

    const jsonStr = JSON.stringify(data, null, 2);
    const blob = new Blob([jsonStr], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const timestamp = new Date().toISOString().replace(/[:.]/g, "-");

    const a = document.createElement("a");
    a.href = url;
    a.download = `golden_audit_report_${timestamp}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

  } catch (err) {
    alert("Export failed: " + err.message);
  }
}

function handleDownloadSingleSlipJson() {
  if (!currentHandoverData) return;
  const jsonStr = JSON.stringify(currentHandoverData, null, 2);
  const blob = new Blob([jsonStr], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `handover_${currentHandoverData.case_id}.json`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// =====================================================================
// 108 CAD Ambulance Callout Ticket Controller
// =====================================================================
async function openCalloutTicketModal(caseId) {
  if (!caseId) return;
  try {
    const res = await fetch(`/api/cases/${caseId}/callout`);
    if (!res.ok) throw new Error("Could not retrieve ambulance callout ticket");
    const ticket = await res.json();

    if (ticket.status === "AWAITING_ALLOCATION") {
      alert("Ambulance allocation is still pending for this incident.");
      return;
    }

    // Populate modal ticket sheet
    if (ticketModalId) ticketModalId.textContent = ticket.callout_ticket_id || `CALLOUT-108-${caseId}`;
    if (ticketModalTime) {
      ticketModalTime.textContent = ticket.dispatch_timestamp
        ? new Date(ticket.dispatch_timestamp).toLocaleTimeString()
        : new Date().toLocaleTimeString();
    }

    if (ticketCaseId) ticketCaseId.textContent = ticket.case_id || caseId;
    if (ticketAcuity) ticketAcuity.textContent = `${ticket.acuity_level} (${ticket.unit_type_required} REQUIRED)`;
    if (ticketLocation) ticketLocation.textContent = ticket.incident_location?.address || "Chennai South Corridor";
    if (ticketGps) {
      const lat = ticket.incident_location?.latitude;
      const lon = ticket.incident_location?.longitude;
      ticketGps.textContent = lat && lon ? `${lat.toFixed(4)}° N, ${lon.toFixed(4)}° E` : "-";
    }
    if (ticketCallerPhone) ticketCallerPhone.textContent = ticket.caller_phone || "Unknown";

    const unit = ticket.allocated_unit || {};
    if (ticketUnitCallsign) ticketUnitCallsign.textContent = unit.unit_id || "AMB-108";
    if (ticketVehNo) ticketVehNo.textContent = unit.vehicle_number || "-";
    if (ticketTier) ticketTier.textContent = `${unit.unit_type || 'ALS'} (${unit.unit_type === 'ALS' ? 'Advanced Life Support' : 'Basic Life Support'})`;
    if (ticketDepot) ticketDepot.textContent = unit.base_station || "-";
    if (ticketEta) {
      ticketEta.textContent = `${unit.eta_to_scene_minutes || '--'} mins (${unit.distance_to_scene_km || '--'} km via ${unit.routing_source || 'OSRM'})`;
    }

    const dest = ticket.destination_hospital || {};
    if (ticketDestHospital) {
      const etaStr = dest.eta_minutes ? ` [🚗 ${dest.eta_minutes}m ETA via ${dest.routing_source || 'OSRM'}]` : "";
      ticketDestHospital.textContent = `${dest.name || 'Emergency Department'}${etaStr} • ${dest.trauma_level || 'LEVEL_1'}`;
    }

    const crew = ticket.crew_roster || {};
    if (ticketParamedic) ticketParamedic.textContent = crew.lead_paramedic || "-";
    if (ticketPilot) ticketPilot.textContent = crew.pilot_driver || "-";
    if (ticketPilotPhone) ticketPilotPhone.textContent = crew.pilot_contact || "-";

    // Equipment pills
    if (ticketEquipManifest) {
      ticketEquipManifest.innerHTML = "";
      const isAls = unit.unit_type === "ALS";
      (unit.equipment_manifest || []).forEach((eq) => {
        const pill = document.createElement("span");
        const isCritical = isAls && (eq.toLowerCase().includes("ventilator") || eq.toLowerCase().includes("defibrillator"));
        pill.className = `equip-pill ${isCritical ? "equip-als" : ""}`;
        pill.textContent = eq;
        ticketEquipManifest.appendChild(pill);
      });
    }

    if (ticketDrivingDirections) {
      ticketDrivingDirections.textContent = ticket.turn_by_turn_route || `Depart ${unit.base_station || 'Depot'} -> Proceed via fastest highway route to ${ticket.incident_location?.address || 'Incident Scene'}`;
    }
    if (ticketHandoverBrief) {
      ticketHandoverBrief.textContent = ticket.paramedic_handover_briefing || "En route to scene. Prepare airway stabilization on arrival.";
    }

    // Live QR Code and mobile companion deep link
    const qrImg = document.getElementById("ticket-qr-img");
    const qrLink = document.getElementById("ticket-qr-link");
    const targetTicket = ticket.callout_ticket_id || `CALLOUT-108-${caseId}`;

    if (qrImg) {
      qrImg.src = ticket.driver_qr_url || `/api/driver/${encodeURIComponent(targetTicket)}/qr?t=${Date.now()}`;
    }
    if (qrLink) {
      const compUrl = ticket.mobile_companion_url || `${window.location.origin}/driver/${encodeURIComponent(targetTicket)}`;
      qrLink.href = compUrl;
      qrLink.textContent = compUrl;
    }

    const btnModalDriver = document.getElementById("btn-modal-open-driver");
    if (btnModalDriver) {
      if (ticket.callout_ticket_id) {
        btnModalDriver.href = `/driver/${encodeURIComponent(ticket.callout_ticket_id)}`;
        btnModalDriver.style.display = "inline-flex";
      } else {
        btnModalDriver.style.display = "none";
      }
    }

    if (modalCalloutTicket) {
      modalCalloutTicket.classList.remove("hidden");
    }

  } catch (err) {
    alert("Error loading callout ticket: " + err.message);
  }
}


