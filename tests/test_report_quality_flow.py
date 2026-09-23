"""Fixed-data tests for one-pass evaluation, revision, and rollback."""

from open_deep_research.deep_researcher import finalize_report, route_after_initial_evaluation
from open_deep_research.quality import choose_report_version
from open_deep_research.state import (
    EvaluationResult,
    Evidence,
    QualityGateDecision,
)


def evaluation(completeness: float, depth: float, evidence: float) -> EvaluationResult:
    """Build an issue-free fixed evaluation for deterministic gate tests."""
    return EvaluationResult(
        completeness_score=completeness,
        depth_score=depth,
        evidence_score=evidence,
        issues=[],
    )


def test_passing_draft_skips_revision() -> None:
    state = {
        "initial_evaluation": evaluation(8, 7, 8),
        "draft_citation_errors": [],
    }

    assert route_after_initial_evaluation(state) == "quality_gate"
    assert route_after_initial_evaluation({
        "initial_evaluation": evaluation(9, 9, 5),
        "draft_citation_errors": [],
    }) == "revise_report"


def test_lower_scoring_revision_keeps_draft() -> None:
    decision = choose_report_version(
        initial_evaluation=evaluation(8, 8, 8),
        initial_citation_errors=[],
        revision_evaluation=evaluation(7, 7, 7),
        revision_citation_errors=[],
    )

    assert decision.selected_version == "draft"
    assert decision.accepted_revision is False
    assert "decreased" in decision.reason


def test_non_decreasing_valid_revision_is_accepted() -> None:
    decision = choose_report_version(
        initial_evaluation=evaluation(5, 7, 6),
        initial_citation_errors=[],
        revision_evaluation=evaluation(7, 7, 7),
        revision_citation_errors=[],
    )

    assert decision.selected_version == "revision"
    assert decision.accepted_revision is True
    assert decision.passed is True


def test_revision_with_unknown_evidence_id_is_rejected() -> None:
    decision = choose_report_version(
        initial_evaluation=evaluation(6, 6, 6),
        initial_citation_errors=[],
        revision_evaluation=evaluation(9, 9, 9),
        revision_citation_errors=["Unknown evidence ID cited by writer: E99"],
    )

    assert decision.selected_version == "draft"
    assert decision.accepted_revision is False
    assert decision.passed is False


def test_final_sources_and_message_use_selected_revision() -> None:
    evidences = [
        Evidence(id="E1", url="https://example.test/draft", title="Draft Source", quote="Draft fact."),
        Evidence(id="E2", url="https://example.test/revision", title="Revision Source", quote="Revision fact."),
    ]
    selected_evaluation = evaluation(8, 8, 8)
    state = {
        "draft_report": "Draft body [E1].",
        "revised_report": "Revision body [E2].\n\n## Sources\n\n- invented source",
        "initial_evaluation": evaluation(6, 6, 6),
        "revision_evaluation": selected_evaluation,
        "evidences": evidences,
        "quality_gate_decision": QualityGateDecision(
            selected_version="revision",
            accepted_revision=True,
            reason="Fixed test selection.",
            selected_overall_score=8,
            passed=True,
        ),
    }

    output = finalize_report(state)

    assert "Revision body [E2]." in output["final_report"]
    assert "[Revision Source](https://example.test/revision)" in output["final_report"]
    assert "Draft Source" not in output["final_report"]
    assert "invented source" not in output["final_report"]
    assert output["final_report"].count("## Sources") == 1
    assert output["messages"][0].content == output["final_report"]
    assert output["citation_errors"] == []
    assert output["final_quality_passed"] is True
