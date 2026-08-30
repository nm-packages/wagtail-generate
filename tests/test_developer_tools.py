"""Tests for generated development tooling."""

from pathlib import Path

from wagtail_generate.developer_tools import (
    configure_database,
    database_driver,
    write_developer_tooling,
)


def generated_settings() -> str:
    return """from pathlib import Path

INSTALLED_APPS = [
    "home",
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": "db.sqlite3",
    }
}
"""


def test_mysql_settings_and_tooling_are_consistent(tmp_path: Path) -> None:
    settings = tmp_path / "base.py"
    settings.write_text(generated_settings())
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "example"\nversion = "0.1.0"\n'
    )

    configure_database(settings, "mysql", "example")
    write_developer_tooling(
        project_directory=tmp_path,
        project_name="example",
        settings_module="src.settings",
        database="mysql",
        python_version="3.14",
    )

    content = settings.read_text()
    assert '"ENGINE": "django.db.backends.mysql"' in content
    assert '"OPTIONS": {"charset": "utf8mb4"}' in content
    assert "django.contrib.postgres" not in content
    assert database_driver("mysql") == "mysqlclient"
    assert "mysql:8.4" in (tmp_path / "compose.yaml").read_text()
    dockerfile = (tmp_path / "Dockerfile").read_text()
    assert "default-libmysqlclient-dev" in dockerfile
    assert "FROM python:3.14-slim AS development" in dockerfile
    assert "gunicorn" not in dockerfile
    assert ".production" not in dockerfile
    makefile = (tmp_path / "Makefile").read_text()
    assert "dev: ## Run Wagtail locally" in makefile
    assert "docker compose up -d --wait db" in makefile
    assert "-include .env" in makefile
    assert "DATABASE_HOST=127.0.0.1 uv run python manage.py migrate" in makefile
    assert "uv run python scripts/check_django_templates.py" in makefile
    assert "uv run python manage.py runserver" in makefile
    assert "check: lint test" in makefile
    assert "docker compose build --pull" in makefile
    assert 'target-version = "py314"' in (tmp_path / "pyproject.toml").read_text()
    assert "MYSQL_ROOT_PASSWORD" in (tmp_path / ".env.example").read_text()
    compose = (tmp_path / "compose.yaml").read_text()
    assert '"${DATABASE_PORT:-3306}:3306"' in compose
    environment = (tmp_path / ".env.example").read_text()
    assert "DATABASE_HOST=127.0.0.1" in environment
    assert "DATABASE_FORWARD_PORT" not in environment
    assert "docker/mysql-init.sh" in compose
    mysql_init = tmp_path / "docker" / "mysql-init.sh"
    assert mysql_init.stat().st_mode & 0o111
    assert "test_${escaped_database}" in mysql_init.read_text()


def test_postgresql_adds_required_django_app(tmp_path: Path) -> None:
    settings = tmp_path / "base.py"
    settings.write_text(generated_settings())

    configure_database(settings, "postgresql", "example")

    content = settings.read_text()
    assert '"ENGINE": "django.db.backends.postgresql"' in content
    assert '"django.contrib.postgres"' in content
    assert database_driver("postgresql") == "psycopg[binary]"
    assert not (tmp_path / "docker" / "mysql-init.sh").exists()


def test_sqlite_needs_no_server_or_database_driver(tmp_path: Path) -> None:
    settings = tmp_path / "base.py"
    settings.write_text(generated_settings())
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "example"\nversion = "0.1.0"\n'
    )

    configure_database(settings, "sqlite3", "example")
    write_developer_tooling(
        project_directory=tmp_path,
        project_name="example",
        settings_module="example.settings",
        database="sqlite3",
        python_version="3.15",
    )

    content = settings.read_text()
    assert '"ENGINE": "django.db.backends.sqlite3"' in content
    assert '"NAME": BASE_DIR / "db.sqlite3"' in content
    assert "import os" not in content
    assert database_driver("sqlite3") is None

    compose = (tmp_path / "compose.yaml").read_text()
    assert "  db:" not in compose
    assert "DATABASE_HOST" not in compose
    makefile = (tmp_path / "Makefile").read_text()
    assert "dev: ## Run Wagtail locally" in makefile
    assert "docker compose up -d --wait db" not in makefile
    assert "-include .env" not in makefile
    assert "DATABASE_HOST=127.0.0.1" not in makefile
    assert "uv run python scripts/check_django_templates.py" in makefile
    assert "uv run python manage.py runserver" in makefile
    assert (tmp_path / ".env.example").read_text() == "WEB_PORT=8000\n"
    dockerfile = (tmp_path / "Dockerfile").read_text()
    assert "libpq" not in dockerfile
    assert "default-libmysqlclient" not in dockerfile
    assert "gunicorn" not in dockerfile
    assert "FROM python:3.15-slim AS development" in dockerfile
    assert 'target-version = "py315"' in (tmp_path / "pyproject.toml").read_text()
    assert (tmp_path / "scripts" / "check_django_templates.py").is_file()
