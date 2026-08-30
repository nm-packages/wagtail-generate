"""Create a UV environment and run Wagtail's project-generation command."""

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT_FILES = (".dockerignore", "Dockerfile", "manage.py")


def run_wagtail_start(
    project_name: str,
    site_name: str | None = None,
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
        ["uv", "init", "--bare", "--no-workspace"],
        ["uv", "add", "wagtail"],
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
        for filename in ROOT_FILES:
            source = generated_directory / filename
            if source.exists():
                source.replace(project_directory / filename)
    else:
        _set_wagtail_site_name(
            project_directory / project_name / "settings" / "base.py",
            site_name or project_name.replace("_", " "),
        )
        (project_directory / "requirements.txt").unlink(missing_ok=True)

    _write_agents_file(
        project_directory=project_directory,
        project_name=project_name,
        site_name=site_name or project_name.replace("_", " ").title(),
        site_subfolder=site_subfolder,
        template=template,
    )

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
- Dependency manager: UV

## Commands

Run commands from the project root:

```shell
uv sync
uv run python manage.py check
uv run python manage.py migrate
uv run python manage.py test
uv run python manage.py runserver
```

Use `uv add` and `uv remove` to manage dependencies. Do not create or maintain a
`requirements.txt`; `pyproject.toml` and `uv.lock` are authoritative.

## Development guidance

- Keep settings in `{settings_module}` and preserve the existing environment split.
- Create and commit Django migrations whenever models change.
- Add tests for model, view, template, and page-behavior changes.
- Run `uv run python manage.py check` and the relevant tests before finishing work.
- Keep secrets out of version control and load deployment values from the environment.
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
