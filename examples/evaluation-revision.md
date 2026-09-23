# Evaluation and one-pass revision

Run the graph in LangGraph Studio with the same setup described in `README.md`. The research
phase is unchanged. After report generation, inspect these state fields in order:

1. `draft_report`, `draft_citation_errors`
2. `initial_evaluation`, `initial_overall_score`
3. `revised_report`, `revision_citation_errors` (empty when revision was skipped)
4. `revision_evaluation`, `revision_overall_score` (empty when revision was skipped or failed)
5. `quality_gate_decision`
6. `final_quality_passed`, `final_report`, `citation_errors`

Example selection record:

```json
{
  "initial_overall_score": 6.33,
  "revision_overall_score": 7.67,
  "quality_gate_decision": {
    "selected_version": "revision",
    "accepted_revision": true,
    "reason": "Revision citations are valid and its score did not decrease (6.33 to 7.67); selecting the revision.",
    "selected_overall_score": 7.67,
    "passed": true
  },
  "final_quality_passed": true,
  "citation_errors": []
}
```

`accepted_revision` only records version selection. `final_quality_passed` is recalculated for
the selected version and may still be `false`. The evidence score is a report-level LLM review;
it is not an independent grounding or factual-verification result.

Run the fixed-data tests without API calls:

```bash
pytest -q tests/test_evidence_pipeline.py tests/test_report_quality_flow.py
```

