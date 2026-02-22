# CI/CD and Deployment

This project uses GitHub Actions for CI and release publishing.

## Workflows

- CI: `.github/workflows/ci.yml`
  - Runs on push to `main` and pull requests.
  - Checks: `ruff check`, `ruff format --check`, `mypy --strict`, `pytest`.
  - Python versions: 3.11, 3.12, 3.13.
  - Builds package artifacts and validates them with `twine check`.

- Release: `.github/workflows/release.yml`
   - On GitHub release `published`: builds distributions, validates version/tag match, attaches artifacts to the GitHub Release page, and publishes to PyPI.
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

### Versioning rules (SemVer)

This project follows Semantic Versioning: `MAJOR.MINOR.PATCH`.

- Patch release: `0.1.1` -> `0.1.2` for fixes only.
- Minor release: `0.1.1` -> `0.2.0` for backward-compatible features.
- Major release: `0.1.1` -> `1.0.0` for breaking changes.

Always keep git tag and project version aligned:

- `pyproject.toml`: `version = "0.2.0"`
- Git tag / GitHub release: `v0.2.0`

The release workflow enforces this and fails on mismatch.

### Complete release pipeline

1. Update local `main`.

```bash
git checkout main
git pull --ff-only origin main
```

2. Run quality checks locally.

```bash
uv sync --extra dev
uv run ruff check .
uv run ruff format --check .
uv run mypy --strict src/
uv run pytest
```

3. Bump version in `pyproject.toml` (SemVer).

4. Commit and push.

```bash
git add pyproject.toml
git commit -m "chore(release): bump version to 0.2.0"
git push origin main
```

5. Optional dry run to TestPyPI.

- Open GitHub Actions -> `Release` -> `Run workflow`
- Select `repository=testpypi`
- Confirm package on TestPyPI before production publish

6. Create release tag and GitHub release.

```bash
git tag v0.2.0
git push origin v0.2.0
```

Then publish a GitHub Release for tag `v0.2.0`.

7. Automatic publish result.

On release `published`, workflow will:

- Build `dist/*.whl` and `dist/*.tar.gz`
- Validate `vX.Y.Z` tag matches `pyproject.toml` version
- Attach built distributions as GitHub Release assets
- Publish to PyPI

### Why reruns are safe

PyPI does not allow filename reuse for the same version. The workflow uses `skip-existing: true`, so reruns do not fail if artifacts were already uploaded.

## Common release failures and fixes

### `HTTP 400 File already exists`

Cause: trying to upload an already published filename (same version).

Fix:

- If release is already published, rerun workflow (safe with `skip-existing`).
- If you need new code, bump version and publish a new tag/release.

### Tag/version mismatch

Cause: tag and `pyproject.toml` version differ (example: tag `v0.2.0`, version `0.1.1`).

Fix:

- Align `pyproject.toml` version and tag.
- Rebuild and republish via new valid release.

### `main` push rejected (non-fast-forward)

Cause: local `main` behind `origin/main`.

Fix:

```bash
git checkout main
git pull --ff-only origin main
git push origin main
```

## Local packaging check

```bash
uv build
uvx twine check dist/*
```
