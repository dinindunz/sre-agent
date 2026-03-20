# ==============================================================================
# Configuration Validation
# ==============================================================================

PYTHON := .venv/bin/python

validate-config:
	@echo "Validating environment configurations..."
	@$(PYTHON) -c "from src.cdk.config import load_config; \
		print('✓ dev.yaml'); load_config('dev'); \
		print('\n✓ All configurations are valid')"

show-config:
	@echo "Configuration for $(ENV) environment:"
	@echo "======================================"
	@$(PYTHON) -c "from src.cdk.config import load_config; \
		import yaml; \
		config = load_config('$(ENV)'); \
		print(yaml.dump({ \
			'environment': config.environment, \
			'agent_runtime': { \
				'log_level': config.agent_runtime.log_level, \
				'otel_logging_enabled': config.agent_runtime.otel_logging_enabled \
			}, \
			'model': { \
				'model_id': config.model.model_id, \
				'thinking_budget_tokens': config.model.thinking_budget_tokens, \
				'model_temperature': config.model.model_temperature, \
				'model_max_tokens': config.model.model_max_tokens \
			}, \
			'cognito': { \
				'access_token_validity_minutes': config.cognito.access_token_validity_minutes, \
				'oauth_cache': { \
					'buffer_percent': config.cognito.oauth_cache.buffer_percent, \
					'buffer_min_seconds': config.cognito.oauth_cache.buffer_min_seconds, \
					'buffer_max_seconds': config.cognito.oauth_cache.buffer_max_seconds \
				} \
			}, \
			'observability': { \
				'enabled': config.observability.enabled \
			} \
		}, default_flow_style=False))"
