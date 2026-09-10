# GOLDEN — Panel Presentation Script & Notes

### Guideline-Grounded Orchestrated LLM Dispatch for Emergency Networks

Team: Koppesh P (23BAI1113) · Abdul Khader (23BAI1123) · Santhosh Kumar (23BAI1236)

> **Current local verification (2026-09-10):** HAPI FHIR is running with a seed
> baseline of 3 organizations and 4 synthetic patients; integration tests have
> brought the live patient count to 16. The full suite passes 35 tests. Voice
> calls are simulated or refused according to the consent register.

The capstone execution plan records the use case, phase workflow, demonstration
script, evaluation evidence, and submission-readiness work:
[CAPSTONE_EXECUTION_PLAN.md](CAPSTONE_EXECUTION_PLAN.md).

> How to use this document: for every slide there are three parts —
> **[SAY]** the actual script you can speak (adapt in your own words, don't read verbatim),
> **[MEANING]** what each technical term/concept actually means, in plain language, and
> **[BE READY FOR]** likely panel questions with short answers.
> Practice saying each slide's script in under 60–90 seconds — 10 slides ≈ 10–12 minute talk, leaving time for Q&A.

---

## SLIDE 1 — Title Slide

**[SAY]**
"Good morning/afternoon, panel. Our project is called GOLDEN — Guideline-Grounded Orchestrated LLM Dispatch for Emergency Networks. In one line: it's an India-grounded, guideline-compliant decision-support system that uses a team of coordinated AI agents to speed up what happens in the first minutes after a road accident is reported — from triage, to finding a hospital bed, to registering the patient digitally, to calling the family — all done in parallel instead of one human dispatcher doing everything one step at a time on the phone."

**[MEANING — know these cold]**

- **"Guideline-grounded"** = the AI's medical/triage decisions are anchored to real clinical/emergency guidelines (not just improvising), so its reasoning can be traced back to an actual protocol.
- **"Orchestrated LLM"** = multiple large language model (LLM) "agents" are coordinated by a controller ("orchestrator"), each agent handling one job, instead of one giant AI doing everything.
- **Framework stack — LangGraph (Python):** LangGraph is a Python library (built by the LangChain team) for building multi-step, multi-agent AI workflows as a _graph_ — nodes are agents/steps, edges are the logic for what happens next (including loops/retries). You chose it because emergency dispatch is naturally a flow with branches (e.g., "if life-threatening, skip to bypass path").
- **HL7 FHIR R4 / ABDM:**
  - **HL7 FHIR** (Fast Healthcare Interoperability Resources, Release 4) is the global standard format healthcare systems use to exchange patient data (like a common language between hospitals' software).
  - **ABDM** = Ayushman Bharat Digital Mission, India's government initiative for a national digital health ecosystem (gives citizens an ABHA health ID, health record linking, etc.). Building around FHIR + ABDM means your system could realistically plug into India's actual digital health infrastructure, not a fictional one.

**[BE READY FOR]**

- _"Why LangGraph and not just calling an LLM API directly?"_ → Because you need state that persists across multiple agents and a long-running interruption (the voice call), with retries and conditional branching — a single API call can't do that; a graph orchestration framework can pause and resume.
- _"Why FHIR?"_ → It's the real-world interoperability standard hospitals actually use, so the project's output isn't a toy format — it's something a real hospital EHR could ingest.

---

## SLIDE 2 — Technical Relevance & Problem Statement

**[SAY]**
"This slide justifies why the project matters, technically and socially. Technically, we use multi-agent orchestration with LangGraph — an orchestrator pattern with specialist agents, a shared strongly-typed state object using Pydantic v2, conditional edges, retry cycles, and durable checkpointing. We're standards-compliant — we generate a real FHIR bundle containing Patient, Encounter, and Condition resources, tested against a live HAPI FHIR server. And critically, this is India-grounded, not a US-centric solution — it's built around India's actual 108 and 112 emergency response numbers, the ABDM/ABHA digital health ecosystem, and the MoRTH Cashless Treatment of Road Accident Victims Scheme, 2025.

The problem: India recorded about 1.99 lakh traffic deaths in 2024 — that's 546 deaths every single day, per NCRB's ADSI 2024 report. The golden hour — the first hour after a severe trauma, when treatment is most likely to save a life — is being lost to fragmented, serial, manual coordination between the 108/112 emergency services and hospitals. And there's a legal driver too: the Supreme Court, in S. Rajaseekaran v. Union of India (2025 INSC 45), tied golden-hour emergency care directly to Article 21 — the right to life."

**[MEANING]**

- **Orchestrator–specialist pattern:** one "coordinator" agent manages control flow and delegates to specialist agents (triage, hospital-matching, voice-calling) — like a project manager assigning tasks to domain experts, rather than one generalist doing everything.
- **Pydantic v2:** a Python library for defining data structures ("models") with strict types and automatic validation. A "shared Pydantic v2 state" means every agent reads/writes to one well-defined, type-checked object, so agents can't corrupt each other's data with malformed output.
- **Conditional edges:** in LangGraph, the path the workflow takes next depends on a condition (e.g., "if hard-SOS flag is true, skip triage LLM and go straight to hospital agent").
- **Retry cycles:** if an agent's output fails validation (e.g., bad JSON), the graph can loop back and retry rather than crashing.
- **Durable checkpointing:** LangGraph can save ("checkpoint") the exact state of the workflow so it can pause (e.g., during a multi-minute phone call) and resume later exactly where it left off — essential because your Voice Agent's call to the family may take minutes, and you can't keep the whole pipeline blocked and waiting synchronously.
- **HAPI FHIR server:** an open-source, widely used reference implementation of a FHIR server — you use it as a real (not simulated) FHIR-compliant backend to prove your Patient/Encounter/Condition bundle is standards-valid.
- **108 / 112:** 108 is India's dedicated ambulance/emergency medical helpline (state-run in most states); 112 is India's unified national single emergency number (ERSS – Emergency Response Support System), covering police/fire/medical.
- **NCRB ADSI 2024:** National Crime Records Bureau's "Accidental Deaths & Suicides in India" annual report — the authoritative government statistics source you're citing for the 1.99 lakh figure.
- **S. Rajaseekaran v. Union of India:** a real Supreme Court of India case concerning road-accident victims' right to timely medical care; you're citing it to show your project addresses a constitutionally-recognized right, not just an engineering convenience.

**[BE READY FOR]**

- _"What exactly is a FHIR bundle?"_ → A structured, standards-compliant package of related clinical resources (here: Patient info + the Encounter/visit + the Condition/diagnosis) bundled together so a hospital system can ingest it as one unit.
- _"Why does golden-hour matter medically?"_ → Trauma mortality and complication rates rise sharply the longer definitive treatment is delayed; the "golden hour" is the widely-used clinical heuristic that outcomes are significantly better if care starts within ~60 minutes of severe injury.

---

## SLIDE 3 — Abstract & Core Idea

**[SAY]**
"The core idea in one sentence: GOLDEN is one multi-agent AI system that _parallelizes_ tasks a human dispatcher currently does _serially_, one phone call at a time. There are four agents at the core: a Coordinator, a Triage/Dispatcher agent, a Hospital & Bed agent, and a Family-Notification Voice agent. What we parallelize is: emergency triage, hospital-and-bed selection, FHIR patient pre-registration, and autonomous family notification — all happening at once instead of in sequence.

I want to be very clear on positioning: this is explicitly decision-support for human dispatchers. It is NOT autonomous medical decision-making — a human is always still in the loop for the actual medical/dispatch decision.

Why this matters economically: MoRTH estimates the socio-economic cost of road accidents at roughly INR 1,47,114 crore — about 0.77% of GDP — and that could be as high as INR 5,96,820 crore, or 3.14% of GDP, once you adjust for underreporting, per World Bank estimates. And on the human side: fewer than 1 in 4 road accident victims in India currently reach care within the golden hour."

**[MEANING]**

- **Serial vs. parallel dispatch:** today, a human dispatcher on the phone does triage, then calls hospitals one by one to find a bed, then arranges registration, then may call the family — each step waits for the previous one to finish. Your system fires these off concurrently as independent agent tasks, which is the core efficiency claim of the whole project.
- **"Decision support, not autonomous" positioning:** this is an important ethical/safety framing for a panel — you're not claiming the AI diagnoses or decides medical treatment; it surfaces recommendations (best hospital, triage acuity) that a human dispatcher approves/acts on. This matters both for medical-safety credibility and for feasibility (you can't and shouldn't claim regulatory-grade autonomous medical AI in a capstone).
- **MoRTH:** Ministry of Road Transport and Highways — the Indian government ministry responsible for road safety data/policy; source of the socio-economic cost estimate.
- **"1 in 4 reach care within golden hour":** this is your core motivating statistic — it directly frames the gap your project targets.

**[BE READY FOR]**

- _"If it's decision support only, what's the actual innovation?"_ → The innovation is the _speed and parallelism_ of gathering and structuring the information a human needs to decide — turning several sequential 2–5 minute phone calls into simultaneous automated agent actions, cutting the time-to-decision, while the human retains final authority.

---

## SLIDE 4 — Objectives & Expected Outcomes

**[SAY]**
"We have three primary objectives. One: build an end-to-end LangGraph pipeline that goes from ingesting an incident report, through triage, hospital/bed matching, FHIR pre-registration, to a family voice call — within a target latency. Two: build a real AI voice-calling agent — using Exotel telephony integrated with Google's Gemini Live model through a custom Python audio bridge, with async webhook-based state resumption so the graph can pause during the call and resume when it's done. Three: implement guideline-grounded triage with a hard-SOS bypass — a deterministic rule-based path that completely skips LLM latency for clearly life-threatening cases.

Our secondary objectives: handling code-mixed Tamil–English input and measuring the accuracy delta versus English-only; mitigating cascading hallucination across agent handoffs using schema validation and inter-agent verification; comparing model tiering — a hosted 70-billion-parameter model versus a local 7–8B model under simulated degraded connectivity; and benchmarking against MedAgentBench, a published healthcare-agent benchmark.

Expected outcomes: a working end-to-end demo with ablation results E1 through E6, a working hard-SOS bypass with offline fallback, a MedAgentBench score compared against published baselines, and a standards-compliant FHIR artifact plus a rehearsed live demo script."

**[MEANING]**

- **Exotel:** an Indian cloud telephony provider (API-based calling/SMS) — lets your code programmatically place and manage real phone calls.
- **Gemini Live:** Google's real-time, low-latency conversational voice AI model — used here as the "brain" that actually talks to the family member on the call.
- **Audio bridge:** custom code that connects two audio systems with different formats/protocols (Exotel's telephony audio stream and Gemini Live's expected audio format) so they can talk to each other.
- **Webhook-based state resumption:** when the phone call ends, Exotel/your call-handling service sends an HTTP callback ("webhook") back to your system, which then resumes the paused LangGraph workflow with the call's outcome — this is _why_ checkpointing (from Slide 2) matters.
- **Hard-SOS bypass:** a deterministic (non-LLM, rule-based) fast path — if the incident report contains clear life-threat keywords/patterns, the system skips the LLM triage step entirely (LLMs add latency and non-zero error risk) and immediately flags it as critical.
- **Code-mixed Tamil–English:** real emergency callers in Tamil Nadu often mix Tamil and English in the same sentence ("code-switching/code-mixing") — a major real-world NLP challenge that pure English-trained systems handle poorly.
- **Cascading hallucination:** when one agent's incorrect/hallucinated output is passed to the next agent as if it were true, and errors compound across the pipeline — a known failure mode in multi-agent LLM systems.
- **Model tiering (70B vs 7–8B):** a bigger model (70 billion parameters) is generally more accurate but needs a hosted/cloud API (needs connectivity); a smaller local model (7–8B parameters) can run offline on modest hardware but is less capable — you test the trade-off for a "degraded connectivity" scenario relevant to rural/disaster settings.
- **MedAgentBench:** a published benchmark (Jiang et al., 2025, NEJM AI) that measures how well an LLM agent can interact with FHIR/EHR systems to complete clinical tasks — you use it as an external, objective yardstick for your Hospital/FHIR agent instead of only self-reported metrics.
- **Ablations (E1–E6):** "ablation" experiments = you remove/change one component at a time and measure the effect, to prove _which_ design choices actually help (see Slide 8 for the six experiments).

**[BE READY FOR]**

- _"What's your target latency?"_ → State whatever number your team has set as the pipeline SLA (e.g., "under X seconds from ingestion to hospital match, excluding the voice call itself"). If not finalized, say it's being measured empirically in Phase 3's evaluation harness.
- _"Why not just always use the biggest, most accurate model?"_ → Cost, latency, and — critically — availability during connectivity loss, which is common in real emergency/rural scenarios; that's exactly what ablation E5 tests.

---

## SLIDE 5 — Scope & Feasibility

**[SAY]**
"To keep this achievable within a capstone timeline, we defined a clear scope. In scope: LangGraph orchestration plus the Triage Agent; the Hospital/Bed Agent with a FHIR server built on HAPI FHIR and populated with Synthea synthetic patient data; FHIR pre-registration and voice-call integration; a live dashboard plus an evaluation and ablation harness; India-grounded prompting with a safety layer; and a simulated ambulance/traffic visualization. Out of scope: real patient data or unconsented call recipients, production hospital APIs or actual ABDM certification, autonomous diagnosis or real traffic-signal control, and vision-language-model-based trauma diagnosis from images.

We made several feasibility corrections from our original plan. The biggest: we reduced from an originally-planned 7-agent system down to a focused 4-agent core. On model hosting, we dropped the idea of self-hosting a 70B model — which would have needed roughly two 80GB GPUs — in favor of free-tier hosted inference: Groq's Llama 3.3 70B, Gemini 2.5 Flash, and OpenRouter, with Llama 3.1 8B or Qwen 2.5 7B running locally via Ollama only for the offline-fallback case. On telephony, we technically verified that Exotel's 8kHz audio can be resampled to Gemini Live's 16kHz/24kHz using Python, NumPy, and SciPy — and for consent and legal safety, test calls are restricted to consenting team members, per TRAI's Telecom Commercial Communications Customer Preference Regulations, 2018. Finally, the route/ambulance visualization and accident-detection vision agents are optional — we'll only add them if the core system is stable."

**[MEANING]**

- **Synthea:** an open-source synthetic patient data generator — produces realistic but entirely fake patient records, so you get FHIR-format test data without touching any real person's medical data (this is _why_ "real patient data" can stay out of scope while you still test with realistic FHIR resources).
- **Ollama:** a tool for running open-weight LLMs locally on your own machine (no cloud API needed) — this is what powers your offline fallback.
- **Groq:** a cloud inference provider known for very fast (low-latency) hosted LLM inference — one of your hosted-model options.
- **OpenRouter:** a service that routes API calls to many different LLM providers/models through one unified API — gives you flexibility to swap models.
- **8kHz vs 16kHz/24kHz resampling:** telephony audio (like Exotel) is traditionally low-bandwidth 8kHz (standard phone-quality audio); Gemini Live expects higher-fidelity 16kHz or 24kHz audio; you must convert ("resample") the audio sample rate in real time so the two systems can understand each other's audio streams.
- **TRAI TCCCPR 2018:** India's telecom regulator's rules governing unsolicited/commercial calls — citing this shows you've thought about the _legal_ constraint on making outbound calls, which is why real calls are restricted to consenting team members rather than real members of the public during development.
- **ABDM certification:** the formal government process to be officially recognized/integrated into India's digital health mission — correctly scoped out because that's a bureaucratic/compliance process far beyond a capstone's scope, even though you build _toward_ FHIR/ABDM compatibility.

**[BE READY FOR]**

- _"Why cut from 7 agents to 4?"_ → More agents = more coordination complexity, more failure points, and less time to properly evaluate any one part; 4 agents let you build something that's actually finished, tested, and demoable rather than partially working across 7.
- _"Isn't relying on free-tier hosted APIs risky?"_ → Yes — that's precisely why you built the local-model offline fallback (Ollama) and why ablation E5 explicitly measures degraded-connectivity behavior.

---

## SLIDE 6 — Preliminary Work Plan (5 Phases)

**[SAY]**
"Our plan has five phases. Phase 0, Foundations: register for PhysioNet/CITI training and ABDM sandbox access, get API keys, set up HAPI FHIR and Synthea, and freeze the architecture — deliverable is a working FHIR store plus working LLM calls and a version-1 design doc. Phase 1, Core Agents: build the Triage Agent, Hospital/Bed Agent, the LangGraph orchestrator with the hard-SOS bypass, and the Voice Agent — deliverable is an end-to-end 'happy path' demo, meaning the simplest successful case works start to finish. Phase 2, Integration, Safety & Dashboard: add the guardrail/validation layer, build the live dashboard, add code-mixed speech-to-text using Whisper, and the offline fallback via Ollama — deliverable is Integrated Demo v1. Phase 3, Evaluation & Experiments: build the evaluation harness and run ablations E1 through E6, including MedAgentBench, plus optional agents if time allows — deliverable is results tables and charts. Phase 4, Writing & Polish: draft an arXiv paper, write the final report, and rehearse the live demo — deliverable is a submission-ready paper and viva package.

There's one key decision gate: after Phases 1 and 2, we only add ONE optional agent if the core system is stable — otherwise we reinvest that time into deeper evaluation instead."

**[MEANING]**

- **PhysioNet/CITI:** PhysioNet is a research resource for physiological/clinical data; CITI training refers to standard research-ethics/human-subjects training often required before accessing health-related datasets or sandboxes — citing this shows you're following proper ethical process even for a sandbox project.
- **"Happy path" demo:** software engineering term for the default success scenario with no errors — proving the simplest case works end-to-end before handling edge cases.
- **Whisper:** OpenAI's open-source automatic speech recognition (speech-to-text) model — used here to transcribe the (potentially code-mixed Tamil-English) spoken incident report into text the Triage Agent can process.
- **Guardrail/validation layer:** code that checks agent outputs against rules/schemas before they're trusted/acted on (ties back to Pydantic validation and moderation checks from Slide 9/10).
- **Decision gate:** a planned checkpoint where the team consciously chooses to expand scope _only if_ the core is solid — a good project-management practice to highlight to a panel, since it shows risk-awareness rather than over-promising.

**[BE READY FOR]**

- _"What's your current phase?"_ → Answer honestly based on where your team actually is right now.
- _"What happens if Phase 1 core agents aren't stable by the deadline?"_ → The decision gate exists exactly for this — you deprioritize optional agents and invest remaining time into hardening/evaluating the 4-agent core rather than adding scope.

---

## SLIDE 7 — Literature Review Highlights & Research Gap

**[SAY]**
"Five key papers shape this project. First, TriAgent by Ibrahim et al., 2026 — it achieves 85% critical-case recall versus a baseline of only 14.7% or less, and it's the closest architectural precedent to GOLDEN. Second, MedAgentBench by Jiang et al., 2025, published in NEJM AI — it found Claude 3.5 Sonnet v2 leads with 69.67% success, and this is the primary FHIR/EHR benchmark we use in this project. Third, a meta-analysis by Cui et al., 2026, found that LLM-only emergency-department triage has a pooled sensitivity of only 61% for the highest-acuity cases — this directly justifies why we use a deterministic hard-SOS bypass instead of trusting the LLM alone for life-threatening cases. Fourth, Gaikwad et al., 2025, found only 20.6% of road-traffic-accident victims in India reached care within the golden hour — this is our core India-specific motivating statistic. Fifth, AgenTask by Lin et al., 2026, showed that handoff clarification between agents improves accuracy by up to 4.69% — this is the basis for our schema validation and inter-agent verification approach.

Our research gap: no existing work combines India-grounded context, code-mixed Tamil–English handling, parallel multi-agent coordination across triage, hospital/bed matching, FHIR, and family notification, a deterministic safety bypass, AND explicit handoff-error mitigation, all in one system. GOLDEN is positioned to fill exactly that combined gap."

**[MEANING]**

- **Recall / sensitivity (in this context):** of all the truly critical cases, what fraction did the system correctly flag as critical? High recall on critical cases matters enormously in triage because _missing_ a critical case (a false negative) can be fatal — much worse than a false alarm.
- **Pooled sensitivity (meta-analysis):** when Cui et al. combine ("pool") results across multiple studies, the _combined_ sensitivity for the highest-acuity/most urgent category was only 61% — meaning LLM-only triage alone missed about 39% of the most critical cases across the studies reviewed. This is your strongest piece of evidence for why you should NOT trust an LLM alone on life-or-death classification.
- **"Handoff" between agents:** the point where one agent's output becomes another agent's input — a known weak point for error propagation in multi-agent systems (this is exactly the "cascading hallucination" problem from Slide 4).
- **Research gap:** in academic writing, this means identifying what specific combination of ideas _hasn't_ been done before by others — your unique contribution isn't necessarily any single technique (multi-agent systems, FHIR integration, code-mixed NLP all individually exist), but the _specific combination_ applied to this specific India-grounded emergency-response problem.

**[BE READY FOR]**

- _"Isn't multi-agent LLM orchestration for healthcare already done elsewhere (e.g., in the US)?"_ → Yes, conceptually (TriAgent is your closest precedent) — but not combined with India-specific context (108/112, ABDM, MoRTH scheme), code-mixed Tamil-English input, and the deterministic safety bypass together — that combination is your gap.
- _"Why cite a meta-analysis for your safety design decision?"_ → Because a meta-analysis (pooling multiple independent studies) is stronger evidence than any single study — it shows the "LLMs miss critical cases sometimes" finding isn't a one-off.

---

## SLIDE 8 — Proposed Methodology & Evaluation

**[SAY]**
"Our methodology is what we call hybrid, safety-first: deterministic rules handle safety-critical decisions, while LLM agents handle open-ended reasoning — and we evaluate the whole approach through six controlled ablation experiments.

E1, Core Architecture — Single Agent versus Multi-Agent: we measure triage accuracy and F1 score, hallucination rate, and latency, to answer whether multi-agent decomposition actually improves the system, or whether it's unnecessary complexity.

E2, Prompt Grounding — Guideline-Grounded versus Open Prompting: we measure triage F1 and high-risk recall, to answer whether grounding the LLM's prompt in actual clinical guidelines improves triage quality.

E3, Safety Bypass — Hard-SOS versus LLM-only: we measure latency and critical-case miss rate, to answer whether deterministic routing makes critical-case handling both safer and faster.

E4, Multilingual Robustness — English versus Tamil–English: we measure the accuracy delta and Whisper's word error rate, to answer how much performance changes with real code-mixed emergency input.

E5, Offline Resilience — Hosted 70B versus Local 7-to-8B: we measure output quality, latency, and availability during simulated connectivity loss, to answer whether the system degrades gracefully rather than failing completely.

E6, External Validation — MedAgentBench: we measure EHR interaction success and compare against Claude 3.5 Sonnet v2, GPT-4o, DeepSeek-V3, and other published baselines, to answer how our Hospital/FHIR agent performs against an established, external benchmark."

**[MEANING]**

- **F1 score:** a single metric combining precision (of the cases you flagged as critical, how many really were critical) and recall (of all truly critical cases, how many did you catch) into one balanced number — standard for classification tasks where both false positives and false negatives matter.
- **Word Error Rate (WER):** the standard metric for speech-to-text accuracy — the percentage of words the transcription got wrong (substituted, deleted, or inserted) compared to the true transcript.
- **Ablation study (recap):** each Ex tests exactly one variable while holding others constant, isolating _which specific design choice_ is responsible for a result — this is what makes your claims scientifically defensible rather than just "we built a system and it seemed to work."
- **Baselines (Claude 3.5 Sonnet v2, GPT-4o, DeepSeek-V3):** other well-known LLMs' published scores on MedAgentBench — used as reference points so your system's score has external, comparable meaning instead of being evaluated in isolation.

**[BE READY FOR]**

- _"What result would make you conclude multi-agent (E1) ISN'T worth it?"_ → If single-agent performs comparably on F1/hallucination while being meaningfully faster, that would suggest the added orchestration complexity isn't justified for this task size — good scientific honesty to state, even if you expect otherwise.
- _"How do you get 'ground truth' for triage accuracy/F1?"_ → Explain your labeling approach (e.g., guideline-based expert/simulated gold labels on your test incident set) — be ready with your actual answer here since panels probe evaluation validity hard.

---

## SLIDE 9 — System Design

**[SAY]**
"All our agents communicate through one strongly-typed Pydantic v2 shared state object — this is what lets LangGraph pause during the voice call and resume exactly where it left off once the webhook callback arrives. That state has several sections: Case Identity and Input — case ID, raw input, language, modality; Triage Output — acuity level, the hard-SOS flag, confidence, and a guideline reference; Hospital/FHIR — candidate hospitals, the selected hospital, bed status, and the bundle ID; Voice/Family — call status, consent, allergies, medications, and blood group; and Control & Audit — the current node in the graph, any errors, the checkpoint, and timestamps.

The Hard-SOS Rule Engine takes the emergency report as input and uses deterministic keyword and pattern matching — zero LLM calls, sub-second response — triggered by terms like unresponsive, not breathing, no pulse, severe bleeding, or cardiac arrest. It's deliberately designed to accept some false positives in order to minimize false negatives — because in this context, missing a real emergency is far worse than one extra false alarm.

The Triage Agent's pipeline: incident goes into a guideline-grounded prompt, the LLM reasons over it, output must fit a fixed JSON schema, Pydantic validates it, and if invalid it retries — only then does it join the shared state. It outputs acuity, confidence, rationale, and a guideline reference.

The Hospital & Bed Agent runs FHIR queries to get candidate hospitals, checks bed availability, ranks candidates by acuity, distance, and availability, and writes the FHIR pre-registration bundle. Importantly, it uses targeted iterative FHIR queries rather than one giant single-shot retrieval — this is consistent with a finding from the FHIR-AgentBench literature that multi-turn querying works better.

The Voice Agent: the Coordinator triggers a non-blocking call — meaning the rest of the pipeline doesn't have to wait — through Exotel, our Python audio bridge, Gemini Live, family interaction happens, then a webhook fires and the checkpoint resumes. If it fails, we persist the payload for manual recovery rather than silently losing data.

Finally, four design patterns tie it together: Orchestrator–Worker, where the Coordinator owns control flow while specialist agents stay independently testable; Circuit Breaker/Fallback, where a hosted-model failure triggers a local-model fallback; Idempotent Writer, meaning FHIR writes and calls can safely be retried without creating duplicates; and Checkpoint & Resume, which lets the graph survive the multi-minute voice interaction."

**[MEANING]**

- **Acuity:** in emergency medicine, a measure of how severe/urgent a patient's condition is (how quickly they need treatment) — this is literally what your Triage Agent is trying to classify.
- **False positive vs. false negative (in this specific context):** a false positive = the system flags a non-emergency as a hard-SOS (wastes some resources, minor cost); a false negative = the system fails to flag a real emergency (potentially fatal cost). Your design explicitly accepts more false positives to drive false negatives toward zero — a classic asymmetric-cost safety design decision, and a great thing to explain confidently if asked.
- **Non-blocking call:** a software design term — the system doesn't freeze/wait for the phone call to finish before continuing other work; it moves on and gets notified later (via webhook) when the call concludes.
- **Idempotent:** an operation that produces the same result no matter how many times it's repeated — critical for network-unreliable operations like FHIR writes or phone calls, where a retry after a timeout shouldn't accidentally create two duplicate patient records or place two calls.
- **Circuit breaker pattern:** a resilience design pattern (borrowed from electrical circuit breakers) — if a dependency (like the hosted LLM API) keeps failing, the system "trips" and reroutes to a fallback (the local model) instead of repeatedly hitting a broken/slow service.
- **FHIR-AgentBench:** a benchmark/study you're citing about how LLM agents best query FHIR servers — their finding (that breaking queries into multiple targeted steps beats one giant query) directly informed your Hospital/Bed Agent's design.

**[BE READY FOR]**

- _"Why not just have every agent talk to every other agent directly?"_ → That's a mesh topology — it gets combinatorially complex and hard to debug/test as agents grow; the orchestrator-worker pattern keeps each specialist agent independently testable and keeps control flow in one place (the Coordinator), which is more maintainable and more debuggable.
- _"What happens on a webhook failure (e.g., the callback never arrives)?"_ → Be ready to explain your actual timeout/retry/manual-recovery handling — this ties to the "persist payload → manual recovery" failure path mentioned for the Voice Agent.

---

## SLIDE 10 — System Architecture

**[SAY]**
"This is the end-to-end architecture view. The pattern is an orchestrator–specialist multi-agent design running as a stateful, cyclic LangGraph graph — 'cyclic' because it can loop back for retries, not just flow one-way.

Ingestion handles incident reports and Tamil-English speech-to-text. Orchestration runs the hard-SOS bypass check before anything else in the flow. The Specialist Agents layer runs the Triage and Hospital agents in a parallel fan-out — meaning both start working at the same time rather than one after another. Data & Integration covers HAPI FHIR, Synthea, and our schemas. External & Presentation covers the hosted LLMs, the live dashboard, and the offline fallback.

Walking through it end to end: the Coordinator runs the hard-SOS check first, then fans out the Triage and Hospital agents in parallel, merges their outputs, and triggers the Voice Agent. The Triage/Dispatcher Agent does guideline-grounded acuity classification, handles Tamil-English code-mixed input, and produces schema-validated output. The Hospital & Bed Agent queries HAPI FHIR and Synthea, checks simulated bed availability, ranks by acuity/distance, and writes the FHIR pre-registration bundle. The Voice Agent places the Exotel outbound call to Gemini Live through our Python audio bridge, and n8n posts the call outcome back, resuming the paused graph. The Safety/Validation Layer applies Pydantic schema gates, deterministic checks, and a moderation call at every single agent handoff. And the Live Dashboard shows real-time case state, agent status, and call status."

**[MEANING]**

- **Cyclic graph:** unlike a simple linear pipeline (A→B→C), a cyclic graph allows going back to a previous node — e.g., "retry triage if validation failed" loops back rather than dead-ending, which is essential for your retry-cycle design from Slide 2.
- **Fan-out (parallel):** one node in the graph triggers multiple independent branches to run concurrently (Triage and Hospital agents both start as soon as the hard-SOS check clears) — this parallelism is the literal mechanism behind your "parallelizes serial dispatcher work" core claim from Slide 3.
- **n8n:** an open-source workflow-automation tool (like Zapier, but self-hostable) — here it's the piece of infrastructure that receives the webhook from the telephony/voice side and posts the call outcome back into your system, triggering the graph to resume.
- **Moderation call:** an automated content-safety check (often another LLM or classifier call) run at each handoff to catch unsafe, nonsensical, or policy-violating content before it propagates further — an extra safety layer on top of schema validation.

**[BE READY FOR]**

- _"Walk me through what happens in the first 5 seconds after an incident report comes in."_ → Ingestion (report/STT) → Hard-SOS deterministic check (sub-second) → if not hard-SOS, fan out Triage + Hospital agents in parallel → each validated against its schema → Coordinator merges → Voice Agent triggered non-blocking → dashboard updates in real time throughout.
- _"Where exactly does n8n sit versus your Python audio bridge?"_ → The audio bridge handles the real-time audio streaming between Exotel and Gemini Live during the live call; n8n is the workflow piece that receives the _call-completion_ webhook event afterward and notifies your LangGraph app to resume — they're different stages (during-call vs. after-call).

---

## Quick-Reference Glossary (skim this right before you walk in)

| Term                    | One-line meaning                                                                                          |
| ----------------------- | --------------------------------------------------------------------------------------------------------- |
| LangGraph               | Python framework for graph-based, stateful multi-agent LLM workflows with branching/retries/checkpointing |
| Pydantic v2             | Python data-validation library; defines strict, type-checked data models                                  |
| HL7 FHIR R4             | Global standard format for exchanging healthcare data                                                     |
| ABDM / ABHA             | India's national digital health mission / the citizen health-ID it issues                                 |
| HAPI FHIR               | Open-source reference FHIR server implementation, used as your real backend                               |
| Synthea                 | Synthetic (fake but realistic) patient data generator                                                     |
| 108 / 112               | India's ambulance helpline / unified national emergency number (ERSS)                                     |
| MoRTH                   | Ministry of Road Transport & Highways (India)                                                             |
| NCRB ADSI               | Government annual report on accidental deaths/suicides — source of the death-toll stats                   |
| Golden hour             | First ~60 minutes after severe trauma, when treatment most improves survival odds                         |
| Hard-SOS bypass         | Deterministic, rule-based fast path that skips the LLM for obviously life-threatening cases               |
| Exotel                  | Indian cloud telephony API provider used for outbound calls                                               |
| Gemini Live             | Google's real-time conversational voice AI model                                                          |
| Whisper                 | OpenAI's open-source speech-to-text model                                                                 |
| Ollama                  | Tool for running LLMs locally/offline                                                                     |
| Groq / OpenRouter       | Hosted LLM inference providers                                                                            |
| MedAgentBench           | Published benchmark for LLM agents interacting with FHIR/EHR systems                                      |
| F1 score                | Balances precision and recall into a single classification-quality metric                                 |
| WER                     | Word Error Rate — speech-to-text accuracy metric                                                          |
| Ablation study          | Experiment removing/varying one component at a time to isolate its effect                                 |
| Idempotent              | Operation safe to repeat/retry without side effects like duplication                                      |
| Circuit breaker         | Resilience pattern: switch to a fallback when a dependency keeps failing                                  |
| Cascading hallucination | LLM error from one agent propagating and compounding through downstream agents                            |
| n8n                     | Open-source workflow-automation tool handling the post-call webhook                                       |

## General Panel-Readiness Tips

- If you don't know an exact number the panel asks for (e.g., an exact latency figure), it's fine to say "that's part of what Phase 3's evaluation harness will report precisely" rather than guessing.
- Be ready to explain **why a human is still in the loop** (Slide 3) — panels often push on AI-safety-in-healthcare questions; your strongest answer is the hard-SOS bypass + decision-support framing + the Cui et al. 61%-sensitivity finding (Slide 7) as evidence LLM-only triage isn't safe enough alone.
- Know your own three names/reg numbers and each person's role if the panel asks who did what.
