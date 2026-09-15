# wagtail-generate

A UV-installable CLI for creating Wagtail CMS projects with UV and Docker
development, SQLite (with PostgreSQL and MySQL options), formatting tools, and
pre-commit hooks.

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
- `--template PATH` supplies a custom local Wagtail project template.

See [Developer guide](docs/development.md) to develop the generator or try its playground.

## Custom user and image models

Interactive generation shows the current user and image model settings and asks
whether to create replacements. Both questions default to **No**. Use
`--custom-user` and `--custom-images` independently to enable them, or
`--no-custom-user` and `--no-custom-images` to skip the corresponding prompts.
Without a terminal, omitted model options are disabled.

```shell
wagtail-generate start mysite --site-name "My Site" --site-directory src \
  --custom-user --custom-images
```

The user option creates `accounts.User`, a minimal `AbstractUser` subclass that
keeps username/password authentication and standard Django/Wagtail administration.
The image option creates `images.CustomImage` and `images.CustomRendition`, without additional
metadata fields. Apps follow the selected source layout; model labels stay the
same. Choose these before adding data: switching user or image models later needs
migration planning and does not automatically transfer existing data.

Django creates initial migrations using the resolved project dependencies during
staged generation. Generation does not apply them; use the normal generated-site
setup commands. The generated README records model settings. A reusable saved
configuration format is deferred.

Custom templates keep their existing models when you choose No. Literal model
settings are displayed when identifiable; computed or ambiguous settings are
reported as undetermined. Choosing Yes rejects existing model settings, conflicting
app paths, or app labels, rather than merging models. Custom model options require
a local template directory and a literal `INSTALLED_APPS` list or tuple.
