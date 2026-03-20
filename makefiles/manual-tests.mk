# ==============================================================================
# Manual Tests - Python Interpreter
# ==============================================================================

# Set PYTHONPATH to project root so tests can import from tests.common
PYTHON := PYTHONPATH=. .venv/bin/python

# ==============================================================================
# Manual Tests - Agent Runtime
# ==============================================================================

agent-hello:
	@echo "Sending hello to agent runtime..."
	@$(PYTHON) tests/manual/runtimes/agent/hello.py

agent-chat:
	@echo "Starting interactive chat with agent..."
	@$(PYTHON) tests/manual/runtimes/agent/chat_client.py
