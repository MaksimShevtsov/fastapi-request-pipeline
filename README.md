# fastapi-request-pipeline

[![CI](https://github.com/MaksimShevtsov/fastapi-request-pipeline/actions/workflows/ci.yml/badge.svg)](https://github.com/MaksimShevtsov/fastapi-request-pipeline/actions/workflows/ci.yml)
[![PyPI Version](https://img.shields.io/pypi/v/fastapi-request-pipeline)](https://pypi.org/project/fastapi-request-pipeline/)

Composable request processing pipeline for FastAPI.

## Install

```bash
pip install fastapi-request-pipeline
```

## Development

```bash
uv sync --dev
uv run pytest
uv run ruff check .
uv run mypy --strict src/
```

## License

MIT
