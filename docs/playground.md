# Disposable playground

The playground rebuilds a SQLite Wagtail site from the current generator source,
installs its dependencies, applies migrations, creates an administrator, runs
checks, and starts the server:

```shell
make playground
```

It uses the fixed `playground` project with Wagtail in `src/`, the starter
homepage, and custom user, image, and rendition models. The site is generated in
`.playground/`, which is ignored by Git. `make help` lists the available
playground commands.

Open <http://127.0.0.1:8000/admin/> and use the disposable credentials shown by
the command. Stop the server with Ctrl-C before rebuilding or resetting.

Every rebuild replaces `.playground/`, including its SQLite database. To remove
it without rebuilding:

```shell
make playground-reset
```

The reset command rejects symlinks and directories without the playground marker.
Ordinary generation must target a directory outside this checkout; only this
dedicated workflow may generate inside `.playground/`.

For focused debugging, the underlying runner accepts generation options:

```shell
uv run python -m wagtail_generate.playground --help
```

The Make workflow deliberately supplies its own fixed configuration. Invalid
options and template paths are checked before an existing playground is reset.
