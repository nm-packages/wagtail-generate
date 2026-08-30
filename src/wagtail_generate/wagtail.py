"""Create a UV environment and run Wagtail's project-generation command."""

import json
import re
import subprocess
import sys
from pathlib import Path

from wagtail_generate.developer_tools import (
    TARGET_PYTHON_VERSION,
    configure_database,
    database_driver,
    write_developer_tooling,
)

ROOT_FILES = (".dockerignore", "Dockerfile", "manage.py")


def run_wagtail_start(
    project_name: str,
    site_name: str | None = None,
    database: str = "postgresql",
    project_root: Path | None = None,
    site_subfolder: Path | None = None,
    template: Path | None = None,
) -> int:
    """Initialize a UV project, install Wagtail, and generate into that project."""
    project_directory = project_root or Path.cwd()

    if site_subfolder is not None:
        conflicts = [
            filename
            for filename in ROOT_FILES
            if (project_directory / filename).exists()
        ]
        if conflicts:
            print(
                "error: refusing to overwrite project-root file(s): "
                + ", ".join(conflicts),
                file=sys.stderr,
            )
            return 2

    commands = [
        [
            "uv",
            "init",
            "--bare",
            "--no-workspace",
            "--python",
            TARGET_PYTHON_VERSION,
            "--name",
            project_name,
        ],
        ["uv", "python", "pin", TARGET_PYTHON_VERSION],
        ["uv", "add", "wagtail", "gunicorn", database_driver(database)],
        ["uv", "add", "--dev", "ruff", "djangofmt", "pre-commit"],
    ]
    for command in commands:
        result = subprocess.run(command, cwd=project_directory, check=False)
        if result.returncode != 0:
            return result.returncode

    wagtail_destination = "."
    if site_subfolder is not None:
        (project_directory / site_subfolder).mkdir(parents=True, exist_ok=True)
        wagtail_destination = str(site_subfolder)

    command = [
        "uv",
        "run",
        "wagtail",
        "start",
        project_name,
        wagtail_destination,
    ]
    if template is not None:
        command.append(f"--template={template}")

    result = subprocess.run(
        command,
        cwd=project_directory,
        check=False,
    )
    if result.returncode != 0:
        return result.returncode

    if site_subfolder is not None:
        generated_directory = project_directory / site_subfolder
        if not _flatten_project_package(
            generated_directory,
            project_name,
            ".".join(site_subfolder.parts),
        ):
            return 2

        _set_wagtail_site_name(
            generated_directory / "settings" / "base.py",
            site_name or project_name.replace("_", " "),
        )
        (generated_directory / "requirements.txt").unlink(missing_ok=True)
        (generated_directory / "README.md").unlink(missing_ok=True)
        for filename in ROOT_FILES:
            source = generated_directory / filename
            if source.exists():
                source.replace(project_directory / filename)
        settings_file = generated_directory / "settings" / "base.py"
        source_directory = str(site_subfolder)
        settings_module = f"{'.'.join(site_subfolder.parts)}.settings"
    else:
        settings_file = project_directory / project_name / "settings" / "base.py"
        _set_wagtail_site_name(
            settings_file, site_name or project_name.replace("_", " ")
        )
        (project_directory / "requirements.txt").unlink(missing_ok=True)
        source_directory = "."
        settings_module = f"{project_name}.settings"

    configure_database(settings_file, database, project_name)
    write_developer_tooling(
        project_directory=project_directory,
        project_name=project_name,
        settings_module=settings_module,
        database=database,
    )

    _write_agents_file(
        project_directory=project_directory,
        project_name=project_name,
        site_name=site_name or project_name.replace("_", " ").title(),
        site_subfolder=site_subfolder,
        database=database,
        template=template,
    )
    _write_readme_file(
        project_directory=project_directory,
        project_name=project_name,
        site_name=site_name or project_name.replace("_", " ").title(),
        site_subfolder=site_subfolder,
        database=database,
    )

    format_result = subprocess.run(
        ["uv", "run", "djangofmt", source_directory],
        cwd=project_directory,
        check=False,
    )
    if format_result.returncode != 0:
        return format_result.returncode

    lint_result = subprocess.run(
        ["uv", "run", "ruff", "check", "--fix", source_directory],
        cwd=project_directory,
        check=False,
    )
    if lint_result.returncode != 0:
        return lint_result.returncode

    python_format_result = subprocess.run(
        ["uv", "run", "ruff", "format", source_directory, "manage.py"],
        cwd=project_directory,
        check=False,
    )
    if python_format_result.returncode != 0:
        return python_format_result.returncode

    return 0


def _set_wagtail_site_name(settings_file: Path, site_name: str) -> None:
    """Replace Wagtail's package-style site name with a human-readable name."""
    content = settings_file.read_text()
    updated = re.sub(
        r"^WAGTAIL_SITE_NAME\s*=.*$",
        f"WAGTAIL_SITE_NAME = {json.dumps(site_name)}",
        content,
        flags=re.MULTILINE,
    )
    if updated != content:
        settings_file.write_text(updated)


def _write_agents_file(
    project_directory: Path,
    project_name: str,
    site_name: str,
    site_subfolder: Path | None,
    database: str,
    template: Path | None,
) -> None:
    """Write project guidance customized for the generated Wagtail layout."""
    agents_file = project_directory / "AGENTS.md"
    if agents_file.exists():
        return

    if site_subfolder is None:
        source_directory = "."
        settings_module = f"{project_name}.settings"
    else:
        source_directory = str(site_subfolder)
        settings_module = f"{'.'.join(site_subfolder.parts)}.settings"

    template_description = (
        f"custom template `{template}`"
        if template is not None
        else "the default Wagtail template"
    )
    agents_file.write_text(
        f"""# Project guidance

## Project

This is the Wagtail CMS project for **{site_name}**. It was generated from
{template_description}.

- Python project package: `{project_name}`
- Site source directory: `{source_directory}`
- Django settings package: `{settings_module}`
- Local Docker database: `{database}`
- Dependency manager: UV

## Commands

Run commands from the project root:

```shell
uv sync
uv run ruff check .
uv run ruff format --check .
uv run djangofmt .
docker compose up --build
docker compose run --rm web python manage.py check
docker compose run --rm web python manage.py test
```

Use `uv add` and `uv remove` to manage dependencies. Do not create or maintain a
`requirements.txt`; `pyproject.toml` and `uv.lock` are authoritative.

## Development guidance

- Keep settings in `{settings_module}` and preserve the existing environment split.
- Create and commit Django migrations whenever models change.
- Add tests for model, view, template, and page-behavior changes.
- Run the Django system check and relevant tests in Compose before finishing work.
- After cloning, run `uv run pre-commit install`. Pre-commit only checks files known
  to Git, so stage new files before expecting `--all-files` to include them.
- Use `docker compose down` to stop local services and `docker compose down --volumes`
  when the local {database} data should also be reset.
- Keep secrets out of version control and load deployment values from the environment.
"""
    )


def _write_readme_file(
    project_directory: Path,
    project_name: str,
    site_name: str,
    site_subfolder: Path | None,
    database: str,
) -> None:
    """Write setup and development instructions for the generated project."""
    source_directory = "." if site_subfolder is None else str(site_subfolder)
    settings_module = (
        f"{project_name}.settings"
        if site_subfolder is None
        else f"{'.'.join(site_subfolder.parts)}.settings"
    )
    database_name = "PostgreSQL" if database == "postgresql" else "MySQL"
    mysql_note = ""
    if database == "mysql":
        mysql_note = """

> [!NOTE]
> Django warns that MySQL cannot enforce Wagtail's conditional `WorkflowState`
> uniqueness constraint. This is a database limitation rather than a setup error.
"""

    (project_directory / "README.md").write_text(
        f"""# {site_name}

Wagtail CMS project generated with `wagtail-generate`.

- Python package: `{project_name}`
- Site source: `{source_directory}`
- Django settings: `{settings_module}`
- Local database: {database_name}
- Python: {TARGET_PYTHON_VERSION}

## Requirements

- [UV](https://docs.astral.sh/uv/)
- Docker with Compose support

## Docker setup

Copy the example environment file if you want to change credentials or forwarded
ports, then start the complete development environment:

```shell
cp .env.example .env
docker compose up --build
```

Compose waits for {database_name}, applies migrations, and serves Wagtail at
<http://localhost:8000>. Create an administrator in another terminal:

```shell
docker compose exec web python manage.py createsuperuser
```

Stop the services with `docker compose down`. Add `--volumes` to also delete the
local database data.
{mysql_note}

## Local UV setup

Start only the database in Docker, install the locked dependencies, migrate, and
run Django locally:

```shell
docker compose up -d db
uv sync
uv run python manage.py migrate
uv run python manage.py runserver
```

The settings default to the database exposed on `127.0.0.1`. Override
`DATABASE_NAME`, `DATABASE_USER`, `DATABASE_PASSWORD`, `DATABASE_HOST`, and
`DATABASE_PORT` when needed.

## Quality checks

```shell
uv run ruff check .
uv run ruff format --check .
uv run djangofmt .
uv run python manage.py test
```

Initialize version control and install the hooks after generation. Pre-commit's
`--all-files` option means all files known to Git, so the initial `git add` is
required:

```shell
git init
git add --all
uv run pre-commit install
uv run pre-commit run --all-files
```

If a formatter changes files during that first run, inspect the changes and run
`git add --all` again before committing.

Use `uv add` and `uv remove` for dependencies. `pyproject.toml` and `uv.lock` are
authoritative; this project intentionally does not use `requirements.txt`.
"""
    )


def _flatten_project_package(
    generated_directory: Path,
    project_name: str,
    destination_module: str,
) -> bool:
    """Move the nested Django project package into the selected source folder."""
    package_directory = generated_directory / project_name
    if not package_directory.is_dir():
        print(
            f"error: Wagtail did not generate the expected {project_name}/ package",
            file=sys.stderr,
        )
        return False

    conflicts = [
        child.name
        for child in package_directory.iterdir()
        if (generated_directory / child.name).exists()
    ]
    if conflicts:
        print(
            "error: refusing to overwrite generated code path(s): "
            + ", ".join(sorted(conflicts)),
            file=sys.stderr,
        )
        return False

    for child in package_directory.iterdir():
        child.replace(generated_directory / child.name)
    package_directory.rmdir()

    old_prefix = f"{project_name}."
    new_prefix = f"{destination_module}."
    for python_file in generated_directory.rglob("*.py"):
        content = python_file.read_text()
        updated = content.replace(old_prefix, new_prefix)
        for app_name in ("home", "search"):
            for suffix in (" ", "."):
                updated = updated.replace(
                    f"from {app_name}{suffix}",
                    f"from {destination_module}.{app_name}{suffix}",
                )
        if updated != content:
            python_file.write_text(updated)

    settings_file = generated_directory / "settings" / "base.py"
    settings = settings_file.read_text()
    for app_name in ("home", "search"):
        settings = settings.replace(
            f'"{app_name}"',
            f'"{destination_module}.{app_name}"',
        )
    settings_file.write_text(settings)

    home_app = generated_directory / "home" / "apps.py"
    app_config = home_app.read_text().replace(
        '    name = "home"',
        f'    name = "{destination_module}.home"',
    )
    home_app.write_text(app_config)

    return True
