# ==============================================================================
# Code Quality Commands
# ==============================================================================

lint:
	@echo "Linting Python code with ruff..."
	@.venv/bin/ruff check src/ app.py

format:
	@echo "Formatting Python code with ruff..."
	@.venv/bin/ruff format src/ app.py
	@.venv/bin/ruff check --select I --fix src/ app.py
	@echo "✓ Code formatted successfully"
