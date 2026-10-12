/* GOLDEN CAD — Guided onboarding tour.
   Self-contained: no external dependencies, exposes window.GoldenTour with
   start()/stop(). Auto-offers itself once on first visit via localStorage. */
(function () {
  "use strict";

  const STORAGE_KEY = "golden_tour_completed_v1";

  const STEPS = [
    {
      kicker: "Welcome",
      title: "GOLDEN 108/112 Dispatch Console",
      text: "A two-minute tour of where everything lives. You can reopen it any time with the Tour button in the header.",
    },
    {
      selector: "#btn-open-simulate-modal",
      kicker: "Step 1",
      title: "Ingest an incident",
      text: "Start here. 'Simulate Incident' opens the intake form: pick a preset or drop a location, then dispatch it into the pipeline.",
      placement: "bottom",
    },
    {
      selector: ".incident-feed-panel",
      kicker: "Step 2",
      title: "Active Incident Queue",
      text: "Every live case appears on the left. Filter by Critical or Urgent, and click a card to inspect it. The tab badge counts them.",
      placement: "right",
    },
    {
      selector: "#case-hero-card",
      kicker: "Step 3",
      title: "Case Inspector",
      text: "The selected case fills this column: acuity, Hard-SOS, and the MoRTH Golden-Hour clock. Dispatcher Override sits on the right.",
      placement: "bottom",
    },
    {
      selector: "#pipeline-tracker-card",
      kicker: "Step 4",
      title: "Orchestration pipeline",
      text: "Watch the deterministic LangGraph stages advance: ingestion, triage, hospital discovery & matching, FHIR pre-registration, voice, handover.",
      placement: "bottom",
    },
    {
      selector: ".specialist-grid",
      kicker: "Step 5",
      title: "Decision panels",
      text: "Clinical triage rationale, the ranked hospital choice with its ranking_reason, FHIR resources, the consent-gated family voice result, and the dispatched ambulance unit.",
      placement: "top",
    },
    {
      selector: "#tactical-corridor-map-card",
      kicker: "Step 6",
      title: "Tactical corridor map",
      text: "Scene, destination and nearby hospitals with the OSRM route. Click a pin for details or to re-route.",
      placement: "top",
    },
    {
      selector: "#tab-analytics",
      kicker: "Step 7",
      title: "Analytics & Audit",
      text: "Switch tabs for fleet KPIs, the acuity distribution, handover slips and the full auditable case table with JSON export.",
      placement: "bottom",
    },
    {
      kicker: "Driver companion",
      title: "Take it to the field",
      text: "On the ambulance panel there's a QR code — scan it with a phone on the same Wi-Fi to open the mobile Driver Companion, and milestone taps sync back here live.",
    },
  ];

  let root, spotlight, tip, kickerEl, titleEl, textEl, dotsEl, backBtn, nextBtn, skipBtn;
  let current = -1;
  let built = false;

  function build() {
    if (built) return;
    root = document.createElement("div");
    root.id = "tour-root";
    root.innerHTML =
      '<div id="tour-spotlight"></div>' +
      '<div id="tour-tip" role="dialog" aria-modal="false">' +
        '<div class="tour-kicker"></div>' +
        '<div class="tour-title"></div>' +
        '<div class="tour-text"></div>' +
        '<div class="tour-footer">' +
          '<div class="tour-dots"></div>' +
          '<div class="tour-actions">' +
            '<button class="tour-btn ghost" data-tour="back">Back</button>' +
            '<button class="tour-btn ghost" data-tour="skip">Skip</button>' +
            '<button class="tour-btn primary" data-tour="next">Next</button>' +
          "</div>" +
        "</div>" +
      "</div>";
    document.body.appendChild(root);

    spotlight = document.getElementById("tour-spotlight");
    tip = document.getElementById("tour-tip");
    kickerEl = tip.querySelector(".tour-kicker");
    titleEl = tip.querySelector(".tour-title");
    textEl = tip.querySelector(".tour-text");
    dotsEl = tip.querySelector(".tour-dots");
    backBtn = tip.querySelector('[data-tour="back"]');
    nextBtn = tip.querySelector('[data-tour="next"]');
    skipBtn = tip.querySelector('[data-tour="skip"]');

    backBtn.addEventListener("click", () => go(current - 1));
    nextBtn.addEventListener("click", () => go(current + 1));
    skipBtn.addEventListener("click", () => stop(true));
    document.addEventListener("keydown", onKey);
    window.addEventListener("resize", () => { if (current >= 0) position(current); });
    built = true;
  }

  function onKey(e) {
    if (current < 0) return;
    if (e.key === "Escape") stop();
    else if (e.key === "ArrowRight") go(current + 1);
    else if (e.key === "ArrowLeft") go(current - 1);
  }

  function renderDots(step) {
    dotsEl.innerHTML = "";
    STEPS.forEach((_, i) => {
      const d = document.createElement("span");
      d.className = "tour-dot" + (i === step ? " active" : "");
      dotsEl.appendChild(d);
    });
  }

  function position(step) {
    const s = STEPS[step];
    const target = s.selector ? document.querySelector(s.selector) : null;
    if (target && target.offsetParent !== null) {
      root.classList.remove("tour-center");
      const r = target.getBoundingClientRect();
      const pad = 8;
      spotlight.style.top = Math.max(6, r.top - pad) + "px";
      spotlight.style.left = Math.max(6, r.left - pad) + "px";
      spotlight.style.width = (r.width + pad * 2) + "px";
      spotlight.style.height = (r.height + pad * 2) + "px";

      // Place the tip near the spotlight, clamped to the viewport.
      const tw = tip.offsetWidth, th = tip.offsetHeight;
      const gap = 16;
      let left, top;
      if (s.placement === "right") {
        left = r.right + pad + gap;
        top = r.top;
        if (left + tw > window.innerWidth - 8) left = r.left - tw - gap;
      } else if (s.placement === "top") {
        left = r.left;
        top = r.top - th - gap;
      } else {
        // default bottom
        left = r.left;
        top = r.bottom + gap;
      }
      left = Math.min(Math.max(8, left), window.innerWidth - tw - 8);
      top = Math.min(Math.max(8, top), window.innerHeight - th - 8);
      tip.style.left = left + "px";
      tip.style.top = top + "px";
    } else {
      root.classList.add("tour-center");
    }
  }

  function go(step) {
    if (step < 0 || step >= STEPS.length) {
      if (step >= STEPS.length) stop(true);
      return;
    }
    current = step;
    const s = STEPS[step];
    kickerEl.textContent = s.kicker || "";
    titleEl.textContent = s.title;
    textEl.textContent = s.text;
    renderDots(step);
    backBtn.disabled = step === 0;
    nextBtn.textContent = step === STEPS.length - 1 ? "Done" : "Next";
    position(step);
    requestAnimationFrame(() => position(step));
  }

  function start() {
    build();
    root.classList.add("tour-open");
    go(0);
  }

  function stop(completed) {
    if (root) root.classList.remove("tour-open");
    current = -1;
    if (completed) {
      try { localStorage.setItem(STORAGE_KEY, "1"); } catch (e) {}
    }
  }

  function maybeAutoStart() {
    let seen = false;
    try { seen = !!localStorage.getItem(STORAGE_KEY); } catch (e) {}
    if (seen) return;
    // Let the dashboard settle before offering the tour.
    setTimeout(start, 900);
  }

  document.addEventListener("DOMContentLoaded", () => {
    const btn = document.getElementById("btn-open-tour");
    if (btn) btn.addEventListener("click", start);
    maybeAutoStart();
  });

  window.GoldenTour = { start, stop };
})();
