SHELL := /bin/zsh
VENV := .venv
PY := $(VENV)/bin/python
MARKDOWN_FILES := README.md CHANGELOG.md TODO.md AGENTS.md docs/*.md
PREFIX ?= $(HOME)/.local
BINDIR ?= $(PREFIX)/bin
INSTALL_NAME ?= tricount-exporter
INSTALL_PATH ?= $(BINDIR)/$(INSTALL_NAME)
CONFIG_DIR ?= $(HOME)/.config/tricount-exporter
CONFIG_PATH ?= $(CONFIG_DIR)/config.toml
APP_HOME ?= $(HOME)/.local/share/$(INSTALL_NAME)
APP_VENV ?= $(APP_HOME)/venv
APP_PY := $(APP_VENV)/bin/python

.DEFAULT_GOAL := help

.PHONY: help check-deps venv app-venv install install-dev install-link install-config uninstall lint test check run clean

help: ## Show available targets
	@awk 'BEGIN { FS = ":.*##" } /^[a-zA-Z_-]+:.*##/ { printf "  %-16s %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

check-deps: ## Verify required system prerequisites
	@command -v python3 >/dev/null 2>&1 \
		|| { echo "python3 not found"; exit 1; }
	@python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" \
		|| { echo "Python 3.11+ required (found $$(python3 --version 2>&1))"; exit 1; }
	@mkdir -p "$(BINDIR)" "$(CONFIG_DIR)"
	@if print -r -- "$$PATH" | tr ':' '\n' | grep -Fx "$(BINDIR)" >/dev/null; then \
		echo "$(BINDIR) is on PATH"; \
	else \
		echo "$(BINDIR) is not on PATH"; \
		echo "Add this to your shell profile:"; \
		echo "export PATH=\"$(BINDIR):\$$PATH\""; \
	fi

venv: ## Create the virtual environment
	@if [[ ! -d "$(VENV)" ]]; then \
		python3 -m venv "$(VENV)"; \
	fi
	"$(PY)" -m ensurepip --upgrade
	"$(PY)" -m pip install --upgrade pip

app-venv: ## Create the standalone runtime virtual environment
	@mkdir -p "$(APP_HOME)"
	@if [[ ! -d "$(APP_VENV)" ]]; then \
		python3 -m venv "$(APP_VENV)"; \
	fi
	"$(APP_PY)" -m ensurepip --upgrade
	"$(APP_PY)" -m pip install --upgrade pip

install: check-deps app-venv ## Install the CLI in a standalone user venv
	"$(APP_PY)" -m pip install setuptools wheel
	"$(APP_PY)" -m pip install --no-build-isolation .
	@$(MAKE) install-link install-config

install-dev: check-deps venv ## Install repo-local dev dependencies
	"$(PY)" -m pip install setuptools wheel
	"$(PY)" -m pip install -e ".[dev]"
	@$(MAKE) install-config

install-link: ## Link the standalone runtime CLI into ~/.local/bin
	@mkdir -p "$(BINDIR)"
	@[[ -x "$(APP_VENV)/bin/$(INSTALL_NAME)" ]] \
		|| { echo "$(APP_VENV)/bin/$(INSTALL_NAME) not found. Run 'make install' first."; exit 1; }
	@ln -sf "$(APP_VENV)/bin/$(INSTALL_NAME)" "$(INSTALL_PATH)"
	@echo "Installed $(INSTALL_NAME) -> $(INSTALL_PATH)"

install-config: ## Install the example config if it does not exist yet
	@mkdir -p "$(CONFIG_DIR)"
	@if [[ ! -f "$(CONFIG_PATH)" ]]; then \
		cp config.toml.example "$(CONFIG_PATH)"; \
		echo "Installed config template to $(CONFIG_PATH)"; \
	else \
		echo "Config already exists at $(CONFIG_PATH)"; \
	fi

uninstall: ## Remove the linked CLI and standalone runtime environment
	@rm -f "$(INSTALL_PATH)"
	@rm -rf "$(APP_HOME)"
	@echo "Removed $(INSTALL_PATH)"

lint: venv ## Run Python and Markdown checks
	PYTHONPATH=src "$(PY)" -m ruff check src tests
	PYTHONPATH=src "$(PY)" -m ruff format --check src tests
	PYTHONPATH=src "$(PY)" -m mypy src
	markdownlint --config .markdownlint.json $(MARKDOWN_FILES)
	shellcheck --enable=all scripts/*.sh

test: venv ## Run regression tests
	PYTHONPATH=src "$(PY)" -m pytest -q

check: lint test ## Run the full maintainer quality gate

run: install ## Show CLI help
	"$(INSTALL_PATH)" --help

clean: ## Remove local build and virtualenv artifacts
	rm -rf $(VENV) .mypy_cache .ruff_cache build dist src/*.egg-info(N) *.egg-info(N)
