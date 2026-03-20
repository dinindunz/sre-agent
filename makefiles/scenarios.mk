# ==============================================================================
# Test Scenarios - CloudWatch Log Injection
# ==============================================================================

PYTHON := PYTHONPATH=. .venv/bin/python

# ==============================================================================
# Scenario 1 - Slow DB Queries
# ==============================================================================

scenario-1-inject:
	@echo "Cleaning up previous log groups..."
	@$(PYTHON) tests/scenarios/slow_db_queries/cleanup.py
	@echo "Injecting slow-db-queries scenario logs into CloudWatch..."
	@$(PYTHON) tests/scenarios/slow_db_queries/inject.py

scenario-1-clean:
	@echo "Cleaning up slow-db-queries scenario log groups..."
	@$(PYTHON) tests/scenarios/slow_db_queries/cleanup.py
