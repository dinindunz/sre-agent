"""SRE Agent runtime entry point.

This module provides the minimal orchestration layer for the SRE agent runtime.
It initialises the BedrockAgentCoreApp, loads configuration, wires tools and
system prompt, then delegates invocation to the agent_handler module.
"""

from agent_handler import invoke_agent
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from prompts.loader import load_system_prompt
from skills.loader import load_skills_summary
from tools import list_log_groups, load_skill, post_jira_comment, query_logs

from config import get_config

# Initialise Bedrock AgentCore app
app = BedrockAgentCoreApp()

# Global state for lazy initialization
_initialized = False
_config = None
_tools = None
_system_prompt = None


def _initialize() -> None:
    """
    Lazy initialization of global dependencies.

    Initialises tools and system prompt on first invocation.
    These are expensive to create, so we do them once per container.
    Agent instances are created per request.
    """
    global _initialized, _config, _tools, _system_prompt

    if _initialized:
        return

    _config = get_config()

    # Tools available to the agent
    _tools = [load_skill, list_log_groups, query_logs, post_jira_comment]

    # Load system prompt with high-level skills summary injected
    skills_section = load_skills_summary()
    _system_prompt = load_system_prompt(skills_section=skills_section)

    _initialized = True


@app.entrypoint
def invoke(payload):
    """
    SRE Agent runtime entrypoint.

    Args:
        payload: Request payload from AgentCore runtime with fields:
            - input.value: User message (optional, default: "Hello")
            - actorId: User identifier (optional, default: "default_actor")
            - sessionId: Session identifier (optional, default: "default_session")

    Returns:
        Response dictionary with AgentCore standard format:
            {
                "output": {"value": text},
                "sessionId": session_id,
                "actorId": actor_id
            }
    """
    _initialize()

    return invoke_agent(
        config=_config,
        tools=_tools,
        system_prompt=_system_prompt,
        payload=payload,
    )


# Start the runtime
app.run()
