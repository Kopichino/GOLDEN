# GOLDEN: Guideline-Grounded Orchestrated LLM Dispatch for Emergency Networks

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![LangGraph](https://img.shields.io/badge/orchestrator-LangGraph-orange.svg)](https://github.com/langchain-ai/langgraph)
[![HL7 FHIR](https://img.shields.io/badge/standard-HL7%20FHIR%20R4-firebrick.svg)](https://hl7.org/fhir/R4/)
[![Tests](https://img.shields.io/badge/tests-31%2F31%20passing-brightgreen.svg)](tests/)
[![Milestone](https://img.shields.io/badge/milestone-50%25%20completed-purple.svg)](PROGRESS.md)
[![ABDM Aligned](https://img.shields.io/badge/ABDM-FHIR%20Compliant-teal.svg)](https://abdm.gov.in/)

> **An India-grounded multi-agent AI decision-support system for pre-hospital emergency response (108/112 services).**  
> Instead of a human dispatcher handling triage, hospital bed queries, patient pre-registration, and family notifications serially on the phone, **GOLDEN** parallelizes these workflows across specialized, guideline-grounded AI agents while keeping the human dispatcher firmly in control.

---

## 📑 Table of Contents
- [1. Motivation & Problem Statement](#1-motivation--problem-statement)
- [2. System Architecture](#2-system-architecture)
- [3. Agent Roster & Core Capabilities](#3-agent-roster--core-capabilities)
- [4. Project Scope & Phase Roadmap](#4-project-scope--phase-roadmap)
- [5. Repository Structure](#5-repository-structure)
- [6. Prerequisites & Environment Setup](#6-prerequisites--environment-setup)
- [7. Step-by-Step Running Guide](#7-step-by-step-running-guide)
- [8. Testing & Verification](#8-testing--verification)
- [9. Ethics, Safety & Regulatory Compliance](#9-ethics-safety--regulatory-compliance)
- [10. References & Further Documentation](#10-references--further-documentation)

---

## 1. Motivation & Problem Statement

In India, over **150,000 traffic fatalities** occur annually. A significant proportion of deaths occur because the critical **"Golden Hour"** (the first 60 minutes after severe trauma) is lost due to communication bottlenecks:

```
TRADITIONAL PRE-HOSPITAL BOTTLENECK (SERIAL):
Emergency Call ──> Triage on Phone ──> Call Hospitals for Beds ──> Dispatch Ambulance ──> Hospital Bay (No Pre-Registration)
[0 - 5 mins]       [5 - 10 mins]      [10 - 20 mins]            [20 - 45 mins]         [Zero pre-hospital medical history]

GOLDEN PRE-HOSPITAL RESPONSE (PARALLEL MULTI-AGENT):
Emergency Call ──┬──> Hard-SOS Rule Engine (<0.02ms bypass) ───────────────┐
                 ├──> Guideline-Grounded Triage Agent (AIIMS / MoRTH 2025) ┼──> Coordinator ──> Instant Ambulance Dispatch
                 ├──> Hospital Matching & Bed Allocation (Haversine + FHIR)│
                 └──> Outbound Family Telephony (Allergy & Medical History)┘
[0 - 10 seconds total orchestrator decision support]
```

### Key Design Principles:
1. **Decision Support, Not Autonomous Dispatch**: GOLDEN is explicitly designed as a real-time advisory layer for human 108/112 controllers with comprehensive **Human-in-the-Loop (HITL) override controls**.
2. **Clinical Grounding**: Built upon official Indian medical protocols:
   - **AIIMS Emergency Department Triage Protocol**
   - **Ministry of Road Transport and Highways (MoRTH) Golden Hour Care SOP 2025**
3. **National Standards Alignment**: Compliant with India's **Ayushman Bharat Digital Mission (ABDM)** using HL7 FHIR R4.

---

## 2. System Architecture

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

---

## 3. Agent Roster & Core Capabilities

### 1. Hard-SOS Rule Engine (`src/agents/hard_sos.py`)
- **Execution Time**: `< 0.02 milliseconds` (< 20 microseconds).
- **Function**: Scans raw incident reports for non-negotiable life threats (`unresponsive`, `not breathing`, `cardiac arrest`, `massive hemorrhage`, `arterial bleeding`, `crushed under`, `amputation`).
- **Asymmetric Safety**: Deliberately biased towards false positives to guarantee zero life-threat false negatives. Completely offline with zero LLM dependency.

### 2. Clinical Triage Agent (`src/agents/triage.py`)
- **Clinical Protocols**: AIIMS Emergency Triage Protocol & MoRTH Golden Hour SOP 2025.
- **Categorical Acuity Levels**: `RED` (Immediate), `YELLOW` (Urgent), `GREEN` (Non-urgent), `BLACK` (Expectant).
- **Multi-Provider Fallback Matrix**: Google Gemini 3.6 Flash (Primary) $\rightarrow$ Groq Qwen 3.6 27B $\rightarrow$ OpenRouter $\rightarrow$ Local Ollama (`qwen2.5:7b`).
- **Schema Contracts**: Strict Pydantic v2 validation with an automatic self-healing retry loop.

### 3. Hospital & Bed Matching Agent (`src/agents/hospital.py`)
- **Geospatial Ranking**: Uses the mathematical **Haversine Great-Circle Formula** to calculate physical distance from the incident coordinates to candidate facilities in `< 0.05ms`.
- **Composite Scoring Formula**:
  $$Score = \frac{100}{1 + Distance} + (Available\_ICU\_Beds \times 2.0) + (Available\_ER\_Beds \times 0.5) + Trauma\_Level\_Bonus$$
- **Pre-Registration Sink**: Builds and posts an atomic **HL7 FHIR R4 Transaction Bundle** to the local HAPI FHIR server, pre-admitting the patient (`Patient` + `Encounter` + `Condition`) before the ambulance reaches the hospital bay.

### 4. Voice Telephony Subsystem (`src/voice/`)
- **Audio Bridge (`audio_bridge.py`)**: Real-time polyphase resampling between Exotel's telephony audio (8kHz G.711 PCM) and conversational wideband LLM audio (16kHz/24kHz) using NumPy and SciPy.
- **Exotel Client (`exotel_client.py`)**: Outbound calling client with TRAI TCCCPR 2018 consent guardrails.
- **Webhook Receiver (`webhook_receiver.py`)**: FastAPI webhook endpoint resuming the LangGraph checkpoint when next-of-kin allergy data is collected.

### 5. Guardrail & Safety Validation Layer (`src/safety/guardrails.py`)
- **`PIISanitizer`**: Auto-redacts 12-digit Indian Aadhaar numbers, 10-digit mobile numbers, and PAN cards into safe replacement tokens (`[AADHAAR-REDACTED]`, `[PHONE-REDACTED]`).
- **`PromptInjectionDetector`**: Detects and neutralizes adversarial instruction hijacking attempts (`ignore previous instructions`, `prescribe narcotics`).
- **`ClinicalSafetyValidator`**: Forbids downgrading high-impact trauma cases to `GREEN` and mandates verified protocol citations.
- **`InterAgentContractGuard`**: Enforces schema contracts across LangGraph boundaries and applies emergency fail-safe states if an LLM response is malformed.

### 6. Live Dispatcher Dashboard (`src/dashboard/`)
- Real-time **Server-Sent Events (SSE)** streaming live state transitions from the coordinator to the browser.
- Dark-theme glassmorphic console with incident feed, deep case inspector, live HL7 FHIR resource viewer, and **Human-in-the-Loop override controls**.

---

## 4. Project Scope & Phase Roadmap

| Phase | Milestone Scope | Status | Deliverables & Artifacts |
| :--- | :--- | :---: | :--- |
| **Phase 0** | **Foundations** |  **COMPLETED** | 5-section state schema (`schema.py`), local HAPI FHIR Docker, Synthea synthetic corridor data, architecture doc. |
| **Phase 1** | **Core Agents & Happy Path** |  **COMPLETED** | Hard-SOS engine, Triage Agent, Hospital Matcher, LangGraph Coordinator, Audio Bridge, CLI demo script (`run_demo.py`). |
| **Phase 2** | **Hardening & Live Dashboard** |  **COMPLETED** | Safety guardrails (`guardrails.py`), FastAPI dashboard server, modern web console (`index.html`), 35 passing tests. |
| **Phase 2.3**| **Voice STT & Circuit Breaker** | ⏳ *Next Step* | Code-mixed Tamil-English Whisper STT & local Ollama circuit-breaker fallback. |
| **Phase 3** | **Empirical Evaluation** | 🔒 *Planned* | Controlled ablations (E1–E6) and MedAgentBench triage evaluation. |
| **Phase 4** | **Documentation & Publication**| 🔒 *Planned* | Capstone project report, paper draft, and presentation artifacts. |

---

## 5. Repository Structure

```
d:/College/SEM7/AD/
├── .env.example                  # Environment configuration template
├── ARCHITECTURE.md               # Frozen 1-page architecture reference
├── PROGRESS.md                   # Chronological project progress tracker
├── SYSTEM_EXPLANATION.md         # Comprehensive deep-dive & viva defense guide
├── README.md                     # Main repository guide
├── docker-compose.yml            # Local HAPI FHIR JPA server (port 8080)
├── requirements.txt              # Production Python dependencies
├── scripts/
│   ├── seed_synthea.py           # Seeds synthetic emergency hospitals into HAPI FHIR
│   ├── run_demo.py               # End-to-end command-line emergency simulation
│   └── test_providers.py         # Multi-provider LLM smoke test script
├── src/
│   ├── config.py                 # Pydantic BaseSettings for keys and endpoints
│   ├── state/
│   │   └── schema.py             # Complete 5-section Pydantic v2 GoldenCaseState
│   ├── agents/
│   │   ├── hard_sos.py           # Sub-second deterministic pattern matcher (<0.02ms)
│   │   ├── triage.py             # AIIMS/MoRTH guideline-grounded triage agent
│   │   ├── hospital.py           # Haversine distance, bed queries, and pre-registration
│   │   └── coordinator.py        # LangGraph cyclic state machine with MemorySaver
│   ├── fhir/
│   │   ├── client.py             # REST client for local HAPI FHIR server
│   │   └── bundle_builder.py     # HL7 FHIR R4 Transaction Bundle generator
│   ├── voice/
│   │   ├── audio_bridge.py       # 8kHz <-> 16kHz/24kHz polyphase audio resampler
│   │   ├── exotel_client.py      # Telephony client with TRAI consent guardrails
│   │   └── webhook_receiver.py   # Webhook endpoint for call completion
│   ├── safety/
│   │   └── guardrails.py         # PII sanitizer, injection detector, clinical validator
│   └── dashboard/
│       ├── server.py             # FastAPI backend with SSE streaming & HITL overrides
│       └── static/
│           ├── index.html        # Modern emergency dispatcher console
│           ├── app.css           # High-contrast dark-mode glassmorphic styling
│           └── app.js            # Real-time SSE subscriber & interactive controller
└── tests/
    ├── test_state_schema.py      # Pydantic v2 schema serialization & boundary tests
    ├── test_hard_sos.py          # Asymmetric cost & <0.02ms benchmark tests
    ├── test_triage.py            # AIIMS/MoRTH classification & retry loop tests
    ├── test_hospital.py          # Haversine distance & bed ranking tests
    ├── test_coordinator.py       # Hard-SOS bypass & parallel fan-out tests
    ├── test_fhir_integration.py  # HAPI FHIR connection & Transaction Bundle tests
    ├── test_audio_bridge.py      # Telephony polyphase resampling tests
    ├── test_guardrails.py        # PII masking & clinical downgrade protection tests
    └── test_dashboard.py         # FastAPI endpoints & HITL override tests
```

---

## 6. Prerequisites & Environment Setup

### 1. System Requirements
- **Operating System**: Windows 10/11, macOS, or Linux.
- **Python**: Version **3.12** (installed via Anaconda or Python standalone).
- **Docker Desktop**: Required to run the local HAPI FHIR R4 server.
- **RAM**: Minimum 8 GB (HAPI FHIR container uses ~1.5 GB heap).

### 2. API Keys Needed (Free Tiers Supported)
- **Google Gemini**: `GEMINI_API_KEY` (Free tier on Google AI Studio for Gemini 3.6 Flash).
- **Groq**: `GROQ_API_KEY` (Free tier for Qwen 3.6 27B / Llama models).
- **OpenRouter** *(Optional)*: `OPENROUTER_API_KEY` for fallback models.
- **Exotel** *(Optional)*: Account SID, Key, Token for live telephony (simulation mode runs without keys).
- **Ollama** *(Optional)*: Local offline models (`ollama run qwen2.5:7b`).

---

## 7. Step-by-Step Running Guide

### Step 1: Clone Repository & Set Up Environment
Open PowerShell or your terminal in the project directory:
```powershell
# If using Anaconda (Recommended):
conda activate base

# If using standard venv:
python -m venv .venv
.venv\Scripts\activate

# Install dependencies:
pip install -r requirements.txt
```

### Step 2: Configure Environment Variables
Copy `.env.example` to `.env` and insert your API keys:
```powershell
copy .env.example .env
```
Edit `.env` and set:
```ini
FHIR_BASE_URL=http://localhost:8080/fhir
GEMINI_API_KEY=your_gemini_api_key_here
GROQ_API_KEY=your_groq_api_key_here
DEFAULT_LLM_PROVIDER=gemini
HARD_SOS_BYPASS_ENABLED=True
```

### Step 3: Start the Local HAPI FHIR Server
Make sure Docker Desktop is running, then start the container:
```powershell
docker compose up -d
```
Verify the FHIR server is running by visiting:  
👉 **[http://localhost:8080/fhir/metadata](http://localhost:8080/fhir/metadata)** (Should return FHIR CapabilityStatement JSON).

### Step 4: Seed Synthetic Emergency Corridor Data
Populate the local FHIR server with emergency hospitals and synthetic trauma patient profiles along the Chennai South corridor:
```powershell
python scripts/seed_synthea.py
```

### Recommended Capstone Verification Flow

Run this sequence for a repeatable local demonstration:

```powershell
docker compose up -d
python scripts/seed_synthea.py
python -m pytest -q
python scripts/run_demo.py
python -m uvicorn src.dashboard.server:app --host 127.0.0.1 --port 8000
```

Then verify `http://127.0.0.1:8000/api/health` reports `ONLINE` and
`fhir_connected=true`. The complete capstone workflow and presentation phases
are tracked in [CAPSTONE_EXECUTION_PLAN.md](CAPSTONE_EXECUTION_PLAN.md).

For the panel presentation sequence and backup terminal demo, use
[DEMO_RUNBOOK.md](DEMO_RUNBOOK.md).

### Step 5: Start the Live Dispatcher Dashboard
Start the FastAPI server on port 8000:
```powershell
python -m uvicorn src.dashboard.server:app --port 8000 --reload
```

### Step 6: Test Live Emergency Dispatch in Browser
1. Open your browser and navigate to: **[http://localhost:8000](http://localhost:8000)**.
2. Ensure the top status indicator displays **HAPI FHIR R4: Online (Port 8080)**.
3. Click **"Simulate Incident"** at top right.
4. Select the preset **Tambaram Flyover Polytrauma** and click **"Dispatch Incident"**.
5. Observe the live multi-agent execution:
   - Acuity classified as **RED** under MoRTH 2025 guidelines.
   - Hospital Agent calculates distance and selects **Government Hospital Chromepet** (3.0 km away, 6 ICU beds).
   - Atomic pre-registration links generated for `Patient/`, `Encounter/`, and `Condition/`.
6. Click **"Simulate Caller Webhook Callback"** to simulate next-of-kin telephone contact: watch patient allergy tags (`Ciprofloxacin`, `Shellfish`, `Metformin`) render in real-time.
7. Click **"Dispatcher Override"** to test human-in-the-loop control.

---

## 8. Testing & Verification

### Run the Full Automated Test Suite (35 Tests)
Execute pytest to run all unit, security, integration, and performance tests:
```powershell
python -m pytest tests/ -v
```
**Expected Outcome**:
```
================== 35 passed, 4 warnings in 13.24s ==================
```

### Run the Command-Line End-to-End Demo
To see colorized execution logs directly in your terminal without a browser:
```powershell
python scripts/run_demo.py
```

---

## 9. Ethics, Safety & Regulatory Compliance

1. **Digital Personal Data Protection (DPDP) Act 2023**:
   - Zero real patient records are accessed or stored. All clinical records, hospital capabilities, and injury mechanisms are 100% synthetic (Synthea-generated).
   - Automated PII sanitizer redacts Indian Aadhaar, phone, and PAN numbers at the gateway.
2. **TRAI TCCCPR 2018 Compliance**:
   - Unsolicited robocalling is strictly prevented via a built-in `SIMULATION_MODE` guardrail. Outbound telephony operates in mock sandbox mode during evaluation.
3. **Clinical Safety Safeguards**:
   - The **Clinical Safety Validator** enforces hard boundaries preventing the LLM from downgrading severe trauma symptoms to `GREEN`.
   - The system is explicitly configured as a **decision-support copilot for human dispatchers**, preserving human agency for every ambulance dispatch.

---

## 10. References & Further Documentation

- Detailed System Guide & Capstone Viva Notes: [SYSTEM_EXPLANATION.md](SYSTEM_EXPLANATION.md)
- Chronological Development Tracker: [PROGRESS.md](PROGRESS.md)
- Frozen Architecture Blueprint: [ARCHITECTURE.md](ARCHITECTURE.md)
- Clinical Guidelines:
  - *AIIMS Emergency Department Triage Protocol (ED-TP)*
  - *Ministry of Road Transport and Highways (MoRTH) Golden Hour Care SOP 2025*
- Standards:
  - *HL7 FHIR R4 Specification*: [https://hl7.org/fhir/R4/](https://hl7.org/fhir/R4/)
  - *Ayushman Bharat Digital Mission (ABDM)*: [https://abdm.gov.in/](https://abdm.gov.in/)

---

*GOLDEN is an academic capstone project developed for advanced emergency medical informatics.*
