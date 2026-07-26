# Detect operating system
ifeq ($(OS),Windows_NT)
    VENV_BIN = .venv/Scripts
    PYTHON = $(VENV_BIN)/python.exe
    PIP = $(VENV_BIN)/pip.exe
else
    VENV_BIN = .venv/bin
    PYTHON = $(VENV_BIN)/python
    PIP = $(VENV_BIN)/pip
endif

.PHONY: all setup run test clean help

all: help

help:
	@echo "Available commands:"
	@echo "  make setup   - Create virtual environment and install dependencies (uses 'uv' if available)"
	@echo "  make run     - Run the main CLI application"
	@echo "  make test    - Run the system verification test suite"
	@echo "  make clean   - Remove virtual environment, temporary database, and cached files"

setup:
	@if command -v uv >/dev/null 2>&1; then \
		echo "Detected 'uv', setting up virtual environment and dependencies..."; \
		uv venv .venv; \
		uv pip install -e .; \
	else \
		echo "Setting up virtual environment using standard python venv..."; \
		python3 -m venv .venv || python -m venv .venv || py -m venv .venv; \
		$(PIP) install --upgrade pip; \
		$(PIP) install -e .; \
	fi
	@echo "Setup complete! Virtual environment is ready."

run:
	@if [ ! -f "$(PYTHON)" ]; then \
		echo "Virtual environment not found. Running setup first..."; \
		$(MAKE) setup; \
	fi
	$(PYTHON) src/climain.py

test:
	@if [ ! -f "$(PYTHON)" ]; then \
		echo "Virtual environment not found. Running setup first..."; \
		$(MAKE) setup; \
	fi
	$(PYTHON) verify_app.py

clean:
	@echo "Cleaning workspace..."
	@rm -rf .venv test_mail.db
	@find . -type d -name "__pycache__" -exec rm -rf {} +
	@echo "Clean completed successfully."
