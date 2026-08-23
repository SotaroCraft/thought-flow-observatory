"""Privacy projection and checksum tests for OpenAlex M5 smoke."""

from __future__ import annotations

import json

from thought_flow.smoke.openalex.project import (
    extract_record_from_envelope,
    project_work_to_privacy_reduced,
    reconstruct_abstract,
)
from thought_flow.smoke.privacy import persisted_envelope_checksum


UPSTREAM_WITH_AUTHORS = {
    "id": "https://openalex.org/W123",
    "doi": "https://doi.org/10.1000/test",
    "title": "Generative AI survey",
    "display_name": "Generative AI survey",
    "type": "article",
    "language": "en",
    "publication_date": "2022-12-01",
    "publication_year": 2022,
    "created_date": "2022-12-02",
    "updated_date": "2023-01-01",
    "primary_location": {
        "source": {"id": "https://openalex.org/S1", "display_name": "Demo Journal", "type": "journal"}
    },
    "abstract_inverted_index": {"Generative": [0], "AI": [1], "methods": [2]},
    "authorships": [
        {
            "author_position": "first",
            "author": {
                "id": "https://openalex.org/A999",
                "display_name": "Ada Example",
                "orcid": "https://orcid.org/0000-0000-0000-0000",
            },
            "institutions": [
                {
                    "id": "https://openalex.org/I1",
                    "display_name": "Example University",
                    "type": "education",
                    "country_code": "US",
                }
            ],
            "countries": ["US", "JP"],
        }
    ],
}


def test_reconstruct_abstract() -> None:
    text = reconstruct_abstract({"methods": [2], "Generative": [0], "AI": [1]})
    assert text == "Generative AI methods"


def test_privacy_projection_strips_authors_and_checksum_is_reduced_only() -> None:
    envelope = project_work_to_privacy_reduced(
        UPSTREAM_WITH_AUTHORS,
        observed_at="2026-08-23T00:00:00Z",
        ingested_at="2026-08-23T00:00:00Z",
        query_meta={"sanitized_url": "https://api.openalex.org/works"},
        match_meta={"provisional_match": True, "smoke_vocabulary_version": "PROVISIONAL-M5-SMOKE/2026-08-23-r1"},
    )
    dumped = json.dumps(envelope)
    assert "Ada Example" not in dumped
    assert "orcid.org" not in dumped
    assert "A999" not in dumped
    assert "author" not in envelope
    assert envelope["multi_country"] is True
    assert set(envelope["authorship_countries"]) == {"JP", "US"}
    assert envelope["abstract_inverted_index"] is not None

    without_checksum = {k: v for k, v in envelope.items() if k != "persisted_envelope_checksum"}
    assert envelope["persisted_envelope_checksum"] == persisted_envelope_checksum(without_checksum)

    # Checksum must not equal a hash of the upstream response.
    upstream_checksum = persisted_envelope_checksum(UPSTREAM_WITH_AUTHORS)
    assert envelope["persisted_envelope_checksum"] != upstream_checksum

    extracted = extract_record_from_envelope(envelope)
    assert "abstract_inverted_index" not in extracted
    assert extracted["abstract_present"] is True


def test_missing_country_flag() -> None:
    bare = {
        "id": "https://openalex.org/W1",
        "title": "Agentic AI systems",
        "authorships": [],
        "abstract_inverted_index": None,
    }
    envelope = project_work_to_privacy_reduced(
        bare,
        observed_at="2026-08-23T00:00:00Z",
        ingested_at="2026-08-23T00:00:00Z",
        query_meta={},
        match_meta={},
    )
    assert envelope["missing_country"] is True
    assert envelope["authorship_countries"] == []


def test_author_substring_in_title_or_abstract_is_not_person_field() -> None:
    upstream = {
        "id": "https://openalex.org/Wauthortext",
        "title": "The author of generative AI systems",
        "display_name": "The author of generative AI systems",
        "abstract_inverted_index": {
            "The": [0],
            "author": [1],
            "discusses": [2],
            "generative": [3],
            "AI": [4],
        },
        "authorships": [
            {
                "author": {
                    "id": "https://openalex.org/A-HIDE",
                    "display_name": "Hidden Person",
                },
                "institutions": [
                    {"id": "https://openalex.org/I1", "type": "education", "country_code": "US"}
                ],
                "countries": ["US"],
            }
        ],
    }
    envelope = project_work_to_privacy_reduced(
        upstream,
        observed_at="2026-08-23T00:00:00Z",
        ingested_at="2026-08-23T00:00:00Z",
        query_meta={"q": 1},
        match_meta={"provisional_match": True},
    )
    assert "author" in (envelope.get("title") or "")
    assert "author" in (envelope.get("abstract_inverted_index") or {})
    assert "author" not in envelope
    assert "Hidden Person" not in json.dumps(envelope)


def test_raw_content_identity_ignores_run_and_observation_metadata() -> None:
    from thought_flow.smoke.openalex.project import openalex_raw_content_identity

    a = project_work_to_privacy_reduced(
        UPSTREAM_WITH_AUTHORS,
        observed_at="2026-08-23T00:00:00Z",
        ingested_at="2026-08-23T00:00:00Z",
        query_meta={"sanitized_url": "https://api.openalex.org/works?page=1"},
        match_meta={"provisional_match": True},
    )
    b = project_work_to_privacy_reduced(
        UPSTREAM_WITH_AUTHORS,
        observed_at="2026-08-23T12:00:00Z",
        ingested_at="2026-08-23T12:00:00Z",
        query_meta={"sanitized_url": "https://api.openalex.org/works?page=2"},
        match_meta={"provisional_match": False},
    )
    assert openalex_raw_content_identity(a) == openalex_raw_content_identity(b)
    assert a["raw_content_identity"] == b["raw_content_identity"]
    assert a["persisted_envelope_checksum"] != b["persisted_envelope_checksum"]
