"""Scenario data for Slow DB Queries (Scenario 1).

Loads the existing JSONL log files and Jira alert template from
tests/scenarios/slow_db_queries/ and converts them into the format
needed by ToolSimulator's initial_state_description.
"""

import json
from pathlib import Path

SCENARIO_DIR = Path(__file__).parent.parent.parent / "scenarios" / "slow_db_queries"
LOGS_DIR = SCENARIO_DIR / "logs"

# Log group names matching what inject.py creates
LOG_GROUPS = [
    "/production/api-service",
    "/production/db-primary",
    "/production/db-replica-1",
    "/production/notification-service",
    "/production/payment-service",
]

# Map log group names to their JSONL files
_LOG_GROUP_TO_FILE = {
    "/production/api-service": "api-service.jsonl",
    "/production/db-primary": "db-primary.jsonl",
    "/production/db-replica-1": "db-replica-1.jsonl",
    "/production/notification-service": "notification-service.jsonl",
    "/production/payment-service": "payment-service.jsonl",
}


def load_jira_alert() -> str:
    """Load the Jira alert text from jira.md."""
    return (SCENARIO_DIR / "jira.md").read_text(encoding="utf-8")


def load_scenario_description() -> str:
    """Load the scenario description from scenario.md."""
    return (SCENARIO_DIR / "scenario.md").read_text(encoding="utf-8")


def load_logs(log_group: str) -> list[dict]:
    """Load parsed log entries for a given log group."""
    filename = _LOG_GROUP_TO_FILE.get(log_group)
    if not filename:
        return []
    filepath = LOGS_DIR / filename
    if not filepath.exists():
        return []
    return [json.loads(line) for line in filepath.read_text(encoding="utf-8").strip().split("\n")]


def build_cloudwatch_state() -> str:
    """Build the initial state description for CloudWatch tool simulation.

    This tells the simulator LLM what log groups exist and what log data
    each group contains, so it can generate realistic responses to
    list_log_groups and query_logs calls.
    """
    lines = [
        "This is a CloudWatch Logs environment for a production system.",
        "",
        "Available log groups:",
    ]
    for group in LOG_GROUPS:
        lines.append(f"  - {group}")

    lines.append("")
    lines.append("Log data per group (use this to answer query_logs calls):")
    lines.append("")

    for group in LOG_GROUPS:
        logs = load_logs(group)
        if not logs:
            continue
        lines.append(f"### {group}")
        lines.append("```jsonl")
        for entry in logs:
            lines.append(json.dumps(entry))
        lines.append("```")
        lines.append("")

    lines.extend([
        "IMPORTANT INSTRUCTIONS FOR SIMULATING TOOL RESPONSES:",
        "- For list_log_groups: return the log group names that match the given prefix.",
        "- For query_logs: parse the CloudWatch Logs Insights query and filter/transform",
        "  the log data above accordingly. Return results as a list of dicts with fields",
        "  matching the query's `fields` clause. If the query filters by level or message",
        "  pattern, apply those filters to the log data.",
        "- Timestamps: treat offset_seconds as seconds from the start of the incident",
        "  window. Convert to realistic ISO timestamps (e.g. 2026-03-26T09:15:00Z base).",
        "- The @timestamp and @message fields should be present in results when requested.",
    ])

    return "\n".join(lines)


def build_jira_state() -> str:
    """Build the initial state description for Jira tool simulation."""
    return (
        "Jira Cloud instance at https://example.atlassian.net.\n"
        "The agent will post comments to incident tickets.\n"
        "When post_jira_comment is called, return a success response with a realistic\n"
        "comment URL like: Comment posted successfully: "
        "https://example.atlassian.net/browse/{issue_key}?focusedCommentId=12345"
    )


def build_skills_state() -> str:
    """Build the initial state description for the skills tool simulation."""
    # Load the actual skill content so the simulator returns it verbatim
    skill_file = (
        Path(__file__).parent.parent.parent.parent
        / "src"
        / "agent"
        / "skills"
        / "incident_triage.md"
    )
    skill_content = skill_file.read_text(encoding="utf-8")
    return (
        "Available skills:\n"
        f'- "Incident Triage" — full content:\n'
        f"```\n{skill_content}```\n\n"
        "When load_skill is called with a matching title, return the full skill content above."
    )
