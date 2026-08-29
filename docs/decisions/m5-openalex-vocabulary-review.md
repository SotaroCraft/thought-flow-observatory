# M5 OpenAlex Vocabulary Review Outcome — Delegated

- Status: Completed for RF evidence packaging. **Not** Gate D freeze. **Not** vocabulary mutation.
- Management ID: TFO-M5-017
- Date: 2026-08-29
- Source of Truth: `docs/requirements.md` v1.0; frozen `implementation-plan.md` v1.0; `docs/decisions/m5-smoke-spec.md` §4.1 / §12.1 #6; `AGENTS.md`.
- Run: `3422ccef-6968-4c29-8b7b-74e182d88873` (immutable Raw; not modified)

---

## 1. Review mode (transparent)

| Field | Value |
|---|---|
| Required by | Smoke-spec §4.1 stratified positive / ambiguous-excluded review |
| Packet prepared by | Cursor (TFO-M5-016); local gitignored path only |
| Human instruction | Explicit: «全部自動で決定してください» (decide all automatically) |
| Adjudicator | ChatGPT under explicit Human delegation |
| Manual row-by-row Human clicking | **NO** |
| Claimed as manual Human row review | **MUST NOT** |
| Vocabulary changed | **NO** (`PROVISIONAL-M5-SMOKE/2026-08-23-r1` unchanged) |

This is a **Human-delegated AI-assisted semantic review**. It is recorded so RF #6 and Codex / Human finalists can judge sufficiency against the frozen “Human reviews” wording without mislabeling the method.

Local packet (not committed; contains display snippets):  
`workspace-data/m5-smoke/human-review/openalex-vocabulary-review-3422ccef.md`

---

## 2. Counts

| Decision | Count | Meaning |
|---|---:|---|
| AGREE | 62 | Expected classifier result semantically acceptable |
| DISAGREE | 11 | Classifier result judged semantically wrong / overly narrow rejection |
| UNSURE | 2 | Displayed snippet insufficient for confident judgment |
| **Total** | **75** | All packet rows adjudicated |

---

## 3. DISAGREE / UNSURE IDs (Gate D evidence; no auto vocabulary change)

**DISAGREE:** OA-REV-009, OA-REV-018, OA-REV-027, OA-REV-038, OA-REV-039, OA-REV-046, OA-REV-048, OA-REV-054, OA-REV-064, OA-REV-074, OA-REV-075

Pattern (non-normative summary): several disagreements are narrow provisional rejections of `AI-generated` / standalone `agent(s)` that the adjudicator judged thematically relevant. These are **limitations of the provisional smoke vocabulary**, not authority to expand terms in M5.

**UNSURE:** OA-REV-069, OA-REV-070 — insufficient displayed context.

---

## 4. Sampling gaps retained

- JP×generative_ai rejected pool: 4/5 (only four ambiguous/excluded candidates existed)
- KR×generative_ai rejected pool: 4/5
- KR×ai_agent positives: 2/5 (only two positives existed in the run)

---

## 5. RF §12.1 #6 mapping

| Element | State |
|---|---|
| Deterministic theme evidence inspectable | YES (title/abstract match fields + vocabulary version on run) |
| Basic positive/negative review recorded | YES — 75 rows with AGREE/DISAGREE/UNSURE under delegated mode |
| Text-field availability | YES (title and abstract-present / reconstructed abstract used in packet) |
| Limitation | Review method is Human-delegated AI-assisted, not manual Human row-by-row |
| Gate D | **Not frozen**; DISAGREE/UNSURE feed M6 vocabulary review |

Cursor recommendation: RF #6 = **SATISFIED WITH LIMITATION** (delegation transparency + provisional vocabulary narrowness). Final RF acceptance remains Human / Codex (§12 / §14.8).
