"""Generate local development, formatting, and database tooling."""

import re
from pathlib import Path

from wagtail_generate.rendering import render_template, template_text, write_template

TARGET_PYTHON_VERSION = "3.12"


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
) -> None:
    """Render Docker, Compose, formatter, pre-commit, and environment files."""
    docker_context = {
        "python_version": TARGET_PYTHON_VERSION,
        "settings_module": settings_module,
        "wsgi_module": settings_module.removesuffix(".settings"),
        "build_database_packages": (
            "libpq-dev"
            if database == "postgresql"
            else "default-libmysqlclient-dev pkg-config"
            if database == "mysql"
            else ""
        ),
        "runtime_database_packages": (
            "libpq5"
            if database == "postgresql"
            else "libmariadb3"
            if database == "mysql"
            else ""
        ),
    }
    project_context = {"project_name": project_name, "database": database}

    write_template(
        project_directory / "Dockerfile",
        "Dockerfile.jinja",
        docker_context,
    )
    write_template(
        project_directory / "compose.yaml",
        f"compose/{database}.yaml.jinja",
        project_context,
    )
    write_template(
        project_directory / ".env.example",
        f"env/{database}.example.jinja",
        project_context,
    )
    write_template(project_directory / ".gitignore", "static/gitignore")
    write_template(project_directory / ".dockerignore", "static/dockerignore")
    write_template(
        project_directory / "Makefile",
        "Makefile.jinja",
        project_context,
    )
    write_template(
        project_directory / ".pre-commit-config.yaml",
        "static/pre-commit-config.yaml",
    )
    if database == "mysql":
        write_template(
            project_directory / "docker" / "mysql-init.sh",
            "static/mysql-init.sh",
            mode=0o755,
        )

    _append_tool_configuration(project_directory / "pyproject.toml")


def database_driver(database: str) -> str | None:
    """Return the Python driver dependency for a selected database."""
    if database == "postgresql":
        return "psycopg[binary]"
    if database == "mysql":
        return "mysqlclient"
    return None


def _append_tool_configuration(pyproject: Path) -> None:
    content = pyproject.read_text()
    if "[tool.ruff]" not in content:
        pyproject.write_text(
            content.rstrip() + template_text("static/pyproject-tools.toml")
        )
