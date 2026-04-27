"""Eval: Incident Triage with ToolSimulator.

Tests that the SRE agent can correctly diagnose the "slow DB queries" scenario
using LLM-simulated tools instead of live AWS/Jira infrastructure.

Usage:
    python -m tests.evals.test_incident_triage
"""

from typing import Any

from pydantic import BaseModel, Field
from strands import Agent
from strands_evals import Case, Experiment
from strands_evals.evaluators import GoalSuccessRateEvaluator
from strands_evals.mappers import StrandsInMemorySessionMapper
from strands_evals.simulation.tool_simulator import ToolSimulator
from strands_evals.telemetry import StrandsEvalsTelemetry

from tests.evals.scenarios.slow_db_queries import (
    build_cloudwatch_state,
    build_jira_state,
    build_skills_state,
    load_jira_alert,
)

# ---------------------------------------------------------------------------
# Telemetry & simulator setup
# ---------------------------------------------------------------------------
telemetry = StrandsEvalsTelemetry().setup_in_memory_exporter()
memory_exporter = telemetry.in_memory_exporter
tool_simulator = ToolSimulator()


# ---------------------------------------------------------------------------
# Output schemas — match real tool return types
# ---------------------------------------------------------------------------
class LogGroupsResponse(BaseModel):
    """Response for list_log_groups."""

    log_groups: list[str] = Field(..., description="List of CloudWatch log group names")


class LogEntry(BaseModel):
    """A single log query result row."""

    timestamp: str = Field(alias="@timestamp", default="", description="Log timestamp")
    message: str = Field(alias="@message", default="", description="Log message")
    level: str = Field(default="", description="Log level (INFO/WARN/ERROR)")
    service: str = Field(default="", description="Service name")
    extra: dict[str, Any] = Field(default_factory=dict, description="Additional fields")


class QueryLogsResponse(BaseModel):
    """Response for query_logs."""

    results: list[dict[str, Any]] = Field(
        ..., description="List of result rows, each a dict of field name to value"
    )


class JiraCommentResponse(BaseModel):
    """Response for post_jira_comment."""

    message: str = Field(..., description="Success or error message with comment URL")


class SkillResponse(BaseModel):
    """Response for load_skill."""

    content: str = Field(..., description="Full markdown content of the skill")


# ---------------------------------------------------------------------------
# Register simulated tools
# ---------------------------------------------------------------------------
@tool_simulator.tool(
    share_state_id="cloudwatch",
    initial_state_description=build_cloudwatch_state(),
    output_schema=LogGroupsResponse,
)
def list_log_groups(prefix: str = "") -> list[str]:
    """List CloudWatch log group names, optionally filtered by a prefix.

    Use this to discover what log groups exist before querying them.

    Args:
        prefix: Optional prefix to filter log groups (e.g. "/production").
                Returns all log groups if empty.

    Returns:
        List of log group names.
    """
    pass


@tool_simulator.tool(
    share_state_id="cloudwatch",
    output_schema=QueryLogsResponse,
)
def query_logs(
    log_group_names: list[str],
    query: str,
    lookback_minutes: int = 60,
    limit: int = 50,
) -> list[dict]:
    """Run a CloudWatch Logs Insights query across one or more log groups.

    Use this to search and filter log entries. Logs Insights query syntax examples:
      - fields @timestamp, @message | filter @message like /ERROR/ | sort @timestamp desc
      - fields @timestamp, level, message | filter level = "ERROR" | stats count() by bin(5m)

    Args:
        log_group_names: List of log group names to query.
        query:           CloudWatch Logs Insights query string.
        lookback_minutes: How far back to search (default: 60 minutes).
        limit:           Maximum number of results to return (default: 50, max: 10000).

    Returns:
        List of result rows, each row is a dict of field name to value.
    """
    pass


@tool_simulator.tool(
    share_state_id="jira",
    initial_state_description=build_jira_state(),
    output_schema=JiraCommentResponse,
)
def post_jira_comment(issue_key: str, comment: str, email: str) -> str:
    """Post a comment on a Jira issue.

    Use this to report investigation findings, root cause analysis, or
    remediation recommendations back to the Jira ticket that triggered this alert.

    Args:
        issue_key: The Jira issue key (e.g. "SAM1-11").
        comment:   The comment text to post. Markdown is supported.
        email:     The actor's email address.

    Returns:
        Success message with comment URL, or an error description.
    """
    pass


@tool_simulator.tool(
    share_state_id="skills",
    initial_state_description=build_skills_state(),
    output_schema=SkillResponse,
)
def load_skill(skill_title: str) -> str:
    """Load the full content of a specific skill by its title.

    Call this when you have identified the right skill from the system prompt
    summary and need the complete step-by-step instructions to execute it.

    Args:
        skill_title: The title of the skill to load (as shown in the system prompt).

    Returns:
        Full markdown content of the skill, or an error message if not found.
    """
    pass


# ---------------------------------------------------------------------------
# System prompt (mirrors src/agent/prompts + skills summary)
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """# System Prompt

You are an SRE agent. When an alert or incident is reported, use your available skills and tools to investigate and resolve it.

## Skill-First Workflow

1. Use `load_skill` to retrieve the relevant skill for the task
2. Follow its steps exactly
3. If no skill applies, use available tools directly

## Available Skills
When a user's request matches a skill, use the load_skill tool to retrieve the full instructions, then follow them.

- **Incident Triage**: Investigate an incident by querying logs across services to identify root cause and post findings."""


# ---------------------------------------------------------------------------
# Task function — runs the agent against a single case
# ---------------------------------------------------------------------------
def run_agent(case: Case) -> dict:
    """Create an agent with simulated tools and run the scenario."""
    # Get simulated tool instances
    sim_list_log_groups = tool_simulator.get_tool("list_log_groups")
    sim_query_logs = tool_simulator.get_tool("query_logs")
    sim_post_jira_comment = tool_simulator.get_tool("post_jira_comment")
    sim_load_skill = tool_simulator.get_tool("load_skill")

    agent = Agent(
        trace_attributes={
            "gen_ai.conversation.id": case.session_id,
            "session.id": case.session_id,
        },
        system_prompt=SYSTEM_PROMPT,
        tools=[sim_load_skill, sim_list_log_groups, sim_query_logs, sim_post_jira_comment],
        callback_handler=None,
    )

    # Run the agent with the Jira alert as input
    result = agent(case.input)

    # Extract text from result
    text = "".join(
        block["text"] for block in result.message.get("content", []) if "text" in block
    )

    print(f"\n{'='*80}")
    print(f"[Case: {case.name}]")
    print(f"[Input]: {case.input[:100]}...")
    print(f"[Output]: {text[:500]}...")
    print(f"{'='*80}\n")

    # Map spans for trajectory evaluation
    finished_spans = memory_exporter.get_finished_spans()
    mapper = StrandsInMemorySessionMapper()
    session = mapper.map_to_session(finished_spans, session_id=case.session_id)

    return {"output": text, "trajectory": session}


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------
jira_alert = load_jira_alert()

test_cases = [
    Case(
        name="slow_db_queries_triage",
        input=jira_alert,
        expected_output=(
            "Root cause: missing index on the orders table in db-primary causing "
            "full sequential scans (Seq Scan) on SELECT * FROM orders WHERE customer_id = $1. "
            "Fix: CREATE INDEX idx_orders_customer_id ON orders (customer_id)."
        ),
        metadata={
            "scenario": "slow_db_queries",
            "expected_root_cause": "missing index on orders table",
            "expected_affected_service": "api-service",
            "expected_affected_db": "db-primary",
            "expected_query": "SELECT * FROM orders WHERE customer_id",
            "red_herrings": ["notification-service queue lag", "db-replica-1 replication lag"],
        },
    ),
]

# ---------------------------------------------------------------------------
# Evaluators
# ---------------------------------------------------------------------------
evaluators = [GoalSuccessRateEvaluator()]

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    experiment = Experiment[str, str](cases=test_cases, evaluators=evaluators)
    reports = experiment.run_evaluations(run_agent)
    for report in reports:
        report.run_display()
