# Developer guide

See the [README](../README.md) for generator usage. Use UV for Python versions,
environments, dependencies, and command execution. Support the Python version
declared in `.python-version` and `pyproject.toml`.

Create a branch before making changes, using `<work-type>/<short-description>`
(for example, `docs/simplify-documentation`, `feature/new-tooling`, or
`testing/path-validation`). Do not work directly on `main`.

## Setup and checks

```shell
uv sync
uv run pre-commit install
uv run wagtail-generate --help
```

Before considering a change complete, run:

```shell
uv run ruff check .
uv run mypy
uv run pytest
```

The test suite records application coverage using `pytest-cov`. To inspect the
current report locally, run:

```shell
uv run pytest --cov=wagtail_generate --cov-report=term-missing
uv run pytest --cov=wagtail_generate --cov-report=html:htmlcov
open htmlcov/index.html
```

Coverage is measured for `src/wagtail_generate/`; the thin `__main__.py`
module shim is excluded. CI enforces the current 95% baseline and uploads the
XML report as a workflow artifact. Raise the threshold when meaningful tests
increase the baseline, rather than excluding reachable code solely to satisfy
the threshold.

Pull requests and pushes to `main` run the same checks in GitHub Actions. The
workflow also builds the source distribution and wheel and runs the installed
distribution smoke test. The smoke test is opt-in locally because it creates an
isolated environment and may need network access:

```shell
WAGTAIL_GENERATE_TEST_DISTRIBUTION=1 uv run pytest tests/test_distribution.py
```

The real-Wagtail compatibility smoke test exercises both supported source
layouts against the installed Wagtail generator, then runs Django checks and
migrations in each generated project. It is opt-in locally because it resolves
and installs Wagtail and its development dependencies for multiple generated sites.
It also generates a PostgreSQL site and verifies the binary driver requirement,
lockfile entries, driver import, and Django system checks without a running database:

```shell
WAGTAIL_GENERATE_TEST_COMPATIBILITY=1 uv run pytest tests/test_wagtail_compatibility.py
```

Run all hooks with `uv run pre-commit run --all-files`. The pytest hook runs the
full suite on every commit, including template-only and configuration-only
changes. Verify a specific changed-file selection with
`uv run pre-commit run pytest --files <path>`.

Add or update tests for
behavior changes, especially path validation, conflicts, source-directory selection,
rendered content, and command exit codes. For an editable CLI installation, use
`uv tool install --editable .`.

The database-environment tests execute generated Make targets with real UV and
inspect Compose configuration without starting containers. Compose checks skip
when Docker Compose is unavailable; install it to run the full environment
coverage with `uv run pytest tests/test_database_environment.py`.

## Release artifact checks

The project uses the MIT license in `LICENSE`. Release archives must include its
full text and copyright notice, with matching package metadata.

Run the artifact check with:

```shell
WAGTAIL_GENERATE_TEST_DISTRIBUTION=1 uv run pytest tests/test_distribution.py
```

This builds a source distribution in a temporary directory, builds a wheel from
that source archive, and verifies both license copies and metadata. It may need
network access to install the build backend, so the ordinary test suite skips it.

## Disposable playground

Rebuild a SQLite site from the current generator source, install dependencies,
apply migrations, create an administrator, run checks, and start the server:

```shell
make playground
```

This single command generates one site with:

- SQLite as the database.
- Wagtail code in `src/`.
- The starter homepage.
- Custom user, image, and rendition models.

The project is named `playground`, with display name `Developer Playground`, and
uses the standard Wagtail template. No arguments or Make variables are needed.
`make help` lists the playground and reset commands.

The underlying Python runner still accepts generation options for focused debugging;
run `uv run python -m wagtail_generate.playground --help` for its option reference.
It shares option definitions with the main CLI. The Make workflow always passes the
configuration above; `PLAYGROUND_ARGS` and the former Make configuration variables
are no longer used. The destination is always `.playground/`.
Invalid options and template paths are rejected before resetting the existing site,
and custom templates must be outside `.playground/`.

Open <http://127.0.0.1:8000/admin/> and sign in with username `admin` and password
`playground` (email: `admin@example.test`). These credentials are for this
disposable local site only.

Stop the server with Ctrl-C before rebuilding or resetting. Every run replaces
`.playground/`, including its SQLite database. To remove it without rebuilding:

```shell
make playground-reset
```

The playground is ignored by Git. Reset rejects symlinks and directories without
its marker. Ordinary generation must target a directory outside this checkout;
only this dedicated workflow may generate inside `.playground/`.

## Source files

Application code lives in `src/wagtail_generate/` and tests in `tests/`.
Generated file content lives in `src/wagtail_generate/templates/`: `.jinja` files
are rendered with project values; files in `templates/static/` are copied.
The generated README is the home for instructions on working in a generated site.
Generated agent guidance defaults to backend commands in the Compose `web`
service, with local UV commands when the user chooses that workflow. Keep its
command examples and the generated README aligned with the actual tooling.
Keep the generated `AGENTS.md` concise: project context, working rules, and links
to task-specific guidance in `docs/agent-instructions/`. Environment commands,
backend conventions, and testing/completion checks live in those linked guides.
Render all guides in the generation plan and preserve existing guidance supplied
by custom templates.
Generated sites use Django's test runner, Ruff, and djangofmt; their completion
checks also include lockfile validation, Django system checks, and detection of
missing migrations. The generator's pytest and mypy setup is separate.

## Design conventions

Keep CLI parsing thin and put generation and filesystem behavior in independently
testable modules. Use typed structures for project options and generated-file
plans. Keep generated-project configuration and templates outside the CLI layer.
The generator uses one tooling and template set; `--site-directory` selects where
Wagtail source lives, while `--template` supplies a custom Wagtail start template.

Build and validate the full generation plan before writing to disk. Refuse to
overwrite existing files without an explicit opt-in. Check the source-checkout
restriction before creating directories or running external commands.

Resolve floating Python and package choices before writing final output, record
them in the generation plan and generated lock files, and render deterministically
for those resolved inputs. Keep template rendering separate from side effects
such as running UV, Django, Git, or frontend commands.

Keep generated Docker, Compose, database settings, formatter configuration, and
project guidance consistent with the selected database and source layout. Load
generated content from template resources rather than embedding large strings in
Python.

Prefer the standard library over new runtime dependencies. Treat UV as an external
prerequisite and install Wagtail into each generated project's environment.

## Module responsibilities

| Module | Responsibility |
| --- | --- |
| `cli.py` | Parse user-facing options and enforce the ordinary generation boundary. |
| `planning.py` | Build typed project, dependency, command, and rendered-file plans. |
| `commands.py` | Run external commands and provide consistent operational errors. |
| `generation.py` | Resolve versions, execute staged plans, configure projects, and publish them. |
| `transformations.py` | Adapt Wagtail's generated package for source-subfolder layouts. |
| `rendering.py` | Load, render, validate, and write packaged templates. |
| `developer_tools.py` | Plan and apply database, Docker, formatter, and development tooling files. |
| `playground.py` | Rebuild and serve the disposable in-checkout developer site. |
| `safety.py` | Validate source packages, checkout boundaries, and permitted destinations. |

## External commands

`commands.py` owns subprocess execution and translates launch failures and nonzero
exit codes into `GenerationError`. Call `run_command()` with a stage and a
human-readable description. Pass arguments as a sequence; commands never use a
shell. Output streams to the terminal by default. Use `capture_output=True` only
when parsing a command's response, such as UV's Python catalog or dependency list.
Captured stderr is included in failure messages.

`planning.py` owns project options, typed plans, command construction, and rendered
documentation. `build_generation_plan()` assembles these with the developer-tooling
plan without running commands or writing the destination. Its helpers group setup,
Wagtail start, formatting, and documentation planning by purpose.

`generation.py` validates the generation boundary, resolves Python and dependencies,
and passes the completed plan to `execute_generation_plan()`. That function owns
staging, cleanup, publication, and execution error reporting. Inside staging,
`_execute_generation_plan_in_directory()` reads in execution order:

1. `_prepare_environment()` creates a relocatable environment and installs dependencies.
2. `_generate_wagtail_site()` creates the selected source directory and runs Wagtail.
3. `_adapt_project_structure()` arranges the generated files and locates settings.
4. `_configure_project()` applies optional model apps, the site name, database,
   tooling, and documentation.
5. Planned model commands create initial migrations when custom models are enabled.
6. `_format_project()` runs the planned template and Python formatters.

Structure adaptation stops generation when the expected package or template files
are missing, or flattening would overwrite a generated file. The focused
transformations in `transformations.py` move the package, create package markers,
rewrite imports, and adjust settings and app configuration. `planning.py` also
keeps runtime and development dependencies as separate typed groups, so command
construction and UV resolution do not depend on tuple positions.

Import rewriting uses Python syntax nodes to preserve relative imports and avoid
rewriting import-like text in comments or strings. Ordinary dotted imports must
load the relocated submodule while binding the original package name; these use
separate imports for loading the submodule and binding the package. Loader imports
use collision-free private aliases and `noqa: F401` so Ruff retains their side
effects when fixing imports. Runtime regression tests cover aliases, multiple
imports, function scope, and nested source layouts.

Only a fully successful sequence is published; the destination is checked again
before publication. Temporary staging is cleaned up on failure.

A failed command raises immediately, so later steps and
publication do not run. The execution boundary reports the error and preserves
the child exit code; launch errors and planning failures return 2. Wagtail stays
in the generated project's environment rather than becoming a generator runtime
dependency.

`playground.py` is the disposable in-checkout workflow. `parse_arguments()` only
parses and validates generation choices (using shared CLI definitions), then
`main()` resets the recognized directory,
calls the generator, and, unless `--generate-only` is selected, runs explicit
`prepare_playground()`,
`create_playground_administrator()`, `check_playground()`, and `serve_playground()`
steps. Each step receives its command and environment directly; command names are
not inspected to decide whether to add credentials or print server information.
The marker is written only after generation succeeds, and reset refuses symlinks or
unrecognized directories.

## Optional model apps

`model_options.py` inspects custom-template model settings without importing them,
plans packaged `accounts`/`images` app templates, and rejects conflicting model
settings, app paths and labels. `ProjectOptions` stores independent boolean model
choices; both default to false. Interactive prompts belong in `cli.py`; direct
Python callers never prompt.

The generation plan includes model files and a Django `makemigrations --noinput
--no-header` command for selected apps. After structure adaptation, configuration
validates conflicts before writing apps or model settings. Migrations are created
in staging against resolved dependencies before formatting and publication. They
are not applied during ordinary generation. Framework-generated migration content
is owned by Django; application templates remain under `templates/models/`.

Real-Wagtail compatibility checks cover four model combinations in each layout,
including migration drift and generated-site tests. Model settings and extension
guidance are recorded in the generated README. Saved configuration is deferred.

### Starter homepage option

`ProjectOptions.starter_homepage` defaults to false. Interactive CLI generation
offers a default-no homepage replacement prompt. `--starter-homepage` and
`--no-starter-homepage` bypass the prompt; non-interactive omission preserves the
existing homepage. `homepage.py` validates the conventional home app and plans packaged HTML
and CSS in `GenerationPlan.homepage_files`. The homepage extends the generated
`base.html`, placing its markup in `content` and its stylesheet in `extra_css`
while preserving `block.super`. This retains the base template's metadata, global
assets, preview support, and Wagtail user bar. Custom base templates must expose
these blocks. Execution revalidates the staged Wagtail
output before writing them. `GenerationPlan.homepage_removals` lists the two
welcome-screen files to remove: `home/templates/home/welcome_page.html` and
`home/static/css/welcome_page.css`. Cleanup uses explicit paths, tolerates missing
files, and rejects symlinks and unexpected directories. Default generation leaves custom homepage content
untouched. Unsupported custom homepage structures fail without publishing a
partial project. Templates live under `templates/homepage/`; keep future frontend
workflows and website presets able to reuse or extend these files independently.
