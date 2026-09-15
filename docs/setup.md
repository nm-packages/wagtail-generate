# Development setup

Use UV for the development environment and all Python commands:

```shell
uv sync
uv run pre-commit install
uv run wagtail-generate --help
```

Run the routine checks before considering a change complete:

```shell
uv run ruff check .
uv run mypy
uv run pytest
```

Run all hooks with:

```shell
uv run pre-commit run --all-files
```

The pytest hook runs the full suite on every commit, including template-only
and configuration-only changes. To verify a specific changed-file selection:

```shell
uv run pre-commit run pytest --files <path>
```

Add or update tests for behavior changes, especially path validation, conflicts,
source-directory selection, rendered content, and command exit codes. For an
editable CLI installation, use `uv tool install --editable .`.
