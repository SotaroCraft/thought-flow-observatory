# M5 Bounded Sensor Smoke Specification

- Status: FROZEN (+ Erratum-001, + Erratum-002). No connector or backfill is implemented by this document.
- Source of Truth: `docs/requirements.md` v1.0, then frozen `implementation-plan.md` v1.0.
- Design inputs: `docs/decisions/m5-sensor-preflight.md` and its external-review PASS in `chatgpt-m5-preflight-review.md`.
- Scope: M5 smoke mechanics only.
- Requirements / AC coverage: FR-DATA-001, FR-DATA-003, FR-DATA-006–007, 12.2–12.5, 17.2–17.3, 19.1–19.3, TBD-001, AC-DATA-001, AC-DATA-003, AC-SEC-001, and the M5 Research Feasibility Gate.

This document freezes bounded requests, sample periods, retention caps, evidence fields, and stop rules so Cursor can implement M5 without inventing research methodology. It explicitly does **not** freeze M6 Gate A–E, the production dictionary, unit/population/denominator, social-layer proxy, Canonical time, country aggregation, multi-country counting, normalization, analysis indicator, threshold, or lead/lag rule. Any smoke result is evidence for those later decisions, not a decision itself.

## 1. Normative language and decision states

`MUST`, `MUST NOT`, `SHOULD`, and `MAY` are normative within this M5 task and cannot weaken the requirements.

Each candidate receives one M5 result:

| Result | Meaning |
|---|---|
| `SMOKE-PASS` | Every mandatory bounded request and evidence check completed; the candidate can be considered by M6. This is not production `GO`. |
| `SMOKE-PASS-WITH-LIMITATIONS` | Mechanics completed, but measured coverage, source semantics, or publication restrictions constrain later use. The limitations must be explicit. |
| `SMOKE-NO-GO` | A stated hard no-go condition was observed. Do not build its M7 connector. |
| `SMOKE-BLOCKED` | The smoke could not legally or technically run because a prerequisite, entitlement, permission, or terms decision is absent. This is not a valid zero. |

Cursor may calculate and report a recommended result. Human / Codex review owns source adoption and the RF decision. A candidate that passes M5 remains subject to M6 Gate A–E before Canonical or analysis use.

## 2. Fixed smoke calendar and common mechanics

### 2.1 Fixed periods

All date ranges are inclusive UTC calendar dates. Request parameters must preserve these exact boundaries, and the manifest must also record the equivalent half-open interval.

| ID | Inclusive dates | Half-open form | Meaning |
|---|---|---|---|
| `OA-START` | 2022-11-30 through 2022-12-04 | `[2022-11-30, 2022-12-05)` | Partial ISO 2022-W48. Tests the exact required start rather than silently adding 2022-11-28/29. |
| `OA-MID` | 2024-10-07 through 2024-10-13 | `[2024-10-07, 2024-10-14)` | Complete ISO 2024-W41, approximately midway between the start and latest smoke boundary. |
| `OA-RECENT` | 2026-08-10 through 2026-08-16 | `[2026-08-10, 2026-08-17)` | Latest complete ISO week before the 2026-08-23 design/access date. |
| `MONTH-START` | 2022-12-01 through 2022-12-31 | `[2022-12-01, 2023-01-01)` | First complete calendar month after the research boundary; used for GitHub, company, and arXiv bounded samples. |
| `MONTH-RECENT` | 2026-07-01 through 2026-07-31 | `[2026-07-01, 2026-08-01)` | Latest complete calendar month before this specification. |
| `TRENDS-FULL` | 2022-11-30 through 2026-08-16 | `[2022-11-30, 2026-08-17)` | Common Trends range ending at the latest complete ISO week. |

These periods are smoke fixtures, not the production week rule. M6 Gate C decides Canonical time and week semantics.

### 2.2 Shared quality states

Every query/cell must end in exactly one primary state; a record may additionally carry source-specific flags.

| State | Required meaning |
|---|---|
| `success` | The request succeeded, the requested observable scope was completely observed, and one or more qualifying results exist. (Added by Erratum-001.) |
| `zero` | The request succeeded, the requested population/window was demonstrably observable, and the source reported no qualifying result. |
| `missing` | A returned record lacks a requested attribute or the attribute is not applicable. It is not converted to zero. It is **not** a generic success label. |
| `unknown` | A returned observation exists, but country or another target attribute cannot be established from an allowed primary attribute. It remains a measured category. |
| `fetch_failure` | Authentication, authorization, network, HTTP, parsing, quota, paging, or source-availability failure prevented observation. It is never converted to zero or missing. |
| `partial` | Only a bounded portion of the requested observable population was retrieved. The observed and unobserved ranges must be separate. |

For Google Trends, a source-returned numeric 0 is recorded as `zero` with `zero_semantics = low_or_insufficient_relative_interest`; it must not be described as no public interest.

When a source does not report request cost, `reported_cost_usd` MUST be `null`. Unknown cost MUST NOT be coerced to `0.0`. Request counts and rate/quota headers remain independent evidence.

### 2.3 Shared request and retry rules

The following terms are distinct throughout this specification:

- `upstream_response`: the ephemeral source/API response before project privacy/licensing projection. It may exist only transiently in memory long enough to create the approved projection. When it contains fields prohibited or not approved for persistence, it MUST NOT be persisted, logged, cached, or hashed.
- `privacy_reduced_raw_envelope`: the allowlisted source-native fields approved for local M5 persistence. This is the project's persisted M5 Raw artifact, is append-only under a unique run, and contains no prohibited personal fields or secrets.
- `persisted_envelope_checksum`: a checksum of the exact persisted `privacy_reduced_raw_envelope`, never of a discarded `upstream_response`. For a separately lawful persisted artifact, such as a Human-exported Trends CSV, its file hash may instead be recorded explicitly as that artifact's hash.

`persisted_envelope_checksum` is an artifact-integrity value and does not redefine `raw_content_identity`. Content identity remains content-derived and excludes run identity, record/run provenance, query identity, and observation/ingestion metadata; those remain separately traceable.

- Every external call MUST have a query identity, run identity, source, UTC request time, target period, response status, returned count, retained count, attempt number, elapsed time, quota/rate evidence when available, and sanitized error category.
- Credentials, authorization headers, cookies, signed URLs, tenant/project/account identifiers not needed for public reproduction, and full `upstream_response` bodies in logs are prohibited.
- Retries are smoke-only: one initial request plus at most two retries for network errors, HTTP 429, and HTTP 5xx. Respect `Retry-After`; otherwise wait 2 seconds and then 8 seconds with small jitter. Do not retry other 4xx responses.
- A source-specific lower rate limit overrides this common rule. Cursor MUST stop before a documented quota or cost ceiling and record `SMOKE-BLOCKED`, not buy capacity or expand scope.
- Pagination MUST use the source's documented mechanism. If the source cap prevents the bounded sample from being characterized after the source-specific partition rule, stop; do not hide truncation.
- Persisted Raw envelopes and extracted records are append-only under a unique run. A repeat run creates a new run and never replaces the earlier Raw.

### 2.4 Common evidence and publication boundary

All source Raw remains under the Git-ignored local workspace until the source's smoke-time licensing decision explicitly permits otherwise. The acquisition boundary MUST apply the source-specific field allowlist to the `upstream_response` before persistence when it contains person-level or otherwise prohibited fields. The resulting `privacy_reduced_raw_envelope` is append-only; the discarded `upstream_response` is not logged, hashed, cached, or saved. Public artifacts may contain only synthetic fixtures, metadata explicitly allowed for redistribution, reacquisition recipes, source IDs/URLs, hashes where lawful, and non-personal safe aggregates. PDFs, filing bodies, README/code content, API dumps with unclear rights, secrets, and personal identifiers MUST NOT be committed.

## 3. Execution order

| Order | Work package | Prerequisite / Human input | Cursor artifact | Stop condition | May continue in parallel |
|---:|---|---|---|---|---|
| 1 | OpenAlex | API key configured outside the repository if the current service requires/rewards one; no purchase authorization | OpenAlex Raw sample, query log, denominator log, coverage and field-availability summary | Terms conflict, required fields/query route absent, mandatory request remains `fetch_failure`, or cost/request ceiling reached | Trends entitlement check and China legal/access check |
| 2 | Google Trends access check | Human supplies alpha entitlement, credential mechanism, and applicable terms; otherwise chooses official UI CSV or no-go | Access decision plus alpha output or manual-import contract/result | No entitlement/terms, moving window misses 2022-11-30, or export cannot be reproduced | OpenAlex and company legal checks |
| 3 | China company legal/access check | Human supplies official service/account route and applicable agreement/terms by 2026-08-28 23:59 Asia/Tokyo | China access/terms evidence record and early source result | Official access, required history, or applicable terms cannot be evidenced by cutoff; broad scraping would be required | Other country company credential setup |
| 4 | SEC / EDINET / Open DART bounded smokes | Approved issuer registry; EDINET and Open DART credentials where required | Source-specific local samples and decisions | Missing official country evidence, history, title/text path, or terms/storage boundary | The three sources may run independently after registry approval |
| 5 | GitHub Organization/Repository smoke | Human-approved organization registry; optional fine-grained read token outside repository | Registry snapshot, bounded repository Raw, search-cap/privacy report | Personal data is needed, country requires inference, or daily partition still reaches search cap/incomplete results | arXiv trigger review and completed-source summaries |
| 6 | arXiv fallback | Triggered only by OpenAlex limitation or explicit need for timing corroboration | Bounded metadata sample and fallback decision | Country requires institution/name inference or the source-specific limits cannot be respected | Decision-table preparation |
| 7 | M5 decisions and RF attempt | All runnable mandatory smokes have terminal evidence; blocked prerequisites are explicit | Source decision table, RF evidence matrix/recommendation, M6 handoff package | Any RF requirement lacks evidence; do not start M7 | None; this is the integration step |

Failure of one candidate does not stop independent candidates. It stops only dependent work and any claim that needs that candidate.

### 3.1 Preflight decisions not reopened

The approved M5 preflight remains closed scope for eliminated or limited-role candidates:

- Job postings are `NO-GO` for the MVP; do not implement or smoke them without a new Human-approved requirements/design decision.
- Issuer IR pages are not a primary Company-sensor acquisition route; use them only as bounded evidence or fallback links.
- Unofficial Google Trends libraries remain `NO-GO`. Undocumented Trends Explore/widget endpoints remain prohibited **except** for the conditional M5-only Transport B path defined by **Erratum-002** (dual live gate required; see Erratum-002).
- GH Archive is not an MVP fallback and requires a separate privacy/requirements decision.
- arXiv remains fallback/corroboration only unless a later reviewed decision changes its role.

Failure of a surviving candidate produces its defined terminal state or escalation. Cursor MUST NOT silently replace it with an eliminated candidate or reopen candidate discovery.

## 4. `PROVISIONAL-M5-SMOKE` vocabulary

### 4.1 Status, version, and matching mechanics

The vocabulary label is exactly `PROVISIONAL-M5-SMOKE`. Its first version identifier is `PROVISIONAL-M5-SMOKE/2026-08-23-r1`; later smoke-only edits increment `rN` and retain prior versions.

It exists only to test source coverage, field availability, and obvious false positives. It is **not Gate D v1**, does not optimize recall, and must not be cited as the production classifier. Every query, extracted match, coverage row, and manifest records `smoke_vocabulary_version` and the matching field/term.

Smoke matching is deterministic and intentionally narrow:

1. Normalize Unicode to NFKC, case-fold Latin text, normalize runs of whitespace, and treat ASCII hyphen variants as spaces for matching.
2. Match the explicit phrases below against title and, where allowed, abstract/description/body-test text. Do not translate, stem, expand acronyms, or call an LLM.
3. A positive phrase qualifies unless the occurrence is wholly part of an exclusion below. If a record contains another unexcluded positive phrase, that other evidence remains valid.
4. Ambiguous terms are recorded for inspection but do not qualify alone.
5. Generic standalone `agent`—in any case, number, script transliteration, or translation—MUST NOT qualify as AI Agent evidence.

For each runnable source, Human reviews at most five provisional positives and five server-returned-but-locally-rejected ambiguous/excluded candidates per country × theme, stratified across the fixed periods where available. If fewer exist, review all. The review records record ID, displayed text field, matched/rejected term, expected result, observed result, and note; it changes no vocabulary automatically.

### 4.2 Small multilingual term set

| Language | Theme | Positive terms / explicit variants | Ambiguous; inspect but do not qualify alone | Exclusion patterns / contexts |
|---|---|---|---|---|
| English | Generative AI | `generative AI`, `generative artificial intelligence`, `GenAI`, `Gen AI` | `generative model`, `foundation model`, `AI-generated`, `AIGC` | `generative adversarial network` / `GAN` alone; `generative design` without an AI-positive phrase |
| English | AI Agent | `AI agent`, `AI agents`, `artificial intelligence agent`, `artificial intelligence agents`, `agentic AI`, `LLM agent`, `LLM agents` | `agent`, `agents`, `agentic`, `autonomous agent`, `multi-agent system` | travel, insurance, real-estate, chemical, pathogen, or software user-agent uses without an AI-positive phrase |
| Japanese | Generative AI | `生成AI`, `生成型AI`, `生成系AI`, `ジェネレーティブAI` | `生成モデル`, `基盤モデル`, `AI生成`, `AIGC` | `生成デザイン` or `敵対的生成ネットワーク` alone |
| Japanese | AI Agent | `AIエージェント`, `AI エージェント`, `エージェント型AI`, `自律型AIエージェント`, `LLMエージェント` | `エージェント`, `自律エージェント`, `マルチエージェント` | 旅行・保険・不動産・芸能・ユーザーエージェント contexts without an AI-positive phrase |
| Korean | Generative AI | `생성형 AI`, `생성형AI`, `생성 AI`, `생성AI`, `생성형 인공지능`, `제너레이티브 AI` | `생성 모델`, `파운데이션 모델`, `AI 생성`, `AIGC` | `생성적 적대 신경망` / `GAN` alone; generative design without an AI-positive phrase |
| Korean | AI Agent | `AI 에이전트`, `AI에이전트`, `에이전틱 AI`, `에이전트형 AI`, `자율형 AI 에이전트`, `LLM 에이전트` | `에이전트`, `자율 에이전트`, `멀티 에이전트` | travel, insurance, real-estate, entertainment, or user-agent contexts without an AI-positive phrase |
| Chinese (simplified/traditional) | Generative AI | `生成式人工智能`, `生成式人工智慧`, `生成式AI`, `生成型人工智能`, `GenAI` | `生成模型`, `基础模型`, `基礎模型`, `AI生成`, `AIGC` | `生成对抗网络` / `生成對抗網路` / `GAN` alone; generative-design contexts without an AI-positive phrase |
| Chinese (simplified/traditional) | AI Agent | `AI智能体`, `AI智能體`, `人工智能智能体`, `人工智慧智能體`, `AI代理`, `Agentic AI`, `LLM智能体`, `LLM智能體` | `智能体`, `智能體`, `代理`, `智能代理`, `自主智能体`, `多智能体` | commercial/intermediary代理, travel, insurance, real-estate, biological agent, or user-agent contexts without an AI-positive phrase |

For server-side candidate discovery, Cursor may issue one exact positive phrase per request if a source cannot express a reliable OR query. Local matching alone determines `provisional_match`. Server ranking/topic labels are auxiliary evidence only.

M6 may replace this vocabulary completely. Because M5 retains allowed source text, matched term, field, normalization version, and source query, M6 can reclassify the immutable sample under a new dictionary without altering M5 Raw or pretending the smoke classifier was frozen.

## 5. OpenAlex smoke contract

### 5.1 Request plan

- Endpoint/mode: documented `GET /works` list/search API, using publication-date and authorship-country filters plus the `search` parameter for candidate discovery. Use `cursor=*` only when a cell needs a second/third page under the ceiling.
- Cells: 4 countries (`JP`, `US`, `KR`, `CN`) × 2 themes × `OA-START`, `OA-MID`, `OA-RECENT` = 24 cells.
- Candidate discovery: issue separate, URL-encoded searches for each relevant `PROVISIONAL-M5-SMOKE` positive phrase; union and deduplicate by OpenAlex Work ID. Do not use OpenAlex topics/keywords as the primary classifier.
- Phrase order is deterministic: target-country language row in table order, followed by English row in table order, skipping duplicates. US uses the English row only. A global audit uses English, Japanese, Korean, then Chinese table order.
- Classification: reconstruct an abstract only from `abstract_inverted_index`; apply the provisional classifier locally to title and reconstructed abstract. Record title-only and title-plus-abstract results separately.
- Country filter is only a retrieval aid. Retain every allowlisted authorship country/evidence field, multi-country case, missing institution country, and approved source-native field needed to measure evidence quality. Do not collapse multi-country Works.

### 5.2 Retention, paging, requests, and cost

- Retain at most 100 unique Work records per country × theme × period cell, ordered by phrase order, source response order, and then stable Work ID for local output.
- Use `per-page=25`. Inspect at most 300 API-returned candidate records and at most 12 HTTP result pages per cell across phrase searches. Request one first page per phrase in the deterministic queue. If the first phrase reports more than 25 results, one second cursor page for that phrase is allowed after all queued phrases that fit under the 12-page ceiling. Stop at the first ceiling and record every unexecuted phrase.
- Intentional smoke retention/inspection truncation is `partial`, with source total and documented cursor path preserved. It is not a source-cap failure and it cannot be reported as `zero`.
- No deep bulk acquisition or snapshot download is allowed.
- Add one country-week denominator request for each country × period (12 requests), with one result row at most and the source-reported total count. Candidate denominators are: all qualifying Works with target-country authorship evidence in that period; also record counts with non-missing title and abstract where the API can obtain them without expanding beyond the ceilings.
- Add one global theme × period audit (6 cells, maximum 100 retained records each) without a country filter to measure `unknown`/multi-country/text-field availability among topic candidates. It is an audit sample, not a global denominator.
- Total OpenAlex request ceiling: 512 HTTP attempts including retries. Total reported API cost ceiling: USD 0.75 or 75% of the documented daily free budget, whichever is lower. Stop before the ceiling; do not purchase capacity.

### 5.3 Retained field allowlist

Retain only what is needed from each Work:

- Work ID, DOI if present, public OpenAlex URL, display/title value, type, language, and primary-location/source identity needed to understand coverage;
- abstract presence plus `abstract_inverted_index` only in local Raw; public samples should prefer abstract-presence flags unless redistribution is explicitly confirmed;
- `publication_date`, `publication_year`, `created_date`, `updated_date`, and local `observed_at` / `ingested_at`;
- Work-level deduplicated institution IDs/types and `country_code`, Work-level union of authorship `countries`, country-evidence/provenance fields exposed by the response after removing author association, and missing/multi-country flags;
- provisional matching term, language, matched field, positive/ambiguous/excluded status, and vocabulary version;
- request URL with key removed, normalized filter/search parameters, cursor/page identity, source total count, response cost, remaining budget/rate headers, HTTP status, retry count, parsing warnings, and `persisted_envelope_checksum`.

Do not persist author objects, author IDs, author display names, ORCID, or other person identifiers in local Raw, extracted, or public artifacts. If the endpoint returns them, create the allowlisted `privacy_reduced_raw_envelope` in memory and discard the `upstream_response`. Do not download PDFs, full text, linked content, or author profiles.

### 5.4 Mechanical success and no-go rules

`SMOKE-PASS` or `SMOKE-PASS-WITH-LIMITATIONS` requires:

- all 24 cells and 12 denominator requests have a terminal non-failure response, including legitimate zeros and explicitly bounded partial samples;
- the exact start boundary is queryable and the same request construction works for midpoint and recent windows;
- source total/count, paging/truncation status, text availability, target-country evidence, missing country evidence, multi-country cases, and provisional match evidence are measurable;
- at least one traceable usable text record exists for each country × theme across the three sentinel windows combined, or the absence is reported as a limitation rather than fabricated; and
- current terms, CC0 evidence, rate/cost behavior, and reacquisition metadata are recorded.

OpenAlex is `SMOKE-NO-GO` as the RF anchor if any country/date cell cannot be queried by the documented schema; the start boundary is unavailable; mandatory requests remain `fetch_failure`; response/paging behavior makes a bounded cell untraceable; deterministic title/abstract evidence cannot be inspected for a required country-theme route; country evidence would require name/language/LLM inference; or current terms conflict with acquisition/storage. Sparse or valid zero cells alone are not no-go.

Low abstract coverage, high `unknown`, or strong country/language imbalance produces `SMOKE-PASS-WITH-LIMITATIONS` and M6 evidence; M5 does not invent an acceptability threshold for Gate A, D, or E.

## 6. Google Trends smoke contract

### 6.1 Shared query probes

Use one explicit search-term probe per theme per country for the access smoke, not all vocabulary variants:

| Country | Generative AI probe | AI Agent probe |
|---|---|---|
| US | `generative AI` | `AI agent` |
| JP | `生成AI` | `AIエージェント` |
| KR | `생성형 AI` | `AI 에이전트` |
| CN | `生成式人工智能` | `AI智能体` |

These probes test acquisition and scale mechanics only. They do not freeze Gate D query definitions. Term mode and Topic mode must be separate runs; never silently substitute a Google Topic for the term above. A Topic run is allowed only when Human supplies the exact official topic ID/name and Cursor records it as a separate probe.

### 6.2 A — official API alpha

This path is executable only after Human records `entitlement_confirmed`, supplies credentials through the secret mechanism, and identifies the applicable alpha terms/version and storage/publication conditions.

- Make four country requests over `TRENDS-FULL`, one per country, grouping that country's two term probes in the same request if the alpha API supports multi-term grouping.
- Request weekly aggregation, country geo, all categories, Web Search property, and the service's documented timezone. Record the requested and returned timezone/week boundaries.
- If grouping is unsupported, issue two separate requests but mark `shared_scale = unverified`; do not compare or merge their levels until scale metadata and repeat evidence justify it.
- Repeat the identical four-request plan after at least 24 hours and no more than seven days. A repeat uses the exact query IDs, order, geo, category, property, period, interval, and timezone.
- Record exact term/topic identity, query grouping, API/version, geo, category, property, dates, interval, timezone, returned week labels, numeric values, zeros, scale/base/reference metadata, sampling/noise/revision identifiers when exposed, observation time, `persisted_envelope_checksum`, quota/cost, and sanitized errors.

Alpha is `SMOKE-PASS`/`WITH-LIMITATIONS` only if all eight term series cover 2022-11-30 through 2026-08-16 with a traceable weekly path, both runs complete, request-to-request scale/join semantics are evidenced, repeat differences are quantified, and terms permit the intended local evidence handling. It is `SMOKE-NO-GO` for the MVP route if the rolling window has lost the start boundary, cells cannot be requested, separate scales are unjoinable, repeated responses cannot be interpreted, or terms prohibit the required use. It is `SMOKE-BLOCKED` when entitlement, credentials, or applicable terms are absent.

### 6.3 B — official UI CSV fallback

This is a Human-operated, bounded fallback; Cursor may validate/import the resulting files but MUST NOT automate browser login or an unofficial client library.

Automating undocumented Explore/widget network endpoints for CSV acquisition is prohibited **except** under **Erratum-002** (M5-only Transport B) when **both** live gates are satisfied. Erratum acceptance alone does **not** authorize a live request. If either gate is absent, record `SMOKE-BLOCKED` and make no Transport B live request.

Transport A (this subsection) remains the required fallback whenever Transport B is unavailable or unauthorized.

For each country:

1. In the official Trends UI, compare that country's two probes together in one request.
2. Set the country explicitly, custom range `2022-11-30` through `2026-08-16`, all categories, Web Search, and record the displayed/CSV granularity and UTC behavior.
3. Record result URL, exact display labels, term versus Topic mode, order, geo, category, property, requested dates, UI-visible timezone/version if any, export time, file name, file SHA-256, row count, first/last returned week, missing rows, and any UI warning.
4. Repeat the same export after at least 24 hours and no more than seven days; preserve both files and quantify changed weeks/values.

The four countries are four independent 0–100 scales. Values must never be compared across countries as levels. If variants require separate requests, those batches are also separate scales unless M6 later adopts a tested reference-query transformation. Cursor must not merge them in M5.

UI CSV is `SMOKE-PASS-WITH-LIMITATIONS` only if four paired exports and repeats cover the full range and their request-relative meaning is preserved. Export absence, lost start boundary, inability to keep both themes in a paired request without an approved reference design, or unexplained structural changes is no-go for the comparative fallback. A source-returned 0 remains low/insufficient relative interest, not absence.

## 7. GitHub Organization registry and repository smoke

### 7.1 Human-approved registry template

The local registry is versioned and contains at most two approved Organizations per country:

| Field | Rule |
|---|---|
| `registry_version` | Immutable version, e.g. `github-org-registry/2026-08-23-r1`. |
| `organization_login` | GitHub Organization login; personal users are prohibited. |
| `display_name` | Organization display name. |
| `target_country` | `JP`, `US`, `KR`, or `CN`; never inferred from member/profile language. |
| `country_evidence_url` | Organization-level official public page or official Organization field. |
| `evidence_type` | Controlled value: `official_hq_page`, `official_company_profile`, or `github_org_explicit_location`. |
| `evidence_date` | Date Human verified the evidence. |
| `approval_state` | `approved`, `rejected`, or `pending`; Cursor uses only `approved`. |
| `notes` | Limitations such as free-text location, reorganization, or country ambiguity. No personal data. |

Cursor MUST NOT invent or finalize Organizations. Fewer than one approved Organization in any target country makes the four-country developer route no-go; fewer than two is allowed but reported as registry undercoverage.

### 7.2 Repository-creation smoke

- Endpoint/mode: documented GitHub REST Organization and Repository Search endpoints. Query only approved Organization logins.
- The population query is `org:{organization_login} fork:false is:public created:{start}..{end}`, with `sort=created`, `order=asc`, and `per_page=100`; all values are URL-encoded and the sanitized query is recorded.
- Strata: each approved Organization × `MONTH-START` and `MONTH-RECENT`.
- Population query: public, non-fork repositories owned by the Organization with `created_at` in the stratum. Provisional theme classification is local over allowed current metadata.
- Initial partition is one calendar month. If `total_count > 900` or `incomplete_results = true`, split into ISO-week date partitions; if still over 900/incomplete, split to individual UTC dates. A daily partition still over 900 or incomplete is a hard no-go for that stratum. Never page past the documented 1,000-result cap.
- Per final partition: at most three pages and 100 results/page. Per Organization × month: retain at most 100 repositories, while preserving total counts and partition/truncation evidence.
- Total smoke ceiling: 200 HTTP attempts including retries and Organization evidence calls. Respect search/core/secondary rate headers and stop before exhaustion.

Allowed persisted repository fields are repository ID, public URL, name/full name, Organization owner login and owner type, public/private/visibility flag, fork flag, `created_at`, `updated_at`, `pushed_at`, description, topics, primary language, archived/disabled/template flags, observed/ingested times, query/partition metadata, rate headers, and provisional match evidence. The API response MUST be projected to this allowlist before append-only Raw persistence. README content is excluded from this smallest smoke.

Explicitly prohibited are personal users and user profiles; member lists; actor, author, committer, contributor, stargazer, watcher, subscriber, email, personal location, commit/event/issue/pull-request payloads; avatars; and any person-level derived/hash identifier. Current repository description/topics are local evidence only and must carry `current_metadata_time_leakage = true` for historical strata.

The smoke passes mechanically only if every country has an approved Organization, both periods are queryable, owner type is Organization, partitions are complete under the ceiling, zero/failure is distinguishable, no prohibited fields enter Raw/extracted/public artifacts, and current-metadata/survivorship limitations are measured. It is no-go if a country lacks an approved Organization, person-level evidence is required, official Events/history is required, search remains capped/incomplete after daily partitioning, or the repository-creation proxy would be mislabeled as general developer activity.

A theme result may be `zero` only when all repositories in that Organization-period stratum were inspected or a complete, below-cap theme-qualified search proves zero. If only the first 100 of a larger complete population were retained/inspected, the theme state is `partial`, never zero.

## 8. Company issuer registry

Human provides a versioned local registry with at most two approved issuers per country, preferably one technology producer and one broad comparator. Listing venue alone never qualifies as country evidence.

| Field | Rule |
|---|---|
| `registry_version` | Immutable version, e.g. `company-issuer-registry/2026-08-23-r1`. |
| `issuer_name` | Public issuer name. |
| `target_country` | `JP`, `US`, `KR`, or `CN`. |
| `regulator_source` | `sec_edgar`, `edinet`, `open_dart`, or the approved China official route. |
| `source_issuer_id` | CIK, EDINET code, DART corp code, or official China identifier. |
| `hq_domicile_evidence_url` | Official regulator/company source with explicit headquarters/domicile. |
| `evidence_type` | `regulator_domicile`, `registered_address`, `official_hq_page`, or another Human-documented primary type. |
| `evidence_date` | Human verification date. |
| `approval_state` | `approved`, `rejected`, or `pending`; Cursor uses only `approved`. |
| `notes` | Foreign issuer, changed domicile, coverage, or identifier caveat. |

No source runs for an issuer until `approval_state = approved`. Registry evidence is input to M6 Gate E; M5 does not freeze the final country rule.

## 9. Company-source smoke contracts

### 9.1 Shared bounded procedure

- Sources remain separate. Do not union raw counts or call them a common scale.
- Use at most two approved issuers per source/country and `MONTH-START` plus `MONTH-RECENT`.
- Enumerate source metadata for the periods under documented endpoints. Retain at most 25 metadata rows per issuer × period; preserve source total/truncation evidence when available.
- Inspect at most two candidate documents per theme × issuer × period to test title/body availability: at most 16 document inspections per country source. Stop earlier once title and one official machine-readable body format have each been tested. A body-availability test uses documented metadata, response headers, or an authorized transient fetch; it does not persist the filing body. Body matching is performed only when the applicable terms and Human privacy review permit it and an allowlisted non-personal text projection is defined. Otherwise record `body_match_not_tested_privacy_boundary` and keep title-only evidence.
- Apply `PROVISIONAL-M5-SMOKE` locally. Title-only and title-plus-body outcomes remain separate. Do not OCR PDFs in M5.
- Record source/document/accession ID, issuer ID/name, registry version and evidence reference, document/form/type, title, language, official source URL, filing/submission/acceptance/publication/update/correction/withdrawal times exposed by the source, `observed_at`, `ingested_at`, text format/availability, query/download route, paging/count/quota evidence, `persisted_envelope_checksum`, provisional match evidence, and sanitized error.
- Full documents are never persisted by this smoke. Public artifacts default to metadata, source links, reacquisition steps, and safe aggregates.

### 9.2 SEC EDGAR

- Prerequisite: two approved US issuers/CIKs and an identified, policy-compliant User-Agent contact configured outside public output; no API key.
- Use official `data.sec.gov` submissions/filing metadata and official filing document links. Filter records to the two fixed months; follow official archived submission-file references only when necessary for 2022 history.
- Evidence includes CIK/accession, form, filing date, acceptance timestamp when exposed, report period, primary-document URL/format, issuer jurisdiction/address/domicile fields, update/observed time, and Fair Access/rate behavior.
- Pass requires stable IDs, both historical/recent metadata retrieval, explicit registry country evidence, bounded official title/text availability, documented access behavior, and a conservative publication decision. No-go if history/official text cannot be retrieved, country depends on exchange listing, document types cannot be bounded, or policy-compliant access fails.

### 9.3 EDINET API v2

- Prerequisite: two approved JP issuers/EDINET identifiers, Human-issued API key in the secret mechanism, current API v2 specification, applicable site/use terms, and storage/publication decision.
- Use the official dated document-list route for every calendar date in the two fixed months: maximum 62 list requests before retries. Respect the stricter current guidance of approximately one request per minute. Download only the bounded inspected documents and only when terms permit.
- Evidence includes document/EDINET/filer ID, form/document type, submit/publication time, period, correction/withdrawal state, available file formats, filer/head-office evidence, response/result metadata, quota behavior, and observed time.
- Pass requires key access, the 2022 period, stable IDs/times, explicit registry country evidence, title or machine-readable content evidence, and established local/publication boundaries. Missing key/terms, insufficient retained history, unverifiable storage rights, or unavoidable inference is blocked/no-go as appropriate.

### 9.4 Open DART

- Prerequisite: two approved KR issuers/corp codes, registered API key outside the repository, captured current terms, account quota/cost evidence, and storage/publication decision.
- Use official company/report search by corp code and each fixed month; inspect official XML/text only within the shared cap.
- Evidence includes corp code, report number, report type/name, receipt/publication date, issuer overview/head-office evidence, correction state, XML/text availability, query/paging/count/quota fields, and observed time.
- Pass requires reproducible company/date queries for both periods, required metadata/text, explicit registry country evidence, and terms/quota compatible with bounded research. No-go if account/quota/terms, history, HQ evidence, or text path fails.

### 9.5 CNINFO / SSE / SZSE official route

- Prerequisite: Human selects exactly one primary official route, supplies two approved mainland issuers/IDs, and captures official account/API agreement or official bounded manual-download terms, quota/cost, historical access, and storage/publication conditions.
- Use only the approved official interface. Query the two fixed months and inspect documents under the shared cap. Record the exact API/manual route; an official visible portal alone is not evidence of authorized automation.
- Evidence includes issuer/security/document ID, explicit registered-address/domicile/HQ evidence, announcement type/title, publication/acceptance time when present, correction/withdrawal state, official URL/format, history/query behavior, quota, terms version/date, and observed time.
- `SMOKE-PASS` requires official repeatable 2022 and recent retrieval, stable IDs/times, title or authorized text availability, explicit issuer-country evidence, and verified applicable terms. If official access, historical retrieval, or applicable terms cannot be evidenced by **2026-08-28 23:59 Asia/Tokyo**, the China source and four-country Company comparative lane are `SMOKE-NO-GO`. Do not compensate with broad scraping, an undocumented endpoint, or listing-venue inference. Other countries may remain descriptive M5 evidence.

## 10. arXiv fallback smoke

Run only when OpenAlex has a measured limitation needing corroboration or the M5 reviewer explicitly requests a research-timing cross-check.

- Endpoint/mode: official arXiv API; use a single connection and wait at least three seconds between requests. OAI-PMH may replace the legacy query API only if the bounded query API cannot lawfully/reliably provide the sample, and the route change is recorded.
- Periods/themes: both themes in `MONTH-START` and `MONTH-RECENT`; at most 40 retained records per theme × month, deduplicated to base arXiv ID and preserving version metadata.
- Search title/abstract with positive phrases, then classify locally. Retain base/version ID, public URL, title, abstract, categories, `published`, `updated`, observed/ingested time, affiliation text stripped of any author association, raw affiliation presence, explicit country-literal presence, query/page/count, provisional match evidence, and errors. The full API response and author names/person identifiers are discarded before local Raw persistence and never enter extracted/public artifacts.
- Country inspection may recognize only an explicitly written target-country name/code in the returned affiliation/address. Institution abbreviation/name lookup, author-name inference, language inference, and LLM completion are prohibited.
- Metadata timing is a useful fallback if both themes have traceable title/abstract-positive records in both periods, base-ID/version handling is reproducible, and `published` versus `updated` is preserved. It remains a limited preprint-timing proxy.
- It is country-comparison no-go if any target country has no explicit country-literal evidence in the bounded sample, if coverage requires institution resolution, or if author/person processing would be needed. Even positive coverage remains only M6 evidence, not a frozen country rule.
- Respect the documented 30,000-call-result ceiling, keep each request below 1,000 results, and apply the shared retry rule without violating the three-second minimum interval. Do not retrieve or redistribute e-prints/PDFs.

## 11. Smoke artifact contract

### 11.1 Required local artifacts

Cursor should create these small, inspectable outputs; `workspace-data/` remains Git-ignored:

```text
workspace-data/m5-smoke/
  registries/
    github-organizations.<version>.csv
    company-issuers.<version>.csv
  runs/<run_id>/
    manifest.json
    queries.jsonl
    raw/<source>/*.privacy-reduced.jsonl
    extracted/<source>.jsonl
    coverage.csv
    privacy-licensing.json
    source-decisions.json
    rf-evidence.json
    m6-handoff.json
```

Manual Trends files are stored under the corresponding run with original file hashes and a separate Human evidence record. Source payloads whose local storage is unverified are not saved; the query, response metadata, lawful hash/reference, and the reason are saved instead.

After review, Cursor updates `docs/decisions/m5-sensor-decision.md` with safe aggregates, limitations, source result, RF recommendation, and links to reacquisition instructions. Any public sample under `data/samples/` must be synthetic or explicitly redistributable and pass the public-safety review.

### 11.2 Minimum machine-readable summary concepts

This is a conceptual contract, not production DDL:

- schema/run identity: `schema_version`, `run_id`, `run_type = m5_smoke`, code revision, start/end UTC;
- scope: sensor, candidate/source, period ID and exact dates, country/geo, theme, vocabulary version, registry version;
- query: sanitized endpoint/mode, normalized parameters, query hash, page/cursor/partition, attempt, observed time;
- outcome: primary quality state, HTTP/source status, total count, inspected/retained/matched/zero/missing/unknown/partial/failure counts, truncation/incomplete flag;
- evidence: country evidence type/coverage, multi-country count, title/abstract/body availability, timestamp fields/precision, provisional matched term/field and review result;
- controls: rate/quota headers, source-reported cost, retry count, stop reason, `persisted_envelope_checksum` or explicitly lawful persisted-artifact file hash, and prior-run relation;
- safety: terms URL/version/access date, local-storage state, public-redistribution state, citation requirement, personal-data-present flag (must be false for GitHub extracted Raw), secret scan state;
- decision: recommended M5 result, reason codes, limitations, reviewer/approval state, and links to evidence and M6 handoff.

Every aggregate must retain a path to its query/run evidence. A successful source response with zero results is distinguishable from a request that never observed the cell.

## 12. RF attempt contract

Documentation alone cannot pass RF. Cursor assembles evidence and a recommendation; Human / Codex review records the final M5 RF state.

### 12.1 `RF PASS`

At least one single route must demonstrate all of the following from actual smoke responses:

1. JP, US, KR, and CN × both themes are addressable without inferred country or fabricated cells.
2. The exact 2022-11-30 boundary is retrievable, a midpoint and recent period are retrievable, and the same documented query construction supports a traceable weekly series over the intervening required period.
3. Every sentinel cell has a terminal observable outcome; a legitimate sparse/zero cell is allowed. An intentional bounded sample may be `partial` only when the source-reported total and a documented uncapped pagination path show how the full population would be acquired. Unavailable, source-capped, untraceable, or failed cells do not qualify.
4. A candidate population and denominator are directly observable, or the source supplies a documented denominator-free index whose scale/normalization is recorded. This is evidence for Gate A, not its freeze.
5. Country evidence is primary-source/structured, `unknown` is measured, multi-country behavior is retained, and no name/language/LLM inference is used.
6. Deterministic theme evidence is inspectable under the versioned provisional vocabulary, including basic positive/negative review and text-field availability. This does not freeze Gate D.
7. publication/event, source update/observation, and local ingestion times are separated sufficiently to hand to Gate C.
8. Acquisition is repeatable under verified current terms, quota/rate/cost, credential, and storage boundaries.

RF may pass on OpenAlex alone if it satisfies all eight points; four sensors do not all have to enter the final analysis. A Trends route may pass only if its fixed terms/topics and denominator-free relative index meet the same evidence standard. Cross-source patching of unavailable cells is not a single route and cannot silently create RF PASS.

### 12.2 `RF BLOCKED`

Record `RF BLOCKED` when every tested/authorized route fails at least one hard RF condition and no bounded, authorized unresolved test could change the result before M5 exit. Examples include an unqueryable target country/theme, lost start boundary, inferred country requirement, untraceable zero, incompatible terms, or unusable time/text semantics. M7 large backfill MUST NOT begin.

### 12.3 `RF INCONCLUSIVE`

Record `RF INCONCLUSIVE` when evidence is incomplete because a prerequisite, repeat observation, transient quota/outage, bounded sample, or provisional-vocabulary adequacy issue remains and a specific authorized next smoke could resolve it. List the missing evidence, owner, bounded next action, and deadline. `RF INCONCLUSIVE` also blocks M7; it must not be converted to PASS by documentation or optimism.

## 13. M6 Gate A–E handoff package

M5 supplies evidence; it does not decide any Gate.

| Surviving sensor | Gate A evidence | Gate B evidence | Gate C evidence | Gate D evidence | Gate E evidence |
|---|---|---|---|---|---|
| OpenAlex / arXiv | Distinct Work/base-ID sample, source total, candidate country-week denominator, dedupe and title/abstract coverage, multi-country sensitivity inputs | Exact statement of observed indexed scholarly work/preprint and limitations | Publication/first-submission, created/updated/version, observed/ingested samples and precision/lag notes | Per-language matched/nonmatched/excluded examples; title-only vs abstract delta; vocabulary version; Human review sample | Raw structured authorship countries/provenance, missing/unknown rate, multi-country examples; arXiv explicit-literal coverage; proof of no inference |
| GitHub | Repository-creation population totals, partitions/caps, non-fork denominator candidate, deletion/survivorship and mutable-metadata evidence | Exact narrow proxy: public Organization repository creation, not developer population/activity or a social layer | Created/pushed/updated/observed samples and proof Events were not used for history | Field-level match/ambiguous/exclusion examples and current-metadata leakage | Approved Organization registry, evidence types/dates, unknown/undercoverage, transfer caveats, and proof prohibited personal fields are absent |
| Company sources | Source-specific document IDs/types, issuer populations, source totals/denominator candidates, truncation and within-source inputs | Exact proxy: official issuer disclosure behavior; source/regulatory limitations | Submission/acceptance/publication/correction/observed/ingested samples and source-lag notes | Title vs body availability and match examples, boilerplate/OCR failures, language/source coverage | Issuer registry and explicit domicile/HQ evidence, foreign/changed/unknown cases, no exchange/language inference |
| Google Trends | Relative-index values, request grouping, scale/reference/sampling/repeat evidence, zero/low-volume semantics | Exact proxy: Google Search relative interest, not public opinion/adoption or a macro layer | Returned week/UTC boundaries, source lag, repeat observation and ingestion times | Exact term/Topic IDs, paired/batch arrangement, variants not tested, vocabulary version | Explicit service geo parameter, country-specific low-volume/zero coverage, and aggregate-only privacy evidence |

Handoff also includes all Raw/query identities, coverage tables, licensing/publication flags, unresolved questions, and candidate result. M6 separately freezes or rejects each sensor.

## 14. Ordered Human actions

1. Configure an OpenAlex API key outside the repository if required for the documented free budget; do not provide it in this document or chat output.
2. Confirm Google Trends alpha entitlement, credential mechanism, quota/cost, applicable terms, and storage/publication rights; otherwise choose bounded official UI CSV or no-go.
3. By 2026-08-28 23:59 Asia/Tokyo, provide an official China disclosure access route/account agreement and applicable terms, or approve Company-lane no-go.
4. Complete and approve the company issuer registry, at most two issuers per country, with explicit HQ/domicile evidence.
5. Configure EDINET and Open DART credentials outside the repository and provide current terms/quota/storage evidence.
6. Complete and approve the GitHub Organization registry, at most two Organizations per country, using only organization-level first-party evidence.
7. If the UI fallback is used, perform and repeat the four official paired Trends exports and provide the files plus evidence fields.
8. Review M5 source decisions and RF evidence; approve `RF PASS`, `RF BLOCKED`, or `RF INCONCLUSIVE`. Do not authorize M7 on the latter two.

## 15. Cursor stop and escalation conditions

Cursor MUST stop the affected smoke and return facts, impact, and options instead of improvising when:

- applicable terms, storage rights, redistribution rights, quota, cost, or access route are unverified;
- access would require broad scraping, an unofficial Trends client library, or an undocumented web endpoint **outside** the conditional Erratum-002 Transport B dual-gate path;
- a permission scope broader than the approved read-only/bounded route is required;
- person-level GitHub or other personal data becomes necessary, even if it could be hashed;
- country assignment requires name, language, institution-name lookup not approved by requirements, listing venue, or LLM inference;
- search/query caps, incomplete results, moving windows, pagination, or source retention prevent characterization of the bounded sample;
- entitlement/credential is unavailable or a mandatory request remains `fetch_failure` after the retry policy;
- the provisional vocabulary appears too weak to test feasibility. Cursor records the failed terms/fields and requests a smoke-vocabulary revision; it does not expand terms or promote the vocabulary to Gate D;
- a source change would require a new privacy, requirements, budget, proxy, denominator, or methodology decision;
- a proposed output would expose a secret, unnecessary account/tenant/project ID, personal information, or content with unclear redistribution rights;
- any instruction conflicts with `docs/requirements.md` or the frozen Plan.

Independent smokes may continue. The blocked source and dependent RF/M7 step may not.

## 16. Self-review

- [x] No M6 Gate A–E decision is frozen; this document fixes only smoke mechanics and handoff evidence.
- [x] `PROVISIONAL-M5-SMOKE` is explicit, versioned, narrow, and replaceable.
- [x] Standalone `agent` never qualifies.
- [x] No personal-data acquisition path was added; GitHub is Organization/Repository-only and arXiv extracted artifacts omit person identities.
- [x] No unofficial Trends client library is permitted. Undocumented Explore/widget endpoints are permitted only under Erratum-002 with the dual live gate (otherwise prohibited).
- [x] No broad scraping is permitted; China has an early legal/access stop.
- [x] Company sources and denominators remain source-specific.
- [x] Cross-sensor raw values are not treated as comparable and sensors are not social layers.
- [x] Zero, missing, unknown, fetch failure, partial, and success (Erratum-001) are distinct.
- [x] RF requires actual smoke evidence and remains blocked/inconclusive without it.
- [x] Every request, record, document inspection, page, cost, and period has a bound.
- [x] No code, connector, backfill, production DDL, or M6 methodology was implemented.

## Erratum-001 — quality-state completeness + unknown cost semantics

- Status: Normative patch to this FROZEN M5 smoke specification.
- Date: 2026-08-23
- Scope: M5 evidence representation only. Does **not** freeze M6 Gate A–E or any production methodology.

### Problem

1. Frozen shared quality states lacked a primary state for **complete observation with one or more qualifying results**. Implementations temporarily overloaded `missing`, which violates the attribute-level meaning of `missing`.
2. When a source did not report API cost, manifests recorded `reported_cost_usd = 0.0`, coercing unknown cost to a numeric zero.

### Patch

1. Add primary state `success` with the definition in §2.2.
2. Mapping for cell/query/denominator outcomes:
   - complete + nonzero qualifying results → `success`
   - complete + zero qualifying results → `zero`
   - bounded ceiling / unobserved remainder → `partial`
   - attribute absence / not applicable → `missing`
   - unresolvable allowed attribute → `unknown`
   - acquisition failure → `fetch_failure`
3. `reported_cost_usd` is `null` when the source reports no cost; only source-reported numeric costs may be summed.

### Non-goals

- No OpenAlex re-fetch is required to apply this erratum to existing Raw.
- Derived evidence MAY be regenerated under a versioned path that preserves original run artifacts and provenance.
- M6 Gate A–E remain unfrozen.

## Erratum-002 — M5 Trends Explore/widget Transport Exception

- Status: Normative patch to this FROZEN M5 smoke specification (text landed on the implementing branch; **Accepted on `main` only after merge**).
- Date: 2026-08-29
- Scope: M5 Trends **acquisition transport mechanics only**. Does **not** change countries, probes, `TRENDS-FULL`, Term mode, category, property, quality states, zero semantics, RF, M6, or production `GO`.

### Sections narrowed

This Erratum narrowly amends only:

- §3.1 (undocumented Trends endpoint absolute NO-GO wording)
- §6.3 (UI CSV path absolute ban on undocumented endpoint automation)
- §15 (stop condition for undocumented Trends endpoints)
- §16 self-review bullet on Trends undocumented endpoints

### Patch

1. Permit an optional M5-only **Transport B** that fetches official Explore multiline **CSV bytes** via Trends Explore/widget endpoints (`/trends/api/explore` → TIMESERIES `request`/`token` → `/trends/api/widgetdata/multiline/csv`), solely as acquisition transport.
2. Transport B is **not** a documented public API and may change without notice. It is **not** a production connector, scheduler, or Canonical dependency.
3. Transport B failure (HTTP error, missing TIMESERIES, 429, parse failure, empty CSV) is acquisition failure / `fetch_failure` / `SMOKE-BLOCKED` as applicable — **never** a valid Trends numeric `zero`.
4. **Dual live gate (both required before any Transport B live request):**
   1. Erratum-002 is **Accepted on `main`** (merged normative text), and
   2. Dated Human-approved evidence exists for applicable **terms**, **automated access**, **storage**, and **publication**.
5. **Erratum acceptance alone MUST NOT authorize a live request.** If either gate is absent → record `SMOKE-BLOCKED` and make **no** Transport B live request.
6. **Transport A** (Human official UI CSV Download + post-download import) remains required fallback.
7. Cookies, auth headers, account/session identifiers, and private URLs MUST NOT be persisted in the repository or public artifacts.
8. TFO Acquisition Contract remains the sole authority for geo / probes / period / category / property / Term mode / quality / zero semantics.

### Non-goals

- No change to RF final, M6 Gate A–E, production `GO`, or research semantics listed above.
- No authorization of unofficial client libraries (e.g. pytrends) or browser UI automation.

M5 SMOKE SPEC STATUS: FROZEN (+ Erratum-001, + Erratum-002)
