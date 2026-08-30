# wagtail-generate

`wagtail-generate` is a UV-installable command-line tool for creating Wagtail CMS
projects with a chosen, repeatable codebase layout.

The repository currently contains the tool foundation. Layout definitions and the
project generation workflow will be added as their requirements are established.

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
  --directory path/to/project \
  --site-directory site
```

Use `--site-directory .` to generate the Wagtail code directly in the project root.

Without a site subfolder, the command runs the equivalent of:

```shell
uv init --bare --no-workspace
uv add wagtail
uv run wagtail start mysite .
```

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

## Planned shape

The generator will keep these concerns separate:

- CLI argument parsing and user interaction
- typed project configuration
- named layout discovery and validation
- filesystem planning and conflict detection
- template rendering
- optional post-generation commands

Generated project files should be treated as a plan before they are written. This
makes dry runs, useful conflict errors, and deterministic tests straightforward.
