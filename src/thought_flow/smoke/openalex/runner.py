"""Bounded OpenAlex M5 smoke runner (Phase 1)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from thought_flow.observability.identity import new_run_identity
from thought_flow.smoke.artifacts import (
    M5RunPaths,
    append_jsonl,
    utc_now,
    write_coverage_csv,
    write_json,
)
from thought_flow.smoke.http_client import RequestBudget, SmokeHttpClient
from thought_flow.smoke.openalex.client import (
    MAX_INSPECTED_PER_CELL,
    MAX_PAGES_PER_CELL,
    MAX_RETAINED_PER_CELL,
    PER_PAGE,
    OpenAlexClient,
    build_filter,
)
from thought_flow.smoke.openalex.project import (
    extract_record_from_envelope,
    openalex_raw_content_identity,
    project_work_to_privacy_reduced,
    reconstruct_abstract,
)
from thought_flow.smoke.periods import (
    OA_RECENT,
    OPENALEX_COUNTRIES,
    OPENALEX_PERIODS,
    OPENALEX_THEMES,
    SmokePeriod,
)
from thought_flow.smoke.progress import progress
from thought_flow.smoke.quality import QualityState
from thought_flow.smoke.vocabulary import (
    classify_title_and_abstract,
    load_provisional_vocabulary,
    positive_phrases_for_country,
)


def _stable_work_id(work: dict[str, Any]) -> str:
    return str(work.get("id") or "")


@dataclass
class CellResult:
    cell_kind: str
    country: str | None
    theme: str | None
    period_id: str
    quality_state: QualityState
    source_total: int | None = None
    phrase_source_counts: dict[str, int] = field(default_factory=dict)
    inspected_count: int = 0
    retained_count: int = 0
    matched_count: int = 0
    missing_country_count: int = 0
    multi_country_count: int = 0
    unknown_country_count: int = 0
    title_only_match_count: int = 0
    title_plus_abstract_match_count: int = 0
    abstract_present_count: int = 0
    pages_used: int = 0
    truncation: bool = False
    observation_complete: bool = False
    stop_reason: str | None = None
    unexecuted_phrases: list[str] = field(default_factory=list)


class OpenAlexSmokeRunner:
    def __init__(
        self,
        *,
        data_root: Path,
        code_revision: str,
        api_key: str | None = None,
        http: SmokeHttpClient | None = None,
        vocab_path: Path | None = None,
        sleep_fn: Callable[..., None] | None = None,
    ) -> None:
        self.data_root = data_root
        self.m5_root = data_root / "m5-smoke"
        self.code_revision = code_revision
        self.vocab = load_provisional_vocabulary(vocab_path)
        client_http = http or SmokeHttpClient()
        if sleep_fn is not None:
            client_http.sleep_fn = sleep_fn
        self.client = OpenAlexClient(http=client_http, api_key=api_key)
        self.run_id = new_run_identity()
        self.paths = M5RunPaths.create(self.m5_root, self.run_id)
        self.coverage: list[dict[str, Any]] = []
        self.terminal_stop: str | None = None

    @property
    def budget(self) -> RequestBudget:
        return self.client.budget

    def run(self) -> dict[str, Any]:
        progress("run initialized", f"run_id={self.run_id} mode=full")
        return self._run_body(mode="full")

    def run_diagnostic_one_cell(
        self,
        *,
        country: str = "US",
        theme: str = "generative_ai",
        period: SmokePeriod | None = None,
    ) -> dict[str, Any]:
        """Live pipeline diagnostic: one country×theme×period cell only. Not SMOKE-PASS."""
        selected = period or OA_RECENT
        progress(
            "diagnostic cell selected",
            f"source=openalex country={country} theme={theme} period={selected.period_id} "
            f"vocab={self.vocab['version']}",
        )
        return self._run_body(
            mode="diagnostic_one_cell",
            diagnostic_country=country,
            diagnostic_theme=theme,
            diagnostic_period=selected,
        )

    def _run_body(
        self,
        *,
        mode: str,
        diagnostic_country: str | None = None,
        diagnostic_theme: str | None = None,
        diagnostic_period: SmokePeriod | None = None,
    ) -> dict[str, Any]:
        started = utc_now()
        progress("manifest/result write", f"phase=start path={self.paths.manifest_path}")
        write_json(
            self.paths.manifest_path,
            {
                "schema_version": "m5-smoke-manifest/v1",
                "run_id": self.run_id,
                "run_type": "m5_smoke",
                "status": "started",
                "started_at": started,
                "code_revision": self.code_revision,
                "smoke_vocabulary_version": self.vocab["version"],
                "source": "openalex",
                "phase": "openalex_phase1",
                "execution_mode": mode,
            },
        )

        try:
            if mode == "diagnostic_one_cell":
                assert diagnostic_country and diagnostic_theme and diagnostic_period
                cell = self._run_theme_cell(
                    country=diagnostic_country,
                    theme=diagnostic_theme,
                    period=diagnostic_period,
                )
                self.coverage.append(cell.__dict__)
            else:
                for period in OPENALEX_PERIODS:
                    for country in OPENALEX_COUNTRIES:
                        for theme in OPENALEX_THEMES:
                            if not self.budget.can_request():
                                self.terminal_stop = self.budget.stop_reason
                                break
                            cell = self._run_theme_cell(
                                country=country, theme=theme, period=period
                            )
                            self.coverage.append(cell.__dict__)
                        if self.terminal_stop:
                            break
                    if self.terminal_stop:
                        break

                if not self.terminal_stop:
                    for period in OPENALEX_PERIODS:
                        for country in OPENALEX_COUNTRIES:
                            if not self.budget.can_request():
                                self.terminal_stop = self.budget.stop_reason
                                break
                            cell = self._run_denominator(country=country, period=period)
                            self.coverage.append(cell.__dict__)
                        if self.terminal_stop:
                            break

                if not self.terminal_stop:
                    for period in OPENALEX_PERIODS:
                        for theme in OPENALEX_THEMES:
                            if not self.budget.can_request():
                                self.terminal_stop = self.budget.stop_reason
                                break
                            cell = self._run_global_audit(theme=theme, period=period)
                            self.coverage.append(cell.__dict__)
                        if self.terminal_stop:
                            break

            ended = utc_now()
            status = "succeeded"
            if self.terminal_stop:
                status = "partial"
            progress("manifest/result write", "phase=coverage_and_licensing")
            write_coverage_csv(self.paths.coverage_path, self.coverage)
            write_json(
                self.paths.privacy_licensing_path,
                {
                    "source": "openalex",
                    "terms_url": "https://help.openalex.org/api/",
                    "licensing_note": "OpenAlex metadata declared CC0; local Raw is privacy-reduced allowlist only.",
                    "personal_data_present": False,
                    "author_fields_persisted": False,
                    "pdf_downloaded": False,
                    "upstream_response_persisted": False,
                    "public_redistribution": "minimal_metadata_preferred",
                    "access_date": started[:10],
                },
            )
            summary = {
                "schema_version": "m5-smoke-manifest/v1",
                "run_id": self.run_id,
                "run_type": "m5_smoke",
                "status": status,
                "started_at": started,
                "ended_at": ended,
                "code_revision": self.code_revision,
                "smoke_vocabulary_version": self.vocab["version"],
                "source": "openalex",
                "phase": "openalex_phase1",
                "execution_mode": mode,
                "http_attempts_used": self.budget.attempts_used,
                "reported_cost_usd": self.budget.cost_usd,
                "cost_ceiling_usd": self.budget.max_cost_usd,
                "stop_reason": self.terminal_stop,
                "coverage_rows": len(self.coverage),
                "artifact_root": str(self.paths.run_dir),
                "rf_recommendation": "not_evaluated_openalex_phase1_only",
            }
            if mode == "diagnostic_one_cell" and self.coverage:
                summary["diagnostic_cell"] = self.coverage[0]
            write_json(self.paths.manifest_path, summary)
            progress(
                "diagnostic finished" if mode == "diagnostic_one_cell" else "full smoke finished",
                f"status={status} attempts={self.budget.attempts_used}",
            )
            return summary
        except Exception as exc:  # noqa: BLE001
            ended = utc_now()
            progress("run failed", f"category={type(exc).__name__}")
            failure = {
                "schema_version": "m5-smoke-manifest/v1",
                "run_id": self.run_id,
                "run_type": "m5_smoke",
                "status": "failed",
                "started_at": started,
                "ended_at": ended,
                "code_revision": self.code_revision,
                "execution_mode": mode,
                "failure_category": type(exc).__name__,
                "failure_message": str(exc)[:500],
                "http_attempts_used": self.budget.attempts_used,
                "reported_cost_usd": self.budget.cost_usd,
                "stop_reason": self.terminal_stop or self.budget.stop_reason,
                "artifact_root": str(self.paths.run_dir),
            }
            write_json(self.paths.manifest_path, failure)
            write_coverage_csv(self.paths.coverage_path, self.coverage)
            raise

    def _run_theme_cell(self, *, country: str, theme: str, period: SmokePeriod) -> CellResult:
        phrases = positive_phrases_for_country(self.vocab, theme=theme, country=country)
        return self._collect_cell(
            cell_kind="country_theme",
            country=country,
            theme=theme,
            period=period,
            phrases=phrases,
        )

    def _run_global_audit(self, *, theme: str, period: SmokePeriod) -> CellResult:
        phrases = positive_phrases_for_country(
            self.vocab, theme=theme, country=None, global_audit=True
        )
        return self._collect_cell(
            cell_kind="global_theme_audit",
            country=None,
            theme=theme,
            period=period,
            phrases=phrases,
        )

    def _run_denominator(self, *, country: str, period: SmokePeriod) -> CellResult:
        filter_expr = build_filter(period=period, country=country, denominator=True)
        result = CellResult(
            cell_kind="country_period_denominator",
            country=country,
            theme=None,
            period_id=period.period_id,
            quality_state="fetch_failure",
        )
        if not self.budget.can_request():
            result.stop_reason = self.budget.stop_reason
            result.quality_state = "fetch_failure"
            return result
        try:
            payload, meta = self.client.fetch_works_page(
                filter_expr=filter_expr,
                search=None,
                cursor="*",
                per_page=1,
            )
        except Exception as exc:  # noqa: BLE001
            self._log_query(
                cell_kind=result.cell_kind,
                country=country,
                theme=None,
                period=period,
                search=None,
                page_index=1,
                meta={"error": type(exc).__name__, "message": str(exc)[:200]},
                quality_state="fetch_failure",
            )
            result.stop_reason = type(exc).__name__
            return result

        self._log_query(
            cell_kind=result.cell_kind,
            country=country,
            theme=None,
            period=period,
            search=None,
            page_index=1,
            meta=meta,
            quality_state="zero" if meta.get("status_code", 500) < 400 else "fetch_failure",
            source_total=(payload.get("meta") or {}).get("count"),
        )
        result.pages_used = 1
        if meta.get("status_code", 500) >= 400 or payload.get("error"):
            result.quality_state = "fetch_failure"
            result.stop_reason = meta.get("terminal_blocker") or f"http_{meta.get('status_code')}"
            return result

        count = (payload.get("meta") or {}).get("count")
        result.source_total = int(count) if count is not None else None
        # Count-only: do not treat returned Work bodies as inspected theme sample.
        result.inspected_count = 0
        result.retained_count = 1 if result.source_total is not None else 0
        if result.source_total is None:
            result.quality_state = "fetch_failure"
        elif result.source_total == 0:
            result.quality_state = "zero"
            result.truncation = False
            result.observation_complete = True
            result.stop_reason = None
        else:
            # Full count observed; theme not applicable to denominator cell.
            result.quality_state = "missing"
            result.truncation = False
            result.observation_complete = True
            result.stop_reason = "denominator_count_observed"
        return result

    def _collect_cell(
        self,
        *,
        cell_kind: str,
        country: str | None,
        theme: str,
        period: SmokePeriod,
        phrases: list[tuple[str, str]],
    ) -> CellResult:
        filter_expr = build_filter(period=period, country=country)
        result = CellResult(
            cell_kind=cell_kind,
            country=country,
            theme=theme,
            period_id=period.period_id,
            quality_state="fetch_failure",
        )
        progress(
            "pagination start",
            f"cell={cell_kind} country={country} theme={theme} period={period.period_id} "
            f"phrases={len(phrases)}",
        )
        retained: dict[str, dict[str, Any]] = {}
        order_keys: list[tuple[int, int, str]] = []
        inspected = 0
        pages_used = 0
        unexecuted: list[str] = []
        any_success = False
        any_failure = False
        phrase_first_totals: dict[str, int] = {}
        second_page_candidates: list[tuple[str, str, str]] = []  # lang, phrase, next_cursor
        phrase_page_hits: dict[str, int] = {}

        def hit_page_ceiling() -> bool:
            return pages_used >= MAX_PAGES_PER_CELL

        def hit_inspect_ceiling() -> bool:
            return inspected >= MAX_INSPECTED_PER_CELL

        def hit_retain_ceiling() -> bool:
            return len(retained) >= MAX_RETAINED_PER_CELL

        # Pass 1: first page per phrase.
        for phrase_idx, (lang, phrase) in enumerate(phrases):
            if hit_page_ceiling() or hit_inspect_ceiling() or hit_retain_ceiling():
                unexecuted.extend(p for _, p in phrases[phrase_idx:])
                break
            if not self.budget.can_request():
                unexecuted.extend(p for _, p in phrases[phrase_idx:])
                result.stop_reason = self.budget.stop_reason
                break
            try:
                payload, meta = self.client.fetch_works_page(
                    filter_expr=filter_expr, search=phrase, cursor="*"
                )
            except Exception as exc:  # noqa: BLE001
                any_failure = True
                self._log_query(
                    cell_kind=cell_kind,
                    country=country,
                    theme=theme,
                    period=period,
                    search=phrase,
                    page_index=pages_used + 1,
                    meta={"error": type(exc).__name__, "message": str(exc)[:200]},
                    quality_state="fetch_failure",
                )
                continue

            pages_used += 1
            self._log_query(
                cell_kind=cell_kind,
                country=country,
                theme=theme,
                period=period,
                search=phrase,
                page_index=pages_used,
                meta=meta,
                quality_state="fetch_failure" if meta.get("status_code", 500) >= 400 else "zero",
                source_total=(payload.get("meta") or {}).get("count"),
            )
            if meta.get("status_code", 500) >= 400 or payload.get("error"):
                any_failure = True
                if meta.get("terminal_blocker"):
                    result.stop_reason = str(meta["terminal_blocker"])
                continue
            any_success = True
            meta_block = payload.get("meta") or {}
            count = meta_block.get("count")
            if count is not None:
                phrase_first_totals[phrase] = int(count)
            results = payload.get("results") or []
            next_cursor = meta_block.get("next_cursor")
            if count is not None and int(count) > PER_PAGE and next_cursor:
                second_page_candidates.append((lang, phrase, str(next_cursor)))

            for result_idx, work in enumerate(results):
                if hit_inspect_ceiling():
                    break
                inspected += 1
                phrase_page_hits[phrase] = phrase_page_hits.get(phrase, 0) + 1
                wid = _stable_work_id(work)
                if not wid or wid in retained:
                    continue
                if hit_retain_ceiling():
                    break
                envelope = self._project_and_persist(
                    work=work,
                    theme=theme,
                    country=country,
                    period=period,
                    phrase=phrase,
                    page_index=pages_used,
                    http_meta=meta,
                )
                retained[wid] = envelope
                order_keys.append((phrase_idx, result_idx, wid))

        # Pass 2: optional second pages for phrases with >25 results, after first pages.
        for lang, phrase, cursor in second_page_candidates:
            if hit_page_ceiling() or hit_inspect_ceiling() or hit_retain_ceiling():
                break
            if not self.budget.can_request():
                result.stop_reason = self.budget.stop_reason
                break
            try:
                payload, meta = self.client.fetch_works_page(
                    filter_expr=filter_expr, search=phrase, cursor=cursor
                )
            except Exception as exc:  # noqa: BLE001
                any_failure = True
                self._log_query(
                    cell_kind=cell_kind,
                    country=country,
                    theme=theme,
                    period=period,
                    search=phrase,
                    page_index=pages_used + 1,
                    meta={"error": type(exc).__name__, "message": str(exc)[:200]},
                    quality_state="fetch_failure",
                )
                continue
            pages_used += 1
            self._log_query(
                cell_kind=cell_kind,
                country=country,
                theme=theme,
                period=period,
                search=phrase,
                page_index=pages_used,
                meta=meta,
                quality_state="fetch_failure" if meta.get("status_code", 500) >= 400 else "zero",
                source_total=phrase_first_totals.get(phrase),
            )
            if meta.get("status_code", 500) >= 400 or payload.get("error"):
                any_failure = True
                if meta.get("terminal_blocker"):
                    result.stop_reason = str(meta["terminal_blocker"])
                continue
            any_success = True
            results = payload.get("results") or []
            for result_idx, work in enumerate(results):
                if hit_inspect_ceiling():
                    break
                inspected += 1
                phrase_page_hits[phrase] = phrase_page_hits.get(phrase, 0) + 1
                wid = _stable_work_id(work)
                if not wid or wid in retained:
                    continue
                if hit_retain_ceiling():
                    break
                envelope = self._project_and_persist(
                    work=work,
                    theme=theme,
                    country=country,
                    period=period,
                    phrase=phrase,
                    page_index=pages_used,
                    http_meta=meta,
                )
                retained[wid] = envelope
                order_keys.append((10_000, result_idx, wid))

        result.pages_used = pages_used
        result.inspected_count = inspected
        result.retained_count = len(retained)
        # Do not sum phrase counts into a cell population total (duplicates across phrases).
        result.phrase_source_counts = dict(phrase_first_totals)
        result.source_total = None
        result.unexecuted_phrases = unexecuted

        matched = 0
        missing_c = 0
        multi_c = 0
        unknown_c = 0
        title_only = 0
        title_plus = 0
        abs_present = 0
        for env in retained.values():
            pm = env.get("provisional_match") or {}
            if pm.get("provisional_match"):
                matched += 1
            if pm.get("title_only_match"):
                title_only += 1
            if pm.get("title_plus_abstract_match"):
                title_plus += 1
            if env.get("abstract_present"):
                abs_present += 1
            if env.get("missing_country"):
                missing_c += 1
                unknown_c += 1
            if env.get("multi_country"):
                multi_c += 1

        result.matched_count = matched
        result.missing_country_count = missing_c
        result.multi_country_count = multi_c
        result.unknown_country_count = unknown_c
        result.title_only_match_count = title_only
        result.title_plus_abstract_match_count = title_plus
        result.abstract_present_count = abs_present

        phrase_truncated = any(
            phrase_first_totals.get(p, 0) > phrase_page_hits.get(p, 0)
            for p in phrase_first_totals
        )
        truncated = bool(
            unexecuted
            or hit_retain_ceiling()
            or inspected >= MAX_INSPECTED_PER_CELL
            or pages_used >= MAX_PAGES_PER_CELL
            or phrase_truncated
        )
        result.truncation = truncated

        if pages_used == 0 and any_failure and not any_success:
            result.quality_state = "fetch_failure"
            result.observation_complete = False
        elif not any_success:
            result.quality_state = "fetch_failure"
            result.observation_complete = False
            if any_failure:
                result.stop_reason = result.stop_reason or "http_or_transport_failure"
        elif truncated:
            # Bounded portion only; unobserved range remains.
            result.quality_state = "partial"
            result.observation_complete = False
            result.stop_reason = result.stop_reason or "bounded_ceiling"
        elif result.retained_count == 0 or matched == 0:
            # Complete observation of the requested cell with no qualifying match.
            result.quality_state = "zero"
            result.truncation = False
            result.observation_complete = True
            result.stop_reason = None
        else:
            # Complete observation with nonzero qualifying results — not partial.
            result.quality_state = "missing"
            result.truncation = False
            result.observation_complete = True
            result.stop_reason = "complete_observation"

        progress(
            "pagination end",
            f"pages={pages_used} inspected={inspected} retained={len(retained)} "
            f"quality={result.quality_state}",
        )
        return result

    def _project_and_persist(
        self,
        *,
        work: dict[str, Any],
        theme: str,
        country: str | None,
        period: SmokePeriod,
        phrase: str,
        page_index: int,
        http_meta: dict[str, Any],
    ) -> dict[str, Any]:
        observed = utc_now()
        abstract = reconstruct_abstract(work.get("abstract_inverted_index"))
        progress("provisional matching", f"work_id={work.get('id')}")
        match_meta = classify_title_and_abstract(
            title=work.get("title") or work.get("display_name"),
            abstract=abstract,
            theme=theme,
            vocab=self.vocab,
        )
        query_meta = {
            "sanitized_url": http_meta.get("sanitized_url"),
            "search_phrase": phrase,
            "page_index": page_index,
            "period": period.to_manifest(),
            "country_filter": country,
            "theme": theme,
            "status_code": http_meta.get("status_code"),
            "retry_count": http_meta.get("retry_count"),
            "cost_usd": http_meta.get("cost_usd"),
            "source_total": None,
        }
        # Project before any persistence; never hash upstream.
        progress("privacy projection start", f"work_id={work.get('id')}")
        envelope = project_work_to_privacy_reduced(
            work,
            observed_at=observed,
            ingested_at=observed,
            query_meta=query_meta,
            match_meta=match_meta,
        )
        progress("privacy projection end", f"checksum={envelope.get('persisted_envelope_checksum')}")
        content_id = envelope.get("raw_content_identity") or openalex_raw_content_identity(envelope)
        raw_path = self.paths.raw_openalex_dir / f"{content_id}.privacy-reduced.jsonl"
        progress("persistence start", f"raw={raw_path.name}")
        append_jsonl(
            raw_path,
            {
                "run_id": self.run_id,
                "raw_content_identity": content_id,
                "observed_at": observed,
                "ingested_at": observed,
                "envelope": envelope,
            },
        )
        append_jsonl(
            self.paths.extracted_openalex_path,
            {
                "run_id": self.run_id,
                "raw_content_identity": content_id,
                "record": extract_record_from_envelope(envelope),
            },
        )
        progress("persistence end", f"raw={raw_path.name}")
        return envelope

    def _log_query(
        self,
        *,
        cell_kind: str,
        country: str | None,
        theme: str | None,
        period: SmokePeriod,
        search: str | None,
        page_index: int,
        meta: dict[str, Any],
        quality_state: str,
        source_total: int | None = None,
    ) -> None:
        material = {
            "source": "openalex",
            "cell_kind": cell_kind,
            "country": country,
            "theme": theme,
            "period_id": period.period_id,
            "search": search,
            "page_index": page_index,
            "sanitized_url": meta.get("sanitized_url"),
        }
        digest = hashlib.sha256(
            json.dumps(material, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        append_jsonl(
            self.paths.queries_path,
            {
                "run_id": self.run_id,
                "observed_at": utc_now(),
                "query_hash": f"q_{digest[:32]}",
                "smoke_vocabulary_version": self.vocab["version"],
                "quality_state": quality_state,
                "source_total": source_total,
                "attempt_number": (meta.get("attempts") or [{}])[-1].get("attempt"),
                "retry_count": meta.get("retry_count"),
                "http_status": meta.get("status_code"),
                "cost_usd": meta.get("cost_usd"),
                "rate": meta.get("observed_headers"),
                **material,
                "period": period.to_manifest(),
                "error": meta.get("error"),
                "error_message": meta.get("message"),
            },
        )


def run_openalex_smoke(
    *,
    data_root: Path,
    code_revision: str,
    api_key: str | None = None,
    http: SmokeHttpClient | None = None,
    diagnostic_one_cell: bool = False,
) -> dict[str, Any]:
    runner = OpenAlexSmokeRunner(
        data_root=data_root,
        code_revision=code_revision,
        api_key=api_key,
        http=http,
    )
    if diagnostic_one_cell:
        return runner.run_diagnostic_one_cell(
            country="US",
            theme="generative_ai",
            period=OA_RECENT,
        )
    return runner.run()
