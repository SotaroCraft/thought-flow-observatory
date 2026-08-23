"""OpenAlex abstract reconstruction and privacy projection."""

from __future__ import annotations

from typing import Any, Mapping

from thought_flow.observability.identity import raw_content_identity
from thought_flow.smoke.privacy import persisted_envelope_checksum

# Person-level keys that must never enter privacy-reduced Raw.
_AUTHOR_OBJECT_KEYS = frozenset(
    {
        "author",
        "raw_author_name",
        "author_position",
        "is_corresponding",
    }
)

# Content-derived identity excludes run/query/observation provenance and checksum.
_CONTENT_IDENTITY_KEYS = (
    "schema",
    "work_id",
    "doi",
    "openalex_url",
    "title",
    "display_name",
    "type",
    "language",
    "primary_location_source",
    "abstract_present",
    "abstract_inverted_index",
    "publication_date",
    "publication_year",
    "created_date",
    "updated_date",
    "institutions",
    "authorship_countries",
    "country_evidence",
    "missing_country",
    "multi_country",
)


def content_identity_payload(envelope: Mapping[str, Any]) -> dict[str, Any]:
    """Source content fields only — no run/query/observation metadata."""
    return {key: envelope.get(key) for key in _CONTENT_IDENTITY_KEYS}


def openalex_raw_content_identity(envelope: Mapping[str, Any]) -> str:
    return raw_content_identity(content_identity_payload(envelope))


def reconstruct_abstract(inverted_index: Mapping[str, list[int]] | None) -> str | None:
    if not inverted_index:
        return None
    positions: list[tuple[int, str]] = []
    for token, idxs in inverted_index.items():
        for idx in idxs:
            positions.append((int(idx), str(token)))
    if not positions:
        return None
    positions.sort(key=lambda item: item[0])
    return " ".join(token for _, token in positions)


def _institution_projection(inst: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": inst.get("id"),
        "ror": inst.get("ror"),
        "display_name": inst.get("display_name"),
        "type": inst.get("type"),
        "country_code": inst.get("country_code"),
    }


def project_work_to_privacy_reduced(
    upstream: Mapping[str, Any],
    *,
    observed_at: str,
    ingested_at: str,
    query_meta: Mapping[str, Any],
    match_meta: Mapping[str, Any],
) -> dict[str, Any]:
    """
    Build privacy_reduced_raw_envelope from an ephemeral upstream_response.

    Author objects / IDs / names / ORCID are discarded. The upstream body is not
    hashed or returned.
    """
    institutions: list[dict[str, Any]] = []
    seen_inst: set[str] = set()
    countries: set[str] = set()
    country_evidence: list[dict[str, Any]] = []

    for authorship in upstream.get("authorships") or []:
        if not isinstance(authorship, dict):
            continue
        for code in authorship.get("countries") or []:
            if code:
                countries.add(str(code).upper())
                country_evidence.append(
                    {
                        "source": "authorships.countries",
                        "country_code": str(code).upper(),
                    }
                )
        for inst in authorship.get("institutions") or []:
            if not isinstance(inst, dict):
                continue
            proj = _institution_projection(inst)
            key = str(proj.get("id") or proj.get("ror") or proj)
            if key in seen_inst:
                continue
            seen_inst.add(key)
            institutions.append(proj)
            cc = proj.get("country_code")
            if cc:
                countries.add(str(cc).upper())
                country_evidence.append(
                    {
                        "source": "authorships.institutions.country_code",
                        "country_code": str(cc).upper(),
                        "institution_id": proj.get("id"),
                    }
                )

    country_list = sorted(countries)
    missing_country = len(country_list) == 0
    multi_country = len(country_list) > 1

    primary_location = upstream.get("primary_location") or {}
    source = primary_location.get("source") if isinstance(primary_location, dict) else None
    source_identity = None
    if isinstance(source, dict):
        source_identity = {
            "id": source.get("id"),
            "display_name": source.get("display_name"),
            "type": source.get("type"),
            "issn_l": source.get("issn_l"),
        }

    inverted = upstream.get("abstract_inverted_index")
    abstract_present = inverted is not None
    # Keep inverted index in local privacy-reduced Raw only (frozen allowlist).
    envelope: dict[str, Any] = {
        "schema": "m5.privacy_reduced_raw_envelope.openalex.v1",
        "work_id": upstream.get("id"),
        "doi": upstream.get("doi"),
        "openalex_url": upstream.get("id"),
        "title": upstream.get("title") or upstream.get("display_name"),
        "display_name": upstream.get("display_name"),
        "type": upstream.get("type"),
        "language": upstream.get("language"),
        "primary_location_source": source_identity,
        "abstract_present": abstract_present,
        "abstract_inverted_index": inverted if isinstance(inverted, dict) else None,
        "publication_date": upstream.get("publication_date"),
        "publication_year": upstream.get("publication_year"),
        "created_date": upstream.get("created_date"),
        "updated_date": upstream.get("updated_date"),
        "observed_at": observed_at,
        "ingested_at": ingested_at,
        "institutions": institutions,
        "authorship_countries": country_list,
        "country_evidence": country_evidence,
        "missing_country": missing_country,
        "multi_country": multi_country,
        "provisional_match": dict(match_meta),
        "query": dict(query_meta),
    }
    # Ensure no author-shaped schema keys leaked (path/field semantics, not text).
    _assert_no_person_fields(envelope)
    content_id = openalex_raw_content_identity(envelope)
    envelope["raw_content_identity"] = content_id
    envelope["persisted_envelope_checksum"] = persisted_envelope_checksum(
        {
            k: v
            for k, v in envelope.items()
            if k not in {"persisted_envelope_checksum"}
        }
    )
    return envelope


def _assert_no_person_fields(obj: Any, path: str = "$") -> None:
    if isinstance(obj, dict):
        # Token dictionaries (abstract_inverted_index) are text tokens, not schema fields.
        if path.endswith(".abstract_inverted_index"):
            return
        # Title/display string values may contain the substring "author"; that is not a field.
        for key, value in obj.items():
            lowered = str(key).lower()
            child_path = f"{path}.{key}"
            if lowered in {"author", "authors", "orcid", "raw_author_name"} or lowered.endswith(
                "_orcid"
            ):
                raise ValueError(f"Prohibited person field in envelope at {child_path}")
            if key in _AUTHOR_OBJECT_KEYS:
                raise ValueError(f"Prohibited authorship key in envelope at {child_path}")
            if lowered in {"title", "display_name"} and isinstance(value, str):
                continue
            _assert_no_person_fields(value, child_path)
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            _assert_no_person_fields(item, f"{path}[{i}]")


def extract_record_from_envelope(envelope: Mapping[str, Any]) -> dict[str, Any]:
    """Public-safer extracted row: abstract inverted index omitted."""
    return {
        "work_id": envelope.get("work_id"),
        "doi": envelope.get("doi"),
        "openalex_url": envelope.get("openalex_url"),
        "title": envelope.get("title"),
        "type": envelope.get("type"),
        "language": envelope.get("language"),
        "publication_date": envelope.get("publication_date"),
        "publication_year": envelope.get("publication_year"),
        "created_date": envelope.get("created_date"),
        "updated_date": envelope.get("updated_date"),
        "observed_at": envelope.get("observed_at"),
        "ingested_at": envelope.get("ingested_at"),
        "abstract_present": envelope.get("abstract_present"),
        "authorship_countries": envelope.get("authorship_countries"),
        "missing_country": envelope.get("missing_country"),
        "multi_country": envelope.get("multi_country"),
        "institutions": [
            {
                "id": i.get("id"),
                "type": i.get("type"),
                "country_code": i.get("country_code"),
            }
            for i in (envelope.get("institutions") or [])
            if isinstance(i, dict)
        ],
        "provisional_match": envelope.get("provisional_match"),
        "persisted_envelope_checksum": envelope.get("persisted_envelope_checksum"),
        "smoke_vocabulary_version": (envelope.get("provisional_match") or {}).get(
            "smoke_vocabulary_version"
        ),
    }
