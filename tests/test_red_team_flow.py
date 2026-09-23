"""Fixed-data tests for targeted Red Team verification and gate priority."""

from open_deep_research.deep_researcher import (
    finalize_report,
    route_after_initial_evaluation,
    route_after_red_team_verification,
)
from open_deep_research.quality import choose_report_version
from open_deep_research.red_team import (
    build_confirmed_issues,
    normalize_issue_verifications,
    validate_red_team_candidates,
)
from open_deep_research.state import (
    ConfirmedRedTeamIssue,
    EvaluationResult,
    Evidence,
    IssueVerification,
    RedTeamIssue,
    RedTeamIssueCandidate,
    RevisionFixVerification,
)


def evaluation(score: float) -> EvaluationResult:
    return EvaluationResult(
        completeness_score=score,
        depth_score=score,
        evidence_score=score,
        issues=[],
    )


def red_team_issue() -> RedTeamIssue:
    return RedTeamIssue(
        issue_id="RT1",
        category="overclaim",
        report_quote="The policy applies to every organization.",
        concern="Evidence E1 limits the policy to participating organizations.",
        evidence_ids=["E1"],
        suggested_fix="Restore the participation condition.",
    )


def confirmed_issue() -> ConfirmedRedTeamIssue:
    return ConfirmedRedTeamIssue(
        issue_id="RT1",
        category="overclaim",
        report_quote="The policy applies to every organization.",
        concern="Evidence E1 limits the policy to participating organizations.",
        evidence_ids=["E1"],
        verification_reason="E1 explicitly contains the participation condition.",
        correction_instruction="Limit the statement to participating organizations.",
    )


def test_red_team_candidates_are_located_and_ids_are_program_assigned() -> None:
    evidence = Evidence(
        id="E1",
        url="https://example.test/policy",
        title="Policy",
        quote="The policy applies to participating organizations.",
    )
    candidates = [
        RedTeamIssueCandidate(
            category="overclaim",
            report_quote="The policy applies to every organization.",
            concern="The scope may have been expanded.",
            evidence_ids=["E1"],
            suggested_fix="Restore the source condition.",
        ),
        RedTeamIssueCandidate(
            category="factual_conflict",
            report_quote="A sentence absent from the report.",
            concern="This cannot be located.",
            evidence_ids=["E99"],
            suggested_fix="Do something.",
        ),
    ]

    issues, errors = validate_red_team_candidates(
        candidates,
        "The policy applies to every organization.",
        [evidence],
    )

    assert [issue.issue_id for issue in issues] == ["RT1"]
    assert len(errors) == 1


def test_omitted_verifier_result_becomes_uncertain_not_approved() -> None:
    results, errors = normalize_issue_verifications(
        [red_team_issue()],
        [],
        [Evidence(id="E1", url="u", title="t", quote="q")],
    )

    assert results[0].verdict == "uncertain"
    assert "omitted" in errors[0]


def test_high_scoring_draft_with_confirmed_issue_still_revises() -> None:
    assert route_after_initial_evaluation({
        "red_team_status": "pending",
        "initial_evaluation": evaluation(9),
        "draft_citation_errors": [],
    }) == "red_team_review"

    state = {
        "initial_evaluation": evaluation(9),
        "draft_citation_errors": [],
        "confirmed_red_team_issues": [confirmed_issue()],
    }

    assert route_after_red_team_verification(state) == "revise_report"


def test_dismissed_issue_does_not_trigger_revision() -> None:
    issue = red_team_issue()
    verification = IssueVerification(
        issue_id="RT1",
        verdict="dismissed",
        reason="E1 directly supports the draft statement.",
        evidence_ids=["E1"],
        correction_instruction="",
    )
    state = {
        "initial_evaluation": evaluation(9),
        "draft_citation_errors": [],
        "confirmed_red_team_issues": build_confirmed_issues([issue], [verification]),
    }

    assert state["confirmed_red_team_issues"] == []
    assert route_after_red_team_verification(state) == "quality_gate"


def test_uncertain_issue_is_not_sent_to_revision() -> None:
    issue = red_team_issue()
    verification = IssueVerification(
        issue_id="RT1",
        verdict="uncertain",
        reason="The excerpt lacks the definition needed to decide scope.",
        evidence_ids=["E1"],
        correction_instruction="",
    )

    assert build_confirmed_issues([issue], [verification]) == []


def test_resolved_confirmed_issue_beats_small_score_drop() -> None:
    decision = choose_report_version(
        initial_evaluation=evaluation(9),
        initial_citation_errors=[],
        revision_evaluation=evaluation(8),
        revision_citation_errors=[],
        confirmed_issues=[confirmed_issue()],
        revision_fix_results=[
            RevisionFixVerification(
                issue_id="RT1",
                status="resolved",
                reason="The revision restores the participation condition.",
            )
        ],
    )

    assert decision.selected_version == "revision"
    assert decision.accepted_revision is True
    assert "All confirmed" in decision.reason


def test_invalid_revision_citation_still_beats_resolved_issue_status() -> None:
    decision = choose_report_version(
        initial_evaluation=evaluation(9),
        initial_citation_errors=[],
        revision_evaluation=evaluation(9),
        revision_citation_errors=["Unknown citation ID: E99"],
        confirmed_issues=[confirmed_issue()],
        revision_fix_results=[
            RevisionFixVerification(
                issue_id="RT1",
                status="resolved",
                reason="The revision restores the participation condition.",
            )
        ],
    )

    assert decision.selected_version == "draft"
    assert decision.accepted_revision is False
    assert decision.passed is False


def test_rephrased_but_unresolved_issue_is_not_accepted() -> None:
    decision = choose_report_version(
        initial_evaluation=evaluation(9),
        initial_citation_errors=[],
        revision_evaluation=evaluation(9),
        revision_citation_errors=[],
        confirmed_issues=[confirmed_issue()],
        revision_fix_results=[
            RevisionFixVerification(
                issue_id="RT1",
                status="unresolved",
                reason="The universal claim remains with different wording.",
            )
        ],
    )

    assert decision.selected_version == "draft"
    assert decision.accepted_revision is False
    assert decision.passed is False


def test_unresolved_issue_cannot_become_passed_when_draft_is_kept() -> None:
    issue = red_team_issue()
    confirmed = confirmed_issue()
    fix_result = RevisionFixVerification(
        issue_id="RT1",
        status="unresolved",
        reason="The scope is still universal.",
    )
    decision = choose_report_version(
        initial_evaluation=evaluation(9),
        initial_citation_errors=[],
        revision_evaluation=evaluation(9),
        revision_citation_errors=[],
        confirmed_issues=[confirmed],
        revision_fix_results=[fix_result],
    )
    state = {
        "draft_report": "The policy applies to every organization [E1].",
        "revised_report": "The policy covers all organizations [E1].",
        "initial_evaluation": evaluation(9),
        "revision_evaluation": evaluation(9),
        "evidences": [
            Evidence(
                id="E1",
                url="https://example.test/policy",
                title="Policy",
                quote="The policy applies to participating organizations.",
            )
        ],
        "red_team_status": "completed",
        "red_team_issues": [issue],
        "red_team_verification_status": "completed",
        "confirmed_red_team_issues": [confirmed],
        "revision_fix_verification_status": "completed",
        "revision_fix_verifications": [fix_result],
        "quality_gate_decision": decision,
    }

    output = finalize_report(state)

    assert output["quality_gate_decision"].selected_version == "draft"
    assert output["final_quality_passed"] is False
    assert output["messages"][0].content == output["final_report"]


def test_disabling_red_team_preserves_second_round_routing() -> None:
    assert route_after_initial_evaluation({
        "red_team_status": "disabled",
        "initial_evaluation": evaluation(9),
        "draft_citation_errors": [],
    }) == "quality_gate"
    assert route_after_initial_evaluation({
        "red_team_status": "disabled",
        "initial_evaluation": evaluation(5),
        "draft_citation_errors": [],
    }) == "revise_report"
