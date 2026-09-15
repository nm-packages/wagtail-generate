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

### Starter homepage

By default, generation preserves the homepage supplied by Wagtail or your custom
project template. During interactive generation, you are offered the choice:

```text
Replace the template homepage with a simple styled starter? [y/N]:
```

Answer yes for a responsive homepage using semantic HTML and plain CSS, or press
Enter to preserve the existing homepage. For scripts, pass `--starter-homepage`
or `--no-starter-homepage` to select the behaviour without a prompt. When input
is not a terminal, omission preserves the existing homepage. For example:

```shell
wagtail-generate start example --site-name "Example" --site-directory src --starter-homepage
```

This option works independently of custom models and requires no Node, frontend
workflow, or website preset. Both root and source-subfolder layouts are supported.
The homepage template lives in `home/templates/home/home_page.html`, with styles
in `home/static/home/css/starter-homepage.css`, under the selected source directory.
It extends the project's `base.html`, preserving the generated document metadata,
global assets, Wagtail user bar, and any existing `content` and `extra_css` block
behaviour. Customize the page through those blocks or extend the stylesheet with a
future frontend workflow or website preset. Custom base templates must expose the
`content` and `extra_css` blocks used by the starter template.

Custom templates are preserved unless replacement is explicitly requested. For
replacement, supply an inspectable template directory containing those conventional
homepage template and model paths. `home/models.py` must define `HomePage(Page)`
without custom `serve`, `get_template`, or `get_context` methods, and any explicit
`template` or `ajax_template` must be `home/home_page.html`. Templates that use
another homepage structure or an archive are rejected with a clear error. Keep
custom URL routing and template-loader configuration compatible with this path.
Replacement also removes the default `home/templates/home/welcome_page.html`
and `home/static/css/welcome_page.css` files when present, including in custom
templates. Other assets, shared templates, model fields, and migrations are retained.
