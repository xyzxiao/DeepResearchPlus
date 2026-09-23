# Targeted Red Team verification

With `enable_red_team: true` (the default), inspect these LangGraph Studio fields:

1. `red_team_status`, `red_team_issues`, `red_team_issue_errors`
2. `red_team_verification_status`, `red_team_verifications`
3. `confirmed_red_team_issues` — this is the exact factual correction input sent to Revision
4. `revision_fix_verification_status`, `revision_fix_verifications`
5. `quality_gate_decision`, `final_quality_passed`

`dismissed` and `uncertain` concerns remain visible but are not sent to Revision. Post-revision
verification checks only the previously confirmed concerns; it is not a new full-report scan.

## Fixed examples without another search

`run_targeted_verifier.py` supplies a fixed report and fixed evidence table:

- RT1 is a valid criticism: the evidence is limited to participating cities through December
  2025, while the report claims every city with no time limit.
- RT2 is deliberately incorrect: it questions a launch date that E2 directly supports.

Run it with an API key already configured in `.env`:

```bash
PYTHONPATH=src python examples/run_targeted_verifier.py
```

This command performs a real verifier model call but no web search. Its outcome should be
reviewed as a model-behavior example, not as a deterministic test. The normal unit tests use
simulated structured results and do not demonstrate semantic verification quality.

Disable the new path for second-round comparison in Studio with:

```json
{
  "enable_red_team": false
}
```

