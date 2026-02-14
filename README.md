# fastapi-request-pipeline

[![CI](https://github.com/MaksimShevtsov/fastapi-request-pipeline/actions/workflows/ci.yml/badge.svg)](https://github.com/MaksimShevtsov/fastapi-request-pipeline/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/MaksimShevtsov/fastapi-request-pipeline/branch/main/graph/badge.svg)](https://codecov.io/gh/MaksimShevtsov/fastapi-request-pipeline)
[![PyPI Version](https://img.shields.io/pypi/v/fastapi-request-pipeline)](https://pypi.org/project/fastapi-request-pipeline/)
[![Python Version](https://img.shields.io/pypi/pyversions/fastapi-request-pipeline)](https://pypi.org/project/fastapi-request-pipeline/)
[![License](https://img.shields.io/github/license/MaksimShevtsov/fastapi-request-pipeline)](https://github.com/MaksimShevtsov/fastapi-request-pipeline/blob/main/LICENSE)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

Composable request processing pipeline for FastAPI.

## Install

```bash
pip install fastapi-request-pipeline
```

## Development

```bash
uv sync --extra dev
uv run pytest
uv run ruff check .
uv run mypy --strict src/
```

## License

MIT
