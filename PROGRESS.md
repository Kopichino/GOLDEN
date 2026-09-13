# GOLDEN — Project Implementation & Progress Tracker
**Guideline-Grounded Orchestrated LLM Dispatch for Emergency Networks**  
*Decision Support for India's 108/112 Pre-Hospital Emergency Response*

---

## 📊 Milestone Overview & Status Summary

| Phase | Description | Status | Verification & Artifacts |
| :--- | :--- | :---: | :--- |
| **Phase 0** | **Foundations**: State Schema, Architecture, HAPI FHIR, Docker & Synthea Data |  **COMPLETED** | HAPI FHIR Docker operational, 3 organizations and 4 patients seeded, FHIR metadata verified |
| **Phase 1** | **Core Agents & Happy Path**: Hard-SOS, Triage, Hospital, LangGraph Coordinator, Voice Pipeline |  **COMPLETED** | End-to-end happy path verified via `scripts/run_demo.py` |
| **Phase 2** | **Hardening, Architecture Refactor & Live Dashboard** |  **COMPLETED** | Safety guardrails, dependency-aware LangGraph state machine, two-stage matching, family consent workflow, live dashboard; 36 passed tests |
| **Phase 3** | **Ablations & Empirical Benchmarking** (E1–E6, MedAgentBench) | 🔒 *LOCKED* | Out of scope for current milestone |
| **Phase 4** | **Paper, Artifacts & Documentation** | 🔒 *LOCKED* | Out of scope for current milestone |

> **Milestone Status: Phase 2 Architecture Refactoring Completed**  
> All components of Phase 0, Phase 1, and Phase 2 (Safety Guardrails, Dashboard, and Dependency-Aware Refactoring) are implemented, fully tested, and verified end-to-end with 36/36 tests passing.


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
          | Immediate Escalation  |                    |    Parallel Fan-Out   |
          +-----------+-----------+                    +-----------+-----------+
                      |                                            |
                      v                        +-------------------+-------------------+
          +-----------------------+            |                                       |
          |  Hospital Discovery   |            v                                       v
          |  (Haversine & Beds)   |     +---------------------+                 +---------------------+
          +-----------+-----------+     | Triage Agent (LLM)  |                 | Hospital Discovery  |
                      |                 | (AIIMS/MoRTH Acuity)|                 | (Candidate Search)  |
                      |                 +----------+----------+                 +----------+----------+
                      |                            |                                       |
                      |                            +-------------------+-------------------+
                      |                                                |
                      |                                                v [Join Barrier]
                      +------------------------------------>+---------------------+
                                                            |  Hospital Matching  |
                                                            | (Acuity-Conditioned)|
                                                            +----------+----------+
                                                                       |
                                                                       v
                                                            +---------------------+
                                                            | FHIR Pre-Reg Service|
                                                            +----------+----------+
                                                                       |
                                                                       v
                                                            +---------------------+
                                                            |Family Communications|
                                                            |  (Consent-Gated)    |
                                                            +----------+----------+
                                                                       |
                                                                       v
                                                            +---------------------+
                                                            | Consolidation & END |
                                                            | (Dispatcher Review) |
                                                            +---------------------+
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

#### C. Two-Stage Hospital Matching Workflow (`src/agents/hospital.py`)
- **Role**: Geospatial search, live bed verification, acuity-conditioned matching, and FHIR pre-registration.
- **Two-Stage Architecture**:
  1. **Stage 1 (`discover_candidates`)**: Concurrently with LLM triage, queries HAPI FHIR for regional emergency facilities, calculates Haversine great-circle distances, and populates `raw_candidates`.
  2. **Stage 2 (`match_and_rank`)**: Conditioned upon validated clinical triage acuity at the LangGraph Join Barrier. Enforces trauma-level requirements and bed availability, generating an auditable `ranking_reason`.
  3. **Stage 3 (`pre_register_patient`)**: Generates and posts an atomic HL7 FHIR R4 Transaction Bundle (`Patient` + `Encounter` + `Condition`).
- **Verification**: `tests/test_hospital.py` and `tests/test_architecture_refactor.py` passed.

#### D. GOLDEN Orchestrator (`src/agents/coordinator.py`)
- **Role**: Stateful LangGraph dependency-aware workflow state machine (not an AI agent).
- **Key Mechanics**:
  - **Hard-SOS Bypass**: Instant escalation to hospital discovery and matching upon deterministic life threat detection (< 0.02ms).
  - **Dependency-Aware Parallelism**: Concurrent dispatch of Triage Agent and Hospital Discovery, followed by an explicit Join Barrier at Hospital Matching.
  - **State Segregation**: Granular node dictionary returns (`{"triage": ...}`, `{"hospital_fhir": ...}`) avoiding LangGraph `InvalidUpdateError`.
  - **Durable Checkpointing**: Powered by LangGraph's `MemorySaver`, assigning thread persistence per `case_id`.
  - **Auditable HITL Control**: `apply_dispatcher_override` persists human dispatcher decisions with timestamps and rationales into `human_overrides`.
- **Verification**: `tests/test_coordinator.py` and `tests/test_architecture_refactor.py` passed.

#### E. Family Communication Workflow & Telephony (`src/voice/`)
- **Family Communication Agent (`src/voice/family_communication.py`)**: Separate workflow checking caller consent (`consent_to_contact_nok`) before triggering telephony actions.
- **Audio Bridge (`src/voice/audio_bridge.py`)**: Real-time polyphase resampling between Exotel's 8kHz G.711/PCM telephony format and Gemini Live's 16kHz/24kHz wideband audio using NumPy and SciPy.
- **Exotel Client (`src/voice/exotel_client.py`)**: Outbound calling client featuring strict TRAI TCCCPR 2018 consent guardrails (simulation mode prevents unauthorized live calls during tests).
- **Webhook Receiver (`src/voice/webhook_receiver.py`)**: FastAPI endpoint (`/webhook/call-outcome`) that validates incoming next-of-kin medical disclosures and triggers graph resumption.
- **Verification**: `tests/test_audio_bridge.py` and `tests/test_architecture_refactor.py` passed.

---

## 🛡️ Phase 2: Hardening, Architecture Refactor & Live Dashboard (Completed)

### 1. Objective
Refactor architecture into a clean, dependency-aware LangGraph state machine with deterministic safety engines, separate workflows, auditable human-in-the-loop control, hardened guardrails, and a live dispatcher dashboard.

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

#### B. Architectural Refactoring & State Schema Extensions (`src/state/schema.py`)
- Added `raw_candidates` and `ranking_reason` to `HospitalState`.
- Added `HumanOverrideRecord` model and `human_overrides` list to `ControlState` for immutable audit trails.
- Added `NodeExecutionTiming` model and `node_timings` list to track latency across all pipeline nodes.
- Helper methods added: `record_node_start()`, `record_node_end()`, `record_human_override()`, `add_audit_entry()`.

#### C. Live Dispatcher Dashboard (`src/dashboard/`)
- **FastAPI Backend Server (`src/dashboard/server.py`)**:
  - Real-Time **Server-Sent Events (SSE)** endpoint (`/api/events`) broadcasting state changes directly to connected browsers.
  - REST endpoints for case listing, case retrieval, health checks, and preset queries.
  - **Human-in-the-Loop Override Endpoint** (`/api/cases/{case_id}/override`): Enables human dispatchers to adjust acuity or change the target hospital destination with mandatory operational notes.
  - **Local FHIR Resource Proxy** (`/api/fhir/{resource_type}/{resource_id}`): Proxies queries directly to the local HAPI FHIR server on port 8080.
- **Modern Emergency Dispatch Web Console (`src/dashboard/static/`)**:
  - Dark-mode glassmorphic console styled in Vanilla CSS, featuring glowing acuity badges, clear typography, and micro-animations.
  - Pipeline Tracker updated to reflect the 6-stage dependency-aware architecture.
  - Real-time case queue, detailed specialist inspector, live HL7 FHIR link modal, and dispatcher override dialog.

#### D. Full Repository Test Suite Verification
```bash
python -m pytest tests/ -v
================== 36 passed in 2.63s ==================
```
- Total test cases: **36 passed, 0 failed**.
- Comprehensive coverage across schema validation, deterministic Hard-SOS, LLM triage, two-stage hospital matching, dependency barriers, FHIR bundle writes, audio resampling, guardrails, dashboard endpoints, and human overrides.

---

## 📝 Change & Update Log

- **2026-09-13 (Phase 2 Architecture Refactoring Completed)**:
  - Refactored architecture from inaccurate "4-agent concurrent" claim to principled dependency-aware LangGraph state machine with deterministic engines.
  - Reclassified components: Hard-SOS (deterministic safety engine), Orchestrator (workflow state machine), Triage Agent (guideline-grounded LLM), Hospital Matching (two-stage workflow), FHIR (interoperability tool layer), Family Communication (consent-gated workflow), Human Dispatcher (override authority).
  - Implemented real dependency-aware parallelism: Triage reasoning and Hospital Discovery run concurrently; Hospital Matching executes at Join Barrier using validated clinical acuity.
  - Added `src/voice/family_communication.py` separating consent-gated family outreach from low-level telephony client.
  - Extended state schema with `raw_candidates`, `ranking_reason`, `HumanOverrideRecord`, and node timings.
  - Added architectural test suite `tests/test_architecture_refactor.py` (5 tests).
  - Full test suite passed: **36 / 36 tests passing**.
- **2026-09-10 (Capstone Phase 1 verification)**:
  - Created `CAPSTONE_EXECUTION_PLAN.md` with the complete delivery workflow, use case, phase exit criteria, evidence requirements, and presentation plan.
  - Ran `python scripts/run_demo.py` successfully: offline triage, hospital ranking, FHIR R4 pre-registration, consent-gated voice state, and webhook checkpoint resumption completed.
  - Started the dashboard and verified `/api/health` returned `ONLINE` with `fhir_connected=true`; `/api/presets` and `/api/cases` responded successfully.
  - Phase 1 is complete; Phase 2 dashboard presentation readiness is now in progress.
- **2026-09-10 (Phase 2 presentation artifact)**:
  - Added `DEMO_RUNBOOK.md` with the five-minute use-case narrative, exact startup commands, expected outputs, panel questions, limitations, and terminal fallback demo.
  - Focused dashboard/coordinator verification passed: **6 passed**.
- **2026-09-07 (Phase 0 & Phase 1)**:
  - Repository initialized with 5-section `GoldenCaseState` Pydantic model.
  - HAPI FHIR JPA server running on Docker; Synthea synthetic data seeded.
  - Hard-SOS engine (<0.02ms), AIIMS/MoRTH Triage Agent, Hospital Matcher with FHIR R4 Bundle generator, LangGraph Coordinator, and Voice Audio Bridge implemented.
  - All 17 automated tests passed.
- **2026-09-07 (Phase 2 Items 1 & 2 — 50% Milestone Reached)**:
  - Implemented `PIISanitizer`, `PromptInjectionDetector`, `ClinicalSafetyValidator`, and `InterAgentContractGuard` in `src/safety/guardrails.py`.
  - Built FastAPI dashboard server with real-time SSE stream, HITL overrides, and FHIR resource proxy in `src/dashboard/server.py`.
  - Built modern dark-theme dispatcher interface (`index.html`, `app.css`, `app.js`).

