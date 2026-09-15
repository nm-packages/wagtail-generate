.DEFAULT_GOAL := help

.PHONY: help sync lint typecheck test check pre-commit coverage \
	test-distribution test-compatibility playground playground-reset

help:
	@echo "make sync              Synchronize the development environment"
	@echo "make lint              Run the Ruff lint check"
	@echo "make typecheck         Run mypy"
	@echo "make test              Run the pytest suite"
	@echo "make check             Run lint, type checking, and tests"
	@echo "make pre-commit        Run all pre-commit hooks"
	@echo "make coverage          Run tests with a coverage summary"
	@echo "make test-distribution Run the opt-in distribution test"
	@echo "make test-compatibility Run the opt-in Wagtail compatibility test"
	@echo "make playground        Rebuild and serve SQLite with src layout, starter homepage, custom users, and custom images"
	@echo "make playground-reset  Delete the generated playground"

sync:
	uv sync

lint:
	uv run ruff check .

typecheck:
	uv run mypy

test:
	uv run pytest

check: lint typecheck test

pre-commit:
	uv run pre-commit run --all-files

coverage:
	uv run pytest --cov=wagtail_generate --cov-report=term-missing

test-distribution:
	WAGTAIL_GENERATE_TEST_DISTRIBUTION=1 uv run pytest tests/test_distribution.py

test-compatibility:
	WAGTAIL_GENERATE_TEST_COMPATIBILITY=1 uv run pytest tests/test_wagtail_compatibility.py

playground:
	uv run python -m wagtail_generate.playground \
		--database sqlite3 --site-directory src \
		--starter-homepage --custom-user --custom-images

playground-reset:
	uv run python -m wagtail_generate.playground --reset
