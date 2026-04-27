.PHONY: help

# Load environment variables from .env file (if it exists)
-include .env
export

# Environment variables
ENV ?= dev

# Include all sub-makefiles
include makefiles/setup.mk
include makefiles/config.mk
include makefiles/code-quality.mk
include makefiles/cdk.mk
include makefiles/users.mk
include makefiles/manual-tests.mk
include makefiles/scenarios.mk
include makefiles/convenience.mk

# Default target - show help
help:
	@echo "SRE Agent - Make Commands"
	@echo "========================="
	@echo ""
	@echo "Setup:"
	@echo "  make install                       - Set up virtual environment and install dependencies"
	@echo ""
	@echo "Configuration:"
	@echo "  make validate-config               - Validate environment configuration"
	@echo "  make show-config ENV=dev           - Show current configuration for an environment"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint                          - Lint Python code with ruff"
	@echo "  make format                        - Format Python code with ruff"
	@echo ""
	@echo "CDK Deployment:"
	@echo "  make deploy                        - Deploy SRE Agent stack (ENV=dev by default)"
	@echo "  make diff                          - Show SRE Agent stack changes"
	@echo "  make destroy                       - Destroy SRE Agent stack"
	@echo ""
	@echo "User Management:"
	@echo "  make create-user                   - Create Cognito user for ACTOR_ID from .env"
	@echo "  make list-users                    - List all Cognito users in the pool"
	@echo ""
	@echo "Manual Tests - Agent Runtime:"
	@echo "  make agent-hello                   - Send a hello message to the agent runtime"
	@echo "  make agent-chat                    - Start interactive chat with the agent"
	@echo ""
	@echo "Scenarios:"
	@echo "  make scenario-1-inject             - Inject slow-db-queries logs into CloudWatch"
	@echo "  make scenario-1-clean              - Delete slow-db-queries CloudWatch log groups"
	@echo ""
	@echo "Evals (ToolSimulator):"
	@echo "  make eval-scenario-1               - Run Scenario 1 eval with simulated tools"
	@echo ""
	@echo "Examples:"
	@echo "  make deploy ENV=prod               - Deploy SRE Agent to production"
	@echo "  make diff ENV=dev                  - Show changes for dev environment"
