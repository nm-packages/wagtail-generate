"""Generate local development, formatting, and database tooling."""

import re
from dataclasses import dataclass
from pathlib import Path

from wagtail_generate.rendering import (
    RenderedFile,
    plan_template,
    render_template,
    write_rendered_files,
)


@dataclass(frozen=True)
class DeveloperToolingPlan:
    """Validated generated files and pyproject configuration."""

    files: tuple[RenderedFile, ...]
    pyproject_suffix: str


def configure_database(settings_file: Path, database: str, project_name: str) -> None:
    """Replace Wagtail's SQLite settings with a rendered database configuration."""
    content = settings_file.read_text()
    if database != "sqlite3" and "import os\n" not in content:
        content = content.replace(
            "from pathlib import Path\n",
            "import os\n\nfrom pathlib import Path\n",
        )

    if database == "postgresql" and '"django.contrib.postgres"' not in content:
        content = content.replace(
            "INSTALLED_APPS = [\n",
            'INSTALLED_APPS = [\n    "django.contrib.postgres",\n',
            1,
        )

    database_settings = render_template(
        f"database/{database}.py.jinja",
        {"project_name": project_name},
    )
    content, replacements = re.subn(
        r"^DATABASES = \{.*?^\}\n",
        database_settings,
        content,
        count=1,
        flags=re.MULTILINE | re.DOTALL,
    )
    if replacements != 1:
        raise ValueError("could not locate Wagtail's generated DATABASES setting")
    settings_file.write_text(content)


def write_developer_tooling(
    project_directory: Path,
    project_name: str,
    settings_module: str,
    database: str,
    python_version: str,
) -> None:
    """Render Docker, Compose, formatter, pre-commit, and environment files."""
    plan = build_developer_tooling_plan(
        project_name=project_name,
        settings_module=settings_module,
        database=database,
        python_version=python_version,
    )
    apply_developer_tooling_plan(project_directory, plan)


def build_developer_tooling_plan(
    project_name: str,
    settings_module: str,
    database: str,
    python_version: str,
) -> DeveloperToolingPlan:
    """Render all developer-tooling files without writing to disk."""
    docker_context = {
        "python_version": python_version,
        "settings_module": settings_module,
        "build_database_packages": (
            "libpq-dev"
            if database == "postgresql"
            else "default-libmysqlclient-dev pkg-config"
            if database == "mysql"
            else ""
        ),
    }
    project_context = {"project_name": project_name, "database": database}
    files = [
        plan_template("Dockerfile", "Dockerfile.jinja", docker_context),
        plan_template(
            "compose.yaml",
            f"compose/{database}.yaml.jinja",
            project_context,
        ),
        plan_template(
            ".env.example",
            f"env/{database}.example.jinja",
            project_context,
        ),
        plan_template(".gitignore", "static/gitignore"),
        plan_template(".dockerignore", "static/dockerignore"),
        plan_template("Makefile", "Makefile.jinja", project_context),
        plan_template(".pre-commit-config.yaml", "static/pre-commit-config.yaml"),
        plan_template(
            "scripts/check_django_templates.py",
            "static/check_django_templates.py",
        ),
    ]
    if database == "mysql":
        files.append(
            plan_template(
                "docker/mysql-init.sh",
                "static/mysql-init.sh",
                mode=0o755,
            )
        )

    ruff_target = "py" + python_version.replace(".", "")
    return DeveloperToolingPlan(
        files=tuple(files),
        pyproject_suffix=render_template(
            "pyproject-tools.toml.jinja",
            {"ruff_target": ruff_target},
        ),
    )


def apply_developer_tooling_plan(
    project_directory: Path,
    plan: DeveloperToolingPlan,
) -> None:
    """Apply a validated developer-tooling plan to a generated project."""
    write_rendered_files(project_directory, plan.files)
    _append_tool_configuration(
        project_directory / "pyproject.toml",
        plan.pyproject_suffix,
    )


def database_driver(database: str) -> str | None:
    """Return the Python driver dependency for a selected database."""
    if database == "postgresql":
        return "psycopg[binary]"
    if database == "mysql":
        return "mysqlclient"
    return None


def _append_tool_configuration(pyproject: Path, configuration: str) -> None:
    content = pyproject.read_text()
    if "[tool.ruff]" not in content:
        pyproject.write_text(content.rstrip() + configuration)
