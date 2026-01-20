# Makefile for chef-gpt development tasks

.PHONY: help install install-dev lint format typecheck test coverage clean all check

# Default target
help:
	@echo "Available targets:"
	@echo "  install      - Install production dependencies"
	@echo "  install-dev  - Install all dependencies (production + dev)"
	@echo "  lint         - Run ruff linter"
	@echo "  format       - Format code with ruff"
	@echo "  typecheck    - Run pyright type checker"
	@echo "  test         - Run tests"
	@echo "  coverage     - Run tests with coverage report"
	@echo "  check        - Run all checks (lint, typecheck, test)"
	@echo "  clean        - Remove generated files"
	@echo "  all          - Install deps and run all checks"

# Install production dependencies
install:
	pip install -r requirements.txt

# Install all dependencies including dev tools
install-dev:
	pip install -r requirements.txt -r requirements-dev.txt

# Run ruff linter
lint:
	ruff check server/ simulator/ tests/

# Run ruff linter with auto-fix
lint-fix:
	ruff check --fix server/ simulator/ tests/

# Format code with ruff
format:
	ruff format server/ simulator/ tests/

# Check formatting without making changes
format-check:
	ruff format --check server/ simulator/ tests/

# Run pyright type checker
typecheck:
	pyright server/ simulator/

# Run all tests
test:
	pytest tests/

# Run simulator tests only
test-simulator:
	pytest tests/simulator/ -v

# Run server tests only
test-server:
	pytest tests/ --ignore=tests/simulator/ -v

# Run tests with coverage
coverage:
	pytest tests/ --cov=server --cov=simulator --cov-report=html --cov-report=xml --cov-report=term-missing

# Run coverage for simulator only
coverage-simulator:
	pytest tests/simulator/ --cov=simulator --cov-report=html --cov-report=term-missing

# Run all checks (lint, typecheck, tests)
check: lint typecheck test

# Run all checks with coverage
check-full: lint typecheck coverage

# Clean generated files
clean:
	rm -rf .pytest_cache/
	rm -rf __pycache__/
	rm -rf server/__pycache__/
	rm -rf simulator/__pycache__/
	rm -rf tests/__pycache__/
	rm -rf tests/simulator/__pycache__/
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf coverage.xml
	rm -rf .ruff_cache/
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

# Full setup and check
all: install-dev check
