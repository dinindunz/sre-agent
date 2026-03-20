"""Core agent invocation handler.

This module creates agent instances per request and processes user input
using the Strands SDK with a Bedrock model.
"""

from typing import Any

from hooks.token_usage_tracker import TokenUsageTracker
from strands import Agent
from strands.models.bedrock import BedrockModel, CacheConfig

from common.logger import logger

# Default values for optional payload fields
DEFAULT_ACTOR_ID = "default_actor"
DEFAULT_SESSION_ID = "default_session"
DEFAULT_USER_MESSAGE = "Hello"


def extract_text_from_result(result: Any) -> str:
    """
    Extract text content from agent result message.

    Args:
        result: Agent execution result with message content

    Returns:
        Concatenated text from all text content blocks, or empty string
    """
    return "".join(block["text"] for block in result.message.get("content", []) if "text" in block)


def invoke_agent(
    config: Any,
    tools: list,
    system_prompt: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """
    Process user input with agent.

    Args:
        config: Application configuration with region and model settings
        tools: List of tools available to the agent
        system_prompt: System prompt (reused across requests)
        payload: Request payload with AgentCore standard format:
            - input.value: User message (default: "Hello")
            - actorId: User identifier (default: "default_actor")
            - sessionId: Session identifier (default: "default_session")

    Returns:
        Response dictionary with AgentCore standard format:
            {
                "output": {"value": text},
                "sessionId": session_id,
                "actorId": actor_id
            }
    """
    # Extract parameters from payload with defaults (AgentCore standard format)
    user_message = payload.get("input", {}).get("value", DEFAULT_USER_MESSAGE)
    actor_id = payload.get("actorId", DEFAULT_ACTOR_ID)
    session_id = payload.get("sessionId", DEFAULT_SESSION_ID)

    # Log invocation
    logger.info(f"[Agent] Invoked: actor={actor_id} session={session_id}")

    # Create Bedrock model with extended + interleaved thinking
    # Note: temperature must be 1.0 when extended thinking is enabled (Bedrock requirement).
    model = BedrockModel(
        model_id=config.model_id,
        cache_config=CacheConfig(strategy="auto"),
        max_tokens=config.model_max_tokens,
        temperature=config.model_temperature,
        additional_request_fields={
            "anthropic_beta": ["interleaved-thinking-2025-05-14"],
            "thinking": {
                "type": "enabled",
                "budget_tokens": config.thinking_budget_tokens,
            },
        },
    )

    # Create agent instance for this request
    agent = Agent(
        model=model,
        tools=tools,
        system_prompt=system_prompt,
        hooks=[TokenUsageTracker()],
    )

    # Execute agent
    result = agent(user_message)

    # Extract text from agent response
    text = extract_text_from_result(result)

    # Log completion
    logger.info("[Agent] Completed")

    # Return AgentCore standard response format
    return {
        "output": {"value": text},
        "sessionId": session_id,
        "actorId": actor_id,
    }
