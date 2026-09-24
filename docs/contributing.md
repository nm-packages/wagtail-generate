# Contributing to wagtail-generate

This guide is for developers contributing to `wagtail-generate`, a CLI for creating Wagtail CMS projects. The [README](../README.md) covers using the generator. The guides below cover setting up the repository, making changes, and validating contributions.

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

When changing a generated agent skill, keep its packaged instructions and linked references consistent with the generated project's commands and layouts. Test executable recipes in disposable generated projects using the [frontend workflow checks](testing.md#frontend-workflow). Keep developer-facing setup instructions available without requiring an AI agent.
