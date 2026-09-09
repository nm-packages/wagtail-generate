# wagtail-generate

`wagtail-generate` is a UV-installable command-line tool for creating Wagtail CMS
projects with a chosen, repeatable codebase layout.

Generated projects are ready for local UV or Docker development, using SQLite by
default with PostgreSQL and MySQL available, plus a consistent formatting and
pre-commit setup.

## Development

Install the project and its development tools:

```shell
uv sync
uv run pre-commit install
```

Run every hook manually with `uv run pre-commit run --all-files`.

Exercise the current generator source end to end in a disposable local site:

```shell
make playground
```

By default, Wagtail code is generated at the project root. To exercise generation
in an alternate source folder instead:

```shell
make playground SITE_DIRECTORY=src
```

This places Wagtail code in `.playground/src/`, while `manage.py`, the UV project,
virtual environment, and lockfile remain at `.playground/`. Both modes run the
same migrations, administrator creation, checks, and development server. Use
`make playground SITE_DIRECTORY=.` (or simply `make playground`) to switch back.
Stop the server with Ctrl-C before switching; each run replaces the previous site.
Only `.` and `src` are accepted playground options.

Every run deletes the previous recognized `.playground/` directory, generates a
fresh standard-layout SQLite project, installs its dependencies, applies
migrations, creates a local administrator, runs Django system checks, and starts the development server at
http://127.0.0.1:8000. Stop it with Ctrl-C before rebuilding or resetting.
The site has its own virtual environment and lockfile. Its files and database are
ignored by Git and are discarded on the next run.

To remove the site without starting another:

```shell
make playground-reset
```

This developer workflow is the sole exception to the source-checkout destination
guard. It rejects a symlink at `.playground/` and will not delete an existing
folder without its playground marker. Ordinary `start` commands still refuse
all destinations inside this repository.

Wagtail admin is ready at http://127.0.0.1:8000/admin/ after startup:

- Username: `admin`
- Password: `playground`
- Email: `admin@example.test`

These fixed credentials are for the disposable local playground. The account is
recreated automatically on every rebuild, and the login details are printed
before the server starts.

Run the CLI:

```shell
uv run wagtail-generate --help
uv run wagtail-generate --version
```

Create a project folder in the current directory, initialize it as a UV project,
install the latest resolvable Wagtail release, and generate the site into it:

```shell
uv run wagtail-generate start mysite
```

The stable `standard` layout is selected by default. It provides the UV, Docker,
database, formatting, and project-guidance setup described below. Select it
explicitly when scripts should record the chosen layout:

```shell
uv run wagtail-generate start mysite --layout standard
```

Human-readable names are accepted and converted to valid lowercase Python package
names. For example, `start "This is my site"` uses `this_is_my_site` for Wagtail's
project package and as the default site subfolder.

The human-facing Wagtail site name is requested separately and defaults to a
title-cased version of the project name:

```text
Site name [This Is My Site]:
```

It can also be supplied non-interactively with `--site-name`. This value populates
`WAGTAIL_SITE_NAME` and the generated `AGENTS.md`. Unless `--directory` is supplied,
it also determines the normalized project folder: `My Site` creates `./my_site`.
It does not affect the Python package name.

SQLite is used by default, so a generated site can run locally without a separate
database server. Select PostgreSQL or MySQL explicitly when the project needs a
server database:

```shell
uv run wagtail-generate start mysite --database postgresql
uv run wagtail-generate start mysite --database mysql
```

PostgreSQL is recommended for full Django feature support. MySQL works for local
development, but Django reports that MySQL cannot enforce Wagtail's conditional
`WorkflowState` uniqueness constraint.

The tool asks where to generate the site:

```text
Generate the site in a subfolder? [y/N]:
```

Press Enter to put the Wagtail code directly in the newly created project root.
Choosing yes asks for a source subfolder name;
press Enter again to use `mysite` as that name. The UV project, virtual environment,
and lockfile always remain in the project root. Only Wagtail's generated code is
placed in the optional subfolder, except for these project-root files:

- `.dockerignore`
- `Dockerfile`
- `manage.py`

The tool refuses to overwrite any of these files if they already exist at the
project root.

The generated `requirements.txt` is removed because UV manages dependencies
through `pyproject.toml` and `uv.lock`.

A customized `AGENTS.md` is written at the project root. It records the readable
site name, Python package, source directory, settings module, template choice, UV
commands, and development guidance for the generated layout.

Generated projects include a UV-native development `Dockerfile`, `compose.yaml`,
`.env.example`, Ruff, djangofmt, pre-commit configuration, and a Makefile.
PostgreSQL and MySQL projects also include database health checks and persistent
storage. At generation time, UV's download catalog selects the newest stable
CPython release line and pins its major/minor version in the project. Patch
releases remain upgradable within that line. Install the locked dependencies,
apply migrations, and run Wagtail locally with:

```shell
make dev
```

Run `make help` to list the other development commands. To build and run the
complete environment in Docker instead, use:

```shell
make docker
```

The Dockerfile uses the selected major/minor image, such as `python:3.14-slim`,
and `make docker` builds with `--pull`. This fetches current patch releases and
the current slim Debian base without moving the generated project to a newer
Python feature release.

Copy `.env.example` to `.env` to customize the forwarded web port and, for a
server database, its credentials and forwarded port. Compose applies migrations
and then starts Wagtail on `http://localhost:8000` by default; PostgreSQL and
MySQL projects first wait for their database health check.

Run the generated checks with:

```shell
uv run ruff check .
uv run ruff format --check .
uv run python scripts/check_django_templates.py
```

Format Django templates with `uv run djangofmt .` when the template check reports
changes.

The generated README includes the initial `git init`, `git add`, and pre-commit
installation sequence. Pre-commit only considers files known to Git, including
when `--all-files` is used.

Wagtail normally nests its Django configuration package inside the destination
(for example, `src/src/settings/`). When a site subfolder is selected, the tool
flattens that package by one level (`src/settings/`) and updates the generated
settings, URL, WSGI, `home`, and `search` module paths accordingly. This keeps the
root-level `manage.py` imports valid.

Override the automatically created site-name project folder with `--directory`:

```shell
uv run wagtail-generate start mysite --directory path/to/destination
```

Specify the Wagtail code location non-interactively with `--site-directory`:

```shell
uv run wagtail-generate start mysite \
  --site-name "My Site" \
  --database postgresql \
  --directory path/to/project \
  --site-directory src
```

Use `--site-directory .` to generate the Wagtail code directly in the project root.
The top-level source package must not conflict with a Python standard-library
module such as `site`, `email`, or `json`. Use a name such as `src` for the source
subfolder. When generating directly in the root, this restriction applies to the
project package name.

Custom Wagtail project templates can be supplied as a file or directory. Relative
template paths are resolved from the directory where `wagtail-generate` is run:

```shell
uv run wagtail-generate start mysite --template templates/custom
```

Without a site subfolder, the command runs the equivalent of:

```shell
uvx uv@0.12.7 python list --only-downloads --output-format json
uvx uv@0.12.7 init --bare --no-workspace --python <latest-stable-major.minor>
uvx uv@0.12.7 python pin <latest-stable-major.minor>
uvx uv@0.12.7 venv --relocatable --python <latest-stable-major.minor>
uvx uv@0.12.7 add wagtail
uvx uv@0.12.7 add --dev ruff djangofmt pre-commit
uvx uv@0.12.7 run wagtail start mysite .
```

The generator pins its UV command version to match the generated Dockerfile. The
selected Python line and resolved dependencies are then recorded in
`.python-version` and `uv.lock`, making the completed project repeatable.
The virtual environment is created as relocatable so its command-line tools
continue to work when the completed project moves from staging to its destination.

SQLite needs no additional database driver. The driver is `psycopg[binary]` for
PostgreSQL or `mysqlclient` for MySQL.

When running the ordinary `start` command from this repository, generation into
the repository root or any directory below it is refused. This prevents generated sites from being
written over the tool's own source tree.

The destination project folder must not contain any files or directories,
including hidden entries. A missing folder is created automatically; an existing
empty folder is accepted. Files elsewhere in the current directory do not prevent
generation because they are outside the new project folder.

Run the checks:

```shell
uv run ruff check .
uv run mypy
uv run pytest
uv run pre-commit run --all-files
```

Install it as a local UV tool while developing:

```shell
uv tool install --editable .
```

## Generated file templates

Generated file content lives under `src/wagtail_generate/templates/`. Files ending
in `.jinja` are rendered with project values; files under `templates/static/` are
copied unchanged. The renderer uses strict undefined values, so missing template
context fails immediately rather than leaving an incomplete generated file.

Templates are loaded with `importlib.resources` and explicitly included in the
built wheel, keeping the same behavior when the command runs through `uvx`.
