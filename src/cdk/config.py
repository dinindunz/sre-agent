"""
Configuration loader for SRE Agent CDK stack.

Loads environment-specific configuration from YAML files in config/ directory.
Provides type-safe configuration objects using Python dataclasses.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass
class AgentRuntimeConfig:
    """Agent runtime configuration."""

    log_level: str = "INFO"
    otel_logging_enabled: bool = False

    def __post_init__(self):
        """Validate log level."""
        self._validate_log_level(self.log_level)
        self.log_level = self.log_level.upper()

    @staticmethod
    def _validate_log_level(level: str) -> None:
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR"}
        if level.upper() not in valid_levels:
            raise ValueError(f"log_level must be one of {valid_levels}, got {level}")


@dataclass
class OAuthCacheConfig:
    """OAuth2 access token caching configuration for agent runtime."""

    buffer_percent: float = 10.0  # Buffer as percentage of token lifetime (0.0-50.0)
    buffer_min_seconds: int = 60  # Minimum buffer in seconds
    buffer_max_seconds: int = 300  # Maximum buffer in seconds (5 minutes)

    def __post_init__(self):
        if not 0.0 <= self.buffer_percent <= 50.0:
            raise ValueError(
                f"buffer_percent must be between 0.0 and 50.0, got {self.buffer_percent}"
            )
        if self.buffer_min_seconds < 0:
            raise ValueError(f"buffer_min_seconds must be >= 0, got {self.buffer_min_seconds}")
        if self.buffer_max_seconds < self.buffer_min_seconds:
            raise ValueError(
                f"buffer_max_seconds ({self.buffer_max_seconds}) must be >= "
                f"buffer_min_seconds ({self.buffer_min_seconds})"
            )


@dataclass
class CognitoConfig:
    """Cognito user pool configuration."""

    access_token_validity_minutes: int = 15  # Access token expiry in minutes (5-1440)
    oauth_cache: OAuthCacheConfig | None = None  # OAuth token caching for agent runtime

    def __post_init__(self):
        if not 5 <= self.access_token_validity_minutes <= 1440:
            raise ValueError(
                f"access_token_validity_minutes must be between 5 and 1440 (24 hours), "
                f"got {self.access_token_validity_minutes}"
            )

        if self.oauth_cache is None:
            self.oauth_cache = OAuthCacheConfig()
        elif isinstance(self.oauth_cache, dict):
            self.oauth_cache = OAuthCacheConfig(**self.oauth_cache)


@dataclass
class ObservabilityConfig:
    """Phoenix observability configuration."""

    enabled: bool = False


@dataclass
class ModelConfig:
    """Bedrock model configuration."""

    model_id: str = "au.anthropic.claude-sonnet-4-5-20250929-v1:0"
    thinking_budget_tokens: int = 8000
    model_temperature: float = 1.0  # Must be 1.0 when extended thinking is enabled
    model_max_tokens: int = 16000

    def __post_init__(self):
        if not self.model_id:
            raise ValueError("model_id is required")
        if not 0.0 <= self.model_temperature <= 1.0:
            raise ValueError(
                f"model_temperature must be between 0.0 and 1.0, got {self.model_temperature}"
            )
        if self.model_max_tokens < 1:
            raise ValueError(f"model_max_tokens must be >= 1, got {self.model_max_tokens}")


@dataclass
class SREAgentConfig:
    """SRE Agent stack configuration."""

    environment: str  # dev, test, prod
    agent_runtime: AgentRuntimeConfig
    observability: ObservabilityConfig
    cognito: CognitoConfig | None = None
    model: ModelConfig | None = None

    def __post_init__(self):
        if isinstance(self.agent_runtime, dict):
            self.agent_runtime = AgentRuntimeConfig(**self.agent_runtime)
        if isinstance(self.observability, dict):
            self.observability = ObservabilityConfig(**self.observability)
        if self.cognito is None:
            self.cognito = CognitoConfig()
        elif isinstance(self.cognito, dict):
            self.cognito = CognitoConfig(**self.cognito)
        if self.model is None:
            self.model = ModelConfig()
        elif isinstance(self.model, dict):
            self.model = ModelConfig(**self.model)


def load_config(environment: str) -> SREAgentConfig:
    """Load environment-specific configuration from YAML file."""
    project_root = Path(__file__).parent.parent.parent
    config_file = project_root / "config" / f"{environment}.yaml"

    if not config_file.exists():
        raise FileNotFoundError(
            f"Configuration file not found: {config_file}\n"
            f"Available configs: {list((project_root / 'config').glob('*.yaml'))}"
        )

    with open(config_file) as f:
        config_data = yaml.safe_load(f)

    config_data["environment"] = environment
    return SREAgentConfig(**config_data)


def get_config_from_context(app: Any) -> SREAgentConfig:
    """Helper to load configuration from CDK app context."""
    env = app.node.try_get_context("env")
    if not env:
        raise ValueError("Environment not specified. Use: cdk deploy --context env=dev")
    return load_config(env)
