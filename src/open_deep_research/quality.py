"""Deterministic report-quality thresholds and selection rules."""

from typing import Optional

from open_deep_research.red_team import all_confirmed_issues_resolved
from open_deep_research.state import (
    ConfirmedRedTeamIssue,
    EvaluationResult,
    QualityGateDecision,
    RevisionFixVerification,
)

# Temporary interview-project thresholds. Keeping them together makes the first
# quality policy easy to inspect and adjust without adding configuration plumbing.
OVERALL_PASS_THRESHOLD = 7.0
DIMENSION_PASS_THRESHOLD = 6.0


def calculate_overall_score(evaluation: EvaluationResult) -> float:
    """Calculate the arithmetic mean instead of asking the model for a total."""
    return (
        evaluation.completeness_score
        + evaluation.depth_score
        + evaluation.evidence_score
    ) / 3


def evaluation_passes(evaluation: Optional[EvaluationResult]) -> bool:
    """Apply both the overall and per-dimension quality thresholds."""
    if evaluation is None:
        return False
    return (
        calculate_overall_score(evaluation) >= OVERALL_PASS_THRESHOLD
        and evaluation.completeness_score >= DIMENSION_PASS_THRESHOLD
        and evaluation.depth_score >= DIMENSION_PASS_THRESHOLD
        and evaluation.evidence_score >= DIMENSION_PASS_THRESHOLD
    )


def choose_report_version(
    initial_evaluation: Optional[EvaluationResult],
    initial_citation_errors: list[str],
    revision_evaluation: Optional[EvaluationResult] = None,
    revision_citation_errors: Optional[list[str]] = None,
    failure_reason: Optional[str] = None,
    confirmed_issues: Optional[list[ConfirmedRedTeamIssue]] = None,
    revision_fix_results: Optional[list[RevisionFixVerification]] = None,
) -> QualityGateDecision:
    """Select the draft or one revision using the documented heuristic rules."""
    initial_score = (
        calculate_overall_score(initial_evaluation)
        if initial_evaluation is not None
        else None
    )
    initial_citations_valid = not initial_citation_errors
    confirmed = confirmed_issues or []
    fix_results = revision_fix_results or []
    revision_errors = revision_citation_errors or []

    if revision_errors:
        if not initial_citations_valid:
            reason = (
                "Both draft and revision contain invalid evidence IDs; keeping the draft "
                "and preserving its citation error state."
            )
        elif confirmed:
            reason = (
                "Revision contains invalid evidence IDs; rejecting it even though the "
                "draft has confirmed Red Team issues."
            )
        else:
            reason = "Revision contains invalid evidence IDs; rejecting it and keeping the draft."
        return QualityGateDecision(
            selected_version="draft",
            accepted_revision=False,
            reason=reason,
            selected_overall_score=initial_score,
            passed=(
                not confirmed
                and evaluation_passes(initial_evaluation)
                and initial_citations_valid
            ),
        )

    if confirmed:
        if revision_evaluation is None:
            return QualityGateDecision(
                selected_version="draft",
                accepted_revision=False,
                reason=failure_reason or (
                    "Confirmed Red Team issues exist, but no evaluated revision is available; "
                    "keeping the draft with unresolved issue state."
                ),
                selected_overall_score=initial_score,
                passed=False,
            )

        revision_score = calculate_overall_score(revision_evaluation)
        if not all_confirmed_issues_resolved(confirmed, fix_results):
            status_by_id = {result.issue_id: result.status for result in fix_results}
            unresolved = ", ".join(
                f"{issue.issue_id}={status_by_id.get(issue.issue_id, 'missing')}"
                for issue in confirmed
                if status_by_id.get(issue.issue_id) != "resolved"
            )
            return QualityGateDecision(
                selected_version="draft",
                accepted_revision=False,
                reason=(
                    "Confirmed Red Team issues were not all resolved "
                    f"({unresolved}); keeping the draft with unresolved issue state."
                ),
                selected_overall_score=initial_score,
                passed=False,
            )

        initial_score_text = f"{initial_score:.2f}" if initial_score is not None else "unavailable"
        return QualityGateDecision(
            selected_version="revision",
            accepted_revision=True,
            reason=(
                "All confirmed Red Team issues were resolved and revision citations are valid; "
                "selecting the correction even though score changes do not control this rule "
                f"({initial_score_text} to {revision_score:.2f})."
            ),
            selected_overall_score=revision_score,
            passed=evaluation_passes(revision_evaluation),
        )

    if revision_evaluation is None:
        reason = failure_reason or (
            "Draft met all score thresholds and citation checks; revision was skipped."
            if evaluation_passes(initial_evaluation) and initial_citations_valid
            else "No evaluated revision is available; keeping the draft."
        )
        return QualityGateDecision(
            selected_version="draft",
            accepted_revision=False,
            reason=reason,
            selected_overall_score=initial_score,
            passed=evaluation_passes(initial_evaluation) and initial_citations_valid,
        )

    revision_score = calculate_overall_score(revision_evaluation)
    initial_score_text = f"{initial_score:.2f}" if initial_score is not None else "unavailable"

    if not initial_citations_valid:
        return QualityGateDecision(
            selected_version="revision",
            accepted_revision=True,
            reason=(
                "Revision removed the draft's invalid evidence IDs; selecting the revision. "
                f"Score changed from {initial_score_text} to {revision_score:.2f}."
            ),
            selected_overall_score=revision_score,
            passed=evaluation_passes(revision_evaluation),
        )

    if initial_score is None:
        return QualityGateDecision(
            selected_version="draft",
            accepted_revision=False,
            reason=failure_reason or "Draft evaluation is unavailable; keeping the draft.",
            selected_overall_score=None,
            passed=False,
        )

    if revision_score < initial_score:
        return QualityGateDecision(
            selected_version="draft",
            accepted_revision=False,
            reason=(
                f"Revision score decreased from {initial_score:.2f} to {revision_score:.2f}; "
                "keeping the draft."
            ),
            selected_overall_score=initial_score,
            passed=evaluation_passes(initial_evaluation),
        )

    return QualityGateDecision(
        selected_version="revision",
        accepted_revision=True,
        reason=(
            f"Revision citations are valid and its score did not decrease "
            f"({initial_score:.2f} to {revision_score:.2f}); selecting the revision."
        ),
        selected_overall_score=revision_score,
        passed=evaluation_passes(revision_evaluation),
    )
