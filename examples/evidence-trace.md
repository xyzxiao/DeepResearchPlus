# Evidence trace example

The default Tavily path now keeps fetched page text inside each Researcher long enough to
verify quotes. OpenAI/Anthropic native web search and generic MCP tools can still contribute
to summaries, but they do not produce verified `Evidence` unless their tool interface also
provides raw page content in the supported Tavily result shape.

Run the graph in LangGraph Studio as described in the main README. After a run, inspect these
output fields:

- `research_results`: one structured result per Researcher, containing its summary, locally
  identified verified evidence, and unanswered questions.
- `evidences`: the deduplicated graph-wide evidence table with final IDs `E1`, `E2`, ... .
- `final_report`: the Writer output with inline `[E1]` citations and a program-generated
  `Sources` section containing only evidence actually cited.
- `evidence_errors`: rejected candidate quotes and their short reasons.
- `citation_errors`: IDs emitted by the Writer that were absent from `evidences`.

A result has this shape (values abbreviated):

```json
{
  "research_results": [
    {
      "summary": "The report states ...",
      "evidences": [
        {
          "id": "R-8D98E7A123",
          "url": "https://example.org/report",
          "title": "Example report",
          "quote": "Revenue increased by 12% in 2025, subject to final audit."
        }
      ],
      "unanswered_questions": ["The report does not explain the regional split."]
    }
  ],
  "evidences": [
    {
      "id": "E1",
      "url": "https://example.org/report",
      "title": "Example report",
      "quote": "Revenue increased by 12% in 2025, subject to final audit."
    }
  ],
  "final_report": "Revenue increased by 12% in 2025 [E1].\n\n## Sources\n\n- [E1] [Example report](https://example.org/report)",
  "evidence_errors": [],
  "citation_errors": []
}
```

The deterministic checks require no API credentials:

```bash
pytest -q tests/test_evidence_pipeline.py
```

