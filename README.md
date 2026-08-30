# wagtail-generate

`wagtail-generate` is a UV-installable command-line tool for creating Wagtail CMS
projects with a chosen, repeatable codebase layout.

Generated projects are ready for local UV or Docker development, with a selectable
PostgreSQL or MySQL database and a consistent formatting and pre-commit setup.

## Development

Install the project and its development tools:

```shell
uv sync
```

Run the CLI:

```shell
uv run wagtail-generate --help
uv run wagtail-generate --version
```

Initialize the current directory as a UV project, install the latest resolvable
Wagtail release, and generate the site into it:

```shell
uv run wagtail-generate start mysite
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
`WAGTAIL_SITE_NAME` and the generated `AGENTS.md`; it does not affect folder or
Python package names.

The local Docker database is also selected independently. PostgreSQL is the
default, with MySQL available as an alternative:

```text
Local Docker database [PostgreSQL/mysql]:
```

For non-interactive generation, use `--database postgresql` or
`--database mysql`.

PostgreSQL is recommended for full Django feature support. MySQL works for local
development, but Django reports that MySQL cannot enforce Wagtail's conditional
`WorkflowState` uniqueness constraint.

The tool asks where to generate the site:

```text
Generate the site in a subfolder? [y/N]:
```

Press Enter to use the current directory. Choosing yes asks for a subfolder name;
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

Generated projects include a UV-native multi-stage `Dockerfile`, `compose.yaml`,
database health checks and persistent storage, `.env.example`, Ruff, djangofmt,
and pre-commit configuration. Start local development with:

```shell
docker compose up --build
```

Copy `.env.example` to `.env` to customize credentials or the forwarded web and
database ports. Compose waits for the database health check, applies migrations,
and then starts Wagtail on `http://localhost:8000` by default.

Run the generated checks with:

```shell
uv run ruff check .
uv run ruff format --check .
uv run djangofmt .
```

The generated README includes the initial `git init`, `git add`, and pre-commit
installation sequence. Pre-commit only considers files known to Git, including
when `--all-files` is used.

Wagtail normally nests its Django configuration package inside the destination
(for example, `src/src/settings/`). When a site subfolder is selected, the tool
flattens that package by one level (`src/settings/`) and updates the generated
settings, URL, WSGI, `home`, and `search` module paths accordingly. This keeps the
root-level `manage.py` imports valid.

Select a different UV project root with `--directory`:

```shell
uv run wagtail-generate start mysite --directory path/to/destination
```

Specify the Wagtail code location non-interactively with `--site-directory`:

```shell
uv run wagtail-generate start mysite \
  --site-name "My Site" \
  --database postgresql \
  --directory path/to/project \
  --site-directory site
```

Use `--site-directory .` to generate the Wagtail code directly in the project root.

Without a site subfolder, the command runs the equivalent of:

```shell
uv init --bare --no-workspace
uv python pin 3.12
uv add wagtail gunicorn psycopg[binary]
uv add --dev ruff djangofmt pre-commit
uv run wagtail start mysite .
```

The database driver is `psycopg[binary]` for PostgreSQL or `mysqlclient` for
MySQL.

When running the tool from this repository, generation into the repository root
or any directory below it is refused. This prevents generated sites from being
written over the tool's own source tree.

The selected project root must not contain any files or directories, including
hidden entries. A missing directory is created automatically; an existing empty
directory is accepted.

Run the checks:

```shell
uv run ruff check .
uv run mypy
uv run pytest
```

Install it as a local UV tool while developing:

```shell
uv tool install --editable .
```
