# Testing

The ordinary test suite runs with:

```shell
make test
```

It records application coverage using `pytest-cov`. To inspect a local report:

```shell
make coverage
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
make test-distribution
make test-compatibility
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

## Frontend workflow

The normal suite checks generated skill metadata, local documentation links, layout-specific recipe paths, preservation of custom guidance, and deterministic planning without frontend side effects. The distribution test also renders the skill from the installed wheel.

To exercise the actual recipe, install Node/npm and run:

```shell
make test-frontend
```

This opt-in test uses disposable sites outside the checkout. It installs Wagtail and npm dependencies, reads the npm scripts directly from the generated recipe, checks plain CSS without npm setup, performs a locked install and production build, and serves Django-collected assets over HTTP with manifest hashing and `DEBUG=False`. It verifies stylesheet image references, imported Sass partial changes, JavaScript changes, build errors, Ctrl-C cleanup, and failure propagation from either a watcher or the Django command. Process-group checks require POSIX; on Windows the build/static checks run before those lifecycle checks are skipped. This is a local static-serving probe; a site's actual CDN or production server still needs deployment-specific verification.

With Docker running, also execute the recipe's Compose service and launcher in both layouts:

```shell
WAGTAIL_GENERATE_TEST_FRONTEND_DOCKER=1 make test-frontend
```

This pulls a Node image, builds the generated web image, and checks interruption and failure of either service. Only the test's uniquely named Compose projects and disposable volumes are removed. These checks need network access and are opt-in to keep the ordinary suite independent of Node and Docker.

For skill behaviour review, use the generated entry point with these representative requests. Review actual decisions and changes; checking the Markdown alone cannot prove an agent will select or follow the skill correctly.

| Request | Expected behaviour |
| --- | --- |
| "Add Sass and JavaScript bundling; I use local UV." | Use the setup skill and Sass recipe; retain local environment and database setup. |
| "Add a stylesheet and a small script without Node." | Use plain mode and preserve the existing template blocks and assets. |
| "Change the header colour." | Edit the existing styling without starting tooling setup. |
| "We already use Vite; add an entry point." | Inspect and extend Vite, without replacing it with the supplied recipe. |
| "Set up Tailwind." | Honour Tailwind; explain the supplied recipe's scope and consult its official integration guidance. |

The initial recipe was exercised with Node 22.22.2, Sass 1.104.1, esbuild 0.28.2, and concurrently 10.0.5. These are validation evidence, not generator runtime dependencies or a promise that future package releases remain compatible. Re-run recipe checks when changing the instructions or supported tooling.
