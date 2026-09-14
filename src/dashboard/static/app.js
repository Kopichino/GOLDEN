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

// Pipeline Steps
const stepMap = {
  "INGESTION": "step-ingest",
  "INGESTED": "step-ingest",
  "HARD_SOS_CHECK": "step-sos",
  "PARALLEL_TRIAGE_DISCOVERY": "step-fanout",
  "PARALLEL_TRIAGE_HOSPITAL": "step-fanout",
  "HOSPITAL_MATCHING": "step-merge",
  "COORDINATOR_MERGE": "step-merge",
  "FHIR_REGISTRATION": "step-voice",
  "VOICE_DISPATCH": "step-voice",
  "AWAITING_WEBHOOK": "step-voice",
  "DISPATCHER_REVIEW": "step-complete",
  "CONSOLIDATION": "step-complete",
  "COMPLETED": "step-complete"
};

// =====================================================================
// Initialization
// =====================================================================
document.addEventListener("DOMContentLoaded", () => {
  setupEventListeners();
  setupAnalyticsTab();
  checkHealth();
  fetchCases();
  fetchAnalytics();
  initSSE();
});

function setupEventListeners() {
  // Simulate Modal
  btnOpenSimulateModal.addEventListener("click", () => {
    modalSimulate.classList.remove("hidden");
  });
  btnCloseSimulateModal.addEventListener("click", () => modalSimulate.classList.add("hidden"));
  btnCancelSimulate.addEventListener("click", () => modalSimulate.classList.add("hidden"));

  // Preset Selection in Modal
  document.querySelectorAll(".preset-btn").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      document.querySelectorAll(".preset-btn").forEach((b) => b.classList.remove("selected"));
      btn.classList.add("selected");
      selectedPresetKey = btn.dataset.preset;
      // Clear custom fields
      document.getElementById("input-custom-narrative").value = "";
    });
  });

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

  // Update Pipeline Tracker
  updatePipelineTracker(audit.execution_stage);
}

function updatePipelineTracker(currentStage) {
  const stepOrder = [
    "step-ingest",
    "step-sos",
    "step-fanout",
    "step-merge",
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
// Actions & Handlers
// =====================================================================
async function handleDispatchSimulation() {
  const customNarrative = document.getElementById("input-custom-narrative").value.trim();
  const customLandmark = document.getElementById("input-custom-landmark").value.trim();
  const customPhone = document.getElementById("input-custom-phone").value.trim();

  let payload = {};
  if (customNarrative) {
    payload = {
      custom_input: customNarrative,
      landmark: customLandmark || "Tambaram Signal, Chennai",
      caller_phone: customPhone || "+91 94441 23456",
      latitude: 12.9249,
      longitude: 80.1472
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
    btnSubmitSimulation.textContent = "Dispatch Incident";
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

