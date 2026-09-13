# GOLDEN Capstone Demo Runbook

**Target duration:** 5 minutes  
**Audience:** Capstone panel, evaluator, or technical reviewer  
**Mode:** Local Docker HAPI FHIR + offline triage + simulated/consent-gated voice

---

## 1. One-Minute Explanation

> GOLDEN is an emergency dispatch decision-support system. It takes an incident report, detects immediate life threats, classifies acuity, finds a suitable nearby hospital, pre-registers the patient through HL7 FHIR, and collects additional family history through a consent-gated voice workflow. The dispatcher remains in control throughout the process.

Emphasize that the system is a prototype using synthetic data and local infrastructure. It supports dispatch decisions; it does not replace clinicians or emergency policy.

---

## 2. Start the Environment

From the repository root:

```powershell
docker compose up -d
Invoke-RestMethod http://localhost:8080/fhir/metadata
python scripts/seed_synthea.py
python -m pytest -q
```

Expected evidence:

- HAPI container is running on port `8080`.
- FHIR metadata returns `CapabilityStatement`.
- The seed creates 3 organizations and 4 synthetic patients.
- The full suite reports 36 passed tests.

Start the dashboard in a second terminal:

```powershell
python -m uvicorn src.dashboard.server:app --host 127.0.0.1 --port 8000
```

Verify:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
```

Expected result includes:

```text
status=ONLINE
fhir_connected=true
```

Open `http://127.0.0.1:8000` in the browser.

---

## 3. Primary Live Scenario

Use the dashboard’s incident simulation control and choose the severe road-accident preset (*Tambaram Flyover Polytrauma*).

Narrate the workflow in this order:

1. **Incident ingestion:** The dispatcher receives a road-accident narrative and location.
2. **Hard-SOS check:** The deterministic safety engine checks for immediate life threats in < 0.02ms before any LLM call.
3. **Parallel Discovery & Triage:**
   - The Triage Agent reasons over clinical acuity (AIIMS / MoRTH 2025). With blank API keys, the offline heuristic fallback is used and clearly identified.
   - Concurrently, Stage 1 Hospital Discovery queries HAPI FHIR and calculates Haversine distances to populate candidate facilities.
4. **Acuity-Conditioned Matching:** At the LangGraph Join Barrier, Stage 2 Hospital Matching scores and ranks hospitals based on the validated clinical acuity, generating an auditable `ranking_reason`.
5. **FHIR pre-registration:** The system creates `Patient`, `Encounter`, and `Condition` resources in one atomic transaction bundle.
6. **Voice workflow:** The Family Communication Agent verifies consent before triggering outbound calls. The call is simulated only for consented test numbers; an unauthorized number produces `CONSENT_REFUSED`.
7. **Human-in-the-Loop Override:** The dispatcher exercises override authority to adjust acuity or hospital destination, generating an immutable audit trail entry in `human_overrides`.

Expected primary evidence:

- Triage status: `RED` for a life-threat scenario or `YELLOW` for the standard trauma preset.
- Hospital bed status: `CONFIRMED` when HAPI is available.
- Ranking reason: Clear explanation why the selected facility was chosen.
- FHIR submission: `SUCCESS`.
- Voice state: `TRIGGERED`, `IDLE`, or `CONSENT_REFUSED` depending on caller consent and configured test numbers.
- Human override: Timestamped log with dispatcher rationale.

---

## 4. Terminal Backup Demonstration

If the browser is unavailable, run:

```powershell
python scripts/run_demo.py
```

The terminal should show:

- Case ingestion
- Hard-SOS decision
- Parallel Triage & Hospital Discovery
- Acuity-conditioned Hospital Matching with `ranking_reason`
- FHIR transaction bundle submission
- Voice consent check
- Simulated webhook resumption
- Final `COMPLETED` state with family history

This is the preferred backup because it exercises the exact same LangGraph orchestrator and FHIR path without relying on browser state.

---

## 5. Panel Questions and Answers

### What problem does GOLDEN solve?

Emergency dispatchers must triage the incident, identify a hospital, reserve resources, register the patient, and contact family with limited information. GOLDEN coordinates these activities through one auditable state workflow.

### Why is the Coordinator an orchestrator instead of an AI agent?

Safety-critical emergency dispatch requires deterministic state transitions, auditable join barriers, and guaranteed error recovery. An LLM coordinator introduces non-deterministic edge traversal and latency. Confining LLM usage to clinical triage gives us semantic reasoning where needed, while keeping orchestration strictly deterministic.

### Why is Hospital Matching split into two stages?

Hospital destination selection depends on clinical acuity (a RED trauma case needs a Level-1 trauma center and ICU beds, while a GREEN case should go to a community clinic to avoid overcrowding). Therefore, Stage 1 (spatial discovery & Haversine distance) runs concurrently with triage, but Stage 2 (matching and ranking) waits at a LangGraph Join Barrier until validated triage acuity is known.

### Why use a deterministic Hard-SOS path?

Immediate life threats should not wait for an LLM response. The rule engine provides a fast (< 0.02ms), explainable bypass and is intentionally biased toward escalation.

### Why FHIR?

FHIR provides a standardized healthcare data contract. The prototype proves that the workflow can create interoperable `Patient`, `Encounter`, and `Condition` records compliant with India's Ayushman Bharat Digital Mission (ABDM).

### Is the patient data real?

No. All local hospital and patient records are synthetic and generated for demonstration and testing.

### What happens without an API key?

The system uses a deterministic offline triage fallback based on AIIMS/MoRTH guidelines. This keeps the demo reproducible and makes the provider dependency explicit.

### Can it place real calls?

Not by default. Exotel is simulation-only unless configured, and the consent register blocks unauthorized numbers.

### What are the limitations?

Hospital capacity is modeled synthetic data, HAPI is local infrastructure, the LLM fallback is keyword-based, and the system is decision support rather than autonomous clinical care.

---

## 6. Evidence Checklist

Before presenting, confirm:

- [ ] Docker container is running.
- [ ] `/fhir/metadata` returns `CapabilityStatement`.
- [ ] Seed command completed.
- [ ] `python -m pytest -q` passes (36 tests).
- [ ] Dashboard `/api/health` reports `ONLINE` and `fhir_connected=true`.
- [ ] One case can be dispatched from the dashboard.
- [ ] FHIR resource IDs and ranking reasons are visible for the dispatched case.
- [ ] Terminal backup demo is available.
- [ ] The presenter can explain synthetic data, offline fallback, two-stage hospital matching, consent safety, and human oversight.

