"""Run two fixed Red Team allegations through the real verifier without web search."""

import asyncio
import json

from dotenv import load_dotenv

from open_deep_research.deep_researcher import verify_red_team_issues
from open_deep_research.state import Evidence, RedTeamIssue


async def main() -> None:
    """Verify one valid criticism and one deliberately incorrect criticism."""
    load_dotenv()
    evidences = [
        Evidence(
            id="E1",
            url="https://example.test/scope",
            title="Pilot scope",
            quote="The pilot applies to participating cities through December 2025.",
        ),
        Evidence(
            id="E2",
            url="https://example.test/launch",
            title="Launch notice",
            quote="The program launched on March 1, 2024.",
        ),
    ]
    state = {
        "draft_report": (
            "The pilot applies to every city without a time limit [E1]. "
            "The program launched on March 1, 2024 [E2]."
        ),
        "evidences": evidences,
        "red_team_issues": [
            RedTeamIssue(
                issue_id="RT1",
                category="overclaim",
                report_quote="The pilot applies to every city without a time limit [E1].",
                concern="The report expands both scope and duration beyond E1.",
                evidence_ids=["E1"],
                suggested_fix="Restore the participating-city and December 2025 limits.",
            ),
            RedTeamIssue(
                issue_id="RT2",
                category="unsupported_inference",
                report_quote="The program launched on March 1, 2024 [E2].",
                concern="The launch date allegedly has no evidence support.",
                evidence_ids=["E2"],
                suggested_fix="Remove the launch date.",
            ),
        ],
    }
    output = await verify_red_team_issues(state, {"configurable": {}})
    serializable = {
        key: [
            item.model_dump() if hasattr(item, "model_dump") else item
            for item in value
        ] if isinstance(value, list) else value
        for key, value in output.items()
    }
    print(json.dumps(serializable, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
