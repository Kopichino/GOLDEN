# GOLDEN Project Context

## Purpose

GOLDEN is an India-focused emergency-response decision-support system. It coordinates:

- Deterministic emergency detection for immediate life threats.
- Guideline-grounded triage.
- Two-stage hospital discovery and acuity-aware matching.
- HL7 FHIR R4 pre-registration.
- Consent-gated family outreach by voice.
- A dispatcher dashboard with auditability and human override authority.

This is decision support, not autonomous medical dispatch. Human dispatchers retain final authority.

## Runtime Components

### Dashboard and orchestration

Command:

```powershell
python -m uvicorn src.dashboard.server:app --host 127.0.0.1 --port 8000
```

Responsibilities:

- Serves the dashboard UI from `src/dashboard/static/`.
- Exposes case, health, event, simulation, and webhook endpoints.
- Owns the `GoldenOrchestrator` instance.
- Publishes LangGraph execution events through Server-Sent Events.
- Receives the voice completion callback and resumes the LangGraph checkpoint.

Important endpoints:

- `GET /`
- `GET /api/health`
- `GET /api/cases`
- `GET /api/cases/{case_id}`
- `GET /api/events`
- `POST /api/simulate`
- `POST /webhook/call-outcome`

### Voice WebSocket server

Command:

```powershell
python -m src.voice.voice_server
```

Default address:

```text
ws://127.0.0.1:8765/ws
```

Responsibilities:

- Receives Exotel bidirectional WebSocket media streams.
- Parses the Exotel `start`, `media`, and `stop` events.
- Resolves `case_id`, `thread_id`, `call_id`, and `stream_sid`.
- Opens a Gemini Live audio session.
- Converts Exotel 8 kHz PCM to Gemini 16 kHz PCM.
- Converts Gemini response audio back to Exotel 8 kHz media frames.
- Handles allow-listed Gemini tool calls.
- Sends structured call results to `VOICE_CALLBACK_URL` when the call ends.
- Creates a per-call transcript under `logs/voice/`.

Exotel must be configured with the public WSS URL that forwards to `/ws`. A tunnel is required for local development.

### HAPI FHIR

HAPI FHIR is not embedded in Python. It runs in Docker on port `8080`.

```powershell
docker compose up -d hapi-fhir
python scripts/seed_synthea.py
```

Default API base:

```text
http://localhost:8080/fhir
```

If port 8080 is refused, Docker Desktop or the HAPI container is not running. Dashboard incident simulation depends on FHIR hospital discovery and will fail until HAPI is reachable.

## Core Architecture

`GoldenOrchestrator` in `src/agents/coordinator.py` builds a LangGraph state machine:

```text
Input case
  -> Hard-SOS deterministic check
  -> either immediate RED escalation
     or parallel triage and hospital discovery
  -> acuity-aware hospital matching
  -> FHIR pre-registration
  -> consent-gated family communication
  -> dispatcher review / completion
```

### Hard-SOS

`src/agents/hard_sos.py` contains deterministic regex rules for life-threatening phrases such as:

- unresponsive
- not breathing
- cardiac arrest
- severe or massive bleeding
- amputation
- crushed or trapped

Hard-SOS bypasses ordinary LLM triage and escalates to RED with maximum confidence.

### Triage

`src/agents/triage.py` classifies cases as RED, YELLOW, GREEN, or BLACK. It uses configured providers with deterministic fallback behavior. Safety validation in `src/safety/guardrails.py` prevents unsafe downgrades of high-risk narratives.

### Hospital workflow

`src/agents/hospital.py` contains:

1. `HospitalDiscovery`: searches FHIR `Organization?type=prov` and reads hospital capabilities.
2. `HospitalMatcher`: ranks candidates using acuity, trauma level, beds, specialties, and distance.
3. `FhirToolService`: submits pre-registration resources or transaction bundles.

The discovery stage requires seeded Organization resources in HAPI FHIR.

## Shared State Contract

`src/state/schema.py` defines the Pydantic state models.

### `GoldenCaseState`

Contains:

- `input_data: CaseIdentityInput`
- `triage: TriageOutput`
- `hospital_fhir: HospitalFhirOutput`
- `voice_family: VoiceFamilyOutput`
- `control_audit: ControlAudit`

### Voice state

`VoiceFamilyOutput` stores:

- `call_status`
- `call_id`
- `recipient_phone`
- `consent_granted`
- `allergies`
- `medications`
- `blood_group`
- `pre_existing_conditions`
- `call_summary`
- `call_duration_seconds`
- `resumed_at`

The voice transcript itself is not placed into the LangGraph state. It is stored locally in the transcript log file.

## Voice Call Flow

1. The coordinator reaches the family communication node.
2. `FamilyCommunicationAgent` verifies the destination against `TEAM_CONSENT_PHONE_NUMBERS`.
3. `ExotelClient` either:
   - returns a local simulated call when `VOICE_SIMULATION_ONLY=true`, or
   - creates an Exotel call using `StreamUrl`, `StreamType=bidirectional`, and callback metadata.
4. Exotel opens the public WebSocket and sends a `start` event.
5. `ExotelCallMetadata.from_start_event()` extracts durable identifiers.
6. `GeminiLiveFamilySession.connect()` opens Gemini Live and sends the internal `CALL_START` trigger.
7. Gemini speaks the greeting and continues the family-history conversation.
8. `LiveVoiceBridge` forwards audio in both directions until Exotel sends `stop`, disconnects, or the configured timeout is reached.
9. Gemini function calls are handled by `FamilyVoiceSession`.
10. On completion, the voice server posts a JSON callback to `VOICE_CALLBACK_URL`.
11. `src/voice/webhook_receiver.py` validates the callback, checks the case/thread match, and calls `resume_from_voice_webhook()` on the coordinator.
12. The structured voice fields are merged into `voice_family` and the workflow continues.

## Gemini Family Agent

The system prompt and tool behavior are in `src/voice/family_voice_session.py`.

The agent is named Shreya and is restricted to collecting family-reported medical history. It must not diagnose, prescribe, estimate ambulance arrival, or override clinical personnel.

Required conversation order:

1. Obtain explicit consent.
2. Allergies.
3. Current medications.
4. Blood group.
5. Pre-existing conditions.
6. Final family summary.

Allow-listed tools are:

- `record_consent`
- `record_allergies`
- `record_medications`
- `record_blood_group`
- `record_conditions`
- `record_family_summary`

All medical tools are rejected until explicit consent is recorded.

### Language hard lock

The current policy is intentionally not automatic language detection:

- Start and remain in English by default.
- Do not switch because of isolated words, accents, names, short acknowledgements, code-mixing, or background speech.
- Switch only when the caller explicitly says they know or can speak only one named supported language, such as `I only know Hindi` or `Hindi only`.
- After that explicit one-time switch, lock the entire call to the named language.
- Supported switch languages are Tamil, Hindi, Telugu, Malayalam, Kannada, and English.
- Do not ask an open-ended language preference question. If clarification is required, ask in English for the name of the one language the caller knows.

## Audio and Turn Detection

`src/voice/audio_bridge.py` resamples:

- Exotel 8 kHz PCM -> Gemini 16 kHz PCM.
- Gemini response audio, normally 24 kHz -> Exotel 8 kHz PCM.

`GeminiLiveFamilySession` enables input/output transcription and configures automatic activity detection with:

- `prefix_padding_ms=200`
- `silence_duration_ms=500`

The silence setting controls how long Gemini waits after speech before committing the caller turn. Lower values reduce latency but can cut off callers who pause between words.

### Voice Latency Metrics

The bridge emits structured `VOICE_LATENCY` log entries through the
`golden.voice.latency` logger. Each snapshot includes:

- `caller_audio_to_gemini_ms`: time from detected caller speech to the first audio frame sent to Gemini.
- `gemini_processing_to_audio_ms`: time from the caller audio handoff to Gemini's first response audio after that caller input.
- `gemini_audio_to_exotel_ms`: time to convert and send Gemini response audio back to Exotel.
- `caller_audio_to_exotel_ms`: end-to-end time from detected caller speech to returned Exotel audio.
- frame counters for media received, Gemini input, Gemini output, and Exotel output.

The first caller speech frame is detected with a lightweight PCM RMS check. Low-
level line noise is suppressed, but real speech is forwarded even while the
opening greeting is still playing, matching the reference bridge behavior. The
keepalive task is not a shutdown signal; only Exotel stop/disconnect, Gemini
session termination, or the configured call timeout ends the bridge.

## Transcript and Event Logs

Each live voice call creates one file:

```text
logs/voice/<case_id>_<call_id>_<UTC timestamp>.log
```

Example contents:

```text
CALLER: Yes, I consent.
AGENT: Thank you. Does the patient have any known allergies?
EVENT TOOL_CALL | [{"name": "record_consent", "args": {"consent_granted": true}}]
```

The logger buffers transcript fragments and writes complete turns. Raw audio is not saved. Generated logs are ignored by Git.

The JSON event lines are audit metadata for Gemini tool calls and errors. They are not a separate database.

## Where Collected Data Goes

The agent calls a Gemini tool. `FamilyDisclosureAccumulator` stores the current call's structured values in memory:

```text
allergies
medications
blood_group
conditions
summary
consent_granted
```

At call end, `FamilyVoiceSession.callback_fields()` creates the callback payload containing those values plus IDs, status, and duration.

The dashboard callback validates:

- callback authentication, if `VOICE_CALLBACK_SECRET` is configured;
- the LangGraph thread exists;
- the callback `case_id` matches the checkpoint case.

Then `FamilyCommunicationAgent.process_webhook_disclosure()` sanitizes text with `PIISanitizer`, normalizes the blood group, creates `VoiceFamilyOutput`, and the coordinator resumes the checkpoint.

The dashboard reads the resulting state through `/api/cases/{case_id}`. The transcript file remains local and is not automatically uploaded to the dashboard or FHIR.

## Environment Variables

Do not copy secrets into documentation or commit `.env`.

Important variables:

```text
FHIR_BASE_URL=http://localhost:8080/fhir
GEMINI_API_KEY=<secret>
GEMINI_LIVE_MODEL=<Gemini Live model>
VOICE_SIMULATION_ONLY=true|false
VOICE_CALLBACK_URL=<public or local callback URL>/webhook/call-outcome
VOICE_CALLBACK_SECRET=<optional signing secret>
EXOTEL_ACCOUNT_SID=<secret>
EXOTEL_API_KEY=<secret>
EXOTEL_API_TOKEN=<secret>
EXOTEL_SUBDOMAIN=<Exotel host>
EXOTEL_CALLER_ID=<caller ID>
EXOTEL_STREAM_URL=<public WSS URL ending in /ws>
EXOTEL_STATUS_CALLBACK_URL=<optional Exotel status callback>
TEAM_CONSENT_PHONE_NUMBERS=<comma-separated allowed numbers>
VOICE_SERVER_HOST=127.0.0.1
VOICE_SERVER_PORT=8765
VOICE_SERVER_PATH=/ws
VOICE_CALL_TIMEOUT_SECONDS=300
```

If `.env` contains an exposed API key, rotate it immediately and replace it with a new key.

## Startup Order

```powershell
# Terminal 1: Docker / HAPI FHIR
docker compose up -d hapi-fhir

# Wait for http://localhost:8080/fhir/metadata, then seed once
python scripts/seed_synthea.py

# Terminal 2: dashboard
python -m uvicorn src.dashboard.server:app --host 127.0.0.1 --port 8000

# Terminal 3: voice WebSocket server
python -m src.voice.voice_server

# Separate tunnel: expose port 8765 as public WSS and port 8000 as public HTTPS when needed
```

For live Exotel calls, use `VOICE_SIMULATION_ONLY=false`, configure the new GOLDEN Exotel account, add an allowed destination number, and ensure the public tunnel URLs are current. Do not reuse an old tunnel URL.

## Tests and Validation

Focused voice tests:

```powershell
python -m pytest tests/test_voice_integration.py -q
```

Full suite:

```powershell
python -m pytest -q
```

Compile voice package:

```powershell
python -m compileall -q src/voice
```

The full suite may require HAPI FHIR to be running and seeded. Voice tests can run without a live phone call because they use fakes for Exotel/Gemini.

## Known Operational Issues

- `ConnectionRefusedError` on `localhost:8080` means Docker Desktop/HAPI FHIR is not running.
- A callback URL with a space or stale tunnel hostname causes DNS or callback failures.
- A live call that reaches the timeout produces cancellation inside the WebSocket reader; the server should report this as a timeout, not as a provider protocol failure.
- Gemini Live can return provider close code `1000` during normal session shutdown. Bridge tasks must be collected so this does not become an unhandled task exception.
- If caller responses are delayed, inspect the voice transcript and turn logs, then adjust Gemini activity detection carefully. Shorter silence detection reduces latency but may interrupt natural pauses.
- The Exotel stream must be bidirectional. Adding an Exotel `Url` alongside `StreamUrl` can cause Exotel to follow the wrong flow and end the call early.
- Dashboard state and FHIR state are separate: voice family history is merged into LangGraph state; hospital resources and pre-registration are stored in HAPI FHIR.

## Important Files

```text
src/config.py                         environment settings
src/state/schema.py                   Pydantic shared state
src/agents/coordinator.py             LangGraph orchestration
src/agents/hard_sos.py                deterministic life-threat bypass
src/agents/triage.py                  triage provider/fallback logic
src/agents/hospital.py                discovery, matching, FHIR service
src/fhir/client.py                    HAPI FHIR REST client
src/fhir/bundle_builder.py            FHIR transaction bundle construction
src/safety/guardrails.py               PII and clinical safety validation
src/voice/family_communication.py     consent and outreach workflow
src/voice/exotel_client.py             outbound Exotel client
src/voice/exotel_media_gateway.py      Exotel event parsing and PCM conversion
src/voice/gemini_live_session.py       Gemini Live setup and tools
src/voice/family_voice_session.py      voice prompt and disclosure accumulator
src/voice/live_bridge.py               bidirectional realtime bridge
src/voice/voice_server.py              WebSocket server and callback posting
src/voice/transcript_logger.py         per-call transcript files
src/voice/webhook_receiver.py          callback validation and checkpoint resumption
src/dashboard/server.py                dashboard API and event stream
scripts/seed_synthea.py                seed synthetic FHIR data
scripts/run_demo.py                    CLI demo
```

## Safety and Privacy Boundaries

- Explicit consent is required before collecting medical history.
- The voice agent is not authorized to diagnose, prescribe, or make dispatch decisions.
- PII sanitization is applied to structured family disclosures before state resumption.
- API keys and provider credentials belong only in `.env` and must not be placed in logs, documentation, or source control.
- Voice logs contain sensitive conversational information; protect the `logs/voice/` directory and apply retention rules before production use.
- Synthetic FHIR seed data is intended for development and demonstration, not real patient care.
