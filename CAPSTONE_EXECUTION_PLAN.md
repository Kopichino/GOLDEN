# GOLDEN Capstone Execution Plan

**Project:** Guideline-Grounded Orchestrated LLM Dispatch for Emergency Networks  
**Purpose:** Turn the working prototype into a reproducible, demonstrable, and presentation-ready capstone system.

**Plan status:** Active  
**Started:** 2026-09-10  
**Current verified baseline:** HAPI FHIR is running locally; the seed baseline contains 3 hospital organizations and 4 synthetic patients; the complete test suite passes 36 tests; dependency-aware LangGraph state machine with join barrier and two-stage hospital matching verified; CLI demo and dashboard smoke checks successful.

---

## 1. Capstone Use Case

GOLDEN is an emergency dispatch decision-support system for road-accident and acute medical incidents in the Indian 108/112 context.

A dispatcher submits an incident report containing:

- What happened and the reported symptoms
- The caller phone number
- The incident location
- Optional language or voice-derived input

GOLDEN then:

1. Detects immediate life threats with a deterministic Hard-SOS safety path (< 0.02ms).
2. Concurrently reasons over clinical acuity (AIIMS/MoRTH) and discovers candidate emergency facilities via Haversine distance and FHIR capabilities.
3. Ranks destination hospitals at a LangGraph Join Barrier using validated clinical acuity and generates an auditable `ranking_reason`.
4. Pre-registers the patient, encounter, and condition using an atomic FHIR R4 transaction bundle.
5. Starts a consent-gated family information outreach workflow in simulation mode.
6. Pauses and resumes the workflow when a call webhook supplies allergies, medication, blood group, or medical history.
7. Shows the entire case lifecycle in a dispatcher dashboard with full auditable human-in-the-loop override authority.

### Demonstration story

> A motorcycle rider is reported unresponsive after a collision on GST Road. GOLDEN immediately marks the case RED, selects a nearby emergency hospital, creates the FHIR pre-registration records, and displays the decision trail to the dispatcher. A simulated family call then adds allergy and medication information before the case is completed.

This is a decision-support prototype. It does not replace a qualified dispatcher, clinician, ambulance crew, or hospital policy.

---

## 2. Delivery Principles

Every stage must leave three kinds of evidence:

1. **Implementation evidence:** code, configuration, or tests.
2. **Runtime evidence:** command output, endpoint response, screenshot, or demo recording.
3. **Documentation evidence:** an update to the relevant Markdown file and this plan.

No stage is marked complete based only on code inspection. A stage is complete only after its verification command succeeds.

---

## 3. Phased Workflow

### Phase 0 — Environment and Reproducibility

**Goal:** Make a fresh local setup predictable.

**Work items:**

- Confirm Python dependencies and environment variables.
- Start Docker Desktop and the HAPI FHIR container.
- Verify `/fhir/metadata` returns a FHIR CapabilityStatement.
- Seed synthetic organizations and patients.
- Record the exact setup commands and known troubleshooting steps.

**Verification:**

```powershell
docker compose up -d
Invoke-RestMethod http://localhost:8080/fhir/metadata
python scripts/seed_synthea.py
```

**Exit criteria:** HAPI is reachable, seed completes, and the setup guide matches reality.

**Documentation:** `SETUP_GUIDE.md`, `README.md`, `PROGRESS.md`, this file.

**Status:** Complete on 2026-09-10.

---

### Phase 1 — Functional Baseline and Use-Case Demo

**Goal:** Prove the complete emergency workflow before making presentation improvements.

**Work items:**

- Run the full automated test suite.
- Run the command-line demo.
- Start the dashboard.
- Exercise one Hard-SOS case and one non-SOS case.
- Exercise the webhook resumption path.
- Capture the expected outputs and known limitations.

**Verification:**

```powershell
python -m pytest -q
python scripts/run_demo.py
python -m uvicorn src.dashboard.server:app --host 127.0.0.1 --port 8000
```

**Exit criteria:** Tests pass, the CLI demo completes, the dashboard health endpoint responds, and the two core scenarios are documented.

**Documentation:** `README.md`, `SYSTEM_EXPLANATION.md`, `PROGRESS.md`, this file.

**Verified result (2026-09-10):** The CLI demo completed an end-to-end YELLOW incident with offline triage, hospital selection, successful FHIR Patient/Encounter/Condition pre-registration, consent-gated voice handling, and successful webhook checkpoint resumption. Dashboard health returned `ONLINE` with `fhir_connected=true`.

**Status:** Complete.

---

### Phase 2 — Dashboard Demonstration Readiness & Architecture Refactoring

**Goal:** Clean component classification, implement real dependency-aware concurrency, and make the project presentation-ready.

**Work items:**

- Classify components accurately (Deterministic Hard-SOS, Orchestrator state machine, Triage LLM agent, Two-stage hospital matching, FHIR tool layer, Consent-gated family communication, Human dispatcher override authority).
- Implement dependency-aware LangGraph state graph with explicit join barrier.
- Split hospital matching into Stage 1 discovery (concurrent with triage) and Stage 2 matching (acuity-conditioned).
- Add `FamilyCommunicationAgent` separating consent logic from telephony.
- Extend state schema with `raw_candidates`, `ranking_reason`, `HumanOverrideRecord`, and node timings.
- Verify dashboard endpoints, presets, HITL overrides, and 6-stage pipeline tracker.
- Add `tests/test_architecture_refactor.py` (5 tests).

**Verification:**

```powershell
python -m pytest tests/ -v
```

**Exit criteria:** Complete test suite passes (36/36), dependency barriers and Hard-SOS bypass function properly, human override records persist with audit notes, and presentation runbook matches code.

**Documentation:** `ARCHITECTURE.md`, `README.md`, `SYSTEM_EXPLANATION.md`, `PROGRESS.md`, `DEMO_RUNBOOK.md`, this file.

**Verified result (2026-09-13):** Full test suite passed 36/36 in 2.63s. Dashboard verified online on port 8000 with interactive simulation and human override persistence.

**Status:** Complete.


---

### Phase 3 — Safety, Reliability, and Explainability Review

**Goal:** Make the prototype defensible as an emergency decision-support system.

**Work items:**

- Verify Hard-SOS false-negative-sensitive patterns.
- Verify triage offline fallback when API keys are absent.
- Verify PII sanitization and prompt-injection handling.
- Verify the consent guardrail prevents unauthorized calls.
- Verify hospital/FHIR failures produce an explicit safe state.
- Add or improve tests for failure paths, duplicate seeding, and unavailable services.
- Review logging so patient phone numbers and sensitive data are not exposed.

**Verification:**

```powershell
python -m pytest -q tests/test_hard_sos.py tests/test_triage.py tests/test_guardrails.py tests/test_fhir_integration.py
```

**Exit criteria:** Safety behaviors are covered by tests and explained in the viva documentation.

**Documentation:** `ARCHITECTURE.md`, `SYSTEM_EXPLANATION.md`, `core.md`, this file.

**Status:** Planned.

---

### Phase 4 — Evaluation and Evidence

**Goal:** Produce measurable evidence instead of only a feature checklist.

**Work items:**

- Define a small evaluation set of representative emergency scenarios.
- Measure Hard-SOS latency, triage behavior, hospital ranking, FHIR write success, and workflow completion.
- Compare hosted-LLM mode with offline fallback mode.
- Record limitations, false-positive tradeoffs, and infrastructure assumptions.
- Produce tables and charts suitable for the report and presentation.

**Verification:**

```powershell
python scripts/run_demo.py
python -m pytest -q
```

**Exit criteria:** The report contains repeatable metrics, scenario definitions, and limitations.

**Documentation:** `PROGRESS.md`, `project_exp.md`, `core.md`, this file.

**Status:** Planned.

---

### Phase 5 — Presentation and Submission Package

**Goal:** Make the capstone understandable in a short live presentation.

**Deliverables:**

- One-page problem and solution summary.
- Architecture diagram and data-flow explanation.
- Five-minute live demo script.
- Backup terminal demo when the browser or an external provider fails.
- Test and runtime evidence appendix.
- Limitations, ethics, privacy, and future-work section.
- Final README setup path that another student can reproduce.

**Exit criteria:** The project can be explained in 60 seconds, demonstrated in 5 minutes, and defended with test evidence.

**Documentation:** all project Markdown files, especially `README.md`, `SYSTEM_EXPLANATION.md`, `project_exp.md`, and `core.md`.

**Status:** Planned.

---

## 4. Immediate Work Queue

1. Run and document the CLI emergency workflow.
2. Verify dashboard health and preset endpoints.
3. Exercise Hard-SOS and non-SOS scenarios against live FHIR.
4. Record the expected panel demonstration sequence. **Done:** `DEMO_RUNBOOK.md`.
5. Review and improve any behavior that blocks a repeatable demo.
6. Update the relevant Markdown files after each verified change.

---

## 5. Current Verified Baseline

| Area | Current result | Evidence |
| --- | --- | --- |
| Docker/HAPI | Running on port 8080 | `docker compose ps` |
| FHIR metadata | `CapabilityStatement` returned | `GET /fhir/metadata` |
| Seed baseline | 3 organizations, 4 patients | `scripts/seed_synthea.py` |
| Live store after tests | 3 organizations, 16 patients | FHIR search response |
| Automated tests | 36 passed | `python -m pytest -v` |
| Hosted LLM | Not configured locally | blank `.env` provider keys |
| Triage fallback | Available | `TriageAgent._offline_triage` |
| Voice | Simulation and consent refusal supported | `ExotelClient` |
| Dashboard | Available on port 8000 when started | Uvicorn + dashboard tests |
| CLI demo | End-to-end workflow completed successfully | `python scripts/run_demo.py` |
| Dashboard smoke check | `ONLINE`, FHIR connected, case queue available | `/api/health`, `/api/presets`, `/api/cases` |

---

## 6. Known Limitations to Present Honestly

- HAPI FHIR is local Docker infrastructure, not a production hospital information system.
- Patient and hospital data are synthetic.
- Hosted LLM keys are optional; without them, deterministic offline triage is used.
- Exotel live calls are not enabled by default and are consent-gated.
- Hospital bed availability is modeled in synthetic FHIR data.
- The system provides decision support and does not make autonomous clinical decisions.
- Integration-test data accumulates in the local HAPI store unless it is cleared deliberately.

---

## 7. Documentation Checkpoint Rule

After every completed work item:

1. Update this plan’s status and verified result.
2. Update the closest technical document.
3. Update `PROGRESS.md` with the date and evidence.
4. Update `README.md` if the user-facing run command changes.
5. Do not claim a feature is complete until a fresh verification command supports it.
