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

The tool asks where to generate the site:

```text
Generate the site in a subfolder? [y/N]:
```

Press Enter to use the current directory. Choosing yes asks for a subfolder name;
press Enter again to use `mysite` as that name. The selected directory contains
the UV project, its virtual environment, and the generated Wagtail site.

For scripts and other non-interactive use, select the directory explicitly:

```shell
uv run wagtail-generate start mysite --directory path/to/destination
```

The command runs the equivalent of:

```shell
uv init --bare --no-workspace
uv add wagtail
uv run wagtail start mysite .
```

When running the tool from this repository, generation into the repository root
or any directory below it is refused. This prevents generated sites from being
written over the tool's own source tree.

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
