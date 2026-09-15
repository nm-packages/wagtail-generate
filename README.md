# wagtail-generate

A UV-installable CLI for creating opinionated Wagtail CMS projects with UV and
Docker development.

## Quick start

Until a package release is published, install the latest code from the GitHub
repository's `main` branch with UV (Python 3.14 or later):

```shell
uv tool install "git+https://github.com/nm-packages/wagtail-generate.git@main"
```

Run the generator from outside its checkout:

```shell
wagtail-generate start mysite --site-name "My Site" --site-directory src
cd my_site
make dev
```

Open <http://localhost:8000>. The generated project's `README.md` explains
administrator setup, Docker, databases, and quality checks.

## Options

Run `wagtail-generate start --help` for the complete option list and defaults.
Running `wagtail-generate start mysite` prompts for a site name and source
location.

- `--site-name "My Site"` sets the display name and default directory name.
- `--directory PATH` sets the destination. It must be missing or empty and
  outside this checkout.
- `--site-directory .` puts Wagtail code at the project root; `--site-directory
  src` puts it in a source subfolder.
- `--database postgresql` or `--database mysql` selects a server database.
  SQLite is the default.
- `--custom-user` and `--custom-images` enable the optional user and image
  model apps. Their `--no-...` forms disable the corresponding interactive
  prompts.
- `--starter-homepage` replaces the template homepage with a simple styled
  homepage. `--no-starter-homepage` preserves the template homepage.

Custom model choices should be made before adding data. Changing them later
requires migration planning. Custom model and homepage options are independent.

## Developer documentation

This repository's developer documentation is split by topic:

- [Development index](docs/development.md) — where to find each guide.
- [Setup](docs/setup.md) — environment setup and routine checks.
- [Testing](docs/testing.md) — test suites, coverage, and opt-in checks.
- [Playground](docs/playground.md) — the disposable generated site.
- [Architecture](docs/architecture.md) — design boundaries and invariants.
- [Releasing](docs/releasing.md) — package artifact and release checks.
