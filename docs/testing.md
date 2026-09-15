# Testing

The ordinary test suite runs with:

```shell
uv run pytest
```

It records application coverage using `pytest-cov`. To inspect a local report:

```shell
uv run pytest --cov=wagtail_generate --cov-report=term-missing
uv run pytest --cov=wagtail_generate --cov-report=html:htmlcov
open htmlcov/index.html
```

Coverage is measured for `src/wagtail_generate/`; the `__main__.py` shim is
excluded. CI enforces the current 95% baseline. Raise the threshold when
meaningful tests increase the baseline instead of excluding reachable code only
to satisfy the threshold.

The following checks are opt-in locally because they build distributions or
resolve and install Wagtail and its development dependencies:

```shell
WAGTAIL_GENERATE_TEST_DISTRIBUTION=1 uv run pytest tests/test_distribution.py
WAGTAIL_GENERATE_TEST_COMPATIBILITY=1 uv run pytest tests/test_wagtail_compatibility.py
```

The distribution test checks the source distribution, wheel, license files, and
package metadata. The compatibility test exercises both source layouts, Django
checks, migrations, model combinations, and a PostgreSQL generated project.

Database-environment tests execute generated Make targets with real UV and
inspect Compose configuration without starting containers:

```shell
uv run pytest tests/test_database_environment.py
```

Compose-specific checks are skipped when Docker Compose is unavailable. Install
Docker Compose to run the complete environment coverage. GitHub Actions runs the
same checks on pushes and pull requests to `main` and also uploads the coverage
report as a workflow artifact.
