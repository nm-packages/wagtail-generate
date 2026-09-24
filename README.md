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

Generated projects also include a `wagtail-frontend-setup` agent skill with guides for plain CSS/JavaScript and Sass with esbuild. Use it when you are ready to choose and implement the site's frontend tooling. Generation adds no Node requirement or frontend dependencies; the site developer owns the chosen stack and the generated guidance.

## Options

Run `wagtail-generate start --help` for the complete option list and defaults.
Running `wagtail-generate start mysite` prompts for a site name and source location. In a terminal, it also asks whether to create custom user and image models and use the starter homepage. Each optional feature defaults to No.

- `--site-name "My Site"` sets the display name and default directory name.
- `--directory PATH` sets the destination. It must be missing or empty and
  outside this checkout.
- `--site-directory .` puts Wagtail code at the project root; `--site-directory
  src` puts it in a source subfolder.
- `--database postgresql` or `--database mysql` selects a server database.
  SQLite is the default.
- `--custom-user` and `--custom-images` enable the optional user and image
  model apps.
- `--starter-homepage` replaces the template homepage with a simple styled
  homepage.

These three features are opt-in: answer Yes at the prompt or pass the corresponding flag to enable them. Passing a flag skips its prompt; otherwise, answer No or press Enter to leave the feature disabled. Non-interactive runs disable omitted features without prompting.

Custom model choices should be made before adding data. Changing them later
requires migration planning. Custom model and homepage options are independent.

## Developer documentation

This repository's developer documentation is split by topic:

- [Contributing](docs/contributing.md) — contributor guidance and links to each guide.
- [Setup](docs/setup.md) — environment setup and routine checks.
- [Testing](docs/testing.md) — test suites, coverage, and opt-in checks.
- [Playground](docs/playground.md) — the disposable generated site.
- [Architecture](docs/architecture.md) — design boundaries and invariants.
- [Releasing](docs/releasing.md) — package artifact and release checks.
