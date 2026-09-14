/**
 * GOLDEN 108 CAD — Field Paramedic & Pilot Companion Controller
 * Mobile-First Dynamic Route, Vitals, and Mission Lifecycle Engine
 */

let missionData = null;
let driverMap = null;
let currentTicketId = null;

// Lifecycle Milestone Definitions
const MILESTONES = {
  DISPATCHED: {
    step: 1,
    icon: "🚨",
    action: "TAP TO ACKNOWLEDGE",
    sub: "Step 1: Confirm Mission Assignment",
    nextStatus: "ACKNOWLEDGED",
    btnClass: "stage-ack"
  },
  ACKNOWLEDGED: {
    step: 2,
    icon: "🚑",
    action: "EN ROUTE TO SCENE",
    sub: "Step 2: Depart Base Depot & Roll Sirens",
    nextStatus: "EN_ROUTE_SCENE",
    btnClass: "stage-en-route"
  },
  EN_ROUTE_SCENE: {
    step: 3,
    icon: "📍",
    action: "ARRIVED ON SCENE",
    sub: "Step 3: Signal Visual Contact with Patient",
    nextStatus: "ON_SCENE",
    btnClass: "stage-on-scene"
  },
  ON_SCENE: {
    step: 4,
    icon: "🩺",
    action: "PATIENT LOADED (TO ED)",
    sub: "Step 4: Stabilized & Rolling to Receiving ED",
    nextStatus: "PATIENT_LOADED",
    btnClass: "stage-loaded"
  },
  PATIENT_LOADED: {
    step: 5,
    icon: "🏥",
    action: "ARRIVED AT ED / HANDOVER",
    sub: "Step 5: Handover to Trauma Resuscitation Team",
    nextStatus: "ARRIVED_ED",
    btnClass: "stage-completed"
  },
  ARRIVED_ED: {
    step: 5,
    icon: "✅",
    action: "COMPLETE MISSION",
    sub: "Final: Sign Triage Handover & Reset Unit",
    nextStatus: "HANDOVER_COMPLETE",
    btnClass: "stage-completed"
  },
  HANDOVER_COMPLETE: {
    step: 5,
    icon: "🎉",
    action: "MISSION COMPLETED",
    sub: "Unit is Ready & Available for Next 108 CAD Call",
    nextStatus: null,
    btnClass: "stage-completed"
  }
};

document.addEventListener("DOMContentLoaded", () => {
  startLiveClock();
  resolveTicketId();
  fetchMissionData();
  setupMilestoneButton();
  initDriverSSE();
});

function startLiveClock() {
  const clockEl = document.getElementById("driver-clock");
  if (!clockEl) return;
  const update = () => {
    const now = new Date();
    clockEl.textContent = now.toTimeString().split(" ")[0];
  };
  update();
  setInterval(update, 1000);
}

function resolveTicketId() {
  const pathParts = window.location.pathname.split("/").filter(Boolean);
  // Matches /driver/{id} or /cad/driver/{id}
  if (pathParts.length >= 2 && (pathParts[0] === "driver" || pathParts[1] === "driver")) {
    currentTicketId = pathParts[pathParts.length - 1];
  } else {
    // Check URL search query
    const params = new URLSearchParams(window.location.search);
    currentTicketId = params.get("ticket") || params.get("case") || "CALLOUT-DEMO";
  }
}

async function fetchMissionData() {
  if (!currentTicketId) return;

  try {
    const res = await fetch(`/api/driver/${encodeURIComponent(currentTicketId)}`);
    if (!res.ok) throw new Error("Could not retrieve mission data for ticket " + currentTicketId);
    missionData = await res.json();
    renderMissionView(missionData);
  } catch (err) {
    console.error("Error loading mission:", err);
    document.getElementById("hero-landmark").textContent = "Mission Not Found (" + currentTicketId + ")";
  }
}

function renderMissionView(data) {
  // 1. Header and Unit
  const unit = data.unit || {};
  document.getElementById("driver-unit-callsign").textContent = unit.unit_id || "AMB-108";
  document.getElementById("driver-veh-plate").textContent = unit.vehicle_number || "TN-07-G-108";
  
  const tierBadge = document.getElementById("driver-unit-tier");
  tierBadge.textContent = unit.unit_type || "ALS";
  if (unit.unit_type === "BLS") {
    tierBadge.classList.add("tier-bls");
  } else {
    tierBadge.classList.remove("tier-bls");
  }

  // 2. Acuity Hero
  const isRed = (data.acuity_level || "RED").toUpperCase() === "RED";
  const heroCard = document.getElementById("acuity-hero-card");
  const heroPill = document.getElementById("hero-alert-pill");
  
  if (isRed) {
    heroCard.classList.remove("yellow-acuity");
    heroPill.textContent = "🚨 PRIORITY RED EMERGENCY (ALS REQUIRED)";
  } else {
    heroCard.classList.add("yellow-acuity");
    heroPill.textContent = "🟡 URGENT " + (data.acuity_level || "YELLOW") + " (BLS TRANSPORT)";
  }

  document.getElementById("hero-ticket-id").textContent = data.ticket_id || currentTicketId;
  document.getElementById("hero-landmark").textContent = data.incident?.address || "Chennai South Highway Corridor";
  
  const phone = data.incident?.caller_phone || "+91 94441 23456";
  document.getElementById("hero-caller-phone").textContent = phone;
  const telBtn = document.getElementById("btn-tel-caller");
  if (telBtn) telBtn.href = `tel:${phone.replace(/\s+/g, '')}`;

  // 3. Milestone State
  updateMilestoneUI(data.mission_status || "DISPATCHED");

  // 4. Mobile Map
  renderMobileMap(data);

  // 5. Turn-by-Turn
  const listEl = document.getElementById("route-instructions-list");
  listEl.innerHTML = "";
  (data.turn_by_turn_instructions || []).forEach((inst) => {
    const li = document.createElement("li");
    li.textContent = inst;
    listEl.appendChild(li);
  });

  // 6. Paramedic Handover Briefing & Narrative
  document.getElementById("paramedic-briefing-text").textContent =
    data.paramedic_briefing || "Airway stabilization protocol active. Prepare cervical collar and IV access on arrival.";
  document.getElementById("victim-raw-narrative").textContent =
    data.incident?.narrative || "Emergency collision logged.";

  // Equipment chips
  const equipWrap = document.getElementById("driver-equip-chips");
  equipWrap.innerHTML = "";
  (unit.equipment_manifest || []).forEach((eq) => {
    const chip = document.createElement("span");
    chip.className = "chip";
    chip.textContent = eq;
    equipWrap.appendChild(chip);
  });

  // 7. Hospital Info
  const hosp = data.hospital || {};
  document.getElementById("driver-hosp-name").textContent = hosp.name || "Emergency Department";
  document.getElementById("driver-hosp-trauma").textContent = hosp.trauma_level || "LEVEL 1 TRAUMA";
  document.getElementById("driver-hosp-eta").textContent = hosp.eta_minutes ? `🚗 ${hosp.eta_minutes} mins` : "--";
  document.getElementById("driver-hosp-icu").textContent = `${hosp.available_icu_beds != null ? hosp.available_icu_beds : 6} Beds Free`;
  document.getElementById("driver-hosp-er").textContent = `${hosp.available_er_beds != null ? hosp.available_er_beds : 12} Available`;
  
  const hospPhone = hosp.reception_phone || "+91 44 2220 9000";
  document.getElementById("driver-hosp-phone").textContent = hospPhone;
  const hospTelBtn = document.getElementById("btn-call-hospital");
  if (hospTelBtn) hospTelBtn.href = `tel:${hospPhone.replace(/\s+/g, '')}`;

  // 8. Crew Info
  const crew = data.crew || {};
  document.getElementById("driver-paramedic-val").textContent = crew.lead_paramedic || "-";
  document.getElementById("driver-pilot-val").textContent = `${crew.pilot_driver || '-'} (${crew.pilot_contact || '-'})`;
}

function updateMilestoneUI(currentStatus) {
  const normStatus = (currentStatus || "DISPATCHED").toUpperCase();
  const def = MILESTONES[normStatus] || MILESTONES.DISPATCHED;

  const btn = document.getElementById("btn-primary-milestone");
  const icon = document.getElementById("milestone-btn-icon");
  const action = document.getElementById("milestone-btn-action");
  const sub = document.getElementById("milestone-btn-sub");

  // Reset classes
  btn.className = "btn-giant-milestone " + def.btnClass;
  icon.textContent = def.icon;
  action.textContent = def.action;
  sub.textContent = def.sub;

  if (!def.nextStatus) {
    btn.disabled = true;
    btn.style.opacity = "0.85";
  } else {
    btn.disabled = false;
    btn.style.opacity = "1";
  }

  // Update 5 Stepper Dots
  const activeStepNum = def.step;
  for (let i = 1; i <= 5; i++) {
    const dot = document.getElementById(`step-dot-${i}`);
    if (!dot) continue;
    dot.classList.remove("active", "completed");
    if (i < activeStepNum) {
      dot.classList.add("completed");
    } else if (i === activeStepNum) {
      dot.classList.add("active");
    }
  }
}

function setupMilestoneButton() {
  const btn = document.getElementById("btn-primary-milestone");
  if (!btn) return;

  btn.addEventListener("click", async () => {
    if (!missionData) return;
    const currentStatus = (missionData.mission_status || "DISPATCHED").toUpperCase();
    const def = MILESTONES[currentStatus] || MILESTONES.DISPATCHED;
    const nextStatus = def.nextStatus;

    if (!nextStatus) return;

    // Play subtle tactical audio beep
    playTacticalBeep();

    btn.disabled = true;
    btn.style.opacity = "0.7";

    try {
      const res = await fetch(`/api/driver/${encodeURIComponent(currentTicketId)}/status`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          status: nextStatus,
          notes: `Milestone advanced to ${nextStatus} via Mobile Driver Companion`
        })
      });

      if (!res.ok) throw new Error("Status update failed");
      const result = await res.json();

      missionData.mission_status = result.mission_status;
      updateMilestoneUI(result.mission_status);

    } catch (err) {
      alert("Network or CAD error updating milestone: " + err.message);
    } finally {
      btn.disabled = false;
      btn.style.opacity = "1";
    }
  });
}

function playTacticalBeep() {
  try {
    const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.type = "sine";
    osc.frequency.setValueAtTime(880, audioCtx.currentTime); // A5 note
    gain.gain.setValueAtTime(0.12, audioCtx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.15);
    osc.connect(gain);
    gain.connect(audioCtx.destination);
    osc.start();
    osc.stop(audioCtx.currentTime + 0.15);
  } catch (e) {
    // AudioContext blocked or not supported
  }
}

function renderMobileMap(data) {
  if (typeof L === "undefined") return;

  const mapElem = document.getElementById("driver-map");
  if (!mapElem) return;

  const unit = data.unit || {};
  const incident = data.incident || {};
  const hosp = data.hospital || {};

  const incLat = incident.latitude || 12.9249;
  const incLon = incident.longitude || 80.1472;
  const unitLat = unit.latitude || 12.9340;
  const unitLon = unit.longitude || 80.1280;
  const hospLat = hosp.latitude || 12.9150;
  const hospLon = hosp.longitude || 80.2000;

  // Update floating HUD
  const hudEta = document.getElementById("hud-eta-pill");
  const hudDist = document.getElementById("hud-dist-pill");
  if (hudEta) hudEta.textContent = `🚗 Scene ETA: ${unit.eta_to_scene_minutes || 6}m`;
  if (hudDist) hudDist.textContent = `📍 ${unit.distance_to_scene_km || 4.8} km (${unit.routing_source || 'OSRM'})`;

  if (!driverMap) {
    driverMap = L.map("driver-map", {
      center: [incLat, incLon],
      zoom: 12,
      zoomControl: false,
      attributionControl: false
    });

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19
    }).addTo(driverMap);
  }

  // Clear existing layers
  driverMap.eachLayer((layer) => {
    if (layer instanceof L.Marker || layer instanceof L.Polyline || layer instanceof L.Circle) {
      driverMap.removeLayer(layer);
    }
  });

  const boundsPoints = [];

  // 1. Ambulance Depot Marker
  const ambIcon = L.divIcon({
    className: "driver-amb-icon",
    html: `<div style="background:#0284c7; border:2px solid #fff; border-radius:50%; width:32px; height:32px; display:flex; align-items:center; justify-content:center; font-size:16px; box-shadow:0 0 12px #0284c7;">🚑</div>`,
    iconSize: [32, 32],
    iconAnchor: [16, 16]
  });
  L.marker([unitLat, unitLon], { icon: ambIcon }).addTo(driverMap).bindPopup(`<strong>${unit.unit_id || 'Ambulance Hub'}</strong><br/>${unit.base_station || ''}`);
  boundsPoints.push([unitLat, unitLon]);

  // 2. Accident Scene Marker
  const hazardIcon = L.divIcon({
    className: "driver-hazard-icon",
    html: `<div style="background:#ef4444; border:2px solid #fff; border-radius:50%; width:34px; height:34px; display:flex; align-items:center; justify-content:center; font-size:17px; box-shadow:0 0 15px #ef4444; animation:pulse-ack 1.5s infinite;">🚨</div>`,
    iconSize: [34, 34],
    iconAnchor: [17, 17]
  });
  L.marker([incLat, incLon], { icon: hazardIcon }).addTo(driverMap).bindPopup(`<strong>ACCIDENT SCENE</strong><br/>${incident.address || ''}`);
  boundsPoints.push([incLat, incLon]);

  // 3. Receiving Hospital Marker
  const hospIcon = L.divIcon({
    className: "driver-hosp-icon",
    html: `<div style="background:#10b981; border:2px solid #fff; border-radius:50%; width:32px; height:32px; display:flex; align-items:center; justify-content:center; font-size:16px; box-shadow:0 0 12px #10b981;">🎯</div>`,
    iconSize: [32, 32],
    iconAnchor: [16, 16]
  });
  L.marker([hospLat, hospLon], { icon: hospIcon }).addTo(driverMap).bindPopup(`<strong>${hosp.name || 'Trauma Center'}</strong><br/>${hosp.trauma_level || ''}`);
  boundsPoints.push([hospLat, hospLon]);

  // 4. Connecting Route
  if (data.route_geometry && data.route_geometry.length >= 2) {
    L.polyline(data.route_geometry, {
      color: "#00f0ff",
      weight: 4,
      opacity: 0.9,
      dashArray: "8, 6"
    }).addTo(driverMap);
  } else {
    // Fallback line
    L.polyline([[unitLat, unitLon], [incLat, incLon], [hospLat, hospLon]], {
      color: "#00f0ff",
      weight: 3,
      opacity: 0.8,
      dashArray: "6, 6"
    }).addTo(driverMap);
  }

  // Auto-fit bounds
  if (boundsPoints.length > 0) {
    try {
      const bounds = L.latLngBounds(boundsPoints);
      driverMap.fitBounds(bounds, { padding: [35, 35], maxZoom: 13 });
    } catch (e) {
      console.warn("Could not fit driver map:", e);
    }
  }
}

function initDriverSSE() {
  const eventSource = new EventSource("/api/events");
  eventSource.onmessage = (e) => {
    try {
      const event = JSON.parse(e.data);
      if (event.case_id && missionData && event.case_id === missionData.case_id) {
        // If hospital override or status update received
        if (event.event_type === "AMBULANCE_STATUS_UPDATE" && event.mission_status) {
          missionData.mission_status = event.mission_status;
          updateMilestoneUI(event.mission_status);
        } else if (event.stage === "DISPATCHER_OVERRIDE") {
          fetchMissionData();
        }
      }
    } catch (err) {}
  };
}
