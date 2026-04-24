.PHONY: init install \
        upgrade upgrade-sql downgrade revision show-history show-current \
        clean-stale up dev down \
        test-crud test-services test-api test-security test test-coverage openapi-snapshot-update \
        format lint typecheck check \
        clean help

.DEFAULT_GOAL := help

# Environment config
include ../.env

# Application config
APP_NAME := sdep-backend

##@ Dependency management

init: ## First-time setup (generates uv.lock)
	@echo "📦 Initializing dependencies..."
	uv sync
	@echo "✅ Dependencies initialized!"

install: ## Install dependencies (from lockfile)
	@echo "📦 Installing dependencies..."
	uv sync --frozen
	@echo "✅ Dependencies installed!"

##@ Alembic

upgrade: ## Upgrade database to latest revision
	@uv run alembic upgrade head

upgrade-sql: ## Show upgrade SQL (offline, no database needed)
	@uv run alembic upgrade head --sql

downgrade: ## Downgrade database by one revision
	@echo "Downgrading database by one revision..."
	@uv run alembic downgrade -1

revision: ## Create revision (MSG='description')
	@echo "Creating new migration revision..."
	@if [ -z "$(MSG)" ]; then \
		echo "Usage: make revision MSG='Description of changes'"; \
		exit 1; \
	fi
	@uv run alembic revision --autogenerate -m "$(MSG)"

show-current: ## Show current database revision
	@echo "Showing current database revision..."
	@uv run alembic current

show-history: ## Show migration history (offline, no database needed)
	@uv run alembic history

##@ Dev

check: ## Format, lint, type check
	@echo "🧪 Checking backend quality..."
	uv run ruff format . ## Format code and auto-fix
	uv run ruff format --check . ## Verify formatting is correct
	uv run ruff check --select I --fix-only . ## Organize imports
	uv run pyright . ## Check typing
	uv run ruff check . ## Lint (check for errors and style issues)
	uvx ty check ## Verify type completeness
	@echo "✅ Quality check completed!"

clean-stale: # Kill any stale uvicorn/backend processes
	@echo "🧹 Cleaning stale backend processes..."
	@# Method 1: Kill by process name pattern
	@ps aux | grep -E "uvicorn.*app.main|python.*uvicorn.*app.main" | grep -v grep | awk '{print $$2}' | while read pid; do \
		USER=$$(ps -o user= -p $$pid 2>/dev/null || echo ""); \
		if [ -n "$$USER" ] && [ "$$USER" != "root" ]; then \
			kill -9 $$pid 2>/dev/null || true; \
		elif [ "$$USER" = "root" ]; then \
			echo "⚠️  Killing root process $$pid - this may require password"; \
			sudo kill -9 $$pid 2>/dev/null || echo "❌ Failed to kill root process $$pid"; \
		fi; \
	done
	@# Method 2: Kill by port using lsof
	@lsof -ti:8000 2>/dev/null | while read pid; do \
		USER=$$(ps -o user= -p $$pid 2>/dev/null || echo ""); \
		if [ -n "$$USER" ] && [ "$$USER" != "root" ]; then \
			kill -9 $$pid 2>/dev/null || true; \
		elif [ "$$USER" = "root" ]; then \
			echo "⚠️  Killing root process $$pid on port 8000 - this may require password"; \
			sudo kill -9 $$pid 2>/dev/null || echo "❌ Failed to kill root process $$pid"; \
		fi; \
	done
	@echo "✅ Stale processes cleaned!"

_start: clean-stale
	@if [ "$$(id -u)" = "0" ]; then \
		echo "❌ Error: Do not run uvicorn as root!"; \
		exit 1; \
	fi
	@echo "🚀 Starting backend..."
	@echo "API docs running at http://localhost:8000/api/docs"
	uv run uvicorn app.main:app --reload --no-server-header
	@echo "✅ Backend started!"

up: _start ## Start backend

dev: _start ## Start backend (alias for up)

down: ## Stop backend
	@echo "🛑 Stopping backend..."
	@PID=$$(pgrep -f "uvicorn app.main:app --reload$$" 2>/dev/null | head -1); \
	if [ -n "$$PID" ]; then \
		kill -TERM $$PID 2>/dev/null && echo "✅ API server stopped!" || echo "Failed to stop API server"; \
	else \
		echo "API server was not running"; \
	fi
	@echo "✅ Backend stopped!"

##@ Unit testing

test: ## Test all (quiet)
	@echo "🧪 Running tests... (please wait)"
	@uv run python -m pytest -n auto -q --tb=line --no-header 2>&1 | tail -20
	@echo "✅ All tests completed!"

test-verbose: ## Test all (verbose)
	@echo "🧪 Running tests... (please wait)"
	uv run python -m pytest -n auto
	@echo "✅ All tests completed!"

test-coverage: ## Test all (coverage)
	@echo "🧪 Running tests with coverage..."
	uv run python -m pytest -n auto --cov=app --cov-report=term-missing --cov-report=html --cov-report=xml
	@echo "✅ Coverage tests completed! Coverage report in htmlcov/"

test-crud: ## Test CRUD only
	@echo "🧪 Running CRUD tests..."
	uv run python -m pytest tests/crud/ -n auto
	@echo "✅ CRUD tests completed!"

test-services: ## Test services only
	@echo "🧪 Running service tests..."
	uv run python -m pytest tests/services/ -n auto
	@echo "✅ Service tests completed!"

test-api: ## Test API only
	@echo "🧪 Running API tests..."
	uv run python -m pytest tests/api/ -n auto
	@echo "✅ API tests completed!"

test-security: ## Test security only
	@echo "🧪 Running security tests..."
	uv run python -m pytest tests/security/ -n auto
	@echo "✅ Security tests completed!"

##@ Housekeeping

openapi-snapshot-update: ## Update the frozen OpenAPI snapshot
	@echo "🧊 Updating frozen OpenAPI snapshot..."
	uv run python -c "from tests.api.test_openapi_schema_frozen import write_openapi_snapshots; print(write_openapi_snapshots())"
	@echo "✅ OpenAPI snapshot updated!"

clean: ## Clean up generated files
	@echo "🧹 Cleaning up..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	@echo "✅ Cleanup completed!"

##@ Help

help: ## Show help
	@echo "🤖 Make"
	@echo ""
	@echo "Available commands:"
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n"} /^[a-zA-Z0-9_-]+:.*?##/ { printf "  \033[36m%-40s\033[0m  %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)
