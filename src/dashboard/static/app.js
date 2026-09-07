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
  "PARALLEL_TRIAGE_HOSPITAL": "step-fanout",
  "COORDINATOR_MERGE": "step-merge",
  "VOICE_DISPATCH": "step-voice",
  "AWAITING_WEBHOOK": "step-voice",
  "COMPLETED": "step-complete"
};

// =====================================================================
// Initialization
// =====================================================================
document.addEventListener("DOMContentLoaded", () => {
  setupEventListeners();
  checkHealth();
  fetchCases();
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
    const distance = hosp.candidate_hospitals?.[0]?.distance_km || 0;
    hospDistanceVal.textContent = `${distance.toFixed(1)} km away`;
    hospTraumaVal.textContent = `Trauma Level: ${hosp.candidate_hospitals?.[0]?.trauma_level || 'LEVEL_2'}`;
    hospBedsVal.textContent = `Available ICU: ${hosp.candidate_hospitals?.[0]?.available_icu_beds || 0}`;
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
      tr.innerHTML = `
        <td><strong>${escapeHtml(c.name)}</strong> ${isSelected ? '<span style="color:var(--accent-cyan)">(Selected)</span>' : ''}</td>
        <td class="font-mono">${c.distance_km.toFixed(1)} km</td>
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
