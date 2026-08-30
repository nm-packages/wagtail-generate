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
from wagtail_generate.rendering import write_template

ROOT_FILES = (".dockerignore", "Dockerfile", "manage.py")


def run_wagtail_start(
    project_name: str,
    site_name: str | None = None,
    database: str = "sqlite3",
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

    runtime_dependencies = ["wagtail", "gunicorn"]
    driver = database_driver(database)
    if driver is not None:
        runtime_dependencies.append(driver)

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
        ["uv", "add", *runtime_dependencies],
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
    write_template(
        agents_file,
        "AGENTS.md.jinja",
        {
            "site_name": site_name,
            "template_description": template_description,
            "project_name": project_name,
            "source_directory": source_directory,
            "settings_module": settings_module,
            "database": database,
        },
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
    write_template(
        project_directory / "README.md",
        "README.md.jinja",
        {
            "site_name": site_name,
            "project_name": project_name,
            "source_directory": source_directory,
            "settings_module": settings_module,
            "database": database,
            "database_name": {
                "sqlite3": "SQLite",
                "postgresql": "PostgreSQL",
                "mysql": "MySQL",
            }[database],
            "python_version": TARGET_PYTHON_VERSION,
        },
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
