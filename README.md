# wagtail-generate

A UV-installable CLI for creating Wagtail CMS projects with a repeatable codebase
layout. The standard layout includes UV and Docker development, SQLite (with
PostgreSQL and MySQL options), formatting tools, and pre-commit hooks.

## Quick start

With UV installed, install from a local checkout (requires Python 3.14 or later):

```shell
uv tool install /path/to/wagtail-generate
```

Run from outside the generator checkout:

```shell
wagtail-generate start mysite --site-name "My Site" --site-directory .
cd my_site
make dev
```

Make is required for `make dev`. Open <http://localhost:8000>. Follow the generated
project's `README.md` for administrator setup, Docker, databases, and checks.
Each site has its own Python environment and lockfile.

## Options

Run `wagtail-generate start --help` for all flags and defaults. Running
`wagtail-generate start mysite` prompts for a site name and source location.

- `--site-name "My Site"` sets the readable name and default folder (`my_site`).
  The positional name (`mysite`) determines the Python package.
  Explicit site names preserve capitalization, punctuation, Unicode, and internal
  spaces; surrounding whitespace is trimmed. Names must be nonempty after
  trimming and contain no control characters, such as embedded tabs or newlines.
  At the prompt, press Enter to accept the suggestion derived from the package
  name. Invalid input prompts again; invalid flag values exit with an error.
- `--directory PATH` overrides the destination, which must be missing or empty
  and outside the generator checkout.
- `--site-directory .` puts Wagtail code at the root; `--site-directory src`
  uses a source subfolder. UV files and `manage.py` remain at the root.
- `--database postgresql` or `--database mysql` selects a server database;
  SQLite is the default. Server database development uses Docker Compose.
- `--layout standard` selects the current generator layout (the default).
  `--template PATH` supplies a custom local Wagtail project template.

See [Developer guide](docs/development.md) to develop the generator or try its playground.
