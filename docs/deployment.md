# CI/CD and Deployment

This project uses GitHub Actions for CI and release publishing.

## Workflows

- CI: `.github/workflows/ci.yml`
  - Runs on push to `main` and pull requests.
  - Checks: `ruff check`, `ruff format --check`, `mypy --strict`, `pytest`.
  - Python versions: 3.11, 3.12, 3.13.
  - Builds package artifacts and validates them with `twine check`.

- Release: `.github/workflows/release.yml`
  - On GitHub release `published`: builds and publishes to PyPI.
  - On manual dispatch: choose `testpypi` or `pypi` target.

## One-time setup (GitHub + PyPI)

1. Create PyPI project `fastapi-request-pipeline` (and optionally TestPyPI project with same name).
2. Configure Trusted Publisher in PyPI:
   - Owner: your GitHub org/user
   - Repository: `fastapi-request-pipeline`
   - Workflow name: `release.yml`
   - Environment: `pypi`
3. Configure Trusted Publisher in TestPyPI similarly, with environment `testpypi`.
4. In GitHub repository settings, create environments:
   - `pypi`
   - `testpypi`
   Optional: add required reviewers for manual approval.

## Branch protection (recommended)

In GitHub repository settings for `main`, enable branch protection rules:

- Require a pull request before merging.
- Require approvals (at least 1).
- Require status checks to pass before merging.
- Include administrators (recommended for consistency).

Select these required checks from the CI workflow:

- `Lint, Typecheck, Test (py3.11)`
- `Lint, Typecheck, Test (py3.12)`
- `Lint, Typecheck, Test (py3.13)`
- `Build package`

This ensures only code that is linted, type-checked, tested, and package-valid reaches `main`.

## Release process

1. Bump version in `pyproject.toml`.
2. Commit and push to `main`.
3. (Optional) Test publish:
   - Run Actions workflow `Release` manually with `repository=testpypi`.
4. Create a GitHub release with tag like `v0.1.1`.
5. `Release` workflow publishes package to PyPI.

## Local packaging check

```bash
uv build
uvx twine check dist/*
```
