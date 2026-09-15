# Development guide

This repository contains `wagtail-generate`, a CLI for creating Wagtail CMS
projects. The README covers running the generator. These guides cover working
on the generator itself.

- [Setup](setup.md) — install dependencies and run the routine checks.
- [Testing](testing.md) — test suites, coverage, and opt-in integration checks.
- [Playground](playground.md) — rebuild and inspect a disposable local site.
- [Architecture](architecture.md) — design boundaries and implementation
  invariants.
- [Releasing](releasing.md) — package artifacts and release checks.

Use UV for Python versions, environments, dependencies, and command execution.
Support the Python version declared in `.python-version` and `pyproject.toml`.

Create a branch before making changes, using `<work-type>/<short-description>`.
Do not work directly on `main`.
