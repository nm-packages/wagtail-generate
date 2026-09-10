# Developer guide

See the [README](../README.md) for generator usage. Use UV for Python versions,
environments, dependencies, and command execution. Support the Python version
declared in `.python-version` and `pyproject.toml`.

Create a branch before making changes, using `<work-type>/<short-description>`
(for example, `docs/simplify-documentation`, `feature/new-layout`, or
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

Run all hooks with `uv run pre-commit run --all-files`. Add or update tests for
behavior changes, especially path validation, conflicts, layout selection,
rendered content, and command exit codes. For an editable CLI installation, use
`uv tool install --editable .`.

## Disposable playground

Rebuild a SQLite site from the current generator source, install dependencies,
apply migrations, create an administrator, run checks, and start the server:

```shell
make playground
```

Use `make playground SITE_DIRECTORY=src` to exercise the source-subfolder layout;
use `make playground SITE_DIRECTORY=.` (the default) for code at the project root.
Only `.` and `src` are accepted.

Open <http://127.0.0.1:8000/admin/> and sign in with username `admin` and password
`playground` (email: `admin@example.test`). These credentials are for this
disposable local site only.

Stop the server with Ctrl-C before rebuilding or resetting. Every run replaces
`.playground/`, including its database. To remove it without rebuilding:

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
plans. Layouts should have stable, discoverable names, with their configuration
and templates outside the CLI layer.

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
