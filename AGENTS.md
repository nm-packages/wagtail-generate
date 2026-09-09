# Repository guidance

## Purpose

This repository contains `wagtail-generate`, a UV-installable Python CLI that
creates opinionated Wagtail CMS projects from named codebase layouts.

## Tooling

- Use UV for Python versions, dependency management, virtual environments, and
  command execution.
- Keep application code under `src/wagtail_generate/` and tests under `tests/`.
- Support the Python version declared in `.python-version` and `pyproject.toml`.
- Do not add a runtime dependency when the standard library is sufficient.
- Treat UV as an external prerequisite. Install Wagtail into each generated
  project's environment rather than into `wagtail-generate` itself.

## Architecture

- Keep CLI parsing thin. Put generation and filesystem behavior in independently
  testable modules.
- Represent project options and generated-file plans with typed data structures.
- Make layouts discoverable by stable names and keep layout-specific templates or
  configuration out of the CLI layer.
- Build and validate a complete generation plan before writing to disk.
- Refuse to overwrite existing files unless the user explicitly opts in.
- Ordinary CLI generation must never write inside the source checkout. Keep this
  guard ahead of directory creation and external command execution. The dedicated
  `make playground` workflow may generate only into the checkout’s `.playground/`
  directory; reset must reject symlinks and unrecognized directories.
- Resolve intentionally floating Python and package choices before writing, record
  them in the generation plan and generated lock files, and keep rendered output
  deterministic for those resolved inputs.
- Separate template rendering from optional side effects such as running `uv`,
  Django, Git, or frontend commands.
- Keep generated Docker, Compose, database settings, formatter configuration, and
  `AGENTS.md` guidance consistent with the selected database and source layout.
- Keep generated file content in `src/wagtail_generate/templates/`; Python should
  orchestrate resource loading and rendering rather than embed large file strings.

## Quality checks

Run these before considering a change complete:

```shell
uv run ruff check .
uv run mypy
uv run pytest
```

Add or update tests for behavior changes, especially path validation, conflicts,
layout selection, rendered content, and command exit codes.
