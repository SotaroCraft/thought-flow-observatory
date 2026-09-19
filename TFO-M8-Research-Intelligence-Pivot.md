# TFO Direction Change — M8+ Research Intelligence Core / Deep Research Intake

**Status:** HUMAN APPROVED DIRECTION CHANGE / PROGRAM CONTROL ADJUDICATION REQUIRED  
**Date:** 2026-08-31  
**Scope:** TFO M8 and later; M1–M7 foundation preserved unless Program Control identifies a concrete conflict  
**Authority:** Human directive  
**Normativity:** This document records the approved direction and requested Plan migration. It does not silently override `docs/requirements.md`, `implementation-plan.md`, or frozen `docs/decisions/*`. Program Control should translate this into the minimum required SoT / Decision updates.

---

## 1. Direction

TFO should no longer optimize primarily for doing research itself.

The new center of gravity is:

> **TFO owns what to analyze, how research should be specified, how returned research is decomposed, classified, scored, compared, integrated, and deepened. Research execution may be delegated to external Deep Research providers.**

In short:

> **Keep Research Intelligence inside TFO; externalize Research Labor.**

External Deep Research outputs are inputs to TFO, not final answers.

Potential providers include OpenAI Deep Research, Gemini Deep Research, Claude/other research systems, human researchers, and other evidence-producing workflows. Provider count is not itself a goal.

---

## 2. Background / motivating example

A Deep Research report on AI-driven personality / cognition / social transformation may contain, in the same artifact:

- empirical study results;
- associations;
- systematic or institutional evidence;
- interpretation;
- forecasts;
- causal hypotheses;
- investment inference;
- repeated citations to the same underlying study;
- apparently conflicting claims that are actually conditional on population / task / time / guardrails.

TFO should treat such a report as a **Research Artifact** and decompose it below report level.

The primary analytical unit should become the **Claim / Evidence unit**, not the report itself.

Example distinction:

```text
Research Artifact
  ↓
Claim A: GenAI reduced writing task time by ~40%
  ↓
Underlying Study / Evidence
  ↓
Population / Task / Study Design / Effect / Limits

Claim B: Humans may shift from "author" to "editor/supervisor" identities
  ↓
Inference / Forecast
  ↓
Supporting evidence links + inference distance + uncertainty
```

These must not be treated as equivalent evidence types.

---

## 3. New target loop

```text
TFO Questioning
  ↓
Research Specification
  ↓
External Deep Research / Research Provider
  ↓
Research Artifact
  ↓
Source / Study / Claim / Evidence extraction
  ↓
Normalization + Classification
  ↓
Citation resolution + underlying-evidence deduplication
  ↓
Corroboration / Contradiction / Conditionality analysis
  ↓
Scoring + quantitative representation
  ↓
Statistical / structured integration
  ↓
Integrated Finding
  ↓
Evidence strong ─────────→ Knowledge
Evidence weak/uncertain ─→ Reality Sensor monitoring
                              ↓
                         OpenAlex / Trends / future approved sensors
                              ↓
                         Confirmation / Weakening / Divergence
                              ↓
                         Next Research Question
                              ↺
```

TFO therefore remains responsible for:

- deciding what is worth analyzing;
- forming hypotheses / research questions;
- defining research scope and required evidence;
- asking for counter-evidence and boundary conditions;
- selecting or comparing Research Providers where useful;
- classifying and evaluating returned evidence;
- generating follow-up research questions.

External Research Providers perform search / discovery / reading / first-pass synthesis as delegated labor.

---

## 4. Core data-model impact

M8+ should evaluate introducing explicit concepts equivalent to:

```text
ResearchRun
ResearchArtifact
Source
Study
Claim
Evidence
Inference
Forecast
Finding
```

Exact schema is **not frozen by this document**.

Important principles:

1. **Claim is the primary comparison unit.**
2. Research reports are not independent evidence merely because different providers generated them.
3. Underlying citations / studies must be resolved sufficiently to detect evidence reuse.
4. Researcher agreement and evidence agreement must be distinguished.
5. Duplicate research-provider claims citing the same study must not be counted as independent corroboration.
6. Observation / Interpretation / Hypothesis separation from existing TFO methodology should be generalized, not discarded.

A useful conceptual classification is:

```text
L0 SOURCE / STUDY
L1 OBSERVATION / EMPIRICAL CLAIM
L2 INTERPRETATION / SYNTHESIS
L3 HYPOTHESIS / FORECAST / DECISION INFERENCE
```

This is conceptual only; Program Control should choose the minimum viable implementation.

---

## 5. Quantification / scoring direction

A major TFO capability should become conversion of qualitative research into structured, analyzable evidence without creating false precision.

TFO should distinguish at least two independent dimensions.

### A. Scientific / Evidence Support

Examples of inputs:

- number of unique underlying studies;
- independence / citation overlap;
- study design;
- sample / population;
- effect direction / effect size when actually available;
- replication / longitudinal status;
- consistency across domains;
- recency;
- source quality;
- inference distance;
- uncertainty.

### B. Real-world / Social Signal

Existing TFO sensors remain relevant for observing whether a proposition is visibly emerging in society even when scientific confidence is weak.

Examples:

- OpenAlex scholarly signal;
- Google Trends attention signal;
- future approved company / developer / other reality sensors.

Therefore one unified score should **not** be assumed.

A valid Finding may look conceptually like:

```text
Scientific Support: LOW / MEDIUM / HIGH (or anchored ordinal equivalent)
Social Momentum: LOW / MEDIUM / HIGH
Economic / Practical Impact: separate if justified
Uncertainty: explicit
```

Do not create precise decimal scores unless calibration and measurement semantics justify them.

Existing M6 principle of not forcing OpenAlex and Trends into one numerical index remains aligned with this direction.

---

## 6. Contradiction is a first-class signal

TFO should not merely count supporting vs opposing reports.

When evidence appears contradictory, classify whether the conflict is explained by moderators / boundary conditions such as:

- domain;
- task complexity;
- user expertise;
- guardrails;
- duration;
- population;
- geography;
- measurement method;
- time period.

A contradiction should be able to generate the next Research Specification.

Example:

```text
Initial claim:
AI reduces human thinking ability.

Evidence pattern:
Education → harm under some unguided conditions
Professional productivity → benefit
Creativity → individual quality up / collective diversity down
Critical thinking → lower self-reported effort with higher AI trust
Complex expert tasks → jagged frontier / failure outside model capability

Next question:
Decompose effect by expertise × guardrails × task complexity × duration.
```

This recursive deepening is a core TFO function.

---

## 7. Impact on existing milestones

### M1–M6

Preserve unless a concrete incompatibility is identified.

Especially preserve:

- immutable Raw principles;
- quality-state distinctions;
- Sensor ≠ society / social layer;
- Observation / Interpretation / Causal Hypothesis separation;
- frozen OpenAlex / Trends methodology contracts;
- country / time / dictionary boundaries already frozen.

### M7

**Do not discard.**

Reframe M7 as **Direct / Reality Sensor Foundation** rather than the sole foundation of TFO research capability.

The current bounded backfill should not expand into a general-purpose historical ingestion platform merely because more infrastructure can be built.

Program Control should reassess the minimum evidence needed to close M7 safely and move to the new M8 core.

### M8

This is the primary affected milestone.

Current M8 `Weekly Canonical and Reproducible Analysis` should be reconsidered as the start of the **Research Intelligence Core**.

Minimum direction:

```text
Research Artifact Intake
→ Claim / Evidence decomposition
→ Classification
→ Deduplication / Citation overlap
→ Corroboration / Contradiction
→ Qualitative-to-structured scoring
→ Integration
→ Finding
→ Reality Sensor follow-up when appropriate
```

Existing weekly Canonical analysis may remain as the Reality Sensor / validation subpath rather than being deleted.

### M9 — BigQuery

Reassess priority.

BigQuery parity may remain a bounded Portfolio / cloud-comparison validation, but it should not delay Research Intelligence Core work if the original MUST can be satisfied narrowly or if Requirements are formally changed.

No silent deletion of an existing MUST is authorized by this document. Program Control must explicitly adjudicate any Requirements change.

### M10

Reframe operations around both:

- Reality Sensor operation; and
- Research Artifact intake / classification / evidence integration lifecycle.

Do not build generalized orchestration prematurely.

### M11

Portfolio story should reflect the higher-level system:

> TFO structures heterogeneous research outputs and direct public-world sensors into auditable evidence, identifies agreement / contradiction / uncertainty, and recursively generates better research questions.

This is stronger than presenting TFO merely as an OpenAlex + Trends analysis pipeline.

---

## 8. Research Provider boundary

TFO should be Research-Provider agnostic at the conceptual boundary, but **must not build a generic provider framework prematurely**.

Start with the artifact format actually available from one Deep Research workflow and generalize only from demonstrated need.

Provider comparison may later measure dimensions such as:

- coverage;
- unique source discovery;
- citation quality;
- contradiction discovery;
- unsupported claims;
- cost;
- latency;
- overlap with other providers.

Provider agreement itself is not evidence independence.

---

## 9. Statistical direction

Use statistical methods only where the data semantics support them.

Possible future tools include:

- evidence maps;
- citation-overlap matrices;
- agreement / disagreement matrices;
- study-design stratification;
- effect-size meta-analysis where compatible effect data truly exists;
- sensitivity analysis;
- Bayesian or ordinal evidence aggregation where assumptions are explicit;
- moderator / subgroup analysis.

Do not force incompatible qualitative claims into pseudo-meta-analysis.

Do not invent effect sizes.

Do not treat report count as independent sample count.

---

## 10. Priority principle

The strategic change is:

**Before:** value centered on finding / acquiring better information.  
**After:** value centered on converting abundant heterogeneous research into structured, comparable, auditable knowledge and deciding what to investigate next.

Key statement:

> **As AI makes research generation abundant, TFO should become more valuable through classification, compression, evidence accounting, contradiction analysis, and recursive research design.**

---

## 11. Program Control requested action

Program Control should:

1. acknowledge this Human-approved direction change;
2. inspect current M7 state and avoid unnecessary M7 platformization;
3. preserve frozen M1–M7 invariants where compatible;
4. determine the minimum Requirements / Implementation Plan / Decision updates required;
5. propose a revised M8+ milestone sequence centered on Research Intelligence;
6. explicitly adjudicate any existing MUST that would be reduced, moved, or removed (especially BigQuery parity);
7. avoid implementing the new architecture before the revised boundary is reviewed / frozen;
8. preserve direct Reality Sensors as an independent validation path;
9. return to Human only for meaningful scope / requirement tradeoffs, not implementation details.

Suggested immediate next bounded action:

> **Program Control design review: produce the minimal M8+ migration plan and identify exactly which existing requirements / milestones require formal change. Do not reopen frozen M6 sensor methodology or expand M7 while doing so.**

---

## 12. Non-goals

This direction does **not** authorize:

- abandoning existing Reality Sensors;
- weakening M6 methodology;
- replacing evidence with LLM judgments;
- LLM-only scoring without anchored semantics;
- a universal scalar trust score;
- generic multi-provider platform engineering;
- automatic causal inference;
- automatic investment decisions;
- massive ontology / knowledge graph construction;
- reopening closed milestones without concrete conflict;
- silently changing frozen MUST requirements.

---

## 13. Human-approved conceptual thesis

> **TFO decides what to investigate and how it should be investigated. External Deep Research can return the research artifact. TFO then decomposes, classifies, scores, compares, integrates, stores, and deepens that evidence, while its direct sensors continue observing whether uncertain propositions emerge in the real world.**

This document is intended to preserve that direction until Program Control translates it into the repository's normative planning artifacts.
