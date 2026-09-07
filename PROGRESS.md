# GOLDEN — Project Implementation & Progress Tracker
**Guideline-Grounded Orchestrated LLM Dispatch for Emergency Networks**  
*Decision Support for India's 108/112 Pre-Hospital Emergency Response*

---

## 📊 Milestone Overview & Status Summary

| Phase | Description | Status | Verification & Artifacts |
| :--- | :--- | :---: | :--- |
| **Phase 0** | **Foundations**: State Schema, Architecture, HAPI FHIR, Docker & Synthea Data |  **COMPLETED** | HAPI FHIR Docker operational, Synthea data seeded, 17/17 tests passing |
| **Phase 1** | **Core Agents & Happy Path**: Hard-SOS, Triage, Hospital, LangGraph Coordinator, Voice Pipeline |  **COMPLETED** | End-to-end happy path verified via `scripts/run_demo.py` |
| **Phase 2** | **Hardening & Live Dispatcher Dashboard** (Items 1 & 2 for 50% Milestone) |  **COMPLETED** | Safety guardrails + live dashboard verified with 31/31 unit tests and browser demo |
| **Phase 3** | **Ablations & Empirical Benchmarking** (E1–E6, MedAgentBench) | 🔒 *LOCKED* | Out of scope for current milestone |
| **Phase 4** | **Paper, Artifacts & Documentation** | 🔒 *LOCKED* | Out of scope for current milestone |

> **Milestone Status: 50% PROJECT MILESTONE ACHIEVED**  
> All components of Phase 0, Phase 1, and Phase 2 Items 1 & 2 are implemented, fully tested, and verified end-to-end.

---

## 🏗️ Phase 0: Foundations (Completed)

### 1. Objective
Establish the project skeleton, data contracts, persistent FHIR R4 standard compliance, and containerized local infrastructure required for realistic emergency medical informatics.

### 2. Implemented Components & Architecture

#### A. Unified State Architecture (`src/state/schema.py`)
A comprehensive Pydantic v2 data model (`GoldenCaseState`) enforcing strict schema bounds across 5 distinct operational sections:
1. **Case Identity & Caller Input**: Case ID, timestamp, caller contact, incident location (latitude, longitude, corridor string), narrative, language/dialect, initial chief complaint.
2. **Triage Assessment**: Clinical acuity (`RED`, `YELLOW`, `GREEN`, `BLACK`), confidence score ($0.0 \le c \le 1.0$), clinical rationale, referenced triage guideline (`AIIMS ED Triage Protocol` / `MoRTH Golden Hour SOP 2025`), deterministic rule flags.
3. **Hospital & Resource State**: Matched destination hospital, Haversine distance ($km$), available ICU/oxygen beds, trauma level, pre-registration bundle transaction ID, FHIR resource references (`Patient/`, `Encounter/`, `Condition/`).
4. **Voice & Telephony State**: Outbound call ID, call status (`QUEUED`, `RINGING`, `IN_PROGRESS`, `COMPLETED`, `FAILED`), next-of-kin contact, collected history (allergies, active medications, existing comorbidities), timestamp of webhook receipt.
5. **Control & Audit**: Current execution node, pipeline stage (`INGESTED`, `TRIAGING`, `ROUTING`, `AWAITING_WEBHOOK`, `COMPLETED`, `ABORTED`), error log, human-in-the-loop dispatcher override flags, audit trail.

- **Verification**: `tests/test_state_schema.py` verifies field boundary validation, JSON serialization/deserialization, and immutability rules.

#### B. Architectural Blueprint (`ARCHITECTURE.md`)
Created a frozen 1-page reference architecture covering:
- Deterministic sub-millisecond emergency bypass vs. LLM reasoning paths.
- Asynchronous LangGraph cyclic state machine.
- Local interoperability with HL7 FHIR R4 standards.
- Fallback matrix across Gemini 3.6 Flash, Groq Qwen 3.6 27B, OpenRouter Nemotron, and local Ollama (`qwen2.5:7b`).

#### C. Local HAPI FHIR R4 Infrastructure (`docker-compose.yml`)
- Orchestrated an official `hapiproject/hapi:latest` instance mapped to host port `8080` with URL `http://localhost:8080/fhir`.
- **Memory Optimization**: Configured `JAVA_TOOL_OPTIONS=-Xms512m -Xmx1536m` to ensure rock-solid stability on Windows Docker Desktop without container crashes.
- **Spring Boot Config**: Corrected tester bean configuration (`hapi.fhir.tester.home.name=Local Tester`, `hapi.fhir.tester.home.server_address=http://localhost:8080/fhir`, `hapi.fhir.tester.home.fhir_version=R4`) resolving blank base URL spring bean exceptions.

#### D. Synthetic Emergency Data Seeding (`scripts/seed_synthea.py`)
- Seeded realistic healthcare organizations and emergency centers mapped along the Chennai South corridor (e.g., *Government Hospital Chromepet*, *Gleneagles HealthCity*, *Chettinad Super Speciality*).
- Created baseline Synthea synthetic patient records with realistic trauma conditions, allergies, and emergency department capability profiles.
- Verified live FHIR REST endpoints with `tests/test_fhir_integration.py`.

---

## 🤖 Phase 1: Core Agents & "Happy Path" Pipeline (Completed)

### 1. Objective
Develop all specialist agents, orchestrate them through a stateful LangGraph state machine with deterministic bypass and parallel fan-out capabilities, and verify an end-to-end emergency simulation.

### 2. Implemented Agents & Subsystems

```
                                  +-------------------+
                                  | Incident Ingested |
                                  +---------+---------+
                                            |
                                            v
                                 +--------------------+
                                 | Hard-SOS Rule Check|
                                 +----+----------+----+
                                      |          |
                      [Life-Threat]   |          | [Non-Immediate]
                     +----------------+          +----------------+
                     |                                            |
                     v                                            v
         +-----------------------+                    +-----------------------+
         | Direct Hospital Route |                    |    Parallel Fan-Out   |
         +-----------+-----------+                    +-----------+-----------+
                     |                                            |
                     |                        +-------------------+-------------------+
                     |                        |                                       |
                     |                        v                                       v
                     |             +---------------------+                 +---------------------+
                     |             | Triage Agent (LLM)  |                 | Hospital/Bed Agent  |
                     |             +----------+----------+                 +----------+----------+
                     |                        |                                       |
                     |                        +-------------------+-------------------+
                     |                                            |
                     +--------------------+-----------------------+
                                          |
                                          v
                              +-----------------------+
                              | LangGraph Coordinator |
                              +-----------+-----------+
                                          |
                                          v
                              +-----------------------+
                              | Outbound Voice Agent  |
                              +-----------+-----------+
                                          |
                                          v
                              +-----------------------+
                              |   Awaiting Webhook    |
                              +-----------+-----------+
                                          |
                               (Caller submits history)
                                          v
                              +-----------------------+
                              |  Checkpoint Resumption|
                              |      & Completion     |
                              +-----------------------+
```

#### A. Hard-SOS Rule Engine (`src/agents/hard_sos.py`)
- **Role**: Sub-millisecond deterministic emergency classifier.
- **Mechanism**: Regex pattern matching for non-negotiable critical conditions (`unresponsive`, `not breathing`, `cardiac arrest`, `severe bleeding`, `crushed under`, `head injury`).
- **Performance**: Benchmark verified at **< 0.02ms** execution latency.
- **Design Philosophy**: Zero LLM dependencies, deliberately biased towards false positives to guarantee zero life-threat false negatives.
- **Verification**: `tests/test_hard_sos.py` passed (critical trigger, false-positive bias, latency).

#### B. Guideline-Grounded Triage Agent (`src/agents/triage.py`)
- **Role**: Structured clinical acuity assessment.
- **Clinical Grounding**: Built directly upon the **AIIMS Emergency Department Triage Protocol** and the **MoRTH Golden Hour Care Standard Operating Procedure 2025**.
- **Model Handling & Failover**:
  - Primary: Google Gemini 3.6 Flash (sub-second response, structured JSON).
  - Secondary Failover: Groq Qwen 3.6 27B / OpenAI OSS models with custom `<think>...</think>` reasoning token stripper.
  - Tertiary Failover: OpenRouter / Local Ollama (`qwen2.5:7b`).
- **Resilience**: Enforces Pydantic schema validation (`TriageOutput`) with a self-healing retry loop.
- **Verification**: `tests/test_triage.py` passed.

#### C. Hospital & Bed Matching Agent (`src/agents/hospital.py`)
- **Role**: Geospatial search, live bed verification, and FHIR pre-registration.
- **Multi-Turn FHIR Queries**:
  1. Searches active emergency organizations in the vicinity via HAPI FHIR REST API.
  2. Queries bed status and emergency capabilities.
  3. Computes Haversine great-circle distance between incident GPS and hospital coordinates.
  4. Applies multi-factor composite ranking: $Score = f(Distance, Beds, TraumaLevel)$.
- **Atomic Pre-Registration Transaction**: Generates and posts an atomic HL7 FHIR R4 Transaction Bundle comprising:
  - `Patient` resource (demographics, contact, triage status).
  - `Encounter` resource (emergency class, priority, status `planned/in-progress`).
  - `Condition` resource (clinical impression, chief complaint, ICD/SNOMED coding).
- **Verification**: `tests/test_hospital.py` passed.

#### D. LangGraph Coordinator Orchestrator (`src/agents/coordinator.py`)
- **Role**: Stateful, cyclic graph coordinating parallel specialist execution.
- **Key Mechanics**:
  - **Hard-SOS Conditional Edge**: Direct bypass to hospital routing if critical life-threat flag is set.
  - **Parallel Fan-Out**: Concurrent dispatch of Triage Agent and Hospital Agent when incident requires full clinical deliberation.
  - **Partial Dict Returns**: Avoids LangGraph state collision (`InvalidUpdateError`) by returning granular node updates (`{"triage": ...}`, `{"hospital_fhir": ...}`).
  - **Durable Checkpointing**: Powered by LangGraph's `MemorySaver`, assigning thread persistence per `case_id`.
  - **Asynchronous Webhook Resumption**: Graph pauses in `AWAITING_WEBHOOK` state after voice dispatch; resumes dynamically via `resume_from_voice_webhook(case_id, payload)`.
- **Verification**: `tests/test_coordinator.py` passed.

#### E. Voice & Telephony Subsystem (`src/voice/`)
- **Audio Bridge (`src/voice/audio_bridge.py`)**: Real-time polyphase resampling between Exotel's 8kHz G.711/PCM telephony format and Gemini Live's 16kHz/24kHz wideband audio using NumPy and SciPy.
- **Exotel Client (`src/voice/exotel_client.py`)**: Outbound calling client featuring strict TRAI TCCCPR 2018 consent guardrails (simulation mode prevents unauthorized live calls during tests).
- **Webhook Receiver (`src/voice/webhook_receiver.py`)**: FastAPI endpoint (`/webhook/call-outcome`) that validates incoming next-of-kin medical disclosures and triggers graph resumption.
- **Verification**: `tests/test_audio_bridge.py` passed.

---

## 🛡️ Phase 2: Hardening & Minimal Live Dashboard (Completed — 50% Milestone)

### 1. Objective
Harden system safety across agent boundaries, neutralize adversarial inputs, protect citizen PII, enforce clinical safety rules, and deliver a live emergency console for human dispatchers.

### 2. Implemented Subsystems

#### A. Guardrail & Safety Validation Layer (`src/safety/guardrails.py`)
- **`PIISanitizer`**:
  - Scans incident text and caller logs for 12-digit Indian Aadhaar numbers, 10-digit Indian phone numbers with country codes, and PAN numbers.
  - Redacts sensitive data into `[AADHAAR-REDACTED]`, `[PHONE-REDACTED]`, and `[PAN-REDACTED]` prior to storage or external LLM inference.
- **`PromptInjectionDetector`**:
  - Neutralizes instruction hijacking patterns (`ignore previous instructions`, `system prompt override`, `act as an unrestricted doctor`, `prescribe drugs`).
  - Flags potential security incidents in audit logs without halting emergency medical dispatch.
- **`ClinicalSafetyValidator`**:
  - Validates categorical acuity boundaries (`RED`, `YELLOW`, `GREEN`, `BLACK`).
  - Mandates substantive clinical rationale and citations to recognized protocols (**AIIMS ED Protocol** or **MoRTH 2025 Golden Hour SOP**).
  - **Asymmetric Downgrade Prevention**: Blocks downgrading cases to `GREEN` when severe trauma symptoms (unconscious, active arterial bleeding, crushed limbs, head injury) are detected.
- **`InterAgentContractGuard`**:
  - Enforces schema contracts at LangGraph handoffs.
  - Automatically escalates corrupted or malformed triage outputs into a safe fail-open `RED` state with audit trails.
  - Ensures a valid fallback hospital candidate is always present.
- **Verification**: `tests/test_guardrails.py` passed (10/10 tests).

#### B. Minimal Live Dispatcher Dashboard (`src/dashboard/`)
- **FastAPI Backend Server (`src/dashboard/server.py`)**:
  - Real-Time **Server-Sent Events (SSE)** endpoint (`/api/events`) broadcasting state changes directly to connected browsers.
  - REST endpoints for case listing, case retrieval, health checks, and preset queries.
  - **Human-in-the-Loop Override Endpoint** (`/api/cases/{case_id}/override`): Enables human dispatchers to adjust acuity or change the target hospital destination with a mandatory operational note.
  - **Local FHIR Resource Proxy** (`/api/fhir/{resource_type}/{resource_id}`): Proxies queries directly to the local HAPI FHIR server on port 8080.
- **Modern Emergency Dispatch Web Console (`src/dashboard/static/`)**:
  - **Aesthetics & Theme**: Dark-mode glassmorphic console styled in Vanilla CSS, featuring glowing acuity badges (`#f43f5e`), clear typography (Inter, Outfit, JetBrains Mono), and micro-animations.
  - **Real-Time Incident Queue**: Color-coded cards reflecting live acuity (`RED`, `YELLOW`, `GREEN`), incident landmarks, and timestamps.
  - **Deep-Dive Case Inspector**:
    1. *Caller Narrative Panel*: Verbatim transcript, sanitized phone number, and GPS coordinates.
    2. *Clinical Triage Agent Panel*: Acuity badge, confidence score, guideline citation, and medical justification.
    3. *Hospital & Live Bed Matching Panel*: Selected facility, distance, trauma level, live ICU beds, and ranked candidate comparison table.
    4. *HL7 FHIR R4 Links*: Clickable links to inspect live `Patient/`, `Encounter/`, and `Condition/` resources in a modal JSON viewer.
    5. *Next-of-Kin Telephony*: Outbound call status, live allergy tags (`Blood: O+`, `Allergy: Ciprofloxacin`, `Allergy: Shellfish`, `Med: Metformin 500mg daily`), and caller webhook callback trigger.
  - **Pipeline Progression Tracker**: Visual 6-step flow (`Ingestion` $\rightarrow$ `Hard-SOS Rule` $\rightarrow$ `Parallel Fan-Out` $\rightarrow$ `Coordinator Merge` $\rightarrow$ `Voice Dispatch` $\rightarrow$ `Final Dispatch`).
  - **Interactive Simulation Modal**: Preset buttons for Chennai South corridor scenarios (*Tambaram Polytrauma*, *Guindy Cardiac Arrest*, *OMR Concussion*) and custom incident submission.

#### C. Full Repository Test Suite Verification
```bash
python -m pytest tests/ -v
================== 31 passed, 1 warning in 77.63s (0:01:17) ===================
```
- Total test cases: **31 passed, 0 failed**.
- Coverage spans all state schemas, deterministic engines, LLM prompts, multi-turn FHIR transactions, audio resampling, LangGraph cyclic routing, safety guardrails, and dashboard server endpoints.

---

## 📝 Change & Update Log

- **2026-09-07 (Phase 0 & Phase 1)**:
  - Repository initialized with 5-section `GoldenCaseState` Pydantic model.
  - HAPI FHIR JPA server running on Docker; Synthea synthetic data seeded.
  - Hard-SOS engine (<0.02ms), AIIMS/MoRTH Triage Agent, Hospital Matcher with FHIR R4 Bundle generator, LangGraph Coordinator, and Voice Audio Bridge implemented.
  - All 17 automated tests passed.
- **2026-09-07 (Phase 2 Items 1 & 2 — 50% Milestone Reached)**:
  - Implemented `PIISanitizer`, `PromptInjectionDetector`, `ClinicalSafetyValidator`, and `InterAgentContractGuard` in `src/safety/guardrails.py`.
  - Created unit tests in `tests/test_guardrails.py` (10 passed).
  - Built FastAPI dashboard server with real-time SSE stream, HITL overrides, and FHIR resource proxy in `src/dashboard/server.py`.
  - Built modern dark-theme dispatcher interface (`index.html`, `app.css`, `app.js`).
  - Created dashboard test suite in `tests/test_dashboard.py` (4 passed).
  - Full test suite verified: **31 passed in 77.63s**.
  - Browser subagent completed live simulation demo on `http://localhost:8000` with screenshots captured.
  - 50% Milestone achieved. Awaiting permission to proceed to Phase 2 Item 3 / subsequent phases.
