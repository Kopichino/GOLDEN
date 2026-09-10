Review-Report

## REVIEW-REPORT

# GOLDEN: Guideline-grounded Orchestrated LLM Dispatch

# for Emergency Networks

### An India-Grounded, Guideline-Compliant Decision-Support Framework for

### Pre-Hospital Emergency Coordination Using Orchestrated LLM Agents

Orchestration Framework: LangGraph (Python)
Interoperability Standard: HL7 FHIR R4 / ABDM

### Current Implementation Note (2026-09-10)

The local implementation has a running HAPI FHIR R4 backend with 3 seeded
organizations and a 4-patient seed baseline. The latest full test run passed
35 tests; integration-test records brought the live patient count to 16.
Exotel calls remain restricted to numbers in the consent register.

The capstone delivery workflow, demonstration sequence, evaluation phases, and
evidence requirements are maintained in
[CAPSTONE_EXECUTION_PLAN.md](CAPSTONE_EXECUTION_PLAN.md).


Review-Report

## Team Members

```
Name Registration Number
Koppesh P 23BAI
Abdul Khader 23BAI
Santhosh Kumar 23BAI
```

Review-Report

## Review 1 – 5 Marks

No. Evaluation Parameter Marks Assessment Focus Mapped
CO(s)

1 Project title and technical
relevance

```
1 Specific, meaningful and aligned with the se-
lected domain/problem.
```
#### CO2, CO

2 Abstract and problem defini-
tion

```
1 Clearly states the context, problem and need
for the proposed work.
```
#### CO2, CO

3 Project objectives and ex-
pected outcome

```
1 Objectives and expected outcomes are clearly
defined and achievable.
```
#### CO2, CO

4 Scope and feasibility 1 Achievable within the semester and available
resources.

#### CO1, CO

5 Preliminary work plan 1 Presents an initial timeline, milestones and al-
location of responsibilities.

#### CO1,

#### CO3, CO

```
Total 5
```

Review-Report

## 1 Project Title and Technical Relevance

### Project Title

GOLDEN: Guideline-grounded Orchestrated LLM Dispatch for Emergency Networks
(An India-Grounded, Guideline-Compliant Decision-Support Framework for Pre-Hospital Emergency
Coordination Using Orchestrated LLM Agents)

### Technical Relevance

The project sits at the intersection of multi-agent AI orchestration and healthcare interoperability
standards, and is deliberately aligned with the Indian emergency-care domain rather than a generic
international framing. Its technical relevance rests on the following points:

- Multi-agent orchestration: The system is built on LangGraph, a stateful, cyclic graph-based or-
    chestration framework, using an orchestrator–specialist pattern with a shared, strongly-typed state
    object (Pydantic v2), conditional edges, retry cycles, and durable checkpointing – representing
    current, production-relevant practice in agentic AI system design rather than a simple prompt-
    chaining pipeline.
- Standards-compliant interoperability: The system is grounded in HL7 FHIR R4, the same
    standard underlying India’s Ayushman Bharat Digital Mission (ABDM). Patient pre-registration
    is implemented as an actual FHIR bundle (Patient + Encounter + Condition resources)
    served via a HAPI FHIR server, making the project directly relevant to India’s national health-data
    interoperability push rather than a closed, proprietary data model.
- India-grounded problem framing: Unlike comparable capstone projects that default to a US-
    centric frame (911, ESI triage, HIPAA), this project is explicitly re-anchored on India’s 108/
    emergency response services, ABDM/ABHA, and the MoRTH Cashless Treatment of Road Acci-
    dent Victims Scheme, 2025 – making the technical design choices verifiable against real, current
    Indian regulatory and clinical standards.
- Applied benchmarking against an established research baseline: The triage/EHR-interaction
    agent is benchmarked against MedAgentBench, a peer-reviewed multi-agent clinical-agent bench-
    mark (Jiang et al., NEJM AI, 2025), situating the project’s technical claims against a verifiable,
    published baseline rather than only self-reported metrics.
- Deterministic safety engineering alongside LLM reasoning: The design combines a determin-
    istic, rule-based “hard-SOS” bypass with LLM-based reasoning – a technically relevant contri-
    bution because it directly addresses a known failure mode of LLM-based systems (unpredictable
    latency and hallucination) in a safety-critical setting.


Review-Report

## 2 Abstract and Problem Definition

### Abstract

India records the world’s highest absolute road-crash death toll, with the National Crime Records Bu-
reau’s Accidental Deaths & Suicides in India (ADSI) 2024 report citing approximately 1.99 lakh traffic-
related deaths in 2024 (up from 1.98 lakh in 2023) – averaging 546 deaths per day. Despite this scale,
the “golden hour” following a crash is routinely lost to fragmented, manual coordination between In-
dia’s 108 ambulance service, the 112 Emergency Response Support System (ERSS), and hospitals. This
project proposes a multi-agent AI decision-support system that parallelizes emergency dispatch triage,
hospital and bed selection, FHIR-based patient pre-registration, and autonomous family notification –
tasks that are today performed serially and manually by a human dispatcher over the phone. The system
is implemented as a stateful, cyclic LangGraph orchestration of a focused four-agent core (Coordinator,
Triage/Dispatcher, Hospital & Bed, and Family-Notification Voice Agent), grounded in Indian clinical
and regulatory standards (108/112, ABDM/FHIR R4, the May 2025 Golden-Hour Cashless Treatment
Scheme), and is explicitly positioned as decision support for human dispatchers rather than autonomous
medical decision-making.

### Problem Definition

The economic burden of India’s road-crash toll is severe: MoRTH estimates the socio-economic cost at
approximately INR 1,47,114 crore (0.77% of GDP), rising to an estimated INR 5,96,820 crore (3.14%
of GDP) once adjusted for underreporting, per the World Bank report Traffic Crash Injuries and Dis-
abilities: The Burden on Indian Society. Peer-reviewed studies indicate that fewer than one in four
road-traffic-accident victims reach a medical facility within the golden hour, and highway-based studies
report emergency care access times of 60 minutes or greater in the majority of cases. This gap was
formally recognized by the Supreme Court of India in S. Rajaseekaran v. Union of India & Ors. (
INSC 45, decided 8 January 2025), which held that the golden-hour provision under Section 162 of the
Motor Vehicles Act upholds the right to life under Article 21, and directed the Central Government to
frame an implementing scheme – leading to MoRTH’s Cashless Treatment of Road Accident Victims
Scheme, 2025, effective 5 May 2025.
Despite this policy push, India’s emergency response remains fragmented across the 108 ambulance
service, the 112 ERSS, and hospitals that are only beginning to interoperate through ABDM’s FHIR R
standard. In practice, the minutes between a crash and hospital admission are lost because a human
dispatcher must triage the call, separately locate a hospital with an available and appropriate bed, sep-
arately notify the victim’s family, and separately initiate patient registration paperwork – each step typ-
ically conducted over the phone, one after another, rather than in parallel. This project’s core problem
statement is therefore: there is currently no lightweight, standards-compliant, India-grounded system
that parallelizes emergency dispatch triage, hospital/bed selection, FHIR-based patient pre-registration,
and family notification using coordinated AI agents, while remaining safe, auditable, and explicitly
scoped as decision support rather than autonomous clinical decision-making.


Review-Report

## 3 Project Objectives and Expected Outcome

### 3.1 Primary Objectives

```
P1. Design and implement a stateful, cyclic multi-agent orchestration (LangGraph) that in-
gests an emergency report, performs guideline-grounded acuity triage, recommends the
optimal receiving hospital with bed availability, pre-registers the patient as a FHIR bun-
dle, and triggers a family-notification voice call – end to end, within a defined target
latency.
P2. Design and build an AI voice-calling agent for “Family Notification & Information-Gathering,”
bridging Exotel telephony with the Gemini Live conversational model through a custom
Python audio bridge, integrated as an asynchronous node using webhook-based state re-
sumption within the orchestration graph.
```
```
P3. Ground triage in Indian and standard clinical protocols, and demonstrate a deterministic
hard-SOS bypass that guarantees life-threatening cases skip LLM inference latency.
```
### 3.2 Secondary Objectives

```
S1. Handle code-mixed (Tamil–English) emergency input and measure the accuracy delta rel-
ative to English-only input.
S2. Quantify and mitigate cascading hallucination across agent handoffs, using schema vali-
dation and inter-agent verification.
S3. Demonstrate model tiering / offline fallback (a hosted 70B model versus a locally served
7–8B model) under simulated degraded connectivity.
S4. Benchmark the triage/EHR-interaction agent against MedAgentBench.
```
### 3.3 Expected Outcomes

1. A working, end-to-end multi-agent decision-support system that demonstrably reduces the num-
    ber of sequential manual steps between an emergency report and (a) a triaged, guideline-grounded
    acuity assessment, (b) a recommended hospital with confirmed simulated bed availability, (c) a
    written FHIR pre-registration bundle, and (d) an autonomous family notification call.
2. Quantitative evidence – via a set of ablation experiments (E1–E6) – that the multi-agent archi-
    tecture outperforms a single-agent baseline on triage accuracy, hallucination rate, and/or latency,
    along with a measured accuracy delta for code-mixed Tamil–English input relative to English-only
    input.
3. A demonstrated deterministic hard-SOS bypass that reliably routes life-threatening cases around
    LLM inference latency, and a working degraded-connectivity fallback using a locally served small
    language model.
4. A benchmark score for the system’s EHR-interaction agent on MedAgentBench, reported along-
    side the published baseline scores (Claude 3.5 Sonnet v2, GPT-4o, DeepSeek-V3, and open-
    weight models) for comparison.


Review-Report 3.3 Expected Outcomes

5. A standards-compliant artifact – a FHIR R4-based patient pre-registration flow directly relevant to
    ABDM – serving as a strong viva talking point and a differentiator from US-centric (911/HIPAA)
    student projects.
6. A rehearsed, live demonstration script covering an Indian-context incident, parallel hospital/triage
    coordination, the live voice call, the hard-SOS bypass, and connectivity-loss resilience.
7. Explicit documentation of ethical and regulatory positioning: the system is framed throughout
    as decision support rather than autonomous medical decision-making, uses only synthetic patient
    data, and restricts all automated voice calls to consented team members under simulated scenarios.


Review-Report

## 4 Scope and Feasibility

### 4.1 In Scope

LangGraph-based orchestration; a Triage Agent; a Hospital/Bed Agent operating over a FHIR server;
FHIR patient pre-registration; family voice-call integration; a live monitoring dashboard; an evaluation
harness with ablation studies; India-grounded guideline prompting; a safety/guardrail validation layer;
and a simulated ambulance/traffic visualization.

### 4.2 Out of Scope

Real patient data of any kind; real, unconsented call recipients; production hospital APIs; autonomous
(non-human-reviewed) medical diagnosis; production ABDM certification (sandbox environment only);
real traffic-signal control (SUMO simulation only, optional); and VLM-based medical trauma diagnosis
(limited to accident detection only, optional).

### 4.3 Feasibility Within Semester and Available Resources

The project was originally scoped as a 7-agent system, which was assessed as over-scoped for a 3–
person team within a single semester – demo value is concentrated in 3–4 agents, so the design has been
deliberately reduced to a focused four-agent core, with two further agents (route/ambulance visualiza-
tion and accident-detection vision) treated as optional stretch goals attempted only if the team is ahead
of schedule. This reduction is the single largest feasibility correction applied to the plan.
A second major feasibility risk was the original intention to self-host 70B-class open-weight models
(Llama-3.3-70B / Qwen-2.5-72B) via vLLM on student hardware. This is not achievable on typical
student hardware – self-hosting such models requires roughly two 80GB GPUs (or four 48GB cards at
4-bit quantization), which a single consumer GPU (8–24GB) cannot provide, and this approach would
fail at demo time. The plan has therefore been revised to use free-tier hosted inference (Groq’s free tier
for Llama 3.3 70B, Google Gemini 2.5 Flash’s free tier, and OpenRouter free models) for the primary
reasoning agents, with a small local model (Llama 3.1 8B or Qwen 2.5 7B) served via Ollama purely for
the offline-fallback demonstration – which is feasible on a laptop-class GPU.
Remaining feasibility considerations:

- Data access: High-value clinical datasets (e.g., MIMIC-IV-ED) require PhysioNet credentialing
    and CITI training, which involves an external approval turnaround – this is initiated at the very
    start of the project to avoid blocking later phases.
- Regulatory sandbox access: ABDM sandbox registration involves an external approval turnaround
    and is initiated early in the Foundations phase.
- Telephony/voice calling: The AI voice-calling agent is planned as one of the project’s strongest
    live-demo assets, built on Exotel’s WebSocket-based bidirectional voice-streaming applet for out-
    bound telephony, bridged to Google’s Gemini Live conversational model via a custom Python
    service. This pairing is technically verified and compatible: Exotel streams raw PCM telephony
    audio at 8 kHz, while Gemini Live natively accepts 16-bit PCM input at 16 kHz and returns 16-bit
    PCM output at 24 kHz over its own WebSocket session – the Python bridge’s resampling stages
    (8 kHz → 16 kHz on the way in, 24 kHz → 8 kHz on the way out, using numpy/scipy) map
    directly onto this format mismatch, and downstream call-result automation is handled via n8n


Review-Report 4.3 Feasibility Within Semester and Available Resources

```
webhooks. Feasibility is bounded by TRAI’s TCCCPR 2018 regulations: the demonstration is re-
stricted to consented team phones running synthetic scenarios, since production-scale automated
calling would require DLT telemarketer registration that is out of scope for an academic prototype
```
- this constraint applies regardless of the specific telephony/voice-model pairing used. A further
constraint is that Gemini Live’s free-tier quota (concurrent sessions and per-session audio dura-
tion) is considerably tighter than the free tier used for the project’s text-based reasoning agents,
and is accounted for when scheduling live-demo rehearsals.
- Optional agents as a safety valve: Route/ambulance visualization and the accident-detection
vision agent are explicitly kept optional, governed by a decision gate: if the core system is stable
once the integration phase is complete, at most one optional agent is added; if not, all optional
agents are cut in favor of deeper evaluation.
Taken together, the reduced agent count, the replacement of infeasible local model hosting with free-
tier hosted inference, and the staged/optional treatment of higher-risk components make the project’s
core deliverables achievable within the semester using resources realistically available to a student team
(free-tier API access, a consumer-grade GPU, and Dockerized open-source infrastructure).


Review-Report

## 5 Preliminary Work Plan

The project is planned for a 3–4 person team, structured into five phases, each with a clear focus, defined
milestones, and a concrete deliverable marking the end of that phase.

```
Phase Focus, Milestones & Deliverable
Phase 0 – Foundations Focus & Milestones: Initiate PhysioNet credentialing and CITI
training applications (all members); register for the ABDM sandbox;
obtain Groq/Gemini/OpenRouter API keys; stand up HAPI FHIR in
Docker and load synthetic Synthea patient data; freeze the problem
statement, taxonomy, and architecture diagram.
Deliverable: Working FHIR datastore, functioning LLM API calls,
project document v1, and a presentation skeleton.
Phase 1 – Core
Agents
```
```
Focus & Milestones: Build the Triage Agent with guideline prompts
and Pydantic schemas; build the Hospital/Bed Agent with FHIR
queries and pre-registration writes; build the LangGraph orchestra-
tor with state management, checkpointing, and the hard-SOS bypass;
design and build the voice-calling agent and integrate it via webhook-
based asynchronous resumption. Responsibilities are allocated across
team members by agent.
Deliverable: An end-to-end “happy path” – text input through triage,
hospital selection, FHIR write, and a fired voice call.
Phase 2 – Integration,
Safety & Dashboard
```
```
Focus & Milestones: Add the guardrail/validation layer and inter-
agent verification for hallucination mitigation; build the live dash-
board (state, map, call status); implement the code-mixed input path
with Whisper STT; add model-tiering / offline fallback via Ollama.
Deliverable: Integrated demo v1 with an internal dry run.
Phase 3 – Evaluation
& Experiments
```
```
Focus & Milestones: Build the evaluation harness; run ablation ex-
periments E1–E6, including the MedAgentBench benchmark run; at-
tempt optional agents (route visualization, SUMO, vision) only if the
core system is already stable.
Deliverable: Results tables and ablation charts.
Phase 4 – Writing &
Polish
```
```
Focus & Milestones: Draft the research paper for arXiv submission;
finalize the written report and presentation; rehearse the demo script
with a contingency buffer for failures.
Deliverable: Submission-ready paper and final viva package.
```
### Decision Gate

Once the core four-agent system is stable and the Phase 1–2 deliverables are complete, the team adds
exactly one optional agent (route visualization is recommended over SUMO or the vision agent). If the
core is not yet stable at that point, all optional agents are cut and the remaining effort is reinvested into
evaluation depth.


Review-Report

### Change Triggers

- If free-tier LLM rate limits are hit during rehearsal, add a small OpenRouter credit top-up to raise
    the daily request floor and pre-cache demo runs in advance.
- If code-mixed (Tamil–English) accuracy proves too low, narrow the scope to Tamil–English only
    and report this as a finding rather than a failure.
- If MCP (Model Context Protocol) integration slips, it is dropped, since it is scoped as a stretch
    goal rather than a dependency.


Review-Report

## 6 Literature Review

Fifteen sources were reviewed across four thematic clusters: (i) multi-agent emergency dispatch and
clinical decision-support architectures, (ii) FHIR/EHR-interaction benchmarks for LLM agents, (iii)
India-specific emergency-medical-service (EMS) evidence, and (iv) LLM-based triage safety and multi-
agent reliability. Together, these clusters motivate the project’s architecture, its choice of evaluation
metrics, and the specific research gap it targets.

### 6.1 Multi-Agent Emergency Dispatch and Clinical Decision Support

Li et al. (2026) present DispatchMAS, a taxonomy-grounded multi-agent emergency dispatch simulator
built on AutoGen, in which LLM caller and dispatcher agents conduct structured calls across 32 chief-
complaint categories and a six-phase protocol. Evaluated on 100 simulated dispatch cases derived from
de-identified MIMIC-III records, it achieved 94% correct potential-agent contact and 97% correct call-
back advice, with inter-rater agreement (Gwet AC1) above 0.70. This is the closest direct precedent for
the project’s Dispatcher/Triage Agent and its structured, protocol-constrained call flow; however, it is an
English-oriented proof of concept with no real ambulance outcomes and no India-specific or code-mixed
input, which this project addresses directly.
Ibrahim et al. (2026) present TriAgent, an adaptive multi-agent architecture for crisis clinical decision
support under incomplete information, combining an orchestrator, retrieval sub-agent, clinical assess-
ment and medication/allergy checks, a critique agent, and parallel safety verification. Evaluated on 1,
MIMIC-IV-ED presentations with synthesized incomplete information, it reported 85.0% critical-case
recall and 65.7% overall triage accuracy, substantially outperforming matched single-model/retrieval
baselines (at most 14.7% critical-case recall). Its combination of adaptive orchestration, retrieval, cri-
tique, and an explicit safety layer is architecturally close to this project’s own Coordinator + specialist-
agent design, and is used as the primary architectural benchmark for comparison, with this project’s
contribution being an India-grounded emergency-coordination focus (triage and hospital/bed selection
and family notification and registration) rather than clinical triage alone.

### 6.2 FHIR / EHR-Interaction Benchmarks

Jiang et al. (2025) introduce MedAgentBench, an interactive benchmark in which LLM agents must
retrieve information and perform clinically meaningful actions inside a FHIR-compliant virtual EHR,
rather than answering static questions. Across 300 clinician-written tasks and 100 virtual patient profiles,
Claude 3.5 Sonnet v2 achieved the strongest reported overall success rate (69.67%), ahead of GPT-4o
(64.00%) and Gemini 1.5 Pro (62.00%). This is the primary precedent for benchmarking this project’s
Hospital/FHIR Agent, and the project reuses MedAgentBench directly (Experiment E6) to situate its
EHR-interaction agent against a published, reproducible baseline.
Lee et al. (2025/2026) present FHIR-AgentBench, which separates FHIR resource retrieval from
answer generation across 2,931 clinician-sourced question-answer pairs derived from MIMIC-IV-FHIR.
The strongest baseline reached only about 50% answer correctness, and multi-turn retrieval (71% recall)
substantially outperformed single-turn retrieval (58% recall) – evidence that naive single-shot FHIR
querying is inadequate and that full-context prompting over large FHIR bundles is impractical. This
directly informs the Hospital/Bed Agent’s design, which issues targeted, iterative FHIR queries rather
than attempting to load entire patient records into context.


Review-Report 6.3 Clinical Multi-Agent Benchmarking Beyond Static QA

### 6.3 Clinical Multi-Agent Benchmarking Beyond Static QA

Schmidgall et al. (2026) present AgentClinic, a multimodal benchmark in which doctor, patient, mea-
surement, and moderator agents interact sequentially under incomplete information, across nine spe-
cialties and seven languages. Reducing the number of allowed interactions from 20 to 10 dropped
diagnostic accuracy from roughly 52% to 25%, and a persistent “Notebook” memory tool improved a
Llama-3 agent’s performance by up to 92% (relative). This paper is the strongest justification in the
reviewed set for evaluating the project’s agents interactively – including a Tamil–English multilingual
experiment – rather than relying only on static, single-turn question answering.

### 6.4 India-Specific Emergency Medical Service Evidence

Gaikwad et al. (2025) retrospectively studied 315 road-traffic-accident victims at a tertiary hospital in
Sangli, India, finding that only 20.6% reached care within the golden hour, with transport problems
(33%), financial barriers (30.5%), unawareness of nearby facilities (14.6%), and language issues (13.3%)
cited as the leading obstacles. This is the project’s strongest India-specific empirical motivation, and its
obstacle table maps directly onto the coordination failures the proposed system targets (transport/routing,
hospital awareness, and language-aware interaction).
Jena et al. (2024) examined Maharashtra’s 108 EMS system, where ambulance-based doctors also
provide general consultations; the state recorded 935,544 such consultations in 2022, a 452% increase
over 2020, demonstrating the scale of existing Indian EMS infrastructure that an AI coordination layer
could augment. Modi et al. (2018) surveyed 1,220 respondents in Maharashtra and found that while
76.2% recognized the 108 number, only 20.2% had ever called it, and 82.9% preferred a unified emer-
gency number – underscoring that any technical solution must also account for public awareness and
usability. Together, these two studies support the project’s explicit framing as a layer that augments
existing 108/112 infrastructure and human dispatchers, rather than replacing them.

### 6.5 LLM-Based Triage: Feasibility and Safety Evidence

Shekhar et al. (2025) tested a general-purpose LLM (ChatGPT-4o Mini) against a critical-care paramedic
panel on 392 real ambulance requests, finding 76.5% agreement overall and 93.8% agreement when the
panel was unanimous – direct evidence that LLM-assisted prioritization is feasible, though the study
evaluates relative ranking only, not end-to-end latency or patient outcomes.
Set against this, Cui et al. (2026) conducted a systematic review and meta-analysis of 11 studies
(3,088 cases) on LLM emergency-department triage, finding pooled sensitivity of only 61% (95% CI
48–73%) for the highest-acuity category, despite high specificity (97%) – with very high heterogeneity
(I^2 =97%) across studies. This is the key paper motivating the project’s deterministic hard-SOS by-
pass: it demonstrates that LLM-only triage cannot be trusted to reliably catch the most critical cases, so
critical-case detection must not depend on LLM inference alone.
Shen et al. (2025) show that knowledge-grounded, ESI-instruction-tuned models (their MIETIC/SDTA
approach, best demonstrated on Qwen2.5-72B) achieve near-perfect high-risk recall (1.00) and strong
overall accuracy (0.91), supporting the value of guideline grounding over open prompting – directly
motivating Experiment E2 (guideline-grounded vs. open prompting). Wang et al. (2025) and Gaber et
al. (2025) provide further precedent for evaluating triage, referral, and RAG-assisted clinical workflows
using GPT-4o/GPT-4-Turbo and Claude 3.x respectively, reinforcing that prompt design and retrieval
grounding are experimental variables worth measuring explicitly rather than fixed choices.


Review-Report 6.3 Clinical Multi-Agent Benchmarking Beyond Static QA

Finally, Walonoski et al. (2018) introduce Synthea, the open-source synthetic patient simulator
(with native FHIR/C-CDA export) that underlies this project’s synthetic patient datastore, allowing safe
demonstration and testing without exposing real patient information.

### 6.6 Multi-Agent Reliability and Cascading Errors

Lin et al. (2026) introduce AgentAsk, which identifies four recurring failure modes at agent-to-agent
handoffs – Data Gap, Signal Corruption, Referential Drift, and Capability Gap – and proposes a lightweight
clarification mechanism that improved accuracy by up to 4.69% while keeping added latency and cost
under 10% of baseline overhead. This is the main paper underlying the project’s cascading-hallucination
research gap (Experiment E1) and directly motivates the Pydantic schema-validation and inter-agent ver-
ification layer used at every hand-off between the Coordinator and its specialist agents.

### 6.7 Summary Table

No. Title (short) Authors,
Year

```
Key Result Relevance to
Project
```
1 DispatchMAS Li et al., 2026 94% correct agent contact; 97%
correct callback advice; Gwet AC
>0.

```
Precedent for
Dispatcher/Triage
Agent and struc-
tured call flow
```
2 MedAgentBench Jiang et al.,
2025

```
Claude 3.5 Sonnet v2: 69.67%
overall success on FHIR-based
EHR tasks
```
```
Primary bench-
mark for the
Hospital/FHIR
Agent (Experi-
ment E6)
```
3 AgentClinic Schmidgall
et al., 2026

```
Accuracy drops from ∼52% to
∼25% with fewer interaction turns
```
```
Justifies interac-
tive, multi-turn,
multilingual
evaluation
```
4 FHIR-AgentBench Lee et al.,
2025/

```
Best baseline ∼50% answer cor-
rectness; multi-turn beats single-
turn retrieval
```
```
Informs iterative,
targeted FHIR
querying design
```
5 Golden Hour in RTA
Victims

```
Gaikwad et
al., 2025
```
```
Only 20.6% reached care
within the golden hour; trans-
port/finance/language barriers
```
```
Core India-
specific problem-
statement evi-
dence
```
6 Maharashtra 108 EMS
Access

```
Jena et al.,
2024
```
```
935,544 consultations in 2022;
452% growth over 2020
```
```
Confirms scale of
existing EMS to
augment, not re-
place
```

Review-Report 6.8 Research Gap

No. Title (short) Authors,
Year

```
Key Result Relevance to
Project
```
7 Public Awareness of
EMS

```
Modi et al.,
2018
```
```
76.2% knew 108; only 20.2% had
ever called it
```
```
Motivates
usability/awareness-
aware design
```
8 LLM Ambulance Dis-
patch & Triage

```
Shekhar et
al., 2025
```
```
76.5% agreement with paramedic
panel (93.8% when unanimous)
```
```
Feasibility prece-
dent for the Triage
Agent
```
9 LLM ED Triage Meta-
Analysis

```
Cui et al.,
2026
```
```
Pooled sensitivity only 61% for
highest-acuity triage
```
```
Motivates the
deterministic
hard-SOS bypass
```
10 Knowledge-Embedded
LLM Triage

```
Shen et al.,
2025
```
```
Qwen2.5-72B: 1.00 high-risk re-
call with guideline grounding
```
```
Motivates
guideline-
grounded prompt-
ing (Experiment
E2)
```
11 LLM ED Triage &
Guidance

```
Wang et al.,
2025
```
```
GPT-4-Turbo: 100% MEWS accu-
racy after prompt engineering
```
```
Precedent for
triage and
hospital-routing
evaluation
```
12 LLM Clinical Decision
Workflows

```
Gaber et al.,
2025
```
```
Claude 3.5 (clinical): 64.40% exact
triage; RAG workflow 65.75%
```
```
Supports RAG-
grounded, multi-
decision workflow
design
```
13 Synthea Walonoski et
al., 2018

```
Large-scale synthetic patient gen-
eration with FHIR export
```
```
Underlies the
project’s synthetic
FHIR datastore
```
14 AgentAsk Lin et al.,
2026

```
Up to 4.69% accuracy gain from
handoff clarification,<10% over-
head
```
```
Basis for schema
validation / inter-
agent verification
(E1)
```
15 TriAgent Ibrahim et
al., 2026

```
85.0% critical-case recall vs.
≤14.7% for baselines
```
```
Closest architec-
tural benchmark
for the four-agent
design
```
### 6.8 Research Gap

Across all fifteen sources, no single study combines: (a) an India-grounded emergency-response context
with documented, India-specific access barriers (transport, cost, awareness, and language); (b) native
handling of code-mixed Tamil–English emergency speech; (c) a multi-agent architecture that paral-


Review-Report 6.8 Research Gap

lelizes triage, hospital/bed selection, FHIR-based pre-registration, and family notification, rather than
addressing only clinical triage (DispatchMAS, TriAgent) or only FHIR/EHR retrieval (MedAgentBench,
FHIR-AgentBench) in isolation; (d) a deterministic, non-LLM-dependent bypass for the highest-acuity
cases, directly motivated by the safety gap Cui et al. (2026) expose in LLM-only triage; and (e) explicit,
measured mitigation of cascading errors across agent handoffs using the AgentAsk (Lin et al., 2026)
failure taxonomy. This project is positioned to fill that combined gap, and its planned ablation exper-
iments (E1–E6, defined in the Proposed Methodology) are each traceable to a specific paper reviewed
above.


Review-Report

## 7 System Architecture

### 7.1 Architectural Pattern

The system follows an orchestrator–specialist multi-agent pattern, implemented as a stateful, cyclic
graph in LangGraph. A single Coordinator agent owns a shared, strongly-typed state object (Pydan-
tic v2) and routes execution to specialist agents via conditional edges. The graph supports retry cycles,
interrupt()-based human-in-the-loop breakpoints, and durable checkpointing (SQLite/PostgreSQL),
which is what allows the graph to pause for minutes while an asynchronous voice call is in progress and
then resume exactly where it left off.

### 7.2 Component Overview

Coordinator / Orchestrator
Receives the incoming emergency report, performs the deterministic hard-SOS check first (by-
passing all LLM calls for unambiguous life-threatening cases), then fans work out to the Triage
Agent and Hospital/Bed Agent in parallel, merges their outputs, and triggers the Voice Agent.

Triage / Dispatcher Agent
Parses the incident report (text or Whisper-transcribed speech, including Tamil–English code-
mixed input), assigns an acuity level using guideline-grounded prompting, and returns a schema-
validated triage object.

Hospital & Bed Agent
Queries the FHIR server (HAPI FHIR, pre-loaded with Synthea synthetic data) for candidate
hospitals, checks a simulated bed-availability table, ranks candidates by acuity and distance, and
writes the FHIR pre-registration bundle (Patient + Encounter + Condition).

Voice Agent (Family Notification & Info-Gathering)
An Exotel outbound call is triggered via webhook; a Python audio bridge resamples audio be-
tween Exotel’s 8 kHz telephony stream and the Gemini Live model’s 16 kHz input / 24 kHz
output, while n8n handles posting the final call outcome back to the orchestrator, resuming the
paused graph.

Safety / Validation Layer
Wraps every agent’s output in Pydantic schema gates and deterministic rule checks, plus a single
hosted moderation call, directly motivated by the AgentAsk handoff-failure taxonomy discussed
in the Literature Review.

Dashboard
A live view of in-flight cases, agent state, and call status, used both for demonstration and as a
human-in-the-loop review point.

### 7.3 Data Flow

1. An incident report (text or transcribed speech) enters the Coordinator.
2. The Coordinator performs the hard-SOS check. Life-threatening cases are routed immediately to
    the Hospital & Bed Agent, skipping LLM-based triage latency entirely.


Review-Report 7.4 Architecture Diagram

3. For all other cases, the Triage Agent and Hospital & Bed Agent run in parallel – triage against the
    guideline knowledge base, and hospital/bed lookup against the FHIR server – rather than serially,
    as a human dispatcher would.
4. The Coordinator merges both outputs, writes the FHIR pre-registration bundle, and asynchronously
    triggers the Voice Agent.
5. The graph checkpoints and pauses; execution resumes when the Voice Agent’s call-completed
    webhook returns (allergies, medications, consent, blood group, etc.).
6. The Safety/Validation Layer checks every hand-off along the way; the Dashboard reflects state
    changes in real time.

### 7.4 Architecture Diagram

```
Figure 1: System architecture
```

Review-Report

## 8 Design of Proposed Methodology and System Design

### 8.1 Design Philosophy and Guiding Principles

The design of GOLDEN is governed by four principles, each chosen to directly address a gap or risk
identified in the Literature Review:

- Decision support, not replacement. The system augments a human dispatcher’s parallel-processing
    capacity; it never issues a final clinical or dispatch decision without a human review point (via
    LangGraph’s interrupt() breakpoints), consistent with the project’s ethical positioning stated
    throughout this report.
- Safety-by-design over probabilistic-only reasoning. Because Cui et al. (2026) show LLM-
    only triage misses up to 39% of the most critical cases, the highest-acuity path is handled by a
    deterministic rule engine before any LLM is invoked, not as a post-hoc check on an LLM’s output.
- Fail-safe degradation over hard failure. Every external dependency (hosted LLM APIs, the
    voice/telephony stack) has a defined fallback path (local model tiering, logged failed callbacks)
    so a single component outage degrades the system’s capability rather than stopping it entirely.
- Auditability by construction. Every inter-agent hand-off is schema-validated and logged, di-
    rectly motivated by the AgentAsk handoff-failure taxonomy (Data Gap, Signal Corruption, Ref-
    erential Drift, Capability Gap) discussed in the Literature Review, so failures are traceable to a
    specific agent and a specific failure mode rather than surfacing as an opaque end-to-end error.

### 8.2 Proposed Methodology

The project’s methodology combines deterministic rule-based engineering for safety-critical decisions
with LLM-based agentic reasoning for open-ended interpretation (free-text/speech triage, guideline
application, conversational information-gathering), coordinated through a stateful multi-agent graph.
This hybrid approach is deliberately evaluated, not assumed: every major design choice is paired with a
controlled ablation experiment, so that the panel and any subsequent reviewer can see evidence for why
each component is included, rather than taking the architecture on faith.

Ablation and Evaluation Experiments

E1 – Core Architecture Ablation
Single-agent (one LLM performs the entire pipeline end to end) versus the full multi-agent
pipeline, compared on triage accuracy/F1, hallucination rate, and latency. Tests whether multi-
agent decomposition is actually justified, motivated by DispatchMAS and TriAgent’s reported
gains over single-model baselines.

E2 – Prompt Grounding Ablation
Guideline-grounded prompting versus open/unconstrained prompting for the Triage Agent,
compared on triage F1 and high-risk recall. Directly tests the finding from Shen et al. (2025),
where guideline grounding drove high-risk recall from well below 1.00 to 1.00.

E3 – Safety Bypass Ablation
The deterministic hard-SOS path versus an LLM-only decision path for the highest-acuity


Review-Report 8.3 System Design

```
cases, compared on latency and critical-case miss rate. Directly tests the safety gap identi-
fied by Cui et al. (2026) (61% pooled sensitivity for highest-acuity LLM triage).
```
E4 – Multilingual Robustness
English-only input versus Tamil–English code-mixed input, measuring the resulting triage ac-
curacy delta and the Whisper word-error-rate (WER) increase. Addresses the language barrier
identified as a contributing factor in 13.3% of golden-hour failures by Gaikwad et al. (2025).

E5 – Tiering / Offline Resilience
A hosted 70B-class reasoning model versus the locally served 7–8B fallback model, compared
on output quality, latency, and availability under simulated connectivity loss.

E6 – External Benchmark Validation
The Hospital & Bed (EHR-interaction) Agent evaluated on MedAgentBench, with results re-
ported directly against its published baseline scores (Claude 3.5 Sonnet v2, GPT-4o, DeepSeek-
V3), so the project’s own benchmark claim is independently comparable rather than self-
defined.

### 8.3 System Design

Shared State Design

All agents read from and write to a single, strongly-typed Pydantic v2 state object owned by the Co-
ordinator – this is the backbone that lets the graph pause for an asynchronous voice call and resume
correctly. Its design groups fields into five categories:

- Case identity & input: case ID, raw input (text or transcript), detected language, input modality.
- Triage output: acuity level, hard-SOS flag, confidence score, guideline reference used.
- Hospital/FHIR output: ranked hospital candidates, selected hospital, bed-confirmation status,
    FHIR bundle ID.
- Voice/family-notification output: call status, consent flag, collected information (allergies, med-
    ications, blood group), retry count.
- Control & audit: current graph node, validation errors from the Safety Layer, checkpoint ID,
    timestamps for each stage transition (used later for latency evaluation in E1–E3).

Per-Agent Algorithmic Design

Hard-SOS Rule Engine
A deterministic, non-LLM keyword and pattern matcher checked first against a fixed, reviewed
list of unambiguous critical indicators (e.g., unresponsive, not breathing, no pulse, severe un-
controlled bleeding, cardiac arrest). Design goal: zero LLM calls, sub-second latency, and a
false-negative rate close to zero even at the cost of some false positives (which merely route a
case through the fast path unnecessarily rather than causing harm).

Triage Agent
Constructs a guideline-grounded prompt (drawing on a curated Indian/standard clinical guide-
line knowledge base), generates a structured output constrained to a fixed JSON schema (acuity


Review-Report 8.3 System Design

```
level, confidence, rationale), and rejects/retries any output that fails schema validation before it
is written to shared state.
```
Hospital & Bed Agent
Issues targeted, iterative FHIR queries (informed by the FHIR-AgentBench finding that multi-
turn retrieval outperforms single-shot retrieval) rather than loading full patient bundles into
context; ranks candidate hospitals with a weighted scoring function over acuity match, distance,
and live bed availability; writes the FHIR pre-registration bundle as an idempotent, retry-safe
transaction so a network retry cannot create duplicate patient records.

Voice Agent
Fires the outbound call as a non-blocking, asynchronous task; defines a fixed webhook contract
for the call-completion callback (status, transcript, extracted fields); on callback failure, persists
the payload for manual recovery rather than silently dropping it, and resumes the checkpointed
graph exactly at the node where it paused.

Safety / Validation Layer
Applied uniformly at every hand-off: (1) Pydantic schema gate, (2) deterministic rule checks
(e.g., value ranges, required fields), (3) a single hosted moderation call. A failure at any stage
routes back to the originating agent for a bounded number of retries before escalating to a
human-in-the-loop breakpoint, rather than propagating a bad value forward.

Design Patterns Employed

- Orchestrator–worker pattern: the Coordinator owns control flow and shared state; specialist
    agents are stateless with respect to anything not explicitly passed to them, which keeps each agent
    independently testable.
- Circuit-breaker / fallback pattern: hosted-model calls that fail or exceed a latency threshold
    trigger a fallback to the locally served model, rather than blocking the whole pipeline.
- Idempotent-writer pattern: FHIR bundle writes and voice call triggers are designed to be safely
    retryable without creating duplicate patients or duplicate outbound calls.
- Checkpoint-and-resume pattern: the LangGraph checkpointer persists state at every node tran-
    sition, which is what allows the graph to survive a multi-minute pause during the voice call and
    resume deterministically from the webhook callback.


Review-Report References

## References

```
[1] Li, X. et al., “DispatchMAS: Fusing Taxonomy and Artificial Intelligence Agents for Emergency
Medical Services,” BMC Emergency Medicine, 2026. DOI: 10.1186/s12873-026-01540-9.
[2] Jiang, Y., Black, K.C., Geng, G., Park, D., Zou, J., Ng, A.Y., Chen, J.H. et al., “MedAgent-
Bench: A Virtual EHR Environment to Benchmark Medical LLM Agents,” NEJM AI, 2025. DOI:
10.1056/AIdbp2500144.
```
```
[3] Schmidgall, S., Ziaei, R., Harris, C. et al., “AgentClinic: A Multimodal Benchmark for Tool-Using
Clinical AI Agents,” npj Digital Medicine, 2026. DOI: 10.1038/s41746-026-02674-7.
```
```
[4] Lee, G., Bach, E., Yang, E., Pollard, T., Johnson, A., Choi, E., Jia, Y., Lee, J.H., “FHIR-
AgentBench: Benchmarking LLM Agents for Realistic Interoperable EHR Question Answering,”
Machine Learning for Health, PMLR 297, 2025/2026.
```
```
[5] Gaikwad, S.A., Shinde, V.D., Kothavale, S.P., “‘Golden Hour’ in Road Traffic Accident Victims:
Hurdles and Impact on Mortality,” Cureus, 2025. DOI: 10.7759/cureus.78772.
```
```
[6] Jena, B.N., Shelke, D., Saunik, S., “Can the Emergency Medical Service (EMS) System Help in
Improving Healthcare Access – Evidence from Maharashtra EMS,” Indian Journal of Community
Medicine, 2024. DOI: 10.4103/ijcm.ijcm 448 23.
[7] Modi, P.D. et al., “Public Awareness of the Emergency Medical Services in Maharashtra, India: A
Questionnaire-based Survey,” Cureus, 2018. DOI: 10.7759/cureus.3309.
```
```
[8] Shekhar, A.C. et al., “Use of a Large Language Model (LLM) for Ambulance Dispatch and Triage,”
American Journal of Emergency Medicine, 2025. DOI: 10.1016/j.ajem.2024.12.032.
```
```
[9] Cui, L. et al., “Diagnostic Accuracy of Large Language Models for Emergency Department
Triage: A Systematic Review and Meta-analysis,” BMC Emergency Medicine, 2026. DOI:
10.1186/s12873-026-01639-z.
```
[10] Shen, Q., Zhang, X., Ren, H., Guo, Q., Yi, Z., “Knowledge-Embedded Large Language Models
for Emergency Triage,” Knowledge-Based Systems, 2025. DOI: 10.1016/j.knosys.2025.113431.

[11] Wang, C., Wang, F., Li, S. et al., “Patient Triage and Guidance in Emergency Departments Using
Large Language Models: Multimetric Study,” Journal of Medical Internet Research, 2025. DOI:
10.2196/71613.

[12] Gaber, F., Shaik, M., Allega, F. et al., “Evaluating Large Language Model Workflows in Clini-
cal Decision Support for Triage and Referral and Diagnosis,” npj Digital Medicine, 2025. DOI:
10.1038/s41746-025-01684-1.

[13] Walonoski, J. et al., “Synthea: An Approach, Method, and Software Mechanism for Generating
Synthetic Patients and the Synthetic Electronic Health Care Record,” Journal of the American
Medical Informatics Association, 2018. DOI: 10.1093/jamia/ocx079.

[14] Lin, B. et al., “AgentAsk: Multi-Agent Systems Need to Ask,” Proceedings of ACL, 2026. DOI:
10.18653/v1/2026.acl-long.1294.


Review-Report References

[15] Ibrahim, A., AlSanousi, A., Serag, A., “TriAgent: An Adaptive Multi-Agent Architecture
for Crisis Clinical Decision Support Under Incomplete Information,” AI (MDPI), 2026. DOI:
10.3390/ai7060230.


