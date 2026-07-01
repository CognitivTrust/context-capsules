# Releasing

This document is for the project's current sole maintainer, Yash Shah. It covers the full release process from preparation to PyPI publication.

## Prerequisites

- Write access to the `CognitivTrust/context-capsules` repository on GitHub.
- PyPI maintainer role on the `context-capsule` package.
- TestPyPI maintainer role on the `context-capsule` package.
- GitHub Environments configured: `testpypi` and `pypi` (with Trusted Publisher / OIDC enabled).

## Versioning policy

Context Capsules follows [Semantic Versioning](https://semver.org):

- **PATCH** (`0.1.1`): backward-compatible bug fixes only.
- **MINOR** (`0.2.0`): backward-compatible new features, new CLI commands, or new optional schema fields.
- **MAJOR** (`1.0.0`): breaking changes (schema MAJOR bump, removed commands, changed exit codes).

The package version in `pyproject.toml` is the single source of truth. The on-disk schema version evolves independently.

While the package is pre-1.0, minor releases may include breaking changes with proper notice in the changelog.

## Release checklist

### 1. Prepare the release branch

```bash
git checkout main
git pull
git checkout -b release/vX.Y.Z
```

### 2. Update the version

Edit `pyproject.toml`:

```toml
[project]
version = "X.Y.Z"
```

### 3. Finalize CHANGELOG.md

Move items from `[Unreleased]` to a new `[X.Y.Z] - YYYY-MM-DD` section:

```markdown
## [X.Y.Z] - YYYY-MM-DD

### Added
- ...

### Fixed
- ...
```

Add an empty `[Unreleased]` section at the top.

### 4. Run the full check locally

```bash
# Windows
.\.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate

ruff check .
ruff format --check .
mypy
pytest
python -m build
twine check dist/*
```

All must pass.

### 5. Open a PR and wait for CI

Push the branch and open a PR against `main`. CI runs lint, format, types, and tests on all supported OS/Python combinations. The PR must be green before merging.

### 6. Merge and tag

```bash
git checkout main
git pull
git tag vX.Y.Z
git push origin vX.Y.Z
```

The `release.yml` workflow triggers automatically on the tag push.

### 7. Monitor the release workflow

The workflow:
1. Builds the distribution.
2. Verifies the tag matches the package version.
3. Publishes to TestPyPI.
4. Smoke-tests the TestPyPI install (`capsule --version` must succeed).
5. Publishes to PyPI.
6. Creates a GitHub release with the changelog entry as the release notes.

If any step fails, see the workflow logs and fix before re-tagging.

### 8. Verify the PyPI release

```bash
pip install context-capsule==X.Y.Z
capsule --version
```

### 9. Post-release

- Announce in GitHub Discussions (Show and Tell).
- Update the `[Unreleased]` section in `CHANGELOG.md` on main if needed.

## Hotfix releases

For urgent fixes to a released version:

1. Branch from the release tag: `git checkout -b hotfix/vX.Y.Z+1 vX.Y.Z`.
2. Apply the fix.
3. Bump the PATCH version, update `CHANGELOG.md`.
4. Open a PR against `main` (cherry-pick the fix to `main` as well).
5. Tag and release following the normal process.

## GitHub Environments setup

The release workflow uses GitHub's OIDC Trusted Publisher to publish without storing API tokens as secrets.

- Go to **Settings → Environments** and create `testpypi` and `pypi`.
- On TestPyPI and PyPI, add a Trusted Publisher for `CognitivTrust/context-capsules` with the environment name matching.
- Set the `pypi` environment to require a manual approval review before publishing (recommended for production).
