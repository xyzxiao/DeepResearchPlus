"""Deterministic validation helpers for targeted adversarial review."""

from open_deep_research.state import (
    ConfirmedRedTeamIssue,
    Evidence,
    IssueVerification,
    RedTeamIssue,
    RedTeamIssueCandidate,
    RevisionFixVerification,
)


def _normalize_whitespace(value: str) -> str:
    return " ".join(value.split())


def validate_red_team_candidates(
    candidates: list[RedTeamIssueCandidate],
    report: str,
    evidences: list[Evidence],
    max_issues: int = 3,
) -> tuple[list[RedTeamIssue], list[str]]:
    """Keep only locatable concerns that reference known evidence IDs."""
    available_ids = {evidence.id for evidence in evidences}
    normalized_report = _normalize_whitespace(report)
    issues: list[RedTeamIssue] = []
    errors: list[str] = []
    seen: set[tuple[str, str, str]] = set()

    if len(candidates) > max_issues:
        errors.append(f"Red Team returned {len(candidates)} issues; only the first {max_issues} were checked.")

    for position, candidate_value in enumerate(candidates[:max_issues], start=1):
        candidate = (
            candidate_value
            if isinstance(candidate_value, RedTeamIssueCandidate)
            else RedTeamIssueCandidate.model_validate(candidate_value)
        )
        normalized_quote = _normalize_whitespace(candidate.report_quote)
        if not normalized_quote or normalized_quote not in normalized_report:
            errors.append(f"Candidate {position}: report_quote could not be located in the draft.")
            continue

        unknown_ids = [
            evidence_id for evidence_id in candidate.evidence_ids
            if evidence_id not in available_ids
        ]
        if unknown_ids:
            errors.append(
                f"Candidate {position}: unknown evidence IDs: {', '.join(unknown_ids)}."
            )
            continue

        key = (
            candidate.category,
            normalized_quote,
            _normalize_whitespace(candidate.concern),
        )
        if key in seen:
            continue
        seen.add(key)
        issues.append(RedTeamIssue(
            issue_id=f"RT{len(issues) + 1}",
            category=candidate.category,
            report_quote=candidate.report_quote,
            concern=candidate.concern,
            evidence_ids=list(dict.fromkeys(candidate.evidence_ids)),
            suggested_fix=candidate.suggested_fix,
        ))

    return issues, errors


def normalize_issue_verifications(
    issues: list[RedTeamIssue],
    results: list[IssueVerification],
    evidences: list[Evidence],
) -> tuple[list[IssueVerification], list[str]]:
    """Return exactly one safe verifier result per issue; missing is uncertain."""
    issue_ids = {issue.issue_id for issue in issues}
    available_evidence_ids = {evidence.id for evidence in evidences}
    result_by_id: dict[str, IssueVerification] = {}
    errors: list[str] = []

    for result_value in results:
        result = (
            result_value
            if isinstance(result_value, IssueVerification)
            else IssueVerification.model_validate(result_value)
        )
        if result.issue_id not in issue_ids:
            errors.append(f"Verifier returned unknown issue ID: {result.issue_id}.")
            continue
        if result.issue_id in result_by_id:
            errors.append(f"Verifier returned duplicate issue ID: {result.issue_id}.")
            continue
        unknown_evidence_ids = [
            evidence_id for evidence_id in result.evidence_ids
            if evidence_id not in available_evidence_ids
        ]
        if unknown_evidence_ids:
            errors.append(
                f"Verifier used unknown evidence IDs for {result.issue_id}: "
                f"{', '.join(unknown_evidence_ids)}."
            )
            result = IssueVerification(
                issue_id=result.issue_id,
                verdict="uncertain",
                reason="Verifier output referenced evidence that is not in the supplied table.",
                evidence_ids=[],
                correction_instruction="",
            )
        elif result.verdict == "confirmed" and not result.correction_instruction.strip():
            errors.append(f"Verifier confirmed {result.issue_id} without a correction instruction.")
            result = result.model_copy(update={
                "verdict": "uncertain",
                "reason": result.reason + " No actionable correction instruction was supplied.",
            })
        result_by_id[result.issue_id] = result

    normalized: list[IssueVerification] = []
    for issue in issues:
        if issue.issue_id not in result_by_id:
            errors.append(f"Verifier omitted issue ID: {issue.issue_id}.")
            normalized.append(IssueVerification(
                issue_id=issue.issue_id,
                verdict="uncertain",
                reason="Verifier returned no result for this issue.",
                evidence_ids=[],
                correction_instruction="",
            ))
        else:
            normalized.append(result_by_id[issue.issue_id])
    return normalized, errors


def build_confirmed_issues(
    issues: list[RedTeamIssue],
    verifications: list[IssueVerification],
) -> list[ConfirmedRedTeamIssue]:
    """Build the transparent list of confirmed instructions sent to Revision."""
    issue_by_id = {issue.issue_id: issue for issue in issues}
    confirmed: list[ConfirmedRedTeamIssue] = []
    for verification in verifications:
        if verification.verdict != "confirmed" or verification.issue_id not in issue_by_id:
            continue
        issue = issue_by_id[verification.issue_id]
        confirmed.append(ConfirmedRedTeamIssue(
            issue_id=issue.issue_id,
            category=issue.category,
            report_quote=issue.report_quote,
            concern=issue.concern,
            evidence_ids=verification.evidence_ids,
            verification_reason=verification.reason,
            correction_instruction=verification.correction_instruction,
        ))
    return confirmed


def normalize_revision_fix_results(
    confirmed_issues: list[ConfirmedRedTeamIssue],
    results: list[RevisionFixVerification],
) -> tuple[list[RevisionFixVerification], list[str]]:
    """Return exactly one post-revision result per confirmed concern."""
    confirmed_ids = {issue.issue_id for issue in confirmed_issues}
    result_by_id: dict[str, RevisionFixVerification] = {}
    errors: list[str] = []

    for result_value in results:
        result = (
            result_value
            if isinstance(result_value, RevisionFixVerification)
            else RevisionFixVerification.model_validate(result_value)
        )
        if result.issue_id not in confirmed_ids:
            errors.append(f"Fix verifier returned unknown issue ID: {result.issue_id}.")
            continue
        if result.issue_id in result_by_id:
            errors.append(f"Fix verifier returned duplicate issue ID: {result.issue_id}.")
            continue
        result_by_id[result.issue_id] = result

    normalized: list[RevisionFixVerification] = []
    for issue in confirmed_issues:
        if issue.issue_id not in result_by_id:
            errors.append(f"Fix verifier omitted issue ID: {issue.issue_id}.")
            normalized.append(RevisionFixVerification(
                issue_id=issue.issue_id,
                status="uncertain",
                reason="No post-revision verification result was returned for this issue.",
            ))
        else:
            normalized.append(result_by_id[issue.issue_id])
    return normalized, errors


def all_confirmed_issues_resolved(
    confirmed_issues: list[ConfirmedRedTeamIssue],
    fix_results: list[RevisionFixVerification],
) -> bool:
    """Require one resolved result for every previously confirmed issue."""
    if not confirmed_issues:
        return True
    status_by_id = {result.issue_id: result.status for result in fix_results}
    return all(status_by_id.get(issue.issue_id) == "resolved" for issue in confirmed_issues)

