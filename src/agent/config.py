"""Configuration management for the agent runtime.

This module provides centralised configuration management with lazy loading
from environment variables.
"""

import os
from functools import lru_cache

from common.logger import logger

# Model pricing per 1K tokens in USD
MODEL_PRICING = {
    "au.anthropic.claude-sonnet-4-5-20250929-v1:0": {
        "input": 0.003,  # $3.00 per 1M tokens
        "output": 0.015,  # $15.00 per 1M tokens
        "cache_write": 0.00375,  # $3.75 per 1M tokens
        "cache_read": 0.0003,  # $0.30 per 1M tokens
    },
}


class AgentConfig:
    """Central configuration for the agent runtime.

    Loads configuration from environment variables on-demand.

    Attributes:
        region_name: AWS region name (from REGION_NAME env var)
        model_id: Bedrock model ID (from MODEL_ID env var)
        model_temperature: Model temperature for generation (from MODEL_TEMPERATURE env var)
        model_max_tokens: Maximum tokens to generate (from MODEL_MAX_TOKENS env var)
        model_pricing: Per-1K-token costs loaded from MODEL_COST_* env vars
    """

    def __init__(self) -> None:
        """Initialise configuration with required environment variables."""
        self.region_name: str = os.environ["REGION_NAME"]
        self.model_id: str = os.environ["MODEL_ID"]
        self.model_temperature: float = float(os.environ.get("MODEL_TEMPERATURE", "1.0"))
        self.model_max_tokens: int = int(os.environ.get("MODEL_MAX_TOKENS", "16000"))
        self.thinking_budget_tokens: int = int(os.environ.get("THINKING_BUDGET_TOKENS", "8000"))
        self.model_pricing: dict = MODEL_PRICING.get(self.model_id, {})

        logger.debug(
            f"[Config] Initialised: region={self.region_name} "
            f"model_id={self.model_id} "
            f"model_temperature={self.model_temperature} "
            f"model_max_tokens={self.model_max_tokens}"
            f"thinking_budget_tokens={self.thinking_budget_tokens}"
        )


@lru_cache
def get_config() -> AgentConfig:
    """
    Get singleton configuration instance.

    Returns:
        Singleton AgentConfig instance
    """
    logger.debug("[Config] Creating singleton AgentConfig instance")
    return AgentConfig()
