# M5 Sensor Preflight

- Status: External Review PASS. Design / research preflight only; no connector or backfill was implemented.
- Source of Truth: `docs/requirements.md` v1.0 and frozen `implementation-plan.md` v1.0.
- Documentation access date: **2026-08-23**.
- Decision vocabulary: `GO` means documentation and sample evidence are sufficient; `NEEDS-SMOKE` means documentation is promising but M5 sample evidence is still absent; `CONDITIONAL` means usable only within the stated restriction; `NO-GO` means do not use for the MVP path.
- Security boundary: country is never inferred from a person's name, language, or LLM output. `unknown` remains a measured result. Public fixtures must not contain secrets, personal identifiers, or source content whose redistribution right is unclear.

## 1. Executive Decision Table

| Sensor | Candidate | Current recommendation | Decision | Biggest risk | Minimum smoke needed |
|---|---|---|---|---|---|
| Research | OpenAlex Works API | Primary candidate | **NEEDS-SMOKE** | Affiliation resolution error/absence and language-specific abstract coverage can make country/theme cells sparse; no M5 sample exists yet | Query three sentinel weeks for all 8 country-theme cells, preserve multi-country/unknown, and measure field and denominator coverage |
| Research | arXiv API / OAI-PMH | Metadata-only fallback or OpenAlex cross-check | **CONDITIONAL** | Affiliation is optional free text and has no structured country field; country comparison is therefore weak | Measure explicit affiliation-country coverage in bounded old/recent samples; fail if it requires inferred country |
| Developer | GitHub REST API, Organization/Repository only | Narrow repository-creation sensor; not a general activity-history sensor | **NEEDS-SMOKE** | Events retain only 30 days, search is capped, current metadata creates survivorship/time-leakage bias, and org location may be missing | Use a Human-approved organization registry; test bounded historical repository creation searches and record unknown/search truncation |
| Company | SEC EDGAR + EDINET + Open DART + CNINFO/exchange disclosure | Country-specific regulator mosaic, not a fictitious global source | **NEEDS-SMOKE** | China API/terms and cross-country document comparability are unresolved; issuer domicile must not be inferred from listing venue | One bounded historical and one recent disclosure sample per country, with issuer-country evidence, timestamps, text availability, and terms check |
| Company | Job postings | Exclude from MVP | **NO-GO** | No four-country, stable, legally documented, reproducible official acquisition path was verified | None unless Human later supplies a licensed, documented dataset covering all four countries |
| General interest | Google Trends official API alpha | Preferred only if access is granted and alpha terms pass review | **NEEDS-SMOKE** | Limited alpha access; sampled/relative interest; API terms and credentials are not yet evidenced locally | Confirm entitlement, export all 8 cells for the full period twice, and compare repeated results/scales |
| General interest | Google Trends UI CSV | Bounded manual fallback | **CONDITIONAL** | Each UI request is normalized to 0–100; separate requests cannot be treated as a common absolute scale | Export both themes together per country with exact query parameters; repeat and compare; restrict claims to within-query/within-country change |
| General interest | Unofficial Trends libraries | Do not adopt | **NO-GO** | Undocumented endpoints and brittle automation/ToS posture | None |

No candidate is `GO` at preflight because no actual M5 source sample was acquired. Documentation review is not a substitute for the RF sample requirement.

## 2. Research Sensor

### 2.1 OpenAlex

**What is observed.** A Work record represents a scholarly work indexed by OpenAlex. The defensible initial signal is the weekly count of qualifying Works, not authors, citations, or social diffusion. OpenAlex documents a global works corpus, REST filtering/search/grouping, and a public snapshot. Its current docs state that all OpenAlex data is CC0. [API reference](https://help.openalex.org/api/) · [snapshot reference](https://help.openalex.org/access/snapshot/)

**Unit / population candidate.** Unit: one distinct core-corpus OpenAlex Work ID with `publication_date` in the weekly window, at least one target-country authorship country, and a deterministic dictionary match in the selected text fields. Population candidate: all core-corpus Works returned under the frozen country/date/type rules. Denominator candidates must be tested separately: all Works with the country evidence in that week, plus counts with usable title and abstract. Do not use citation count as the primary unit.

**Country evidence.** `authorships.institutions.country_code` and `authorships.countries` are structured ISO country attributes. They originate from matched ROR institutions or an explicit country in the raw affiliation address. OpenAlex explicitly documents imperfect institution parsing and known failure modes. Preserve every matched target country on multi-country Works, retain no-country records as `unknown`, and record whether evidence was institution-backed or direct-address-derived when available. Do not collapse multi-country attribution before Gate E. [Authorship attributes](https://help.openalex.org/data/authorships/) · [institution country assignment and failure modes](https://help.openalex.org/data/institutions/)

**Timestamp semantics.** `publication_date` is usually the earliest electronic-publication date selected for the primary location and is the best current candidate for Canonical event time. `created_date` is when the Work entered OpenAlex. `updated_date` is the last change to any record field, including citation-count changes, and must not be treated as publication or topic activity. `observed_at` and local `ingested_at` remain run metadata. [Work attributes](https://help.openalex.org/data/works/attributes/)

**Theme evidence.** Title is broadly available; `abstract_inverted_index` may be null and, when present, can be deterministically reconstructed. The docs report abstract availability above 60% for 2022 Works but warn that reconstructed abstracts can contain trailing non-abstract text. M6 must compare title-only and title-plus-abstract results and record text availability by country/language. OpenAlex topics/keywords are algorithmic metadata and may be retained as auxiliary evidence, not as the primary two-theme classifier. The primary classifier remains the versioned JP/EN/KR/ZH dictionary, including exclusions and no ambiguous standalone `agent`.

**Historical coverage.** The documented corpus and snapshot cover historical Works well before 2022-11-30. The API supports date filtering and cursor paging. This establishes documented availability, not actual 8-cell coverage. The free public snapshot is quarterly, complete, anonymous, available as JSONL or Parquet, and hundreds of GB; it is inappropriate for the first smoke but a reproducible fallback after source adoption. [Snapshot reference](https://help.openalex.org/access/snapshot/)

**Access method / rate and cost.** Start with the REST API and a free API key. Current limits include 100 requests/second, 100 results/page, 10,000 results under basic paging, and cursor paging beyond that. A free key currently provides a $1/day budget, documented as up to 10,000 list/filter calls or 1,000 searches if used exclusively; keyless use is one tenth. The smoke must log response cost and remaining budget and must not buy usage automatically. [Authentication and limits](https://help.openalex.org/api/authentication/) · [example costs](https://help.openalex.org/access/example-costs/)

**Licensing / redistribution.** OpenAlex declares its data CC0. Local API Raw and source metadata can therefore be retained, subject to the project's public-safety rules. Despite that declaration, public repository samples should contain only the minimum metadata needed to reproduce the decision; do not download or redistribute linked PDFs. The full-text/content service is outside this smoke.

**Minimum smoke.** Use three fixed ISO-week windows (first eligible week, one midpoint week, latest complete week). For each of 4 countries × 2 themes, collect bounded result metadata and the total count; separately collect a country-week denominator. Record Work ID, source URL, title, abstract presence, publication/created/updated values, authorship countries and provenance available in the response, language, type, query, response count, observed time, cost headers, and error state. Apply the candidate dictionary locally to the returned text and manually review a stratified positive/negative sample.

**Failure fallback.** First narrow to title-only or selected Work types while stating the coverage loss. If one or more country-theme cells remain unobservable, test arXiv only as a coverage cross-check; do not infer missing OpenAlex countries. If no source demonstrates all 8 cells over the required period, RF is blocked and M7 backfill does not start.

**Recommendation: NEEDS-SMOKE / likely primary.** It is the only reviewed candidate that documents structured four-country affiliation, historical dates, topic text, scalable access, and permissive metadata redistribution in one source. This is a preliminary inference from documentation, not RF evidence.

### 2.2 arXiv

**What is observed.** One arXiv e-print/version with title, abstract, authors, categories, first-submission time, and latest-version time. Unit candidate: one distinct base arXiv ID first submitted in the week and matching the frozen dictionary. Population candidate: all arXiv records under the frozen category and date scope. The source observes preprints, not research output generally.

**Country evidence.** Author affiliation is optional and appears as a free-text `arxiv:affiliation` field. The official API exposes no normalized institution or country field. Only an explicitly written country/address could qualify as country evidence; abbreviated institution names such as the official example `NMSU` cannot be converted to a country under the no-inference rule. This is the central reason arXiv is not the primary four-country path. [API metadata fields](https://info.arxiv.org/help/api/user-manual.html)

**Timestamp semantics.** Atom `published` is the processed date of version 1; `updated` is the processed date of the retrieved version. Use `published` for the candidate weekly event time. Do not interpret later version updates as new research emergence without a separate approved measure. API feed `updated` is feed freshness, not article activity.

**Theme evidence and history.** Title and abstract are documented descriptive metadata and support deterministic matching. API sorting includes submitted and last-updated dates. History easily predates the required start, but the legacy query API caps a call at 30,000 results, recommends queries below 1,000, and directs bulk metadata harvesting to OAI-PMH. Repeated legacy API calls must be single-connection and no more than one every three seconds. [API manual](https://info.arxiv.org/help/api/user-manual.html) · [API Terms](https://info.arxiv.org/help/api/tou.html)

**Licensing / redistribution.** Descriptive metadata—including title, abstract, authors, identifiers, and classifications—is CC0 and may be retrieved, stored, transformed, and shared. E-print PDFs/source files have per-item licenses; the majority are not generally redistributable. Public outputs must cite/link to arXiv and must not mirror e-prints without the applicable license. arXiv requests a specific acknowledgment for API use. [license policy](https://info.arxiv.org/help/license/index.html) · [bulk access warning](https://info.arxiv.org/help/bulk_data_s3.html)

**Minimum smoke.** For both themes, take fixed bounded samples from the first eligible month and a recent complete month. Measure affiliation presence, explicit country-address presence for JP/US/KR/CN, title/abstract availability, version handling, duplicate base IDs, and dictionary false positives. No institution-name lookup is allowed in this smoke.

**Failure fallback.** Retain arXiv only to corroborate topic timing or OpenAlex records without making country-level claims. If explicit country coverage is low—as expected from the schema—record `NO-GO for four-country primary; CONDITIONAL cross-check` rather than expanding personal/author inference.

**Recommendation: CONDITIONAL.** Good reproducible research metadata, poor country evidence.

## 3. Developer Sensor

### 3.1 GitHub REST API

**What is observed.** The smallest defensible MVP measure is **new qualifying public repositories created per week by approved Organization country**, with a separately labeled current stock snapshot. This is narrower than “developer activity.” Stars, current topics, `pushed_at`, and current repository existence are mutable snapshots and cannot reconstruct weekly popularity or activity since 2022.

**Unit / population candidate.** Unit: one non-fork, public repository owned by a Human-approved Organization, with repository `created_at` in the week and a deterministic match in name/description/topics/approved README excerpt. Population: all public, non-fork repositories for the fixed Organization registry, including nonmatching repositories for denominators. Denominator candidates: all qualifying repositories created by those Organizations per week and number of active Organizations with API coverage. Personal-account repositories are excluded, not reclassified as organizations.

**Country evidence.** The Organization API exposes a public `location` string and `is_verified`, but `location` is free text, optional, and not necessarily legal headquarters. Country must come from a versioned Organization registry whose evidence is an explicit organization-level public field or official organization/company page. Listing venue, member location, contributor location, language, or repository text is not country evidence. If an Organization cannot be mapped without person-level data, retain `unknown`. [Organizations endpoint](https://docs.github.com/en/rest/orgs/orgs)

**Timestamp semantics.** `created_at` is repository creation and is the only strong historical event candidate in the initial smoke. `pushed_at` is the last push known at observation time, not a historical series. `updated_at` reflects repository metadata updates. `observed_at` and local `ingested_at` must be recorded. The REST Events timeline contains at most 300 events and only the past 30 days, so it cannot support the required history. [Events endpoint](https://docs.github.com/en/rest/activity/events) · [Repositories endpoint](https://docs.github.com/en/rest/repos/repos)

**Theme evidence.** Repository name, description, topics, and selected README text can support deterministic matching. Topics are owner-supplied mutable labels. Current metadata applied to old `created_at` creates time leakage: a repository created in 2022 may have acquired AI text later. The smoke must report this limitation and compare metadata-only against a tiny manually inspected creation-history sample where feasible. Do not use LLM topic classification.

**Historical/API constraints.** Repository Search provides up to 1,000 results per search and up to 100/page; authenticated non-code search is limited to 30 requests/minute, unauthenticated search to 10/minute. Partitioning by creation date can avoid a single 1,000-result truncation only if each partition is checked and recorded. Standard unauthenticated REST access is 60 requests/hour and authenticated user access is generally 5,000/hour; search and secondary limits remain separate. [Search limits](https://docs.github.com/en/rest/search/search) · [REST rate limits](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api)

**Privacy assessment.** The Organization/Repository path is within the frozen privacy boundary only if Raw capture excludes individual user, actor, author, committer, email, and personal-location payloads. Event, commit, contributor, stargazer, watcher, and user-profile harvesting is out of scope. If immutable Raw semantics would require storing those person-level API responses, that path is **BLOCKED PENDING REQUIREMENTS DECISION**. Do not hash personal identity as a workaround; hashing still processes and persists identity.

**Terms / publication.** GitHub's current Acceptable Use Policy permits research use of public, non-personal information when resulting publications are open access and requires compliance with the Privacy Statement. API use is subject to the API Terms and rate limits. Repository content remains subject to its owners' licenses; public repository metadata access does not grant blanket republication rights. Publish queries, organization evidence, source links, counts, and non-personal aggregates—not copied README/code or raw API dumps. [Acceptable Use Policies](https://docs.github.com/en/site-policy/acceptable-use-policies/github-acceptable-use-policies) · [Terms of Service, API Terms](https://docs.github.com/en/site-policy/github-terms/github-terms-of-service)

**Minimum smoke.** Human approves two clearly official Organizations per country (or explicitly records fewer/unknown). For each, list a bounded set of repositories and run creation-date-partitioned searches for one first-period and one recent-period month. Record Organization evidence URL/evidence date, repository ID/URL, owner type, fork/public state, created/pushed/updated/observed times, topic fields, result totals, `incomplete_results`, page boundary, rate headers, and excluded personal fields. Measure unknown Organization rate, cells with zero, and searches exceeding 1,000.

**No-go criteria.** Any target country lacks a defensible Organization set; required cells depend on personal profiles; event history is required; search partitions remain truncated/incomplete; or current-metadata survivorship makes the proposed claim misleading.

**Failure fallback.** Keep only a current, explicitly nonhistorical repository snapshot or record the sensor as no-go. GH Archive is not a first-party GitHub API, contains person-level actors, and would greatly expand Raw/privacy scope; it is not an MVP fallback without a separate requirements/privacy decision.

**Recommendation: NEEDS-SMOKE, narrowly scoped.** It must not be named “developer activity” unless M6 Gate A approves a more meaningful, privacy-safe measure.

## 4. Company Sensor

There is no verified single global company-disclosure source with comparable four-country coverage. The surviving design is a source-specific mosaic with one common conceptual unit: one official issuer disclosure published in the week and matching the frozen dictionary. Source and document type remain explicit dimensions; raw counts are not compared across regulators without Gate A approval.

### 4.1 Concrete shortlist

| Country | Candidate | History / timestamp / text | Access and current official evidence | Country/HQ rule | Recommendation |
|---|---|---|---|---|---|
| US | SEC EDGAR submissions and filing documents | Filing history, accession/filing dates, HTML/text/XBRL; APIs update as filings disseminate and bulk submissions ZIP is nightly | No API key; REST JSON plus public bulk ZIP. Fair Access limit is no more than 10 requests/sec and requires identified, efficient clients. [API docs](https://www.sec.gov/edgar/sec-api-documentation) · [developer policy](https://www.sec.gov/developer) | Use explicit issuer jurisdiction/address/domicile evidence; CIK or US exchange listing alone is not headquarters | **NEEDS-SMOKE / primary US** |
| JP | FSA EDINET API v2 | Dated filing lists and downloadable disclosure packages; required history appears available but exact retained range and text extraction must be sampled | API v2, API key required; official FAQ says disclosed documents available in the viewer are retrievable and advises at most about once/minute because lists update once/minute. [official guide/spec index](https://disclosure2dl.edinet-fsa.go.jp/guide/static/disclosure/WZEK0110.html) · [FAQ](https://disclosure2dl.edinet-fsa.go.jp/guide/static/disclosure/WZEK0090_001.html) | Use explicit filer/head-office metadata or Human-approved issuer registry; do not equate EDINET filing with Japanese HQ automatically | **NEEDS-SMOKE / primary JP** |
| KR | FSS Open DART | Search by company/type/date; filing originals are downloadable XML; corporate overview and corp-code file are available | Registration/API key required; official service documents APIs, bulk financial downloads, and usage limits, but the exact account quota for this project is **UNVERIFIED**. [service overview](https://opendart.fss.or.kr/intro/main.do) · [developer guide](https://opendart.fss.or.kr/guide/main.do?apiGrpCd=DS001) · [terms](https://opendart.fss.or.kr/intro/terms.do) | Use explicit corporate overview/head-office fields or approved registry; preserve missing/foreign-headquartered issuers as unknown/out of scope | **NEEDS-SMOKE / primary KR** |
| CN | CNINFO disclosure / CNINFO Data Service; bounded SSE/SZSE official-announcement fallback | Official announcements and PDFs exist. Historical API field coverage, timestamp semantics, full-text search, and 2022 retention are **UNVERIFIED** | CNINFO Data Service presents an API-doc/login surface, but accessible official API terms, quota, cost, and redistribution rights were not verified in this preflight. [CNINFO Data Service](https://webapi.cninfo.com.cn/) | Use explicit registered address/domicile/head-office evidence from issuer/regulator data; mainland listing alone is not HQ | **NEEDS-SMOKE with stop condition**; **NO-GO** if terms/access cannot be evidenced before freeze |

### 4.2 Measurement and comparability

- Unit candidate: one distinct official disclosure accession/document ID, not a company-week binary unless Gate A chooses that aggregation.
- Population candidate: all in-scope filing/announcement types from a frozen issuer registry per source. The denominator is all in-scope documents in the same source/week and issuers with observable coverage.
- Theme evidence: official title plus searchable filing/announcement text. A title-only fallback is allowed only as a separately named, lower-recall measure. PDF OCR is not assumed. PDFs whose redistribution rights are unclear remain local or are represented by metadata/link only.
- Time: distinguish regulator acceptance/submission time, issuer publication time, source observation time, and local ingestion time. Different filing deadlines and regulator publication lag are source mechanics, not social propagation.
- Cross-country comparison: compare standardized within-source changes only after document-type and issuer-population controls. A raw SEC-vs-EDINET-vs-DART-vs-CNINFO document count is not a common scale.

### 4.3 Minimum smoke

Human supplies a small versioned issuer registry: two clearly headquartered issuers per country, preferably one technology producer and one broad comparator, with official headquarters evidence. For each regulator/source, retrieve metadata for one first-period and one recent-period month; then select at most two documents per theme for title/text checks. Record document ID, issuer ID/name, headquarters evidence URL/date, source/document type, publication/acceptance/observed times, language, text format, query/download route, lag, corrections/withdrawals, quota response, and license/terms URL.

### 4.4 Eliminations and fallback

- **Job postings: NO-GO for MVP.** No official, stable, four-country historical API/bulk source with verified reuse terms was found. Company career pages would require broad heterogeneous scraping and have deletion/survivorship bias.
- **Issuer IR pages as primary: NO-GO.** They are useful only as bounded evidence/fallback links because site structure, retention, timestamps, robots/terms, and publication practices vary by issuer.
- If China remains unverified, the company sensor cannot claim four-country comparability. Keep the other country profiles as M5 evidence, mark this lane no-go for final four-country analysis, and rely on a different sensor for RF.

**Recommendation: NEEDS-SMOKE.** Adopt only if all four country-specific source profiles pass their own terms, history, country, and timestamp checks. A partial company lane may still be published descriptively but cannot satisfy the Research MUST alone.

## 5. General-interest Sensor

### 5.1 Google Trends official API alpha

**What is observed.** Relative Google Search interest, not query volume, public opinion, adoption, or population share. Google states that Trends uses an anonymized, categorized, aggregated sample, normalizes by geography/time search totals, filters low-volume and duplicate searches, and adds statistical noise. Zero can mean insufficient volume, not absence. [Trends data FAQ](https://support.google.com/trends/answer/4365533?hl=en)

**Historical/country/time feasibility.** The alpha documents a rolling 1,800-day/five-year window, daily/weekly/monthly/yearly aggregation, country/subregion restriction, data up to roughly two days ago, and consistent scaling across API requests. On 2026-08-23, the rolling window covers 2022-11-30, but this must be rechecked at run time because the start boundary advances daily. API values remain relative interest, not absolute counts. [official alpha docs](https://developers.google.com/search/apis/trends) · [official announcement](https://developers.google.com/search/blog/2025/07/trends-api)

**Access / repeatability / terms.** The API remains alpha and available only to a limited set of approved testers. Project entitlement, credential handling, exact quota, alpha-specific terms, response stability, revision behavior, and data-retention permission are **UNVERIFIED** until Human provides access and terms. Do not make the alpha a hard dependency before entitlement is evidenced.

**Theme/query evidence.** Use the frozen language dictionary to define explicit queries/topics per country, but do not sum query series unless the overlap and scale rule is frozen. “Topic” and “search term” are different query semantics and must not be silently mixed. Two themes should be requested in the same call when supported; otherwise the API's documented consistent scale must be verified empirically. Results support within-country time change. Cross-country level comparison still requires Gate A because normalized interest has different search populations and volumes.

**Minimum smoke.** Confirm alpha entitlement and archive the applicable terms URL/version. Request weekly data from 2022-11-30 through the latest complete week for both themes in each country, then repeat identical requests on a second observation date. Record exact term/topic IDs, language, geo, category, search property, period, interval, timezone, returned scale metadata, values, zeros, response/revision identifiers if present, observed time, quota/cost, and terms. Success requires all 8 series, stable joinability, explainable revisions, and no undocumented automation.

**Recommendation: NEEDS-SMOKE / preferred general-interest route if authorized.**

### 5.2 Google Trends UI CSV

The official UI supports CSV export and requires attribution when Trends data is reused. The UI scales every request to 0–100; therefore separately exported requests are not a common scale. Long-range graphs use UTC. Manual export is legally and operationally preferable to automating undocumented UI endpoints. [export/citation help](https://support.google.com/trends/answer/4365538?hl=en) · [data FAQ](https://support.google.com/trends/answer/4365533?hl=en)

**Bounded procedure.** Export both themes together for each country over the identical full period, with all query settings and result URLs recorded. Repeat once. If the UI cannot hold all language variants together, use a predeclared reference query repeated in every batch and treat any rescaling as an M6 methodology decision—not an automatic merge. Publish only within-query or separately normalized within-country change; never compare raw 0–100 levels from separate requests.

**Recommendation: CONDITIONAL manual fallback.** This can support an MVP series if reproducibility differences are measured and the Human accepts manual acquisition. It is not an automated weekly connector.

### 5.3 Alternatives and eliminations

- **Google Trends BigQuery public dataset: NO-GO for the required dictionary series.** It provides Top 25 and Top 25 Rising queries by country with a rolling historical enrichment, but arbitrary fixed theme queries are not the population; recent top-term selection creates severe selection/truncation bias. It may be a contextual source only. [official dataset help](https://support.google.com/trends/answer/12764470?hl=en)
- **Wikimedia Analytics API: NO-GO as direct fallback pending contrary sample evidence.** Official endpoints provide project-by-country totals, per-page time series, and country top-page lists from 2015, under CC0. The reviewed documentation does not establish a single per-page × viewer-country historical endpoint. Language edition is not country, and top-page lists impose top-k selection. [pageview API](https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/reference/page-views.html) · [access/license policy](https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/documentation/access-policy.html)
- **Unofficial Google Trends clients: NO-GO.** They rely on undocumented web endpoints and cannot be the default legally reproducible path.

## 6. Cross-sensor Research Feasibility

**RF PRELIMINARY VIABLE — RF IS NOT PASSED.**

The documented OpenAlex path appears capable of `JP / US / KR / CN × Generative AI / AI Agent × 2022-11-30 onward`: it offers historical Works, structured authorship country attributes, publication dates, title/abstract metadata, deterministic local classification, API paging, and CC0 metadata. Google Trends could provide a second path if official alpha access exists or bounded UI CSV proves repeatable. Company and GitHub are not presently reliable RF anchors.

This is only preliminary because no actual M5 record/count sample exists. RF may pass only after a sample demonstrates:

1. at least one non-error, traceable weekly series route across every one of the 8 cells and the required historical boundary;
2. an explicit population and denominator or a justified denominator-free index;
3. country evidence and measured `unknown`, including multi-country behavior;
4. usable theme text and acceptable false-positive/false-negative evidence;
5. publication/event/observed/ingestion time separation; and
6. reproducible acquisition under current terms and quota.

If OpenAlex fails even one required country-theme path and no authorized Trends path succeeds, report `RF PRELIMINARY BLOCKED`, do not begin M7 bulk backfill, and return the Research MUST as blocked. Sparse or null values are acceptable; an unavailable or untraceable series is not the same as a zero.

## 7. M5 Smoke Matrix for Cursor

| Candidate | Exact objective / minimum request | Fields to record | Success criteria | No-go criteria | Credential / expected cost-quota | Legal/ToS check |
|---|---|---|---|---|---|---|
| OpenAlex | 4 countries × 2 themes × 3 fixed weeks plus 4 country denominators per week; at most 100 records/cell | Query, count, Work ID/URL, title, abstract presence, language/type, all authorship countries, country evidence form, publication/created/updated/observed, paging/cost headers, error | Every cell query is reproducible; historical/current records and denominator exist; country/unknown and text coverage measurable | Missing target cell due to schema/access, unacceptable unknown/text absence, unstable query, or terms conflict | Free API key; bounded smoke should remain within the documented $1/day free budget; log actual cost | Recheck CC0/API/snapshot pages; no PDF/content download |
| arXiv | Two themes × two fixed months; bounded 40-record sample/theme/month | Base/version ID, title, abstract, published/updated, categories, raw affiliation presence, explicit country text, observed, query/page | Useful metadata and enough explicit country evidence for the stated fallback role | Country requires institution/name inference or explicit coverage is insufficient | No key documented; one connection and ≤1 request/3 sec | Recheck API Terms; metadata CC0; cite arXiv; no e-print redistribution |
| GitHub | Human-approved 2 Organizations/country; bounded repository lists plus two month-partitioned creation searches | Org evidence URL/date, org location/verified state, repo ID/URL, owner type, fork/public, created/pushed/updated/observed, name/description/topics, result count, incomplete flag, rate headers, excluded fields | Non-personal 8-cell sample, bounded partitions below cap, meaningful repository-creation measure, measured unknown | Personal data needed, 1,000 cap/incomplete results unresolved, no country orgs, or historical claim depends on events/current mutable metadata | Prefer fine-grained read token; authenticated search 30/min and core generally 5,000/hour; no paid tier | Recheck API Terms, Acceptable Use, Privacy; publish aggregates/links only |
| SEC EDGAR | Two approved issuers; first-period and recent-month filing metadata; ≤2 matched docs/theme | CIK/accession, issuer/country evidence, form, filing/acceptance date, source URL, title/text format, observed, correction, lag | 2022 history, official text, stable ID/time, reproducible query/download | HQ evidence or historical text unavailable; document types cannot be bounded | No key; ≤10 requests/sec, use identifiable User-Agent; zero expected fee | Recheck SEC developer/privacy rules; public redistribution status of each document remains conservative |
| EDINET | Same bounded pattern for two approved issuers | EDINET/doc ID, filer/HQ evidence, form, submit/publication time, files/text, observed, corrections, API response | API-key access, required history/text, explicit country and stable timestamps | Key unavailable, retained history insufficient, or redistribution/terms cannot be established | Human-issued API key; poll ≤about once/min; fee **UNVERIFIED** | Read current API v2 spec and applicable site/use terms before storage/publication |
| Open DART | Same bounded pattern for two approved issuers | corp code, report number, issuer/HQ evidence, report type/name, receipt date, XML/text, observed, corrections, quota | Required history and XML/title text with reproducible corp/date query | Quota/account/terms or HQ/history/text fails | Registration/API key; project quota and fee **UNVERIFIED** | Capture current terms and account quota; do not publish original filings by default |
| CNINFO / SSE / SZSE | Two approved mainland issuers; first-period and recent metadata; ≤2 matched docs/theme | issuer/security/document ID, explicit domicile/HQ, announcement type/title, publication time, download URL/format, observed, API/manual route | Official repeatable history and text, documented access/terms, explicit country | Any API/terms/quota/retention remains unverified by freeze; broad scraping required | Account/key/cost/quota **UNVERIFIED** | Human must capture official API agreement/terms; public redistribution defaults to prohibited/unknown |
| Trends alpha | 4 geos × 2 themes, identical full weekly range, repeated on two observation dates | Exact term/topic, geo/category/property, period/interval/timezone, values/zeros, scale/revision metadata, observed, quota/cost | 8 series, full boundary, consistent joinable scale, explainable repeat variation, authorized use | No entitlement/terms, moving window misses start, unstable/unjoinable series | Alpha approval/credential required; quota/cost **UNVERIFIED** | Archive alpha terms/version and permitted storage/publication scope |
| Trends UI CSV | One two-theme export/country for full period, repeated once | Query/result URL, term-vs-topic, geo/category/property, CSV, UTC/granularity, observed, UI version if visible | Four repeatable paired exports; claims limited to within-query/within-country scale | Separate scales must be mixed, export unavailable, or variation is too large | Human browser; no API credential; manual time cost only | Use official export and attribution; no scripted UI endpoint |

All smoke outputs stay local until the licensing matrix below permits publication. A success response with zero results is recorded as a valid zero only when the request and population are demonstrably available; authentication, quota, parsing, and coverage failures are not zeros.

## 8. Inputs Needed for M6 Gate A–E

| Sensor | Gate A: unit / population / denominator / normalization | Gate B: proxy limitation | Gate C: time evidence | Gate D: dictionary evidence | Gate E: country / unknown / privacy evidence |
|---|---|---|---|---|---|
| Research | Distinct Work/base-ID dedupe; country-week corpus denominator; title/abstract coverage; multi-country counting sensitivity; source/type mix | “Indexed scholarly output/preprint,” not thought, adoption, or a social layer | Field-level samples of publication/first submission, version update, source created/updated, observed, ingestion; timezone and lag | JP/EN/KR/ZH positives, exclusions, title-only vs abstract delta, ≥stratified false-positive/negative review per cell | Raw authorship countries, evidence provenance, no-country rate, multi-country examples, OpenAlex-vs-raw-affiliation mismatch; no author-name inference |
| Developer | Repository creation unit, fixed Organization registry/population, non-fork denominator, search truncation/deletion survivorship, current-metadata leakage | “Public organization repository creation,” not developer population, usage, productivity, or meso diffusion | Repo created/pushed/updated/observed samples; proof that Events cannot backfill; no fabricated event series | Metadata-field ablation, ambiguous `agent` exclusions, current-topic mutation examples, manual positive/negative review | Versioned Organization-country evidence, unknown org/repo share, org transfer cases; proof no User identity/location entered Raw/Canonical/public artifacts |
| Company | Disclosure ID and issuer population; document-type denominator; issuer coverage; within-source normalization; regulator/source fixed effects | “Official corporate disclosure behavior,” not company adoption, investment, or meso diffusion | Acceptance/publication/observed/ingestion samples, corrections/withdrawals, regulator and document-type publication lag | Title-vs-body recall, language/document boilerplate exclusions, OCR/text failures, reviewed sample by source/theme | Explicit issuer domicile/HQ evidence, foreign issuers and changes, unknown rate; no inference from exchange or language |
| General interest | Relative search-interest index or paired UI index; query population; normalization/sampling/noise; zero semantics; no absolute volume denominator | “Google Search interest,” not public opinion, prevalence, adoption, or macro layer itself | Week boundary, UTC, API two-day lag, observed/ingestion, repeated-query revision | Exact term/topic IDs and variants; overlap/double-count rules; term vs topic; same-request/batch/reference-query test | Service `geo` parameter as country evidence; no language-edition proxy; low-volume/zero coverage per country; aggregate-only privacy boundary |

Gate A–E remain open after this preflight. M6 must freeze only the sensors that have the above sample evidence; others remain Raw-only or no-go.

## 9. Licensing / Publication Matrix

| Candidate | Local Raw storage | Public repository redistribution | Metadata citation | Derived aggregate publication |
|---|---|---|---|---|
| OpenAlex metadata | **YES**, declared CC0; keep only required fields | **YES under CC0**, but prefer minimal metadata/IDs; no linked PDFs | Cite OpenAlex, query, snapshot/API version, access date | **YES**, with source/method/coverage citation |
| arXiv descriptive metadata | **YES**, CC0 | **YES for descriptive metadata**; **NO by default** for PDFs/source/e-prints | Required acknowledgment/source link should be included | **YES**, with attribution and no mirrored e-print content |
| GitHub Organization/Repository metadata | **CONDITIONAL**: public non-personal allowlist only; token excluded | **NO for raw API dumps/content by default**; publish source links and synthetic fixtures | **YES**, with API query/date and GitHub attribution where appropriate | **CONDITIONAL YES** for non-personal open-access research output under current policies |
| SEC EDGAR | **YES for bounded official retrieval**, subject to current SEC access policy | **CONDITIONAL / UNVERIFIED per document**; do not commit full filings | **YES** | **YES**, with accession/source links and methodology |
| EDINET | **CONDITIONAL** pending current API/site terms captured in smoke | **UNVERIFIED**; metadata/link only until verified | **YES** | **CONDITIONAL**, after terms and document quotation rules are verified |
| Open DART | **CONDITIONAL** under registered API terms/quota | **UNVERIFIED** for original filing payloads | **YES** | **CONDITIONAL**, cite report number/source and verify terms |
| CNINFO / SSE / SZSE | **UNVERIFIED** | **UNVERIFIED / default NO** | **YES for source links** | **UNVERIFIED** until API/service agreement is reviewed |
| Google Trends alpha | **UNVERIFIED until alpha terms/access are supplied** | **UNVERIFIED** | **YES**, Google attribution required | **CONDITIONAL**, subject to alpha terms and clear relative-interest labeling |
| Google Trends UI CSV | **CONDITIONAL YES** for bounded research evidence under Google Terms | **CONDITIONAL**; do not commit raw CSV until terms review confirms intended reuse | **YES**, official help requires Google attribution | **CONDITIONAL YES**, with attribution, query settings, and normalization caveat |
| Google Trends BigQuery dataset | **CONDITIONAL** under Google Cloud dataset terms | **UNVERIFIED** for row-level republication | **YES** | **YES if used only as contextual derived output and terms are followed** |
| Wikimedia Analytics API | **YES**, CC0 | **YES**, CC0 | **YES** | **YES**, but it does not currently qualify as the required theme-country path |

Secrets/API keys belong only in the configured secret mechanism and never in Raw envelopes, logs, screenshots, fixtures, or commits. Where public redistribution is `UNVERIFIED`, publish a reacquisition recipe, schema, source ID/URL, hashes where lawful, and synthetic examples—not source payloads.

## 10. Adversarial Findings

1. **OpenAlex can look complete while being country-biased.** Structured country is produced by affiliation matching with documented errors and missing affiliations; Korean/Chinese non-English metadata or corporate affiliations may have different coverage. A global count alone cannot validate the 8 cells.
2. **OpenAlex “publication date” is a selected bibliographic date.** Earliest electronic publication and primary-location choice can move the apparent onset. `updated_date` is especially invalid as emergence time because unrelated citation changes update it.
3. **arXiv country attribution is not solved by having affiliation text.** Converting abbreviations or institution names to countries is inference and would violate the frozen rule unless an explicit approved authority mapping becomes part of requirements/methodology.
4. **GitHub repository creation is a stock-survivor sample.** Deleted, renamed, transferred, or privatized repositories disappear or move; old repositories are classified with current text/topics. Apparent historical changes may be present-day survivorship and metadata editing.
5. **GitHub Events do not provide the required history.** Official REST event timelines retain only 30 days. A third-party archive would alter provenance, privacy, storage, and terms and cannot silently replace the candidate.
6. **GitHub Organization location is not necessarily headquarters.** It is optional free text. Expanding to members' personal locations would breach the explicit boundary and still would not establish organization country.
7. **Company regulator counts have incomparable publication regimes.** Filing mandates, issuer populations, document types, corrections, languages, and deadlines differ. A spike can reflect a deadline or policy change, not company attention or propagation.
8. **The China company path is the critical weak link.** An official visible portal is not proof of authorized programmatic history, stable quota, text search, or redistribution. If these remain unverified, the lane is no-go for four-country findings.
9. **IR pages and jobs create survivorship bias.** Current pages omit removed postings and older releases; heterogeneous scraping would select companies by site design. Neither is an acceptable primary plan.
10. **Google Trends values are not volumes.** They are sampled, normalized relative interest with low-volume suppression and noise. Zero is not “no interest,” and equal values across countries do not imply equal search counts.
11. **UI Trends exports are request-relative.** Mixing separate 0–100 requests can manufacture leads and country differences. Even an anchor approach needs a frozen transformation and stability evidence.
12. **The alpha API is not an entitlement.** Public documentation of an alpha does not prove this project can call it or retain/publish responses. The moving five-year window also means the required start date will eventually age out.
13. **BigQuery Top 25 and country top-page alternatives are selected outcomes.** They answer “what made the top list,” not “how did the fixed two themes vary.” Backfilled scores for recently selected terms do not remove selection bias.
14. **Four sensors do not equal four social layers.** Each is a source-specific proxy. Cross-sensor scale, publication lag, and population differences can mimic diffusion. Gate B and C must prevent layer labels or causal propagation claims from becoming sensor facts.

## 11. Recommended M5 Execution Order

1. **OpenAlex first.** It is the most plausible RF anchor, requires only a small free-key smoke, and can reveal country/text/period failure early.
2. **Google Trends entitlement check in parallel as a Human action, then alpha smoke or manual CSV.** Access uncertainty is binary and time-sensitive; do not wait until after company-source work to discover no entitlement.
3. **China company-source legal/access smoke.** It is the company lane's dominant blocker. Stop the four-country company path immediately if official terms/history cannot be evidenced; do not compensate with scraping.
4. **SEC, EDINET, and Open DART bounded metadata/document smokes.** Run only after the common document/issuer evidence fields are fixed, and retain source-specific denominators.
5. **GitHub Organization/Repository smoke.** Require the Human-approved organization registry and privacy field allowlist first. Stop if the measure requires event/individual data.
6. **arXiv fallback smoke only if OpenAlex coverage needs corroboration.** Do not spend deadline budget trying to manufacture structured country data from free text.
7. **Write M5 decisions and attempt RF.** Pass RF only from actual coverage profiles; then hand samples—not conclusions—to M6 Gate A–E before any backfill.

This order protects the 2026-08-31 Architecture Freeze by testing the sole plausible RF anchor and the largest access/legal blockers before lower-value expansions.

## 12. Open Decisions

1. **Human: Google Trends alpha entitlement and terms.** Supply proof of access, current quota/cost, and the applicable alpha agreement; otherwise approve bounded manual UI export or mark the lane no-go.
2. **Human: Organization registry scope.** Approve the initial GitHub Organizations and organization-level headquarters evidence. No individual profile may be added to improve coverage.
3. **Human: Company issuer registry.** Approve two bounded issuers per country and the explicit headquarters/domicile evidence hierarchy; regulator venue alone is insufficient.
4. **Human: China company source.** Decide whether a CNINFO Data Service account/API agreement is available for review. If not available by the M5 cutoff, approve a company-lane no-go rather than broad scraping.
5. **Sample-dependent: OpenAlex country rule candidate.** M6 Gate E must decide full counting vs another multi-country aggregation only after reporting sensitivity and unknown; M5 does not freeze it.
6. **Sample-dependent: research unit and denominator.** M6 Gate A must choose Work vs source-specific item, document-type scope, and denominator after coverage inspection.
7. **Sample-dependent: theme text boundary.** M6 Gate D must choose title-only vs title-plus-abstract/body and freeze the 4-language dictionary after Human review.
8. **Sample-dependent: Trends query batching/normalization.** M6 Gate A/D must approve term-vs-topic definitions and any reference-query transformation. Separate UI scales may not be merged by default.
9. **Sample-dependent: GitHub viability.** If repository creation is too weak a proxy, choose no-go. Any proposal to use individual-level commits/events is blocked pending a formal requirements/privacy decision.

M5 PREFLIGHT STATUS: EXTERNAL REVIEW PASS
