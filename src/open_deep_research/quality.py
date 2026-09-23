"""Deterministic report-quality thresholds and selection rules."""

from typing import Optional

from open_deep_research.state import EvaluationResult, QualityGateDecision

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
) -> QualityGateDecision:
    """Select the draft or one revision using the documented heuristic rules."""
    initial_score = (
        calculate_overall_score(initial_evaluation)
        if initial_evaluation is not None
        else None
    )
    initial_citations_valid = not initial_citation_errors

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

    revision_errors = revision_citation_errors or []
    revision_score = calculate_overall_score(revision_evaluation)
    revision_citations_valid = not revision_errors
    initial_score_text = f"{initial_score:.2f}" if initial_score is not None else "unavailable"

    if not initial_citations_valid and not revision_citations_valid:
        return QualityGateDecision(
            selected_version="draft",
            accepted_revision=False,
            reason=(
                "Both draft and revision contain invalid evidence IDs; keeping the draft "
                "and preserving its citation error state."
            ),
            selected_overall_score=initial_score,
            passed=False,
        )

    if not revision_citations_valid:
        return QualityGateDecision(
            selected_version="draft",
            accepted_revision=False,
            reason="Revision contains invalid evidence IDs; rejecting it and keeping the draft.",
            selected_overall_score=initial_score,
            passed=evaluation_passes(initial_evaluation) and initial_citations_valid,
        )

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
