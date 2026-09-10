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
- The full suite reports 35 passed tests.

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

Use the dashboard’s incident simulation control and choose the severe road-accident preset.

Narrate the workflow in this order:

1. **Incident ingestion:** The dispatcher receives a road-accident narrative and location.
2. **Hard-SOS check:** The deterministic safety engine checks for immediate life threats before any LLM call.
3. **Triage:** The case receives an acuity level and a guideline reference. With blank API keys, the local offline keyword fallback is used and clearly identified.
4. **Hospital matching:** The system queries HAPI FHIR, ranks hospitals by distance and capability, and selects the best candidate.
5. **FHIR pre-registration:** The system creates `Patient`, `Encounter`, and `Condition` resources in one transaction bundle.
6. **Voice workflow:** The call is simulated only for consented test numbers. An unauthorized number produces `CONSENT_REFUSED`, demonstrating the safety guardrail.
7. **Dashboard evidence:** The case card shows the acuity, selected hospital, FHIR IDs, voice state, and audit trail.

Expected primary evidence:

- Triage status: `RED` for a life-threat scenario or `YELLOW` for the standard trauma preset.
- Hospital bed status: `CONFIRMED` when HAPI is available.
- FHIR submission: `SUCCESS`.
- Voice state: `TRIGGERED`, `IDLE`, or `CONSENT_REFUSED` depending on the configured test number.

---

## 4. Terminal Backup Demonstration

If the browser is unavailable, run:

```powershell
python scripts/run_demo.py
```

The terminal should show:

- Case ingestion
- Hard-SOS decision
- Triage output
- Hospital candidate ranking
- FHIR bundle submission
- Voice consent result
- Simulated webhook resumption
- Final `COMPLETED` state with family history

This is the preferred backup because it exercises the same coordinator and FHIR path without relying on browser state.

---

## 5. Panel Questions and Answers

### What problem does GOLDEN solve?

Emergency dispatchers must triage the incident, identify a hospital, reserve resources, register the patient, and contact family with limited information. GOLDEN coordinates these activities through one auditable state workflow.

### Why use a deterministic Hard-SOS path?

Immediate life threats should not wait for an LLM response. The rule engine provides a fast, explainable bypass and is intentionally biased toward escalation.

### Why FHIR?

FHIR provides a standardized healthcare data contract. The prototype proves that the workflow can create interoperable `Patient`, `Encounter`, and `Condition` records instead of storing only application-specific JSON.

### Is the patient data real?

No. All local hospital and patient records are synthetic and generated for demonstration and testing.

### What happens without an API key?

The system uses a deterministic offline triage fallback. This keeps the demo reproducible and makes the provider dependency explicit.

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
- [ ] `python -m pytest -q` passes.
- [ ] Dashboard `/api/health` reports `ONLINE` and `fhir_connected=true`.
- [ ] One case can be dispatched from the dashboard.
- [ ] FHIR resource IDs are visible for the dispatched case.
- [ ] Terminal backup demo is available.
- [ ] The presenter can explain synthetic data, offline fallback, consent safety, and human oversight.
