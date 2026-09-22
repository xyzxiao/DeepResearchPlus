"""Deterministic tests for evidence verification and citation handling."""

from open_deep_research.state import Evidence, EvidenceCandidate, SourceDocument
from open_deep_research.utils import (
    aggregate_evidences,
    append_cited_sources,
    validate_evidence_candidates,
    validate_report_citations,
)


def test_quote_must_exist_in_raw_source() -> None:
    source = SourceDocument(
        url="https://example.test/report",
        title="Annual report",
        raw_content="Revenue increased by 12% in 2025, subject to final audit.\nNext paragraph.",
    )
    candidates = [
        EvidenceCandidate(
            url=source.url,
            quote="Revenue increased by 12% in 2025, subject to final audit.",
        ),
        EvidenceCandidate(
            url=source.url,
            quote="Revenue grew significantly in 2025 after the audit.",
        ),
    ]

    evidences, errors = validate_evidence_candidates(candidates, [source])

    assert [evidence.quote for evidence in evidences] == [
        "Revenue increased by 12% in 2025, subject to final audit."
    ]
    assert len(errors) == 1
    assert "not found verbatim" in errors[0]


def test_parallel_researcher_evidence_is_deduplicated_and_reassigned() -> None:
    duplicate_a = Evidence(
        id="R-A",
        url="https://example.test/a",
        title="Source A",
        quote="A fact with\nnormalized whitespace.",
    )
    duplicate_b = Evidence(
        id="R-B",
        url="https://example.test/a",
        title="Source A duplicate",
        quote="A fact with normalized whitespace.",
    )
    distinct = Evidence(
        id="R-C",
        url="https://example.test/b",
        title="Source B",
        quote="Another fact.",
    )

    aggregated = aggregate_evidences([duplicate_a, distinct, duplicate_b])

    assert [evidence.id for evidence in aggregated] == ["E1", "E2"]
    assert [evidence.url for evidence in aggregated] == [
        "https://example.test/a",
        "https://example.test/b",
    ]


def test_unknown_writer_citation_is_reported_without_fake_source() -> None:
    evidences = [
        Evidence(
            id="E1",
            url="https://example.test/a",
            title="Source A",
            quote="Verified fact.",
        )
    ]
    report = "Supported claim [E1]. Unsupported claim [E99]."

    cited_ids, errors = validate_report_citations(report, evidences)
    final_report = append_cited_sources(report, evidences, cited_ids, errors)

    assert cited_ids == ["E1"]
    assert errors == ["Unknown evidence ID cited by writer: E99"]
    assert "[Source A](https://example.test/a)" in final_report
    assert "E99" in final_report
    assert "example.test/99" not in final_report
