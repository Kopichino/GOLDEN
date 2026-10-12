# GOLDEN Capstone Demo Runbook

**Target duration:** 5 minutes  
**Audience:** Capstone panel, evaluator, or technical reviewer  
**Mode:** Local Docker HAPI FHIR + offline triage + consent-gated Exotel/Gemini voice

---

## 0. Pre-flight: what must be running

| Process | Command | Port | Needed for |
| --- | --- | --- | --- |
| HAPI FHIR | `docker compose up -d` | 8080 | Hospital discovery, `Patient`/`Encounter`/`Condition` pre-registration |
| CAD dashboard | `python -m uvicorn src.dashboard.server:app --host 0.0.0.0 --port 8000` | 8000 | Dispatcher UI, Driver Companion, `/webhook/call-outcome`, SSE |
| Voice bridge | `python -m src.voice.voice_server` | 8765 | Exotel ↔ Gemini Live audio bridge (live calls only) |
| Public stream tunnel | `ngrok websocket 8765` | — | `EXOTEL_STREAM_URL` that Exotel can dial into |
| Public callback tunnel | `cloudflared tunnel --url http://localhost:8000` | — | `VOICE_CALLBACK_URL` that Exotel can post back to |

Use the project virtualenv (`.venv/Scripts/python.exe` on Windows) for everything, including
`scripts/seed_synthea.py` and the QR flow: the system Python has no `qrcode` package, so the
callout ticket renders an empty QR instead of failing loudly.

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
python -m pytest tests/test_voice_integration.py tests/test_audio_bridge.py -q
```

Expected evidence:

- HAPI container is running on port `8080`.
- FHIR metadata returns `CapabilityStatement`.
- The seed creates 3 organizations and 4 synthetic patients.
- The focused voice suite passes. The full suite collects 99 tests; `tests/test_fhir_integration.py`
  needs a live HAPI server, so 3 of them fail while Docker is stopped — start Docker before claiming
  `python -m pytest -q` is green.

Start the dashboard in a second terminal:

```powershell
python -m uvicorn src.dashboard.server:app --host 0.0.0.0 --port 8000
```

Bind to `0.0.0.0`, not `127.0.0.1`: the callout-ticket QR encodes the machine's LAN
address, so a phone on the same Wi-Fi can only open the Driver Companion if the
dashboard accepts non-loopback connections.

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

## 3. Guided Tour and Navigation

The dashboard opens a 9-step spotlight tour on first visit (queue → triage → hospital ranking → FHIR
slip → corridor map → voice card → driver companion → overrides → analytics). It is stored in
`localStorage` key `golden_tour_completed_v1`, so it does not repeat for the panel. To show it again:

```javascript
// Browser console
localStorage.removeItem("golden_tour_completed_v1"); location.reload();
// or, without a reload:
GoldenTour.start();
```

Talking points per panel: the left queue is the case list, the centre is the decision canvas
(triage + ranking + FHIR), the right rail is the specialist cards (voice, dispatch, audit).

---

## 4. Driver Companion and QR Handoff

After dispatch, the case exposes a 108 callout ticket and a QR code.

- Scan with a phone camera, or open the printed `mobile_companion_url` (`/driver/<CALLOUT-ID>`) directly.
- The page is responsive: a single-column phone layout below 900px, and a two-column desktop layout
  at 900px and above (mission card + live map beside it), so the same URL works on the vehicle
  tablet and on the presenter's laptop.
- The crew can acknowledge rollout, on-scene arrival, and patient handover; each acknowledgement
  broadcasts to the dispatcher over SSE.

Smoke test before the panel (from the machine hosting the dashboard):

```powershell
curl.exe -s -o NUL -w "%{http_code}" http://<LAN-IP>:8000/api/health
```

Any non-`200` means the phone will not resolve the QR address — usually uvicorn is bound to
loopback, or the phone is on a different SSID / VLAN.

---

## 5. Primary Live Scenario

Use the dashboard’s incident simulation control and choose the severe road-accident preset (*Tambaram Flyover Polytrauma*).

Narrate the workflow in this order:

1. **Incident ingestion:** The dispatcher receives a road-accident narrative and location.
2. **Hard-SOS check:** The deterministic safety engine checks for immediate life threats in < 0.02ms before any LLM call.
3. **Parallel Discovery & Triage:**
   - The Triage Agent reasons over clinical acuity (AIIMS / MoRTH 2025). With blank API keys, the offline heuristic fallback is used and clearly identified.
   - Concurrently, Stage 1 Hospital Discovery queries HAPI FHIR and calculates Haversine distances to populate candidate facilities.
4. **Acuity-Conditioned Matching:** At the LangGraph Join Barrier, Stage 2 Hospital Matching scores and ranks hospitals based on the validated clinical acuity, generating an auditable `ranking_reason`.
5. **FHIR pre-registration:** The system creates `Patient`, `Encounter`, and `Condition` resources in one atomic transaction bundle.
6. **Voice workflow:** The Family Communication Agent verifies the allowlist, triggers Exotel, and pauses while the separate GOLDEN voice server bridges Exotel audio to Gemini Live. The completed call posts a signed result callback.
7. **Human-in-the-Loop Override:** The dispatcher exercises override authority to adjust acuity or hospital destination, generating an immutable audit trail entry in `human_overrides`.

Expected primary evidence:

- Triage status: `RED` for a life-threat scenario or `YELLOW` for the standard trauma preset.
- Hospital bed status: `CONFIRMED` when HAPI is available.
- Ranking reason: Clear explanation why the selected facility was chosen.
- FHIR submission: `SUCCESS`.
- Voice state: `TRIGGERED`, `IDLE`, or `CONSENT_REFUSED` depending on simulation/live configuration and consent.
- Human override: Timestamped log with dispatcher rationale.

---

## 6. Live Exotel + Gemini Voice Call (optional, real dial-out)

Required `.env` values — all four must be mutually consistent or the call connects and then
reports no result:

```text
VOICE_SIMULATION_ONLY = false
EXOTEL_STREAM_URL     = wss://<ngrok-host>/ws        # -> voice_server on :8765
VOICE_CALLBACK_URL    = https://<cloudflared-host>/webhook/call-outcome   # -> dashboard on :8000
VOICE_CALLBACK_SECRET = <shared HMAC secret>
```

Order of operations:

1. Start the dashboard and the voice server first, so both listeners exist before the tunnels route traffic.
2. Start the tunnels and copy the **live** hostnames into `.env`. Ephemeral hosts change on every
   restart, and a stale quick-tunnel hostname goes silent (NXDOMAIN) while the old `cloudflared`
   process is still running — always re-verify:
   ```powershell
   Resolve-DnsName <cloudflared-host>
   ```
3. Restart both Python processes; each reads `.env` only at startup.
4. Check the tunnel endpoints before dialing: the stream URL host must answer on plain HTTP with a
   WebSocket-rejection status (not a 502 — a 502 means the voice server is not running).
5. Dial: `EXOTEL_CALLER_ID` must be a number verified on the Exotel account (trial accounts also pin
   the destination; `VOICE_TEST_RECIPIENT_PHONE` overrides it for demos). Add the answering phone to
   `TEAM_CONSENT_PHONE_NUMBERS` or the agent will refuse outreach on consent grounds.

Call outcome handling:

- Media-stream legs have **no REST terminate**; the call drops when the app closes its WebSocket, so
  hang up on the family handset and expect the callback a moment later.
- `EXOTEL_RECORD_CALLS=false` by default: no audio is stored. The evidence is the structured
  history (allergies, medications, blood group, pre-existing conditions, summary) plus the full turn
  transcript, written to `logs/voice/<CASE-ID>_<call-id>_<timestamp>.log`.
- The voice card shows every collected turn, and the summary/conditions land at the end of the call,
  so scroll the transcript rather than assuming the call was cut short.
- If FHIR is down, the card shows `FHIR UPDATE FAILED` while the case data itself is still complete —
  the callback resumed the graph; only the record write failed.

---

## 7. Terminal Backup Demonstration

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

### Voice Process Boundary and Direct Callback Test

The dashboard process hosts the coordinator and `/webhook/call-outcome`; the
separate `src.voice.voice_server` process hosts the Exotel WebSocket bridge.
Both processes use only GOLDEN environment variables.

Start the bridge in another PowerShell terminal:

```powershell
python -m src.voice.voice_server
```

After a case is awaiting the callback, a local client can send a structured
callback from another PowerShell terminal:

```powershell
$payload = @{
   thread_id = "thread-GOLDEN-..."
   case_id = "GOLDEN-..."
   call_id = "CALL-SIM-..."
   call_status = "COMPLETED"
   consent_granted = $true
   allergies = @("Penicillin")
   medications = @("Metformin")
   pre_existing_conditions = @("Diabetes")
   call_summary = "Family member confirmed the reported history."
   call_duration_seconds = 42
} | ConvertTo-Json

Invoke-RestMethod `
   -Uri http://127.0.0.1:8000/webhook/call-outcome `
   -Method Post `
   -ContentType "application/json" `
   -Body $payload
```

Replace the placeholder IDs with the `case_id` and `thread_id` returned by the
dashboard's incident request. When `VOICE_CALLBACK_SECRET` is configured, the
client must also generate the documented signature, timestamp, and nonce
headers. The dashboard's built-in simulated callback is simpler for the panel
demo and does not require those headers in local mode.

---

## 8. Latency Evidence (offline, reproducible, no phone needed)

```powershell
python scripts/voice_latency_harness.py --mode stub --trials 15 --out data/latency_results/run.json
```

`data/caller_utterance_8k.pcm` is the fixed inbound utterance, and the committed
`data/latency_results/after_fix_*.json` files are the measured baselines (stub, stub with transcript
I/O, and live-bridge). Quote those files rather than re-measuring during the panel; `--mode live`
requires credentials and a real Gemini quota and is not part of the demo path.

---

## 9. Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| QR scans, phone shows "site can't be reached" | uvicorn bound to `127.0.0.1`, or the `companion_url` says `http://` while the tunnel serves `https` | Run with `--host 0.0.0.0`; the URL is built from the request's host and scheme, so access the dashboard through the tunnel before printing |
| Call connects, agent speaks, no data in the dashboard | Callback host in `.env` is a dead tunnel | Re-verify with `Resolve-DnsName`, update `VOICE_CALLBACK_URL`, restart the dashboard |
| `/ws` returns 502 through ngrok | Voice server not running | `python -m src.voice.voice_server` |
| Exotel rejects the call | Caller ID or destination not verified on the account | Set `EXOTEL_CALLER_ID` to the ExoPhone number and `VOICE_TEST_RECIPIENT_PHONE` to the trial-verified number |
| `FHIR UPDATE FAILED` on the voice card | HAPI container down | `docker compose up -d`, re-run `python scripts/seed_synthea.py` |
| CSS/layout looks wrong only in the test browser | Cached stylesheet | Disable cache in DevTools (or CDP `Network.setCacheDisabled`) before screenshotting |

---

## 10. Panel Questions and Answers

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

Yes, when `VOICE_SIMULATION_ONLY=false`, the new GOLDEN Exotel settings are
configured, and the destination is in `TEAM_CONSENT_PHONE_NUMBERS`. The code
does not contain or reuse any previous-project credential, URL, phone number,
or account identifier.

### Where is the call audio?

Nowhere, by design. `EXOTEL_RECORD_CALLS` defaults to `false`, so no recording is
stored. The auditable artefact is the structured history the agent collected plus the turn-by-turn
transcript in `logs/voice/`.

### What are the limitations?

Hospital capacity is modeled synthetic data, HAPI is local infrastructure, the LLM fallback is keyword-based, and the system is decision support rather than autonomous clinical care.

---

## 11. Evidence Checklist

Before presenting, confirm:

- [ ] Docker container is running.
- [ ] `/fhir/metadata` returns `CapabilityStatement`.
- [ ] Seed command completed.
- [ ] `python -m pytest -q` passes (99 collected; the 3 FHIR integration tests need HAPI up).
- [ ] Dashboard `/api/health` reports `ONLINE` and `fhir_connected=true`.
- [ ] One case can be dispatched from the dashboard.
- [ ] FHIR resource IDs and ranking reasons are visible for the dispatched case.
- [ ] Tour plays to the last step, and `GoldenTour.start()` re-opens it.
- [ ] Driver Companion opens from the QR on a phone and from the same URL on a desktop viewport.
- [ ] Voice card shows the full transcript, including conditions and the closing summary.
- [ ] Terminal backup demo is available.
- [ ] Exotel values, if enabled, belong to the new GOLDEN account.
- [ ] `EXOTEL_STREAM_URL` is a new operator-owned public WSS endpoint.
- [ ] Live tunnel hostnames in `.env` resolve right now, not from a previous session.
- [ ] The presenter can explain synthetic data, offline fallback, two-stage hospital matching, consent safety, and human oversight.
