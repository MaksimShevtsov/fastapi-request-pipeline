# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

fastapi-request-pipeline — a Python library for request processing pipelines in FastAPI. Licensed under MIT.

## Status

Feature 001-request-pipeline is implemented with full test coverage (198 tests).

## Tooling

- **Package management:** uv
- **Testing:** pytest + pytest-asyncio
- **Linting/Formatting:** ruff
- **Type checking:** mypy (strict)
- **Git hooks:** pre-commit

## Commands

- Install: `uv sync`
- Install with dev deps: `uv sync --extra dev`
- Test: `uv run pytest`
- Test with coverage: `uv run pytest --cov`
- Single test: `uv run pytest tests/test_foo.py::TestBar::test_baz -v`
- Lint: `uv run ruff check .`
- Lint fix: `uv run ruff check --fix .`
- Format: `uv run ruff format .`
- Type check: `uv run mypy --strict src/`
- Pre-commit install: `uv run pre-commit install`
- Pre-commit run all: `uv run pre-commit run --all-files`

## Active Technologies
- Python 3.11+ + FastAPI 0.100+, Pydantic V2 (via FastAPI), Starlette (via FastAPI) (001-request-pipeline)
- N/A — library operates in-memory; throttling uses pluggable backend with in-memory default (001-request-pipeline)
- N/A — documentation-only feature (Markdown files) + None — no code changes, only documentation files (001-llm-docs)

## Recent Changes
- 001-request-pipeline: Added Python 3.11+ + FastAPI 0.100+, Pydantic V2 (via FastAPI), Starlette (via FastAPI)
